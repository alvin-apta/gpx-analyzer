import json
import httpx
from .config import settings
from .gpx import Point

COSTING = {"car": "auto", "motorcycle": "motorcycle", "bicycle": "bicycle", "foot": "pedestrian"}

async def valhalla_match(points: list[Point], mode: str) -> dict:
    # Keep payload modest for public/demo endpoints while preserving endpoints.
    step = max(1, len(points) // 800)
    sampled = points[::step]
    if sampled[-1] is not points[-1]: sampled.append(points[-1])
    shape = [{"lat": p.lat, "lon": p.lon, **({"time": int(p.time.timestamp())} if p.time else {})} for p in sampled]
    payload = {"shape": shape, "costing": COSTING[mode], "shape_match": "map_snap", "units": "kilometers",
      "filters": {"action": "include", "attributes": ["shape", "edge.length", "edge.names", "edge.speed_limit",
      "edge.traversability", "edge.forward", "edge.way_id", "edge.begin_shape_index", "edge.end_shape_index",
      "matched.point", "matched.distance_from_trace_point"]}}
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(f"{settings.valhalla_url.rstrip('/')}/trace_attributes", json=payload)
        response.raise_for_status(); data = response.json()
    matched = data.get("matched_points", [])
    offsets = [p.get("distance_from_trace_point") for p in matched]
    edges = []
    for e in data.get("edges", []):
        names = e.get("names") or []
        edges.append({**e, "name": names[0] if names else None, "wrong_way": False})
    return {"shape": data.get("shape"), "edges": edges, "offsets": offsets,
            "speed_limits": [e.get("speed_limit") for e in edges],
            "distance_m": sum((e.get("length") or 0) * 1000 for e in edges),
            "quality": max(0, 1 - (sum(o or 0 for o in offsets) / max(len(offsets), 1)) / 100)}

async def valhalla_reference(points: list[Point], mode: str) -> dict:
    payload = {"locations": [{"lat": points[0].lat, "lon": points[0].lon},
                             {"lat": points[-1].lat, "lon": points[-1].lon}],
               "costing": COSTING[mode], "units": "kilometers"}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(f"{settings.valhalla_url.rstrip('/')}/route", json=payload)
        response.raise_for_status(); data = response.json()
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
