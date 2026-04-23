import frappe
from frappe.utils import getdate, today, add_days
from calendar import monthrange

from hmd_agro.hmd_agro.utils.live_state import (
    CATEGORIES, empty_row, set_total, effectif_on_date,
    count_velages, count_naissances, count_avortements_mort_nes,
    count_achats, count_exits, count_changements_cat,
)
from hmd_agro.hmd_agro.utils.import_rapport import read_imported
from hmd_agro.hmd_agro.doctype.allotement_history.allotement_history import lot_population_on_date


# Row label → key mapping for imported days. Ordered to match the live report.
_IMPORTED_ROWS = [
    ("Effectif Initial",         "effectif_initial",     True),
    ("Changement Catégorie (+)", "changement_cat_plus",  False),
    ("Changement Catégorie (-)", "changement_cat_minus", False),
    ("Vêlage",                   "velage",               False),
    ("Naissance",                "naissance",            False),
    ("Avortement / Mort-né",     "avortement_mort_ne",   False),
    ("Achat",                    "achat",                False),
    ("Vente (Quantité)",         "vente_qty",            False),
    ("Vente (Prix DT)",          "vente_prix",           False),
    ("Mortalité",                "mortalite",            False),
    ("Réforme",                  "reforme",              False),
    ("Effectif Final",           "effectif_final",       True),
]


def execute(filters=None):
    filters = filters or {}
    date = getdate(filters.get("date") or today())
    section = filters.get("section") or "Tout"

    nb_jours = monthrange(date.year, date.month)[1]
    date_debut = getdate(f"{date.year}-{date.month:02d}-01")
    date_fin = getdate(f"{date.year}-{date.month:02d}-{nb_jours}")

    ctx = {"date_filter": date, "date_debut": date_debut,
           "date_fin": date_fin, "nb_jours": nb_jours}

    builders = {
        "Effectif": _effectif,
        "Production": _production,
        "Production par Lot": _production_lot,
        "Alimentation": _alimentation,
        "Indicateurs": _indicateurs,
    }
    return builders.get(section, _tout)(ctx)


# ─── Effectif ────────────────────────────────────────────────────────────────

def _effectif(ctx):
    """Per-day Effectif table — live from event doctypes, imported fallback."""
    columns = [{"fieldname": "ligne", "label": "", "fieldtype": "Data", "width": 180}]
    for cat in CATEGORIES:
        columns.append({"fieldname": cat, "label": cat, "fieldtype": "Int", "width": 100})

    date = ctx["date_filter"]

    imp = read_imported(date)
    if imp:
        return columns, [_row(label, imp.get(key, {}), is_total)
                         for label, key, is_total in _IMPORTED_ROWS]

    if getdate(date) > getdate(today()):
        return columns, [_gap_row("Pas encore de données pour cette date.")]

    initial = effectif_on_date(add_days(date, -1))
    final = effectif_on_date(date)
    cat_plus, cat_minus = count_changements_cat(date)
    vente_qty, vente_prix = count_exits(date, "VENDU")
    mortalite, _ = count_exits(date, "MORT")
    reforme, _ = count_exits(date, "REFORME")

    rows = [
        ("Effectif Initial",         initial,                          True),
        ("Changement Catégorie (+)", cat_plus,                         False),
        ("Changement Catégorie (-)", cat_minus,                        False),
        ("Vêlage",                   count_velages(date),              False),
        ("Naissance",                count_naissances(date),           False),
        ("Avortement / Mort-né",     count_avortements_mort_nes(date), False),
        ("Achat",                    count_achats(date),               False),
        ("Vente (Quantité)",         vente_qty,                        False),
        ("Vente (Prix DT)",          vente_prix,                       False),
        ("Mortalité",                mortalite,                        False),
        ("Réforme",                  reforme,                          False),
        ("Effectif Final",           final,                            True),
    ]
    return columns, [_row(label, values, is_total) for label, values, is_total in rows]


