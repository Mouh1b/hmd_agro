"""Verify Step 4: Aliment → Item migration consistency."""
import frappe

TYPE_TO_ITEM_GROUP = {
    "CONCENTRE": "Concentré", "FOURRAGE": "Fourrage", "MINERAL": "Minéral",
    "ENSILAGE": "Ensilage", "PAILLE": "Paille", "SUPPLEMENT": "Supplément",
}
UNITE_TO_UOM = {"KG": "Kg", "GRAMME": "Gram"}


def run():
    print("\n" + "=" * 70)
    print("  Verification Step 4 — Aliment → Item migration")
    print("=" * 70)

    aliments = frappe.get_all("Aliment",
        fields=["name", "nom_aliment", "type_aliment", "unite",
                "prix_unitaire", "ms_pct", "item"],
        order_by="nom_aliment")

    print(f"\n  Aliments dans le système: {len(aliments)}\n")

    layer_ok = {"link": 0, "item": 0, "group_match": 0, "uom_match": 0, "rate_match": 0}
    issues = []

    for a in aliments:
        print(f"  ┌─ {a.nom_aliment}")
        print(f"  │  Aliment.type_aliment:    {a.type_aliment}")
        print(f"  │  Aliment.unite:           {a.unite}")
        print(f"  │  Aliment.prix_unitaire:   {a.prix_unitaire}")
        print(f"  │  Aliment.item:            {a.item}")

        if not a.item:
            issues.append(f"{a.nom_aliment}: pas de lien Item")
            print(f"  └─ ❌ pas de lien Item\n")
            continue
        layer_ok["link"] += 1

        item = frappe.db.get_value("Item", a.item,
            ["name", "item_name", "item_group", "stock_uom", "standard_rate", "is_stock_item"],
            as_dict=True)
        if not item:
            issues.append(f"{a.nom_aliment}: Item {a.item} introuvable")
            print(f"  └─ ❌ Item {a.item} introuvable\n")
            continue
        layer_ok["item"] += 1
        print(f"  │  Item.item_group:         {item.item_group}")
        print(f"  │  Item.stock_uom:          {item.stock_uom}")
        print(f"  │  Item.standard_rate:      {item.standard_rate}")

        # Check item_group mapping
        expected_group = TYPE_TO_ITEM_GROUP.get(a.type_aliment, "Aliment")
        if item.item_group == expected_group:
            layer_ok["group_match"] += 1
            grp_status = "✓"
        else:
            issues.append(f"{a.nom_aliment}: Item.item_group={item.item_group} ≠ attendu {expected_group}")
            grp_status = "❌"

        # Check stock_uom mapping
        expected_uom = UNITE_TO_UOM.get(a.unite, "Unit")
        if item.stock_uom == expected_uom:
            layer_ok["uom_match"] += 1
            uom_status = "✓"
        else:
            issues.append(f"{a.nom_aliment}: stock_uom={item.stock_uom} ≠ attendu {expected_uom}")
            uom_status = "❌"

        # Check standard_rate
        if float(item.standard_rate or 0) == float(a.prix_unitaire or 0):
            layer_ok["rate_match"] += 1
            rate_status = "✓"
        else:
            issues.append(f"{a.nom_aliment}: standard_rate={item.standard_rate} ≠ prix_unitaire {a.prix_unitaire}")
            rate_status = "❌"

        print(f"  └─ Mapping: groupe {grp_status}, uom {uom_status}, prix {rate_status}\n")

    # No SLE / Bin expected for Aliments — verify
    aliment_sle_count = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabStock Ledger Entry` sle
        JOIN `tabItem` i ON i.name = sle.item_code
        WHERE i.item_code LIKE 'ALI-%' AND sle.is_cancelled = 0
    """)[0][0]
    aliment_bin_count = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabBin` b
        JOIN `tabItem` i ON i.name = b.item_code
        WHERE i.item_code LIKE 'ALI-%'
    """)[0][0]

    print("=" * 70)
    print(f"  Aliments avec lien Item:        {layer_ok['link']}/{len(aliments)}")
    print(f"  Items existants:                {layer_ok['item']}/{len(aliments)}")
    print(f"  item_group correct:             {layer_ok['group_match']}/{len(aliments)}")
    print(f"  stock_uom correct:              {layer_ok['uom_match']}/{len(aliments)}")
    print(f"  standard_rate = prix_unitaire:  {layer_ok['rate_match']}/{len(aliments)}")
    print(f"  Stock Ledger Entries Aliment:   {aliment_sle_count}  (attendu: 0 — pas d'ouverture)")
    print(f"  Bins Aliment:                   {aliment_bin_count}  (attendu: 0 — pas de stock)")
    print("=" * 70)

    # Cross-check: Item Groups created
    aliment_groups = frappe.get_all("Item Group",
        filters={"parent_item_group": "Aliment"}, pluck="name")
    print(f"\n  Sous-groupes Aliment dans ERPNext: {sorted(aliment_groups)}")

    if issues:
        print("\n  ⚠️  ISSUES DÉTECTÉES:")
        for i in issues:
            print(f"    - {i}")
    else:
        print("\n  ✅ Tout est cohérent — migration Aliment vérifiée.")

    return {"checked": len(aliments), **layer_ok, "issues": issues}
