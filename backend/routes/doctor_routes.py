"""backend/routes/doctor_routes.py — doctor-facing endpoints (Session 6).

Extracted verbatim from ``main.py``:
  GET /api/doctor/patients
  GET /api/doctor/patient/{patient_id}
  GET /api/doctor/patient/{patient_id}/reports
  GET /api/doctor/profile
  PUT /api/doctor/profile
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from database import get_db
from schemas import DoctorProfileReq

router = APIRouter()


@router.get("/api/doctor/patients")
def list_patients():
    conn = get_db()
    rows = conn.execute(
        "SELECT p.id, p.phone, p.name, p.date_of_birth, p.gender, p.blood_group, p.created_at, COUNT(r.id) as report_count "
        "FROM patients p LEFT JOIN reports r ON p.id = r.patient_id "
        "GROUP BY p.id ORDER BY p.created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/api/doctor/patient/{patient_id}")
def get_patient_detail(patient_id: str):
    conn = get_db()
    row = conn.execute("SELECT * FROM patients WHERE id=?", (patient_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Patient not found")
    d = dict(row)
    d.pop("password_hash", None)
    conn.close()
    return d


@router.get("/api/doctor/patient/{patient_id}/reports")
def patient_report_list(patient_id: str):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, filename, filetype, shared_at, analyzed, ocr_text, analysis FROM reports WHERE patient_id=? ORDER BY shared_at DESC",
        (patient_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/api/doctor/profile")
def get_doctor_profile(doctor_id: str = Query("")):
    conn = get_db()
    row = conn.execute("SELECT * FROM doctors WHERE id=?", (doctor_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Doctor not found")
    d = dict(row)
    d.pop("password_hash", None)
    return d


@router.put("/api/doctor/profile")
def update_doctor_profile(req: DoctorProfileReq, doctor_id: str = Query("")):
    conn = get_db()
    conn.execute(
        "UPDATE doctors SET name=?, specialization=?, license_number=?, email=? WHERE id=?",
        (req.name, req.specialization, req.license_number, req.email, doctor_id),
    )
    conn.commit()
    conn.close()
    return {"ok": True}