def _row(label, values, is_total):
    return {"ligne": label, "is_total": is_total,
            **{cat: values.get(cat, 0) for cat in CATEGORIES}}


def _gap_row(msg):
    return {"ligne": msg, "is_total": True, **{cat: None for cat in CATEGORIES}}


# ─── Production ──────────────────────────────────────────────────────────────

def _production(ctx):
    columns = [
        {"fieldname": "jour", "label": "Jour", "fieldtype": "Int", "width": 60},
        {"fieldname": "nb_lactantes", "label": "VL", "fieldtype": "Int", "width": 60},
        {"fieldname": "production", "label": "Production (L)", "fieldtype": "Float", "precision": 1, "width": 110},
        {"fieldname": "moyenne", "label": "Moy/VL (L)", "fieldtype": "Float", "precision": 1, "width": 100},
        {"fieldname": "taux_tb", "label": "TB (%)", "fieldtype": "Float", "precision": 2, "width": 80},
        {"fieldname": "taux_tp", "label": "TP (%)", "fieldtype": "Float", "precision": 2, "width": 80},
        {"fieldname": "commercialise", "label": "Commercialisé (L)", "fieldtype": "Float", "precision": 1, "width": 120},
    ]

    daily = frappe.db.sql("""
        SELECT DAY(date_traite) AS jour,
            SUM(quantite_litres) AS prod,
            AVG(NULLIF(taux_tb, 0)) AS tb,
            AVG(NULLIF(taux_tp, 0)) AS tp
        FROM `tabTraite`
        WHERE date_traite BETWEEN %s AND %s
        GROUP BY DAY(date_traite)
    """, (ctx["date_debut"], ctx["date_fin"]), as_dict=True)

    daily_map = {d.jour: d for d in daily}

    # Per-day historical lactating-cow count (reconstructed from events)
    vl_by_day = {
        j: effectif_on_date(add_days(ctx["date_debut"], j - 1))["Vaches - Lact."]
        for j in range(1, ctx["nb_jours"] + 1)
    }
    total_cow_days = sum(vl_by_day.values())
    nb_vl_end = vl_by_day[ctx["nb_jours"]]

    data = []
    total_prod = 0
    for j in range(1, ctx["nb_jours"] + 1):
        d = daily_map.get(j, {})
        prod = float(d.get("prod") or 0)
        total_prod += prod
        nb_vl = vl_by_day[j]
        data.append({
            "jour": j, "nb_lactantes": nb_vl,
            "production": round(prod, 1),
            "moyenne": round(prod / nb_vl, 1) if nb_vl and prod else 0,
            "taux_tb": round(float(d.get("tb") or 0), 2) or None,
            "taux_tp": round(float(d.get("tp") or 0), 2) or None,
            "commercialise": None,
        })

    data.append({
        "jour": None, "is_total": 1, "nb_lactantes": nb_vl_end,
        "production": round(total_prod, 1),
        "moyenne": round(total_prod / total_cow_days, 1) if total_cow_days else 0,
    })

    chart = {
        "data": {
            "labels": [str(j) for j in range(1, ctx["nb_jours"] + 1)],
            "datasets": [{"name": "Production (L)", "values": [
                float(daily_map.get(j, {}).get("prod") or 0) for j in range(1, ctx["nb_jours"] + 1)
            ]}]
        },
        "type": "bar", "colors": ["#4299e1"]
    }

    return columns, data, None, chart


# ─── Production par Lot ──────────────────────────────────────────────────────

def _production_lot(ctx):
    """4-row table: Effectif (D), D-1 production, D production, Moyenne (D).
    Effectif and production are historical (frozen via Traite.id_lot at save time).
    Sources: Rapport Journalier Importe (imported) or Traite.id_lot (live)."""
    date = ctx["date_filter"]
    prev_date = add_days(date, -1)

    imp = read_imported(date)
    if imp and imp.get("production_lot"):
        return _render_imported_lot(imp, date, prev_date)
    return _render_live_lot(date, prev_date)


