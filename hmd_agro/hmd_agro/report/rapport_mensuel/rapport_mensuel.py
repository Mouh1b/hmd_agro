import frappe
import json
from frappe.utils import getdate, today, cint
from calendar import monthrange

MOIS_FR = {
    "Janvier": 1, "Février": 2, "Mars": 3, "Avril": 4,
    "Mai": 5, "Juin": 6, "Juillet": 7, "Août": 8,
    "Septembre": 9, "Octobre": 10, "Novembre": 11, "Décembre": 12
}

CATEGORIES = [
    "Vaches - Lact.", "Vaches - Tarie", "Gén. - Vide", "Gén. - Pleine",
    "Veaux", "Engraiss.", "Velles", "Total"
]

# Maps report columns to snapshot JSON keys and Animal filters
CAT_CONFIG = {
    "Vaches - Lact.": {"key": "vaches_lactantes", "filters": {"categorie": "VACHE", "etat_lactation": "EN_PRODUCTION"}},
    "Vaches - Tarie": {"key": "vaches_taries", "filters": {"categorie": "VACHE", "etat_lactation": "TARIE"}},
    "Gén. - Vide": {"key": "genisses_vides", "filters": {"categorie": "GENISSE", "etat_gestation": "VIDE"}},
    "Gén. - Pleine": {"key": "genisses_pleines", "filters": {"categorie": "GENISSE", "etat_gestation": "GESTANTE"}},
    "Veaux": {"key": "veaux", "filters": {"categorie": "VEAU"}},
    "Engraiss.": {"key": "engraissement", "filters": {"categorie": "TAURILLON"}},
    "Velles": {"key": "velles", "filters": {"categorie": "VELLE"}},
}


def execute(filters=None):
    filters = filters or {}
    mois_nom = filters.get("mois") or "Janvier"
    mois = MOIS_FR.get(mois_nom, 1)
    annee = int(filters.get("annee") or today()[:4])
    jour = cint(filters.get("jour")) or 0
    section = filters.get("section") or "Tout"

    nb_jours = monthrange(annee, mois)[1]
    if jour:
        jour = min(jour, nb_jours)
        date_debut = date_fin = getdate(f"{annee}-{mois:02d}-{jour:02d}")
    else:
        date_debut = getdate(f"{annee}-{mois:02d}-01")
        date_fin = getdate(f"{annee}-{mois:02d}-{nb_jours}")

    ctx = {"date_debut": date_debut, "date_fin": date_fin, "nb_jours": nb_jours, "mois": mois, "annee": annee, "jour": jour}

    builders = {
        "Effectif": _effectif,
        "Production": _production,
        "Production par Lot": _production_lot,
        "Alimentation": _alimentation,
        "Indicateurs": _indicateurs,
    }

    if section in builders:
        return builders[section](ctx)
    return _tout(ctx)


# ─── Effectif ───

