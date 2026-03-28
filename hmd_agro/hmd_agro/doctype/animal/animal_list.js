frappe.listview_settings["Animal"] = {
    hide_name_column: true,

    formatters: {
        nom_metier: function(value, df, doc) {
            if (!value && doc.name) {
                value = doc.name.slice(-4);
            }
            return value || "";
        }
    },

    onload: function(listview) {
        listview.page.add_action_item(__("Changer de Lot"), function() {
            var selected = listview.get_checked_items();
            if (!selected.length) {
                frappe.msgprint("Veuillez selectionner au moins un animal.");
                return;
            }

            var d = new frappe.ui.Dialog({
                title: "Changer de Lot — " + selected.length + " animal(aux)",
                fields: [
                    {
                        fieldname: "lot",
                        fieldtype: "Link",
                        label: "Nouveau Lot",
                        options: "Lot",
                        reqd: 1
                    }
                ],
                primary_action_label: "Appliquer",
                primary_action: function(values) {
                    d.disable_primary_action();
                    frappe.call({
                        method: "frappe.client.bulk_update",
                        args: {
                            docs: JSON.stringify(selected.map(function(item) {
                                return { doctype: "Animal", docname: item.name, id_lot: values.lot };
                            }))
                        },
                        callback: function(r) {
                            d.hide();
                            if (r.message && r.message.failed_docs && r.message.failed_docs.length) {
                                frappe.msgprint(r.message.failed_docs.length + " erreur(s) lors du changement.");
                            } else {
                                frappe.show_alert({
                                    message: selected.length + " animal(aux) deplace(s) vers " + values.lot,
                                    indicator: "green"
                                });
                            }
                            listview.clear_checked_items();
                            listview.refresh();
                        }
                    });
                }
            });
            d.show();
        });
    }
};