def _render_imported_lot(imp, date, prev_date):
    lot_data = imp["production_lot"]
    # Try to also fetch D-1's import so the prev-day production row isn't always blank.
    prev_imp = read_imported(prev_date)
    prev_prod = (prev_imp or {}).get("production_lot") or {}

    lots = sorted(set(lot_data) | set(prev_prod))
    columns = _lot_columns(lots)
    total_eff = sum(lot_data.get(lot, {}).get("effectif", 0) for lot in lots)
    total_prod = sum(lot_data.get(lot, {}).get("production", 0) for lot in lots)

    rows = [
        {"jour": "Effectif", "is_total": True, "total": total_eff,
         **{lot: lot_data.get(lot, {}).get("effectif", 0) or None for lot in lots}},
        {"jour": prev_date.strftime("%d/%m"),
         **{lot: prev_prod.get(lot, {}).get("production", 0) or None for lot in lots},
         "total": sum(prev_prod.get(lot, {}).get("production", 0) for lot in lots) or None},
        {"jour": date.strftime("%d/%m"),
         **{lot: lot_data.get(lot, {}).get("production", 0) or None for lot in lots},
         "total": total_prod or None},
        {"jour": "Moyenne / lot", "is_total": True,
         **{lot: _safe_div(lot_data.get(lot, {}).get("production", 0),
                           lot_data.get(lot, {}).get("effectif", 0)) for lot in lots},
         "total": _safe_div(total_prod, total_eff)},
    ]
    return columns, rows


def _render_live_lot(date, prev_date):
    prod_curr = _traite_by_lot(date)
    prod_prev = _traite_by_lot(prev_date)
    eff_curr = _lactantes_by_lot_on_date(date)

    # Always include all currently-lactating lots, plus any historical lots
    # that appear in D-1/D data (handles renamed lots gracefully).
    lots = sorted(set(_active_lactating_lots()) | set(prod_curr) | set(prod_prev) | set(eff_curr))
    columns = _lot_columns(lots)
    total_eff = sum(eff_curr.values())
    total_prod = sum(prod_curr.values())

    rows = [
        {"jour": "Effectif", "is_total": True, "total": total_eff,
         **{lot: eff_curr.get(lot, 0) or None for lot in lots}},
        _lot_day_row(prev_date.strftime("%d/%m"), lots, prod_prev),
        _lot_day_row(date.strftime("%d/%m"), lots, prod_curr),
        {"jour": "Moyenne / lot", "is_total": True,
         **{lot: _safe_div(prod_curr.get(lot, 0), eff_curr.get(lot, 0)) for lot in lots},
         "total": _safe_div(total_prod, total_eff)},
    ]
    return columns, rows


def _active_lactating_lots():
    """Distinct lots with at least one currently-lactating cow."""
    return [r[0] for r in frappe.db.sql("""
        SELECT DISTINCT id_lot FROM `tabAnimal`
        WHERE statut = 'ACTIF' AND etat_lactation = 'EN_PRODUCTION'
          AND id_lot IS NOT NULL AND id_lot != ''
    """)]


def _traite_by_lot(date):
    """Production per lot using Traite.id_lot (stamped at save time)."""
    rows = frappe.db.sql("""
        SELECT id_lot AS lot, SUM(quantite_litres) AS litres
        FROM `tabTraite`
        WHERE date_traite = %s AND id_lot IS NOT NULL AND id_lot != ''
        GROUP BY id_lot
    """, str(date), as_dict=True)
    return {r.lot: round(float(r.litres or 0), 1) for r in rows}


def _lactantes_by_lot_on_date(date):
    """Historical lactantes count per lot for `date`, derived from Traite.id_lot
    (frozen at save time). Counts distinct animals milked per lot that day."""
    rows = frappe.db.sql("""
        SELECT id_lot AS lot, COUNT(DISTINCT animal) AS n
        FROM `tabTraite`
        WHERE date_traite = %s AND id_lot IS NOT NULL AND id_lot != ''
        GROUP BY id_lot
    """, str(date), as_dict=True)
    return {r.lot: int(r.n) for r in rows}


