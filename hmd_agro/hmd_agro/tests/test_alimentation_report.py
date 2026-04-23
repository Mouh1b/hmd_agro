"""
Tests unitaires — Rapport Mensuel / Alimentation (Ration)

Convention: ms_pct stored as fraction (0.86 = 86%); the report multiplies by 100
for display. Ration composition is immutable — to change a ration, create a new
Ration. Mid-month switches are tracked via Lot Ration History.

Run: bench execute hmd_agro.hmd_agro.tests.test_alimentation_report.run_all_tests
"""
import frappe
from frappe.utils import getdate

from hmd_agro.hmd_agro.report.rapport_mensuel.rapport_mensuel import _alimentation

PREFIX = "TEST-ALI-"
CTX = {"date_debut": getdate("2099-03-01"), "date_fin": getdate("2099-03-31"),
       "nb_jours": 31, "mois": 3, "annee": 2099, "jour": 1}


def log(msg, level="INFO"):
    prefix = {"PASS": "  OK", "FAIL": "FAIL", "HEAD": "----"}.get(level, "    ")
    print(f"  {prefix}  {msg}")

def check(condition, pass_msg, fail_msg, results):
    if condition:
        log(pass_msg, "PASS")
        results["pass"] += 1
    else:
        log(fail_msg, "FAIL")
        results["fail"] += 1


_created = []

def _aliment(suffix, nom, ms_pct=0.85, prix=1.0, type_aliment="CONCENTRE"):
    name = f"{PREFIX}{suffix}"
    doc = frappe.get_doc({
        "doctype": "Aliment", "nom_aliment": name, "type_aliment": type_aliment,
        "unite": "KG", "prix_unitaire": prix, "ms_pct": ms_pct,
    })
    doc.name = name
    doc.db_insert()
    _created.append(("Aliment", name))
    return name

def _ration(suffix, composition):
    name = f"{PREFIX}{suffix}"
    doc = frappe.get_doc({
        "doctype": "Ration", "nom_ration": name, "active": 1,
    })
    doc.name = name
    doc.db_insert()
    _created.append(("Ration", name))
    for idx, (aliment_name, qty) in enumerate(composition, 1):
        child = frappe.get_doc({
            "doctype": "Composition Ration", "parent": name, "parenttype": "Ration",
            "parentfield": "composition", "idx": idx,
            "aliment": aliment_name, "quantite": qty, "unite": "KG",
        })
        child.db_insert()
        _created.append(("Composition Ration", child.name))
    return name

def _lot(suffix, ration, nb_animaux):
    name = f"{PREFIX}{suffix}"
    doc = frappe.get_doc({
        "doctype": "Lot", "nom": name, "actif": 1,
        "id_ration_actuelle": ration, "nb_animaux": nb_animaux,
    })
    doc.name = name
    doc.db_insert()
    _created.append(("Lot", name))
    return name

def _animal(suffix, lot, date_naissance="2095-01-01"):
    doc = frappe.get_doc({
        "doctype": "Animal", "identification_tn": f"{PREFIX}{suffix}",
        "nom_metier": f"{PREFIX}{suffix}", "categorie": "VACHE", "sexe": "F",
        "statut": "ACTIF", "etat_lactation": "EN_PRODUCTION", "etat_gestation": "VIDE",
        "date_naissance": date_naissance, "date_entree": "2099-01-01", "id_lot": lot,
    })
    doc.name = f"{PREFIX}{suffix}"
    doc.db_insert()
    _created.append(("Animal", doc.name))
    return doc

def _traite(animal_name, date, litres, lot):
    doc = frappe.get_doc({
        "doctype": "Traite", "animal": animal_name, "date_traite": date,
        "quantite_litres": litres, "type_traite": "MATIN", "id_lot": lot,
    })
    doc.db_insert()
    _created.append(("Traite", doc.name))

