frappe.query_reports["Statistiques IA Mensuelles"] = {
    filters: [
        {
            fieldname: "annee",
            label: __("Année"),
            fieldtype: "Int",
            default: new Date().getFullYear(),
            reqd: 1
        }
    ],

    formatter(value, row, column, data, default_formatter) {
        if (value == null || value === "") {
            return default_formatter(value, row, column, data);
        }

        // Bold TOTAL row
        if (data && data.mois === "TOTAL") {
            return `<b>${default_formatter(value, row, column, data)}</b>`;
        }

        // Color coding for % réussite columns
        const reussite_cols = [
            "pct_reussite_ia1", "pct_reussite_ia2", "pct_reussite_ia3",
            "pct_reussite_ia_sup", "pct_reussite_global"
        ];
        if (reussite_cols.includes(column.fieldname)) {
            const pct = Number(value);
            let color = "gray";
            if (pct >= 50) color = "green";
            else if (pct >= 40) color = "orange";
            else if (pct > 0) color = "red";
            return `<span style="color:${color};font-weight:600">${default_formatter(value, row, column, data)}</span>`;
        }

        // Color coding for % perte (inverse: low=good)
        const perte_cols = ["pct_perte_velles", "pct_perte_veaux"];
        if (perte_cols.includes(column.fieldname)) {
            const pct = Number(value);
            let color = "gray";
            if (pct === 0) color = "green";
            else if (pct <= 10) color = "orange";
            else if (pct > 10) color = "red";
            return `<span style="color:${color};font-weight:600">${default_formatter(value, row, column, data)}</span>`;
        }

        return default_formatter(value, row, column, data);
    }
};
