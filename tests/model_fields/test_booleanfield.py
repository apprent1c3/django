from django import forms
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.test import SimpleTestCase, TestCase

from .models import BooleanModel, FksToBooleans, NullBooleanModel


class BooleanFieldTests(TestCase):
    def _test_get_prep_value(self, f):
        """
        Tests the get_prep_value method for converting input values into boolean representations.

        This test case evaluates the function's ability to handle various input types, including boolean, string, and integer values, as well as the special case of None.

        It verifies that the function correctly maps True-like values (True, '1', 1) to True, False-like values (False, '0', 0) to False, and None to None, ensuring accurate preparation of values for further processing.
        """
        self.assertIs(f.get_prep_value(True), True)
        self.assertIs(f.get_prep_value("1"), True)
        self.assertIs(f.get_prep_value(1), True)
        self.assertIs(f.get_prep_value(False), False)
        self.assertIs(f.get_prep_value("0"), False)
        self.assertIs(f.get_prep_value(0), False)
        self.assertIsNone(f.get_prep_value(None))

    def _test_to_python(self, f):
        """
        Verifies the conversion of a given input to its Python equivalent.

        This method tests the to_python method of an object, ensuring it correctly
        converts integer values to their corresponding boolean representations in Python.

        Specifically, it checks that a value of 1 is converted to True and a value of 0 is
        converted to False, as per Python's standard truthiness rules.
        """
        self.assertIs(f.to_python(1), True)
        self.assertIs(f.to_python(0), False)

    def test_booleanfield_get_prep_value(self):
        self._test_get_prep_value(models.BooleanField())

    def test_nullbooleanfield_get_prep_value(self):
        self._test_get_prep_value(models.BooleanField(null=True))

    def test_booleanfield_to_python(self):
        self._test_to_python(models.BooleanField())

    def test_nullbooleanfield_to_python(self):
        self._test_to_python(models.BooleanField(null=True))

    def test_booleanfield_choices_blank(self):
        """
        BooleanField with choices and defaults doesn't generate a formfield
        with the blank option (#9640, #10549).
        """
        choices = [(1, "Si"), (2, "No")]
        f = models.BooleanField(choices=choices, default=1, null=False)
        self.assertEqual(f.formfield().choices, choices)

    def test_booleanfield_choices_blank_desired(self):
        """
        BooleanField with choices and no default should generated a formfield
        with the blank option.
        """
        choices = [(1, "Si"), (2, "No")]
        f = models.BooleanField(choices=choices)
        self.assertEqual(f.formfield().choices, [("", "---------")] + choices)

    def test_nullbooleanfield_formfield(self):
        """
        Tests that a BooleanField model field with null=True generates a NullBooleanField form field. This ensures that the form field correctly handles null values, providing a tri-state checkbox input for true, false, and unknown states.
        """
        f = models.BooleanField(null=True)
        self.assertIsInstance(f.formfield(), forms.NullBooleanField)

    def test_return_type(self):
        b = BooleanModel.objects.create(bfield=True)
        b.refresh_from_db()
        self.assertIs(b.bfield, True)

        b2 = BooleanModel.objects.create(bfield=False)
        b2.refresh_from_db()
        self.assertIs(b2.bfield, False)

        b3 = NullBooleanModel.objects.create(nbfield=True)
        b3.refresh_from_db()
        self.assertIs(b3.nbfield, True)

        b4 = NullBooleanModel.objects.create(nbfield=False)
        b4.refresh_from_db()
        self.assertIs(b4.nbfield, False)

    def test_select_related(self):
        """
        Boolean fields retrieved via select_related() should return booleans.
        """
        bmt = BooleanModel.objects.create(bfield=True)
        bmf = BooleanModel.objects.create(bfield=False)
        nbmt = NullBooleanModel.objects.create(nbfield=True)
        nbmf = NullBooleanModel.objects.create(nbfield=False)
        m1 = FksToBooleans.objects.create(bf=bmt, nbf=nbmt)
        m2 = FksToBooleans.objects.create(bf=bmf, nbf=nbmf)

        # select_related('fk_field_name')
        ma = FksToBooleans.objects.select_related("bf").get(pk=m1.id)
        self.assertIs(ma.bf.bfield, True)
        self.assertIs(ma.nbf.nbfield, True)

        # select_related()
        mb = FksToBooleans.objects.select_related().get(pk=m1.id)
        mc = FksToBooleans.objects.select_related().get(pk=m2.id)
        self.assertIs(mb.bf.bfield, True)
        self.assertIs(mb.nbf.nbfield, True)
        self.assertIs(mc.bf.bfield, False)
        self.assertIs(mc.nbf.nbfield, False)

    def test_null_default(self):
        """
        A BooleanField defaults to None, which isn't a valid value (#15124).
        """
        boolean_field = BooleanModel._meta.get_field("bfield")
        self.assertFalse(boolean_field.has_default())
        b = BooleanModel()
        self.assertIsNone(b.bfield)
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                b.save()

        nb = NullBooleanModel()
        self.assertIsNone(nb.nbfield)
        nb.save()  # no error


class ValidationTest(SimpleTestCase):
    def test_boolean_field_doesnt_accept_empty_input(self):
        """
        Tests that a BooleanField raises a ValidationError when given empty input.

        This test case verifies the expected behavior of a BooleanField when it
        receives an empty or None value, ensuring that it properly handles invalid input
        and raises an exception as required by the validation rules.

        Args:
            None

        Returns:
            None

        Raises:
            ValidationError: If the input value is empty or None.

        """
        f = models.BooleanField()
        with self.assertRaises(ValidationError):
            f.clean(None, None)

    def test_nullbooleanfield_blank(self):
        """
        NullBooleanField shouldn't throw a validation error when given a value
        of None.
        """
        nullboolean = NullBooleanModel(nbfield=None)
        nullboolean.full_clean()