def _effectif(ctx):
    columns = [{"fieldname": "ligne", "label": "", "fieldtype": "Data", "width": 180}]
    for cat in CATEGORIES:
        columns.append({"fieldname": cat, "label": cat, "fieldtype": "Int", "width": 100})

    date_debut, date_fin = ctx["date_debut"], ctx["date_fin"]
    now = getdate(today())
    is_today = (date_fin >= now)
    snap = _read_snapshot(date_debut)

    # No snapshot and not today → can't show data
    if not snap and not is_today:
        is_past = date_fin < now
        msg = "Pas de snapshot pour cette période." if is_past else "Période future."
        row = {"ligne": f"{msg} Données non disponibles.", "is_total": True}
        for cat in CATEGORIES:
            row[cat] = None
        return columns, [row]

    # Events during period
    naissances, mort_nes = _count_naissances(date_debut, date_fin)
    achats = _count_achats(date_debut, date_fin)
    cat_plus, cat_minus, mortalite, ventes, reformes = _parse_version_logs(date_debut, date_fin)
    velage_row = _count_velages(date_debut, date_fin)
    prix_vente = _sum_prix_vente(date_debut, date_fin)

    avort_row = _empty_row()
    for cat in CATEGORIES[:-1]:
        avort_row[cat] = mort_nes.get(cat, 0)
    avort_row["Total"] = mort_nes["Total"] + frappe.db.count("Avortement", {"date_avortement": ["between", [date_debut, date_fin]]})

    # Calculate entrees/sorties per category
    entrees, sorties = _empty_row(), _empty_row()
    for cat in CATEGORIES[:-1]:
        entrees[cat] = naissances.get(cat, 0) + achats.get(cat, 0) + cat_plus.get(cat, 0)
        sorties[cat] = mortalite.get(cat, 0) + ventes.get(cat, 0) + reformes.get(cat, 0) + cat_minus.get(cat, 0)

    if snap:
        # Forward: snapshot → Final
        effectif_init = snap
        effectif_fin = _empty_row()
        for cat in CATEGORIES[:-1]:
            effectif_fin[cat] = max(effectif_init[cat] + entrees[cat] - sorties[cat], 0)
    else:
        # Backward: live count (= Final) → Init
        effectif_fin = _live_count()
        effectif_init = _empty_row()
        for cat in CATEGORIES[:-1]:
            effectif_init[cat] = max(effectif_fin[cat] + sorties[cat] - entrees[cat], 0)

    _set_total(effectif_init)
    _set_total(effectif_fin)

    data = [
        _make_row("Effectif Initial", effectif_init, is_total=True),
        _make_row("Changement Catégorie (+)", cat_plus),
        _make_row("Changement Catégorie (-)", cat_minus),
        _make_row("Vêlage", velage_row),
        _make_row("Naissance", naissances),
        _make_row("Avortement / Mort-né", avort_row),
        _make_row("Vente (Quantité)", ventes),
        _make_row("Vente (Prix DT)", prix_vente),
        _make_row("Mortalité", mortalite),
        _make_row("Réforme", reformes),
        _make_row("Effectif Final", effectif_fin, is_total=True),
    ]

    return columns, data


def _read_snapshot(date):
    """Read snapshot for a specific date. Returns None if not found."""
    data = frappe.db.get_value("Snapshot Mensuel", {"date_snapshot": str(date)}, "data")
    if not data:
        return None
    raw = json.loads(data)
    result = _empty_row()
    for cat, cfg in CAT_CONFIG.items():
        result[cat] = raw.get(cfg["key"], 0)
    _set_total(result)
    return result


def _live_count():
    result = _empty_row()
    for cat, cfg in CAT_CONFIG.items():
        result[cat] = frappe.db.count("Animal", {"statut": "ACTIF", **cfg["filters"]})
    _set_total(result)
    return result


def _count_velages(date_debut, date_fin):
    result = _empty_row()
    velages = frappe.db.sql("""
        SELECT v.animal, a.etat_lactation
        FROM `tabVelage` v JOIN `tabAnimal` a ON v.animal = a.name
        WHERE v.date_velage BETWEEN %s AND %s
    """, (date_debut, date_fin), as_dict=True)
    for v in velages:
        col = "Vaches - Tarie" if v.etat_lactation == "TARIE" else "Vaches - Lact."
        result[col] += 1
    _set_total(result)
    return result


def _count_naissances(date_debut, date_fin):
    naissances = _empty_row()
    mort_nes = _empty_row()

    vel_data = frappe.db.sql("""
        SELECT sexe_veau1, vivant_veau1, sexe_veau2, vivant_veau2, nombre_veaux
        FROM `tabVelage` WHERE date_velage BETWEEN %s AND %s
    """, (date_debut, date_fin), as_dict=True)

    for v in vel_data:
        for suffix in ["1", "2"]:
            if suffix == "2" and cint(v.nombre_veaux) < 2:
                continue
            sexe = v.get(f"sexe_veau{suffix}")
            vivant = v.get(f"vivant_veau{suffix}")
            col = "Veaux" if sexe == "M" else "Velles" if sexe == "F" else None
            if col:
                if vivant:
                    naissances[col] += 1
                else:
                    mort_nes[col] += 1

    for d in (naissances, mort_nes):
        _set_total(d)
    return naissances, mort_nes


