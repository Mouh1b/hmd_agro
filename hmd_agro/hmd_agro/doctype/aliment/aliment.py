# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Aliment(Document):
    def validate(self):
        if self.prix_unitaire is not None and self.prix_unitaire < 0:
            frappe.throw("Le prix unitaire ne peut pas etre negatif.")
