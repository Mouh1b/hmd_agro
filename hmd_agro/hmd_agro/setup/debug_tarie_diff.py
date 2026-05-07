"""One-off debug script: list Tarie cohort changes between Feb 28 and Mar 31, 2026.
Run: bench --site hmd.localhost execute hmd_agro.hmd_agro.setup.debug_tarie_diff.run
"""
import frappe
from hmd_agro.hmd_agro.utils.live_state import states_on_date


def run():
    animals = [r[0] for r in frappe.db.sql(
        "SELECT name FROM `tabAnimal` WHERE categorie='VACHE'")]
    s28 = states_on_date(animals, "2026-02-28")
    s31 = states_on_date(animals, "2026-03-31")
    t28 = sorted([a for a, st in s28.items() if st[1] == "TARIE"])
    t31 = sorted([a for a, st in s31.items() if st[1] == "TARIE"])
    print(f"Tarie Feb 28 ({len(t28)}): {t28}")
    print(f"Tarie Mar 31 ({len(t31)}): {t31}")
    print(f"NEW Tarie (in Mar31 not Feb28): {sorted(set(t31) - set(t28))}")
    print(f"GONE Tarie (in Feb28 not Mar31): {sorted(set(t28) - set(t31))}")
