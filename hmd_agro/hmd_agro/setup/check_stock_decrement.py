"""One-shot check: did the most recent TRAITEMENT_MEDICAL decrement Medicament.stock_actuel?"""
import frappe


def run():
    last = frappe.get_all("Traitement",
        filters={"type_traitement": "TRAITEMENT_MEDICAL"},
        fields=["name", "animal", "date_traitement", "creation"],
        order_by="creation desc", limit_page_length=1)
    if not last:
        print("Aucun TRAITEMENT_MEDICAL trouvé.")
        return
    t = last[0]
    print(f"\nDernier TRAITEMENT_MEDICAL: {t.name}  (créé {t.creation}, animal {t.animal})\n")

    rows = frappe.get_all("Traitement Medicale",
        filters={"parent": t.name},
        fields=["medicament", "dose", "unite_dose"])
    if not rows:
        print("  Aucune ligne de médicament dans ce traitement.")
        return

    for r in rows:
        med = frappe.db.get_value("Medicament", r.medicament,
            ["stock_actuel", "type_medicament"], as_dict=True)
        print(f"  - médicament: {r.medicament}")
        print(f"      dose: {r.dose} {r.unite_dose}")
        print(f"      stock_actuel actuel: {med.stock_actuel}")
        print(f"      type_medicament: {med.type_medicament}")
        # Show any direct DB modification history if available
