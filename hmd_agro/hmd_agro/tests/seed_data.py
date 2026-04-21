"""
Seed 6 test animals with diverse activity histories.
Uses real save() so all hooks cascade — produces consistent state.

Run:  bench --site hmd.localhost execute hmd_agro.hmd_agro.tests.seed_data.seed
Undo: bench --site hmd.localhost execute hmd_agro.hmd_agro.tests.seed_data.cleanup
"""

import frappe

PREFIX_TN = "999000"  # All seeded animals: 9990000001..9990000006
LOT = "Individuel"
TAUREAU = "Triad"
MERE_EXTERNE = "mere_externe_01"


# ─── Helpers (use real save() — hooks fire) ──────────────────────────────────

def _animal(suffix, date_naissance, date_entree):
    # Gap of 10 between mothers — calves get auto-assigned MAX+1 by Velage hook,
    # so each mother needs slack room for her newborns without colliding with the next.
    tn = f"{PREFIX_TN}{suffix * 10:04d}"
    doc = frappe.get_doc({
        "doctype": "Animal",
        "identification_tn": tn,
        "categorie": "GENISSE",
        "sexe": "F",
        "date_naissance": date_naissance,
        "est_achat": 1,
        "date_entree": date_entree,
        "id_pere": TAUREAU,
        "id_mere_externe": MERE_EXTERNE,
        "id_lot": LOT,
        "statut": "ACTIF",
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def _ia(animal, date_ia, resultat="REUSSIE"):
    frappe.get_doc({
        "doctype": "Insemination",
        "animal": animal,
        "date_ia": date_ia,
        "taureau": TAUREAU,
        "type_semence": "CONVENTIONNELLE",
        "resultat": resultat,
    }).insert(ignore_permissions=True)


def _velage(animal, date_velage, sexe="F"):
    frappe.get_doc({
        "doctype": "Velage",
        "animal": animal,
        "date_velage": date_velage,
        "type_velage": "FACILE",
        "nombre_veaux": "1",
        "sexe_veau1": sexe,
        "vivant_veau1": 1,
    }).insert(ignore_permissions=True)


def _avortement(animal, date_avortement):
    frappe.get_doc({
        "doctype": "Avortement",
        "animal": animal,
        "date_avortement": date_avortement,
        "cause": "INCONNUE",
    }).insert(ignore_permissions=True)


def _tarissement(animal, date_tarissement):
    """Find the EN_COURS lactation and close it."""
    name = frappe.db.get_value("Lactation", {"animal": animal, "statut": "EN_COURS"}, "name")
    if not name:
        raise Exception(f"No EN_COURS lactation for {animal} to tarit")
    lac = frappe.get_doc("Lactation", name)
    lac.statut = "TARIE"
    lac.date_tarissement = date_tarissement
    lac.save(ignore_permissions=True)


# ─── Main ────────────────────────────────────────────────────────────────────

def seed():
    """Create 6 animals with planned histories. Idempotent (cleans up first)."""
    cleanup()

    # Animal 1 — VACHE EN_PRODUCTION GESTANTE (Lact 1 ongoing, 2nd IA succeeded)
    a1 = _animal(1, "2022-01-15", "2023-08-01")
    _ia(a1, "2023-12-01", "REUSSIE")
    _velage(a1, "2024-09-07")
    _ia(a1, "2025-02-01", "REUSSIE")

    # Animal 2 — VACHE TARIE GESTANTE (Lact 1 ended, waiting for 2nd velage)
    a2 = _animal(2, "2022-03-01", "2023-09-01")
    _ia(a2, "2023-12-15", "REUSSIE")
    _velage(a2, "2024-09-21")
    _ia(a2, "2025-01-15", "REUSSIE")
    _tarissement(a2, "2025-09-15")

    # Animal 3 — VACHE EN_PRODUCTION VIDE (had ONE failed IA before success)
    a3 = _animal(3, "2022-06-01", "2023-12-01")
    _ia(a3, "2024-02-01", "ECHOUEE")
    _ia(a3, "2024-05-01", "REUSSIE")
    _velage(a3, "2025-02-04")

    # Animal 4 — VACHE EN_PRODUCTION VIDE (2 lactations done, in Lact 2)
    a4 = _animal(4, "2021-09-01", "2023-03-01")
    _ia(a4, "2023-06-01", "REUSSIE")
    _velage(a4, "2024-03-08")
    _ia(a4, "2024-07-01", "REUSSIE")
    _tarissement(a4, "2025-01-08")
    _velage(a4, "2025-04-08")

    # Animal 5 — VACHE EN_PRODUCTION VIDE (had ONE avortement before successful pregnancy)
    a5 = _animal(5, "2022-09-01", "2024-02-01")
    _ia(a5, "2024-06-01", "REUSSIE")
    _avortement(a5, "2024-10-15")
    _ia(a5, "2025-01-15", "REUSSIE")
    _velage(a5, "2025-10-22")

    # Animal 6 — GENISSE GESTANTE (1st pregnancy, near calving)
    a6 = _animal(6, "2023-04-01", "2024-09-01")
    _ia(a6, "2025-09-15", "REUSSIE")

    # ─── Suggestion-engine targeted cases (today = 2026-04-21) ─────────────────

    # Animal 7 — PRIMIPARE FV (DIM ≈ 60 days, 1st lactation, → FV)
    a7 = _animal(7, "2022-08-01", "2024-08-01")
    _ia(a7, "2025-05-16", "REUSSIE")
    _velage(a7, "2026-02-20")

    # Animal 8 — MULTIPARE THP (Lact 2 ongoing, DIM ≈ 80 days, → THP)
    a8 = _animal(8, "2022-01-01", "2023-08-01")
    _ia(a8, "2023-11-25", "REUSSIE")
    _velage(a8, "2024-09-01")
    _ia(a8, "2025-04-26", "REUSSIE")
    _tarissement(a8, "2026-01-15")
    _velage(a8, "2026-01-31")

    # Animal 9 — VACHE EN_PRODUCTION GESTANTE near calving (≈45d), → TARISSEMENT
    a9 = _animal(9, "2022-01-01", "2023-08-01")
    _ia(a9, "2023-12-25", "REUSSIE")
    _velage(a9, "2024-10-01")
    _ia(a9, "2025-08-29", "REUSSIE")  # velage prévue ≈ 2026-06-05

    # Animal 10 — PRIMIPARE FP (DIM ≈ 320 days, 1st lactation, → FP)
    a10 = _animal(10, "2022-06-01", "2024-01-01")
    _ia(a10, "2024-08-29", "REUSSIE")
    _velage(a10, "2025-06-05")

    frappe.db.commit()
    return {"created": [a1, a2, a3, a4, a5, a6, a7, a8, a9, a10]}


def cleanup():
    """Remove all seeded data (animals + their events + their lactations)."""
    seed_animals = frappe.db.sql_list(
        "SELECT name FROM `tabAnimal` WHERE identification_tn LIKE %s",
        (f"{PREFIX_TN}%",))
    if seed_animals:
        for dt in ("Velage", "Avortement", "Insemination", "Lactation"):
            frappe.db.sql(
                f"DELETE FROM `tab{dt}` WHERE animal IN %s", (seed_animals,))
        frappe.db.sql(
            "DELETE FROM `tabAnimal` WHERE name IN %s", (seed_animals,))
    frappe.db.commit()
    return {"deleted": len(seed_animals)}
