import os, uuid, json, sqlite3, shutil, threading, traceback, time
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from cryptography.fernet import Fernet
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
# Compatibility bridge for the existing Python engines while the canonical
# BIxlerator BIXLERATOR_* environment names are used by the application.
for _old, _new in {
    "BLXLERATOR_LLM_API_KEY": "BIXLERATOR_LLM_API_KEY",
    "BLXLERATOR_LLM_API_URL": "BIXLERATOR_LLM_API_URL",
    "BLXLERATOR_LLM_MODEL": "BIXLERATOR_LLM_MODEL",
    "BLXLERATOR_IMAGE_API_KEY": "BIXLERATOR_IMAGE_API_KEY",
    "BLXLERATOR_IMAGE_API_URL": "BIXLERATOR_IMAGE_API_URL",
    "BLXLERATOR_IMAGE_MODEL": "BIXLERATOR_IMAGE_MODEL",
    "BLXLERATOR_IMAGE_PROVIDER": "BIXLERATOR_IMAGE_PROVIDER",
}.items():
    if os.getenv(_new) and not os.getenv(_old):
        os.environ[_old] = os.getenv(_new)

UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output_data"
FRONTEND_DIR = BASE_DIR / "frontend" / "dist"
DB_PATH = BASE_DIR / "bixlerator.db"
MAX_UPLOAD_MB = int(os.getenv("BIXLERATOR_MAX_UPLOAD_MB", "500"))
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

import conversion_engine
import pii_engine
import doc_generator
import image_generator

app = FastAPI(title="BIxlerator API", version="1.0.0", docs_url="/api/docs", redoc_url="/api/redoc")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in os.getenv("BIXLERATOR_CORS_ORIGINS", "*").split(",")],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = ThreadPoolExecutor(max_workers=int(os.getenv("BIXLERATOR_WORKERS", "1")))
jobs_lock = threading.Lock()
jobs = {}

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.execute("""CREATE TABLE IF NOT EXISTS activity(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset TEXT NOT NULL,
        module TEXT NOT NULL,
        initiated_by TEXT NOT NULL,
        status TEXT NOT NULL,
        output_path TEXT,
        created_at TEXT NOT NULL,
        duration_seconds REAL
    )""")
    try:
        conn.execute("ALTER TABLE activity ADD COLUMN duration_seconds REAL")
    except sqlite3.OperationalError:
        pass
    conn.execute("""CREATE TABLE IF NOT EXISTS counters(
        name TEXT PRIMARY KEY,
        value INTEGER NOT NULL
    )""")
    defaults={"qvd_assets":0,"pii_columns":0,"dax_expressions":0}
    for k,v in defaults.items():
        conn.execute("INSERT OR IGNORE INTO counters(name,value) VALUES(?,?)",(k,v))
    conn.commit(); conn.close()

init_db()

def add_activity(asset,module,user,status,output=None):
    conn=db()
    cur=conn.execute("INSERT INTO activity(asset,module,initiated_by,status,output_path,created_at,duration_seconds) VALUES(?,?,?,?,?,?,?)",
                     (asset,module,user,status,output,datetime.now(timezone.utc).isoformat(),None))
    conn.commit(); aid=cur.lastrowid; conn.close()
    return aid

def update_activity(aid,status,output=None,duration_seconds=None):
    conn=db()
    if output is not None:
        conn.execute("UPDATE activity SET status=?, output_path=?, duration_seconds=? WHERE id=?",(status,output,duration_seconds,aid))
    else:
        conn.execute("UPDATE activity SET status=?, duration_seconds=? WHERE id=?",(status,duration_seconds,aid))
    conn.commit(); conn.close()

def inc_counter(name,delta=1):
    conn=db(); conn.execute("UPDATE counters SET value=value+? WHERE name=?",(delta,name)); conn.commit(); conn.close()

def stats():
    conn=db()
    rows={r["name"]:r["value"] for r in conn.execute("SELECT name,value FROM counters")}
    activities=[dict(r) for r in conn.execute("SELECT id,asset,module,initiated_by,status,created_at,output_path,duration_seconds FROM activity ORDER BY id DESC LIMIT 50")]
    avg_row=conn.execute("SELECT AVG(duration_seconds) AS avg_seconds FROM activity WHERE status='Completed' AND duration_seconds IS NOT NULL").fetchone()
    avg_seconds=avg_row["avg_seconds"] if avg_row and avg_row["avg_seconds"] is not None else 0
    conn.close()
    return rows,activities,avg_seconds

