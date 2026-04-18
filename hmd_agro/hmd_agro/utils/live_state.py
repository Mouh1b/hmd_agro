"""
Reconstruct animal states and Effectif report rows from live event doctypes.

No snapshots — each query walks Lactation, Insemination, Velage, Avortement
to determine what each animal's state was on any given date.
"""

import frappe
from frappe.utils import getdate, today, cint

CATEGORIES = [
    "Vaches - Lact.", "Vaches - Tarie", "Gén. - Vide", "Gén. - Pleine",
    "Veaux", "Engraiss.", "Velles", "Total",
]

_SIMPLE_CAT = {"VEAU": "Veaux", "TAURILLON": "Engraiss.", "VELLE": "Velles"}


def resolve_col(cat, lact, gest):
    if cat == "VACHE":
        return "Vaches - Tarie" if lact == "TARIE" else "Vaches - Lact."
    if cat == "GENISSE":
        return "Gén. - Pleine" if gest == "GESTANTE" else "Gén. - Vide"
    return _SIMPLE_CAT.get(cat)


def empty_row():
    return {c: 0 for c in CATEGORIES}


def set_total(row):
    row["Total"] = sum(v for k, v in row.items() if k != "Total")


# ─── Effectif aggregates ─────────────────────────────────────────────────────

def effectif_on_date(date):
    """Count animals per category on `date`. Live query for today, reconstructed for past."""
    date = getdate(date)
    if date == getdate(today()):
        return _live_effectif()
    return _reconstructed_effectif(date)


def _live_effectif():
    """Current Animal table → category counts."""
    rows = frappe.db.sql("""
        SELECT categorie, etat_lactation, etat_gestation, COUNT(*) AS n
        FROM `tabAnimal` WHERE statut = 'ACTIF'
        GROUP BY categorie, etat_lactation, etat_gestation
    """, as_dict=True)
    agg = empty_row()
    for r in rows:
        col = resolve_col(r.categorie, r.etat_lactation or "", r.etat_gestation or "")
        if col:
            agg[col] += r.n
    set_total(agg)
    return agg


def _reconstructed_effectif(date):
    """Reconstruct each animal's state on `date` from event doctypes, then aggregate."""
    d = str(date)

    # 1. Animals present on date D
    animals = frappe.db.sql("""
        SELECT name, categorie, sexe, date_naissance, est_achat, date_entree, date_sortie, statut
        FROM `tabAnimal`
        WHERE (CASE WHEN est_achat = 1 THEN date_entree ELSE date_naissance END) <= %s
          AND (statut = 'ACTIF' OR (date_sortie IS NOT NULL AND date_sortie > %s))
    """, (d, d), as_dict=True)

    if not animals:
        agg = empty_row()
        set_total(agg)
        return agg

    names = [a.name for a in animals]

    # 2. First velage per animal (GENISSE → VACHE transition)
    first_velage = {}
    for r in frappe.db.sql("""
        SELECT animal, MIN(date_velage) AS first_vel
        FROM `tabVelage` WHERE animal IN %s GROUP BY animal
    """, (names,), as_dict=True):
        first_velage[r.animal] = r.first_vel

    # 3. Lactation state on D: most recent lactation starting on or before D
    lact_state = {}
    for r in frappe.db.sql("""
        SELECT l1.animal,
               l1.date_debut,
               l1.date_tarissement,
               l1.statut
        FROM `tabLactation` l1
        INNER JOIN (
            SELECT animal, MAX(date_debut) AS max_debut
            FROM `tabLactation` WHERE date_debut <= %s
            GROUP BY animal
        ) l2 ON l1.animal = l2.animal AND l1.date_debut = l2.max_debut
        WHERE l1.animal IN %s
    """, (d, names), as_dict=True):
        if r.date_tarissement and getdate(r.date_tarissement) <= date:
            lact_state[r.animal] = "TARIE"
        else:
            lact_state[r.animal] = "EN_PRODUCTION"

    # 4. Gestation state on D: last REUSSIE IA before/on D, not followed by Velage/Avortement
    last_ia = {}
    for r in frappe.db.sql("""
        SELECT animal, MAX(date_ia) AS last_ia_date
        FROM `tabInsemination`
        WHERE resultat = 'REUSSIE' AND date_ia <= %s AND animal IN %s
        GROUP BY animal
    """, (d, names), as_dict=True):
        last_ia[r.animal] = r.last_ia_date

    last_end_gest = {}
    for r in frappe.db.sql("""
        SELECT animal, MAX(date_velage) AS last_end
        FROM `tabVelage` WHERE date_velage <= %s AND animal IN %s GROUP BY animal
    """, (d, names), as_dict=True):
        last_end_gest[r.animal] = r.last_end
    for r in frappe.db.sql("""
        SELECT animal, MAX(date_avortement) AS last_end
        FROM `tabAvortement` WHERE date_avortement <= %s AND animal IN %s GROUP BY animal
    """, (d, names), as_dict=True):
        prev = last_end_gest.get(r.animal)
        if not prev or r.last_end > prev:
            last_end_gest[r.animal] = r.last_end

    # 5. Aggregate
    agg = empty_row()
    for a in animals:
        cat = a.categorie
        # GENISSE → VACHE if first velage happened on or before D
        fv = first_velage.get(a.name)
        if fv and getdate(fv) <= date and cat in ("GENISSE", "VACHE"):
            cat = "VACHE"

        lact = ""
        if cat == "VACHE":
            lact = lact_state.get(a.name, "")

        gest = "VIDE"
        ia_date = last_ia.get(a.name)
        if ia_date:
            end_date = last_end_gest.get(a.name)
            if not end_date or getdate(ia_date) > getdate(end_date):
                gest = "GESTANTE"

        col = resolve_col(cat, lact, gest)
        if col:
            agg[col] += 1

    set_total(agg)
    return agg


