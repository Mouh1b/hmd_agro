frappe.query_reports["Allotement Animaux"] = {
    onload(report) {
        if (report.__allotement_actions_added) {
            return;
        }
        report.__allotement_actions_added = true;

        report.page.add_inner_button(__("Panneau Suggestions"), () => {
            if (is_past_date()) return;
            const rows = (frappe.query_report.data || []).filter((r) => r.suggestion_lot);
            if (!rows.length) {
                frappe.msgprint(__("Aucune suggestion disponible pour le moment."));
                return;
            }
            open_suggestion_dialog(report, rows);
        });

        report.page.add_inner_button(__("Mouvements Manuels"), () => {
            if (is_past_date()) return;
            const rows = (frappe.query_report.data || []).filter((r) => r.animal);
            if (!rows.length) {
                frappe.msgprint(__("Aucune ligne disponible."));
                return;
            }
            open_manual_dialog(report, rows);
        });
    },

    filters: [
        {
            fieldname: "reference_date",
            label: __("Date de reference (J)"),
            fieldtype: "Date",
            default: frappe.datetime.add_days(frappe.datetime.get_today(), -1),
            reqd: 1
        },
        {
            fieldname: "lot",
            label: __("Lot"),
            fieldtype: "Link",
            options: "Lot"
        }
    ],

    formatter(value, row, column, data, default_formatter) {
        if (value == null || value === "") {
            return default_formatter(value, row, column, data);
        }

        if (column.fieldname === "delta_j_vs_j_1") {
            const pct = Number(value);
            let color = "gray";
            if (pct > 0) {
                color = "green";
            } else if (pct < 0) {
                color = pct <= -15 ? "red" : "orange";
            }
            const sign = pct > 0 ? "+" : "";
            return `<span style="color:${color};font-weight:600">${sign}${pct}%</span>`;
        }

        if (["j_2", "j_1", "j", "moyenne_3j"].includes(column.fieldname)) {
            return `<b>${default_formatter(value, row, column, data)}</b>`;
        }

        return default_formatter(value, row, column, data);
    }
};


function is_past_date() {
    const ref = frappe.query_report.get_filter_value("reference_date");
    const yesterday = frappe.datetime.add_days(frappe.datetime.get_today(), -1);
    if (ref && ref < yesterday) {
        frappe.msgprint(__("Les actions ne sont pas disponibles pour les dates passées."));
        return true;
    }
    return false;
}


const MOVE_TABLE_FIELDS = [
    {
        fieldname: "animal",
        fieldtype: "Link",
        options: "Animal",
        label: __("Animal"),
        in_list_view: 0,
        hidden: 1
    },
    {
        fieldname: "nom_metier",
        fieldtype: "Data",
        label: __("N° Travail"),
        in_list_view: 1,
        read_only: 1,
        columns: 2
    },
    {
        fieldname: "lot_actuel",
        fieldtype: "Data",
        label: __("Lot actuel"),
        in_list_view: 1,
        read_only: 1,
        columns: 2
    },
    {
        fieldname: "lot_destination",
        fieldtype: "Link",
        options: "Lot",
        label: __("Lot destination"),
        reqd: 0,
        in_list_view: 1,
        columns: 2
    }
];


