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
        o = GenericIPAddress.objects.create(ip="")
        o.refresh_from_db()
        self.assertIsNone(o.ip)
        GenericIPAddress.objects.update(ip="")
        o.refresh_from_db()
        self.assertIsNone(o.ip)

    def test_save_load(self):
        """
        Tests the ability to save and load a GenericIPAddress instance.

        Verifies that an instance of GenericIPAddress can be successfully created, saved, 
        and then loaded from the database, ensuring that the IP address is preserved 
        during this process.

        The test checks for data consistency by comparing the IP address of the 
        originally created instance with the IP address of the loaded instance.

        """
        instance = GenericIPAddress.objects.create(ip="::1")
        loaded = GenericIPAddress.objects.get()
        self.assertEqual(loaded.ip, instance.ip)