def weekly_count(module):
    conn=db()
    row=conn.execute("SELECT COUNT(*) AS n FROM activity WHERE module=? AND status='Completed' AND created_at >= datetime('now','-7 days')",(module,)).fetchone()
    conn.close()
    return int(row["n"] or 0)

def safe_name(name):
    name=Path(name or "upload").name
    return "".join(c for c in name if c.isalnum() or c in "._-")[:180] or "upload"

async def save_upload(upload: UploadFile):
    name=safe_name(upload.filename)
    path=UPLOAD_DIR / f"{uuid.uuid4().hex}_{name}"
    size=0
    with open(path,"wb") as f:
        while True:
            chunk=await upload.read(1024*1024)
            if not chunk: break
            size += len(chunk)
            if size > MAX_UPLOAD_MB*1024*1024:
                path.unlink(missing_ok=True)
                raise HTTPException(413,f"File exceeds {MAX_UPLOAD_MB} MB limit")
            f.write(chunk)
    return path

def submit_job(module,asset,user,fn):
    aid=add_activity(asset,module,user,"Running")
    jid=uuid.uuid4().hex
    started=time.time()
    with jobs_lock:
        jobs[jid]={"id":jid,"activity_id":aid,"module":module,"asset":asset,"status":"queued","message":"Queued","started_at":started}
    def runner():
        started_running=time.time()
        with jobs_lock: jobs[jid].update(status="running",message="Processing",started_at=started_running)
        try:
            output,message=fn()
            if not output:
                raise RuntimeError(message or "Engine did not produce an output")
            output=str(output)
            duration=round(time.time()-started_running,3)
            with jobs_lock: jobs[jid].update(status="completed",message=message,output_path=output,duration_seconds=duration)
            update_activity(aid,"Completed",output,duration)
            if module == "QVD → CSV":
                inc_counter("qvd_assets",1)
            elif module == "Qlik → DAX":
                inc_counter("dax_expressions",count_dax_expressions(asset))
        except Exception as e:
            msg=str(e)
            duration=round(time.time()-started_running,3)
            with jobs_lock: jobs[jid].update(status="failed",message=msg,duration_seconds=duration)
            update_activity(aid,"Failed",None,duration)
    executor.submit(runner)
    return jid

def count_dax_expressions(asset):
    try:
        source = UPLOAD_DIR
        matches=sorted(source.glob(f"*_{safe_name(asset)}"), key=lambda p:p.stat().st_mtime, reverse=True)
        if not matches: return 0
        df=pd.read_excel(matches[0])
        if "QLIK EXPRESSIONS" not in df.columns: return 0
        return int(df["QLIK EXPRESSIONS"].fillna("").astype(str).str.strip().ne("").sum())
    except Exception:
        return 0

class TextRequest(BaseModel):
    prompt: str
    width: int = 1024
    height: int = 1024
    user: str = "Zoheb"

@app.get("/api/health")
def health():
    return {"status":"ok","service":"bixlerator-api","version":"1.0.0"}

@app.get("/api/dashboard")
def dashboard():
    c,a,avg_seconds=stats()
    return {"kpis":{
        "qvd_assets_converted":c.get("qvd_assets",0),
        "pii_columns_secured":c.get("pii_columns",0),
        "dax_expressions":c.get("dax_expressions",0),
        "avg_conversion_seconds":round(avg_seconds,1),
        "qvd_this_week":weekly_count("QVD → CSV"),
        "dax_this_week":weekly_count("Qlik → DAX")
    },"activity":a}

@app.get("/api/jobs/{job_id}")
def job_status(job_id):
    with jobs_lock:
        j=dict(jobs.get(job_id) or {})
    if not j: raise HTTPException(404,"Job not found")
    j.pop("output_path", None)
    j.pop("error", None)
    j.pop("encryption_key", None)
    j.pop("started_at", None)
    return j

@app.get("/api/jobs/{job_id}/download")
def job_download(job_id):
    with jobs_lock: j=jobs.get(job_id)
    if not j or j.get("status")!="completed": raise HTTPException(409,"Output is not ready")
    p=Path(j["output_path"])
    if not p.exists(): raise HTTPException(404,"Output file no longer exists")
    return FileResponse(p,filename=p.name,media_type="application/octet-stream")

