import csv, io, json
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

def csv_export(trip) -> bytes:
    out = io.StringIO(); w = csv.writer(out)
    w.writerow(["category", "title", "severity", "confidence", "start_index", "end_index", "measured", "threshold", "unit"])
    for f in trip.findings:
        w.writerow([f.category, f.title, f.severity, f.confidence, f.start_index, f.end_index,
                    f.measured_value, f.threshold, f.unit])
    return out.getvalue().encode()

def geojson_export(trip) -> bytes:
    coords = [[p["lon"], p["lat"], *([p["ele"]] if p.get("ele") is not None else [])] for p in trip.points_json]
    features = [{"type":"Feature", "properties":{"layer":"raw_track", "trip_id":trip.id},
                 "geometry":{"type":"LineString", "coordinates":coords}}]
    for f in trip.findings:
        subset = coords[f.start_index:min(f.end_index + 1, len(coords))]
        geometry = {"type":"LineString", "coordinates":subset} if len(subset)>1 else {"type":"Point", "coordinates":subset[0]}
        features.append({"type":"Feature", "properties":{"category":f.category,"severity":f.severity,
          "confidence":f.confidence,"title":f.title}, "geometry":geometry})
    return json.dumps({"type":"FeatureCollection", "features":features}).encode()

def pdf_export(trip) -> bytes:
    out=io.BytesIO(); doc=SimpleDocTemplate(out,pagesize=A4,rightMargin=36,leftMargin=36,topMargin=36,bottomMargin=36)
    styles=getSampleStyleSheet(); story=[Paragraph("GPX Inspector",styles["Title"]),Paragraph(trip.name,styles["Heading2"]),Spacer(1,12)]
    metrics=[["Mode",trip.mode],["Raw distance",f"{trip.raw_distance_m/1000:.2f} km"],
             ["Matched distance",f"{trip.matched_distance_m/1000:.2f} km" if trip.matched_distance_m else "Unavailable"],
             ["Maximum speed",f"{trip.max_speed_kmh:.1f} km/h" if trip.max_speed_kmh else "Unavailable"],
             ["Findings",str(len(trip.findings))],["Rules version",trip.analysis_version]]
    t=Table(metrics,colWidths=[150,300]); t.setStyle(TableStyle([("BACKGROUND",(0,0),(0,-1),colors.HexColor("#0D1422")),
      ("TEXTCOLOR",(0,0),(0,-1),colors.white),("GRID",(0,0),(-1,-1),.5,colors.HexColor("#94A3B8")),("PADDING",(0,0),(-1,-1),8)])); story += [t,Spacer(1,18),Paragraph("Findings",styles["Heading2"])]
    rows=[["Severity","Finding","Confidence"]]+[[f.severity.upper(),f.title,f"{f.confidence:.0%}"] for f in trip.findings]
    ft=Table(rows,colWidths=[80,340,80],repeatRows=1); ft.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#121C2D")),
      ("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.5,colors.grey),("PADDING",(0,0),(-1,-1),6)])); story.append(ft)
    story += [Spacer(1,18),Paragraph("These findings are analytical indicators, not legal proof. Provider coverage and GPS quality affect confidence.",styles["BodyText"])]
    doc.build(story); return out.getvalue()
