"""Inventory of cows + DIM-suggested lot + predicted dialog behavior.
Helps plan manual moves to cover all consideration scenarios."""
import frappe
from frappe.utils import add_days, getdate, today


LOT_RANK = {"FV": 1, "THP": 2, "HP": 3, "MP": 4, "FP": 5,
            "TARISSEMENT": 6, "TARIE": 7}
LOT_DIM_RANGE_MULTI = {"FV": (0, 30), "THP": (30, 120), "HP": (120, 240),
                       "MP": (240, 305), "FP": (305, 9999)}
LOT_DIM_RANGE_PRIMI = {"FV": (0, 300), "FP": (300, 9999)}


def dim_target(dim, n):
    if dim is None: return None
    if n == 1: return "FV" if dim <= 300 else "FP"
    if dim <= 30: return "FV"
    if dim <= 120: return "THP"
    if dim <= 240: return "HP"
    if dim <= 305: return "MP"
    return "FP"


def predict(cur_type, target, dim, moy, seuil_cur, seuil_tgt, num_lact):
    """Return (visible, color, reason)."""
    if not target:
        return (False, "", "no DIM target (DIM=None)")
    dim_moves = (target != cur_type)
    if dim_moves:
        cur_rank = LOT_RANK.get(cur_type, 0)
        tgt_rank = LOT_RANK.get(target, 0)
        if moy and seuil_cur and tgt_rank > cur_rank and moy >= seuil_cur:
            return (True, "RED", f"démote→{target} mais prod {moy}≥{seuil_cur} → garder en {cur_type}")
        if moy and seuil_tgt and tgt_rank < cur_rank and moy < seuil_tgt:
            return (False, "SUPPRESSED", f"promote→{target} mais prod {moy}<{seuil_tgt} → masqué")
        return (True, "WHITE", f"DIM seul: {cur_type}→{target}")
    # No DIM mismatch — check yellow
    if not seuil_cur or not moy:
        return (False, "", "DIM ok + pas de signal prod")
    rng = (LOT_DIM_RANGE_PRIMI if num_lact == 1 else LOT_DIM_RANGE_MULTI).get(cur_type)
    if rng and moy < seuil_cur:
        lo, hi = rng
        if dim >= lo + (2/3)*(hi - lo):
            return (True, "YELLOW", f"prod {moy}<{seuil_cur} + DIM {dim} en fin de stage {cur_type}")
    return (False, "", "DIM ok + prod ok ou pas en fin de stage")


def run():
    ref = getdate(add_days(today(), -1))
    j_1, j_2 = add_days(ref, -1), add_days(ref, -2)

    rows = frappe.db.sql("""
        SELECT a.name AS animal, a.nom_metier, a.id_lot AS lot,
               a.etat_gestation, a.date_velage_prevue,
               l.numero_lactation, l.date_debut,
               SUM(CASE WHEN t.date_traite=%(j2)s THEN t.quantite_litres ELSE 0 END) AS j_2,
               SUM(CASE WHEN t.date_traite=%(j1)s THEN t.quantite_litres ELSE 0 END) AS j_1,
               SUM(CASE WHEN t.date_traite=%(j)s  THEN t.quantite_litres ELSE 0 END) AS j
        FROM `tabAnimal` a
        INNER JOIN `tabLactation` l ON l.animal = a.name AND l.statut = 'EN_COURS'
        LEFT JOIN `tabTraite` t ON t.animal = a.name AND t.date_traite BETWEEN %(j2)s AND %(j)s
        WHERE a.statut = 'ACTIF' AND a.categorie = 'VACHE'
        GROUP BY a.name
    """, {"j": ref, "j1": j_1, "j2": j_2}, as_dict=True)

    seuils = {l.name: float(l.seuil_production_3j or 0)
              for l in frappe.get_all("Lot",
                  fields=["name", "seuil_production_3j"])}
    type_map = {l.name: l.lot_type for l in frappe.get_all("Lot",
                  fields=["name", "lot_type"])}
    type_to_lot = {t: n for n, t in type_map.items() if t}

    by_scenario = {"WHITE": [], "RED": [], "YELLOW": [], "SUPPRESSED": [], "NONE": []}
    by_lot = {}

    print(f"\n=== Inventaire complet ({len(rows)} vaches en production) — ref date {ref} ===\n")
    print(f"{'Nom':<6} {'Lot':<14} {'Type':<6} {'Lact':<5} {'DIM':<5} {'Prod':<6} "
          f"{'Tgt':<6} {'Cat':<11} {'Détail'}")
    print("-" * 130)

    for r in sorted(rows, key=lambda x: (x.lot or "", x.nom_metier or "")):
        moy = round((float(r.j_2 or 0) + float(r.j_1 or 0) + float(r.j or 0)) / 3, 1)
        cur_type = type_map.get(r.lot)
        dim = (ref - getdate(r.date_debut)).days
        target = dim_target(dim, r.numero_lactation)
        seuil_cur = seuils.get(r.lot, 0)
        seuil_tgt = seuils.get(type_to_lot.get(target, ""), 0)
        visible, color, reason = predict(cur_type, target, dim, moy, seuil_cur, seuil_tgt,
                                         r.numero_lactation)
        cat = color if visible else (color or "NONE")
        print(f"{r.nom_metier:<6} {(r.lot or ''):<14} {(cur_type or '-'):<6} "
              f"{r.numero_lactation:<5} {dim:<5} {moy:<6} {(target or '-'):<6} "
              f"{cat:<11} {reason}")
        by_scenario.setdefault(cat, []).append(r.nom_metier)
        by_lot.setdefault(r.lot, []).append(r.nom_metier)

    print("\n=== Couverture des scénarios ===")
    for sc in ["WHITE", "RED", "YELLOW", "SUPPRESSED", "NONE"]:
        cows = by_scenario.get(sc, [])
        flag = "✓" if cows else "✗ MANQUANT"
        print(f"  {flag} {sc:<11}: {len(cows):>2} cas — {', '.join(cows[:8]) or '-'}")
