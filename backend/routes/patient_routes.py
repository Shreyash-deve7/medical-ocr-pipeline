"""backend/routes/patient_routes.py — patient profile + clinical records (Session 6).

Patient-owned / patient-scoped endpoints extracted verbatim from ``main.py``:
  GET/PUT  /api/patient/profile
  GET      /api/patient/{patient_id}/allergies  (+ POST, DELETE /api/allergies/{id})
  GET/POST /api/patient/{patient_id}/conditions  (+ DELETE /api/conditions/{id})
  GET/POST /api/patient/{patient_id}/medications (+ DELETE /api/medications/{id})
  GET/POST /api/vitals
  GET/POST /api/patient/{patient_id}/prescriptions | /api/prescriptions
  GET/POST /api/patient/{patient_id}/notes | /api/notes
  GET/POST /api/appointments (+ PUT /api/appointments/{id})
  GET/POST /api/patient/{patient_id}/labs | /api/labs
  GET/POST /api/patient/{patient_id}/diagnoses (+ DELETE /api/diagnoses/{id})
  GET/POST /api/patient/{patient_id}/referrals | /api/referrals (+ PUT /api/referrals/{id})
  GET/POST /api/patient/{patient_id}/invoices | /api/invoices (+ PUT /api/invoices/{id})
  GET/POST /api/patient/{patient_id}/insurance (+ DELETE /api/insurance/{id})
  GET      /api/patient/{patient_id}/export
  GET      /api/patient/{patient_id}/fhir
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from database import get_db
from schemas import (
    AllergyReq,
    AppointmentReq,
    ClinicalNoteReq,
    ConditionReq,
    DiagnosisCodeReq,
    InvoiceReq,
    InsuranceReq,
    LabResultReq,
    MedicationReq,
    PatientProfileReq,
    PrescriptionReq,
    ReferralReq,
    VitalReq,
)

router = APIRouter()


@router.get("/api/patient/profile")
def get_patient_profile(token: str):
    from auth import decode_token
    payload = decode_token(token)
    conn = get_db()
    row = conn.execute("SELECT * FROM patients WHERE id=?", (payload["sub"],)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Patient not found")
    d = dict(row)
    d.pop("password_hash", None)
    return d


@router.put("/api/patient/profile")
def update_patient_profile(token: str, req: PatientProfileReq):
    from auth import decode_token
    payload = decode_token(token)
    conn = get_db()
    conn.execute(
        "UPDATE patients SET name=?, date_of_birth=?, gender=?, blood_group=?, email=?, address=?, emergency_contact=?, emergency_phone=? WHERE id=?",
        (req.name, req.date_of_birth, req.gender, req.blood_group, req.email, req.address, req.emergency_contact, req.emergency_phone, payload["sub"]),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Allergies ─────────────────────────────────────────────────

@router.get("/api/patient/{patient_id}/allergies")
def list_allergies(patient_id: str):
    conn = get_db()
    rows = conn.execute("SELECT * FROM allergies WHERE patient_id=? ORDER BY noted_at DESC", (patient_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/api/patient/{patient_id}/allergies")
def add_allergy(patient_id: str, req: AllergyReq):
    aid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    conn.execute("INSERT INTO allergies (id, patient_id, allergen, severity, reaction, noted_at) VALUES (?,?,?,?,?,?)",
                 (aid, patient_id, req.allergen, req.severity, req.reaction, now))
    conn.commit()
    conn.close()
    return {"id": aid}


@router.delete("/api/allergies/{allergy_id}")
def delete_allergy(allergy_id: str):
    conn = get_db()
    conn.execute("DELETE FROM allergies WHERE id=?", (allergy_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Conditions ────────────────────────────────────────────────

@router.get("/api/patient/{patient_id}/conditions")
def list_conditions(patient_id: str):
    conn = get_db()
    rows = conn.execute("SELECT * FROM conditions WHERE patient_id=? ORDER BY created_at DESC", (patient_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/api/patient/{patient_id}/conditions")
def add_condition(patient_id: str, req: ConditionReq):
    cid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    conn.execute("INSERT INTO conditions (id, patient_id, name, status, diagnosed_at, notes, created_at) VALUES (?,?,?,?,?,?,?)",
                 (cid, patient_id, req.name, req.status, req.diagnosed_at, req.notes, now))
    conn.commit()
    conn.close()
    return {"id": cid}


@router.delete("/api/conditions/{condition_id}")
def delete_condition(condition_id: str):
    conn = get_db()
    conn.execute("DELETE FROM conditions WHERE id=?", (condition_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Medications ───────────────────────────────────────────────

@router.get("/api/patient/{patient_id}/medications")
def list_medications(patient_id: str):
    conn = get_db()
    rows = conn.execute("SELECT * FROM medications WHERE patient_id=? ORDER BY created_at DESC", (patient_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/api/patient/{patient_id}/medications")
def add_medication(patient_id: str, req: MedicationReq):
    mid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    conn.execute(
        "INSERT INTO medications (id, patient_id, name, dosage, frequency, status, prescribed_by, start_date, end_date, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (mid, patient_id, req.name, req.dosage, req.frequency, req.status, req.prescribed_by, req.start_date, req.end_date, now),
    )
    conn.commit()
    conn.close()
    return {"id": mid}


@router.delete("/api/medications/{medication_id}")
def delete_medication(medication_id: str):
    conn = get_db()
    conn.execute("DELETE FROM medications WHERE id=?", (medication_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Vitals ────────────────────────────────────────────────────

@router.get("/api/patient/{patient_id}/vitals")
def list_vitals(patient_id: str, limit: int = Query(50)):
    conn = get_db()
    rows = conn.execute("SELECT * FROM vitals WHERE patient_id=? ORDER BY recorded_at DESC LIMIT ?", (patient_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/api/vitals")
def record_vital(req: VitalReq):
    vid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    conn.execute(
        "INSERT INTO vitals (id, patient_id, systolic, diastolic, heart_rate, temperature, spo2, respiratory_rate, weight, height, blood_sugar, notes, recorded_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (vid, req.patient_id, req.systolic, req.diastolic, req.heart_rate, req.temperature, req.spo2, req.respiratory_rate, req.weight, req.height, req.blood_sugar, req.notes, now),
    )
    conn.commit()
    conn.close()
    return {"id": vid}


# ── Prescriptions ─────────────────────────────────────────────

@router.get("/api/patient/{patient_id}/prescriptions")
def list_prescriptions(patient_id: str):
    conn = get_db()
    rows = conn.execute("SELECT * FROM prescriptions WHERE patient_id=? ORDER BY created_at DESC", (patient_id,)).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["items"] = json.loads(d["items"]) if isinstance(d["items"], str) else d["items"]
        result.append(d)
    return result


@router.post("/api/prescriptions")
def create_prescription(req: PrescriptionReq):
    pid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    conn.execute(
        "INSERT INTO prescriptions (id, patient_id, doctor_name, diagnosis, notes, items, created_at) VALUES (?,?,?,?,?,?,?)",
        (pid, req.patient_id, req.doctor_name, req.diagnosis, req.notes, json.dumps(req.items), now),
    )
    conn.commit()
    conn.close()
    return {"id": pid}


# ── Clinical Notes (SOAP) ────────────────────────────────────

@router.get("/api/patient/{patient_id}/notes")
def list_clinical_notes(patient_id: str):
    conn = get_db()
    rows = conn.execute("SELECT * FROM clinical_notes WHERE patient_id=? ORDER BY created_at DESC", (patient_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/api/notes")
def create_clinical_note(req: ClinicalNoteReq):
    nid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    conn.execute(
        "INSERT INTO clinical_notes (id, patient_id, doctor_name, visit_type, subjective, objective, assessment, plan, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (nid, req.patient_id, req.doctor_name, req.visit_type, req.subjective, req.objective, req.assessment, req.plan, now),
    )
    conn.commit()
    conn.close()
    return {"id": nid}


# ── Appointments ──────────────────────────────────────────────

@router.get("/api/appointments")
def list_appointments(patient_id: str = Query(None), status: str = Query(None)):
    conn = get_db()
    query = "SELECT a.*, p.name as patient_name, p.phone as patient_phone FROM appointments a JOIN patients p ON a.patient_id = p.id WHERE 1=1"
    params: list = []
    if patient_id:
        query += " AND a.patient_id=?"
        params.append(patient_id)
    if status:
        query += " AND a.status=?"
        params.append(status)
    query += " ORDER BY a.scheduled_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/api/appointments")
def create_appointment(req: AppointmentReq):
    aid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    conn.execute(
        "INSERT INTO appointments (id, patient_id, doctor_name, scheduled_at, duration_min, visit_type, status, notes, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (aid, req.patient_id, req.doctor_name, req.scheduled_at, req.duration_min, req.visit_type, req.status, req.notes, now),
    )
    conn.commit()
    conn.close()
    return {"id": aid}


@router.put("/api/appointments/{appointment_id}")
def update_appointment(appointment_id: str, req: AppointmentReq):
    conn = get_db()
    conn.execute(
        "UPDATE appointments SET doctor_name=?, scheduled_at=?, duration_min=?, visit_type=?, status=?, notes=? WHERE id=?",
        (req.doctor_name, req.scheduled_at, req.duration_min, req.visit_type, req.status, req.notes, appointment_id),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Lab Results ───────────────────────────────────────────────

@router.get("/api/patient/{patient_id}/labs")
def list_lab_results(patient_id: str):
    conn = get_db()
    rows = conn.execute("SELECT * FROM lab_results WHERE patient_id=? ORDER BY tested_at DESC", (patient_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/api/labs")
def add_lab_result(req: LabResultReq):
    lid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    tested = req.tested_at or now
    conn = get_db()
    conn.execute(
        "INSERT INTO lab_results (id, patient_id, test_name, value, unit, reference_low, reference_high, status, report_id, tested_at, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (lid, req.patient_id, req.test_name, req.value, req.unit, req.reference_low, req.reference_high, req.status, req.report_id, tested, now),
    )
    conn.commit()
    conn.close()
    return {"id": lid}


# ── Diagnoses ─────────────────────────────────────────────────

@router.get("/api/patient/{patient_id}/diagnoses")
def list_diagnoses(patient_id: str):
    conn = get_db()
    rows = conn.execute("SELECT * FROM diagnosis_codes WHERE patient_id=? ORDER BY diagnosed_at DESC", (patient_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/api/patient/{patient_id}/diagnoses")
def add_diagnosis(patient_id: str, req: DiagnosisCodeReq):
    did = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    conn.execute(
        "INSERT INTO diagnosis_codes (id, patient_id, code, description, diagnosed_at, notes, created_at) VALUES (?,?,?,?,?,?,?)",
        (did, patient_id, req.code, req.description, now, req.notes, now),
    )
    conn.commit()
    conn.close()
    return {"id": did}


@router.delete("/api/diagnoses/{diagnosis_id}")
def delete_diagnosis(diagnosis_id: str):
    conn = get_db()
    conn.execute("DELETE FROM diagnosis_codes WHERE id=?", (diagnosis_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Referrals ─────────────────────────────────────────────────

@router.get("/api/patient/{patient_id}/referrals")
def list_referrals(patient_id: str):
    conn = get_db()
    rows = conn.execute("SELECT * FROM referrals WHERE patient_id=? ORDER BY created_at DESC", (patient_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/api/referrals")
def create_referral(req: ReferralReq):
    rid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    conn.execute(
        "INSERT INTO referrals (id, patient_id, from_doctor_name, to_specialty, to_doctor_name, reason, urgency, status, notes, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (rid, req.patient_id, req.from_doctor_name, req.to_specialty, req.to_doctor_name, req.reason, req.urgency, "pending", req.notes, now),
    )
    conn.commit()
    conn.close()
    return {"id": rid}


@router.put("/api/referrals/{referral_id}/status")
def update_referral_status(referral_id: str, status: str = Query(...)):
    conn = get_db()
    conn.execute("UPDATE referrals SET status=? WHERE id=?", (status, referral_id))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Invoices / Billing ────────────────────────────────────────

@router.get("/api/patient/{patient_id}/invoices")
def list_invoices(patient_id: str):
    conn = get_db()
    rows = conn.execute("SELECT * FROM invoices WHERE patient_id=? ORDER BY created_at DESC", (patient_id,)).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["items"] = json.loads(d["items"]) if isinstance(d["items"], str) else d["items"]
        result.append(d)
    return result


@router.post("/api/invoices")
def create_invoice(req: InvoiceReq):
    iid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    conn.execute(
        "INSERT INTO invoices (id, patient_id, items, subtotal, tax, total, notes, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (iid, req.patient_id, json.dumps(req.items), req.subtotal, req.tax, req.total, req.notes, now),
    )
    conn.commit()
    conn.close()
    return {"id": iid}


@router.put("/api/invoices/{invoice_id}/status")
def update_invoice_status(invoice_id: str, status: str = Query(...)):
    conn = get_db()
    conn.execute("UPDATE invoices SET status=? WHERE id=?", (status, invoice_id))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Insurance ─────────────────────────────────────────────────

@router.get("/api/patient/{patient_id}/insurance")
def list_insurance(patient_id: str):
    conn = get_db()
    rows = conn.execute("SELECT * FROM insurance WHERE patient_id=? ORDER BY created_at DESC", (patient_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/api/patient/{patient_id}/insurance")
def add_insurance(patient_id: str, req: InsuranceReq):
    iid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    conn.execute(
        "INSERT INTO insurance (id, patient_id, provider_name, policy_number, group_number, subscriber_name, relationship, effective_date, expiry_date, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (iid, patient_id, req.provider_name, req.policy_number, req.group_number, req.subscriber_name, req.relationship, req.effective_date, req.expiry_date, now),
    )
    conn.commit()
    conn.close()
    return {"id": iid}


@router.delete("/api/insurance/{insurance_id}")
def delete_insurance(insurance_id: str):
    conn = get_db()
    conn.execute("DELETE FROM insurance WHERE id=?", (insurance_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Export / Print ────────────────────────────────────────────

@router.get("/api/patient/{patient_id}/export")
def export_patient_data(patient_id: str):
    conn = get_db()
    patient = conn.execute("SELECT * FROM patients WHERE id=?", (patient_id,)).fetchone()
    if not patient:
        conn.close()
        raise HTTPException(404, "Patient not found")
    p = dict(patient)
    p.pop("password_hash", None)

    allergies = [dict(r) for r in conn.execute("SELECT * FROM allergies WHERE patient_id=?", (patient_id,)).fetchall()]
    conditions = [dict(r) for r in conn.execute("SELECT * FROM conditions WHERE patient_id=?", (patient_id,)).fetchall()]
    medications = [dict(r) for r in conn.execute("SELECT * FROM medications WHERE patient_id=?", (patient_id,)).fetchall()]
    vitals = [dict(r) for r in conn.execute("SELECT * FROM vitals WHERE patient_id=? ORDER BY recorded_at DESC LIMIT 20", (patient_id,)).fetchall()]
    prescriptions = [dict(r) for r in conn.execute("SELECT * FROM prescriptions WHERE patient_id=?", (patient_id,)).fetchall()]
    for rx in prescriptions:
        rx["items"] = json.loads(rx["items"]) if isinstance(rx["items"], str) else rx["items"]
    notes = [dict(r) for r in conn.execute("SELECT * FROM clinical_notes WHERE patient_id=?", (patient_id,)).fetchall()]
    labs = [dict(r) for r in conn.execute("SELECT * FROM lab_results WHERE patient_id=?", (patient_id,)).fetchall()]
    appointments = [dict(r) for r in conn.execute("SELECT * FROM appointments WHERE patient_id=?", (patient_id,)).fetchall()]
    diagnoses = [dict(r) for r in conn.execute("SELECT * FROM diagnosis_codes WHERE patient_id=?", (patient_id,)).fetchall()]
    referrals_list = [dict(r) for r in conn.execute("SELECT * FROM referrals WHERE patient_id=?", (patient_id,)).fetchall()]
    invoices_list = [dict(r) for r in conn.execute("SELECT * FROM invoices WHERE patient_id=?", (patient_id,)).fetchall()]
    for inv in invoices_list:
        inv["items"] = json.loads(inv["items"]) if isinstance(inv["items"], str) else inv["items"]
    insurance_list = [dict(r) for r in conn.execute("SELECT * FROM insurance WHERE patient_id=?", (patient_id,)).fetchall()]
    conn.close()

    return {
        "patient": p,
        "allergies": allergies,
        "conditions": conditions,
        "medications": medications,
        "vitals": vitals,
        "prescriptions": prescriptions,
        "clinical_notes": notes,
        "lab_results": labs,
        "appointments": appointments,
        "diagnoses": diagnoses,
        "referrals": referrals_list,
        "invoices": invoices_list,
        "insurance": insurance_list,
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }


# ── FHIR-Compatible Export ────────────────────────────────────

@router.get("/api/patient/{patient_id}/fhir")
def export_fhir(patient_id: str):
    conn = get_db()
    patient = conn.execute("SELECT * FROM patients WHERE id=?", (patient_id,)).fetchone()
    if not patient:
        conn.close()
        raise HTTPException(404, "Patient not found")
    p = dict(patient)
    allergies = [dict(r) for r in conn.execute("SELECT * FROM allergies WHERE patient_id=?", (patient_id,)).fetchall()]
    conditions = [dict(r) for r in conn.execute("SELECT * FROM conditions WHERE patient_id=?", (patient_id,)).fetchall()]
    medications = [dict(r) for r in conn.execute("SELECT * FROM medications WHERE patient_id=?", (patient_id,)).fetchall()]
    vitals = [dict(r) for r in conn.execute("SELECT * FROM vitals WHERE patient_id=? ORDER BY recorded_at DESC LIMIT 5", (patient_id,)).fetchall()]
    conn.close()

    gender_map = {"male": "male", "female": "female", "m": "male", "f": "female"}
    fhir_bundle = {
        "resourceType": "Bundle",
        "type": "document",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": p["id"],
                    "name": [{"use": "official", "text": p.get("name", "")}],
                    "telecom": [{"system": "phone", "value": p["phone"]}],
                    "gender": gender_map.get((p.get("gender") or "").lower(), "unknown"),
                    "birthDate": p.get("date_of_birth", ""),
                }
            }
        ] + [
            {
                "resource": {
                    "resourceType": "AllergyIntolerance",
                    "id": a["id"],
                    "patient": {"reference": f"Patient/{patient_id}"},
                    "code": {"text": a["allergen"]},
                    "criticality": "high" if a.get("severity") == "severe" else "low",
                    "recordedDate": a.get("noted_at", ""),
                }
            } for a in allergies
        ] + [
            {
                "resource": {
                    "resourceType": "Condition",
                    "id": c["id"],
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "code": {"text": c["name"]},
                    "clinicalStatus": {"coding": [{"code": c.get("status", "active")}]},
                }
            } for c in conditions
        ] + [
            {
                "resource": {
                    "resourceType": "MedicationStatement",
                    "id": m["id"],
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "medicationCodeableConcept": {"text": m["name"]},
                    "dosage": [{"text": f"{m.get('dosage', '')} {m.get('frequency', '')}".strip()}],
                    "status": "active" if m.get("status") == "active" else "stopped",
                }
            } for m in medications
        ] + [
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": v["id"],
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "effectiveDateTime": v.get("recorded_at", ""),
                    "component": [
                        comp for comp in [
                            {"code": {"text": "Systolic Blood Pressure"}, "valueQuantity": {"value": v["systolic"], "unit": "mmHg"}} if v.get("systolic") else None,
                            {"code": {"text": "Diastolic Blood Pressure"}, "valueQuantity": {"value": v["diastolic"], "unit": "mmHg"}} if v.get("diastolic") else None,
                            {"code": {"text": "Heart Rate"}, "valueQuantity": {"value": v["heart_rate"], "unit": "bpm"}} if v.get("heart_rate") else None,
                            {"code": {"text": "Body Temperature"}, "valueQuantity": {"value": v["temperature"], "unit": "°F"}} if v.get("temperature") else None,
                            {"code": {"text": "SpO2"}, "valueQuantity": {"value": v["spo2"], "unit": "%"}} if v.get("spo2") else None,
                        ] if comp is not None
                    ],
                }
            } for v in vitals
        ],
    }
    return fhir_bundle
