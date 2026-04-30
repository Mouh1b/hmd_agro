"""Predict what consideration colors would appear if seuils were
LOT1=28, LOT2=22, LOT4=17 — without actually changing them in DB."""
import frappe
from frappe.utils import add_days, getdate, today


LOT_DIM_RANGE_MULTI = {
    "FV": (0, 30), "THP": (30, 120), "HP": (120, 240),
    "MP": (240, 305), "FP": (305, 9999),
}
LOT_DIM_RANGE_PRIMI = {"FV": (0, 300), "FP": (300, 9999)}


def lot_dim_range(t, n):
    src = LOT_DIM_RANGE_PRIMI if n == 1 else LOT_DIM_RANGE_MULTI
    return src.get(t)


def dim_target_type(dim, n):
    if dim is None: return None
    if n == 1: return "FV" if dim <= 300 else "FP"
    if dim <= 30: return "FV"
    if dim <= 120: return "THP"
    if dim <= 240: return "HP"
    if dim <= 305: return "MP"
    return "FP"


def run():
    SIMULATED = {"LOT1": 28.0, "LOT2": 22.0, "LOT4": 17.0}
    print(f"\n=== Simulation seuils {SIMULATED} ===\n")

    ref = getdate(add_days(today(), -1))
    j_1, j_2 = add_days(ref, -1), add_days(ref, -2)

    rows = frappe.db.sql("""
        SELECT a.name AS animal, a.nom_metier, a.id_lot AS lot,
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

    type_map = {l.name: l.lot_type for l in frappe.get_all("Lot",
                  fields=["name", "lot_type"])}

    will_show = []
    for r in rows:
        moy = round((float(r.j_2 or 0) + float(r.j_1 or 0) + float(r.j or 0)) / 3, 1)
        cur_type = type_map.get(r.lot)
        dim = (ref - getdate(r.date_debut)).days
        seuil = SIMULATED.get(r.lot, 0)
        target = dim_target_type(dim, r.numero_lactation)
        dim_says_move = target and target != cur_type

        color, reason = "", ""
        if seuil and moy:
            if dim_says_move and moy >= seuil:
                color = "green"
                reason = f"{moy} ≥ {seuil} en {cur_type}"
            elif not dim_says_move and moy < seuil:
                rng = lot_dim_range(cur_type, r.numero_lactation)
                if rng:
                    lo, hi = rng
                    if dim >= lo + (2/3)*(hi - lo):
                        color = "yellow"
                        reason = f"{moy} < {seuil}, fin de stage {cur_type}"

        if dim_says_move or color == "yellow":
            will_show.append({
                "nom": r.nom_metier, "lot": r.lot, "cur_type": cur_type,
                "target": target, "dim": dim, "moy": moy, "color": color, "reason": reason
            })

    counts = {"green": 0, "yellow": 0, "neutral": 0}
    for w in will_show:
        counts[w["color"] or "neutral"] += 1

    print(f"Lignes affichées: {len(will_show)} → 🟢 {counts['green']}  🟡 {counts['yellow']}  ⚪ {counts['neutral']}\n")
    for w in sorted(will_show, key=lambda x: ({'yellow':0,'green':1,'':2}[x['color']], x['nom'])):
        flag = {"green": "🟢", "yellow": "🟡"}.get(w["color"], "⚪")
        arrow = f"{w['cur_type']}→{w['target']}" if w['target'] != w['cur_type'] else f"reste {w['cur_type']}"
        print(f"  {flag} {w['nom']} (lot {w['lot']}, DIM {w['dim']}, moy3j={w['moy']}, {arrow}){' — ' + w['reason'] if w['reason'] else ''}")