def _lot_columns(lots):
    cols = [{"fieldname": "jour", "label": "", "fieldtype": "Data", "width": 100}]
    for lot in lots:
        cols.append({"fieldname": lot, "label": lot, "fieldtype": "Float", "precision": 1, "width": 100})
    cols.append({"fieldname": "total", "label": "Total", "fieldtype": "Float", "precision": 1, "width": 100})
    return cols


def _lot_day_row(label, lots, prod_map):
    total = sum(prod_map.get(lot, 0) for lot in lots)
    return {"jour": label,
            **{lot: prod_map.get(lot, 0) or None for lot in lots},
            "total": round(total, 1) or None}


def _safe_div(num, den):
    return round(num / den, 1) if den else None


# ─── Alimentation ────────────────────────────────────────────────────────────

def _alimentation(ctx):
    # Per-day historical reconstruction: for each day in the month and each lot,
    # look up the ration that was assigned and the population, then accumulate
    # monthly totals. Handles mid-month ration switches and population changes.
    active_lots = frappe.get_all("Lot", filters={"actif": 1},
                                 fields=["name"], order_by="name")
    if not active_lots:
        return [{"fieldname": "msg", "label": "", "fieldtype": "Data", "width": 300}], \
               [{"msg": "Aucun lot actif."}]

    date_debut, date_fin, nb_jours = ctx["date_debut"], ctx["date_fin"], ctx["nb_jours"]
    days = [add_days(date_debut, i) for i in range(nb_jours)]
    lot_names_all = [l.name for l in active_lots]

    # Pre-fetch all ration history for active lots (1 query) so the per-day
    # lookup is in-memory instead of N×D SQL calls.
    history = {}
    for r in frappe.db.sql("""
        SELECT lot, to_ration, DATE(creation) AS dt
        FROM `tabLot Ration History`
        WHERE lot IN %s
        ORDER BY creation ASC
    """, (lot_names_all,), as_dict=True):
        history.setdefault(r.lot, []).append((r.dt, r.to_ration))

    # Fallback when no history exists for a lot — use the current ration.
    current_ration = {l.name: frappe.db.get_value("Lot", l.name, "id_ration_actuelle")
                      for l in active_lots}

    def ration_for(lot, day):
        for dt, rat in reversed(history.get(lot, [])):
            if dt <= day:
                return rat
        return current_ration.get(lot)

    comp_cache = {}
    def composition(ration):
        if ration in comp_cache:
            return comp_cache[ration]
        rows = frappe.db.sql("""
            SELECT c.aliment, c.quantite, a.ms_pct
            FROM `tabComposition Ration` c JOIN `tabAliment` a ON c.aliment = a.name
            WHERE c.parent = %s
        """, ration, as_dict=True) if ration else []
        comp_cache[ration] = rows
        return rows

    # Walk each day, accumulate per-lot monthly totals.
    monthly_qty = {}      # {(aliment, lot): kg total over month}
    monthly_ms = {}       # {lot: kg MS total over month}
    cow_days = {}         # {lot: sum(daily_pop) — cow-days for /tête division}
    aliment_ms_pct = {}   # {aliment: ms_pct fraction}
    lots_with_data = set()

    for day in days:
        pop = lot_population_on_date(day)
        for lot in lot_names_all:
            n_pop = pop.get(lot, 0)
            if n_pop == 0:
                continue
            cow_days[lot] = cow_days.get(lot, 0) + n_pop
            ration = ration_for(lot, day)
            if not ration:
                continue
            for c in composition(ration):
                aliment = c.aliment
                ms_pct = float(c.ms_pct or 0)
                aliment_ms_pct[aliment] = ms_pct
                day_qty = float(c.quantite or 0) * n_pop
                monthly_qty[(aliment, lot)] = monthly_qty.get((aliment, lot), 0) + day_qty
                monthly_ms[lot] = monthly_ms.get(lot, 0) + day_qty * ms_pct
                lots_with_data.add(lot)

    if not lots_with_data:
        return [{"fieldname": "msg", "label": "", "fieldtype": "Data", "width": 300}], \
               [{"msg": "Aucun lot avec ration assignée pour ce mois."}]

    lot_names = sorted(lots_with_data)
    columns = [
        {"fieldname": "aliment", "label": "Aliment", "fieldtype": "Data", "width": 180},
        {"fieldname": "ms_pct", "label": "MS%", "fieldtype": "Percent", "width": 80},
    ]
    for lot in lot_names:
        columns.append({"fieldname": lot, "label": lot, "fieldtype": "Float", "precision": 2, "width": 100})

    data = []
    for aliment in sorted(set(a for a, _ in monthly_qty)):
        # ms_pct stored as fraction (0.86) — multiply by 100 for the % column display.
        row = {"aliment": aliment, "ms_pct": aliment_ms_pct.get(aliment, 0) * 100}
        for lot in lot_names:
            v = monthly_qty.get((aliment, lot), 0)
            row[lot] = round(v, 2) if v else None
        data.append(row)

    ms_total_row = {"aliment": "MS Total Distribué", "ms_pct": None, "is_total": True}
    for lot in lot_names:
        v = monthly_ms.get(lot, 0)
        ms_total_row[lot] = round(v, 2) if v else None
    data.append(ms_total_row)

    # MS per cow-day: monthly_MS / sum(daily_pop) — robust to mid-month population changes.
    ms_tete_row = {"aliment": "MS Distribué/Tête", "ms_pct": None, "is_total": True}
    for lot in lot_names:
        cd = cow_days.get(lot, 0)
        ms_tete_row[lot] = round(monthly_ms.get(lot, 0) / cd, 2) if cd else None
    data.append(ms_tete_row)

    # Production attributed to the historically-stamped lot (Traite.id_lot frozen at save).
    prod = frappe.db.sql("""
        SELECT id_lot, SUM(quantite_litres) AS total_prod
        FROM `tabTraite`
        WHERE date_traite BETWEEN %s AND %s AND id_lot IN %s
        GROUP BY id_lot
    """, (date_debut, date_fin, lot_names), as_dict=True)
    prod_per_lot = {p.id_lot: float(p.total_prod or 0) for p in prod}

    eff_row = {"aliment": "Efficacité alimentaire L/Kg MS", "ms_pct": None, "is_total": True}
    for lot in lot_names:
        ms = monthly_ms.get(lot, 0)
        milk = prod_per_lot.get(lot, 0)
        eff_row[lot] = round(milk / ms, 2) if ms else None
    data.append(eff_row)

    return columns, data


