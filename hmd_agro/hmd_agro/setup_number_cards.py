"""
Create Number Card and Dashboard Chart documents for the HMD AGRO workspace.
Run: bench execute hmd_agro.hmd_agro.setup_number_cards.create_number_cards
"""
import frappe
import json


def create_number_cards():
    cards = [
        {
            "name": "Animaux Actifs",
            "label": "Animaux Actifs",
            "document_type": "Animal",
            "filters_json": '[["Animal", "statut", "=", "ACTIF"]]',
            "function": "Count",
            "color": "#2490EF",
            "show_percentage_stats": 0,
            "is_standard": 1,
            "module": "HMD AGRO"
        },
        {
            "name": "Alertes en Attente",
            "label": "Alertes en Attente",
            "document_type": "Alerte",
            "filters_json": '[["Alerte", "statut", "=", "NOUVELLE"]]',
            "function": "Count",
            "color": "#E24C4C",
            "show_percentage_stats": 0,
            "is_standard": 1,
            "module": "HMD AGRO"
        },
        {
            "name": "Lactations en Cours",
            "label": "Lactations en Cours",
            "document_type": "Lactation",
            "filters_json": '[["Lactation", "statut", "=", "EN_COURS"]]',
            "function": "Count",
            "color": "#48BB74",
            "show_percentage_stats": 0,
            "is_standard": 1,
            "module": "HMD AGRO"
        },
        {
            "name": "Attente Lait",
            "label": "Attente Lait",
            "document_type": "Animal",
            "filters_json": '[["Animal", "attente_lait_active", "=", 1]]',
            "function": "Count",
            "color": "#ED8936",
            "show_percentage_stats": 0,
            "is_standard": 1,
            "module": "HMD AGRO"
        },
        {
            "name": "Gestantes",
            "label": "Gestantes",
            "document_type": "Animal",
            "filters_json": '[["Animal", "etat_gestation", "=", "GESTANTE"], ["Animal", "statut", "=", "ACTIF"]]',
            "function": "Count",
            "color": "#9F7AEA",
            "show_percentage_stats": 0,
            "is_standard": 1,
            "module": "HMD AGRO"
        },
        {
            "name": "Production Aujourd'hui",
            "label": "Production Aujourd'hui (L)",
            "document_type": "Traite",
            "filters_json": json.dumps([["Traite", "date_traite", "=", "Today"]]),
            "function": "Sum",
            "aggregate_function_based_on": "quantite_litres",
            "color": "#4299E1",
            "show_percentage_stats": 0,
            "is_standard": 1,
            "module": "HMD AGRO"
        }
    ]

    for card_data in cards:
        if frappe.db.exists("Number Card", card_data["name"]):
            print(f"  Already exists: {card_data['name']}")
            continue

        doc = frappe.get_doc({
            "doctype": "Number Card",
            "type": "Document Type",
            **card_data
        })
        doc.insert(ignore_permissions=True)
        print(f"  Created: {card_data['name']}")

    # Dashboard Charts
    charts = [
        {
            "name": "Production Lait Journaliere",
            "chart_name": "Production Lait Journaliere",
            "chart_type": "Sum",
            "document_type": "Traite",
            "based_on": "date_traite",
            "value_based_on": "quantite_litres",
            "timespan": "Last Month",
            "time_interval": "Daily",
            "timeseries": 1,
            "type": "Bar",
            "color": "#4299E1",
            "filters_json": "[]",
            "is_public": 1,
            "is_standard": 1,
            "module": "HMD AGRO"
        }
    ]

    for chart_data in charts:
        if frappe.db.exists("Dashboard Chart", chart_data["name"]):
            print(f"  Chart already exists: {chart_data['name']}")
            continue

        doc = frappe.get_doc({
            "doctype": "Dashboard Chart",
            **chart_data
        })
        doc.insert(ignore_permissions=True)
        print(f"  Chart created: {chart_data['name']}")

    frappe.db.commit()
    print("\nSetup complete.")
