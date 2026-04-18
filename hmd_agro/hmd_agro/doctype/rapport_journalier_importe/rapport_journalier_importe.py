import frappe
from frappe.model.document import Document


class RapportJournalierImporte(Document):
    pass


@frappe.whitelist()
def import_file(file_url, annee, mois):
    """Parse an uploaded Rapport Mensuel workbook and write one row per daily sheet."""
    from hmd_agro.hmd_agro.utils.import_rapport import import_workbook
    return import_workbook(file_url, annee, mois)
