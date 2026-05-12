# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Medicament(Document):
    def validate(self):
        if self.stock_actuel is not None and self.stock_actuel < 0:
            frappe.msgprint(
                f"Attention: Le stock de {self.nom_medicament} est négatif ({self.stock_actuel}). "
                f"Veuillez vérifier l'inventaire.",
                indicator="orange",
                alert=True
            )

    def after_insert(self):
        """Auto-create the matching ERPNext Item and link it. Without this hook,
        new Médicaments created via the UI wouldn't get an Item, breaking the
        Stock Entry dual-write path in Traitement and any future Phase B reports
        that aggregate from the Stock Ledger."""
        if not self.item:
            from hmd_agro.hmd_agro.setup.medicament_migration import _migrate_one_medicament
            _migrate_one_medicament(self)
        if self.reorder_level:
            from hmd_agro.hmd_agro.utils.reorder_sync import sync_reorder_level
            sync_reorder_level("Medicament", self.name)

    def on_update(self):
        """Sync reorder_level into Item.reorder_levels so ERPNext's native
        reorder_item scheduler can auto-create Material Requests when stock
        falls below threshold. Skipped on inserts (after_insert handles those)."""
        if self.is_new() or not self.has_value_changed("reorder_level"):
            return
        from hmd_agro.hmd_agro.utils.reorder_sync import sync_reorder_level
        sync_reorder_level("Medicament", self.name)