# ─── Indicateurs ─────────────────────────────────────────────────────────────

def _indicateurs(ctx):
    columns = [
        {"fieldname": "indicateur", "label": "Indicateur", "fieldtype": "Data", "width": 280},
        {"fieldname": "valeur", "label": "Valeur", "fieldtype": "Float", "precision": 1, "width": 120},
        {"fieldname": "unite", "label": "Unité", "fieldtype": "Data", "width": 100},
    ]

    date_debut, date_fin = ctx["date_debut"], ctx["date_fin"]

    # End-of-month historical herd composition (reconstructed from events)
    eff = effectif_on_date(date_fin)
    vl = eff["Vaches - Lact."]
    vt = eff["Vaches - Tarie"]
    vp = vl + vt

    prod = frappe.db.sql("""
        SELECT SUM(quantite_litres) FROM `tabTraite`
        WHERE date_traite BETWEEN %s AND %s
    """, (date_debut, date_fin))[0][0] or 0

    concentre = _total_concentre(ctx["nb_jours"])
    nb_ia = frappe.db.count("Insemination", {"date_ia": ["between", [date_debut, date_fin]]})
    ia_ok = frappe.db.count("Insemination", {"date_ia": ["between", [date_debut, date_fin]], "resultat": "REUSSIE"})
    nb_vel = frappe.db.count("Velage", {"date_velage": ["between", [date_debut, date_fin]]})

    data = [
        {"indicateur": "Vaches Présentes", "valeur": vp, "unite": "têtes"},
        {"indicateur": "Vaches Lactantes", "valeur": vl, "unite": "têtes"},
        {"indicateur": "Vaches Taries", "valeur": vt, "unite": "têtes"},
        {"indicateur": "Production Totale", "valeur": round(prod, 1), "unite": "litres"},
        {"indicateur": "Moy. Production/VL/Jour", "valeur": round(prod / (vl * ctx["nb_jours"]), 1) if vl else 0, "unite": "L/tête"},
        {"indicateur": "Concentré Total", "valeur": round(concentre, 1), "unite": "kg"},
        {"indicateur": "Concentré/Tête", "valeur": round(concentre / vp, 1) if vp else 0, "unite": "kg/tête"},
        {"indicateur": "L/C (Efficacité)", "valeur": round(prod / concentre, 2) if concentre else 0, "unite": "L/kg"},
        {"indicateur": "Nombre IA", "valeur": nb_ia, "unite": ""},
        {"indicateur": "Taux Réussite IA", "valeur": round(ia_ok / nb_ia * 100, 1) if nb_ia else 0, "unite": "%"},
        {"indicateur": "Nombre Vêlages", "valeur": nb_vel, "unite": ""},
        {"indicateur": "Frais Concentré", "valeur": None, "unite": "DT (à intégrer)"},
        {"indicateur": "Frais Fourrage", "valeur": None, "unite": "DT (à intégrer)"},
        {"indicateur": "Coût Alimentaire/L", "valeur": None, "unite": "DT/L (à intégrer)"},
        {"indicateur": "Main d'Oeuvre", "valeur": None, "unite": "DT (à intégrer)"},
        {"indicateur": "Chiffre d'Affaires Lait", "valeur": None, "unite": "DT (à intégrer)"},
    ]

    return columns, data


