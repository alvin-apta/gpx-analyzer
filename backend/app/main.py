import hashlib, json
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import Response, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select
from redis import Redis
from rq import Queue
from .config import settings
from .database import Base, engine, get_db
from .models import Trip
from .gpx import parse_track, decode_polyline
from .tasks import process_trip
from .exports import csv_export, geojson_export, pdf_export
from .providers import ollama_explain

app=FastAPI(title="GPX Inspector API",version="0.1.0")
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:3000"],allow_methods=["*"],allow_headers=["*"])

@app.on_event("startup")
def startup(): Base.metadata.create_all(engine); settings.upload_dir.mkdir(parents=True,exist_ok=True)

def trip_dict(t, detail=False):
    data={"id":t.id,"name":t.name,"mode":t.mode,"status":t.status,"created_at":t.created_at.isoformat(),
      "point_count":t.point_count,"duration_s":t.duration_s,"raw_distance_m":t.raw_distance_m,
      "matched_distance_m":t.matched_distance_m,"route_distance_m":t.route_distance_m,"straight_distance_m":t.straight_distance_m,
      "max_speed_kmh":t.max_speed_kmh,"match_quality":t.match_quality,"error":t.error,"analysis_version":t.analysis_version,
      "findings":[{"id":f.id,"category":f.category,"severity":f.severity,"confidence":f.confidence,
      "start_index":f.start_index,"end_index":f.end_index,"measured_value":f.measured_value,"threshold":f.threshold,
      "unit":f.unit,"title":f.title,"explanation":f.explanation,"evidence":f.evidence} for f in t.findings]}
    if detail:
        data["points"] = t.points_json
        data["matched_points"] = decode_polyline((t.matched_json or {}).get("encoded"))
        data["reference_points"] = decode_polyline((t.reference_json or {}).get("encoded"))
    return data

@app.get("/api/health")
def health(): return {"status":"ok","model":settings.ollama_model}

@app.get("/api/trips")
def trips(db:Session=Depends(get_db)):
    return [trip_dict(t) for t in db.scalars(select(Trip).options(selectinload(Trip.findings)).order_by(Trip.created_at.desc())).all()]

@app.post("/api/trips",status_code=202)
async def upload(file:UploadFile=File(...),mode:str=Form(...),db:Session=Depends(get_db)):
    if mode not in ("car","motorcycle","bicycle","foot"): raise HTTPException(422,"Unsupported mode")
    data=await file.read(settings.max_upload_bytes+1)
    if len(data)>settings.max_upload_bytes: raise HTTPException(413,"File exceeds 50 MB")
    try: track_name,_=parse_track(data, file.filename or "")
    except ValueError as exc: raise HTTPException(422,str(exc))
    checksum=hashlib.sha256(data).hexdigest(); trip=Trip(name=track_name or file.filename or "Untitled trip",mode=mode,checksum=checksum,source_path="")
    db.add(trip); db.flush(); suffix=".csv" if (file.filename or "").lower().endswith(".csv") else ".gpx"; path=settings.upload_dir/f"{trip.id}{suffix}"; path.write_bytes(data); trip.source_path=str(path); db.commit()
    try: Queue("gpx",connection=Redis.from_url(settings.redis_url)).enqueue(process_trip,trip.id,job_timeout=300)
    except Exception: process_trip(trip.id)
    return {"id":trip.id,"status":"queued"}

@app.get("/api/trips/{trip_id}")
def get_trip(trip_id:str,db:Session=Depends(get_db)):
    t=db.scalar(select(Trip).where(Trip.id==trip_id).options(selectinload(Trip.findings)))
    if not t: raise HTTPException(404,"Trip not found")
    return trip_dict(t,True)

@app.delete("/api/trips/{trip_id}",status_code=204)
def delete_trip(trip_id:str,db:Session=Depends(get_db)):
    t=db.get(Trip,trip_id)
    if not t: raise HTTPException(404,"Trip not found")
    Path(t.source_path).unlink(missing_ok=True); db.delete(t); db.commit()

@app.get("/api/trips/{trip_id}/exports/{kind}")
def export(trip_id:str,kind:str,db:Session=Depends(get_db)):
    t=db.scalar(select(Trip).where(Trip.id==trip_id).options(selectinload(Trip.findings)))
    if not t: raise HTTPException(404,"Trip not found")
    funcs={"csv":(csv_export,"text/csv"),"geojson":(geojson_export,"application/geo+json"),"pdf":(pdf_export,"application/pdf")}
    if kind not in funcs: raise HTTPException(404,"Unknown export")
    body,mime=funcs[kind][0](t),funcs[kind][1]
    return Response(body,media_type=mime,headers={"Content-Disposition":f'attachment; filename="{t.id}.{kind}"'})

@app.post("/api/trips/{trip_id}/explanation")
async def explain(trip_id:str,db:Session=Depends(get_db)):
    t=db.scalar(select(Trip).where(Trip.id==trip_id).options(selectinload(Trip.findings)))
    if not t: raise HTTPException(404,"Trip not found")
    summary={k:v for k,v in trip_dict(t).items() if k not in ("id","created_at")}
    try: return {"source":f"ollama:{settings.ollama_model}","text":await ollama_explain(summary)}
    except Exception as exc: raise HTTPException(503,f"Local Qwen unavailable: {exc}")

SAMPLE_DIR=Path(__file__).parent.parent/"samples"
@app.get("/api/sample-packs")
def sample_packs():
    manifest=json.loads((SAMPLE_DIR/"manifest.json").read_text())
    return manifest
@app.get("/api/sample-packs/{city}/{filename}")
def sample_file(city:str,filename:str):
    path=(SAMPLE_DIR/city/filename).resolve()
    if SAMPLE_DIR.resolve() not in path.parents or not path.exists(): raise HTTPException(404,"Sample not found")
    return FileResponse(path,media_type="application/gpx+xml",filename=filename)
