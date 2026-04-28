import frappe

def run():
    print("--- SED ---")
    print(frappe.db.sql("""
        SELECT item_code, qty, batch_no, t_warehouse
        FROM `tabStock Entry Detail`
        WHERE item_code='SEM-Willow-CONV'
    """, as_dict=True))
    print("\n--- All SLE for SEM-Willow ---")
    print(frappe.db.sql("""
        SELECT name, item_code, batch_no, actual_qty, voucher_no
        FROM `tabStock Ledger Entry`
        WHERE item_code='SEM-Willow-CONV'
    """, as_dict=True))
    print("\n--- Bin ---")
    print(frappe.db.sql("""
        SELECT name, item_code, warehouse, actual_qty
        FROM `tabBin`
        WHERE item_code LIKE 'SEM-%'
    """, as_dict=True))
    print("\n--- Batch list ---")
    print(frappe.db.sql("""
        SELECT name, item, batch_qty FROM `tabBatch` WHERE item LIKE 'SEM-%'
    """, as_dict=True))
