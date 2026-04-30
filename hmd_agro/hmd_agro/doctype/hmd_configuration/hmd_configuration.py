# Copyright (c) 2026, Mouhib Bouzamita and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class HMDConfiguration(Document):
    def validate(self):
        self.validate_dim_monotonicity()

    def validate_dim_monotonicity(self):
        """DIM stage boundaries must be strictly increasing.
        Otherwise the allotement engine misclassifies cows."""
        boundaries = [
            ("dim_fv_max_multi", self.dim_fv_max_multi),
            ("dim_thp_max", self.dim_thp_max),
            ("dim_hp_max", self.dim_hp_max),
            ("dim_mp_max", self.dim_mp_max),
        ]
        for i in range(1, len(boundaries)):
            prev_name, prev_val = boundaries[i - 1]
            cur_name, cur_val = boundaries[i]
            if cur_val is None or prev_val is None:
                continue
            if cur_val <= prev_val:
                frappe.throw(
                    f"Les bornes DIM doivent être strictement croissantes : "
                    f"{cur_name} ({cur_val}) doit être > {prev_name} ({prev_val})."
                )
        if self.dim_primipare_cap and self.dim_mp_max and self.dim_primipare_cap > self.dim_mp_max:
            frappe.throw(
                f"Le cap primipare ({self.dim_primipare_cap}) ne peut pas dépasser "
                f"le DIM max MP ({self.dim_mp_max})."
            )
