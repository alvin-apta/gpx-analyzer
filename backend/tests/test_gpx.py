from pathlib import Path
from app.gpx import parse_gpx, basic_metrics
from app.analysis import analyze

def test_parse_and_analyze_sample():
    data = Path("samples/jakarta/mixed-car.gpx").read_bytes()
    name, points = parse_gpx(data)
    metrics = basic_metrics(points)
    assert name == "Central Jakarta Mixed Demo"
    assert len(points) == 7
    assert metrics["raw_distance_m"] > 1000
    assert metrics["max_speed_kmh"] > 140
    assert any(f["category"] == "impossible_speed" for f in analyze(points, "car"))

def test_rejects_non_gpx():
    try:
        parse_gpx(b"<root/>")
        assert False
    except ValueError as exc:
        assert "not GPX" in str(exc)

def test_missing_time_disables_speed_only():
    xml=b'''<gpx version="1.1"><trk><trkseg><trkpt lat="0" lon="0"/><trkpt lat="0" lon="0.001"/></trkseg></trk></gpx>'''
    _, points=parse_gpx(xml)
    metrics=basic_metrics(points)
    assert metrics["raw_distance_m"] > 100
    assert metrics["max_speed_kmh"] is None
