# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Semence(Document):
    def validate(self):
        if self.quantite_restante > self.quantite_recue:
            frappe.throw("La quantité restante ne peut pas dépasser la quantité reçue.")

        if self.quantite_restante < 0:
            frappe.throw("La quantité restante ne peut pas être négative.")

        if self.date_expiration and self.date_reception:
            if self.date_expiration < self.date_reception:
                frappe.throw("La date d'expiration ne peut pas être antérieure à la date de réception.")

    def before_save(self):
        if self.is_new() and not self.quantite_restante:
            self.quantite_restante = self.quantite_recue

    def after_insert(self):
        """Auto-create the matching ERPNext Item (one per Taureau×type) and a
        Batch (per Semence record), then post an opening Stock Entry for
        quantite_restante. Without this hook, new Semence records wouldn't
        appear in the Stock Ledger and Insémination's dual-write would have
        nowhere to post the consumption."""
        if self.item:
            return
        from hmd_agro.hmd_agro.setup.semence_migration import _migrate_one_semence
        _migrate_one_semence(self)