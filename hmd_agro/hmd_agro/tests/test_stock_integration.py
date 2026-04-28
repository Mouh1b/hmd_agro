"""
Sprint 5 — Phase A — Step 3 validation.

End-to-end test of dual-write: when a Traitement is created/deleted, both
Medicament.stock_actuel AND Bin.actual_qty must move in lockstep.

Run: bench --site hmd.localhost execute hmd_agro.hmd_agro.tests.test_stock_integration.run
"""
import frappe
from frappe.utils import today

PREFIX = "TEST-INT-"
WAREHOUSE = "Magasin Principal - HMD"


def _bin_qty(item_code):
    return frappe.db.get_value("Bin",
        {"item_code": item_code, "warehouse": WAREHOUSE},
        "actual_qty") or 0


def _cleanup():
    """Remove all TEST-INT-* fixtures from prior runs via raw DB delete.
    Bypasses ERPNext doc lifecycle (cancel/save) to avoid SLE timeline re-validation
    that throws NegativeStockError on dual-write compensation pairs.
    Test-only — no audit-trail concerns."""
    test_item = f"MED-{PREFIX}MED1"

    # 1. Stock Entries referencing our test data
    se_names = frappe.db.sql("""
        SELECT name FROM `tabStock Entry`
        WHERE remarks LIKE %s OR remarks LIKE %s OR remarks LIKE %s
    """, (f"%{PREFIX}%", f"%{test_item}%", f"%Médicament {PREFIX}%"))
    for (se_name,) in se_names:
        frappe.db.sql("DELETE FROM `tabStock Entry Detail` WHERE parent=%s", se_name)
        frappe.db.sql("DELETE FROM `tabStock Entry` WHERE name=%s", se_name)
    # 2. Stock Ledger Entries + Bins for the test item
    frappe.db.sql("DELETE FROM `tabStock Ledger Entry` WHERE item_code=%s", test_item)
    frappe.db.sql("DELETE FROM `tabBin` WHERE item_code=%s", test_item)
    # 3. Traitements + child rows
    t_names = frappe.db.sql("SELECT name FROM `tabTraitement` WHERE animal LIKE %s",
                             f"{PREFIX}%")
    for (t_name,) in t_names:
        frappe.db.sql("DELETE FROM `tabTraitement Medicale` WHERE parent=%s", t_name)
        frappe.db.sql("DELETE FROM `tabTraitement` WHERE name=%s", t_name)
    # 4. Test Animals
    frappe.db.sql("DELETE FROM `tabAnimal` WHERE name LIKE %s", f"{PREFIX}%")
    # 5. Test Items
    frappe.db.sql("DELETE FROM `tabItem` WHERE name LIKE %s", f"MED-{PREFIX}%")
    # 6. Test Medicaments
    frappe.db.sql("DELETE FROM `tabMedicament` WHERE name LIKE %s", f"{PREFIX}%")
    frappe.db.commit()


def _check(cond, msg, results):
    if cond:
        print(f"  OK   {msg}")
        results["pass"] += 1
    else:
        print(f"  FAIL {msg}")
        results["fail"] += 1


