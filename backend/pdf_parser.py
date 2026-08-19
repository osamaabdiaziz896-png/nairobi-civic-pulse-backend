"""
pdf_parser.py
Core Module: PDF Data Ingestion (FR1, FR2 / NFR1, NFR2 from Chapter 4).

Extracts flagship-project tables from a county CIDP-style PDF using pdfplumber,
cleans/normalizes the values with pandas, and categorizes each row by sector.

The parser is deliberately tolerant of messy government table formatting
(Section 6.2 "PDF Formatting Variations" limitation from the report):
 - it tries table extraction first,
 - falls back to line-by-line regex extraction on the raw text when a page
   has no machine-readable table,
 - normalizes budget strings like "KES 12,500,000" / "12.5M" / "-" into floats.

Usage:
    python -m backend.pdf_parser path/to/cidp.pdf --out sample_data/parsed_projects.csv
"""

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

try:
    import pdfplumber
except ImportError:  # pragma: no cover
    pdfplumber = None

SECTOR_KEYWORDS = {
    "Health": ["hospital", "clinic", "dispensary", "health centre", "health center", "maternity"],
    "Infrastructure": ["road", "bridge", "drainage", "street light", "bus", "market", "footbridge"],
    "Housing": ["housing", "estate", "slum upgrading", "affordable housing", "apartments"],
    "Water": ["water", "sewer", "borehole", "sanitation"],
    "Education": ["school", "polytechnic", "vocational", "ecde", "library"],
}

STATUS_KEYWORDS = {
    "Completed": ["completed", "complete", "done", "commissioned"],
    "Ongoing": ["ongoing", "in progress", "underway", "on-going"],
    "Planned": ["planned", "proposed", "not started", "pending"],
}

BUDGET_MULTIPLIERS = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}


def normalize_budget(raw: str) -> float:
    """Turn 'KES 12,500,000', '12.5M', 'Ksh. 3,200,000.00', '-' etc. into a float."""
    if raw is None:
        return 0.0
    raw = str(raw).strip().lower()
    if raw in ("", "-", "n/a", "na", "tbd"):
        return 0.0
    raw = raw.replace("kes", "").replace("ksh", "").replace(",", "").strip()
    match = re.match(r"^([\d.]+)\s*([kmb])?$", raw)
    if not match:
        digits = re.sub(r"[^\d.]", "", raw)
        try:
            return float(digits) if digits else 0.0
        except ValueError:
            return 0.0
    value, suffix = match.groups()
    value = float(value)
    if suffix:
        value *= BUDGET_MULTIPLIERS[suffix]
    return value


def classify_sector(text: str) -> str:
    text_l = (text or "").lower()
    for sector, keywords in SECTOR_KEYWORDS.items():
        if any(k in text_l for k in keywords):
            return sector
    return "Infrastructure"  # sensible default for county capital projects


def classify_status(text: str) -> str:
    text_l = (text or "").lower()
    for status, keywords in STATUS_KEYWORDS.items():
        if any(k in text_l for k in keywords):
            return status
    return "Planned"


def extract_tables_from_pdf(pdf_path: str) -> pd.DataFrame:
    """Primary extraction path: pull structured tables page by page."""
    if pdfplumber is None:
        raise RuntimeError("pdfplumber is not installed. Run: pip install pdfplumber")

    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            for table in tables:
                if not table or len(table) < 2:
                    continue
                header = [str(h).strip().lower() if h else "" for h in table[0]]
                for raw_row in table[1:]:
                    row = dict(zip(header, raw_row))
                    name = row.get("project") or row.get("project name") or row.get("name")
                    if not name:
                        continue
                    budget_raw = row.get("budget") or row.get("cost") or row.get("allocation")
                    status_raw = row.get("status") or ""
                    ward_raw = row.get("ward") or row.get("location") or ""
                    rows.append({
                        "project_name": str(name).strip(),
                        "sector": classify_sector(name),
                        "status": classify_status(status_raw) if status_raw else classify_status(name),
                        "budget": normalize_budget(budget_raw),
                        "ward": str(ward_raw).strip() if ward_raw else None,
                        "page": page_num,
                    })

            # Fallback: no machine-readable table found on this page, try
            # line-based regex extraction on the raw text instead.
            if not tables:
                text = page.extract_text() or ""
                for line in text.split("\n"):
                    m = re.match(
                        r"^(?P<name>[A-Za-z0-9 ,'\-\/]{8,80}?)\s{2,}(?P<budget>KES?\s?[\d,\.]+[kmb]?)",
                        line.strip(), re.IGNORECASE,
                    )
                    if m:
                        rows.append({
                            "project_name": m.group("name").strip(),
                            "sector": classify_sector(m.group("name")),
                            "status": classify_status(line),
                            "budget": normalize_budget(m.group("budget")),
                            "ward": None,
                            "page": page_num,
                        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df.drop_duplicates(subset=["project_name"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.insert(0, "project_id", [f"NCP-{i+1:04d}" for i in range(len(df))])
    return df


def main():
    parser = argparse.ArgumentParser(description="Extract flagship projects from a CIDP-style PDF")
    parser.add_argument("pdf_path", help="Path to the CIDP PDF file")
    parser.add_argument("--out", default="sample_data/parsed_projects.csv", help="Output CSV path")
    args = parser.parse_args()

    df = extract_tables_from_pdf(args.pdf_path)
    if df.empty:
        print("No project rows were extracted. Check the PDF's table formatting.", file=sys.stderr)
        sys.exit(1)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"Extracted {len(df)} projects -> {args.out}")


if __name__ == "__main__":
    main()