def _allotement_history(animal, from_lot, to_lot, creation_dt):
    """Insert an Allotement History row with a backdated `creation` so the
    population helper sees a mid-month move."""
    doc = frappe.get_doc({
        "doctype": "Allotement History",
        "animal": animal, "from_lot": from_lot, "to_lot": to_lot,
        "moved_by": "Administrator", "source": "MANUAL",
        "reason": "Test fixture",
    }).insert(ignore_permissions=True)
    frappe.db.sql("UPDATE `tabAllotement History` SET creation=%s, modified=%s WHERE name=%s",
                  (creation_dt, creation_dt, doc.name))
    _created.append(("Allotement History", doc.name))
    return doc.name

def _ration_history(lot, from_ration, to_ration, creation_dt):
    """Insert a Lot Ration History row with a backdated `creation` so the
    ration helper sees a mid-month switch."""
    doc = frappe.get_doc({
        "doctype": "Lot Ration History",
        "lot": lot, "from_ration": from_ration, "to_ration": to_ration,
        "changed_by": "Administrator", "source": "MANUAL",
    }).insert(ignore_permissions=True)
    frappe.db.sql("UPDATE `tabLot Ration History` SET creation=%s, modified=%s WHERE name=%s",
                  (creation_dt, creation_dt, doc.name))
    _created.append(("Lot Ration History", doc.name))
    return doc.name

def _cleanup():
    for dt, name in reversed(_created):
        frappe.db.sql(f"DELETE FROM `tab{dt}` WHERE name=%s", name)
    _created.clear()
    frappe.db.commit()

def _find_row(data, label):
    return next((r for r in data if r.get("aliment") == label), None)


# ─── Setup A: baseline (constant population, single ration per lot) ─────────

def _setup_baseline():
    frappe.db.sql("DELETE FROM `tabAliment` WHERE name LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabRation` WHERE name LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabComposition Ration` WHERE parent LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabLot` WHERE name LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabAnimal` WHERE identification_tn LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabTraite` WHERE animal LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabAllotement History` WHERE animal LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabLot Ration History` WHERE lot LIKE %s", f"{PREFIX}%")
    frappe.db.commit()

    soja = _aliment("SOJA", "Soja", ms_pct=0.90, prix=1.4)
    mais = _aliment("MAIS", "Mais", ms_pct=0.88, prix=1.0)
    ration_hp = _ration("RATION-HP", [(soja, 2), (mais, 5)])
    ration_mp = _ration("RATION-MP", [(soja, 1), (mais, 3)])
    lot_hp = _lot("HP", ration_hp, 3)
    lot_mp = _lot("MP", ration_mp, 2)

    hp1 = _animal("HP1", lot_hp); hp2 = _animal("HP2", lot_hp); hp3 = _animal("HP3", lot_hp)
    mp1 = _animal("MP1", lot_mp); mp2 = _animal("MP2", lot_mp)

    # 31 days × 10L per HP cow, 5L per MP cow
    for day in range(1, 32):
        date_str = f"2099-03-{day:02d}"
        for a in (hp1, hp2, hp3): _traite(a.name, date_str, 10, lot_hp)
        for a in (mp1, mp2):     _traite(a.name, date_str, 5,  lot_mp)
    frappe.db.commit()


# ─── Tests against baseline ─────────────────────────────────────────────────

def test_columns(results):
    log("Columns — Aliment + MS% + lots", "HEAD")
    cols, _ = _alimentation(CTX)
    col_names = [c["fieldname"] for c in cols]
    check("aliment" in col_names, "Has aliment", "Missing aliment", results)
    check("ms_pct" in col_names, "Has ms_pct", "Missing ms_pct", results)
    check(f"{PREFIX}HP" in col_names, "Has HP lot", f"Cols: {col_names}", results)
    check(f"{PREFIX}MP" in col_names, "Has MP lot", f"Cols: {col_names}", results)

