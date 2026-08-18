"""Generate dense, road-following Jabodetabek demo GPX files from Valhalla routes."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
import httpx

from app.gpx import decode_polyline

VALHALLA = "https://valhalla1.openstreetmap.de"
ROOT = Path(__file__).resolve().parents[1] / "samples"
ROUTES = {
    "jakarta": ("mixed-car.gpx", "Central Jakarta Dense Road Demo", "auto", (-6.1754, 106.8272), (-6.1932, 106.8231), 42),
    "bogor": ("normal-bike.gpx", "Bogor Dense Bicycle Baseline", "bicycle", (-6.5951, 106.7931), (-6.6033, 106.7967), 18),
    "depok": ("mixed-car.gpx", "Depok Dense Road Demo", "auto", (-6.3629, 106.8242), (-6.3907, 106.8254), 38),
    "tangerang": ("mixed-car.gpx", "Tangerang Dense Motorcycle Demo", "motorcycle", (-6.1783, 106.6319), (-6.1923, 106.6389), 35),
    "bekasi": ("mixed-car.gpx", "Bekasi Dense Road Demo", "auto", (-6.2383, 106.9756), (-6.2496, 107.0010), 40),
}

def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    x = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371000 * 2 * math.asin(math.sqrt(x))

def densify(points: list[dict], spacing: float = 8) -> list[tuple[float, float]]:
    dense: list[tuple[float, float]] = []
    for left, right in zip(points, points[1:]):
        a, b = (left["lat"], left["lon"]), (right["lat"], right["lon"])
        count = max(1, math.ceil(distance(a, b) / spacing))
        for i in range(count):
            t = i / count
            dense.append((a[0] + (b[0]-a[0])*t, a[1] + (b[1]-a[1])*t))
    dense.append((points[-1]["lat"], points[-1]["lon"]))
    return dense

def route_shape(costing: str, start, end) -> list[tuple[float, float]]:
    payload = {"locations": [{"lat": start[0], "lon": start[1]}, {"lat": end[0], "lon": end[1]}],
               "costing": costing, "units": "kilometers"}
    response = httpx.post(f"{VALHALLA}/route", json=payload, timeout=60)
    response.raise_for_status()
    encoded = response.json()["trip"]["legs"][0]["shape"]
    return densify(decode_polyline(encoded), 8)

def write_gpx(path: Path, name: str, points: list[tuple[float, float]], speed_kmh: float, mixed: bool):
    timestamp = datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc)
    rows = []
    previous = points[0]
    for index, point in enumerate(points):
        if index:
            seconds = max(1.0, distance(previous, point) / (speed_kmh / 3.6))
            # Timing-only anomalies retain road-following geometry.
            if mixed and index in range(len(points)//3, len(points)//3 + 4): seconds *= .18
            if mixed and index in range(len(points)*2//3, len(points)*2//3 + 3): seconds *= 3.5
            timestamp += timedelta(seconds=seconds)
        rows.append(f'<trkpt lat="{point[0]:.7f}" lon="{point[1]:.7f}"><time>{timestamp.isoformat().replace("+00:00", "Z")}</time></trkpt>')
        previous = point
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="GPX Inspector" xmlns="http://www.topografix.com/GPX/1/1"><trk>'
    xml += f"<name>{name}</name><trkseg>\n" + "\n".join(rows) + "\n</trkseg></trk></gpx>\n"
    path.write_text(xml, encoding="utf-8")
    return len(points)

def main():
    for city, (filename, name, costing, start, end, speed) in ROUTES.items():
        points = route_shape(costing, start, end)
        count = write_gpx(ROOT / city / filename, name, points, speed, city != "bogor")
        print(f"{city}: {count} points")

if __name__ == "__main__":
    main()
