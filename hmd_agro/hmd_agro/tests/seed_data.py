"""
Seed test animals into the system.

Two modes:
  seed(n=10)        — ADDITIVE. Generates n random animals with realistic
                      lifecycles. Doesn't touch existing animals. Suffix
                      auto-picked above the highest existing.
  seed_baseline()   — Deterministic 17-cow fixture for rule-coverage tests.
                      Cleans up first, then re-creates the same set.
  cleanup()         — Removes all seeded animals (PREFIX_TN match).

Run examples:
  bench --site hmd.localhost execute hmd_agro.hmd_agro.tests.seed_data.seed --kwargs "{'n': 20}"
  bench --site hmd.localhost execute hmd_agro.hmd_agro.tests.seed_data.seed_baseline
  bench --site hmd.localhost execute hmd_agro.hmd_agro.tests.seed_data.cleanup
"""

import random
from datetime import timedelta

import frappe
from frappe.utils import getdate, today

PREFIX_TN = "999000"  # All seeded animals: 9990000010..9990000XX0
LOT = "Individuel"
TAUREAU = "Triad"
MERE_EXTERNE = "mere_externe_01"


# ─── Helpers (use real save() — hooks fire) ──────────────────────────────────

def _animal(suffix, date_naissance, date_entree):
    """Bought GENISSE — gap of 10 between mothers so velage-created calves
    don't collide with the next mother's ID."""
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


