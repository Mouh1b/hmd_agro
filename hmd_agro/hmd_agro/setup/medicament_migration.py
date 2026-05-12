"""
Sprint 5 — Phase A — Step 2: Médicament → Item migration.

For each existing Medicament:
  1. Create an ERPNext Item (item_code = MED-{nom_medicament})
  2. Create an opening Stock Entry (Material Receipt) into Magasin Principal
     for the current `stock_actuel` quantity (skipped if 0)
  3. Set Medicament.item = the new Item

Idempotent: re-running skips Médicaments that already have `item` set.

Run:
    bench --site hmd.localhost execute \\
        hmd_agro.hmd_agro.setup.medicament_migration.migrate_medicaments
"""
import frappe
from frappe.utils import today

COMPANY = "hmd-agro"
WAREHOUSE = "Magasin Principal - HMD"
DEFAULT_UOM = "Unit"

# Medicament.type_medicament → Item Group name
TYPE_TO_ITEM_GROUP = {
    "ANTIBIOTIQUE": "Antibiotique",
    "ANTI_INFLAMMATOIRE": "Anti-inflammatoire",
    "ANTIPARASITAIRE": "Antiparasitaire",
    "VACCIN": "Vaccin",
    "HORMONE": "Hormone",
    "VITAMINE": "Vitamine",
    "AUTRE": "Autre Médicament",
}


def _migrate_one_medicament(med, verbose=False):
    """Per-record migration: ensure Item exists + link Medicament.item to it.
    Creates an opening Stock Entry only when called with stock_actuel > 0
    (existing records during bulk migration). Returns a dict of action flags.

    Used by both:
      - migrate_medicaments() bulk runner (existing records)
      - Medicament.after_insert() hook (newly created records)
    """
    if med.get("item"):
        if verbose:
            print(f"  [skip]      {med.nom_medicament} (déjà migré → {med.item})")
        return {"skipped_already_migrated": 1}

    item_code = f"MED-{med.nom_medicament}"
    item_group = TYPE_TO_ITEM_GROUP.get(med.type_medicament, "Médicament")
    actions = {"created_item": 0, "created_opening": 0,
               "linked": 0, "skipped_existing_item": 0}

    if frappe.db.exists("Item", item_code):
        if verbose:
            print(f"  [link]      {med.nom_medicament} → Item {item_code} déjà existant, lien seulement")
        actions["skipped_existing_item"] = 1
    else:
        item = frappe.get_doc({
            "doctype": "Item",
            "item_code": item_code,
            "item_name": med.nom_medicament,
            "item_group": item_group,
            "stock_uom": DEFAULT_UOM,
            "is_stock_item": 1,
            "include_item_in_manufacturing": 0,
            "description": f"Médicament migré depuis HMD Agro (type: {med.type_medicament})",
        })
        item.insert(ignore_permissions=True)
        if verbose:
            print(f"  [create]    Item {item_code} (groupe: {item_group})")
        actions["created_item"] = 1

    stock_actuel = med.get("stock_actuel") or 0
    if stock_actuel > 0:
        se = frappe.get_doc({
            "doctype": "Stock Entry",
            "stock_entry_type": "Material Receipt",
            "company": COMPANY,
            "posting_date": today(),
            "items": [{
                "item_code": item_code,
                "qty": stock_actuel,
                "uom": DEFAULT_UOM,
                "stock_uom": DEFAULT_UOM,
                "conversion_factor": 1,
                "t_warehouse": WAREHOUSE,
                "basic_rate": 0,
                "allow_zero_valuation_rate": 1,
            }],
            "remarks": f"Stock d'ouverture migration (Médicament {med.name})",
        })
        se.insert(ignore_permissions=True)
        se.submit()
        if verbose:
            print(f"              ↳ Stock d'ouverture: {stock_actuel} unités → {WAREHOUSE}")
        actions["created_opening"] = 1
    elif verbose:
        print(f"              ↳ Stock = 0, pas de Stock Entry d'ouverture")

    frappe.db.set_value("Medicament", med.name, "item", item_code)
    actions["linked"] = 1
    return actions


@frappe.whitelist()
def migrate_medicaments():
    """Create Items + opening Stock Entries for all Médicaments not yet migrated."""
    print("\n" + "=" * 60)
    print("  Sprint 5 — Médicament → Item Migration")
    print("=" * 60)

    if not frappe.db.exists("Warehouse", WAREHOUSE):
        frappe.throw(f"Warehouse '{WAREHOUSE}' n'existe pas. Lancez stock_foundation d'abord.")

    medicaments = frappe.get_all("Medicament",
        fields=["name", "nom_medicament", "type_medicament", "stock_actuel", "item"],
        order_by="nom_medicament")

    print(f"\n  Médicaments trouvés: {len(medicaments)}\n")

    stats = {"created_item": 0, "created_opening": 0, "linked": 0,
             "skipped_already_migrated": 0, "skipped_existing_item": 0}

    for med in medicaments:
        actions = _migrate_one_medicament(med, verbose=True)
        for k, v in actions.items():
            stats[k] = stats.get(k, 0) + v

    frappe.db.commit()

    print("\n" + "=" * 60)
    print(f"  Items créés:               {stats['created_item']}")
    print(f"  Stock d'ouverture créés:   {stats['created_opening']}")
    print(f"  Médicaments liés:          {stats['linked']}")
    print(f"  Déjà migrés (skip):        {stats['skipped_already_migrated']}")
    print(f"  Item existant (lien seul): {stats['skipped_existing_item']}")
    print("=" * 60 + "\n")

    return stats
