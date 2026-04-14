frappe.query_reports["Rapport Mensuel"] = {
    filters: [
        {
            fieldname: "mois",
            label: __("Mois"),
            fieldtype: "Select",
            options: "Janvier\nFévrier\nMars\nAvril\nMai\nJuin\nJuillet\nAoût\nSeptembre\nOctobre\nNovembre\nDécembre",
            default: (() => {
                const m = new Date().getMonth(); // 0-11
                const names = ["Janvier","Février","Mars","Avril","Mai","Juin","Juillet","Août","Septembre","Octobre","Novembre","Décembre"];
                return names[m === 0 ? 11 : m - 1]; // previous month
            })(),
            reqd: 1
        },
        {
            fieldname: "annee",
            label: __("Année"),
            fieldtype: "Int",
            default: new Date().getFullYear(),
            reqd: 1
        },
        {
            fieldname: "jour",
            label: __("Jour"),
            fieldtype: "Int",
            description: "Laisser vide pour le mois entier"
        },
        {
            fieldname: "section",
            label: __("Section"),
            fieldtype: "Select",
            options: "Tout\nEffectif\nProduction\nProduction par Lot\nAlimentation\nIndicateurs",
            default: "Tout"
        }
    ],

    formatter(value, row, column, data, default_formatter) {
        if (value == null || value === "") {
            return default_formatter(value, row, column, data);
        }

        // Bold TOTAL and section header rows
        if (data && (data.is_total || data.is_header)) {
            return `<b>${default_formatter(value, row, column, data)}</b>`;
        }

        return default_formatter(value, row, column, data);
    }
};
