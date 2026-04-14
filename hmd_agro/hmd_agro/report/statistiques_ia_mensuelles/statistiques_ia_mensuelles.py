import frappe
from frappe.utils import today, cint

MOIS_FR = {
    1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril",
    5: "Mai", 6: "Juin", 7: "Juillet", 8: "Août",
    9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"
}


def execute(filters=None):
    filters = filters or {}
    annee = int(filters.get("annee") or today()[:4])

    columns = build_columns()
    rows = [build_row(m, annee) for m in range(1, 13)]
    rows.append(build_total_row(rows))

    chart = build_chart(rows[:-1])  # exclude TOTAL row from chart
    summary = build_summary(rows[-1], annee)

    return columns, rows, None, chart, summary


def build_columns():
    return [
        {"fieldname": "mois", "label": "Le mois", "fieldtype": "Data", "width": 100},
        {"fieldname": "nb_velages", "label": "NB vêlage", "fieldtype": "Int", "width": 90},
        {"fieldname": "velles_nees", "label": "Velle Naissance", "fieldtype": "Int", "width": 110},
        {"fieldname": "velles_mortes", "label": "Velle Morte", "fieldtype": "Int", "width": 95},
        {"fieldname": "pct_perte_velles", "label": "% perte velles", "fieldtype": "Percent", "width": 95},
        {"fieldname": "veaux_nes", "label": "Veaux Naissance", "fieldtype": "Int", "width": 110},
        {"fieldname": "veaux_morts", "label": "Veaux Morts", "fieldtype": "Int", "width": 95},
        {"fieldname": "pct_perte_veaux", "label": "% perte veaux", "fieldtype": "Percent", "width": 95},
        {"fieldname": "nb_avortements", "label": "Avrtt", "fieldtype": "Int", "width": 70},
        {"fieldname": "nb_ia1", "label": "NB IA1", "fieldtype": "Int", "width": 75},
        {"fieldname": "vg_ia1", "label": "VG+ IA1", "fieldtype": "Int", "width": 80},
        {"fieldname": "pct_reussite_ia1", "label": "% réussite IA1", "fieldtype": "Percent", "width": 100},
        {"fieldname": "nb_ia2", "label": "NB IA2", "fieldtype": "Int", "width": 75},
        {"fieldname": "vg_ia2", "label": "VG+ IA2", "fieldtype": "Int", "width": 80},
        {"fieldname": "pct_reussite_ia2", "label": "% réussite IA2", "fieldtype": "Percent", "width": 100},
        {"fieldname": "nb_ia3", "label": "NB IA3", "fieldtype": "Int", "width": 75},
        {"fieldname": "vg_ia3", "label": "VG+ IA3", "fieldtype": "Int", "width": 80},
        {"fieldname": "pct_reussite_ia3", "label": "% réussite IA3", "fieldtype": "Percent", "width": 100},
        {"fieldname": "nb_ia_sup", "label": "NB >IA3", "fieldtype": "Int", "width": 80},
        {"fieldname": "vg_ia_sup", "label": "VG+ >IA3", "fieldtype": "Int", "width": 85},
        {"fieldname": "pct_reussite_ia_sup", "label": "% réussite >IA3", "fieldtype": "Percent", "width": 110},
        {"fieldname": "nb_ia_total", "label": "NB IA Global", "fieldtype": "Int", "width": 100},
        {"fieldname": "vg_total", "label": "VG+ Global", "fieldtype": "Int", "width": 95},
        {"fieldname": "pct_reussite_global", "label": "% réussite Global", "fieldtype": "Percent", "width": 115},
    ]


