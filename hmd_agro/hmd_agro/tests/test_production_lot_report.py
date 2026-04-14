"""
Tests unitaires — Rapport Mensuel / Production par Lot
Run: bench execute hmd_agro.hmd_agro.tests.test_production_lot_report.run_all_tests
"""
import frappe
from frappe.utils import getdate

from hmd_agro.hmd_agro.report.rapport_mensuel.rapport_mensuel import _production_lot

PREFIX = "TEST-PLT-"
ANNEE, MOIS = 2099, 3
CTX = {"date_debut": getdate("2099-03-01"), "date_fin": getdate("2099-03-31"),
       "nb_jours": 31, "mois": MOIS, "annee": ANNEE, "jour": 0}


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

def _lot(name):
    if frappe.db.exists("Lot", name):
        return
    doc = frappe.get_doc({"doctype": "Lot", "nom": name, "actif": 1, "nb_animaux": 0})
    doc.db_insert()
    _created.append(("Lot", name))

def _animal(suffix, lot, etat_lactation="EN_PRODUCTION"):
    doc = frappe.get_doc({
        "doctype": "Animal", "identification_tn": f"{PREFIX}{suffix}",
        "nom_metier": f"{PREFIX}{suffix}", "categorie": "VACHE", "sexe": "F",
        "statut": "ACTIF", "etat_lactation": etat_lactation, "etat_gestation": "VIDE",
        "date_naissance": "2095-01-01", "date_entree": "2099-01-01", "id_lot": lot,
    })
    doc.name = f"{PREFIX}{suffix}"
    doc.db_insert()
    _created.append(("Animal", doc.name))
    return doc

def _traite(animal_name, date, litres):
    doc = frappe.get_doc({
        "doctype": "Traite", "animal": animal_name, "date_traite": date,
        "quantite_litres": litres, "type_traite": "MATIN",
    })
    doc.db_insert()
    _created.append(("Traite", doc.name))

def _cleanup():
    for dt, name in reversed(_created):
        frappe.db.sql(f"DELETE FROM `tab{dt}` WHERE name=%s", name)
    _created.clear()
    frappe.db.commit()

def _find_row(data, jour_val):
    return next((r for r in data if r.get("jour") == jour_val), None)


def _setup():
    # Clean stale
    frappe.db.sql("DELETE FROM `tabTraite` WHERE animal LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabAnimal` WHERE identification_tn LIKE %s", f"{PREFIX}%")
    frappe.db.commit()

    # 2 lots: HP (3 cows), MP (2 cows)
    _lot(f"{PREFIX}HP")
    _lot(f"{PREFIX}MP")

    hp1 = _animal("HP1", f"{PREFIX}HP")
    hp2 = _animal("HP2", f"{PREFIX}HP")
    hp3 = _animal("HP3", f"{PREFIX}HP")
    mp1 = _animal("MP1", f"{PREFIX}MP")
    mp2 = _animal("MP2", f"{PREFIX}MP")

    # Day 1: HP=30L (10+10+10), MP=15L (8+7)
    _traite(hp1.name, "2099-03-01", 10)
    _traite(hp2.name, "2099-03-01", 10)
    _traite(hp3.name, "2099-03-01", 10)
    _traite(mp1.name, "2099-03-01", 8)
    _traite(mp2.name, "2099-03-01", 7)

    # Day 2: HP=33L (11+11+11), MP=16L (9+7)
    _traite(hp1.name, "2099-03-02", 11)
    _traite(hp2.name, "2099-03-02", 11)
    _traite(hp3.name, "2099-03-02", 11)
    _traite(mp1.name, "2099-03-02", 9)
    _traite(mp2.name, "2099-03-02", 7)

    # Day 3: only HP=27L (9+9+9), MP has no data
    _traite(hp1.name, "2099-03-03", 9)
    _traite(hp2.name, "2099-03-03", 9)
    _traite(hp3.name, "2099-03-03", 9)

    frappe.db.commit()


# ─── Tests ───

def test_columns(results):
    log("Columns — dynamic per lot", "HEAD")
    cols, _ = _production_lot(CTX)
    col_names = [c["fieldname"] for c in cols]
    check("jour" in col_names, "Has jour", "Missing jour", results)
    check(f"{PREFIX}HP" in col_names, "Has HP lot", f"Cols: {col_names}", results)
    check(f"{PREFIX}MP" in col_names, "Has MP lot", f"Cols: {col_names}", results)
    check("total" in col_names, "Has total", "Missing total", results)
    check("moy_vl" in col_names, "Has moy_vl", "Missing moy_vl", results)

