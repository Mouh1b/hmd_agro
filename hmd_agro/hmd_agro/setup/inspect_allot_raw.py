"""Raw values + timing checks for Allotment session bug."""
import frappe


def run():
    print("\n=== Raw stored values for ALS-2026-04-21-00578 (first 5 rows) ===")
    rows = frappe.db.sql("""
        SELECT animal, nom_metier, production_j_2, production_j_1, production_j, dim
        FROM `tabAllotment Session Row`
        WHERE parent = 'ALS-2026-04-21-00578'
        LIMIT 5
    """, as_dict=True)
    for r in rows:
        print(f"  {r.nom_metier}: pj_2={r.production_j_2!r} pj_1={r.production_j_1!r} pj={r.production_j!r} (dim={r.dim})")

    print("\n=== Traite creation timestamps for animal 0050 (9990000050) on 17-21/04 ===")
    rows = frappe.db.sql("""
        SELECT name, date_traite, type_traite, quantite_litres, creation
        FROM `tabTraite`
        WHERE animal = '9990000050' AND date_traite BETWEEN '2026-04-17' AND '2026-04-21'
        ORDER BY date_traite, type_traite
    """, as_dict=True)
    for r in rows:
        print(f"  {r.date_traite} {r.type_traite}: {r.quantite_litres}L  (Traite créée le {r.creation})")

    print("\n=== Traite creation pattern: when were the 17-21/04 traites added? ===")
    rows = frappe.db.sql("""
        SELECT DATE(creation) AS created_on, COUNT(*) AS n
        FROM `tabTraite`
        WHERE date_traite BETWEEN '2026-04-17' AND '2026-04-21'
        GROUP BY DATE(creation)
        ORDER BY created_on
    """, as_dict=True)
    for r in rows:
        print(f"  Créées le {r.created_on}: {r.n} Traite docs")

    print("\n=== Sessions vs Traite timing (who came first?) ===")
    print("  Session ALS-2026-04-21-00578 créée le 2026-04-21 21:03:59")
    print("  → Si les Traites pour 17-21/04 ont été créées APRÈS le 21/04 21:03,")
    print("    ça explique pourquoi la session a 0 (aucune donnée à snapshotter au moment du save).")
