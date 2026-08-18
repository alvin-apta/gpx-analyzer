import json
import httpx
from .config import settings
from .gpx import Point

COSTING = {"car": "auto", "motorcycle": "motorcycle", "bicycle": "bicycle", "foot": "pedestrian"}

def provider_error(exc: Exception) -> RuntimeError:
    if isinstance(exc, httpx.TimeoutException):
        return RuntimeError(f"Valhalla timed out while contacting {exc.request.url}")
    if isinstance(exc, httpx.HTTPStatusError):
        return RuntimeError(f"Valhalla returned HTTP {exc.response.status_code} from {exc.request.url}")
    return RuntimeError(f"Valhalla request failed: {type(exc).__name__}: {exc}")

async def valhalla_match(points: list[Point], mode: str) -> dict:
    # A vehicle-history file can contain hours with no observations. Treat those
    # as separate traces instead of inventing a route through the missing period.
    groups: list[list[Point]] = [[]]
    for point in points:
        previous = groups[-1][-1] if groups[-1] else None
        gap = (point.time - previous.time).total_seconds() if previous and point.time and previous.time else 0
        if previous and gap > 15 * 60: groups.append([])
        groups[-1].append(point)
    segments, snapped_segments, edges, offsets, limits, total_distance = [], [], [], [], [], 0.0
    try:
        async with httpx.AsyncClient(timeout=90) as client:
          for group in groups:
            if len(group) < 2:
                offsets.extend([None] * len(group)); continue
            step = max(1, len(group) // 800)
            sampled = group[::step]
            if sampled[-1] is not group[-1]: sampled.append(group[-1])
            shape = [{"lat": p.lat, "lon": p.lon, **({"time": int(p.time.timestamp())} if p.time else {})} for p in sampled]
            payload = {"shape": shape, "costing": COSTING[mode], "shape_match": "map_snap", "units": "kilometers",
              "filters": {"action": "include", "attributes": ["shape", "edge.length", "edge.names", "edge.speed_limit",
              "edge.traversability", "edge.forward", "edge.way_id", "edge.begin_shape_index", "edge.end_shape_index",
              "matched.point", "matched.distance_from_trace_point"]}}
            response = await client.post(f"{settings.valhalla_url.rstrip('/')}/trace_attributes", json=payload)
            if response.status_code == 400:
                offsets.extend([None] * len(group))
                continue
            response.raise_for_status(); data = response.json()
            if data.get("shape"): segments.append(data["shape"])
            matched = data.get("matched_points", [])
            snapped = [{"lat": point["lat"], "lon": point["lon"]} for point in matched
                       if point.get("lat") is not None and point.get("lon") is not None]
            if len(snapped) > 1: snapped_segments.append(snapped)
            group_offsets = [p.get("distance_from_trace_point") for p in matched]
            offsets.extend((group_offsets + [None] * len(group))[:len(group)])
            for edge in data.get("edges", []):
                names = edge.get("names") or []
                normalized = {**edge, "name": names[0] if names else None, "wrong_way": False}
                edges.append(normalized); limits.append(edge.get("speed_limit"))
                total_distance += (edge.get("length") or 0) * 1000
    except httpx.HTTPError as exc: raise provider_error(exc) from exc
    if not segments:
        raise RuntimeError("Valhalla could not match any continuous portion of this track")
    valid_offsets = [value for value in offsets if value is not None]
    return {"segments": segments, "snapped_segments": snapped_segments, "edges": edges, "offsets": offsets, "speed_limits": limits,
            "distance_m": total_distance,
            "quality": max(0, 1 - (sum(valid_offsets) / max(len(valid_offsets), 1)) / 100)}

async def valhalla_reference(points: list[Point], mode: str) -> dict:
    payload = {"locations": [{"lat": points[0].lat, "lon": points[0].lon},
                             {"lat": points[-1].lat, "lon": points[-1].lon}],
               "costing": COSTING[mode], "units": "kilometers"}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{settings.valhalla_url.rstrip('/')}/route", json=payload)
            response.raise_for_status(); data = response.json()
    except httpx.HTTPError as exc: raise provider_error(exc) from exc
    trip = data.get("trip", {}); legs = trip.get("legs", [])
    return {"distance_m": (trip.get("summary", {}).get("length") or 0) * 1000,
            "encoded": legs[0].get("shape") if legs else None}

async def ollama_explain(summary: dict) -> str:
    prompt = ("You are explaining a deterministic GPX safety analysis. Do not invent or modify findings. "
              "Write a concise analyst summary with caveats. Data:\n" + json.dumps(summary))
    async with httpx.AsyncClient(timeout=90) as client:
        models = await client.get(f"{settings.ollama_url.rstrip('/')}/models")
        models.raise_for_status()
        ids = [x.get("id") for x in models.json().get("data", [])]
        if settings.ollama_model not in ids:
            raise RuntimeError(f"Required model {settings.ollama_model} is not installed")
        response = await client.post(f"{settings.ollama_url.rstrip('/')}/chat/completions", json={
            "model": settings.ollama_model, "temperature": 0.2,
            "messages": [{"role": "user", "content": prompt}]})
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
