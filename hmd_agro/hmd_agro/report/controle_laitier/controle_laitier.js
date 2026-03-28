frappe.query_reports["Controle Laitier"] = {
    filters: [
        {
            fieldname: "from_date",
            label: __("Du"),
            fieldtype: "Date",
            default: frappe.datetime.add_days(frappe.datetime.get_today(), -7),
            reqd: 1
        },
        {
            fieldname: "to_date",
            label: __("Au"),
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

    after_datatable_render(datatable) {
        if (datatable.wrapper.querySelector(".sticky-col-style")) return;
        let style = document.createElement("style");
        style.className = "sticky-col-style";
        // Col 0 = row number, Col 1 = nom_metier
        let col0Width = datatable.getColumn(0).width || 40;
        style.textContent = `
            .dt-cell--col-0 {
                position: sticky !important;
                left: 0;
                z-index: 10;
                background: var(--card-bg) !important;
            }
            .dt-cell--header-0 {
                position: sticky !important;
                left: 0;
                z-index: 11;
                background: var(--card-bg) !important;
            }
            .dt-cell--col-1 {
                position: sticky !important;
                left: ${col0Width}px;
                z-index: 10;
                background: var(--card-bg) !important;
            }
            .dt-cell--header-1 {
                position: sticky !important;
                left: ${col0Width}px;
                z-index: 11;
                background: var(--card-bg) !important;
            }
        `;
        datatable.wrapper.appendChild(style);
    }
};
