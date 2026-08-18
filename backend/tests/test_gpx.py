from datetime import datetime, timedelta, timezone
from pathlib import Path
from app.gpx import Point, parse_gpx, parse_vehicle_csv, basic_metrics
from app.analysis import analyze

def test_parse_and_analyze_sample():
    data = Path("samples/jakarta/mixed-car.gpx").read_bytes()
    name, points = parse_gpx(data)
    metrics = basic_metrics(points)
    assert name == "Central Jakarta Dense Road Demo"
    assert len(points) > 100
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

def test_parse_vehicle_history_csv_uses_reported_speed_and_sorts_time():
    data = """Tanggal,Plat Nomor,Jenis Kendaraan,Imei,Tipe Perangkat,Pengemudi,Garis Lintang,Garis Bujur,Lokasi,Geolokasi,Kecepatan (Km/Jam),ACC
29 Jul 2026 10:05:00 WIB,B 1234 CD,Truck,1,Tracker,-,-6.2,106.8,Second,-,42.00,Nyala
29 Jul 2026 10:00:00 WIB,B 1234 CD,Truck,1,Tracker,-,-6.21,106.79,First,-,20.00,Nyala
""".encode()
    name, points = parse_vehicle_csv(data)
    metrics = basic_metrics(points)
    assert name == "B 1234 CD — 29 Jul 2026"
    assert points[0].location == "First"
    assert points[0].time < points[1].time
    assert points[1].speed_kmh == 42
    assert metrics["max_speed_kmh"] == 42

def test_sparse_reversal_is_low_confidence_and_single_offset_is_suppressed():
    start = datetime(2026, 7, 29, tzinfo=timezone.utc)
    points = [
        Point(0, 0, None, start, 0, 20),
        Point(0, .01, None, start + timedelta(minutes=5), 0, 20),
        Point(0, 0, None, start + timedelta(minutes=10), 0, 20),
    ]
    findings = analyze(points, "car", {"offsets": [0, 100, 0], "edges": [], "speed_limits": []})
    reversal = next(item for item in findings if item["category"] == "direction_reversal")
    assert reversal["severity"] == "low"
    assert reversal["confidence"] < .5
    assert not any(item["category"] == "off_road" for item in findings)
