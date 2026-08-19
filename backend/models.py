"""
models.py
ORM models matching the ERD in Chapter 4 of the Nairobi Civic Pulse report
(Figure 4.5). Simplified to the two core entities the dashboard needs:
Document (a source CIDP PDF) and Project (a flagship project extracted from it).
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Numeric, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from backend.database import Base

# Allowed enumerations (kept as plain strings/constants rather than DB enums
# so SQLite and Postgres both work without extra migration steps)
SECTORS = ["Health", "Infrastructure", "Housing", "Water", "Education"]
STATUSES = ["Planned", "Ongoing", "Completed"]


class Document(Base):
    __tablename__ = "documents"

    document_id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    source_url = Column(String(255), nullable=True)
    fiscal_year = Column(String(50), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    projects = relationship("Project", back_populates="document", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(50), unique=True, nullable=False)  # e.g. NCP-0001
    document_id = Column(Integer, ForeignKey("documents.document_id"), nullable=True)

    project_name = Column(String(255), nullable=False)
    sector = Column(String(100), nullable=False)          # Health / Infrastructure / Housing ...
    status = Column(String(100), nullable=False)           # Planned / Ongoing / Completed
    ward = Column(String(255), nullable=True)
    budget = Column(Numeric(14, 2), nullable=False, default=0)
    contractor_name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    document = relationship("Document", back_populates="projects")

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "project_name": self.project_name,
            "sector": self.sector,
            "status": self.status,
            "ward": self.ward,
            "budget": float(self.budget) if self.budget is not None else 0,
            "contractor_name": self.contractor_name,
            "description": self.description,
            "fiscal_year": self.document.fiscal_year if self.document else None,
        }
