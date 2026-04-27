import frappe
import json
from frappe.utils import getdate, add_days, today


@frappe.whitelist()
def get_lactating_animals(date):
    """Get all animals with active lactation and their traites for the given date."""
    date = getdate(date)

    # Animals whose lactation covered the selected date
    # (date_debut <= D AND (date_tarissement IS NULL OR date_tarissement >= D))
    # and who were present in the herd on D (statut ACTIF or exited on/after D).
    animals = frappe.db.sql("""
        SELECT
            a.name as animal,
            a.nom_metier,
            a.identification_tn,
            a.id_lot as lot,
            IFNULL(a.attente_lait_active, 0) as attente_lait,
            l.name as lactation
        FROM `tabAnimal` a
        INNER JOIN `tabLactation` l ON l.animal = a.name
            AND l.date_debut <= %s
            AND (l.date_tarissement IS NULL OR l.date_tarissement >= %s)
        WHERE a.statut = 'ACTIF'
           OR (a.date_sortie IS NOT NULL AND a.date_sortie >= %s)
        ORDER BY a.id_lot ASC, a.nom_metier DESC
    """, (date, date, date), as_dict=True)

    if not animals:
        return []

    animal_names = [a.animal for a in animals]

    # Existing traites for the selected date
    traites = frappe.db.sql("""
        SELECT animal, session, quantite_litres, name, id_lot
        FROM `tabTraite`
        WHERE date_traite = %s AND animal IN %s
    """, (date, animal_names), as_dict=True)

    traite_map = {}
    historic_lot = {}
    for t in traites:
        traite_map.setdefault(t.animal, {})[t.session] = {
            "qty": t.quantite_litres,
            "name": t.name
        }
        if t.id_lot:
            historic_lot[t.animal] = t.id_lot

    # Previous day totals for drop detection
    prev_date = add_days(date, -1)
    prev_totals = frappe.db.sql("""
        SELECT animal, SUM(quantite_litres) as total
        FROM `tabTraite`
        WHERE date_traite = %s AND animal IN %s
        GROUP BY animal
    """, (prev_date, animal_names), as_dict=True)

    prev_map = {p.animal: p.total for p in prev_totals}

    result = []
    for a in animals:
        at = traite_map.get(a.animal, {})
        result.append({
            "animal": a.animal,
            "nom_metier": a.nom_metier or a.animal,
            "identification_tn": a.identification_tn or "",
            "lot": historic_lot.get(a.animal) or a.lot or "",
            "attente_lait": a.attente_lait,
            "lactation": a.lactation,
            "matin": at.get("MATIN"),
            "soir": at.get("SOIR"),
            "prev_total": prev_map.get(a.animal, 0) or 0
        })

    return result


@frappe.whitelist()
def save_traites(date, entries):
    """Save multiple traites at once. Uses frappe.get_doc so all validations fire."""
    if isinstance(entries, str):
        entries = json.loads(entries)

    created = 0
    updated = 0
    errors = []

    for entry in entries:
        try:
            if entry.get("traite_name"):
                # Update existing
                doc = frappe.get_doc("Traite", entry["traite_name"])
                doc.quantite_litres = entry["quantite_litres"]
                doc.save()
                updated += 1
            else:
                # Create new
                doc = frappe.get_doc({
                    "doctype": "Traite",
                    "animal": entry["animal"],
                    "date_traite": date,
                    "session": entry["session"],
                    "quantite_litres": entry["quantite_litres"]
                })
                doc.insert()
                created += 1
        except Exception as e:
            errors.append({
                "animal": entry.get("animal"),
                "session": entry.get("session"),
                "error": str(e)
            })

    frappe.db.commit()

    return {
        "created": created,
        "updated": updated,
        "errors": errors
    }