def _animal_born(suffix, date_naissance, mother, categorie="GENISSE", sexe="F"):
    """Born-on-farm animal — id_mere must point to an existing animal."""
    tn = f"{PREFIX_TN}{suffix * 10:04d}"
    doc = frappe.get_doc({
        "doctype": "Animal",
        "identification_tn": tn,
        "categorie": categorie,
        "sexe": sexe,
        "date_naissance": date_naissance,
        "est_achat": 0,
        "id_pere": TAUREAU,
        "id_mere": mother,
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


# ─── Random additive seed ────────────────────────────────────────────────────

ARCHETYPES = [
    ("young_genisse",            15),  # Genisse, no IA yet
    ("genisse_pending",          15),  # Genisse, IA REUSSIE recently (gestante)
    ("primipare_lactating",      20),  # 1 velage done, EN_COURS
    ("multipare_lactating",      25),  # 2 velages, 2nd EN_COURS
    ("primipare_tarie_gestante", 10),  # 1 velage + tarissement + new IA
    ("multipare_tarie_gestante", 10),  # 2 velages + tarissement + new IA
    ("with_avortement",           5),  # avortement in history, then velage
]


def _next_suffix():
    """Highest existing seed suffix + 1 (mothers use multiples of 10)."""
    rows = frappe.db.sql_list(
        "SELECT name FROM `tabAnimal` WHERE identification_tn LIKE %s",
        (f"{PREFIX_TN}%",))
    max_s = 0
    for n in rows:
        try:
            tail = int(n[len(PREFIX_TN):])
            if tail % 10 == 0:
                max_s = max(max_s, tail // 10)
        except (ValueError, TypeError):
            continue
    return max_s + 1


def _iso(d):
    return d.isoformat() if hasattr(d, "isoformat") else str(d)


def _pick_archetype():
    names = [a for a, _ in ARCHETYPES]
    weights = [w for _, w in ARCHETYPES]
    return random.choices(names, weights=weights)[0]


def _make_random_animal(suffix, today_d):
    """Build one animal of a randomly-picked archetype with realistic dates."""
    arc = _pick_archetype()

    if arc == "young_genisse":
        dob = today_d - timedelta(days=random.randint(420, 700))   # 14-23 months
        entry = dob + timedelta(days=random.randint(180, 360))
        return _animal(suffix, _iso(dob), _iso(entry))

    if arc == "genisse_pending":
        dob = today_d - timedelta(days=random.randint(700, 900))
        entry = dob + timedelta(days=random.randint(200, 400))
        a = _animal(suffix, _iso(dob), _iso(entry))
        ia_d = today_d - timedelta(days=random.randint(60, 270))
        if random.random() < 0.35:
            _ia(a, _iso(ia_d - timedelta(days=21 + random.randint(0, 30))), "ECHOUEE")
        _ia(a, _iso(ia_d), "REUSSIE")
        return a

    if arc == "primipare_lactating":
        velage_d = today_d - timedelta(days=random.randint(20, 300))
        ia_d = velage_d - timedelta(days=280)
        dob = velage_d - timedelta(days=random.randint(800, 1200))
        entry = dob + timedelta(days=random.randint(200, 400))
        if entry > today_d:
            return None
        a = _animal(suffix, _iso(dob), _iso(entry))
        if random.random() < 0.3:
            _ia(a, _iso(ia_d - timedelta(days=21 + random.randint(0, 30))), "ECHOUEE")
        _ia(a, _iso(ia_d), "REUSSIE")
        _velage(a, _iso(velage_d))
        return a

    if arc == "multipare_lactating":
        velage_2 = today_d - timedelta(days=random.randint(20, 300))
        ia_2 = velage_2 - timedelta(days=280)
        velage_1 = ia_2 - timedelta(days=random.randint(60, 90))
        ia_1 = velage_1 - timedelta(days=280)
        tariss = velage_2 - timedelta(days=random.randint(45, 80))
        dob = velage_1 - timedelta(days=random.randint(800, 1200))
        entry = dob + timedelta(days=random.randint(200, 400))
        if entry > today_d:
            return None
        a = _animal(suffix, _iso(dob), _iso(entry))
        _ia(a, _iso(ia_1), "REUSSIE")
        _velage(a, _iso(velage_1))
        _ia(a, _iso(ia_2), "REUSSIE")
        _tarissement(a, _iso(tariss))
        _velage(a, _iso(velage_2))
        return a

    if arc == "primipare_tarie_gestante":
        next_velage = today_d + timedelta(days=random.randint(20, 100))
        next_ia = next_velage - timedelta(days=280)
        if next_ia >= today_d:
            return _make_random_animal(suffix, today_d)  # retry
        velage_1 = next_ia - timedelta(days=random.randint(60, 90))
        ia_1 = velage_1 - timedelta(days=280)
        tariss = today_d - timedelta(days=random.randint(20, 80))
        dob = velage_1 - timedelta(days=random.randint(800, 1200))
        entry = dob + timedelta(days=random.randint(200, 400))
        if entry > today_d:
            return None
        a = _animal(suffix, _iso(dob), _iso(entry))
        _ia(a, _iso(ia_1), "REUSSIE")
        _velage(a, _iso(velage_1))
        _ia(a, _iso(next_ia), "REUSSIE")
        _tarissement(a, _iso(tariss))
        return a

    if arc == "multipare_tarie_gestante":
        next_velage = today_d + timedelta(days=random.randint(20, 100))
        next_ia = next_velage - timedelta(days=280)
        if next_ia >= today_d:
            return _make_random_animal(suffix, today_d)
        velage_2 = next_ia - timedelta(days=random.randint(60, 90))
        ia_2 = velage_2 - timedelta(days=280)
        velage_1 = ia_2 - timedelta(days=random.randint(60, 90))
        ia_1 = velage_1 - timedelta(days=280)
        tariss_1 = velage_2 - timedelta(days=random.randint(45, 80))
        tariss_2 = today_d - timedelta(days=random.randint(20, 60))
        dob = velage_1 - timedelta(days=random.randint(800, 1200))
        entry = dob + timedelta(days=random.randint(200, 400))
        if entry > today_d:
            return None
        a = _animal(suffix, _iso(dob), _iso(entry))
        _ia(a, _iso(ia_1), "REUSSIE")
        _velage(a, _iso(velage_1))
        _ia(a, _iso(ia_2), "REUSSIE")
        _tarissement(a, _iso(tariss_1))
        _velage(a, _iso(velage_2))
        _ia(a, _iso(next_ia), "REUSSIE")
        _tarissement(a, _iso(tariss_2))
        return a

    if arc == "with_avortement":
        velage_d = today_d - timedelta(days=random.randint(50, 250))
        good_ia = velage_d - timedelta(days=280)
        avo_d = good_ia - timedelta(days=random.randint(40, 90))
        bad_ia = avo_d - timedelta(days=random.randint(60, 150))
        dob = bad_ia - timedelta(days=random.randint(450, 800))
        entry = dob + timedelta(days=random.randint(180, 360))
        if entry > today_d:
            return None
        a = _animal(suffix, _iso(dob), _iso(entry))
        _ia(a, _iso(bad_ia), "REUSSIE")
        _avortement(a, _iso(avo_d))
        _ia(a, _iso(good_ia), "REUSSIE")
        _velage(a, _iso(velage_d))
        return a

    return None


@frappe.whitelist()
def seed(n=10):
    """ADDITIVE: add n random animals with realistic lifecycles, picking
    suffixes above the highest existing. Does not delete or modify existing data."""
    n = int(n)
    today_d = getdate(today())
    next_s = _next_suffix()
    created = []
    for i in range(n):
        suffix = next_s + i
        try:
            name = _make_random_animal(suffix, today_d)
            if name:
                created.append(name)
        except Exception:
            frappe.log_error(title=f"Seed: failed for suffix={suffix}",
                             message=frappe.get_traceback())
    frappe.db.commit()
    return {"created": created, "count": len(created), "from_suffix": next_s}


# ─── Deterministic baseline (legacy) ─────────────────────────────────────────

@frappe.whitelist()
def seed_baseline():
    """Deterministic 17-cow fixture for rule-coverage tests. Idempotent (cleans first)."""
    cleanup()

    # Animal 1 — VACHE EN_PRODUCTION GESTANTE (Lact 1 ongoing, 2nd IA succeeded)
    a1 = _animal(1, "2022-01-15", "2023-08-01")
    _ia(a1, "2023-12-01", "REUSSIE")
    _velage(a1, "2024-09-07")
    _ia(a1, "2025-02-01", "REUSSIE")

    # Animal 2 — VACHE TARIE GESTANTE
    a2 = _animal(2, "2022-03-01", "2023-09-01")
    _ia(a2, "2023-12-15", "REUSSIE")
    _velage(a2, "2024-09-21")
    _ia(a2, "2025-01-15", "REUSSIE")
    _tarissement(a2, "2025-09-15")

    # Animal 3 — VACHE EN_PRODUCTION VIDE (1 failed IA before success)
    a3 = _animal(3, "2022-06-01", "2023-12-01")
    _ia(a3, "2024-02-01", "ECHOUEE")
    _ia(a3, "2024-05-01", "REUSSIE")
    _velage(a3, "2025-02-04")

    # Animal 4 — VACHE EN_PRODUCTION VIDE (2 lactations, in Lact 2)
    a4 = _animal(4, "2021-09-01", "2023-03-01")
    _ia(a4, "2023-06-01", "REUSSIE")
    _velage(a4, "2024-03-08")
    _ia(a4, "2024-07-01", "REUSSIE")
    _tarissement(a4, "2025-01-08")
    _velage(a4, "2025-04-08")

    # Animal 5 — VACHE EN_PRODUCTION VIDE (1 avortement before success)
    a5 = _animal(5, "2022-09-01", "2024-02-01")
    _ia(a5, "2024-06-01", "REUSSIE")
    _avortement(a5, "2024-10-15")
    _ia(a5, "2025-01-15", "REUSSIE")
    _velage(a5, "2025-10-22")

    # Animal 6 — GENISSE GESTANTE
    a6 = _animal(6, "2023-04-01", "2024-09-01")
    _ia(a6, "2025-09-15", "REUSSIE")

    # ─── Suggestion-engine targeted cases (today = 2026-04-21) ─────────────────
    a7 = _animal(7, "2022-08-01", "2024-08-01")
    _ia(a7, "2025-05-16", "REUSSIE"); _velage(a7, "2026-02-20")

    a8 = _animal(8, "2022-01-01", "2023-08-01")
    _ia(a8, "2023-11-25", "REUSSIE"); _velage(a8, "2024-09-01")
    _ia(a8, "2025-04-26", "REUSSIE"); _tarissement(a8, "2026-01-15")
    _velage(a8, "2026-01-31")

    a9 = _animal(9, "2022-01-01", "2023-08-01")
    _ia(a9, "2023-12-25", "REUSSIE"); _velage(a9, "2024-10-01")
    _ia(a9, "2025-08-29", "REUSSIE")  # velage prévue ≈ 2026-06-05 → TARISSEMENT

    a10 = _animal(10, "2022-06-01", "2024-01-01")
    _ia(a10, "2024-08-29", "REUSSIE"); _velage(a10, "2025-06-05")

    # ─── Round 2: DIM bucket coverage + born-on-farm ─────────────────────────
    a11 = _animal(11, "2021-08-01", "2023-02-01")
    _ia(a11, "2023-12-01", "REUSSIE"); _velage(a11, "2024-09-07")
    _ia(a11, "2024-12-15", "REUSSIE"); _tarissement(a11, "2025-08-15")
    _velage(a11, "2025-11-23")

    a12 = _animal(12, "2021-05-01", "2022-11-01")
    _ia(a12, "2023-09-15", "REUSSIE"); _velage(a12, "2024-06-21")
    _ia(a12, "2024-10-15", "REUSSIE"); _tarissement(a12, "2025-05-30")
    _velage(a12, "2025-07-26")

    a13 = _animal(13, "2022-01-01", "2023-07-01")
    _ia(a13, "2024-01-15", "REUSSIE"); _velage(a13, "2024-10-22")
    _ia(a13, "2025-02-20", "REUSSIE"); _tarissement(a13, "2025-12-15")
    _velage(a13, "2026-04-12")

    a14 = _animal(14, "2023-06-01", "2024-09-01")
    _ia(a14, "2025-04-01", "REUSSIE"); _avortement(a14, "2025-09-15")
    _ia(a14, "2026-01-15", "REUSSIE")

    a15 = _animal(15, "2021-12-01", "2023-06-01")
    _ia(a15, "2024-09-15", "ECHOUEE"); _ia(a15, "2024-12-01", "ECHOUEE")
    _ia(a15, "2025-03-01", "ECHOUEE"); _ia(a15, "2025-06-01", "REUSSIE")
    _velage(a15, "2026-03-09")

    _animal_born(16, "2026-04-12", mother="9990000010", categorie="VELLE", sexe="F")
    _animal_born(17, "2025-11-15", mother="9990000040", categorie="VELLE", sexe="F")
    _animal_born(18, "2024-09-21", mother="9990000020", categorie="GENISSE", sexe="F")
    a19 = _animal_born(19, "2024-05-15", mother="9990000040", categorie="GENISSE", sexe="F")
    _ia(a19, "2026-01-15", "REUSSIE")
    a20 = _animal_born(20, "2021-04-01", mother="9990000040", categorie="GENISSE", sexe="F")
    _ia(a20, "2023-02-15", "REUSSIE"); _velage(a20, "2023-11-22")
    _ia(a20, "2024-03-15", "REUSSIE"); _tarissement(a20, "2024-09-30")
    _velage(a20, "2024-12-23")
    _ia(a20, "2025-04-01", "REUSSIE"); _tarissement(a20, "2025-08-15")
    _velage(a20, "2025-09-15")

    frappe.db.commit()
    return {"created": [a1, a2, a3, a4, a5, a6, a7, a8, a9, a10,
                        a11, a12, a13, a14, a15, a19, a20]}


# ─── Cleanup ─────────────────────────────────────────────────────────────────

@frappe.whitelist()
def cleanup():
    """Remove all seeded data (animals + their events + lactations + traites)."""
    seed_animals = frappe.db.sql_list(
        "SELECT name FROM `tabAnimal` WHERE identification_tn LIKE %s",
        (f"{PREFIX_TN}%",))
    if seed_animals:
        # Traite first to avoid orphan Traites pointing to deleted Lactations
        # after re-seed (Animal name is reused, but Lactation auto-names differ).
        for dt in ("Traite", "Velage", "Avortement", "Insemination", "Lactation"):
            frappe.db.sql(
                f"DELETE FROM `tab{dt}` WHERE animal IN %s", (seed_animals,))
        frappe.db.sql(
            "DELETE FROM `tabAnimal` WHERE name IN %s", (seed_animals,))
    frappe.db.commit()
    return {"deleted": len(seed_animals)}
