"""
seed.py
Core Module: Relational Database Seeder (Section 5.2 "Database Integration Module").

Reads a CSV of extracted projects (either the bundled sample_data/sample_cidp_projects.csv,
which stands in for a parsed CIDP PDF, or one you generated yourself with pdf_parser.py)
and maps it into the PostgreSQL/SQLite schema defined in backend/models.py.

Usage:
    python -m backend.seed                                  # loads the bundled sample data
    python -m backend.seed --csv sample_data/parsed_projects.csv --fiscal-year "2023-2027"
"""

import argparse
from pathlib import Path

import pandas as pd

from backend.database import SessionLocal, init_db
from backend.models import Document, Project

DEFAULT_CSV = Path(__file__).resolve().parent.parent / "sample_data" / "sample_cidp_projects.csv"


def seed_from_csv(csv_path: str, fiscal_year: str = "2023-2027", filename: str = "Nairobi_CIDP.pdf"):
    init_db()
    df = pd.read_csv(csv_path)

    db = SessionLocal()
    try:
        document = Document(filename=filename, fiscal_year=fiscal_year)
        db.add(document)
        db.flush()  # get document.document_id without committing yet

        inserted, skipped = 0, 0
        for _, row in df.iterrows():
            exists = db.query(Project).filter_by(project_id=row["project_id"]).first()
            if exists:
                skipped += 1
                continue
            project = Project(
                project_id=row["project_id"],
                document_id=document.document_id,
                project_name=row["project_name"],
                sector=row["sector"],
                status=row["status"],
                ward=row.get("ward"),
                budget=row.get("budget", 0) or 0,
                contractor_name=row.get("contractor_name"),
                description=row.get("description"),
            )
            db.add(project)
            inserted += 1

        db.commit()
        print(f"Seed complete: {inserted} projects inserted, {skipped} already existed (skipped).")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Seed the database with parsed CIDP project data")
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help="CSV of extracted projects")
    parser.add_argument("--fiscal-year", default="2023-2027")
    parser.add_argument("--filename", default="Nairobi_CIDP.pdf")
    args = parser.parse_args()

    seed_from_csv(args.csv, args.fiscal_year, args.filename)


if __name__ == "__main__":
    main()