@app.post("/api/qvd/convert")
async def qvd_convert(file: UploadFile=File(...), user: str=Form("Zoheb")):
    if not file.filename.lower().endswith(".qvd"): raise HTTPException(400,"Upload a .qvd file")
    p=await save_upload(file)
    return {"job_id":submit_job("QVD → CSV",file.filename,user,lambda: conversion_engine.convert_qvd(str(p)))}

@app.post("/api/dax/convert")
async def dax_convert(file: UploadFile=File(...), user: str=Form("Zoheb")):
    if not file.filename.lower().endswith((".xlsx",".xls")): raise HTTPException(400,"Upload an Excel .xlsx/.xls file")
    p=await save_upload(file)
    return {"job_id":submit_job("Qlik → DAX",file.filename,user,lambda: conversion_engine.convert_qlik_to_dax(str(p)))}

@app.post("/api/script/convert")
async def script_convert(file: UploadFile=File(...), user: str=Form("Zoheb")):
    if not file.filename.lower().endswith((".txt",".qvs",".qlik")): raise HTTPException(400,"Upload a Qlik script text file")
    p=await save_upload(file)
    return {"job_id":submit_job("Script → Python",file.filename,user,lambda: conversion_engine.convert_qlik_script_to_python(str(p)))}

@app.post("/api/docs/generate")
async def docs_generate(file: UploadFile=File(...), user: str=Form("Zoheb")):
    if not file.filename.lower().endswith((".txt",".qvs",".qlik")): raise HTTPException(400,"Upload a Qlik script text file")
    p=await save_upload(file)
    return {"job_id":submit_job("Documentation",file.filename,user,lambda: doc_generator.generate_qlik_documentation(str(p)))}

@app.post("/api/pii/scan")
async def pii_scan(file: UploadFile=File(...)):
    if not file.filename.lower().endswith(".csv"): raise HTTPException(400,"Upload a .csv file")
    p=await save_upload(file)
    try:
        cols=pii_engine.scan_pii_columns(str(p))
        return {"file":file.filename,"columns":cols,"detection":"GenAI-assisted PII classification","note":"Classification is based on column metadata in the supplied engine."}
    except Exception as e:
        raise HTTPException(500,str(e))

@app.post("/api/pii/mask")
async def pii_mask(file: UploadFile=File(...), columns: str=Form(...), key: str=Form(""), user: str=Form("Zoheb")):
    if not file.filename.lower().endswith(".csv"): raise HTTPException(400,"Upload a .csv file")
    p=await save_upload(file)
    selected=[x.strip() for x in columns.split(",") if x.strip()]
    if not selected: raise HTTPException(400,"Select at least one column")
    key = key.strip() or Fernet.generate_key().decode()
    def work():
        out=pii_engine.mask_pii_data(str(p),selected,key,str(OUTPUT_DIR))
        inc_counter("pii_columns",len(selected))
        return out,f"PII protection completed for {len(selected)} selected column(s). Encryption key generated/provided by the caller."
    jid=submit_job("PII Shield",file.filename,user,work)
    return {"job_id":jid,"encryption_key":key}

@app.post("/api/pii/unmask")
async def pii_unmask(file: UploadFile=File(...), columns: str=Form(...), key: str=Form(...), user: str=Form("Zoheb")):
    if not file.filename.lower().endswith(".csv"): raise HTTPException(400,"Upload a .csv file")
    if not key.strip(): raise HTTPException(400,"Encryption key is required")
    p=await save_upload(file)
    selected=[x.strip() for x in columns.split(",") if x.strip()]
    if not selected: raise HTTPException(400,"Select at least one column")
    return {"job_id":submit_job("PII Unmask",file.filename,user,lambda: pii_engine.unmask_pii_data(str(p),selected,key.strip(),str(OUTPUT_DIR)))}

@app.post("/api/uiux/generate")
def uiux_generate(req: TextRequest):
    def work():
        result=image_generator.call_image_generation_api(req.prompt,req.width,req.height)
        imgs=image_generator.extract_images_from_response(result)
        paths=image_generator.save_base64_images(imgs,str(OUTPUT_DIR),"wireframe")
        if not paths: return None,"Image engine returned no images"
        return paths[0],"Wireframe generated successfully."
    return {"job_id":submit_job("UI/UX Generator","dashboard-wireframe",req.user,work)}

if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")
    @app.get("/{full_path:path}")
    def spa(full_path: str):
        candidate=FRONTEND_DIR / full_path
        if candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIR / "index.html")