def test_aliment_monthly_totals(results):
    log("Monthly totals — HP: Soja=186, Mais=465; MP: Soja=62, Mais=186 (×31 days)", "HEAD")
    _, data = _alimentation(CTX)
    soja = _find_row(data, f"{PREFIX}SOJA")
    mais = _find_row(data, f"{PREFIX}MAIS")
    # HP: 3 cows × 2kg Soja × 31 days = 186; 3 × 5 × 31 = 465
    check(soja[f"{PREFIX}HP"] == 186, "HP Soja = 186kg/mois", f"Got {soja[f'{PREFIX}HP']}", results)
    check(mais[f"{PREFIX}HP"] == 465, "HP Mais = 465kg/mois", f"Got {mais[f'{PREFIX}HP']}", results)
    # MP: 2 × 1 × 31 = 62; 2 × 3 × 31 = 186
    check(soja[f"{PREFIX}MP"] == 62, "MP Soja = 62kg/mois", f"Got {soja[f'{PREFIX}MP']}", results)
    check(mais[f"{PREFIX}MP"] == 186, "MP Mais = 186kg/mois", f"Got {mais[f'{PREFIX}MP']}", results)

def test_ms_pct(results):
    log("MS% — Soja=90, Mais=88 (fraction × 100 for display)", "HEAD")
    _, data = _alimentation(CTX)
    soja = _find_row(data, f"{PREFIX}SOJA")
    mais = _find_row(data, f"{PREFIX}MAIS")
    check(soja["ms_pct"] == 90.0, "Soja MS% = 90", f"Got {soja['ms_pct']}", results)
    check(mais["ms_pct"] == 88.0, "Mais MS% = 88", f"Got {mais['ms_pct']}", results)

def test_ms_total(results):
    log("MS Total Distribué (kg/mois)", "HEAD")
    _, data = _alimentation(CTX)
    row = _find_row(data, "MS Total Distribué")
    # HP: (186 × 0.9) + (465 × 0.88) = 167.4 + 409.2 = 576.6
    check(row[f"{PREFIX}HP"] == 576.6, "HP MS Total = 576.6", f"Got {row[f'{PREFIX}HP']}", results)
    # MP: (62 × 0.9) + (186 × 0.88) = 55.8 + 163.68 = 219.48
    check(row[f"{PREFIX}MP"] == 219.48, "MP MS Total = 219.48", f"Got {row[f'{PREFIX}MP']}", results)

def test_ms_tete(results):
    log("MS Distribué/Tête (kg per cow-day) — HP: 6.2, MP: 3.54", "HEAD")
    _, data = _alimentation(CTX)
    row = _find_row(data, "MS Distribué/Tête")
    # HP: 576.6 / (3 × 31) = 6.2
    check(row[f"{PREFIX}HP"] == 6.2, "HP MS/cow-day = 6.2", f"Got {row[f'{PREFIX}HP']}", results)
    # MP: 219.48 / (2 × 31) = 3.54
    check(row[f"{PREFIX}MP"] == 3.54, "MP MS/cow-day = 3.54", f"Got {row[f'{PREFIX}MP']}", results)

def test_efficacite(results):
    log("Efficacité — monthly milk / monthly MS", "HEAD")
    _, data = _alimentation(CTX)
    row = _find_row(data, "Efficacité alimentaire L/Kg MS")
    # HP: milk = 3 × 10 × 31 = 930 L; MS = 576.6; eff = 930/576.6 = 1.61
    check(row[f"{PREFIX}HP"] == 1.61, "HP eff = 1.61", f"Got {row[f'{PREFIX}HP']}", results)
    # MP: milk = 2 × 5 × 31 = 310 L; MS = 219.48; eff = 310/219.48 = 1.41
    check(row[f"{PREFIX}MP"] == 1.41, "MP eff = 1.41", f"Got {row[f'{PREFIX}MP']}", results)


# ─── Setup B: population grows mid-month (day 15) ──────────────────────────

