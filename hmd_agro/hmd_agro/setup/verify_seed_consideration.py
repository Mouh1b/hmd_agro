"""Verify seeded Traites + predict green/yellow/neutral counts the
Suggestions panel will show. Mirrors the JS compute_consideration logic."""
import frappe
from frappe.utils import add_days, getdate, today


LOT_DIM_RANGE_MULTI = {
    "FV": (0, 30), "THP": (30, 120), "HP": (120, 240),
    "MP": (240, 305), "FP": (305, 9999),
}
LOT_DIM_RANGE_PRIMI = {"FV": (0, 300), "FP": (300, 9999)}
LOT_RANK = {"FV": 1, "THP": 2, "HP": 3, "MP": 4, "FP": 5,
            "TARISSEMENT": 6, "TARIE": 7}


def lot_dim_range(lot_type, numero_lactation):
    src = LOT_DIM_RANGE_PRIMI if numero_lactation == 1 else LOT_DIM_RANGE_MULTI
    return src.get(lot_type)


def run():
    ref = getdate(add_days(today(), -1))
    j_1 = add_days(ref, -1)
    j_2 = add_days(ref, -2)
    print(f"\nReport reference dates: J={ref}  J-1={j_1}  J-2={j_2}\n")

    rows = frappe.db.sql("""
        SELECT a.name AS animal, a.nom_metier, a.id_lot AS lot,
               l.numero_lactation, l.date_debut,
               SUM(CASE WHEN t.date_traite=%(j2)s THEN t.quantite_litres ELSE 0 END) AS j_2,
               SUM(CASE WHEN t.date_traite=%(j1)s THEN t.quantite_litres ELSE 0 END) AS j_1,
               SUM(CASE WHEN t.date_traite=%(j)s  THEN t.quantite_litres ELSE 0 END) AS j
        FROM `tabAnimal` a
        INNER JOIN `tabLactation` l
            ON l.animal = a.name AND l.statut = 'EN_COURS'
        LEFT JOIN `tabTraite` t
            ON t.animal = a.name AND t.date_traite BETWEEN %(j2)s AND %(j)s
        WHERE a.statut = 'ACTIF' AND a.categorie = 'VACHE'
        GROUP BY a.name
    """, {"j": ref, "j1": j_1, "j2": j_2}, as_dict=True)

    seuils = {l.name: float(l.seuil_production_3j or 0)
              for l in frappe.get_all("Lot",
                  fields=["name", "seuil_production_3j", "lot_type"])}
    lot_type = {l.name: l.lot_type for l in frappe.get_all("Lot",
                  fields=["name", "lot_type"])}
    type_to_lot = {t: n for n, t in lot_type.items() if t}

    # Mirror Python _get_suggestion DIM rule
    def dim_suggested_type(dim, num_lact):
        if dim is None:
            return None
        if num_lact == 1:
            return "FV" if dim <= 300 else "FP"
        if dim <= 30: return "FV"
        if dim <= 120: return "THP"
        if dim <= 240: return "HP"
        if dim <= 305: return "MP"
        return "FP"

    will_show = []  # rows that will appear in the dialog
    for r in rows:
        moy = round((float(r.j_2 or 0) + float(r.j_1 or 0) + float(r.j or 0)) / 3, 1)
        cur_type = lot_type.get(r.lot)
        dim = (ref - getdate(r.date_debut)).days
        seuil = seuils.get(r.lot, 0)
        target_type = dim_suggested_type(dim, r.numero_lactation)
        dim_says_move = target_type and target_type != cur_type

        # Resolve color (mirrors JS compute_consideration after refactor)
        color, sub_type, reason = "", "", ""
        if moy:
            if dim_says_move:
                tgt_seuil = seuils.get(type_to_lot.get(target_type, ""), 0)
                cur_rank = LOT_RANK.get(cur_type, 0)
                tgt_rank = LOT_RANK.get(target_type, 0)
                if tgt_rank > cur_rank and seuil and moy >= seuil:
                    color, sub_type = "green", "demote_keep"
                    reason = f"démote→{target_type}, moy {moy} ≥ seuil {seuil} en {cur_type} → garder"
                elif tgt_rank < cur_rank and tgt_seuil and moy < tgt_seuil:
                    color, sub_type = "green", "promote_not_ready"
                    reason = f"promote→{target_type}, moy {moy} < seuil {tgt_seuil} en {target_type} → SUPPRESSED"
            elif seuil and moy < seuil:
                rng = lot_dim_range(cur_type, r.numero_lactation)
                if rng:
                    lo, hi = rng
                    if dim >= lo + (2/3)*(hi - lo):
                        color = "yellow"
                        reason = f"moy {moy} < seuil {seuil}, DIM {dim} dans dernier tiers de {cur_type}({lo}-{hi})"

        # Apply suppression: DIM-mismatch + promote_not_ready → don't show
        suppressed = (dim_says_move and sub_type == "promote_not_ready")
        if (dim_says_move or color == "yellow") and not suppressed:
            will_show.append({
                "nom": r.nom_metier, "lot": r.lot, "cur_type": cur_type,
                "target_type": target_type, "dim": dim, "moy": moy,
                "color": color, "reason": reason,
            })

    counts = {"green": 0, "yellow": 0, "neutral": 0}
    for w in will_show:
        counts[w["color"] or "neutral"] += 1

    print(f"Total VACHE en production: {len(rows)}")
    print(f"\nSeront affichées dans le dialogue Suggestions: {len(will_show)}")
    print(f"  🟢 Green:   {counts['green']}")
    print(f"  🟡 Yellow:  {counts['yellow']}")
    print(f"  ⚪ Neutre:  {counts['neutral']}  (DIM-only, sans seuil)")

    print("\nDétail des lignes affichées:")
    for w in sorted(will_show, key=lambda x: ({'yellow':0,'green':1,'':2}[x['color']], x['nom'])):
        flag = {"green": "🟢", "yellow": "🟡"}.get(w["color"], "⚪")
        arrow = f"{w['cur_type']}→{w['target_type']}" if w['target_type'] != w['cur_type'] else f"reste {w['cur_type']}"
        print(f"  {flag} {w['nom']} (lot {w['lot']}, DIM {w['dim']}, moy3j={w['moy']}, {arrow}){' — ' + w['reason'] if w['reason'] else ''}")

    print("\n--- Distribution complète des vaches ---")
    by_lot = {}
    for r in rows:
        moy = round((float(r.j_2 or 0) + float(r.j_1 or 0) + float(r.j or 0)) / 3, 1)
        cur_type = lot_type.get(r.lot)
        dim = (ref - getdate(r.date_debut)).days
        seuil = seuils.get(r.lot, 0)
        rng = lot_dim_range(cur_type, r.numero_lactation)
        in_last_third = ""
        if rng:
            lo, hi = rng
            in_last_third = " [dernier 1/3]" if dim >= lo + (2/3)*(hi - lo) else ""
        by_lot.setdefault(r.lot or "(no lot)", []).append(
            f"  {r.nom_metier} DIM {dim} moy3j {moy}L{in_last_third}"
        )
    for lot in sorted(by_lot):
        seuil = seuils.get(lot, 0)
        cur_type = lot_type.get(lot, "?")
        print(f"\n{lot} ({cur_type}, seuil={seuil}):")
        for line in sorted(by_lot[lot]):
            print(line)
