# Copyright (c) 2026, Mouhib Bouzamita and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today, add_days


class TestPesee(FrappeTestCase):
    """Comprehensive tests for Pesee doctype validations and side effects."""

    def setUp(self):
        # --- Batiment ---
        if not frappe.db.exists("Batiment", "PES-TEST-BAT"):
            frappe.get_doc({
                "doctype": "Batiment",
                "nom_batiment": "PES-TEST-BAT",
                "type_batiment": "ELEVAGE",
            }).insert(ignore_permissions=True)

        # --- Lot ---
        if not frappe.db.exists("Lot", "PES-TEST-LOT"):
            frappe.get_doc({
                "doctype": "Lot",
                "nom": "PES-TEST-LOT",
                "batiment": "PES-TEST-BAT",
                "superficie_m2": 100.0,
                "capacite_optimale": 20,
                "capacite_maximale": 30,
            }).insert(ignore_permissions=True)

        # --- Taureau ---
        if not frappe.db.exists("Taureau", "PES-TEST-PERE"):
            frappe.get_doc({
                "doctype": "Taureau",
                "nom_taureau": "PES-TEST-PERE",
                "code_taureau": "PESTP001",
                "race": "Holstein",
            }).insert(ignore_permissions=True)

        # --- Mere externe ---
        meres = frappe.get_all("Mere externe", limit=1)
        if meres:
            self.mere_externe = meres[0].name
        else:
            doc = frappe.get_doc({"doctype": "Mere externe"}).insert(ignore_permissions=True)
            self.mere_externe = doc.name

        # --- ACTIF animal ---
        if not frappe.db.exists("Animal", "8500000001"):
            frappe.get_doc({
                "doctype": "Animal",
                "identification_tn": "8500000001",
                "categorie": "VACHE",
                "race": "Holstein",
                "date_naissance": add_days(today(), -1000),
                "id_lot": "PES-TEST-LOT",
                "id_pere": "PES-TEST-PERE",
                "est_achat": 1,
                "id_mere_externe": self.mere_externe,
                "statut": "ACTIF",
            }).insert(ignore_permissions=True)
        else:
            frappe.db.set_value("Animal", "8500000001", {
                "statut": "ACTIF",
                "dernier_poids": 0,
            })

        # --- Non-ACTIF animal (VENDU) ---
        if not frappe.db.exists("Animal", "8500000002"):
            frappe.get_doc({
                "doctype": "Animal",
                "identification_tn": "8500000002",
                "categorie": "VACHE",
                "race": "Holstein",
                "date_naissance": add_days(today(), -1000),
                "id_lot": "PES-TEST-LOT",
                "id_pere": "PES-TEST-PERE",
                "est_achat": 1,
                "id_mere_externe": self.mere_externe,
                "statut": "ACTIF",
            }).insert(ignore_permissions=True)
            # Set to VENDU after insert to bypass validation
            frappe.db.set_value("Animal", "8500000002", "statut", "VENDU")

        # Clean up pesees for test animal
        for p in frappe.get_all("Pesee", filters={"animal": "8500000001"}):
            frappe.delete_doc("Pesee", p.name, force=True, ignore_permissions=True)

        frappe.db.commit()

    def tearDown(self):
        frappe.db.rollback()

    # ──────────────────────────────────────────────
    # Happy path
    # ──────────────────────────────────────────────
    def test_valid_creation(self):
        """Happy path: create a valid pesee."""
        pesee = frappe.get_doc({
            "doctype": "Pesee",
            "animal": "8500000001",
            "date_pesee": add_days(today(), -5),
            "poids_kg": 450.0,
            "type_pesee": "MENSUELLE",
        }).insert(ignore_permissions=True)

        self.assertTrue(pesee.name)
        self.assertEqual(pesee.poids_kg, 450.0)

    # ──────────────────────────────────────────────
    # Validation errors
    # ──────────────────────────────────────────────
    def test_non_actif_animal_fails(self):
        """Non-ACTIF animal cannot have a pesee."""
        with self.assertRaises(frappe.exceptions.ValidationError):
            frappe.get_doc({
                "doctype": "Pesee",
                "animal": "8500000002",
                "date_pesee": add_days(today(), -5),
                "poids_kg": 400.0,
                "type_pesee": "MENSUELLE",
            }).insert(ignore_permissions=True)

    def test_future_date_fails(self):
        """Future date is not allowed."""
        with self.assertRaises(frappe.exceptions.ValidationError):
            frappe.get_doc({
                "doctype": "Pesee",
                "animal": "8500000001",
                "date_pesee": add_days(today(), 1),
                "poids_kg": 450.0,
                "type_pesee": "MENSUELLE",
            }).insert(ignore_permissions=True)

    # ──────────────────────────────────────────────
    # Auto calculations
    # ──────────────────────────────────────────────
    def test_calculate_age(self):
        """age_jours should be calculated from date_naissance to date_pesee."""
        pesee = frappe.get_doc({
            "doctype": "Pesee",
            "animal": "8500000001",
            "date_pesee": add_days(today(), -5),
            "poids_kg": 450.0,
            "type_pesee": "MENSUELLE",
        }).insert(ignore_permissions=True)

        # Animal born 1000 days ago, pesee 5 days ago => age = 995
        self.assertEqual(pesee.age_jours, 995)

    def test_calculate_gmq(self):
        """GMQ is calculated from the difference between two pesees."""
        # First pesee: 30 days ago, 400 kg
        frappe.get_doc({
            "doctype": "Pesee",
            "animal": "8500000001",
            "date_pesee": add_days(today(), -30),
            "poids_kg": 400.0,
            "type_pesee": "MENSUELLE",
        }).insert(ignore_permissions=True)

        # Second pesee: 10 days ago, 430 kg
        pesee2 = frappe.get_doc({
            "doctype": "Pesee",
            "animal": "8500000001",
            "date_pesee": add_days(today(), -10),
            "poids_kg": 430.0,
            "type_pesee": "MENSUELLE",
        }).insert(ignore_permissions=True)

        # GMQ = (430-400) / 20 days * 1000 = 1500 g/day
        self.assertAlmostEqual(pesee2.gain_quotidien_moyen, 1500.0, places=1)

    # ──────────────────────────────────────────────
    # Animal sync
    # ──────────────────────────────────────────────
    def test_update_animal_poids_after_insert(self):
        """After inserting pesee, animal.dernier_poids should be updated."""
        frappe.get_doc({
            "doctype": "Pesee",
            "animal": "8500000001",
            "date_pesee": add_days(today(), -5),
            "poids_kg": 455.0,
            "type_pesee": "MENSUELLE",
        }).insert(ignore_permissions=True)

        poids = frappe.db.get_value("Animal", "8500000001", "dernier_poids")
        self.assertAlmostEqual(float(poids), 455.0, places=1)

    def test_update_animal_poids_on_delete(self):
        """After deleting the latest pesee, animal.dernier_poids falls back to previous."""
        frappe.get_doc({
            "doctype": "Pesee",
            "animal": "8500000001",
            "date_pesee": add_days(today(), -30),
            "poids_kg": 400.0,
            "type_pesee": "MENSUELLE",
        }).insert(ignore_permissions=True)

        p2 = frappe.get_doc({
            "doctype": "Pesee",
            "animal": "8500000001",
            "date_pesee": add_days(today(), -5),
            "poids_kg": 460.0,
            "type_pesee": "MENSUELLE",
        }).insert(ignore_permissions=True)

        # Delete the latest pesee
        frappe.delete_doc("Pesee", p2.name, force=True, ignore_permissions=True)

        poids = frappe.db.get_value("Animal", "8500000001", "dernier_poids")
        self.assertAlmostEqual(float(poids), 400.0, places=1)

    # ──────────────────────────────────────────────
    # Lock identity fields
    # ──────────────────────────────────────────────
    def test_lock_identity_fields(self):
        """Cannot change the animal field after creation."""
        pesee = frappe.get_doc({
            "doctype": "Pesee",
            "animal": "8500000001",
            "date_pesee": add_days(today(), -5),
            "poids_kg": 450.0,
            "type_pesee": "MENSUELLE",
        }).insert(ignore_permissions=True)

        pesee.reload()
        pesee.animal = "8500000002"
        with self.assertRaises(frappe.exceptions.ValidationError):
            pesee.save(ignore_permissions=True)

    # ──────────────────────────────────────────────
    # Type validation
    # ──────────────────────────────────────────────
    def test_valid_type_pesee(self):
        """Type must be a valid Select option."""
        for t in ["NAISSANCE", "MENSUELLE", "SEVRAGE", "VENTE"]:
            pesee = frappe.get_doc({
                "doctype": "Pesee",
                "animal": "8500000001",
                "date_pesee": add_days(today(), -5),
                "poids_kg": 450.0,
                "type_pesee": t,
            }).insert(ignore_permissions=True)
            self.assertEqual(pesee.type_pesee, t)
            frappe.delete_doc("Pesee", pesee.name, force=True, ignore_permissions=True)