def _count_achats(date_debut, date_fin):
    result = _empty_row()
    for cat, cfg in CAT_CONFIG.items():
        result[cat] = frappe.db.count("Animal", {
            **cfg["filters"], "est_achat": 1,
            "date_entree": ["between", [date_debut, date_fin]]
        })
    _set_total(result)
    return result


_CAT_TO_COL = {
    "VACHE": "Vaches - Lact.", "GENISSE": "Gén. - Vide",
    "VEAU": "Veaux", "TAURILLON": "Engraiss.", "VELLE": "Velles",
}

def _parse_version_logs(date_debut, date_fin):
    """Single pass over Version logs: returns cat_plus, cat_minus, mortalite, ventes, reformes."""
    cat_plus, cat_minus = _empty_row(), _empty_row()
    mortalite, ventes, reformes = _empty_row(), _empty_row(), _empty_row()

    versions = frappe.db.sql("""
        SELECT data, docname FROM `tabVersion`
        WHERE ref_doctype = 'Animal' AND creation BETWEEN %s AND %s
    """, (date_debut, date_fin), as_dict=True)

    for ver in versions:
        try:
            changes = json.loads(ver.data).get("changed", [])
        except (json.JSONDecodeError, TypeError):
            continue

        for field, old_val, new_val in changes:
            if field == "categorie":
                old_col = _CAT_TO_COL.get(old_val)
                new_col = _CAT_TO_COL.get(new_val)
                if old_col:
                    cat_minus[old_col] += 1
                if new_col:
                    cat_plus[new_col] += 1
            elif field == "etat_lactation":
                if old_val == "EN_PRODUCTION" and new_val == "TARIE":
                    cat_minus["Vaches - Lact."] += 1
                    cat_plus["Vaches - Tarie"] += 1
                elif old_val == "TARIE" and new_val == "EN_PRODUCTION":
                    cat_minus["Vaches - Tarie"] += 1
                    cat_plus["Vaches - Lact."] += 1
            elif field == "etat_gestation":
                if old_val == "VIDE" and new_val == "GESTANTE":
                    cat_minus["Gén. - Vide"] += 1
                    cat_plus["Gén. - Pleine"] += 1
                elif old_val == "GESTANTE" and new_val == "VIDE":
                    cat_minus["Gén. - Pleine"] += 1
                    cat_plus["Gén. - Vide"] += 1
            elif field == "statut" and new_val in ("MORT", "VENDU", "REFORME"):
                # Find column from categorie change in same version, or query DB
                col = None
                for f2, o2, _ in changes:
                    if f2 == "categorie" and o2:
                        col = _CAT_TO_COL.get(o2)
                        break
                if not col:
                    animal = frappe.db.get_value("Animal", ver.docname,
                        ["categorie", "etat_lactation", "etat_gestation"], as_dict=True)
                    if animal:
                        col = _resolve_col(animal.categorie, animal.etat_lactation, animal.etat_gestation)
                if col:
                    target = {"MORT": mortalite, "VENDU": ventes, "REFORME": reformes}[new_val]
                    target[col] += 1
                    target["Total"] += 1

    for d in (cat_plus, cat_minus):
        _set_total(d)
    return cat_plus, cat_minus, mortalite, ventes, reformes


def _sum_prix_vente(date_debut, date_fin):
    result = _empty_row()
    animals = frappe.db.sql("""
        SELECT categorie, etat_lactation, etat_gestation, prix_vente
        FROM `tabAnimal`
        WHERE statut IN ('VENDU', 'REFORME')
        AND date_sortie BETWEEN %s AND %s
        AND prix_vente > 0
    """, (date_debut, date_fin), as_dict=True)

    for a in animals:
        col = _resolve_col(a.categorie, a.etat_lactation, a.etat_gestation)
        if col:
            result[col] += int(a.prix_vente)
    _set_total(result)
    return result


def _resolve_col(categorie, etat_lactation=None, etat_gestation=None):
    if categorie == "VACHE":
        return "Vaches - Tarie" if etat_lactation == "TARIE" else "Vaches - Lact."
    if categorie == "GENISSE":
        return "Gén. - Pleine" if etat_gestation == "GESTANTE" else "Gén. - Vide"
    return _CAT_TO_COL.get(categorie)


