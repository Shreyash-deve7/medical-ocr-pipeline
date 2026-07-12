"""backend/routes/auth_routes.py — patient + doctor registration / login (Session 6).

Endpoints (identical paths/methods/responses to the old ``main.py``):
  POST /api/patient/register
  POST /api/patient/login
  POST /api/doctor/register
  POST /api/doctor/login
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from auth import _hash_pw, _verify_pw, create_token
from database import get_db
from schemas import DoctorRegisterReq, LoginReq, RegisterReq

router = APIRouter()


@router.post("/api/patient/register")
def register(req: RegisterReq):
    conn = get_db()
    if conn.execute("SELECT id FROM patients WHERE phone=?", (req.phone,)).fetchone():
        conn.close()
        raise HTTPException(409, "Phone already registered")
    pid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO patients (id, phone, password_hash, name, created_at) VALUES (?,?,?,?,?)",
        (pid, req.phone, _hash_pw(req.password), req.name, now),
    )
    conn.commit()
    conn.close()
    return {"token": create_token(pid), "patient_id": pid}


@router.post("/api/patient/login")
def login(req: LoginReq):
    conn = get_db()
    row = conn.execute("SELECT id, password_hash FROM patients WHERE phone=?", (req.phone,)).fetchone()
    if not row or not _verify_pw(req.password, row["password_hash"]):
        conn.close()
        raise HTTPException(401, "Invalid credentials")
    patient_id = row["id"]
    conn.close()
    return {"token": create_token(patient_id), "patient_id": patient_id}


@router.post("/api/doctor/register")
def doctor_register(req: DoctorRegisterReq):
    conn = get_db()
    if conn.execute("SELECT id FROM doctors WHERE phone=?", (req.phone,)).fetchone():
        conn.close()
        raise HTTPException(409, "Phone already registered")
    did = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO doctors (id, phone, password_hash, name, specialization, license_number, email, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (did, req.phone, _hash_pw(req.password), req.name, req.specialization, req.license_number, req.email, now),
    )
    conn.commit()
    conn.close()
    return {"token": create_token(did, "doctor"), "doctor_id": did}


@router.post("/api/doctor/login")
def doctor_login(req: LoginReq):
    conn = get_db()
    row = conn.execute("SELECT id, password_hash FROM doctors WHERE phone=?", (req.phone,)).fetchone()
    if not row or not _verify_pw(req.password, row["password_hash"]):
        conn.close()
        raise HTTPException(401, "Invalid credentials")
    doctor_id = row["id"]
    conn.close()
    return {"token": create_token(doctor_id, "doctor"), "doctor_id": doctor_id}
