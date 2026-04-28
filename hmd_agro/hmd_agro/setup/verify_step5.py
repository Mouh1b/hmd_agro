"""Verify Step 5: Semence → Item + Batch migration consistency."""
import frappe

TYPE_TO_ITEM_GROUP = {
    "CONVENTIONNELLE": "Semence Conventionnelle",
    "SEXEE": "Semence Sexée",
}
TYPE_SHORT = {"CONVENTIONNELLE": "CONV", "SEXEE": "SEX"}


def run():
    print("\n" + "=" * 70)
    print("  Verification Step 5 — Semence → Item + Batch migration")
    print("=" * 70)

    semences = frappe.get_all("Semence",
        fields=["name", "taureau", "type_semence", "date_expiration",
                "quantite_recue", "quantite_restante", "item"],
        order_by="creation")

    print(f"\n  Semences dans le système: {len(semences)}\n")

    layer_ok = {"link": 0, "item": 0, "batch": 0, "bin_match": 0}
    issues = []

    for s in semences:
        print(f"  ┌─ {s.name}  (taureau={s.taureau}, type={s.type_semence})")
        print(f"  │  quantite_restante: {s.quantite_restante} / {s.quantite_recue}")
        print(f"  │  date_expiration:   {s.date_expiration}")
        print(f"  │  Semence.item:      {s.item}")

        if not s.item:
            issues.append(f"{s.name}: pas de lien Item")
            print(f"  └─ ❌ pas de lien\n")
            continue
        layer_ok["link"] += 1

        # Item exists?
        expected_code = f"SEM-{s.taureau}-{TYPE_SHORT.get(s.type_semence)}"
        if s.item != expected_code:
            issues.append(f"{s.name}: item={s.item} ≠ attendu {expected_code}")
        item = frappe.db.get_value("Item", s.item,
            ["item_group", "stock_uom", "has_batch_no"], as_dict=True)
        if not item:
            issues.append(f"{s.name}: Item {s.item} introuvable")
            print(f"  └─ ❌ Item introuvable\n")
            continue
        layer_ok["item"] += 1
        print(f"  │  Item.item_group:   {item.item_group}")
        print(f"  │  Item.stock_uom:    {item.stock_uom}")
        print(f"  │  Item.has_batch_no: {item.has_batch_no}")

        # Batch exists with batch_id = Semence.name?
        batch = frappe.db.get_value("Batch", s.name,
            ["item", "expiry_date"], as_dict=True)
        if not batch:
            issues.append(f"{s.name}: Batch absent")
            print(f"  └─ ❌ Batch absent\n")
            continue
        layer_ok["batch"] += 1
        print(f"  │  Batch.item:        {batch.item}")
        print(f"  │  Batch.expiry_date: {batch.expiry_date}")

        # Per-batch balance: ERPNext stores it on Batch.batch_qty (computed from SLEs)
        bin_qty = frappe.db.get_value("Batch", s.name, "batch_qty") or 0
        print(f"  │  Bin (par batch):   {bin_qty}")

        if int(bin_qty) == int(s.quantite_restante or 0):
            layer_ok["bin_match"] += 1
            print(f"  └─ ✅ quantite_restante ({s.quantite_restante}) == Bin batch ({int(bin_qty)})\n")
        else:
            issues.append(f"{s.name}: drift quantite_restante={s.quantite_restante} ≠ Bin={bin_qty}")
            print(f"  └─ ❌ DRIFT\n")

    # Cross-check: total Bin per (Taureau, type_semence) Item
    print("=" * 70)
    print("  Vérification cumulée par Item (somme des batches)\n")
    items = frappe.get_all("Item", filters={"item_code": ["like", "SEM-%"]},
        pluck="name")
    for it in items:
        bin_total = sum((frappe.get_all("Bin",
            filters={"item_code": it, "warehouse": "Magasin Principal - HMD"},
            pluck="actual_qty") or [0]))
        # Sum of quantite_restante for all Semences linked to this Item
        sem_total = frappe.db.sql("""
            SELECT SUM(quantite_restante) FROM `tabSemence` WHERE item = %s
        """, it)[0][0] or 0
        ok = int(bin_total) == int(sem_total)
        print(f"  {it}: Σ Semence.quantite_restante = {sem_total} | "
              f"Bin total = {bin_total}  {'✓' if ok else '❌'}")

    print("\n" + "=" * 70)
    print(f"  Semences avec lien Item:        {layer_ok['link']}/{len(semences)}")
    print(f"  Items existants:                {layer_ok['item']}/{len(semences)}")
    print(f"  Batches existants:              {layer_ok['batch']}/{len(semences)}")
    print(f"  qte_restante ↔ Bin par batch:   {layer_ok['bin_match']}/{len(semences)}")
    print("=" * 70)

    if issues:
        print("\n  ⚠️  ISSUES:")
        for i in issues:
            print(f"    - {i}")
    else:
        print("\n  ✅ Migration Semence vérifiée.")

    return {"checked": len(semences), **layer_ok, "issues": issues}