def _total_concentre(nb_jours):
    lots = frappe.get_all("Lot", filters={"actif": 1, "id_ration_actuelle": ["is", "set"]},
                          fields=["id_ration_actuelle", "nb_animaux"])
    total = 0
    for lot in lots:
        comps = frappe.get_all("Composition Ration",
            filters={"parent": lot.id_ration_actuelle}, fields=["aliment", "quantite"])
        for c in comps:
            if frappe.db.get_value("Aliment", c.aliment, "type_aliment") == "CONCENTRE":
                total += float(c.quantite or 0) * (lot.nb_animaux or 0) * nb_jours
    return total


# ─── Tout ────────────────────────────────────────────────────────────────────

def _tout(ctx):
    columns = [
        {"fieldname": "label", "label": "", "fieldtype": "Data", "width": 280},
        {"fieldname": "valeur", "label": "Valeur", "fieldtype": "Data", "width": 150},
    ]

    _, eff_data = _effectif(ctx)[:2]
    _, prod_data = _production(ctx)[:2]
    _, ind_data = _indicateurs(ctx)[:2]

    data = []

    data.append({"label": "── EFFECTIF ──", "valeur": "", "is_header": 1})
    for row in eff_data:
        data.append({"label": row["ligne"], "valeur": str(row.get("Total", 0)), "is_total": row.get("is_total")})

    data.append({"label": "── PRODUCTION ──", "valeur": "", "is_header": 1})
    total = prod_data[-1] if prod_data else {}
    data.append({"label": "Production totale mois", "valeur": f"{total.get('production', 0)} L"})
    data.append({"label": "Moy/VL/Jour", "valeur": f"{total.get('moyenne', 0)} L"})

    data.append({"label": "── INDICATEURS ──", "valeur": "", "is_header": 1})
    for row in ind_data:
        val = row.get("valeur")
        unite = row.get("unite") or ""
        data.append({"label": row["indicateur"], "valeur": f"{val} {unite}" if val is not None else unite})

    return columns, data
