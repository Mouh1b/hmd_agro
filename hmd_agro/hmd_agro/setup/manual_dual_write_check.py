"""Manual check — completely independent of the test file.
Picks a real Médicament from your production data, observes before/after a
Traitement is inserted and then deleted, and prints raw values."""
import frappe
from frappe.utils import today


def _bin(item):
    return frappe.db.get_value("Bin",
        {"item_code": item, "warehouse": "Magasin Principal - HMD"},
        "actual_qty") or 0


def _stock(med):
    return frappe.db.get_value("Medicament", med, "stock_actuel")


def run():
    print("\n" + "=" * 70)
    print("  MANUAL OBSERVATION — dual-write Traitement / Médicament")
    print("=" * 70)

    # Pick the first migrated medicament that has stock > 1
    med = frappe.db.get_value("Medicament",
        {"item": ["!=", ""], "stock_actuel": [">", 1]},
        ["name", "item", "stock_actuel"], as_dict=True)
    if not med:
        print("Aucun médicament migré avec stock > 1.")
        return

    print(f"\n  Médicament choisi: {med.name}")
    print(f"  Item lié: {med.item}\n")

    # Pick the first ACTIF VACHE animal
    animal = frappe.db.get_value("Animal",
        {"statut": "ACTIF", "categorie": "VACHE"}, "name")
    if not animal:
        print("Aucune vache active disponible.")
        return
    print(f"  Animal cible: {animal}\n")

    # ── BEFORE
    s0 = _stock(med.name)
    b0 = _bin(med.item)
    print(f"  AVANT Traitement:  stock_actuel={s0}  Bin.actual_qty={b0}")

    # ── INSERT Traitement
    t = frappe.get_doc({
        "doctype": "Traitement",
        "animal": animal,
        "date_traitement": today(),
        "type_traitement": "TRAITEMENT_MEDICAL",
        "praticien": "Manual check",
        "medicaments": [{
            "medicament": med.name, "dose": 1, "unite_dose": "ml",
            "voie_administration": "ORALE",
        }],
    })
    t.insert(ignore_permissions=True)
    frappe.db.commit()
    print(f"  Traitement créé: {t.name}")

    s1 = _stock(med.name)
    b1 = _bin(med.item)
    print(f"  APRÈS création:    stock_actuel={s1}  Bin.actual_qty={b1}")
    print(f"  Δ stock_actuel = {s1 - s0}")
    print(f"  Δ Bin          = {b1 - b0}")
    print(f"  → Cohérence:   {'OK ✓' if s1 == int(b1) else 'DRIFT ❌'}")

    # ── DELETE Traitement
    frappe.delete_doc("Traitement", t.name, ignore_permissions=True)
    frappe.db.commit()

    s2 = _stock(med.name)
    b2 = _bin(med.item)
    print(f"\n  APRÈS suppression: stock_actuel={s2}  Bin.actual_qty={b2}")
    print(f"  Δ vs initial:  stock_actuel={s2 - s0}, Bin={b2 - b0}")
    print(f"  → Restauration: {'OK ✓' if s2 == s0 and b2 == b0 else 'PROBLÈME ❌'}")

    print("=" * 70)