def _setup_population_change():
    _setup_baseline()
    # Add 2 more HP cows that "join" lot HP on day 15 via Allotement History.
    # They start in lot MP so they don't count as HP for days 1-14.
    extra1 = _animal("HP-EXTRA1", f"{PREFIX}MP")
    extra2 = _animal("HP-EXTRA2", f"{PREFIX}MP")
    _allotement_history(extra1.name, f"{PREFIX}MP", f"{PREFIX}HP", "2099-03-15 12:00:00")
    _allotement_history(extra2.name, f"{PREFIX}MP", f"{PREFIX}HP", "2099-03-15 12:00:00")
    frappe.db.commit()

def test_population_change_midmonth(results):
    log("Mid-month pop change — HP: 3 cows days 1-14, 5 cows days 15-31", "HEAD")
    _, data = _alimentation(CTX)
    mais = _find_row(data, f"{PREFIX}MAIS")
    # HP Mais: 5kg × (3 cows × 14 days + 5 cows × 17 days) = 5 × (42 + 85) = 5 × 127 = 635
    check(mais[f"{PREFIX}HP"] == 635, "HP Mais = 635kg/mois (pop-weighted)",
          f"Got {mais[f'{PREFIX}HP']}", results)
    # MP loses the 2 extras after day 14 — they were in MP days 1-14 only.
    # MP Mais: 3kg × (2 base + 2 extras) × 14 + 3kg × 2 × 17 = 168 + 102 = 270
    check(mais[f"{PREFIX}MP"] == 270, "MP Mais = 270kg/mois",
          f"Got {mais[f'{PREFIX}MP']}", results)


# ─── Setup C: lot switches ration mid-month (day 15) ───────────────────────

def _setup_ration_switch():
    _setup_baseline()
    # Create a 3rd ration and switch HP from RATION-HP to RATION-NEW on day 15.
    soja = f"{PREFIX}SOJA"; mais = f"{PREFIX}MAIS"
    ration_new = _ration("RATION-NEW", [(soja, 4), (mais, 8)])  # heavier than RATION-HP
    _ration_history(f"{PREFIX}HP", f"{PREFIX}RATION-HP", ration_new, "2099-03-15 12:00:00")
    frappe.db.commit()

def test_ration_switch_midmonth(results):
    log("Mid-month ration switch — HP: RATION-HP days 1-14, RATION-NEW days 15-31", "HEAD")
    _, data = _alimentation(CTX)
    soja = _find_row(data, f"{PREFIX}SOJA")
    mais = _find_row(data, f"{PREFIX}MAIS")
    # HP Soja: 2kg × 3 × 14 (RATION-HP) + 4kg × 3 × 17 (RATION-NEW) = 84 + 204 = 288
    check(soja[f"{PREFIX}HP"] == 288, "HP Soja = 288kg/mois",
          f"Got {soja[f'{PREFIX}HP']}", results)
    # HP Mais: 5kg × 3 × 14 + 8kg × 3 × 17 = 210 + 408 = 618
    check(mais[f"{PREFIX}HP"] == 618, "HP Mais = 618kg/mois",
          f"Got {mais[f'{PREFIX}HP']}", results)


# ─── Runner ───

def run_all_tests():
    print("\n" + "=" * 60)
    print("  RAPPORT MENSUEL / ALIMENTATION — TESTS")
    print("=" * 60)
    results = {"pass": 0, "fail": 0}

    print("\n  [Setup A: baseline]")
    try:
        _setup_baseline()
        test_columns(results)
        test_aliment_monthly_totals(results)
        test_ms_pct(results)
        test_ms_total(results)
        test_ms_tete(results)
        test_efficacite(results)
    finally:
        _cleanup()

    print("\n  [Setup B: mid-month population change]")
    try:
        _setup_population_change()
        test_population_change_midmonth(results)
    finally:
        _cleanup()

    print("\n  [Setup C: mid-month ration switch]")
    try:
        _setup_ration_switch()
        test_ration_switch_midmonth(results)
    finally:
        _cleanup()

    total = results["pass"] + results["fail"]
    print(f"\n  RESULTATS: {results['pass']}/{total} passés, {results['fail']} échoués\n")
    return results
