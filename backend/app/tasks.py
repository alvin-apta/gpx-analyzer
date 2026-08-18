import asyncio
from sqlalchemy import delete
from .database import SessionLocal
from .models import Trip, Finding
from .gpx import parse_track, serialize, basic_metrics
from .analysis import analyze
from .providers import valhalla_match, valhalla_reference

def process_trip(trip_id: str):
    with SessionLocal() as db:
        trip = db.get(Trip, trip_id)
        if not trip: return
        trip.status = "processing"; db.commit()
        try:
            trip.error = None
            data = open(trip.source_path, "rb").read()
            _, points = parse_track(data, trip.source_path); metrics = basic_metrics(points)
            trip.points_json = serialize(points); trip.point_count = len(points)
            for key in ("raw_distance_m", "straight_distance_m", "duration_s", "max_speed_kmh"):
                setattr(trip, key, metrics[key])
            match = None
            try:
                trip.matched_json = {}; trip.reference_json = {}
                trip.matched_distance_m = None; trip.route_distance_m = None; trip.match_quality = None
                match = asyncio.run(valhalla_match(points, trip.mode))
                trip.matched_distance_m = match["distance_m"]
                trip.match_quality = match["quality"]
                # Shape is stored encoded; raw points remain usable if decoding is unavailable.
                trip.matched_json = {"segments": match.get("segments", []),
                                     "snapped_segments": match.get("snapped_segments", [])}
                reference = asyncio.run(valhalla_reference(points, trip.mode))
                trip.route_distance_m = reference["distance_m"]
                trip.reference_json = {"encoded": reference.get("encoded")}
            except Exception as exc:
                trip.error = f"Map matching unavailable: {exc}"
            db.execute(delete(Finding).where(Finding.trip_id == trip.id))
            for item in analyze(points, trip.mode, match): db.add(Finding(trip_id=trip.id, **item))
            trip.status = "complete"; db.commit()
        except Exception as exc:
            trip.status = "failed"; trip.error = str(exc); db.commit()
