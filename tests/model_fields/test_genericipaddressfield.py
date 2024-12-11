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
        Tests that a blank string for the IP address is saved as null in the database.

        This test case verifies that when an empty string is assigned to the IP address,
        it is correctly stored as null in the database. It checks this behavior both
        when creating a new object and when updating an existing one, ensuring that the
        database accurately reflects the null value.
        """
        o = GenericIPAddress.objects.create(ip="")
        o.refresh_from_db()
        self.assertIsNone(o.ip)
        GenericIPAddress.objects.update(ip="")
        o.refresh_from_db()
        self.assertIsNone(o.ip)

    def test_save_load(self):
        """
        Tests the save and load functionality of a GenericIPAddress instance.

        Verifies that an instance of GenericIPAddress can be successfully saved to the database and then loaded back, ensuring that the saved and loaded instances have the same IP address.

        This test case ensures data consistency and integrity by checking that the IP address of the saved instance matches the IP address of the loaded instance, confirming that the data is correctly persisted and retrieved from the database.
        """
        instance = GenericIPAddress.objects.create(ip="::1")
        loaded = GenericIPAddress.objects.get()
        self.assertEqual(loaded.ip, instance.ip)
