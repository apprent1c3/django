from django.core.exceptions import ValidationError
from django.db import models
from django.test import TestCase

from .models import GenericIPAddress


class GenericIPAddressFieldTests(TestCase):
    def test_genericipaddressfield_formfield_protocol(self):
        """
        GenericIPAddressField with a specified protocol does not generate a
        formfield without a protocol.
        """
        model_field = models.GenericIPAddressField(protocol="IPv4")
        form_field = model_field.formfield()
        with self.assertRaises(ValidationError):
            form_field.clean("::1")
        model_field = models.GenericIPAddressField(protocol="IPv6")
        form_field = model_field.formfield()
        with self.assertRaises(ValidationError):
            form_field.clean("127.0.0.1")

    def test_null_value(self):
        """
        Null values should be resolved to None.
        """
        GenericIPAddress.objects.create()
        o = GenericIPAddress.objects.get()
        self.assertIsNone(o.ip)

    def test_blank_string_saved_as_null(self):
        """
        Tests that a blank string for an IP address is saved as null in the database.

        Verifies that when a GenericIPAddress object is created with an empty string,
        it is stored as null, and that this behavior is consistent when updating
        existing objects. Ensures data integrity by checking the IP address value
        after refreshing the object from the database.

        """
        o = GenericIPAddress.objects.create(ip="")
        o.refresh_from_db()
        self.assertIsNone(o.ip)
        GenericIPAddress.objects.update(ip="")
        o.refresh_from_db()
        self.assertIsNone(o.ip)

    def test_save_load(self):
        """

        Tests the save and load functionality of the GenericIPAddress model.

        Ensures that an instance of GenericIPAddress can be successfully saved to the database and then loaded back,
        with its attributes remaining intact. Specifically, it verifies that the IP address is correctly persisted.

        """
        instance = GenericIPAddress.objects.create(ip="::1")
        loaded = GenericIPAddress.objects.get()
        self.assertEqual(loaded.ip, instance.ip)
