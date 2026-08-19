# Nairobi Civic Pulse

A digital accountability tracker for Nairobi County development projects, built to match
the system design in *Nairobi Civic Pulse: A Digital Accountability Tracker for County
Development* (Chapter 4 — three-tier architecture, ERD, use case, flowchart, sequence diagram).

```
Presentation Layer   -> Tailwind/Jinja2 dashboard (frontend/)
Application Layer    -> FastAPI backend + PDF ingestion pipeline (backend/)
Data Layer           -> PostgreSQL (falls back to SQLite with zero config)
```

## 1. Project structure

```
nairobi_civic_pulse/
├── backend/
│   ├── app.py            # FastAPI app: routes, dashboard, REST API
│   ├── database.py        # SQLAlchemy engine/session (Postgres or SQLite fallback)
│   ├── models.py           # Document & Project ORM models (matches the ERD)
│   ├── pdf_parser.py       # FR1: pdfplumber + pandas extraction/normalization
│   └── seed.py              # Relational database seeder
├── frontend/
│   ├── templates/index.html # Citizen dashboard page
│   └── static/
│       ├── css/dashboard.css
│       └── js/app.js         # Search/filter, KPI cards, Chart.js charts
├── sample_data/
│   └── sample_cidp_projects.csv  # Demo dataset standing in for a parsed CIDP PDF
├── requirements.txt
├── docker-compose.yml      # One-command Postgres + app
├── Dockerfile
└── .env.example
```

## 2. Quickest way to run it (no PostgreSQL install needed)

The app auto-falls-back to a local SQLite file if `DATABASE_URL` isn't set, so you can see
everything working in under two minutes:

```bash
cd nairobi_civic_pulse
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

uvicorn backend.app:app --reload
```

Open **http://127.0.0.1:8000** — the dashboard loads, auto-seeds itself from
`sample_data/sample_cidp_projects.csv` on first run (15 sample flagship projects across
Health, Infrastructure, Housing, Water and Education), and the search/filter/KPI/chart
features are immediately usable.

## 3. Running with real PostgreSQL (matches the report's architecture exactly)

**Option A — Docker Compose (recommended):**

```bash
docker compose up --build
```

This starts PostgreSQL 16 and the FastAPI app together, creates the schema automatically,
and seeds the sample data. Visit **http://localhost:8000**.

**Option B — Local Postgres:**

```bash
createdb nairobi_civic_pulse
createuser civic_user --pwprompt      # set password to civic_pass, or your own

cp .env.example .env
# edit .env if you used different credentials
export $(cat .env | xargs)            # or use `python-dotenv` / your shell's env loader

pip install -r requirements.txt
uvicorn backend.app:app --reload
```

## 4. Ingesting a real CIDP-style PDF

Two ways:

**A. Command line** (produces a CSV you can inspect before loading it):

```bash
python -m backend.pdf_parser path/to/your_cidp.pdf --out sample_data/parsed_projects.csv
python -m backend.seed --csv sample_data/parsed_projects.csv --fiscal-year "2023-2027"
```

**B. Via the API**, once the server is running:

```bash
curl -X POST "http://127.0.0.1:8000/api/ingest" \
  -F "file=@path/to/your_cidp.pdf" \
  -F "fiscal_year=2023-2027"
```

The parser (`backend/pdf_parser.py`) first tries `pdfplumber`'s structured table
extraction; if a page has no machine-readable table (a real limitation noted in the report,
Section 6.2 "PDF Formatting Variations"), it falls back to line-by-line regex extraction.
Budgets like `"KES 12,500,000"`, `"12.5M"`, or `"-"` are all normalized to floats, and each
project is auto-categorized into a sector (Health / Infrastructure / Housing / Water /
Education) and a status (Planned / Ongoing / Completed) using keyword matching — you can
extend `SECTOR_KEYWORDS` / `STATUS_KEYWORDS` in that file for your specific document.

## 5. API reference

| Method | Endpoint          | Description                                      |
|--------|-------------------|---------------------------------------------------|
| GET    | `/`               | Citizen dashboard (HTML)                           |
| GET    | `/api/stats`      | KPI summary: totals, budget, by-status, by-sector   |
| GET    | `/api/sectors`    | Distinct sector/status lists for filter dropdowns   |
| GET    | `/api/projects`   | Search/filter/paginate: `?q=&sector=&status=&page=` |
| POST   | `/api/ingest`     | Upload a PDF (`file=`) to parse + seed it live      |

Interactive OpenAPI docs are auto-generated at **http://127.0.0.1:8000/docs**.

## 6. Verifying each core module works (matches Chapter 5 "System Testing Results")

1. **PDF extraction (FR1, NFR1/NFR2):** run `python -m backend.pdf_parser` against any
   PDF containing a table with columns like `Project | Status | Budget`; confirm the output
   CSV in `sample_data/`.
2. **Database seeding:** run `python -m backend.seed` twice — the second run should report
   `0 inserted` (duplicates skipped by `project_id`), confirming idempotent seeding.
3. **Dashboard search/filter:** on the running dashboard, type a ward name (e.g. `Dandora`)
   into the search box, and use the Sector/Status dropdowns — the table, KPI cards, and both
   charts update live.
4. **API directly:** `curl "http://127.0.0.1:8000/api/projects?sector=Health&status=Ongoing"`.

## 7. Notes

- The bundled `sample_data/sample_cidp_projects.csv` is realistic demo data (Nairobi wards,
  sector mix, budget ranges) standing in for a real parsed CIDP PDF, so you can demo the full
  pipeline — ingestion → database → dashboard — without needing an actual government
  document on hand. Swap in a real CIDP PDF at any time using Section 4 above.
- The schema mirrors the ERD in the report (Figure 4.5): `documents` (source PDFs) →
  `projects` (flagship projects, foreign-keyed to their source document).
