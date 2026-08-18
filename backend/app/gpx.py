import math
from dataclasses import dataclass
from datetime import datetime
from defusedxml import ElementTree as ET
from pyproj import Geod

GEOD = Geod(ellps="WGS84")

@dataclass
class Point:
    lat: float
    lon: float
    ele: float | None
    time: datetime | None
    segment: int

def parse_gpx(data: bytes) -> tuple[str | None, list[Point]]:
    try:
        root = ET.fromstring(data)
    except Exception as exc:
        raise ValueError(f"Invalid GPX XML: {exc}") from exc
    if root.tag.split("}")[-1] != "gpx":
        raise ValueError("The uploaded file is not GPX")
    name = next((n.text for n in root.iter() if n.tag.split("}")[-1] == "name" and n.text), None)
    points: list[Point] = []
    segment = -1
    for node in root.iter():
        kind = node.tag.split("}")[-1]
        if kind == "trkseg":
            segment += 1
        if kind != "trkpt":
            continue
        try:
            lat, lon = float(node.attrib["lat"]), float(node.attrib["lon"])
        except (KeyError, ValueError) as exc:
            raise ValueError("A track point has invalid coordinates") from exc
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("A track point is outside valid coordinate bounds")
        ele = None; timestamp = None
        for child in node:
            label = child.tag.split("}")[-1]
            if label == "ele" and child.text:
                try: ele = float(child.text)
                except ValueError: pass
            elif label == "time" and child.text:
                try: timestamp = datetime.fromisoformat(child.text.replace("Z", "+00:00"))
                except ValueError: pass
        points.append(Point(lat, lon, ele, timestamp, max(segment, 0)))
    if len(points) < 2:
        raise ValueError("A GPX track must contain at least two track points")
    if len(points) > 250_000:
        raise ValueError("GPX exceeds the 250,000 point limit")
    return name, points

def distance_m(a: Point, b: Point) -> float:
    return abs(GEOD.inv(a.lon, a.lat, b.lon, b.lat)[2])

def bearing(a: Point, b: Point) -> float:
    return GEOD.inv(a.lon, a.lat, b.lon, b.lat)[0] % 360

def angle_delta(a: float, b: float) -> float:
    return abs((b - a + 180) % 360 - 180)

def serialize(points: list[Point]) -> list[dict]:
    return [{"lat": p.lat, "lon": p.lon, "ele": p.ele,
             "time": p.time.isoformat() if p.time else None, "segment": p.segment}
            for p in points]

def deserialize(data: list[dict]) -> list[Point]:
    return [Point(p["lat"], p["lon"], p.get("ele"),
                  datetime.fromisoformat(p["time"]) if p.get("time") else None,
                  p.get("segment", 0)) for p in data]

def decode_polyline(encoded: str | None, precision: int = 6) -> list[dict]:
    """Decode Valhalla's encoded polyline into latitude/longitude objects."""
    if not encoded:
        return []
    coordinates, index, lat, lon, factor = [], 0, 0, 0, 10 ** precision
    while index < len(encoded):
        deltas = []
        for _ in range(2):
            result = shift = 0
            while True:
                if index >= len(encoded):
                    raise ValueError("Truncated encoded polyline")
                value = ord(encoded[index]) - 63
                index += 1
                result |= (value & 0x1F) << shift
                shift += 5
                if value < 0x20:
                    break
            deltas.append(~(result >> 1) if result & 1 else result >> 1)
        lat += deltas[0]; lon += deltas[1]
        coordinates.append({"lat": lat / factor, "lon": lon / factor})
    return coordinates

def basic_metrics(points: list[Point]) -> dict:
    distances, speeds, headings = [], [], []
    total = 0.0
    for a, b in zip(points, points[1:]):
        d = distance_m(a, b) if a.segment == b.segment else 0
        total += d; distances.append(d); headings.append(bearing(a, b))
        dt = (b.time - a.time).total_seconds() if a.time and b.time else 0
        speeds.append(d / dt * 3.6 if dt > 0 else None)
    valid = [s for s in speeds if s is not None]
    duration = ((points[-1].time - points[0].time).total_seconds()
                if points[0].time and points[-1].time else None)
    return {"raw_distance_m": total, "straight_distance_m": distance_m(points[0], points[-1]),
            "duration_s": duration, "max_speed_kmh": max(valid) if valid else None,
            "distances": distances, "speeds": speeds, "headings": headings}
