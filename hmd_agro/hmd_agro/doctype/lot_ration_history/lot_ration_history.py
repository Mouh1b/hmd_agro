# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class LotRationHistory(Document):
    pass


def ration_on_date(lot, date):
    """Most recent ration assigned to `lot` on/before `date`. Falls back to the
    lot's current id_ration_actuelle if no history exists yet."""
    d = str(getdate(date))
    row = frappe.db.sql("""
        SELECT to_ration FROM `tabLot Ration History`
        WHERE lot = %s AND DATE(creation) <= %s
        ORDER BY creation DESC LIMIT 1
    """, (lot, d))
    if row and row[0][0]:
        return row[0][0]
    return frappe.db.get_value("Lot", lot, "id_ration_actuelle")


@frappe.whitelist()
def baseline_all_lots():
    """One-shot: insert a BASELINE entry for every lot that has a ration but
    no history yet. Run once after deploying the doctype."""
    rows = frappe.db.sql("""
        SELECT l.name, l.id_ration_actuelle
        FROM `tabLot` l
        WHERE l.actif = 1 AND l.id_ration_actuelle IS NOT NULL AND l.id_ration_actuelle != ''
          AND NOT EXISTS (
              SELECT 1 FROM `tabLot Ration History` h WHERE h.lot = l.name
          )
    """, as_dict=True)
    created = 0
    for r in rows:
        frappe.get_doc({
            "doctype": "Lot Ration History",
            "lot": r.name,
            "from_ration": None,
            "to_ration": r.id_ration_actuelle,
            "changed_by": frappe.session.user,
            "source": "BASELINE",
        }).insert(ignore_permissions=True)
        created += 1
    frappe.db.commit()
    return {"baselined": created}
