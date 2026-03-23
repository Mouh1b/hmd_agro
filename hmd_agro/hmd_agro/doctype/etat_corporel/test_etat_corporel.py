# Copyright (c) 2026, Mouhib Bouzamita and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today, add_days


class TestEtatCorporel(FrappeTestCase):
    """Comprehensive tests for Etat Corporel doctype validations and side effects."""

    def setUp(self):
        # --- Batiment ---
        if not frappe.db.exists("Batiment", "EC-TEST-BAT"):
            frappe.get_doc({
                "doctype": "Batiment",
                "nom_batiment": "EC-TEST-BAT",
                "type_batiment": "ELEVAGE",
            }).insert(ignore_permissions=True)

        # --- Lot ---
        if not frappe.db.exists("Lot", "EC-TEST-LOT"):
            frappe.get_doc({
                "doctype": "Lot",
                "nom": "EC-TEST-LOT",
                "batiment": "EC-TEST-BAT",
                "superficie_m2": 100.0,
                "capacite_optimale": 20,
                "capacite_maximale": 30,
            }).insert(ignore_permissions=True)

        # --- Taureau ---
        if not frappe.db.exists("Taureau", "EC-TEST-PERE"):
            frappe.get_doc({
                "doctype": "Taureau",
                "nom_taureau": "EC-TEST-PERE",
                "code_taureau": "ECTP001",
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
        if not frappe.db.exists("Animal", "8600000001"):
            frappe.get_doc({
                "doctype": "Animal",
                "identification_tn": "8600000001",
                "categorie": "VACHE",
                "race": "Holstein",
                "date_naissance": add_days(today(), -1000),
                "id_lot": "EC-TEST-LOT",
                "id_pere": "EC-TEST-PERE",
                "est_achat": 1,
                "id_mere_externe": self.mere_externe,
                "statut": "ACTIF",
            }).insert(ignore_permissions=True)
        else:
            frappe.db.set_value("Animal", "8600000001", {
                "statut": "ACTIF",
                "etat_corporel": 0,
            })

        # --- Non-ACTIF animal ---
        if not frappe.db.exists("Animal", "8600000002"):
            frappe.get_doc({
                "doctype": "Animal",
                "identification_tn": "8600000002",
                "categorie": "VACHE",
                "race": "Holstein",
                "date_naissance": add_days(today(), -1000),
                "id_lot": "EC-TEST-LOT",
                "id_pere": "EC-TEST-PERE",
                "est_achat": 1,
                "id_mere_externe": self.mere_externe,
                "statut": "ACTIF",
            }).insert(ignore_permissions=True)
            frappe.db.set_value("Animal", "8600000002", "statut", "VENDU")

        # Clean up existing etat corporel records
        for ec in frappe.get_all("Etat Corporel", filters={"animal": "8600000001"}):
            frappe.delete_doc("Etat Corporel", ec.name, force=True, ignore_permissions=True)

        frappe.db.commit()

    def tearDown(self):
        frappe.db.rollback()

    # ──────────────────────────────────────────────
    # Happy path
    # ──────────────────────────────────────────────
    def test_valid_creation(self):
        """Happy path: create a valid etat corporel."""
        ec = frappe.get_doc({
            "doctype": "Etat Corporel",
            "animal": "8600000001",
            "date": add_days(today(), -5),
            "score": "3",
        }).insert(ignore_permissions=True)

        self.assertTrue(ec.name)

    # ──────────────────────────────────────────────
    # Score validation
    # ──────────────────────────────────────────────
    def test_invalid_score_too_high(self):
        """Score 6 is not valid."""
        with self.assertRaises(frappe.exceptions.ValidationError):
            frappe.get_doc({
                "doctype": "Etat Corporel",
                "animal": "8600000001",
                "date": add_days(today(), -5),
                "score": "6",
            }).insert(ignore_permissions=True)

    def test_invalid_score_negative(self):
        """Score -1 is not valid."""
        with self.assertRaises(frappe.exceptions.ValidationError):
            frappe.get_doc({
                "doctype": "Etat Corporel",
                "animal": "8600000001",
                "date": add_days(today(), -5),
                "score": "-1",
            }).insert(ignore_permissions=True)

    def test_invalid_score_not_half_step(self):
        """Score 2.3 is not valid (must be 0.5 steps)."""
        with self.assertRaises(frappe.exceptions.ValidationError):
            frappe.get_doc({
                "doctype": "Etat Corporel",
                "animal": "8600000001",
                "date": add_days(today(), -5),
                "score": "2.3",
            }).insert(ignore_permissions=True)

    def test_all_valid_scores(self):
        """All valid scores (1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5) should work."""
        for score in ["1", "1.5", "2", "2.5", "3", "3.5", "4", "4.5", "5"]:
            ec = frappe.get_doc({
                "doctype": "Etat Corporel",
                "animal": "8600000001",
                "date": add_days(today(), -5),
                "score": score,
            }).insert(ignore_permissions=True)
            self.assertTrue(ec.name)
            frappe.delete_doc("Etat Corporel", ec.name, force=True, ignore_permissions=True)

    # ──────────────────────────────────────────────
    # Animal validation
    # ──────────────────────────────────────────────
    def test_non_actif_animal_fails(self):
        """Non-ACTIF animal cannot have an etat corporel."""
        with self.assertRaises(frappe.exceptions.ValidationError):
            frappe.get_doc({
                "doctype": "Etat Corporel",
                "animal": "8600000002",
                "date": add_days(today(), -5),
                "score": "3",
            }).insert(ignore_permissions=True)

    # ──────────────────────────────────────────────
    # Date validation
    # ──────────────────────────────────────────────
    def test_future_date_fails(self):
        """Future date is not allowed."""
        with self.assertRaises(frappe.exceptions.ValidationError):
            frappe.get_doc({
                "doctype": "Etat Corporel",
                "animal": "8600000001",
                "date": add_days(today(), 1),
                "score": "3",
            }).insert(ignore_permissions=True)

    # ──────────────────────────────────────────────
    # Animal sync
    # ──────────────────────────────────────────────
    def test_update_animal_score_after_insert(self):
        """After inserting etat corporel, animal.etat_corporel should be updated."""
        frappe.get_doc({
            "doctype": "Etat Corporel",
            "animal": "8600000001",
            "date": add_days(today(), -5),
            "score": "3.5",
        }).insert(ignore_permissions=True)

        score = frappe.db.get_value("Animal", "8600000001", "etat_corporel")
        self.assertEqual(float(score), 3.5)

    def test_update_animal_score_on_delete(self):
        """After deleting the latest etat corporel, animal.etat_corporel falls back."""
        frappe.get_doc({
            "doctype": "Etat Corporel",
            "animal": "8600000001",
            "date": add_days(today(), -30),
            "score": "2.5",
        }).insert(ignore_permissions=True)

        ec2 = frappe.get_doc({
            "doctype": "Etat Corporel",
            "animal": "8600000001",
            "date": add_days(today(), -5),
            "score": "4",
        }).insert(ignore_permissions=True)

        # Delete the latest record
        frappe.delete_doc("Etat Corporel", ec2.name, force=True, ignore_permissions=True)

        score = frappe.db.get_value("Animal", "8600000001", "etat_corporel")
        self.assertEqual(float(score), 2.5)

    # ──────────────────────────────────────────────
    # Lock identity fields
    # ──────────────────────────────────────────────
    def test_lock_identity_fields(self):
        """Cannot change the animal field after creation."""
        ec = frappe.get_doc({
            "doctype": "Etat Corporel",
            "animal": "8600000001",
            "date": add_days(today(), -5),
            "score": "3",
        }).insert(ignore_permissions=True)

        ec.reload()
        ec.animal = "8600000002"
        with self.assertRaises(frappe.exceptions.ValidationError):
            ec.save(ignore_permissions=True)
