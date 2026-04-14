"""
Tests unitaires — Rapport Mensuel / Effectif
Run: bench execute hmd_agro.hmd_agro.tests.test_effectif_report.run_all_tests
"""
import frappe
import json
from frappe.utils import getdate

from hmd_agro.hmd_agro.report.rapport_mensuel.rapport_mensuel import (
    _effectif, _read_snapshot, _count_naissances, _count_achats,
    _count_velages, _parse_version_logs, _sum_prix_vente, _empty_row,
)

PREFIX = "TEST-EFF-"
MOIS1, MOIS2 = 1, 2
ANNEE = 2099

CTX_M1 = {"date_debut": getdate("2099-01-01"), "date_fin": getdate("2099-01-31"),
           "nb_jours": 31, "mois": MOIS1, "annee": ANNEE, "jour": 0}
CTX_M2 = {"date_debut": getdate("2099-02-01"), "date_fin": getdate("2099-02-28"),
           "nb_jours": 28, "mois": MOIS2, "annee": ANNEE, "jour": 0}


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


# ─── Data helpers ───

_created = []

def _animal(suffix, categorie, sexe, statut="ACTIF", etat_lactation="", etat_gestation="VIDE",
            est_achat=0, date_entree="2099-01-15", prix_vente=0, date_sortie=None):
    doc = frappe.get_doc({
        "doctype": "Animal", "identification_tn": f"{PREFIX}{suffix}",
        "nom_metier": f"{PREFIX}{suffix}", "categorie": categorie, "sexe": sexe,
        "statut": statut, "etat_lactation": etat_lactation, "etat_gestation": etat_gestation,
        "date_naissance": "2095-01-01", "date_entree": date_entree,
        "est_achat": est_achat, "prix_vente": prix_vente, "date_sortie": date_sortie,
    })
    doc.name = f"{PREFIX}{suffix}"
    doc.db_insert()
    _created.append(("Animal", doc.name))
    return doc

def _velage(animal_name, date, sexe1, vivant1=1, nombre=1, sexe2=None, vivant2=0):
    doc = frappe.get_doc({
        "doctype": "Velage", "animal": animal_name, "date_velage": date,
        "type_velage": "FACILE", "nombre_veaux": str(nombre),
        "sexe_veau1": sexe1, "vivant_veau1": vivant1,
        "sexe_veau2": sexe2, "vivant_veau2": vivant2,
    })
    doc.db_insert()
    _created.append(("Velage", doc.name))

def _avortement(animal_name, date):
    doc = frappe.get_doc({"doctype": "Avortement", "animal": animal_name,
                          "date_avortement": date, "cause": "AUTRE"})
    doc.db_insert()
    _created.append(("Avortement", doc.name))

def _snapshot(date_str, data_dict):
    d = getdate(date_str)
    doc = frappe.get_doc({"doctype": "Snapshot Mensuel", "annee": d.year, "mois": d.month,
                          "date_snapshot": date_str, "data": json.dumps(data_dict)})
    doc.name = f"SNAP-{date_str}"
    doc.db_insert()
    _created.append(("Snapshot Mensuel", doc.name))

def _fake_version(docname, date, changes):
    doc = frappe.get_doc({"doctype": "Version", "ref_doctype": "Animal",
                          "docname": docname, "data": json.dumps({"changed": changes})})
    doc.db_insert()
    frappe.db.set_value("Version", doc.name, "creation", date, update_modified=False)
    _created.append(("Version", doc.name))

def _cleanup():
    for dt, name in reversed(_created):
        frappe.db.sql(f"DELETE FROM `tab{dt}` WHERE name=%s", name)
    _created.clear()
    frappe.db.commit()

def _find_row(data, label):
    return next((r for r in data if r.get("ligne") == label), None)


# ─── Setup ───

