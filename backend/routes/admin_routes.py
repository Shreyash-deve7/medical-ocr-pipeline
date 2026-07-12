"""backend/routes/admin_routes.py — cross-cutting admin / system endpoints (Session 6).

Extracted verbatim from ``main.py``:
  GET/POST /api/messages | PUT /api/messages/{id}/read
  GET      /api/notifications | PUT /api/notifications/{id}/read | PUT /api/notifications/read-all
  GET      /api/drug-interactions | GET /api/drug-interactions/check
  GET      /api/icd10
  GET/POST /api/templates | DELETE /api/templates/{id}
  GET      /api/audit-log
  GET      /api/analytics
  GET/POST /api/providers | PUT/DELETE /api/providers/{id} | GET /api/providers/engines
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from database import _notify, get_db
from schemas import MessageReq, ProviderReq, TemplateReq

router = APIRouter()


# ── Messages ─────────────────────────────────────────────────

@router.get("/api/messages")
def list_messages(user_type: str = Query("doctor"), user_id: str = Query("")):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM messages WHERE (sender_type=? AND sender_id=?) OR (receiver_type=? AND receiver_id=?) ORDER BY created_at DESC LIMIT 100",
        (user_type, user_id, user_type, user_id),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/api/messages")
def send_message(req: MessageReq, sender_type: str = Query("doctor"), sender_id: str = Query("")):
    mid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    conn.execute(
        "INSERT INTO messages (id, sender_type, sender_id, receiver_type, receiver_id, subject, body, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (mid, sender_type, sender_id, req.receiver_type, req.receiver_id, req.subject, req.body, now),
    )
    _notify(conn, req.receiver_type, req.receiver_id, f"New message: {req.subject or 'No subject'}", req.body[:100], "message")
    conn.commit()
    conn.close()
    return {"id": mid}


@router.put("/api/messages/{message_id}/read")
def mark_message_read(message_id: str):
    conn = get_db()
    conn.execute("UPDATE messages SET is_read=1 WHERE id=?", (message_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Notifications ────────────────────────────────────────────

@router.get("/api/notifications")
def list_notifications(user_type: str = Query("doctor"), user_id: str = Query(""), unread_only: bool = Query(False)):
    conn = get_db()
    query = "SELECT * FROM notifications WHERE user_type=? AND user_id=?"
    params = [user_type, user_id]
    if unread_only:
        query += " AND is_read=0"
    query += " ORDER BY created_at DESC LIMIT 50"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.put("/api/notifications/{notification_id}/read")
def mark_notification_read(notification_id: str):
    conn = get_db()
    conn.execute("UPDATE notifications SET is_read=1 WHERE id=?", (notification_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.put("/api/notifications/read-all")
def mark_all_notifications_read(user_type: str = Query("doctor"), user_id: str = Query("")):
    conn = get_db()
    conn.execute("UPDATE notifications SET is_read=1 WHERE user_type=? AND user_id=?", (user_type, user_id))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Drug Interactions ────────────────────────────────────────

@router.get("/api/drug-interactions")
def list_drug_interactions():
    conn = get_db()
    rows = conn.execute("SELECT * FROM drug_interactions ORDER BY severity DESC, drug_a").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/api/drug-interactions/check")
def check_drug_interactions(drugs: str = Query("")):
    drug_list = [d.strip().lower() for d in drugs.split(",") if d.strip()]
    if len(drug_list) < 2:
        return {"interactions": [], "checked": drug_list}
    conn = get_db()
    rows = conn.execute("SELECT * FROM drug_interactions").fetchall()
    conn.close()
    found = []
    for r in rows:
        d = dict(r)
        a_lower = d["drug_a"].lower()
        b_lower = d["drug_b"].lower()
        for i, da in enumerate(drug_list):
            for db in drug_list[i+1:]:
                # Match only when the user-supplied drug name is contained within
                # the known drug name (or is an exact match), not the reverse.
                # This prevents short queries like "in" from matching everything.
                a_match = (da == a_lower or da in a_lower.split() or a_lower == da or a_lower in da.split())
                b_match = (db == b_lower or db in b_lower.split() or b_lower == db or b_lower in db.split())
                if (a_match and b_match) or (b_match and a_match):
                    found.append(d)
    return {"interactions": found, "checked": drug_list}


# ── ICD-10 Codes ─────────────────────────────────────────────

@router.get("/api/icd10")
def search_icd10(q: str = Query("")):
    conn = get_db()
    if q:
        rows = conn.execute(
            "SELECT * FROM icd10_codes WHERE code LIKE ? OR description LIKE ? ORDER BY code LIMIT 30",
            (f"%{q}%", f"%{q}%"),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM icd10_codes ORDER BY code LIMIT 50").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Templates ────────────────────────────────────────────────

@router.get("/api/templates")
def list_templates(template_type: str = Query(None)):
    conn = get_db()
    if template_type:
        rows = conn.execute("SELECT * FROM templates WHERE template_type=? ORDER BY name", (template_type,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM templates ORDER BY template_type, name").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["content"] = json.loads(d["content"]) if isinstance(d["content"], str) else d["content"]
        result.append(d)
    return result


@router.post("/api/templates")
def create_template(req: TemplateReq):
    tid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    conn.execute(
        "INSERT INTO templates (id, template_type, name, content, created_at) VALUES (?,?,?,?,?)",
        (tid, req.template_type, req.name, json.dumps(req.content), now),
    )
    conn.commit()
    conn.close()
    return {"id": tid}


@router.delete("/api/templates/{template_id}")
def delete_template(template_id: str):
    conn = get_db()
    conn.execute("DELETE FROM templates WHERE id=?", (template_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Audit Log ────────────────────────────────────────────────

@router.get("/api/audit-log")
def get_audit_log(limit: int = Query(100)):
    conn = get_db()
    rows = conn.execute("SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Analytics Dashboard ──────────────────────────────────────

@router.get("/api/analytics")
def get_analytics():
    conn = get_db()
    patients_count = conn.execute("SELECT COUNT(*) as c FROM patients").fetchone()["c"]
    reports_count = conn.execute("SELECT COUNT(*) as c FROM reports").fetchone()["c"]
    analyzed_count = conn.execute("SELECT COUNT(*) as c FROM reports WHERE analyzed=1").fetchone()["c"]
    appointments_today = conn.execute(
        "SELECT COUNT(*) as c FROM appointments WHERE date(scheduled_at) = date('now') AND status='scheduled'"
    ).fetchone()["c"]
    appointments_upcoming = conn.execute(
        "SELECT COUNT(*) as c FROM appointments WHERE scheduled_at > datetime('now') AND status='scheduled'"
    ).fetchone()["c"]
    prescriptions_count = conn.execute("SELECT COUNT(*) as c FROM prescriptions").fetchone()["c"]
    vitals_count = conn.execute("SELECT COUNT(*) as c FROM vitals").fetchone()["c"]
    lab_count = conn.execute("SELECT COUNT(*) as c FROM lab_results").fetchone()["c"]

    recent_patients = conn.execute(
        "SELECT id, name, phone, created_at FROM patients ORDER BY created_at DESC LIMIT 5"
    ).fetchall()
    recent_appointments = conn.execute(
        "SELECT a.*, p.name as patient_name FROM appointments a JOIN patients p ON a.patient_id = p.id ORDER BY a.scheduled_at DESC LIMIT 5"
    ).fetchall()

    conn.close()
    return {
        "patients": patients_count,
        "reports": reports_count,
        "analyzed": analyzed_count,
        "pending_reports": reports_count - analyzed_count,
        "appointments_today": appointments_today,
        "appointments_upcoming": appointments_upcoming,
        "prescriptions": prescriptions_count,
        "vitals_recorded": vitals_count,
        "lab_results": lab_count,
        "recent_patients": [dict(r) for r in recent_patients],
        "recent_appointments": [dict(r) for r in recent_appointments],
    }


# ── Provider CRUD ─────────────────────────────────────────────

@router.get("/api/providers")
def list_providers():
    conn = get_db()
    rows = conn.execute("SELECT * FROM providers ORDER BY kind, name").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["config"] = json.loads(d["config"])
        cfg = d["config"]
        if "api_key" in cfg and cfg["api_key"]:
            cfg["api_key"] = cfg["api_key"][:6] + "..." + cfg["api_key"][-4:] if len(cfg["api_key"]) > 10 else "***"
        result.append(d)
    return result


@router.post("/api/providers")
def create_provider(req: ProviderReq):
    if req.kind not in ("ocr", "ai"):
        raise HTTPException(400, "kind must be 'ocr' or 'ai'")
    if req.kind == "ocr" and req.engine not in ("pipeline", "auto"):
        raise HTTPException(400, "Only the MedVault Dual Pipeline (pipeline/auto) is supported for OCR")
    pid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    if req.is_default:
        conn.execute("UPDATE providers SET is_default=0 WHERE kind=?", (req.kind,))
    conn.execute(
        "INSERT INTO providers (id, kind, name, engine, config, is_default, created_at) VALUES (?,?,?,?,?,?,?)",
        (pid, req.kind, req.name, req.engine, json.dumps(req.config), 1 if req.is_default else 0, now),
    )
    conn.commit()
    conn.close()
    return {"id": pid}


@router.put("/api/providers/{provider_id}")
def update_provider(provider_id: str, req: ProviderReq):
    if req.kind == "ocr" and req.engine not in ("pipeline", "auto"):
        raise HTTPException(400, "Only the MedVault Dual Pipeline (pipeline/auto) is supported for OCR")
    conn = get_db()
    if req.is_default:
        conn.execute("UPDATE providers SET is_default=0 WHERE kind=?", (req.kind,))
    conn.execute(
        "UPDATE providers SET name=?, engine=?, config=?, is_default=? WHERE id=?",
        (req.name, req.engine, json.dumps(req.config), 1 if req.is_default else 0, provider_id),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.delete("/api/providers/{provider_id}")
def delete_provider(provider_id: str):
    conn = get_db()
    conn.execute("DELETE FROM providers WHERE id=?", (provider_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/api/providers/engines")
def list_engines():
    return {
        "ocr": [
            {"id": "pipeline", "name": "MedVault Dual Pipeline (PaddleOCR + Qwen2.5-VL)", "fields": [
                {"key": "class_weights", "label": "Classifier Weights Path", "placeholder": "optional", "required": False},
                {"key": "paddle_endpoint", "label": "Printed OCR URL", "placeholder": "http://127.0.0.1:8001/ocr", "required": False},
                {"key": "qwen_server_url", "label": "Qwen VL URL", "placeholder": "http://127.0.0.1:8002/v1/chat/completions", "required": False},
            ]},
        ],
        "ai": [
            {"id": "gemini", "name": "Google Gemini", "fields": [
                {"key": "api_key", "label": "API Key", "placeholder": "AIza...", "required": True, "secret": True},
                {"key": "model", "label": "Model", "placeholder": "gemini-2.0-flash", "required": False},
            ]},
            {"id": "openai", "name": "OpenAI / Compatible", "fields": [
                {"key": "api_key", "label": "API Key", "placeholder": "sk-...", "required": True, "secret": True},
                {"key": "model", "label": "Model", "placeholder": "gpt-4o", "required": False},
                {"key": "base_url", "label": "Base URL", "placeholder": "https://api.openai.com/v1", "required": False},
            ]},
            {"id": "ollama", "name": "Ollama (Local)", "fields": [
                {"key": "model", "label": "Model", "placeholder": "llava", "required": False},
                {"key": "base_url", "label": "Base URL", "placeholder": "http://localhost:11434", "required": False},
            ]},
            {"id": "custom_openai", "name": "Custom Endpoint (OpenAI-compatible)", "fields": [
                {"key": "endpoint", "label": "Endpoint URL", "placeholder": "https://your-api.com/v1/chat/completions", "required": True},
                {"key": "api_key", "label": "API Key", "placeholder": "optional", "required": False, "secret": True},
                {"key": "model", "label": "Model", "placeholder": "optional", "required": False},
            ]},
        ],
    }