def build_row(mois, annee):
    """Build one monthly row by aggregating Velage, Avortement, Insemination."""
    # Velages and births
    velages = frappe.db.sql("""
        SELECT nombre_veaux, sexe_veau1, vivant_veau1, sexe_veau2, vivant_veau2
        FROM `tabVelage`
        WHERE MONTH(date_velage) = %s AND YEAR(date_velage) = %s
    """, (mois, annee), as_dict=True)

    nb_velages = len(velages)
    velles_nees = velles_mortes = 0
    veaux_nes = veaux_morts = 0
    for v in velages:
        if v.sexe_veau1 == "F":
            velles_nees += 1
            if not v.vivant_veau1:
                velles_mortes += 1
        elif v.sexe_veau1 == "M":
            veaux_nes += 1
            if not v.vivant_veau1:
                veaux_morts += 1
        if cint(v.nombre_veaux) >= 2:
            if v.sexe_veau2 == "F":
                velles_nees += 1
                if not v.vivant_veau2:
                    velles_mortes += 1
            elif v.sexe_veau2 == "M":
                veaux_nes += 1
                if not v.vivant_veau2:
                    veaux_morts += 1

    # Avortements
    nb_avortements = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabAvortement`
        WHERE MONTH(date_avortement) = %s AND YEAR(date_avortement) = %s
    """, (mois, annee))[0][0]

    # IA aggregations by rank
    ia_stats = frappe.db.sql("""
        SELECT
            CASE
                WHEN numero_ia = 1 THEN 1
                WHEN numero_ia = 2 THEN 2
                WHEN numero_ia = 3 THEN 3
                ELSE 4
            END AS rang,
            COUNT(*) AS nb,
            SUM(CASE WHEN resultat = 'REUSSIE' THEN 1 ELSE 0 END) AS vg
        FROM `tabInsemination`
        WHERE MONTH(date_ia) = %s AND YEAR(date_ia) = %s
        GROUP BY rang
    """, (mois, annee), as_dict=True)

    ia_map = {s.rang: s for s in ia_stats}
    nb_ia1 = ia_map.get(1, {}).get("nb", 0) or 0
    vg_ia1 = ia_map.get(1, {}).get("vg", 0) or 0
    nb_ia2 = ia_map.get(2, {}).get("nb", 0) or 0
    vg_ia2 = ia_map.get(2, {}).get("vg", 0) or 0
    nb_ia3 = ia_map.get(3, {}).get("nb", 0) or 0
    vg_ia3 = ia_map.get(3, {}).get("vg", 0) or 0
    nb_ia_sup = ia_map.get(4, {}).get("nb", 0) or 0
    vg_ia_sup = ia_map.get(4, {}).get("vg", 0) or 0

    nb_ia_total = nb_ia1 + nb_ia2 + nb_ia3 + nb_ia_sup
    vg_total = vg_ia1 + vg_ia2 + vg_ia3 + vg_ia_sup

    return {
        "mois": MOIS_FR[mois],
        "nb_velages": nb_velages,
        "velles_nees": velles_nees,
        "velles_mortes": velles_mortes,
        "pct_perte_velles": pct(velles_mortes, velles_nees),
        "veaux_nes": veaux_nes,
        "veaux_morts": veaux_morts,
        "pct_perte_veaux": pct(veaux_morts, veaux_nes),
        "nb_avortements": nb_avortements,
        "nb_ia1": nb_ia1, "vg_ia1": vg_ia1, "pct_reussite_ia1": pct(vg_ia1, nb_ia1),
        "nb_ia2": nb_ia2, "vg_ia2": vg_ia2, "pct_reussite_ia2": pct(vg_ia2, nb_ia2),
        "nb_ia3": nb_ia3, "vg_ia3": vg_ia3, "pct_reussite_ia3": pct(vg_ia3, nb_ia3),
        "nb_ia_sup": nb_ia_sup, "vg_ia_sup": vg_ia_sup, "pct_reussite_ia_sup": pct(vg_ia_sup, nb_ia_sup),
        "nb_ia_total": nb_ia_total, "vg_total": vg_total, "pct_reussite_global": pct(vg_total, nb_ia_total),
    }


def build_total_row(monthly_rows):
    """Aggregate the 12 monthly rows into a TOTAL row."""
    sums = {k: 0 for k in [
        "nb_velages", "velles_nees", "velles_mortes", "veaux_nes", "veaux_morts",
        "nb_avortements", "nb_ia1", "vg_ia1", "nb_ia2", "vg_ia2",
        "nb_ia3", "vg_ia3", "nb_ia_sup", "vg_ia_sup", "nb_ia_total", "vg_total"
    ]}
    for r in monthly_rows:
        for k in sums:
            sums[k] += r.get(k) or 0

    return {
        "mois": "TOTAL",
        **sums,
        "pct_perte_velles": pct(sums["velles_mortes"], sums["velles_nees"]),
        "pct_perte_veaux": pct(sums["veaux_morts"], sums["veaux_nes"]),
        "pct_reussite_ia1": pct(sums["vg_ia1"], sums["nb_ia1"]),
        "pct_reussite_ia2": pct(sums["vg_ia2"], sums["nb_ia2"]),
        "pct_reussite_ia3": pct(sums["vg_ia3"], sums["nb_ia3"]),
        "pct_reussite_ia_sup": pct(sums["vg_ia_sup"], sums["nb_ia_sup"]),
        "pct_reussite_global": pct(sums["vg_total"], sums["nb_ia_total"]),
    }


def pct(num, denom):
    if not denom:
        return 0
    return round((num / denom) * 100, 1)


def build_chart(monthly_rows):
    labels = [r["mois"][:3] for r in monthly_rows]
    return {
        "data": {
            "labels": labels,
            "datasets": [
                {"name": "% IA1", "values": [r["pct_reussite_ia1"] for r in monthly_rows]},
                {"name": "% IA2", "values": [r["pct_reussite_ia2"] for r in monthly_rows]},
                {"name": "% IA3", "values": [r["pct_reussite_ia3"] for r in monthly_rows]},
                {"name": "% Global", "values": [r["pct_reussite_global"] for r in monthly_rows]},
            ]
        },
        "type": "line",
        "colors": ["#48bb78", "#4299e1", "#ed8936", "#9f7aea"]
    }


def build_summary(total_row, annee):
    veaux_vivants = (total_row["velles_nees"] - total_row["velles_mortes"]) \
                  + (total_row["veaux_nes"] - total_row["veaux_morts"])
    total_naissances = total_row["velles_nees"] + total_row["veaux_nes"]
    total_morts = total_row["velles_mortes"] + total_row["veaux_morts"]
    pct_perte_global = pct(total_morts, total_naissances)

    return [
        {"value": total_row["nb_velages"], "label": f"Vêlages {annee}", "datatype": "Int"},
        {"value": veaux_vivants, "label": "Veaux + velles vivants", "datatype": "Int"},
        {"value": pct_perte_global, "label": "% perte global", "datatype": "Percent"},
        {"value": total_row["pct_reussite_global"], "label": "% réussite IA global", "datatype": "Percent"},
    ]