def _setup():
    # Clean stale data from previous failed run
    frappe.db.sql("DELETE FROM `tabAnimal` WHERE identification_tn LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabVelage` WHERE animal LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabAvortement` WHERE animal LIKE %s", f"{PREFIX}%")
    frappe.db.sql("DELETE FROM `tabSnapshot Mensuel` WHERE date_snapshot LIKE %s", f"{ANNEE}%")
    frappe.db.sql("DELETE FROM `tabVersion` WHERE ref_doctype='Animal' AND docname LIKE %s", f"{PREFIX}%")
    frappe.db.commit()

    # M1 snapshot (Jan 1): 5 lact, 2 taries, 3 gen vides, 1 gen pleine, 2 veaux, 1 taurillon, 2 velles = 16
    _snapshot("2099-01-01", {
        "vaches_lactantes": 5, "vaches_taries": 2, "genisses_vides": 3,
        "genisses_pleines": 1, "veaux": 2, "engraissement": 1, "velles": 2, "total": 16,
    })

    # M1 events: 2 velages (1 lact + 1 tarie), 1 achat genisse, 1 vente vache 800DT, 1 mort veau
    v1 = _animal("V1", "VACHE", "F", etat_lactation="EN_PRODUCTION")
    _velage(v1.name, "2099-01-10", "M")
    v1t = _animal("V1T", "VACHE", "F", etat_lactation="TARIE")
    _velage(v1t.name, "2099-01-12", "F")
    _animal("G1-ACHAT", "GENISSE", "F", est_achat=1, date_entree="2099-01-20")
    v_sold = _animal("V-SOLD", "VACHE", "F", statut="VENDU", etat_lactation="EN_PRODUCTION",
                     prix_vente=800, date_sortie="2099-01-25")
    v_dead = _animal("VEAU-DEAD", "VEAU", "M", statut="MORT", date_sortie="2099-01-28")
    _fake_version(v_sold.name, "2099-01-25", [["statut", "ACTIF", "VENDU"]])
    _fake_version(v_dead.name, "2099-01-28", [["statut", "ACTIF", "MORT"]])

    # M2 snapshot (Feb 1)
    _snapshot("2099-02-01", {
        "vaches_lactantes": 4, "vaches_taries": 2, "genisses_vides": 4,
        "genisses_pleines": 1, "veaux": 2, "engraissement": 1, "velles": 2, "total": 16,
    })

    # M2 events: 1 velage jumeaux M+F, 1 avortement, 1 réforme tarie 500DT
    v2 = _animal("V2", "VACHE", "F", etat_lactation="EN_PRODUCTION")
    _velage(v2.name, "2099-02-05", "M", nombre=2, sexe2="F", vivant2=1)
    _animal("V3-AVORT", "VACHE", "F", etat_lactation="EN_PRODUCTION")
    _avortement("TEST-EFF-V3-AVORT", "2099-02-15")
    v_ref = _animal("V-REF", "VACHE", "F", statut="REFORME", etat_lactation="TARIE",
                    prix_vente=500, date_sortie="2099-02-20")
    _fake_version(v_ref.name, "2099-02-20", [["statut", "ACTIF", "REFORME"]])
    frappe.db.commit()


# ─── Tests ───

def test_snapshot_read(results):
    log("Snapshot — reads stored data", "HEAD")
    r = _read_snapshot(getdate(f"{ANNEE}-{MOIS1:02d}-01"))
    check(r["Vaches - Lact."] == 5, "Vaches Lact = 5", f"Got {r['Vaches - Lact.']}", results)
    check(r["Vaches - Tarie"] == 2, "Vaches Tarie = 2", f"Got {r['Vaches - Tarie']}", results)
    check(r["Total"] == 16, "Total = 16", f"Got {r['Total']}", results)
    check(_read_snapshot(getdate("2098-12-31")) is None, "Missing date = None", "Should be None", results)

def test_velages_m1(results):
    log("M1 — velages (1 lact + 1 tarie)", "HEAD")
    r = _count_velages(CTX_M1["date_debut"], CTX_M1["date_fin"])
    check(r["Vaches - Lact."] == 1, "1 velage lactante", f"Got {r['Vaches - Lact.']}", results)
    check(r["Vaches - Tarie"] == 1, "1 velage tarie", f"Got {r['Vaches - Tarie']}", results)
    check(r["Total"] == 2, "Total = 2", f"Got {r['Total']}", results)

def test_naissances_m1(results):
    log("M1 — naissances (1 M + 1 F vivants)", "HEAD")
    n, m = _count_naissances(CTX_M1["date_debut"], CTX_M1["date_fin"])
    check(n["Veaux"] == 1, "1 veau", f"Got {n['Veaux']}", results)
    check(n["Velles"] == 1, "1 velle", f"Got {n['Velles']}", results)
    check(m["Total"] == 0, "0 mort-nés", f"Got {m['Total']}", results)

def test_naissances_m2(results):
    log("M2 — jumeaux (M + F vivants)", "HEAD")
    n, _ = _count_naissances(CTX_M2["date_debut"], CTX_M2["date_fin"])
    check(n["Total"] == 2, "Total = 2", f"Got {n['Total']}", results)

def test_achats_m1(results):
    log("M1 — 1 achat génisse", "HEAD")
    r = _count_achats(CTX_M1["date_debut"], CTX_M1["date_fin"])
    check(r["Gén. - Vide"] == 1, "1 génisse", f"Got {r['Gén. - Vide']}", results)

