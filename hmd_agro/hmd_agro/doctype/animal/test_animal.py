# Copyright (c) 2026, Mouhib Bouzamita and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today, add_days, getdate


class TestAnimal(FrappeTestCase):
    """Comprehensive tests for Animal doctype validations and logic."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create prerequisite records once for the entire test class

        # Batiment
        if not frappe.db.exists("Batiment", "Test Batiment"):
            frappe.get_doc({
                "doctype": "Batiment",
                "nom_batiment": "Test Batiment",
                "type_batiment": "ELEVAGE",
            }).insert(ignore_permissions=True)

        # Lot (requires Batiment)
        if not frappe.db.exists("Lot", "Test Lot"):
            frappe.get_doc({
                "doctype": "Lot",
                "nom": "Test Lot",
                "batiment": "Test Batiment",
                "superficie_m2": 100,
                "capacite_optimale": 20,
                "capacite_maximale": 30,
            }).insert(ignore_permissions=True)

        # Taureau (pere)
        if not frappe.db.exists("Taureau", "Test Pere"):
            frappe.get_doc({
                "doctype": "Taureau",
                "nom_taureau": "Test Pere",
                "code_taureau": "TP001",
                "race": "Holstein",
            }).insert(ignore_permissions=True)

        # Mere externe (for achat animals)
        mere = frappe.db.get_value("Mere externe", {}, "name")
        if not mere:
            doc = frappe.get_doc({"doctype": "Mere externe"})
            doc.insert(ignore_permissions=True)
            mere = doc.name
        cls.mere_externe = mere

        # Mother animal (for non-achat animals) - needs to be an existing Animal
        if not frappe.db.exists("Animal", "8000099901"):
            frappe.get_doc({
                "doctype": "Animal",
                "identification_tn": "8000099901",
                "race": "Holstein",
                "date_naissance": add_days(today(), -1000),
                "categorie": "VACHE",
                "est_achat": 1,
                "id_mere_externe": cls.mere_externe,
                "id_pere": "Test Pere",
                "id_lot": "Test Lot",
                "statut": "ACTIF",
            }).insert(ignore_permissions=True)

        frappe.db.commit()

    def _make_animal(self, **kwargs):
        """Helper: create an Animal doc with sensible defaults (non-achat female).
        Override any field via kwargs."""
        import time
        counter = getattr(self.__class__, '_animal_counter', 0) + 1
        self.__class__._animal_counter = counter
        # Use 10-digit unique IDs to avoid TEMP collisions
        ts = str(int(time.time()))[-5:]
        default_tn = f"80{ts}{counter:03d}"

        defaults = {
            "doctype": "Animal",
            "identification_tn": default_tn,
            "race": "Holstein",
            "date_naissance": add_days(today(), -365),
            "categorie": "VACHE",
            "est_achat": 0,
            "id_mere": "8000099901",
            "id_pere": "Test Pere",
            "id_lot": "Test Lot",
            "statut": "ACTIF",
        }
        defaults.update(kwargs)
        return frappe.get_doc(defaults)

    # ──────────────────────────────────────────────
    # set_nom_metier
    # ──────────────────────────────────────────────

    def test_nom_metier_10_digits(self):
        """10-digit ID -> nom_metier = last 4 digits"""
        doc = self._make_animal(
            identification_tn="8000099902",
            est_achat=1,
            id_mere_externe=self.mere_externe,
            id_mere=None,
        )
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.nom_metier, "9902")

    def test_nom_metier_temp(self):
        """TEMP-XX ID -> nom_metier = full TEMP-XX"""
        doc = self._make_animal(identification_tn="TEMP-42")
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.nom_metier, "TEMP-42")

    # ──────────────────────────────────────────────
    # set_sexe_from_categorie
    # ──────────────────────────────────────────────

    def test_sexe_female_from_vache(self):
        doc = self._make_animal(categorie="VACHE")
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.sexe, "F")

    def test_sexe_female_from_genisse(self):
        doc = self._make_animal(categorie="GENISSE")
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.sexe, "F")

    def test_sexe_female_from_velle(self):
        doc = self._make_animal(categorie="VELLE")
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.sexe, "F")

    def test_sexe_male_from_veau(self):
        doc = self._make_animal(categorie="VEAU")
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.sexe, "M")

    def test_sexe_male_from_taurillon(self):
        doc = self._make_animal(categorie="TAURILLON")
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.sexe, "M")

    # ──────────────────────────────────────────────
    # validate_mere_obligatoire
    # ──────────────────────────────────────────────

    def test_non_achat_without_mere_raises(self):
        """Non-achat animal without id_mere must fail"""
        doc = self._make_animal(est_achat=0, id_mere=None)
        with self.assertRaises(frappe.exceptions.ValidationError):
            doc.insert(ignore_permissions=True)
        frappe.db.rollback()

    def test_non_achat_with_mere_succeeds(self):
        doc = self._make_animal(est_achat=0, id_mere="8000099901")
        doc.insert(ignore_permissions=True)
        self.assertTrue(doc.name)

    def test_achat_without_mere_externe_raises(self):
        """Achat animal without id_mere_externe must fail"""
        doc = self._make_animal(est_achat=1, id_mere=None, id_mere_externe=None)
        with self.assertRaises(frappe.exceptions.ValidationError):
            doc.insert(ignore_permissions=True)
        frappe.db.rollback()

    def test_achat_with_mere_externe_succeeds(self):
        doc = self._make_animal(
            est_achat=1,
            id_mere=None,
            id_mere_externe=self.mere_externe,
            date_entree=add_days(today(), -100),
        )
        doc.insert(ignore_permissions=True)
        self.assertTrue(doc.name)

    # ──────────────────────────────────────────────
    # validate_dates
    # ──────────────────────────────────────────────

    def test_future_birth_date_raises(self):
        """Birth date in the future must fail"""
        doc = self._make_animal(date_naissance=add_days(today(), 1))
        with self.assertRaises(frappe.exceptions.ValidationError):
            doc.insert(ignore_permissions=True)
        frappe.db.rollback()

    def test_today_birth_date_succeeds(self):
        """Birth date = today is valid"""
        doc = self._make_animal(date_naissance=today())
        doc.insert(ignore_permissions=True)
        self.assertTrue(doc.name)

    def test_past_birth_date_succeeds(self):
        doc = self._make_animal(date_naissance=add_days(today(), -30))
        doc.insert(ignore_permissions=True)
        self.assertTrue(doc.name)

    def test_achat_entry_before_birth_raises(self):
        """Achat: date_entree < date_naissance must fail"""
        birth = add_days(today(), -100)
        entry = add_days(today(), -200)  # before birth
        doc = self._make_animal(
            est_achat=1,
            id_mere=None,
            id_mere_externe=self.mere_externe,
            date_naissance=birth,
            date_entree=entry,
        )
        with self.assertRaises(frappe.exceptions.ValidationError):
            doc.insert(ignore_permissions=True)
        frappe.db.rollback()

    def test_achat_entry_after_birth_succeeds(self):
        birth = add_days(today(), -200)
        entry = add_days(today(), -100)  # after birth
        doc = self._make_animal(
            est_achat=1,
            id_mere=None,
            id_mere_externe=self.mere_externe,
            date_naissance=birth,
            date_entree=entry,
        )
        doc.insert(ignore_permissions=True)
        self.assertTrue(doc.name)

    def test_achat_entry_same_as_birth_succeeds(self):
        birth = add_days(today(), -100)
        doc = self._make_animal(
            est_achat=1,
            id_mere=None,
            id_mere_externe=self.mere_externe,
            date_naissance=birth,
            date_entree=birth,
        )
        doc.insert(ignore_permissions=True)
        self.assertTrue(doc.name)

    # ──────────────────────────────────────────────
    # validate_identification_tn
    # ──────────────────────────────────────────────

    def test_valid_tn_10_digits(self):
        doc = self._make_animal(
            identification_tn="8000099903",
            est_achat=1,
            id_mere=None,
            id_mere_externe=self.mere_externe,
        )
        doc.insert(ignore_permissions=True)
        self.assertTrue(doc.name)

    def test_valid_tn_temp_format(self):
        doc = self._make_animal(identification_tn="TEMP-99")
        doc.insert(ignore_permissions=True)
        self.assertTrue(doc.name)

    def test_invalid_tn_too_short(self):
        doc = self._make_animal(identification_tn="12345")
        with self.assertRaises(frappe.exceptions.ValidationError):
            doc.insert(ignore_permissions=True)
        frappe.db.rollback()

    def test_invalid_tn_letters(self):
        doc = self._make_animal(identification_tn="ABCDEFGHIJ")
        with self.assertRaises(frappe.exceptions.ValidationError):
            doc.insert(ignore_permissions=True)
        frappe.db.rollback()

    def test_invalid_tn_temp_wrong_format(self):
        """TEMP-1 (single digit) should fail"""
        doc = self._make_animal(identification_tn="TEMP-1")
        with self.assertRaises(frappe.exceptions.ValidationError):
            doc.insert(ignore_permissions=True)
        frappe.db.rollback()

    def test_invalid_tn_temp_three_digits(self):
        """TEMP-123 should fail (only 2 digits allowed)"""
        doc = self._make_animal(identification_tn="TEMP-123")
        with self.assertRaises(frappe.exceptions.ValidationError):
            doc.insert(ignore_permissions=True)
        frappe.db.rollback()

    def test_invalid_tn_9_digits(self):
        doc = self._make_animal(identification_tn="123456789")
        with self.assertRaises(frappe.exceptions.ValidationError):
            doc.insert(ignore_permissions=True)
        frappe.db.rollback()

    def test_invalid_tn_11_digits(self):
        doc = self._make_animal(identification_tn="12345678901")
        with self.assertRaises(frappe.exceptions.ValidationError):
            doc.insert(ignore_permissions=True)
        frappe.db.rollback()

    # ──────────────────────────────────────────────
    # validate_and_format_identification_fr
    # ──────────────────────────────────────────────

    def test_valid_fr_formatted(self):
        """FR1234567890 should be formatted as FR 12 3456 7890"""
        doc = self._make_animal(identification_fr="FR1234567890")
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.identification_fr, "FR 12 3456 7890")

    def test_valid_fr_with_spaces(self):
        """FR with spaces should be cleaned and re-formatted"""
        doc = self._make_animal(identification_fr="FR 98 7654 3210")
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.identification_fr, "FR 98 7654 3210")

    def test_valid_fr_lowercase(self):
        """Lowercase 'fr' should be accepted and uppercased"""
        doc = self._make_animal(identification_fr="fr1111222233")
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.identification_fr, "FR 11 1122 2233")

    def test_invalid_fr_no_prefix(self):
        """Missing FR prefix"""
        doc = self._make_animal(identification_fr="1234567890")
        with self.assertRaises(frappe.exceptions.ValidationError):
            doc.insert(ignore_permissions=True)
        frappe.db.rollback()

    def test_invalid_fr_wrong_prefix(self):
        doc = self._make_animal(identification_fr="DE1234567890")
        with self.assertRaises(frappe.exceptions.ValidationError):
            doc.insert(ignore_permissions=True)
        frappe.db.rollback()

    def test_invalid_fr_too_few_digits(self):
        doc = self._make_animal(identification_fr="FR123456789")
        with self.assertRaises(frappe.exceptions.ValidationError):
            doc.insert(ignore_permissions=True)
        frappe.db.rollback()

    def test_invalid_fr_too_many_digits(self):
        doc = self._make_animal(identification_fr="FR12345678901")
        with self.assertRaises(frappe.exceptions.ValidationError):
            doc.insert(ignore_permissions=True)
        frappe.db.rollback()

    def test_no_fr_is_ok(self):
        """identification_fr is optional"""
        doc = self._make_animal(identification_fr=None)
        doc.insert(ignore_permissions=True)
        self.assertTrue(doc.name)

    # ──────────────────────────────────────────────
    # set_default_gestation
    # ──────────────────────────────────────────────

    def test_female_gets_default_vide(self):
        """Female animal without etat_gestation should default to VIDE"""
        doc = self._make_animal(categorie="VACHE")
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.etat_gestation, "VIDE")

    def test_male_no_default_gestation(self):
        """Male animal should NOT get default gestation"""
        doc = self._make_animal(categorie="VEAU")
        doc.insert(ignore_permissions=True)
        self.assertFalse(doc.etat_gestation)

    def test_genisse_gets_default_vide(self):
        doc = self._make_animal(categorie="GENISSE")
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.etat_gestation, "VIDE")

    # ──────────────────────────────────────────────
    # protect_status_fields
    # ──────────────────────────────────────────────

    def test_protect_etat_gestation_manual_change(self):
        """Manually changing etat_gestation on existing animal must fail"""
        doc = self._make_animal()
        doc.insert(ignore_permissions=True)

        doc.reload()
        doc.etat_gestation = "GESTANTE"
        with self.assertRaises(frappe.exceptions.ValidationError):
            doc.save(ignore_permissions=True)
        frappe.db.rollback()

    def test_protect_etat_lactation_manual_change(self):
        """Manually changing etat_lactation on existing animal must fail"""
        doc = self._make_animal()
        doc.insert(ignore_permissions=True)

        doc.reload()
        doc.etat_lactation = "EN_PRODUCTION"
        with self.assertRaises(frappe.exceptions.ValidationError):
            doc.save(ignore_permissions=True)
        frappe.db.rollback()

    def test_protect_status_fields_skipped_on_new(self):
        """Protection should not apply on insert (new document)"""
        doc = self._make_animal()
        # This should succeed - new doc, no protection
        doc.insert(ignore_permissions=True)
        self.assertTrue(doc.name)

    def test_protect_status_fields_skipped_with_flag(self):
        """Protection should be skipped when ignore_validate flag is set"""
        doc = self._make_animal()
        doc.insert(ignore_permissions=True)

        doc.reload()
        doc.flags.ignore_validate = True
        doc.etat_gestation = "GESTANTE"
        doc.save(ignore_permissions=True)
        self.assertEqual(doc.etat_gestation, "GESTANTE")

    # ──────────────────────────────────────────────
    # protect_reproduction_fields
    # ──────────────────────────────────────────────

    def test_protect_id_ia_fecondante_manual_change(self):
        """Manually changing id_ia_fecondante on existing animal must fail"""
        doc = self._make_animal()
        doc.insert(ignore_permissions=True)

        doc.reload()
        doc.id_ia_fecondante = "some-fake-ia"
        with self.assertRaises(frappe.exceptions.ValidationError):
            doc.save(ignore_permissions=True)
        frappe.db.rollback()

    def test_protect_date_velage_prevue_manual_change(self):
        doc = self._make_animal()
        doc.insert(ignore_permissions=True)

        doc.reload()
        doc.date_velage_prevue = today()
        with self.assertRaises(frappe.exceptions.ValidationError):
            doc.save(ignore_permissions=True)
        frappe.db.rollback()

    def test_protect_date_tarissement_manual_change(self):
        doc = self._make_animal()
        doc.insert(ignore_permissions=True)

        doc.reload()
        doc.date_tarissement = today()
        with self.assertRaises(frappe.exceptions.ValidationError):
            doc.save(ignore_permissions=True)
        frappe.db.rollback()

    def test_protect_reproduction_fields_skipped_on_new(self):
        """Reproduction protection should not apply on insert"""
        doc = self._make_animal()
        doc.insert(ignore_permissions=True)
        self.assertTrue(doc.name)

    def test_protect_reproduction_fields_skipped_with_flag(self):
        """Reproduction protection skipped with ignore_validate"""
        doc = self._make_animal()
        doc.insert(ignore_permissions=True)

        doc.reload()
        doc.flags.ignore_validate = True
        doc.date_velage_prevue = today()
        doc.save(ignore_permissions=True)
        self.assertEqual(str(doc.date_velage_prevue), today())

    # ──────────────────────────────────────────────
    # save without changes (no false positives)
    # ──────────────────────────────────────────────

    def test_save_without_changes_succeeds(self):
        """Re-saving an existing animal with no field changes should succeed"""
        doc = self._make_animal()
        doc.insert(ignore_permissions=True)

        doc.reload()
        doc.save(ignore_permissions=True)  # no changes, should not raise
        self.assertTrue(doc.name)

    # ──────────────────────────────────────────────
    # before_rename / after_rename
    # ──────────────────────────────────────────────

    def test_rename_to_valid_10_digits(self):
        doc = self._make_animal(identification_tn="TEMP-50")
        doc.insert(ignore_permissions=True)

        new_name = "5555566666"
        frappe.rename_doc("Animal", doc.name, new_name, force=True)
        renamed = frappe.get_doc("Animal", new_name)
        self.assertEqual(renamed.nom_metier, "6666")

    def test_rename_to_valid_temp(self):
        doc = self._make_animal(identification_tn="TEMP-51")
        doc.insert(ignore_permissions=True)

        new_name = "TEMP-77"
        frappe.rename_doc("Animal", doc.name, new_name, force=True)
        renamed = frappe.get_doc("Animal", new_name)
        self.assertEqual(renamed.nom_metier, "TEMP-77")

    def test_rename_to_invalid_raises(self):
        doc = self._make_animal(identification_tn="TEMP-52")
        doc.insert(ignore_permissions=True)

        with self.assertRaises(frappe.exceptions.ValidationError):
            frappe.rename_doc("Animal", doc.name, "INVALID", force=True)
        frappe.db.rollback()

    # ──────────────────────────────────────────────
    # is_valid_identification_tn (module-level function)
    # ──────────────────────────────────────────────

    def test_is_valid_identification_tn_function(self):
        from hmd_agro.hmd_agro.doctype.animal.animal import is_valid_identification_tn

        # Valid cases
        self.assertTrue(is_valid_identification_tn("1234567890"))
        self.assertTrue(is_valid_identification_tn("TEMP-01"))
        self.assertTrue(is_valid_identification_tn("TEMP-99"))
        self.assertTrue(is_valid_identification_tn(None))
        self.assertTrue(is_valid_identification_tn(""))

        # Invalid cases
        self.assertFalse(is_valid_identification_tn("12345"))
        self.assertFalse(is_valid_identification_tn("TEMP-1"))
        self.assertFalse(is_valid_identification_tn("TEMP-123"))
        self.assertFalse(is_valid_identification_tn("ABCDEFGHIJ"))
        self.assertFalse(is_valid_identification_tn("FR1234567890"))

    # ──────────────────────────────────────────────
    # Mandatory fields from JSON (reqd: 1)
    # ──────────────────────────────────────────────

    def test_missing_identification_tn_raises(self):
        doc = self._make_animal(identification_tn=None)
        with self.assertRaises((frappe.exceptions.MandatoryError, frappe.exceptions.ValidationError)):
            doc.insert(ignore_permissions=True)
        frappe.db.rollback()

    def test_invalid_race_raises(self):
        """Setting an invalid race value should fail Select validation."""
        doc = self._make_animal(race="INVALID_RACE")
        with self.assertRaises(frappe.exceptions.ValidationError):
            doc.insert(ignore_permissions=True)
        frappe.db.rollback()

    def test_missing_date_naissance_raises(self):
        doc = self._make_animal(date_naissance=None)
        with self.assertRaises(frappe.exceptions.MandatoryError):
            doc.insert(ignore_permissions=True)
        frappe.db.rollback()

    def test_invalid_categorie_raises(self):
        """Setting an invalid categorie value should fail Select validation."""
        doc = self._make_animal(categorie="INVALID_CATEGORIE")
        with self.assertRaises(frappe.exceptions.ValidationError):
            doc.insert(ignore_permissions=True)
        frappe.db.rollback()

    def test_missing_id_pere_raises(self):
        doc = self._make_animal(id_pere=None)
        with self.assertRaises(frappe.exceptions.MandatoryError):
            doc.insert(ignore_permissions=True)
        frappe.db.rollback()

    def test_missing_id_lot_raises(self):
        doc = self._make_animal(id_lot=None)
        with self.assertRaises(frappe.exceptions.MandatoryError):
            doc.insert(ignore_permissions=True)
        frappe.db.rollback()

    def test_missing_statut_uses_default(self):
        """Statut has default ACTIF, so not providing it should still work"""
        doc = self._make_animal()
        del doc.statut  # remove it so default kicks in
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.statut, "ACTIF")

    # ──────────────────────────────────────────────
    # Full valid animal creation (integration)
    # ──────────────────────────────────────────────

    def test_create_valid_non_achat_vache(self):
        """Full valid non-achat VACHE creation"""
        doc = self._make_animal(
            identification_tn="TEMP-60",
            categorie="VACHE",
            est_achat=0,
            id_mere="8000099901",
        )
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.sexe, "F")
        self.assertEqual(doc.etat_gestation, "VIDE")
        self.assertEqual(doc.nom_metier, "TEMP-60")
        self.assertEqual(doc.statut, "ACTIF")

    def test_create_valid_achat_genisse(self):
        """Full valid achat GENISSE creation"""
        doc = self._make_animal(
            identification_tn="TEMP-61",
            categorie="GENISSE",
            est_achat=1,
            id_mere=None,
            id_mere_externe=self.mere_externe,
            date_entree=add_days(today(), -50),
        )
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.sexe, "F")
        self.assertEqual(doc.etat_gestation, "VIDE")

    def test_create_valid_male_veau(self):
        """Full valid male VEAU creation"""
        doc = self._make_animal(
            identification_tn="TEMP-62",
            categorie="VEAU",
            est_achat=0,
            id_mere="8000099901",
        )
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.sexe, "M")
        self.assertFalse(doc.etat_gestation)
