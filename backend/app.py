"""
app.py
Application Layer / Presentation Layer entry point (Figure 4.1 three-tier architecture).

Serves:
  - GET  /                    -> the citizen dashboard (Tailwind HTML)
  - GET  /api/projects        -> search/filter/paginate projects (FR3, FR4)
  - GET  /api/stats           -> KPI summary for the dashboard cards
  - GET  /api/sectors         -> distinct sector list (for filter dropdown)
  - POST /api/ingest          -> upload a CIDP PDF and ingest it end-to-end (FR1)

Run with:
    uvicorn backend.app:app --reload
"""

import shutil
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Depends, Query, UploadFile, File, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database import get_db, init_db, SessionLocal
from backend.models import Project, Document, SECTORS, STATUSES
from backend.pdf_parser import extract_tables_from_pdf
from backend.seed import seed_from_csv, DEFAULT_CSV

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(title="Nairobi Civic Pulse", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "frontend" / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "frontend" / "templates"))


@app.on_event("startup")
def on_startup():
    init_db()
    # Auto-seed with sample data on first run so the dashboard is never empty.
    db = SessionLocal()
    try:
        if db.query(Project).count() == 0:
            seed_from_csv(str(DEFAULT_CSV))
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    total_budget = db.query(func.coalesce(func.sum(Project.budget), 0)).scalar()
    total_projects = db.query(func.count(Project.id)).scalar()

    by_status = dict(
        db.query(Project.status, func.count(Project.id)).group_by(Project.status).all()
    )
    by_sector = dict(
        db.query(Project.sector, func.count(Project.id)).group_by(Project.sector).all()
    )
    budget_by_sector = dict(
        db.query(Project.sector, func.coalesce(func.sum(Project.budget), 0))
        .group_by(Project.sector).all()
    )

    return {
        "total_projects": total_projects,
        "total_budget": float(total_budget),
        "by_status": {s: by_status.get(s, 0) for s in STATUSES},
        "by_sector": {s: by_sector.get(s, 0) for s in SECTORS},
        "budget_by_sector": {s: float(budget_by_sector.get(s, 0)) for s in SECTORS},
    }


@app.get("/api/sectors")
def get_sectors():
    return {"sectors": SECTORS, "statuses": STATUSES}


@app.get("/api/projects")
def list_projects(
    q: Optional[str] = Query(None, description="Keyword search on project name / ward"),
    sector: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Project)

    if q:
        like = f"%{q}%"
        query = query.filter(
            (Project.project_name.ilike(like)) | (Project.ward.ilike(like))
        )
    if sector:
        query = query.filter(Project.sector == sector)
    if status:
        query = query.filter(Project.status == status)

    total = query.count()
    items = (
        query.order_by(Project.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": [p.to_dict() for p in items],
    }


@app.post("/api/ingest")
async def ingest_pdf(file: UploadFile = File(...), fiscal_year: str = "2023-2027"):
    """Upload a real CIDP-style PDF; it is parsed and immediately seeded into the DB."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Please upload a .pdf file")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    df = extract_tables_from_pdf(tmp_path)
    if df.empty:
        raise HTTPException(422, "No project tables could be extracted from this PDF")

    csv_path = BASE_DIR / "sample_data" / f"ingested_{Path(file.filename).stem}.csv"
    df.to_csv(csv_path, index=False)
    seed_from_csv(str(csv_path), fiscal_year=fiscal_year, filename=file.filename)

    return {"message": f"Ingested {len(df)} projects from {file.filename}"}