def _set_total(row):
    row["Total"] = sum(v for k, v in row.items() if k != "Total")


def _empty_row():
    return {c: 0 for c in CATEGORIES}


def _make_row(label, values, is_total=False):
    row = {"ligne": label, "is_total": is_total}
    for cat in CATEGORIES:
        row[cat] = values.get(cat, 0)
    return row


# ─── Production ───

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
    nb_vl = frappe.db.count("Animal", {"categorie": "VACHE", "statut": "ACTIF", "etat_lactation": "EN_PRODUCTION"})

    data = []
    total_prod = 0
    for j in range(1, ctx["nb_jours"] + 1):
        d = daily_map.get(j, {})
        prod = float(d.get("prod") or 0)
        total_prod += prod
        data.append({
            "jour": j, "nb_lactantes": nb_vl,
            "production": round(prod, 1),
            "moyenne": round(prod / nb_vl, 1) if nb_vl and prod else 0,
            "taux_tb": round(float(d.get("tb") or 0), 2) or None,
            "taux_tp": round(float(d.get("tp") or 0), 2) or None,
            "commercialise": None,
        })

    data.append({
        "jour": None, "is_total": 1, "nb_lactantes": nb_vl,
        "production": round(total_prod, 1),
        "moyenne": round(total_prod / (nb_vl * ctx["nb_jours"]), 1) if nb_vl else 0,
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


# ─── Production par Lot ───

def _production_lot(ctx):
    date_debut, date_fin = ctx["date_debut"], ctx["date_fin"]

    # Get active lots with lactating cows
    lots = frappe.db.sql("""
        SELECT a.id_lot, COUNT(*) as effectif
        FROM `tabAnimal` a
        WHERE a.statut = 'ACTIF' AND a.categorie = 'VACHE' AND a.etat_lactation = 'EN_PRODUCTION'
        AND a.id_lot IS NOT NULL AND a.id_lot != '' AND a.id_lot != 'Individuel'
        GROUP BY a.id_lot ORDER BY a.id_lot
    """, as_dict=True)

    if not lots:
        return [{"fieldname": "msg", "label": "", "fieldtype": "Data", "width": 300}], \
               [{"msg": "Aucun lot actif avec des vaches lactantes."}]

    lot_names = [l.id_lot for l in lots]
    lot_effectif = {l.id_lot: l.effectif for l in lots}

    # Columns: Jour + one per lot + Total + Moy/VL
    columns = [{"fieldname": "jour", "label": "Jour", "fieldtype": "Data", "width": 80}]
    for lot in lot_names:
        columns.append({"fieldname": lot, "label": lot, "fieldtype": "Float", "precision": 1, "width": 100})
    columns.append({"fieldname": "total", "label": "Total", "fieldtype": "Float", "precision": 1, "width": 100})
    columns.append({"fieldname": "moy_vl", "label": "Moy/VL", "fieldtype": "Float", "precision": 1, "width": 80})

    # Query: production per lot per day
    prod_data = frappe.db.sql("""
        SELECT t.date_traite, a.id_lot, SUM(t.quantite_litres) as prod
        FROM `tabTraite` t JOIN `tabAnimal` a ON t.animal = a.name
        WHERE t.date_traite BETWEEN %s AND %s
        AND a.id_lot IN %s
        GROUP BY t.date_traite, a.id_lot
    """, (date_debut, date_fin, lot_names), as_dict=True)

    # Build lookup: {date: {lot: prod}}
    prod_map = {}
    for p in prod_data:
        prod_map.setdefault(str(p.date_traite), {})[p.id_lot] = float(p.prod or 0)

    # Build rows — one per day
    data = []
    nb_vl_total = sum(lot_effectif.values())
    lot_totals = {lot: 0 for lot in lot_names}
    grand_total = 0

    for j in range(1, ctx["nb_jours"] + 1):
        date_str = str(getdate(f"{ctx['annee']}-{ctx['mois']:02d}-{j:02d}"))
        day_lots = prod_map.get(date_str, {})
        day_total = sum(day_lots.values())

        row = {"jour": str(j)}
        for lot in lot_names:
            val = day_lots.get(lot, 0)
            row[lot] = round(val, 1) if val else None
            lot_totals[lot] += val
        row["total"] = round(day_total, 1) if day_total else None
        row["moy_vl"] = round(day_total / nb_vl_total, 1) if nb_vl_total and day_total else None
        grand_total += day_total
        data.append(row)

    # Effectif row
    eff_row = {"jour": "Effectif", "is_total": True}
    for lot in lot_names:
        eff_row[lot] = lot_effectif.get(lot, 0)
    eff_row["total"] = nb_vl_total
    data.append(eff_row)

    # Moyenne row
    days_with_data = len(prod_map)
    moy_row = {"jour": "Moyenne/lot", "is_total": True}
    for lot in lot_names:
        eff = lot_effectif.get(lot, 0)
        moy_row[lot] = round(lot_totals[lot] / (eff * days_with_data), 1) if eff and days_with_data else None
    moy_row["total"] = round(grand_total / (nb_vl_total * days_with_data), 1) if nb_vl_total and days_with_data else None
    data.append(moy_row)

    return columns, data


# ─── Alimentation ───

def _alimentation(ctx):
    columns = [
        {"fieldname": "aliment", "label": "Aliment", "fieldtype": "Data", "width": 160},
        {"fieldname": "prix_unitaire", "label": "Prix Unit. (DT)", "fieldtype": "Currency", "width": 110},
        {"fieldname": "quantite_jour", "label": "Qté/jour (Total)", "fieldtype": "Float", "precision": 1, "width": 120},
        {"fieldname": "cout_jour", "label": "Coût/jour (DT)", "fieldtype": "Currency", "width": 110},
        {"fieldname": "cout_mois", "label": "Coût/mois (DT)", "fieldtype": "Currency", "width": 110},
    ]

    lots = frappe.get_all("Lot", filters={"actif": 1, "id_ration_actuelle": ["is", "set"]},
                          fields=["name", "id_ration_actuelle", "nb_animaux"])

    aliment_totals = {}
    for lot in lots:
        ration = frappe.get_doc("Ration", lot.id_ration_actuelle)
        for comp in ration.composition:
            aliment_doc = frappe.get_doc("Aliment", comp.aliment)
            key = aliment_doc.nom_aliment
            qty = float(comp.quantite or 0) * (lot.nb_animaux or 0)
            if key not in aliment_totals:
                aliment_totals[key] = {"prix": float(aliment_doc.prix_unitaire or 0), "qty": 0}
            aliment_totals[key]["qty"] += qty

    data = []
    total_cout_jour = 0
    for nom, info in aliment_totals.items():
        cout_jour = round(info["qty"] * info["prix"], 2)
        total_cout_jour += cout_jour
        data.append({
            "aliment": nom,
            "prix_unitaire": info["prix"],
            "quantite_jour": round(info["qty"], 1),
            "cout_jour": cout_jour,
            "cout_mois": round(cout_jour * ctx["nb_jours"], 2),
        })

    data.append({
        "aliment": "TOTAL", "is_total": 1,
        "quantite_jour": round(sum(r["quantite_jour"] for r in data), 1),
        "cout_jour": round(total_cout_jour, 2),
        "cout_mois": round(total_cout_jour * ctx["nb_jours"], 2),
    })

    return columns, data


# ─── Indicateurs ───

def _indicateurs(ctx):
    columns = [
        {"fieldname": "indicateur", "label": "Indicateur", "fieldtype": "Data", "width": 280},
        {"fieldname": "valeur", "label": "Valeur", "fieldtype": "Float", "precision": 1, "width": 120},
        {"fieldname": "unite", "label": "Unité", "fieldtype": "Data", "width": 100},
    ]

    date_debut, date_fin = ctx["date_debut"], ctx["date_fin"]

    vp = frappe.db.count("Animal", {"categorie": "VACHE", "statut": "ACTIF"})
    vl = frappe.db.count("Animal", {"categorie": "VACHE", "statut": "ACTIF", "etat_lactation": "EN_PRODUCTION"})
    vt = frappe.db.count("Animal", {"categorie": "VACHE", "statut": "ACTIF", "etat_lactation": "TARIE"})

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


# ─── Tout ───

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
