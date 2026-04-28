"""Verify Step 2: Médicament → Item migration consistency across all 4 layers
(Medicament link, Item, Stock Ledger Entry, Bin)."""
import frappe


def run():
    print("\n" + "=" * 70)
    print("  Verification Step 2 — Médicament → Item migration")
    print("=" * 70)

    meds = frappe.get_all("Medicament",
        fields=["name", "nom_medicament", "type_medicament", "stock_actuel", "item"],
        order_by="nom_medicament")

    print(f"\n  Médicaments dans le système: {len(meds)}\n")

    layer_ok = {"link": 0, "item": 0, "sle": 0, "bin": 0, "match": 0}
    issues = []

    for med in meds:
        print(f"  ┌─ {med.nom_medicament} (type={med.type_medicament})")
        print(f"  │  Medicament.stock_actuel: {med.stock_actuel}")
        print(f"  │  Medicament.item:         {med.item}")

        if not med.item:
            issues.append(f"{med.nom_medicament}: pas de lien Item")
            print(f"  └─ ❌ pas de lien Item\n")
            continue
        layer_ok["link"] += 1

        # Layer 1: Item exists?
        item = frappe.db.get_value("Item", med.item,
            ["name", "item_name", "item_group", "stock_uom", "is_stock_item"], as_dict=True)
        if not item:
            issues.append(f"{med.nom_medicament}: Item {med.item} introuvable")
            print(f"  └─ ❌ Item {med.item} introuvable\n")
            continue
        layer_ok["item"] += 1
        print(f"  │  Item.item_group:         {item.item_group}")
        print(f"  │  Item.stock_uom:          {item.stock_uom}")
        print(f"  │  Item.is_stock_item:      {item.is_stock_item}")

        # Layer 2: Stock Ledger Entries for this item
        sles = frappe.get_all("Stock Ledger Entry",
            filters={"item_code": med.item, "is_cancelled": 0},
            fields=["voucher_type", "voucher_no", "actual_qty", "qty_after_transaction"])
        if not sles:
            issues.append(f"{med.nom_medicament}: aucune SLE")
            print(f"  └─ ❌ aucune Stock Ledger Entry\n")
            continue
        layer_ok["sle"] += 1
        print(f"  │  SLE entries:             {len(sles)}  ({sles[0].voucher_type} {sles[0].voucher_no}, qty={sles[0].actual_qty})")

        # Layer 3: Bin
        bin_qty = frappe.db.get_value("Bin",
            {"item_code": med.item, "warehouse": "Magasin Principal - HMD"},
            "actual_qty")
        if bin_qty is None:
            issues.append(f"{med.nom_medicament}: pas de Bin")
            print(f"  └─ ❌ pas de Bin row\n")
            continue
        layer_ok["bin"] += 1
        print(f"  │  Bin.actual_qty:          {bin_qty}")

        # Layer 4: Match between stock_actuel and Bin
        if int(bin_qty) == int(med.stock_actuel or 0):
            layer_ok["match"] += 1
            print(f"  └─ ✅ stock_actuel ({med.stock_actuel}) == Bin.actual_qty ({int(bin_qty)})\n")
        else:
            issues.append(f"{med.nom_medicament}: drift stock_actuel={med.stock_actuel} ≠ Bin={bin_qty}")
            print(f"  └─ ❌ DRIFT: stock_actuel ({med.stock_actuel}) ≠ Bin ({int(bin_qty)})\n")

    # Aggregate counts
    print("=" * 70)
    print(f"  Médicaments avec lien Item:        {layer_ok['link']}/{len(meds)}")
    print(f"  Items existants:                   {layer_ok['item']}/{len(meds)}")
    print(f"  Stock Ledger Entries présentes:    {layer_ok['sle']}/{len(meds)}")
    print(f"  Bins présents:                     {layer_ok['bin']}/{len(meds)}")
    print(f"  stock_actuel ↔ Bin cohérents:      {layer_ok['match']}/{len(meds)}")
    print("=" * 70)

    # Cross-check: total Stock Entries created in this migration
    se_count = frappe.db.count("Stock Entry",
        {"stock_entry_type": "Material Receipt",
         "remarks": ["like", "Stock d'ouverture migration%"]})
    print(f"\n  Stock Entries de migration:        {se_count}")

    # Cross-check: total SLE rows in Magasin Principal
    sle_total = frappe.db.count("Stock Ledger Entry",
        {"warehouse": "Magasin Principal - HMD", "is_cancelled": 0})
    print(f"  SLE total dans Magasin Principal:  {sle_total}")

    # Cross-check: warehouse + company linkage
    wh = frappe.db.get_value("Warehouse", "Magasin Principal - HMD",
        ["company", "is_group", "parent_warehouse"], as_dict=True)
    print(f"\n  Magasin Principal - HMD:")
    print(f"    company:           {wh.company}")
    print(f"    is_group:          {wh.is_group}")
    print(f"    parent_warehouse:  {wh.parent_warehouse}")

    if issues:
        print("\n  ⚠️  ISSUES DÉTECTÉES:")
        for i in issues:
            print(f"    - {i}")
    else:
        print("\n  ✅ Tout est cohérent — migration vérifiée end-to-end.")

    return {"checked": len(meds), **layer_ok, "issues": issues}