def test_sorties_m1(results):
    log("M1 — 1 vente + 1 mort", "HEAD")
    _, _, mort, ventes, ref = _parse_version_logs(CTX_M1["date_debut"], CTX_M1["date_fin"])
    check(ventes["Vaches - Lact."] == 1, "1 vache vendue", f"Got {ventes['Vaches - Lact.']}", results)
    check(mort["Veaux"] == 1, "1 veau mort", f"Got {mort['Veaux']}", results)
    check(ref["Total"] == 0, "0 réformes", f"Got {ref['Total']}", results)

def test_sorties_m2(results):
    log("M2 — 1 réforme tarie", "HEAD")
    _, _, _, _, ref = _parse_version_logs(CTX_M2["date_debut"], CTX_M2["date_fin"])
    check(ref["Vaches - Tarie"] == 1, "1 réforme tarie", f"Got {ref['Vaches - Tarie']}", results)

def test_prix_vente(results):
    log("Prix vente — M1: 800 DT lact, M2: 500 DT tarie", "HEAD")
    r1 = _sum_prix_vente(CTX_M1["date_debut"], CTX_M1["date_fin"])
    check(r1["Vaches - Lact."] == 800, "M1: 800 DT", f"Got {r1['Vaches - Lact.']}", results)
    r2 = _sum_prix_vente(CTX_M2["date_debut"], CTX_M2["date_fin"])
    check(r2["Vaches - Tarie"] == 500, "M2: 500 DT", f"Got {r2['Vaches - Tarie']}", results)

def test_effectif_m1(results):
    log("M1 — effectif complet", "HEAD")
    cols, data = _effectif(CTX_M1)
    check(len(cols) == 9 and len(data) == 11, "9 cols, 11 rows", f"Got {len(cols)} cols, {len(data)} rows", results)

    init = _find_row(data, "Effectif Initial")
    check(init["Total"] == 16, "Init = 16", f"Got {init['Total']}", results)

    vel = _find_row(data, "Vêlage")
    check(vel["Vaches - Lact."] == 1 and vel["Vaches - Tarie"] == 1, "Velage 1+1", f"Got L:{vel['Vaches - Lact.']} T:{vel['Vaches - Tarie']}", results)

    naiss = _find_row(data, "Naissance")
    check(naiss["Veaux"] == 1 and naiss["Velles"] == 1, "Naiss 1+1", f"Got V:{naiss['Veaux']} F:{naiss['Velles']}", results)

    check(_find_row(data, "Vente (Quantité)")["Vaches - Lact."] == 1, "Vente = 1", "Vente wrong", results)
    check(_find_row(data, "Mortalité")["Veaux"] == 1, "Mort = 1", "Mort wrong", results)
    check(_find_row(data, "Effectif Final")["Total"] >= 0, "Final >= 0", "Final negative", results)

def test_effectif_m2(results):
    log("M2 — effectif complet", "HEAD")
    _, data = _effectif(CTX_M2)

    check(_find_row(data, "Effectif Initial")["Total"] == 16, "Init = 16", f"Got {_find_row(data, 'Effectif Initial')['Total']}", results)
    check(_find_row(data, "Naissance")["Total"] == 2, "Naiss = 2 (jumeaux)", f"Got {_find_row(data, 'Naissance')['Total']}", results)
    check(_find_row(data, "Réforme")["Vaches - Tarie"] == 1, "Réforme tarie = 1", f"Got {_find_row(data, 'Réforme')['Vaches - Tarie']}", results)
    check(_find_row(data, "Vente (Prix DT)")["Vaches - Tarie"] == 500, "Prix = 500", f"Got {_find_row(data, 'Vente (Prix DT)')['Vaches - Tarie']}", results)


# ─── Runner ───

def run_all_tests():
    print("\n" + "=" * 60)
    print("  RAPPORT MENSUEL / EFFECTIF — TESTS")
    print("=" * 60)

    results = {"pass": 0, "fail": 0}
    try:
        _setup()
        test_snapshot_read(results)
        test_velages_m1(results)
        test_naissances_m1(results)
        test_naissances_m2(results)
        test_achats_m1(results)
        test_sorties_m1(results)
        test_sorties_m2(results)
        test_prix_vente(results)
        test_effectif_m1(results)
        test_effectif_m2(results)
    finally:
        _cleanup()

    total = results["pass"] + results["fail"]
    print(f"\n  RESULTATS: {results['pass']}/{total} passés, {results['fail']} échoués\n")
    return results
