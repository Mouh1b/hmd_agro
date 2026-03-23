# Copyright (c) 2026, Mouhib Bouzamita and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today, add_days, getdate


class TestLactation(FrappeTestCase):
    """Comprehensive tests for Lactation doctype validations and side effects."""

    def setUp(self):
        # --- Batiment ---
        if not frappe.db.exists("Batiment", "LAC-TEST-BAT"):
            frappe.get_doc({
                "doctype": "Batiment",
                "nom_batiment": "LAC-TEST-BAT",
                "type_batiment": "ELEVAGE",
            }).insert(ignore_permissions=True)

        # --- Lot ---
        if not frappe.db.exists("Lot", "LAC-TEST-LOT"):
            frappe.get_doc({
                "doctype": "Lot",
                "nom": "LAC-TEST-LOT",
                "batiment": "LAC-TEST-BAT",
                "superficie_m2": 100.0,
                "capacite_optimale": 20,
                "capacite_maximale": 30,
            }).insert(ignore_permissions=True)

        # --- Taureau ---
        if not frappe.db.exists("Taureau", "LAC-TEST-PERE"):
            frappe.get_doc({
                "doctype": "Taureau",
                "nom_taureau": "LAC-TEST-PERE",
                "code_taureau": "LACTP001",
                "race": "Holstein",
            }).insert(ignore_permissions=True)

        # --- Mere externe ---
        meres = frappe.get_all("Mere externe", limit=1)
        if meres:
            self.mere_externe = meres[0].name
        else:
            doc = frappe.get_doc({"doctype": "Mere externe"}).insert(ignore_permissions=True)
            self.mere_externe = doc.name

        # --- Female VACHE animal ---
        if not frappe.db.exists("Animal", "8300000001"):
            frappe.get_doc({
                "doctype": "Animal",
                "identification_tn": "8300000001",
                "categorie": "VACHE",
                "race": "Holstein",
                "date_naissance": add_days(today(), -1000),
                "id_lot": "LAC-TEST-LOT",
                "id_pere": "LAC-TEST-PERE",
                "est_achat": 1,
                "id_mere_externe": self.mere_externe,
                "statut": "ACTIF",
            }).insert(ignore_permissions=True)
        else:
            frappe.db.set_value("Animal", "8300000001", {
                "statut": "ACTIF",
                "etat_lactation": "",
                "categorie": "VACHE",
            })

        # --- Male animal (for ERR-LAC-01) ---
        if not frappe.db.exists("Animal", "8300000002"):
            frappe.get_doc({
                "doctype": "Animal",
                "identification_tn": "8300000002",
                "categorie": "TAURILLON",
                "race": "Holstein",
                "date_naissance": add_days(today(), -500),
                "id_lot": "LAC-TEST-LOT",
                "id_pere": "LAC-TEST-PERE",
                "est_achat": 1,
                "id_mere_externe": self.mere_externe,
                "statut": "ACTIF",
            }).insert(ignore_permissions=True)

        # --- VEAU animal (for ERR-LAC-02) ---
        if not frappe.db.exists("Animal", "8300000003"):
            frappe.get_doc({
                "doctype": "Animal",
                "identification_tn": "8300000003",
                "categorie": "VEAU",
                "race": "Holstein",
                "date_naissance": add_days(today(), -30),
                "id_lot": "LAC-TEST-LOT",
                "id_pere": "LAC-TEST-PERE",
                "est_achat": 1,
                "id_mere_externe": self.mere_externe,
                "statut": "ACTIF",
            }).insert(ignore_permissions=True)

        # Clean up any existing lactations for our test animal
        for lac in frappe.get_all("Lactation", filters={"animal": "8300000001"}):
            frappe.delete_doc("Lactation", lac.name, force=True, ignore_permissions=True)

        frappe.db.commit()

    def tearDown(self):
        frappe.db.rollback()

    # ──────────────────────────────────────────────
    # Happy path
    # ──────────────────────────────────────────────
    def test_valid_creation(self):
        """Happy path: create a valid lactation for a VACHE."""
        lac = frappe.get_doc({
            "doctype": "Lactation",
            "animal": "8300000001",
            "statut": "EN_COURS",
            "date_debut": add_days(today(), -30),
        }).insert(ignore_permissions=True)

        self.assertTrue(lac.name)
        self.assertEqual(lac.statut, "EN_COURS")

    # ──────────────────────────────────────────────
    # Validation errors
    # ──────────────────────────────────────────────
    def test_male_animal_fails(self):
        """ERR-LAC-01: Male animal cannot have a lactation."""
        with self.assertRaises(frappe.exceptions.ValidationError) as ctx:
            frappe.get_doc({
                "doctype": "Lactation",
                "animal": "8300000002",
                "statut": "EN_COURS",
                "date_debut": add_days(today(), -30),
            }).insert(ignore_permissions=True)
        self.assertIn("ERR-LAC-01", str(ctx.exception))

    def test_veau_animal_fails(self):
        """VEAU is male, so ERR-LAC-01 (male check) fires before ERR-LAC-02 (categorie check)."""
        with self.assertRaises(frappe.exceptions.ValidationError) as ctx:
            frappe.get_doc({
                "doctype": "Lactation",
                "animal": "8300000003",
                "statut": "EN_COURS",
                "date_debut": add_days(today(), -30),
            }).insert(ignore_permissions=True)
        self.assertIn("ERR-LAC-01", str(ctx.exception))

    def test_duplicate_en_cours_fails(self):
        """ERR-LAC-03: Cannot have two EN_COURS lactations for the same animal."""
        frappe.get_doc({
            "doctype": "Lactation",
            "animal": "8300000001",
            "statut": "EN_COURS",
            "date_debut": add_days(today(), -60),
        }).insert(ignore_permissions=True)

        with self.assertRaises(frappe.exceptions.ValidationError) as ctx:
            frappe.get_doc({
                "doctype": "Lactation",
                "animal": "8300000001",
                "statut": "EN_COURS",
                "date_debut": add_days(today(), -10),
            }).insert(ignore_permissions=True)
        self.assertIn("ERR-LAC-03", str(ctx.exception))

    def test_date_tarissement_before_date_debut_fails(self):
        """ERR-LAC-04: date_tarissement cannot be before date_debut."""
        with self.assertRaises(frappe.exceptions.ValidationError) as ctx:
            frappe.get_doc({
                "doctype": "Lactation",
                "animal": "8300000001",
                "statut": "EN_COURS",
                "date_debut": add_days(today(), -30),
                "date_tarissement": add_days(today(), -60),
            }).insert(ignore_permissions=True)
        self.assertIn("ERR-LAC-04", str(ctx.exception))

    # ──────────────────────────────────────────────
    # Status transitions
    # ──────────────────────────────────────────────
    def test_transition_en_cours_to_tarie(self):
        """Valid transition: EN_COURS -> TARIE."""
        lac = frappe.get_doc({
            "doctype": "Lactation",
            "animal": "8300000001",
            "statut": "EN_COURS",
            "date_debut": add_days(today(), -30),
        }).insert(ignore_permissions=True)

        lac.reload()
        lac.statut = "TARIE"
        lac.date_tarissement = today()
        lac.save(ignore_permissions=True)
        self.assertEqual(lac.statut, "TARIE")

    def test_transition_en_cours_to_interrompue(self):
        """Valid transition: EN_COURS -> INTERROMPUE."""
        lac = frappe.get_doc({
            "doctype": "Lactation",
            "animal": "8300000001",
            "statut": "EN_COURS",
            "date_debut": add_days(today(), -30),
        }).insert(ignore_permissions=True)

        lac.reload()
        lac.statut = "INTERROMPUE"
        lac.save(ignore_permissions=True)
        self.assertEqual(lac.statut, "INTERROMPUE")

    def test_transition_tarie_to_en_cours_fails(self):
        """TARIE is a final state, cannot go back to EN_COURS."""
        lac = frappe.get_doc({
            "doctype": "Lactation",
            "animal": "8300000001",
            "statut": "EN_COURS",
            "date_debut": add_days(today(), -30),
        }).insert(ignore_permissions=True)

        lac.reload()
        lac.statut = "TARIE"
        lac.date_tarissement = today()
        lac.save(ignore_permissions=True)

        lac.reload()
        lac.statut = "EN_COURS"
        with self.assertRaises(frappe.exceptions.ValidationError):
            lac.save(ignore_permissions=True)

    def test_transition_interrompue_to_tarie_fails(self):
        """INTERROMPUE is a final state, cannot transition to TARIE."""
        lac = frappe.get_doc({
            "doctype": "Lactation",
            "animal": "8300000001",
            "statut": "EN_COURS",
            "date_debut": add_days(today(), -30),
        }).insert(ignore_permissions=True)

        lac.reload()
        lac.statut = "INTERROMPUE"
        lac.save(ignore_permissions=True)

        lac.reload()
        lac.statut = "TARIE"
        with self.assertRaises(frappe.exceptions.ValidationError):
            lac.save(ignore_permissions=True)

    # ──────────────────────────────────────────────
    # Auto calculations
    # ──────────────────────────────────────────────
    def test_auto_set_numero_lactation(self):
        """numero_lactation is auto-incremented per animal."""
        lac1 = frappe.get_doc({
            "doctype": "Lactation",
            "animal": "8300000001",
            "statut": "EN_COURS",
            "date_debut": add_days(today(), -60),
        }).insert(ignore_permissions=True)
        self.assertEqual(lac1.numero_lactation, 1)

        # End first lactation so we can create a second
        lac1.reload()
        lac1.statut = "TARIE"
        lac1.date_tarissement = add_days(today(), -10)
        lac1.save(ignore_permissions=True)

        lac2 = frappe.get_doc({
            "doctype": "Lactation",
            "animal": "8300000001",
            "statut": "EN_COURS",
            "date_debut": add_days(today(), -5),
        }).insert(ignore_permissions=True)
        self.assertEqual(lac2.numero_lactation, 2)

    def test_calculate_jours_lactation(self):
        """jours_lactation should be calculated from date_debut to today or date_tarissement."""
        lac = frappe.get_doc({
            "doctype": "Lactation",
            "animal": "8300000001",
            "statut": "EN_COURS",
            "date_debut": add_days(today(), -30),
        }).insert(ignore_permissions=True)

        self.assertEqual(lac.jours_lactation, 30)

    # ──────────────────────────────────────────────
    # Lock identity fields
    # ──────────────────────────────────────────────
    def test_lock_identity_fields(self):
        """Cannot change the animal field after creation."""
        # Create a second female animal
        if not frappe.db.exists("Animal", "8300000004"):
            frappe.get_doc({
                "doctype": "Animal",
                "identification_tn": "8300000004",
                "categorie": "VACHE",
                "race": "Holstein",
                "date_naissance": add_days(today(), -1000),
                "id_lot": "LAC-TEST-LOT",
                "id_pere": "LAC-TEST-PERE",
                "est_achat": 1,
                "id_mere_externe": self.mere_externe,
                "statut": "ACTIF",
            }).insert(ignore_permissions=True)

        lac = frappe.get_doc({
            "doctype": "Lactation",
            "animal": "8300000001",
            "statut": "EN_COURS",
            "date_debut": add_days(today(), -30),
        }).insert(ignore_permissions=True)

        lac.reload()
        lac.animal = "8300000004"
        with self.assertRaises(frappe.exceptions.ValidationError):
            lac.save(ignore_permissions=True)

    # ──────────────────────────────────────────────
    # Animal sync
    # ──────────────────────────────────────────────
    def test_after_insert_syncs_animal_etat_lactation(self):
        """after_insert sets animal.etat_lactation = EN_PRODUCTION."""
        frappe.get_doc({
            "doctype": "Lactation",
            "animal": "8300000001",
            "statut": "EN_COURS",
            "date_debut": add_days(today(), -30),
        }).insert(ignore_permissions=True)

        etat = frappe.db.get_value("Animal", "8300000001", "etat_lactation")
        self.assertEqual(etat, "EN_PRODUCTION")

    def test_sync_animal_etat_on_tarie(self):
        """When lactation becomes TARIE, animal.etat_lactation = TARIE."""
        lac = frappe.get_doc({
            "doctype": "Lactation",
            "animal": "8300000001",
            "statut": "EN_COURS",
            "date_debut": add_days(today(), -30),
        }).insert(ignore_permissions=True)

        lac.reload()
        lac.statut = "TARIE"
        lac.date_tarissement = today()
        lac.save(ignore_permissions=True)

        etat = frappe.db.get_value("Animal", "8300000001", "etat_lactation")
        self.assertEqual(etat, "TARIE")

    def test_sync_animal_etat_on_interrompue(self):
        """When lactation becomes INTERROMPUE, animal.etat_lactation is cleared."""
        lac = frappe.get_doc({
            "doctype": "Lactation",
            "animal": "8300000001",
            "statut": "EN_COURS",
            "date_debut": add_days(today(), -30),
        }).insert(ignore_permissions=True)

        lac.reload()
        lac.statut = "INTERROMPUE"
        lac.save(ignore_permissions=True)

        etat = frappe.db.get_value("Animal", "8300000001", "etat_lactation")
        self.assertEqual(etat, "")
