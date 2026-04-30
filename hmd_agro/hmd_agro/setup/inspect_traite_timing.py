"""When were the Traite records for 17-21/04/2026 actually created in the DB?"""
import frappe


def run():
    print("\n=== Traite creation pattern (when were they entered into the system?) ===")
    rows = frappe.db.sql("""
        SELECT DATE(creation) AS created_on, COUNT(*) AS n
        FROM `tabTraite`
        WHERE date_traite BETWEEN '2026-04-17' AND '2026-04-21'
        GROUP BY DATE(creation)
        ORDER BY created_on
    """, as_dict=True)
    for r in rows:
        print(f"  Traite docs créés le {r.created_on}: {r.n}")

    print("\n=== Sessions créées + leur date_session ===")
    sessions = frappe.db.sql("""
        SELECT name, session_date, creation
        FROM `tabAllotment Session`
        ORDER BY creation DESC LIMIT 12
    """, as_dict=True)
    for s in sessions:
        print(f"  {s.name}  session_date={s.session_date}  créée le {s.creation}")
