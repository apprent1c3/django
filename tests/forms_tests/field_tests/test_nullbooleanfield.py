from django.forms import Form, HiddenInput, NullBooleanField, RadioSelect
from django.test import SimpleTestCase

from . import FormFieldAssertionsMixin


class NullBooleanFieldTest(FormFieldAssertionsMixin, SimpleTestCase):
    def test_nullbooleanfield_clean(self):
        f = NullBooleanField()
        self.assertIsNone(f.clean(""))
        self.assertTrue(f.clean(True))
        self.assertFalse(f.clean(False))
        self.assertIsNone(f.clean(None))
        self.assertFalse(f.clean("0"))
        self.assertTrue(f.clean("1"))
        self.assertIsNone(f.clean("2"))
        self.assertIsNone(f.clean("3"))
        self.assertIsNone(f.clean("hello"))
        self.assertTrue(f.clean("true"))
        self.assertFalse(f.clean("false"))

    def test_nullbooleanfield_2(self):
        # The internal value is preserved if using HiddenInput (#7753).
        """
        Tests the rendering of a form with hidden NullBooleanFields, verifying that the initial values for the fields are correctly translated into HTML hidden input elements.
        """
        class HiddenNullBooleanForm(Form):
            hidden_nullbool1 = NullBooleanField(widget=HiddenInput, initial=True)
            hidden_nullbool2 = NullBooleanField(widget=HiddenInput, initial=False)

        f = HiddenNullBooleanForm()
        self.assertHTMLEqual(
            str(f),
            '<input type="hidden" name="hidden_nullbool1" value="True" '
            'id="id_hidden_nullbool1">'
            '<input type="hidden" name="hidden_nullbool2" value="False" '
            'id="id_hidden_nullbool2">',
        )

    def test_nullbooleanfield_3(self):
        """

        Tests the functionality of a NullBooleanField within a form when its widget is set to HiddenInput.

        This test case verifies that the field can successfully handle hidden input and initial values,
        and that the form's validation and cleaning process correctly sets the boolean value based on the input.

        It checks that the form cleans without errors and that the cleaned data reflects the expected boolean values.

        """
        class HiddenNullBooleanForm(Form):
            hidden_nullbool1 = NullBooleanField(widget=HiddenInput, initial=True)
            hidden_nullbool2 = NullBooleanField(widget=HiddenInput, initial=False)

        f = HiddenNullBooleanForm(
            {"hidden_nullbool1": "True", "hidden_nullbool2": "False"}
        )
        self.assertIsNone(f.full_clean())
        self.assertTrue(f.cleaned_data["hidden_nullbool1"])
        self.assertFalse(f.cleaned_data["hidden_nullbool2"])

    def test_nullbooleanfield_4(self):
        # Make sure we're compatible with MySQL, which uses 0 and 1 for its
        # boolean values (#9609).
        NULLBOOL_CHOICES = (("1", "Yes"), ("0", "No"), ("", "Unknown"))

        class MySQLNullBooleanForm(Form):
            nullbool0 = NullBooleanField(widget=RadioSelect(choices=NULLBOOL_CHOICES))
            nullbool1 = NullBooleanField(widget=RadioSelect(choices=NULLBOOL_CHOICES))
            nullbool2 = NullBooleanField(widget=RadioSelect(choices=NULLBOOL_CHOICES))

        f = MySQLNullBooleanForm({"nullbool0": "1", "nullbool1": "0", "nullbool2": ""})
        self.assertIsNone(f.full_clean())
        self.assertTrue(f.cleaned_data["nullbool0"])
        self.assertFalse(f.cleaned_data["nullbool1"])
        self.assertIsNone(f.cleaned_data["nullbool2"])

    def test_nullbooleanfield_changed(self):
        """
        Checks whether the value of a NullBooleanField has changed.

        This method compares the initial and current values of the NullBooleanField and returns
        True if they are different, and False otherwise. It handles various combinations of 
        Boolean and null values, including edge cases where the initial or current value is 
        a string representation of a Boolean value. The comparison is case-sensitive for 
        string values. 

        It returns True for changes between Boolean and null values, as well as between 
        different Boolean values. It returns False when the initial and current values are 
        the same, including cases where both are null or where both are the same Boolean 
        value, regardless of whether the values are represented as strings or actual Boolean 
        types. 

        This function is useful for detecting changes to a NullBooleanField in a form or 
        other data structure, where the field may have been initially set to null or a 
        Boolean value, and may have been subsequently changed to a different value.
        """
        f = NullBooleanField()
        self.assertTrue(f.has_changed(False, None))
        self.assertTrue(f.has_changed(None, False))
        self.assertFalse(f.has_changed(None, None))
        self.assertFalse(f.has_changed(False, False))
        self.assertTrue(f.has_changed(True, False))
        self.assertTrue(f.has_changed(True, None))
        self.assertTrue(f.has_changed(True, False))
        # HiddenInput widget sends string values for boolean but doesn't clean
        # them in value_from_datadict.
        self.assertFalse(f.has_changed(False, "False"))
        self.assertFalse(f.has_changed(True, "True"))
        self.assertFalse(f.has_changed(None, ""))
        self.assertTrue(f.has_changed(False, "True"))
        self.assertTrue(f.has_changed(True, "False"))
        self.assertTrue(f.has_changed(None, "False"))