def test_day1(results):
    log("Day 1 — HP=30, MP=15, Total=45", "HEAD")
    _, data = _production_lot(CTX)
    row = _find_row(data, "1")
    check(row[f"{PREFIX}HP"] == 30, "HP=30", f"Got {row[f'{PREFIX}HP']}", results)
    check(row[f"{PREFIX}MP"] == 15, "MP=15", f"Got {row[f'{PREFIX}MP']}", results)
    check(row["total"] == 45, "Total=45", f"Got {row['total']}", results)
    check(row["moy_vl"] is not None, "Moy/VL calculated", f"Got {row['moy_vl']}", results)

def test_day2(results):
    log("Day 2 — HP=33, MP=16, Total=49", "HEAD")
    _, data = _production_lot(CTX)
    row = _find_row(data, "2")
    check(row[f"{PREFIX}HP"] == 33, "HP=33", f"Got {row[f'{PREFIX}HP']}", results)
    check(row[f"{PREFIX}MP"] == 16, "MP=16", f"Got {row[f'{PREFIX}MP']}", results)
    check(row["total"] == 49, "Total=49", f"Got {row['total']}", results)

def test_day3_partial(results):
    log("Day 3 — HP=27, MP=None (no data)", "HEAD")
    _, data = _production_lot(CTX)
    row = _find_row(data, "3")
    check(row[f"{PREFIX}HP"] == 27, "HP=27", f"Got {row[f'{PREFIX}HP']}", results)
    check(row[f"{PREFIX}MP"] is None, "MP=None", f"Got {row[f'{PREFIX}MP']}", results)
    check(row["total"] == 27, "Total=27", f"Got {row['total']}", results)

def test_empty_day(results):
    log("Day 4 — no data, all None", "HEAD")
    _, data = _production_lot(CTX)
    row = _find_row(data, "4")
    check(row[f"{PREFIX}HP"] is None, "HP=None", f"Got {row[f'{PREFIX}HP']}", results)
    check(row["total"] is None, "Total=None", f"Got {row['total']}", results)

def test_effectif_row(results):
    log("Effectif row — HP=3, MP=2, Total=5", "HEAD")
    _, data = _production_lot(CTX)
    row = _find_row(data, "Effectif")
    check(row[f"{PREFIX}HP"] == 3, "HP=3", f"Got {row[f'{PREFIX}HP']}", results)
    check(row[f"{PREFIX}MP"] == 2, "MP=2", f"Got {row[f'{PREFIX}MP']}", results)
    check(row["total"] >= 5, "Total>=5 (includes real data)", f"Got {row['total']}", results)

def test_moyenne_row(results):
    log("Moyenne row — per cow per day", "HEAD")
    _, data = _production_lot(CTX)
    row = _find_row(data, "Moyenne/lot")
    # HP: (30+33+27)/(3 cows * 3 days) = 90/9 = 10.0
    check(row[f"{PREFIX}HP"] == 10.0, "HP moy=10.0", f"Got {row[f'{PREFIX}HP']}", results)
    # MP: (15+16)/(2 cows * 3 days) = 31/6 = 5.2
    check(row[f"{PREFIX}MP"] == 5.2, "MP moy=5.2", f"Got {row[f'{PREFIX}MP']}", results)

def test_row_count(results):
    log("31 day rows + effectif + moyenne = 33", "HEAD")
    _, data = _production_lot(CTX)
    check(len(data) == 33, "33 rows", f"Got {len(data)}", results)


# ─── Runner ───

def run_all_tests():
    print("\n" + "=" * 60)
    print("  RAPPORT MENSUEL / PRODUCTION PAR LOT — TESTS")
    print("=" * 60)

    results = {"pass": 0, "fail": 0}
    try:
        _setup()
        test_columns(results)
        test_day1(results)
        test_day2(results)
        test_day3_partial(results)
        test_empty_day(results)
        test_effectif_row(results)
        test_moyenne_row(results)
        test_row_count(results)
    finally:
        _cleanup()

    total = results["pass"] + results["fail"]
    print(f"\n  RESULTATS: {results['pass']}/{total} passés, {results['fail']} échoués\n")
    return results
