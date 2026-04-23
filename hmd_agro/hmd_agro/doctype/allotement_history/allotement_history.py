# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class AllotementHistory(Document):
    pass


def lot_on_date(animal, date):
    """Return the cow's lot on date D by replaying the audit log.
    Looks up the most recent Allotement History entry with creation <= D.
    Falls back to the cow's current Animal.id_lot if no history exists yet
    (i.e. she hasn't moved since tracking started)."""
    d = str(getdate(date))
    row = frappe.db.sql("""
        SELECT to_lot FROM `tabAllotement History`
        WHERE animal = %s AND DATE(creation) <= %s
        ORDER BY creation DESC LIMIT 1
    """, (animal, d))
    if row and row[0][0]:
        return row[0][0]
    return frappe.db.get_value("Animal", animal, "id_lot")


def lot_population_on_date(date):
    """Count of animals per lot on date D. For each animal present on D, takes
    her most recent Allotement History entry ≤ D, falling back to current
    Animal.id_lot when no entry exists (i.e. dates before tracking started).
    Returns {lot_name: count}."""
    d = str(getdate(date))
    rows = frappe.db.sql("""
        SELECT lot, COUNT(*) AS n FROM (
            SELECT
                COALESCE(
                    (SELECT h.to_lot FROM `tabAllotement History` h
                     WHERE h.animal = a.name AND DATE(h.creation) <= %s
                     ORDER BY h.creation DESC LIMIT 1),
                    a.id_lot
                ) AS lot
            FROM `tabAnimal` a
            WHERE (CASE WHEN a.est_achat = 1 THEN a.date_entree ELSE a.date_naissance END) <= %s
              AND (a.statut = 'ACTIF' OR (a.date_sortie IS NOT NULL AND a.date_sortie > %s))
        ) AS x
        WHERE x.lot IS NOT NULL AND x.lot != ''
        GROUP BY lot
    """, (d, d, d), as_dict=True)
    return {r.lot: int(r.n) for r in rows}


@frappe.whitelist()
def baseline_all_animals():
    """One-shot: insert a BASELINE history row for every animal that has a lot
    but no history yet. Use this once after deploying the doctype so every
    cow has a starting point."""
    rows = frappe.db.sql("""
        SELECT a.name, a.id_lot
        FROM `tabAnimal` a
        WHERE a.id_lot IS NOT NULL AND a.id_lot != ''
          AND NOT EXISTS (
              SELECT 1 FROM `tabAllotement History` h WHERE h.animal = a.name
          )
    """, as_dict=True)
    created = 0
    for r in rows:
        frappe.get_doc({
            "doctype": "Allotement History",
            "animal": r.name,
            "from_lot": None,
            "to_lot": r.id_lot,
            "moved_by": frappe.session.user,
            "source": "BASELINE",
            "reason": "Initial state at tracking start",
        }).insert(ignore_permissions=True)
        created += 1
    frappe.db.commit()
    return {"baselined": created}
