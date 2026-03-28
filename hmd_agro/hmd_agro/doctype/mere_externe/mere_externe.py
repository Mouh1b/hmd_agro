# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import re
import frappe
from frappe.model.document import Document


class Mereexterne(Document):
    def validate(self):
        self.validate_identification_fr()
        self.validate_production()

    def validate_identification_fr(self):
        """Same format as Animal: 10 digits"""
        if self.identification_fr:
            if not re.match(r'^\d{10}$', self.identification_fr):
                frappe.throw("L'identification FR doit être 10 chiffres (ex: 1234567890).")

    def validate_production(self):
        """Production values must be positive"""
        for field in ["production_l1", "production_l2", "production_l3", "meilleure_lactation"]:
            val = self.get(field)
            if val is not None and val < 0:
                label = self.meta.get_field(field).label
                frappe.throw(f"{label} ne peut pas être négative.")
