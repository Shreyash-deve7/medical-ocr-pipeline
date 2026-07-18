"""SQLAlchemy ORM models placeholder for the MedVault Hepatology OCR pipeline."""

from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from database import Base


class Patient(Base):
    __tablename__ = "patients"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, unique=True, index=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Report(Base):
    __tablename__ = "reports"

    id = Column(String, primary_key=True, index=True)
    patient_id = Column(String, index=True, nullable=False)
    file_path = Column(String, nullable=False)
    ocr_text = Column(Text, nullable=True)
    classification = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
