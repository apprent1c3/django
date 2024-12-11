from django import forms
from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import UUIDPK


class UUIDPKForm(forms.ModelForm):
    class Meta:
        model = UUIDPK
        fields = "__all__"


class ModelFormBaseTest(TestCase):
    def test_create_save_error(self):
        form = UUIDPKForm({})
        self.assertFalse(form.is_valid())
        msg = "The UUIDPK could not be created because the data didn't validate."
        with self.assertRaisesMessage(ValueError, msg):
            form.save()

    def test_update_save_error(self):
        """
        Tests that updating a UUIDPK instance with invalid data raises a ValueError.

        This test case checks the error handling when attempting to save a UUIDPKForm with
        invalid data. It verifies that the form is invalid, and that saving the form with
        invalid data raises a ValueError with a descriptive error message, indicating that
        the UUIDPK instance cannot be changed due to validation errors.
        """
        obj = UUIDPK.objects.create(name="foo")
        form = UUIDPKForm({}, instance=obj)
        self.assertFalse(form.is_valid())
        msg = "The UUIDPK could not be changed because the data didn't validate."
        with self.assertRaisesMessage(ValueError, msg):
            form.save()

    def test_model_multiple_choice_field_uuid_pk(self):
        """
        Test that the model multiple choice field with a UUID primary key correctly raises a validation error when given an invalid UUID. 

        The test ensures that providing an invalid UUID value to the field results in a ValidationError being raised with a message indicating that the provided value is not a valid UUID.
        """
        f = forms.ModelMultipleChoiceField(UUIDPK.objects.all())
        with self.assertRaisesMessage(
            ValidationError, "“invalid_uuid” is not a valid UUID."
        ):
            f.clean(["invalid_uuid"])
