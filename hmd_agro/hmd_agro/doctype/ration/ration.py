# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Ration(Document):
    def validate(self):
        self.validate_unique_aliments()
        self.calculate_cout_estime()

    def validate_unique_aliments(self):
        """CF-CRA-01: No duplicate aliments in composition"""
        seen = set()
        for row in self.composition:
            if row.aliment in seen:
                frappe.throw(f"L'aliment '{row.aliment}' est deja present dans la composition.")
            seen.add(row.aliment)

    def calculate_cout_estime(self):
        """RC-RAT-01: cout_estime = SUM(quantite x prix_unitaire)"""
        total = 0
        for row in self.composition:
            prix = frappe.db.get_value("Aliment", row.aliment, "prix_unitaire") or 0
            row.sous_total = round(row.quantite * prix, 3)
            total += row.sous_total
        self.cout_estime = round(total, 3)
