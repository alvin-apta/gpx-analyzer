from dataclasses import dataclass
from statistics import median
from .gpx import Point, basic_metrics, angle_delta

PRESETS = {
    "car": {"speed": 140, "accel": 4.5, "brake": -6.0, "turn": 100, "idle": 180},
    "motorcycle": {"speed": 130, "accel": 5.5, "brake": -7.0, "turn": 115, "idle": 180},
    "bicycle": {"speed": 55, "accel": 3.0, "brake": -4.0, "turn": 125, "idle": 300},
    "foot": {"speed": 15, "accel": 2.0, "brake": -3.0, "turn": 145, "idle": 600},
}

def summarize_available_data(points: list[Point]) -> dict:
    speeds = [point.speed_kmh for point in points if point.speed_kmh is not None]
    ordered = sorted(speeds)
    gaps, long_gap_s, sessions = [], 0.0, 1 if points else 0
    for previous, point in zip(points, points[1:]):
        gap = (point.time - previous.time).total_seconds() if point.time and previous.time else 0
        gaps.append(gap)
        if gap > 15 * 60: long_gap_s += gap; sessions += 1
    stops, start = [], None
    for index, point in enumerate(points):
        stopped = point.speed_kmh is not None and point.speed_kmh <= 3
        prior_gap = ((point.time - points[index-1].time).total_seconds()
                     if index and point.time and points[index-1].time else 0)
        if stopped and (start is None or prior_gap > 15 * 60): start = index
        if start is not None and (not stopped or index == len(points) - 1 or prior_gap > 15 * 60):
            end = index if stopped and index == len(points) - 1 else index - 1
            duration = ((points[end].time - points[start].time).total_seconds()
                        if end >= start and points[end].time and points[start].time else 0)
            if end > start and duration >= 5 * 60:
                stops.append({"start_index": start, "end_index": end, "duration_s": duration,
                              "location": points[start].location, "acc_on": points[start].ignition == "Nyala"})
            start = index if stopped and prior_gap > 15 * 60 else None
    geofences = {}
    for point in points:
        if point.geofence: geofences[point.geofence] = geofences.get(point.geofence, 0) + 1
    return {
        "speed": {"average_kmh": sum(speeds) / len(speeds) if speeds else None,
                  "median_kmh": median(speeds) if speeds else None,
                  "p95_kmh": ordered[int(.95 * (len(ordered) - 1))] if ordered else None,
                  "zero_speed_points": sum(value == 0 for value in speeds)},
        "sampling": {"median_interval_s": median(gaps) if gaps else None,
                     "long_gap_count": sum(gap > 15 * 60 for gap in gaps), "long_gap_s": long_gap_s},
        "ignition": {"on_points": sum(point.ignition == "Nyala" for point in points),
                     "off_points": sum(point.ignition == "Mati" for point in points)},
        "activity_sessions": sessions, "stop_candidates": stops, "geofence_observations": geofences,
    }

def severity(ratio: float) -> str:
    return "critical" if ratio >= 1.8 else "high" if ratio >= 1.4 else "medium" if ratio >= 1.15 else "low"

def finding(category, index, measured, threshold, unit, title, explanation, confidence=.85, span=1, evidence=None, severity_override=None):
    return {"category": category, "start_index": index, "end_index": index + span,
            "measured_value": round(measured, 2), "threshold": threshold, "unit": unit,
            "severity": severity_override or severity(abs(measured) / max(abs(threshold), .01)), "confidence": confidence,
            "title": title, "explanation": explanation, "evidence": evidence or {}}

def analyze(points: list[Point], mode: str, match: dict | None = None) -> list[dict]:
    preset = PRESETS[mode]; m = basic_metrics(points); results = []
    speeds = m["speeds"]
    for i, speed in enumerate(speeds):
        if speed is not None and speed > preset["speed"]:
            results.append(finding("impossible_speed", i, speed, preset["speed"], "km/h",
                "Unusually high speed", "Observed speed exceeds the plausible preset for this transport mode."))
    for i in range(1, len(speeds)):
        if speeds[i] is None or speeds[i-1] is None or not points[i].time or not points[i+1].time: continue
        dt = (points[i+1].time - points[i].time).total_seconds()
        if dt <= 0: continue
        accel = (speeds[i] - speeds[i-1]) / 3.6 / dt
        threshold = preset["accel"] if accel >= 0 else preset["brake"]
        if accel > preset["accel"] or accel < preset["brake"]:
            results.append(finding("sudden_acceleration" if accel > 0 else "sudden_braking", i,
                accel, threshold, "m/s²", "Sudden acceleration" if accel > 0 else "Sudden braking",
                "Speed changed more quickly than the fixed mode preset allows.", .8))
    for i in range(1, len(m["headings"])):
        turn = angle_delta(m["headings"][i-1], m["headings"][i])
        if turn > preset["turn"] and (speeds[i] or 0) > (8 if mode in ("car", "motorcycle") else 3):
            before = (points[i].time - points[i-1].time).total_seconds() if points[i].time and points[i-1].time else None
            after = (points[i+1].time - points[i].time).total_seconds() if points[i+1].time and points[i].time else None
            sparse = before is None or after is None or max(before, after) > 60
            results.append(finding("direction_reversal" if sparse else "sudden_direction_change", i, turn,
                150 if sparse else preset["turn"], "degrees",
                "Direction reversal — review route" if sparse else "Sudden direction change",
                "The sampled path reverses direction, but the multi-minute gap cannot show whether this was abrupt, required by the route, or a GPS artifact."
                if sparse else "Closely spaced track points show a sharp heading change while moving.",
                .45 if sparse else .72, evidence={"sample_gap_before_s": before, "sample_gap_after_s": after},
                severity_override="low" if sparse else None))
    if match:
        offsets = match.get("offsets", [])
        threshold = 75 if mode in ("car", "motorcycle") else 50
        for i, value in enumerate(offsets):
            adjacent_offset = any(0 <= j < len(offsets) and offsets[j] is not None and offsets[j] > threshold
                                  for j in (i - 1, i + 1))
            moving = i < len(points) and (points[i].speed_kmh is None or points[i].speed_kmh > 5)
            if value is not None and value > threshold and adjacent_offset and moving:
                results.append(finding("off_road", i, value, threshold, "m", "Sustained road offset — review",
                    "Consecutive moving samples are offset from the mapped road. GPS accuracy, private access roads, and incomplete OSM data remain possible explanations.",
                    .6, severity_override="low"))
        for edge in match.get("edges", []):
            if edge.get("traversability") in ("forward", "backward") and edge.get("wrong_way"):
                idx = edge.get("begin_shape_index", 0)
                results.append(finding("possible_wrong_way", idx, 1, 1, "flag", "Possible wrong-way movement",
                    "Travel direction appears inconsistent with this edge's permitted direction.", .65,
                    evidence={"way_id": edge.get("way_id"), "road": edge.get("name")}))
        limits = match.get("speed_limits", [])
        for i, limit in enumerate(limits):
            if i < len(speeds) and limit and speeds[i] and speeds[i] > limit * 1.1:
                results.append(finding("speeding", i, speeds[i], limit, "km/h", "Speed above mapped limit",
                    "Calculated track speed is above the mapped road speed limit plus tolerance.", .78))
    # Collapse near-duplicate detector hits.
    dedup = {}
    for item in results:
        key = (item["category"], item["start_index"] // 3)
        if key not in dedup or item["confidence"] > dedup[key]["confidence"]: dedup[key] = item
    return list(dedup.values())
