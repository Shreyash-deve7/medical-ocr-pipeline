"""
tests/test_routes_integration.py — Session 7 route-layer coverage (offline).

Drives the FastAPI route layer through ``TestClient`` with the OCR backend,
AI backend, and the upload background task mocked so nothing requires GPU /
network / real models. Exercises auth, patient, doctor, reports and admin
endpoints to lift backend coverage toward the 80% gate.

A temp DB / upload dir is configured via env vars (set BEFORE backend import)
so the app lifespan (init_db) never writes into the repo.
"""
import os
import sys
import tempfile

_TMP = tempfile.mkdtemp(prefix="medvault_routes_")
os.environ["DB_PATH"] = os.path.join(_TMP, "medapp.db")
os.environ["UPLOAD_DIR"] = os.path.join(_TMP, "uploads")

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from fastapi.testclient import TestClient
from backend.main import app
import database as db_module
import auth as auth_module
from services.ai_service import AIProvider


class _FakeAI(AIProvider):
    def analyze(self, prompt, text, images):
        return "fake analysis output"


@pytest.fixture
def client(monkeypatch):
    # Avoid any real OCR / AI / background processing in the test process.
    monkeypatch.setattr("services.ocr_service.AutoOCRProvider.extract_text",
                        lambda self, fp, ft: "fake ocr text")
    monkeypatch.setattr("services.ocr_service.AutoOCRProvider.extract_structured",
                        lambda self, fp, ft: [])
    monkeypatch.setattr("routes.reports_routes.build_ai", lambda engine, config: _FakeAI())
    monkeypatch.setattr("services.pipeline_service.process_report_automatic",
                        lambda rid: None)
    # Seed a default AI provider so the analyze route takes the build_ai path.
    db_module.init_db()
    # The upload route writes to backend/uploads (hardcoded, ignores config).
    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "backend", "uploads"),
                exist_ok=True)
    conn = db_module.get_db()
    conn.execute(
        "INSERT OR IGNORE INTO providers (id,kind,name,engine,config,is_default,created_at) "
        "VALUES ('aid','ai','default','gemini','{}',1,'now')")
    conn.commit()
    conn.close()
    with TestClient(app) as c:
        yield c


def _decode_sub(token):
    return auth_module.decode_token(token)["sub"]


