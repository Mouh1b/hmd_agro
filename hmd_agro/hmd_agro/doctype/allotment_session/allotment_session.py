# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.model.document import Document


class AllotmentSession(Document):
    pass


def _moved(r):
    return (r.get("lot_before") or "") != (r.get("lot_after") or "")


@frappe.whitelist()
def confirm_session(session_date, rows, notes=None):
    """Persist a snapshot of the Allotement table at the moment changes are confirmed.
    Called from the dialogs (suggestion + manuel) right after lot moves are applied.

    `rows` is a JSON list of objects from the live report grid — one row per
    active cow. Rows where lot_before != lot_after are flagged as `moved`."""
    if isinstance(rows, str):
        rows = json.loads(rows)

    doc = frappe.get_doc({
        "doctype": "Allotment Session",
        "session_date": session_date,
        "created_by": frappe.session.user,
        "notes": notes or "",
        "moves_count": sum(1 for r in rows if _moved(r)),
        "rows": [{
            "animal": r.get("animal"),
            "nom_metier": r.get("nom_metier") or "",
            "lot_before": r.get("lot_before") or "",
            "lot_after": r.get("lot_after") or "",
            "moved": 1 if _moved(r) else 0,
            "dim": r.get("dim") or 0,
            "jours_gestation": r.get("jours_gestation") or 0,
            "production_j_2": r.get("production_j_2") or 0,
            "production_j_1": r.get("production_j_1") or 0,
            "production_j": r.get("production_j") or 0,
            "delta": r.get("delta"),
            "moyenne_3j": r.get("moyenne_3j") or 0,
            "suggestion": r.get("suggestion") or "",
        } for r in rows],
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"name": doc.name, "moves_count": doc.moves_count}


@frappe.whitelist()
def list_sessions(limit=30):
    """Return recent sessions for the Historique picker."""
    return frappe.db.sql("""
        SELECT name, session_date, moves_count, created_by, notes
        FROM `tabAllotment Session`
        ORDER BY session_date DESC, creation DESC
        LIMIT %s
    """, int(limit), as_dict=True)