function open_suggestion_dialog(report, rows) {
    const table_data = rows.map((r) => ({
        animal: r.animal,
        nom_metier: r.nom_metier,
        lot_actuel: r.lot_actuel,
        lot_destination: r.suggestion_lot || ""
    }));

    const d = new frappe.ui.Dialog({
        title: __("Suggestions de mouvements"),
        size: "large",
        fields: [
            {
                fieldname: "help",
                fieldtype: "HTML",
                options:
                    '<div style="margin-bottom:8px;color:var(--text-muted);">' +
                    __("Cochez les animaux à déplacer, puis confirmez. Utilisez 'Appliquer lot commun' pour changer la destination des animaux sélectionnés.") +
                    "</div>"
            },
            {
                fieldname: "lot_destination_bulk",
                fieldtype: "Link",
                label: __("Lot commun"),
                options: "Lot"
            },
            {
                fieldname: "btn_apply_bulk",
                fieldtype: "Button",
                label: __("Appliquer lot commun"),
                click() {
                    const lot = d.get_value("lot_destination_bulk");
                    if (!lot) {
                        frappe.msgprint(__("Sélectionnez un lot commun."));
                        return;
                    }
                    const selected = d.fields_dict.moves.grid.get_selected_children() || [];
                    if (!selected.length) {
                        frappe.msgprint(__("Cochez les animaux à modifier."));
                        return;
                    }
                    const selectedAnimals = new Set(selected.map((r) => r.animal));
                    d.fields_dict.moves.grid.grid_rows.forEach((row) => {
                        if (selectedAnimals.has(row.doc.animal)) {
                            row.doc.lot_destination = lot;
                            row.refresh_fields();
                        }
                    });
                }
            },
            {
                fieldname: "moves",
                fieldtype: "Table",
                label: __("Mouvements"),
                cannot_add_rows: true,
                cannot_delete_rows: true,
                in_place_edit: true,
                reqd: 1,
                fields: MOVE_TABLE_FIELDS,
                data: table_data
            }
        ],
        primary_action_label: __("Confirmer transfert"),
        primary_action() {
            const selectedRows = d.fields_dict.moves.grid.get_selected_children() || [];
            if (!selectedRows.length) {
                frappe.msgprint(__("Cochez les animaux à déplacer."));
                return;
            }

            const toMove = selectedRows.filter((r) =>
                r.animal && r.lot_destination && r.lot_destination !== r.lot_actuel
            );

            if (!toMove.length) {
                frappe.msgprint(__("Aucune ligne valide parmi les sélectionnées."));
                return;
            }

            apply_moves(d, report, toMove);
        }
    });

    d.show();
}


function open_manual_dialog(report, rows) {
    const table_data = rows.map((r) => ({
        animal: r.animal,
        nom_metier: r.nom_metier,
        lot_actuel: r.lot_actuel,
        lot_destination: ""
    }));

    const d = new frappe.ui.Dialog({
        title: __("Mouvements manuels"),
        size: "large",
        fields: [
            {
                fieldname: "help",
                fieldtype: "HTML",
                options:
                    '<div style="margin-bottom:8px;color:var(--text-muted);">' +
                    __("Selectionnez les animaux, choisissez le lot destination (individuel ou lot commun), puis appliquez.") +
                    "</div>"
            },
            {
                fieldname: "lot_destination_bulk",
                fieldtype: "Link",
                label: __("Lot destination commun"),
                options: "Lot"
            },
            {
                fieldname: "moves",
                fieldtype: "Table",
                label: __("Mouvements"),
                cannot_add_rows: true,
                cannot_delete_rows: true,
                in_place_edit: true,
                reqd: 1,
                fields: MOVE_TABLE_FIELDS,
                data: table_data
            }
        ],
        primary_action_label: __("Confirmer transfert"),
        primary_action(values) {
            const moves = values.moves || [];
            const selectedRows = d.fields_dict.moves.grid.get_selected_children() || [];
            const lotCommun = d.get_value("lot_destination_bulk");

            if (lotCommun && selectedRows.length) {
                const selectedAnimals = new Set(selectedRows.map((r) => r.animal));
                moves.forEach((m) => {
                    if (selectedAnimals.has(m.animal)) {
                        m.lot_destination = lotCommun;
                    }
                });
            }

            const toMove = moves.filter((r) =>
                r.animal && r.lot_destination && r.lot_destination !== r.lot_actuel
            );

            if (!toMove.length) {
                frappe.msgprint(__("Aucune ligne valide: renseignez un lot destination différent du lot actuel."));
                return;
            }

            apply_moves(d, report, toMove);
        }
    });

    d.show();
}


function apply_moves(dialog, report, toMove) {
    dialog.disable_primary_action();
    frappe.call({
        method: "frappe.client.bulk_update",
        args: {
            docs: JSON.stringify(
                toMove.map((r) => ({
                    doctype: "Animal",
                    docname: r.animal,
                    id_lot: r.lot_destination
                }))
            )
        },
        freeze: true,
        freeze_message: __("Application des mouvements..."),
        callback(res) {
            const failed = (res.message && res.message.failed_docs) || [];
            dialog.hide();

            if (failed.length) {
                frappe.msgprint(
                    __("{0} mouvement(s) appliqué(s), {1} erreur(s).", [
                        toMove.length - failed.length,
                        failed.length
                    ])
                );
            } else {
                frappe.show_alert({
                    message: __("{0} mouvement(s) appliqué(s).", [toMove.length]),
                    indicator: "green"
                });
            }

            report.refresh();
        }
    });
}