def test_auth_and_patient_and_reports_and_admin(client):
    # ── Auth ──
    r = client.post("/api/patient/register",
                    json={"phone": "9990000001", "password": "pw", "name": "Pat"})
    assert r.status_code == 200
    ptoken = client.post("/api/patient/login",
                         json={"phone": "9990000001", "password": "pw"}).json()["token"]
    patient_id = _decode_sub(ptoken)

    # duplicate register -> error
    assert client.post("/api/patient/register",
                       json={"phone": "9990000001", "password": "pw", "name": "x"}).status_code >= 400
    # wrong password -> error
    assert client.post("/api/patient/login",
                       json={"phone": "9990000001", "password": "bad"}).status_code >= 400

    r = client.post("/api/doctor/register",
                    json={"phone": "9990000002", "password": "pw", "name": "Doc"})
    assert r.status_code == 200
    drtoken = client.post("/api/doctor/login",
                          json={"phone": "9990000002", "password": "pw"}).json()["token"]

    # ── Patient profile + clinical records ──
    assert client.get("/api/patient/profile", params={"token": ptoken}).status_code == 200
    assert client.put("/api/patient/profile", params={"token": ptoken},
                      json={"name": "Pat", "gender": "F"}).status_code == 200

    # allergies
    aid = client.post(f"/api/patient/{patient_id}/allergies",
                      json={"allergen": "Penicillin"}).json()["id"]
    assert client.get(f"/api/patient/{patient_id}/allergies").status_code == 200
    assert client.delete(f"/api/allergies/{aid}").status_code == 200
    # conditions
    cid = client.post(f"/api/patient/{patient_id}/conditions",
                      json={"name": "Hypertension"}).json()["id"]
    assert client.get(f"/api/patient/{patient_id}/conditions").status_code == 200
    assert client.delete(f"/api/conditions/{cid}").status_code == 200
    # medications
    mid = client.post(f"/api/patient/{patient_id}/medications",
                      json={"name": "Metformin"}).json()["id"]
    assert client.get(f"/api/patient/{patient_id}/medications").status_code == 200
    assert client.delete(f"/api/medications/{mid}").status_code == 200
    # vitals
    assert client.post("/api/vitals",
                       json={"patient_id": patient_id, "systolic": 120,
                             "diastolic": 80}).status_code == 200
    assert client.get(f"/api/patient/{patient_id}/vitals").status_code == 200
    # prescriptions
    assert client.post("/api/prescriptions",
                       json={"patient_id": patient_id, "diagnosis": "d"}).status_code == 200
    assert client.get(f"/api/patient/{patient_id}/prescriptions").status_code == 200
    # notes
    assert client.post("/api/notes",
                       json={"patient_id": patient_id, "assessment": "a"}).status_code == 200
    assert client.get(f"/api/patient/{patient_id}/notes").status_code == 200
    # appointments
    assert client.post("/api/appointments",
                       json={"patient_id": patient_id,
                             "scheduled_at": "2030-01-01T10:00:00"}).status_code == 200
    assert client.get("/api/appointments", params={"patient_id": patient_id}).status_code == 200
    # labs
    assert client.post("/api/labs",
                       json={"patient_id": patient_id, "test_name": "ALT",
                             "value": 40}).status_code == 200
    assert client.get(f"/api/patient/{patient_id}/labs").status_code == 200
    # diagnoses
    dgid = client.post(f"/api/patient/{patient_id}/diagnoses",
                       json={"patient_id": patient_id, "code": "E11",
                             "description": "T2DM"}).json()["id"]
    assert client.get(f"/api/patient/{patient_id}/diagnoses").status_code == 200
    assert client.delete(f"/api/diagnoses/{dgid}").status_code == 200
    # referrals
    assert client.post("/api/referrals",
                       json={"patient_id": patient_id, "to_specialty": "Cardiology",
                             "reason": "r"}).status_code == 200
    assert client.get(f"/api/patient/{patient_id}/referrals").status_code == 200
    # invoices
    assert client.post("/api/invoices",
                       json={"patient_id": patient_id, "items": [{"x": 1}],
                             "total": 10}).status_code == 200
    assert client.get(f"/api/patient/{patient_id}/invoices").status_code == 200
    # insurance
    iid = client.post(f"/api/patient/{patient_id}/insurance",
                      json={"patient_id": patient_id, "provider_name": "P",
                            "policy_number": "123"}).json()["id"]
    assert client.get(f"/api/patient/{patient_id}/insurance").status_code == 200
    assert client.delete(f"/api/insurance/{iid}").status_code == 200
    # export + fhir
    assert client.get(f"/api/patient/{patient_id}/export").status_code == 200
    assert client.get(f"/api/patient/{patient_id}/fhir").status_code == 200

    # ── Doctor endpoints ──
    assert client.get("/api/doctor/patients").status_code == 200
    assert client.get(f"/api/doctor/patient/{patient_id}").status_code == 200
    assert client.get(f"/api/doctor/patient/{patient_id}/reports").status_code == 200
    assert client.get("/api/doctor/profile", params={"doctor_id": _decode_sub(drtoken)}).status_code == 200
    assert client.put("/api/doctor/profile",
                      params={"doctor_id": _decode_sub(drtoken)},
                      json={"name": "Doc", "specialization": "Hepatology"}).status_code == 200

    # ── Reports: upload -> list -> file -> ocr-structured -> analyze ──
    png = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
           b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf"
           b"\xc0\xf0\x1f\x00\x05\x05\x02\x00\x8d\xae\x9c\xc8\x00\x00\x00\x00IEND"
           b"\xaeB`\x82")
    up = client.post("/api/patient/upload",
                     data={"token": ptoken},
                     files={"file": ("doc.png", png, "image/png")})
    assert up.status_code == 200
    rid = up.json()["report_id"]
    assert client.get("/api/patient/reports", params={"token": ptoken}).status_code == 200
    assert client.get(f"/api/file/{rid}").status_code == 200
    assert client.post("/api/doctor/ocr-structured",
                       json={"report_id": rid}).status_code == 200
    ana = client.post("/api/doctor/analyze", json={"report_id": rid})
    assert ana.status_code == 200 and "analysis" in ana.json()

    # ── Admin endpoints ──
    assert client.get("/api/drug-interactions").status_code == 200
    assert client.get("/api/drug-interactions/check",
                      params={"drugs": "Warfarin,Aspirin"}).status_code == 200
    assert client.get("/api/icd10", params={"q": "diabetes"}).status_code == 200
    assert client.get("/api/providers").status_code == 200
    assert client.get("/api/providers/engines").status_code == 200
    assert client.get("/api/analytics").status_code == 200
    assert client.get("/api/audit-log").status_code == 200
    # provider CRUD
    pr = client.post("/api/providers",
                     json={"kind": "ai", "name": "tmp", "engine": "ollama",
                           "config": {"model": "x"}})
    assert pr.status_code == 200
    pid = pr.json()["id"]
    assert client.put(f"/api/providers/{pid}",
                      json={"kind": "ai", "name": "tmp2", "engine": "ollama",
                            "config": {}}).status_code == 200
    assert client.delete(f"/api/providers/{pid}").status_code == 200
    # templates CRUD
    tr = client.post("/api/templates",
                     json={"template_type": "note", "name": "t", "content": {"a": 1}})
    assert tr.status_code == 200
    tid = tr.json()["id"]
    assert client.get("/api/templates", params={"template_type": "note"}).status_code == 200
    assert client.delete(f"/api/templates/{tid}").status_code == 200
    # messages + notifications
    assert client.post("/api/messages",
                       json={"receiver_type": "patient", "receiver_id": patient_id,
                             "subject": "s", "body": "b"}).status_code == 200
    assert client.get("/api/messages", params={"user_type": "patient",
                                               "user_id": patient_id}).status_code == 200
    assert client.get("/api/notifications", params={"user_type": "patient",
                                                    "user_id": patient_id}).status_code == 200
    assert client.put("/api/notifications/read-all",
                      params={"user_type": "patient", "user_id": patient_id}).status_code == 200


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
