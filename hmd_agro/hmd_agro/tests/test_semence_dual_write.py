"""
Sprint 5 — Phase A — Step 5 validation.

End-to-end test of Insémination dual-write: when an Insémination is created/deleted,
both Semence.quantite_restante AND Batch.batch_qty must move in lockstep.

Run: bench --site hmd.localhost execute hmd_agro.hmd_agro.tests.test_semence_dual_write.run
"""
import frappe
from frappe.utils import today

PREFIX = "TEST-INS-"
WAREHOUSE = "Magasin Principal - HMD"


def _batch_qty(batch_id):
    return frappe.db.get_value("Batch", batch_id, "batch_qty") or 0


def _qte_restante(sem_name):
    return frappe.db.get_value("Semence", sem_name, "quantite_restante")


def _cleanup():
    """Raw DB delete of test fixtures."""
    test_item_pattern = f"SEM-{PREFIX}%"
    # SEs referencing test data
    se_names = frappe.db.sql("""
        SELECT name FROM `tabStock Entry`
        WHERE remarks LIKE %s OR remarks LIKE %s
    """, (f"%{PREFIX}%", f"%batch {PREFIX}%"))
    for (n,) in se_names:
        frappe.db.sql("DELETE FROM `tabStock Entry Detail` WHERE parent=%s", n)
        frappe.db.sql("DELETE FROM `tabStock Entry` WHERE name=%s", n)
    # SLEs + Bins
    frappe.db.sql("DELETE FROM `tabStock Ledger Entry` WHERE item_code LIKE %s",
                  test_item_pattern)
    frappe.db.sql("DELETE FROM `tabBin` WHERE item_code LIKE %s", test_item_pattern)
    # Inseminations
    for ia in frappe.get_all("Insemination", filters={"name": ["like", f"%{PREFIX}%"]}):
        frappe.db.sql("DELETE FROM `tabInsemination` WHERE name=%s", ia.name)
    # Animals + Taureau
    frappe.db.sql("DELETE FROM `tabAnimal` WHERE name LIKE %s", f"{PREFIX}%")
    # Semences
    sem_names = [r[0] for r in frappe.db.sql("SELECT name FROM `tabSemence` WHERE name LIKE %s",
                                              f"%{PREFIX}%")]
    for sn in sem_names:
        frappe.db.sql("DELETE FROM `tabSemence` WHERE name=%s", sn)
        frappe.db.sql("DELETE FROM `tabBatch` WHERE name=%s", sn)
    # Items
    frappe.db.sql("DELETE FROM `tabItem` WHERE name LIKE %s", test_item_pattern)
    # Taureau
    frappe.db.sql("DELETE FROM `tabTaureau` WHERE name LIKE %s", f"{PREFIX}%")
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
    print("  Sprint 5 — Test intégration dual-write Insémination → Stock Entry")
    print("=" * 70)
    results = {"pass": 0, "fail": 0}

    _cleanup()

    # Setup: Taureau + Semence + Animal
    taureau = frappe.get_doc({
        "doctype": "Taureau", "nom_taureau": f"{PREFIX}BULL",
        "code_taureau": f"{PREFIX}001", "race": "Holstein",
    })
    taureau.name = f"{PREFIX}BULL"
    taureau.db_insert()

    sem = frappe.get_doc({
        "doctype": "Semence",
        "taureau": taureau.name,
        "type_semence": "CONVENTIONNELLE",
        "date_reception": today(),
        "date_expiration": "2030-01-01",
        "quantite_recue": 10,
        "quantite_restante": 10,
        "prix_unitaire": 50,
    })
    sem.insert(ignore_permissions=True)

    from hmd_agro.hmd_agro.setup.semence_migration import migrate_semences
    migrate_semences()
    frappe.db.commit()

    item_code = f"SEM-{taureau.name}-CONV"
    print(f"\n  Semence test: {sem.name} → Item {item_code}")
    print(f"  État initial: quantite_restante=10, Batch.batch_qty={_batch_qty(sem.name)}\n")
    _check(_qte_restante(sem.name) == 10, "quantite_restante initial = 10", results)
    _check(_batch_qty(sem.name) == 10, "Batch.batch_qty initial = 10", results)

    # Animal
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

    # Create Insemination
    print("  ── Création Insémination")
    ia = frappe.get_doc({
        "doctype": "Insemination",
        "animal": animal.name,
        "taureau": taureau.name,
        "type_semence": "CONVENTIONNELLE",
        "date_ia": today(),
        "resultat": "EN_ATTENTE",
    })
    ia.insert(ignore_permissions=True)
    frappe.db.commit()

    after_create_q = _qte_restante(sem.name)
    after_create_b = _batch_qty(sem.name)
    print(f"  Après création: quantite_restante={after_create_q}, batch_qty={after_create_b}")
    _check(after_create_q == 9, "quantite_restante décrémenté à 9 (vieux chemin)", results)
    _check(after_create_b == 9, "Batch.batch_qty décrémenté à 9 (nouveau chemin)", results)
    _check(after_create_q == int(after_create_b),
        f"COHÉRENCE: quantite_restante ({after_create_q}) == batch ({after_create_b})", results)

    # Verify Material Issue Stock Entry created
    issue_count = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabStock Entry`
        WHERE stock_entry_type='Material Issue' AND docstatus=1
          AND remarks LIKE %s
    """, f"%Insemination {ia.name}%")[0][0]
    _check(issue_count == 1, "1 Stock Entry Material Issue créé", results)

    # Delete Insemination
    print("\n  ── Suppression Insémination")
    frappe.delete_doc("Insemination", ia.name, ignore_permissions=True)
    frappe.db.commit()

    after_delete_q = _qte_restante(sem.name)
    after_delete_b = _batch_qty(sem.name)
    print(f"  Après suppression: quantite_restante={after_delete_q}, batch_qty={after_delete_b}")
    _check(after_delete_q == 10, "quantite_restante restauré à 10", results)
    _check(after_delete_b == 10, "Batch.batch_qty restauré à 10", results)
    _check(after_delete_q == int(after_delete_b),
        f"COHÉRENCE: quantite_restante ({after_delete_q}) == batch ({after_delete_b})", results)

    # Audit drift on production Semences
    print("\n  ── Audit drift sur les Semences en production")
    drifts = []
    for s in frappe.get_all("Semence", fields=["name", "quantite_restante", "item"]):
        if not s.item:
            continue
        bq = _batch_qty(s.name)
        if int(s.quantite_restante or 0) != int(bq or 0):
            drifts.append((s.name, s.quantite_restante, bq))
    _check(len(drifts) == 0, "Aucun drift en production", results)
    for d in drifts:
        print(f"     ⚠️  {d[0]}: quantite_restante={d[1]} ≠ batch_qty={d[2]}")

    _cleanup()

    print("\n" + "=" * 70)
    print(f"  RÉSULTATS: {results['pass']}/{results['pass']+results['fail']} passés, "
          f"{results['fail']} échoués")
    print("=" * 70)
    return results
