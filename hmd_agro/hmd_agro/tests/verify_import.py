import frappe
import json


def run():
    d = json.loads(frappe.db.get_value(
        "Rapport Journalier Importe", {"date": "2026-01-15"}, "rapport_json"))
    cols = ["Vaches - Lact.", "Vaches - Tarie", "Gén. - Vide", "Gén. - Pleine",
            "Veaux", "Engraiss.", "Velles", "Total"]
    keys = ["effectif_initial", "changement_cat_plus", "changement_cat_minus",
            "velage", "naissance", "avortement_mort_ne", "vente_qty",
            "vente_prix", "mortalite", "effectif_final"]
    print("=== IMPORTED DB ROWS for 2026-01-15 ===")
    for k in keys:
        v = d.get(k, {})
        row = [v.get(c, 0) for c in cols]
        print(f"  {k:25s} {row}")
    print()
    print("production_lot:")
    for lot, vals in d.get("production_lot", {}).items():
        e = vals.get("effectif")
        p = vals.get("production")
        print(f"  {lot:20s} effectif={e}, production={p}")
