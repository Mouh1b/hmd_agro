"""Inspect Allotment Sessions and Traite data around 2026-04-17 to 2026-04-21."""
import frappe
from frappe.utils import getdate, add_days


def run():
    print("\n" + "=" * 78)
    print("  Inspection Allotement — autour du 20/04/2026")
    print("=" * 78)

    # 1. List all Allotment Sessions with their date
    sessions = frappe.get_all("Allotment Session",
        fields=["name", "session_date", "creation"],
        order_by="session_date desc",
        limit_page_length=20)
    print(f"\n  ── Allotment Sessions existantes ({len(sessions)}) ──")
    for s in sessions:
        print(f"     {s.name}  session_date={s.session_date}  créée le {s.creation}")

    # 2. Sessions around 17-21 April 2026
    target_dates = [getdate(f"2026-04-{d:02d}") for d in range(17, 22)]
    relevant = [s for s in sessions if s.session_date in target_dates]
    print(f"\n  ── Sessions correspondant aux dates demandées (17-21/04) ──")
    if not relevant:
        print("     Aucune session enregistrée pour ces dates.")
    for s in relevant:
        print(f"     {s.name}  session_date={s.session_date}")

    # 3. For each relevant session, show its rows
    for s in relevant:
        print(f"\n  ── Contenu session {s.name} (session_date={s.session_date}) ──")
        rows = frappe.get_all("Allotment Session Row",
            filters={"parent": s.name},
            fields=["animal", "nom_metier", "lot_before", "lot_after", "moved",
                    "production_j_2", "production_j_1", "production_j",
                    "dim", "jours_gestation"],
            order_by="nom_metier")
        for r in rows:
            tot_summary = (f"j-2={r.production_j_2 or '-'}  "
                           f"j-1={r.production_j_1 or '-'}  "
                           f"j={r.production_j or '-'}")
            mv = " → " + r.lot_after if r.moved else ""
            print(f"     {r.nom_metier:>10}  ({r.animal})  lot={r.lot_before}{mv}")
            print(f"                 {tot_summary}  dim={r.dim} gest={r.jours_gestation}")

    # 4. Independent check: actual Traite records for those 5 days
    print(f"\n  ── Données Traite réelles 17-21/04/2026 ──")
    traites = frappe.db.sql("""
        SELECT animal, date_traite, SUM(quantite_litres) AS total
        FROM `tabTraite`
        WHERE date_traite BETWEEN '2026-04-17' AND '2026-04-21'
        GROUP BY animal, date_traite
        ORDER BY date_traite, animal
    """, as_dict=True)
    by_animal_date = {}
    for t in traites:
        by_animal_date.setdefault(t.animal, {})[str(t.date_traite)] = float(t.total or 0)
    print(f"     {len(traites)} lignes (animal, date) avec traite")
    print(f"     Animaux uniques avec traites cette période: {len(by_animal_date)}")
    for animal, by_date in sorted(by_animal_date.items()):
        nom = frappe.db.get_value("Animal", animal, "nom_metier") or animal[-4:]
        print(f"     {nom:>10} ({animal}): " +
              ", ".join(f"{d}={q}" for d, q in sorted(by_date.items())))

    # 5. Cross-check: for each session, which animals had traites that DON'T appear in the session?
    if relevant:
        for s in relevant:
            print(f"\n  ── Cross-check session {s.name} ──")
            session_animals = set(frappe.db.sql_list(
                "SELECT animal FROM `tabAllotment Session Row` WHERE parent=%s", s.name))
            session_date = s.session_date
            j2 = add_days(session_date, -2)
            j1 = add_days(session_date, -1)
            print(f"     Session attend traites des dates: J-2={j2}, J-1={j1}, J={session_date}")

            # Animals with traites in (j-2, j-1, j) but NOT in session
            traite_animals = set(frappe.db.sql_list("""
                SELECT DISTINCT animal FROM `tabTraite`
                WHERE date_traite BETWEEN %s AND %s
            """, (j2, session_date)))
            missing = traite_animals - session_animals
            if missing:
                print(f"     ⚠️  {len(missing)} animaux avec traites mais ABSENTS de la session:")
                for m in sorted(missing):
                    nom = frappe.db.get_value("Animal", m, "nom_metier") or m[-4:]
                    statut = frappe.db.get_value("Animal", m, ["statut", "categorie"], as_dict=True)
                    print(f"        {nom} ({m}): statut={statut.statut}, cat={statut.categorie}")
            else:
                print(f"     ✓ Toutes les vaches avec traites sont dans la session.")

            # Animals in session with empty Tot fields
            empty_tot = frappe.db.sql("""
                SELECT animal, nom_metier, production_j_2, production_j_1, production_j
                FROM `tabAllotment Session Row`
                WHERE parent = %s
                  AND COALESCE(production_j_2, 0) = 0
                  AND COALESCE(production_j_1, 0) = 0
                  AND COALESCE(production_j, 0) = 0
            """, s.name, as_dict=True)
            if empty_tot:
                print(f"     ⚠️  {len(empty_tot)} lignes avec Tot vides — vérification croisée:")
                for r in empty_tot:
                    actual = by_animal_date.get(r.animal, {})
                    if actual:
                        print(f"        {r.nom_metier} ({r.animal}): session=tout vide, mais réelles {actual}")
                    else:
                        print(f"        {r.nom_metier} ({r.animal}): session vide ET pas de traites réelles")

    print("\n" + "=" * 78)