def run():
    print("\n" + "=" * 70)
    print("  Sprint 5 — Test intégration dual-write Traitement → Stock Entry")
    print("=" * 70)
    results = {"pass": 0, "fail": 0}

    _cleanup()

    # ── Setup: create test Médicament + run migration on it
    med_name = f"{PREFIX}MED1"
    med = frappe.get_doc({
        "doctype": "Medicament",
        "nom_medicament": med_name,
        "type_medicament": "ANTIBIOTIQUE",
        "delai_attente_lait": 5,
        "stock_actuel": 10,
    })
    med.insert(ignore_permissions=True)

    from hmd_agro.hmd_agro.setup.medicament_migration import migrate_medicaments
    migrate_medicaments()
    frappe.db.commit()

    item_code = f"MED-{med_name}"
    initial_stock = frappe.db.get_value("Medicament", med_name, "stock_actuel")
    initial_bin = _bin_qty(item_code)
    print(f"\n  Médicament {med_name} migré → Item {item_code}")
    print(f"  Etat initial: stock_actuel={initial_stock}, Bin.actual_qty={initial_bin}\n")
    _check(initial_stock == 10, "stock_actuel initial = 10", results)
    _check(initial_bin == 10, "Bin.actual_qty initial = 10", results)

    # ── Create test Animal
    animal = frappe.get_doc({
        "doctype": "Animal",
        "identification_tn": f"{PREFIX}A1",
        "nom_metier": f"{PREFIX}A1",
        "categorie": "VACHE", "sexe": "F",
        "statut": "ACTIF", "etat_lactation": "EN_PRODUCTION", "etat_gestation": "VIDE",
        "date_naissance": "2020-01-01", "date_entree": "2024-01-01",
    })
    animal.name = f"{PREFIX}A1"
    animal.db_insert()
    frappe.db.commit()

    # ── Create Traitement avec 1 ligne médicament
    print("  ── Création Traitement (1 ligne médicament)")
    traitement = frappe.get_doc({
        "doctype": "Traitement",
        "animal": animal.name,
        "date_traitement": today(),
        "type_traitement": "TRAITEMENT_MEDICAL",
        "praticien": "Test",
        "medicaments": [{
            "medicament": med_name,
            "dose": 5,
            "unite_dose": "ml",
            "voie_administration": "ORALE",
        }],
    })
    traitement.insert(ignore_permissions=True)
    frappe.db.commit()

    after_create_stock = frappe.db.get_value("Medicament", med_name, "stock_actuel")
    after_create_bin = _bin_qty(item_code)
    print(f"  Après création: stock_actuel={after_create_stock}, Bin.actual_qty={after_create_bin}")
    _check(after_create_stock == 9, "stock_actuel décrémenté à 9 (vieux chemin)", results)
    _check(after_create_bin == 9, "Bin.actual_qty décrémenté à 9 (nouveau chemin)", results)
    _check(after_create_stock == after_create_bin,
        f"COHÉRENCE: stock_actuel ({after_create_stock}) == Bin ({after_create_bin})", results)

    # ── Vérifier qu'un Stock Entry Material Issue a bien été créé
    issue_count = frappe.db.count("Stock Entry",
        {"stock_entry_type": "Material Issue", "docstatus": 1,
         "remarks": ["like", f"%Traitement {traitement.name}%"]})
    _check(issue_count == 1,
        f"1 Stock Entry Material Issue créé avec remarks référence Traitement", results)

    # ── Supprimer le Traitement
    print("\n  ── Suppression Traitement")
    frappe.delete_doc("Traitement", traitement.name, ignore_permissions=True)
    frappe.db.commit()

    after_delete_stock = frappe.db.get_value("Medicament", med_name, "stock_actuel")
    after_delete_bin = _bin_qty(item_code)
    print(f"  Après suppression: stock_actuel={after_delete_stock}, Bin.actual_qty={after_delete_bin}")
    _check(after_delete_stock == 10, "stock_actuel restauré à 10", results)
    _check(after_delete_bin == 10, "Bin.actual_qty restauré à 10 (Material Receipt compensatoire)", results)
    _check(after_delete_stock == after_delete_bin,
        f"COHÉRENCE: stock_actuel ({after_delete_stock}) == Bin ({after_delete_bin})", results)

    # ── Audit cheptel: tous les Médicaments réels doivent avoir cohérence
    print("\n  ── Audit drift sur tous les Médicaments du système")
    drifts = []
    for m in frappe.get_all("Medicament", fields=["name", "stock_actuel", "item"]):
        if not m.item:
            continue
        bin_q = _bin_qty(m.item) if m.item else 0
        if int(m.stock_actuel or 0) != int(bin_q):
            drifts.append((m.name, m.stock_actuel, bin_q))
    _check(len(drifts) == 0,
        f"Aucun drift détecté sur les Médicaments en production",
        results)
    if drifts:
        for d in drifts:
            print(f"     ⚠️  {d[0]}: stock_actuel={d[1]} ≠ Bin={d[2]}")

    # ── Cleanup
    _cleanup()

    print("\n" + "=" * 70)
    print(f"  RÉSULTATS: {results['pass']}/{results['pass']+results['fail']} passés, "
          f"{results['fail']} échoués")
    print("=" * 70)
    return results
