import frappe
import json
from frappe.model.document import Document
from frappe.utils import today, getdate


class SnapshotMensuel(Document):
    pass


SNAP_CATEGORIES = {
    "vaches_lactantes": {"categorie": "VACHE", "statut": "ACTIF", "etat_lactation": "EN_PRODUCTION"},
    "vaches_taries": {"categorie": "VACHE", "statut": "ACTIF", "etat_lactation": "TARIE"},
    "genisses_vides": {"categorie": "GENISSE", "statut": "ACTIF", "etat_gestation": "VIDE"},
    "genisses_pleines": {"categorie": "GENISSE", "statut": "ACTIF", "etat_gestation": "GESTANTE"},
    "veaux": {"categorie": "VEAU", "statut": "ACTIF"},
    "engraissement": {"categorie": "TAURILLON", "statut": "ACTIF"},
    "velles": {"categorie": "VELLE", "statut": "ACTIF"},
}

def take_snapshot():
    """Scheduled daily: save effectif count for today."""
    date = today()
    if frappe.db.exists("Snapshot Mensuel", {"date_snapshot": date}):
        return

    now = getdate(date)
    data = {key: frappe.db.count("Animal", filters) for key, filters in SNAP_CATEGORIES.items()}
    data["total"] = sum(data.values())

    doc = frappe.get_doc({
        "doctype": "Snapshot Mensuel",
        "annee": now.year,
        "mois": now.month,
        "date_snapshot": date,
        "data": json.dumps(data),
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
