"""Run the real allotement engine and dump what it suggests for each cow."""
import frappe
from hmd_agro.hmd_agro.report.allotement_animaux.allotement_animaux import execute


def run():
    cols, data = execute()
    print(f"\n{'Nom':<6} {'Lot actuel':<14} {'Suggestion':<14} {'Différent?'}")
    print("-" * 60)
    for r in sorted(data, key=lambda x: (x.get("lot_actuel") or "", x.get("nom_metier") or "")):
        nom = r.get("nom_metier") or ""
        cur = r.get("lot_actuel") or ""
        sugg = r.get("suggestion_lot") or "(aucune)"
        diff = "OUI ←" if sugg and sugg != cur else ""
        print(f"{nom:<6} {cur:<14} {sugg:<14} {diff}")
