frappe.query_reports["Allotement Animaux"] = {
    onload(report) {
        if (report.__allotement_actions_added) {
            return;
        }
        report.__allotement_actions_added = true;

        report.page.add_inner_button(__("Panneau Suggestions"), () => {
            if (is_session_mode(report)) return;
            const rows = (frappe.query_report.data || []).filter((r) => r.suggestion_lot);
            if (!rows.length) {
                frappe.msgprint(__("Aucune suggestion disponible pour le moment."));
                return;
            }
            open_suggestion_dialog(report, rows);
        });

        report.page.add_inner_button(__("Mouvements Manuels"), () => {
            if (is_session_mode(report)) return;
            const rows = (frappe.query_report.data || []).filter((r) => r.animal);
            if (!rows.length) {
                frappe.msgprint(__("Aucune ligne disponible."));
                return;
            }
            open_manual_dialog(report, rows);
        });

        report.page.add_inner_button(__("Historique"), () => open_history_dialog(report));

        report.page.add_inner_button(__("Live"), () => {
            report.set_filter_value("session", "");
            report.set_filter_value("today_display", frappe.datetime.get_today());
            report.refresh();
        }).hide();

        // Toggle Live button visibility based on whether a session is selected.
        const refreshLiveBtn = () => {
            const btn = report.page.inner_toolbar.find('.btn:contains("Live")');
            is_session_mode(report) ? btn.show() : btn.hide();
        };
        const origRefresh = report.refresh.bind(report);
        report.refresh = function () {
            const r = origRefresh();
            setTimeout(refreshLiveBtn, 100);
            return r;
        };
    },

    filters: [
        {
            fieldname: "today_display",
            label: __("Aujourd'hui"),
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            read_only: 1
        },
        {
            fieldname: "lot",
            label: __("Lot"),
            fieldtype: "Link",
            options: "Lot"
        },
        {
            fieldname: "session",
            label: __("Session"),
            fieldtype: "Link",
            options: "Allotment Session",
            hidden: 1
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


function is_session_mode(report) {
    return !!report.get_filter_value("session");
}


function open_history_dialog(report) {
    frappe.call({
        method: "hmd_agro.hmd_agro.doctype.allotment_session.allotment_session.list_sessions",
        args: { limit: 50 },
        callback(r) {
            const sessions = r.message || [];
            if (!sessions.length) {
                frappe.msgprint(__("Aucune session enregistrée pour le moment."));
                return;
            }
            const html = `
                <table style="width:100%;font-size:13px;border-collapse:collapse;">
                  <thead>
                    <tr style="border-bottom:1px solid var(--border-color);">
                      <th style="padding:6px;text-align:left;">Date</th>
                      <th style="padding:6px;text-align:left;">Mouvements</th>
                      <th style="padding:6px;text-align:left;">Créée par</th>
                      <th style="padding:6px;text-align:left;">Notes</th>
                      <th style="padding:6px;"></th>
                    </tr>
                  </thead>
                  <tbody>
                  ${sessions.map((s) => `
                    <tr style="border-bottom:1px solid var(--light-border-color);">
                      <td style="padding:6px;">${s.session_date}</td>
                      <td style="padding:6px;">${s.moves_count}</td>
                      <td style="padding:6px;">${s.created_by || ""}</td>
                      <td style="padding:6px;color:var(--text-muted);">${s.notes || ""}</td>
                      <td style="padding:6px;text-align:right;">
                        <button class="btn btn-xs btn-default" data-session="${s.name}" data-date="${s.session_date}">${__("Voir")}</button>
                      </td>
                    </tr>`).join("")}
                  </tbody>
                </table>`;

            const d = new frappe.ui.Dialog({
                title: __("Historique des sessions"),
                size: "large",
                fields: [{ fieldname: "list", fieldtype: "HTML", options: html }]
            });
            d.show();
            d.$wrapper.find("button[data-session]").on("click", function () {
                const name = $(this).data("session");
                const date = $(this).data("date");
                d.hide();
                report.set_filter_value("session", name);
                report.set_filter_value("today_display", date);
                report.refresh();
            });
        }
    });
}


const MOVE_TABLE_FIELDS = [
    { fieldname: "animal", fieldtype: "Link", options: "Animal", label: __("Animal"), hidden: 1 },
    { fieldname: "nom_metier", fieldtype: "Data", label: __("N° Travail"),
      in_list_view: 1, read_only: 1, columns: 2 },
    { fieldname: "lot_actuel", fieldtype: "Data", label: __("Lot actuel"),
      in_list_view: 1, read_only: 1, columns: 2 },
    { fieldname: "lot_destination", fieldtype: "Link", options: "Lot",
      label: __("Lot destination"), in_list_view: 1, columns: 2 }
];


function open_suggestion_dialog(report, rows) {
    const table_data = rows.map((r) => ({
        animal: r.animal,
        nom_metier: r.nom_metier,
        lot_actuel: r.lot_actuel,
        lot_destination: r.suggestion_lot || ""
    }));
    _open_moves_dialog(report, {
        title: __("Suggestions de mouvements"),
        help: __("Cochez les animaux à déplacer, puis confirmez. Utilisez 'Appliquer lot commun' pour changer la destination des animaux cochés."),
        table_data
    });
}


function open_manual_dialog(report, rows) {
    const table_data = rows.map((r) => ({
        animal: r.animal,
        nom_metier: r.nom_metier,
        lot_actuel: r.lot_actuel,
        lot_destination: ""
    }));
    _open_moves_dialog(report, {
        title: __("Mouvements manuels"),
        help: __("Renseignez le lot destination (manuellement ou via 'Appliquer lot commun' sur les animaux cochés), cochez les lignes à déplacer, puis confirmez."),
        table_data
    });
}


function _open_moves_dialog(report, { title, help, table_data }) {
    frappe.call({
        method: "hmd_agro.hmd_agro.report.allotement_animaux.allotement_animaux.get_lots_capacity",
        callback(r) {
            const lots = r.message || [];
            _build_moves_dialog(report, { title, help, table_data, lots });
        }
    });
}


function _build_moves_dialog(report, { title, help, table_data, lots }) {
    const d = new frappe.ui.Dialog({
        title,
        size: "extra-large",
        fields: [
            { fieldname: "capacity_preview", fieldtype: "HTML",
              options: render_capacity_table(lots, new Map()) },
            { fieldname: "btn_refresh", fieldtype: "Button",
              label: __("Actualiser capacité"),
              click() { refresh_capacity(d, lots); } },
            { fieldname: "help", fieldtype: "HTML",
              options: `<div style="margin:8px 0;color:var(--text-muted);font-size:13px;">${help}</div>` },
            { fieldname: "lot_destination_bulk", fieldtype: "Link",
              label: __("Lot commun"), options: "Lot" },
            { fieldname: "btn_apply_bulk", fieldtype: "Button",
              label: __("Appliquer lot commun"),
              click() { apply_common_lot(d, lots); } },
            { fieldname: "moves", fieldtype: "Table",
              label: __("Mouvements"),
              cannot_add_rows: true, cannot_delete_rows: true, in_place_edit: true, reqd: 1,
              fields: MOVE_TABLE_FIELDS, data: table_data }
        ],
        primary_action_label: __("Confirmer transfert"),
        primary_action() { confirm_transfer(d, report); }
    });
    d.show();
}


function apply_common_lot(d, lots) {
    const lot = d.get_value("lot_destination_bulk");
    if (!lot) { frappe.msgprint(__("Sélectionnez un lot commun.")); return; }
    const checked = checked_rows(d);
    if (!checked.length) { frappe.msgprint(__("Cochez les animaux à modifier.")); return; }
    const names = new Set(checked.map((doc) => doc.animal));
    d.fields_dict.moves.grid.grid_rows.forEach((row) => {
        if (names.has(row.doc.animal)) {
            row.doc.lot_destination = lot;
            row.refresh_field("lot_destination");
        }
    });
    refresh_capacity(d, lots);
}


function confirm_transfer(d, report) {
    const toMove = checked_rows(d).filter((doc) =>
        doc.lot_destination && doc.lot_destination !== doc.lot_actuel
    );
    if (!toMove.length) {
        frappe.msgprint(__("Cochez des animaux avec un lot destination différent de leur lot actuel."));
        return;
    }
    apply_moves(d, report, toMove);
}


function checked_rows(d) {
    // Force-commit any in-flight cell edit (e.g. user picked a value but hasn't blurred),
    // then use Frappe's built-in selection API. Single source of truth.
    if (document.activeElement) document.activeElement.blur();
    return d.fields_dict.moves.grid.get_selected_children() || [];
}


function compute_pending_deltas(d) {
    const deltas = new Map();
    checked_rows(d).forEach((doc) => {
        const dest = doc.lot_destination;
        const cur = doc.lot_actuel;
        if (!dest || dest === cur) return;
        if (cur) deltas.set(cur, (deltas.get(cur) || 0) - 1);
        deltas.set(dest, (deltas.get(dest) || 0) + 1);
    });
    return deltas;
}


function refresh_capacity(d, lots) {
    const deltas = compute_pending_deltas(d);
    const html = render_capacity_table(lots, deltas);
    d.fields_dict.capacity_preview.$wrapper.html(html);
}


function render_capacity_table(lots, deltas) {
    if (!lots.length) {
        return '<div style="color:var(--text-muted);font-size:13px;">Aucun lot actif.</div>';
    }
    const cellStyle = "padding:5px 8px;border:1px solid var(--border-color);text-align:center;font-size:12px;white-space:nowrap;";
    const headerStyle = cellStyle + "background:var(--fg-color);font-weight:600;";
    const rowLabel = "padding:5px 8px;border:1px solid var(--border-color);font-size:12px;font-weight:600;background:var(--fg-color);text-align:left;";

    const headerCells = lots.map((l) => {
        const label = l.name + (l.lot_type ? `<br><span style="font-size:10px;color:var(--text-muted);">${l.lot_type}</span>` : "");
        return `<th style="${headerStyle}">${label}</th>`;
    }).join("");

    const effectifCells = lots.map((l) => {
        const delta = deltas.get(l.name) || 0;
        const after = (l.nb_animaux || 0) + delta;
        const opt = l.capacite_optimale || 0;
        const max = l.capacite_maximale || 0;
        let color = "";
        if (max && after > max) color = "background:#fee;color:#c00;font-weight:600;";
        else if (opt && after > opt) color = "background:#ffe;color:#c80;font-weight:600;";
        const arrow = delta !== 0 ? `<span style="color:var(--text-muted);"> (${delta > 0 ? "+" : ""}${delta})</span>` : "";
        return `<td style="${cellStyle}${color}">${after}${arrow}</td>`;
    }).join("");

    const capacityCells = lots.map((l) => {
        const opt = l.capacite_optimale || 0;
        const max = l.capacite_maximale || 0;
        return `<td style="${cellStyle}">${opt} / ${max}</td>`;
    }).join("");

    const hpCells = lots.map((l) => {
        const flag = l.adapte_hautes_performances
            ? '<span style="color:#080;">✓</span>'
            : '<span style="color:#aaa;">✗</span>';
        return `<td style="${cellStyle}">${flag}</td>`;
    }).join("");

    return `
        <div style="overflow-x:auto;margin-bottom:6px;">
        <table style="border-collapse:collapse;width:100%;">
          <thead><tr><th style="${headerStyle}"></th>${headerCells}</tr></thead>
          <tbody>
            <tr><td style="${rowLabel}">Effectif</td>${effectifCells}</tr>
            <tr><td style="${rowLabel}">Capacité (opt / max)</td>${capacityCells}</tr>
            <tr><td style="${rowLabel}">Hautes perf.</td>${hpCells}</tr>
          </tbody>
        </table>
        </div>`;
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
            const failedNames = new Set(failed.map((f) => f.name || f.docname));
            const succeeded = toMove.filter((r) => !failedNames.has(r.animal));

            // Build the snapshot from the report's full grid + the moves we just applied.
            // Session dates itself to today — the moment the decision was committed.
            const sessionDate = frappe.datetime.get_today();
            const allRows = (frappe.query_report.data || []).filter((r) => r.animal);
            const movedMap = new Map(succeeded.map((r) => [r.animal, r.lot_destination]));
            const snapshot = allRows.map((r) => ({
                animal: r.animal,
                nom_metier: r.nom_metier,
                lot_before: r.lot_actuel,
                lot_after: movedMap.get(r.animal) || r.lot_actuel,
                dim: r.dim,
                jours_gestation: r.jours_gestation,
                production_j_2: r.j_2,
                production_j_1: r.j_1,
                production_j: r.j,
                delta: r.delta_j_vs_j_1,
                moyenne_3j: r.moyenne_3j,
                suggestion: r.suggestion_lot
            }));

            frappe.call({
                method: "hmd_agro.hmd_agro.doctype.allotment_session.allotment_session.confirm_session",
                args: {
                    session_date: sessionDate,
                    rows: JSON.stringify(snapshot)
                },
                callback() {
                    dialog.hide();
                    if (failed.length) {
                        frappe.msgprint(
                            __("{0} mouvement(s) appliqué(s), {1} erreur(s). Session enregistrée.",
                                [succeeded.length, failed.length])
                        );
                    } else {
                        frappe.show_alert({
                            message: __("{0} mouvement(s) appliqué(s). Session enregistrée.",
                                [succeeded.length]),
                            indicator: "green"
                        });
                    }
                    report.refresh();
                }
            });
        }
    });
}
