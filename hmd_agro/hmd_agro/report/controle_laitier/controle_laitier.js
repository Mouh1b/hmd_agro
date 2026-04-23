frappe.query_reports["Controle Laitier"] = {
    filters: [
        {
            fieldname: "view_mode",
            label: __("Vue"),
            fieldtype: "Select",
            options: "Conversion\nCL",
            default: "Conversion",
            reqd: 1,
        },
        {
            fieldname: "reference_date",
            label: __("Date"),
            fieldtype: "Date",
            default: frappe.datetime.add_days(frappe.datetime.get_today(), -1),
            depends_on: "eval:doc.view_mode == 'Conversion'",
        },
        {
            fieldname: "from_date",
            label: __("Du"),
            fieldtype: "Date",
            default: frappe.datetime.add_days(frappe.datetime.get_today(), -7),
            depends_on: "eval:doc.view_mode == 'CL'",
        },
        {
            fieldname: "to_date",
            label: __("Au"),
            fieldtype: "Date",
            default: frappe.datetime.add_days(frappe.datetime.get_today(), -1),
            depends_on: "eval:doc.view_mode == 'CL'",
        },
        {
            fieldname: "lot",
            label: __("Lot"),
            fieldtype: "Link",
            options: "Lot",
        },
    ],

    formatter(value, row, column, data, default_formatter) {
        if (value == null || value === "") {
            return default_formatter(value, row, column, data);
        }
        if (["total", "moyenne", "moyenne_3j"].includes(column.fieldname)) {
            return `<b>${default_formatter(value, row, column, data)}</b>`;
        }
        if (column.fieldname === "delta") {
            const pct = Number(value);
            let color = "gray";
            let bold = false;
            if (pct > 0) {
                color = "green";
            } else if (pct < 0) {
                if (pct <= -30) { color = "red"; bold = true; }
                else color = "orange";
            }
            const sign = pct > 0 ? "+" : "";
            const style = `color:${color};${bold ? "font-weight:bold;" : ""}`;
            return `<span style="${style}">${sign}${pct}%</span>`;
        }
        return default_formatter(value, row, column, data);
    },

    after_datatable_render(datatable) {
        // Sticky first 2 columns (row number + nom_metier) — useful in CL wide grid.
        if (datatable.wrapper.querySelector(".sticky-col-style")) return;
        const style = document.createElement("style");
        style.className = "sticky-col-style";
        const col0Width = datatable.getColumn(0).width || 40;
        style.textContent = `
            .dt-cell--col-0, .dt-cell--header-0 {
                position: sticky !important; left: 0; z-index: 10;
                background: var(--card-bg) !important;
            }
            .dt-cell--header-0 { z-index: 11; }
            .dt-cell--col-1, .dt-cell--header-1 {
                position: sticky !important; left: ${col0Width}px; z-index: 10;
                background: var(--card-bg) !important;
            }
            .dt-cell--header-1 { z-index: 11; }
        `;
        datatable.wrapper.appendChild(style);
    },
};
