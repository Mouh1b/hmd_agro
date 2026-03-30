frappe.ui.form.on("Ration", {
    refresh(frm) {
        frm.fields_dict.composition.grid.get_field("aliment").get_query = function() {
            return {};
        };
    }
});

frappe.ui.form.on("Composition Ration", {
    aliment(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.aliment) {
            frappe.db.get_value("Aliment", row.aliment, ["prix_unitaire", "unite"], function(r) {
                if (r) {
                    frappe.model.set_value(cdt, cdn, "unite", r.unite);
                    let sous_total = (row.quantite || 0) * (r.prix_unitaire || 0);
                    frappe.model.set_value(cdt, cdn, "sous_total", sous_total);
                    calculate_cout_estime(frm);
                }
            });
        }
    },

    quantite(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.aliment) {
            frappe.db.get_value("Aliment", row.aliment, "prix_unitaire", function(r) {
                if (r) {
                    let sous_total = (row.quantite || 0) * (r.prix_unitaire || 0);
                    frappe.model.set_value(cdt, cdn, "sous_total", sous_total);
                    calculate_cout_estime(frm);
                }
            });
        }
    },

    composition_remove(frm) {
        calculate_cout_estime(frm);
    }
});

function calculate_cout_estime(frm) {
    let total = 0;
    (frm.doc.composition || []).forEach(function(row) {
        total += row.sous_total || 0;
    });
    frm.set_value("cout_estime", total);
}