# ─── Change rows (events on date D) ─────────────────────────────────────────

def count_velages(date):
    """Vêlage row: bucketed by the cow's post-vêlage state (Lact normally, Tarie if same-day tarissement)."""
    d = str(getdate(date))
    rows = frappe.db.sql("""
        SELECT l.statut, l.date_tarissement
        FROM `tabVelage` v
        LEFT JOIN `tabLactation` l ON l.animal = v.animal AND l.date_debut = v.date_velage
        WHERE v.date_velage = %s
    """, d, as_dict=True)
    row = empty_row()
    for r in rows:
        if r.statut == "TARIE" and r.date_tarissement and str(r.date_tarissement) == d:
            row["Vaches - Tarie"] += 1
        else:
            row["Vaches - Lact."] += 1
    set_total(row)
    return row


def count_naissances(date):
    d = str(getdate(date))
    rows = frappe.db.sql("""
        SELECT sexe_veau1, vivant_veau1, sexe_veau2, vivant_veau2, nombre_veaux
        FROM `tabVelage` WHERE date_velage = %s
    """, d, as_dict=True)
    result = empty_row()
    for v in rows:
        for sfx in ("1", "2"):
            if sfx == "2" and cint(v.nombre_veaux) < 2:
                continue
            sexe, vivant = v.get(f"sexe_veau{sfx}"), v.get(f"vivant_veau{sfx}")
            if not sexe:
                continue
            if vivant:
                if sexe == "M": result["Veaux"] += 1
                elif sexe == "F": result["Velles"] += 1
    set_total(result)
    return result


def count_avortements_mort_nes(date):
    d = str(getdate(date))
    avort = frappe.db.count("Avortement", {"date_avortement": d})
    mort_nes = frappe.db.sql("""
        SELECT SUM(
            CASE WHEN vivant_veau1 = 0 THEN 1 ELSE 0 END +
            CASE WHEN vivant_veau2 = 0 AND nombre_veaux = '2' THEN 1 ELSE 0 END
        ) FROM `tabVelage` WHERE date_velage = %s
    """, d)[0][0] or 0
    result = empty_row()
    result["Total"] = avort + int(mort_nes)
    return result


def count_exits(date, statut):
    """Vente / Mortalité / Réforme per category."""
    d = str(getdate(date))
    rows = frappe.db.sql("""
        SELECT categorie, etat_lactation, etat_gestation, COUNT(*) AS n, SUM(prix_vente) AS prix
        FROM `tabAnimal`
        WHERE date_sortie = %s AND statut = %s
        GROUP BY categorie, etat_lactation, etat_gestation
    """, (d, statut), as_dict=True)
    qty = empty_row()
    prix = empty_row()
    for r in rows:
        col = resolve_col(r.categorie, r.etat_lactation or "", r.etat_gestation or "")
        if col:
            qty[col] += r.n
            prix[col] += int(r.prix or 0)
    set_total(qty)
    set_total(prix)
    return qty, prix


def count_achats(date):
    d = str(getdate(date))
    rows = frappe.db.sql("""
        SELECT categorie, etat_lactation, etat_gestation, COUNT(*) AS n
        FROM `tabAnimal`
        WHERE est_achat = 1 AND date_entree = %s
        GROUP BY categorie, etat_lactation, etat_gestation
    """, d, as_dict=True)
    result = empty_row()
    for r in rows:
        col = resolve_col(r.categorie, r.etat_lactation or "", r.etat_gestation or "")
        if col:
            result[col] += r.n
    set_total(result)
    return result


def count_changements_cat(date):
    """Tarissement + IA réussie on date D, excluding vêlage-induced transitions."""
    d = str(getdate(date))
    cat_plus, cat_minus = empty_row(), empty_row()

    # Tarissement: lactation closed on D, NOT caused by a vêlage on same day
    tarissements = frappe.db.sql("""
        SELECT l.animal FROM `tabLactation` l
        WHERE l.date_tarissement = %s AND l.statut = 'TARIE'
        AND NOT EXISTS (
            SELECT 1 FROM `tabVelage` v WHERE v.animal = l.animal AND v.date_velage = %s
        )
    """, (d, d))
    cat_minus["Vaches - Lact."] += len(tarissements)
    cat_plus["Vaches - Tarie"] += len(tarissements)

    # IA réussie: insemination on D with resultat=REUSSIE
    ia_reussies = frappe.db.count("Insemination", {"date_ia": d, "resultat": "REUSSIE"})
    cat_minus["Gén. - Vide"] += ia_reussies
    cat_plus["Gén. - Pleine"] += ia_reussies

    set_total(cat_plus)
    set_total(cat_minus)
    return cat_plus, cat_minus
