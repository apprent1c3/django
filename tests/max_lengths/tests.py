import unittest

from django.test import TestCase

from .models import PersonWithCustomMaxLengths, PersonWithDefaultMaxLengths


class MaxLengthArgumentsTests(unittest.TestCase):
    def verify_max_length(self, model, field, length):
        self.assertEqual(model._meta.get_field(field).max_length, length)

    def test_default_max_lengths(self):
        self.verify_max_length(PersonWithDefaultMaxLengths, "email", 254)
        self.verify_max_length(PersonWithDefaultMaxLengths, "vcard", 100)
        self.verify_max_length(PersonWithDefaultMaxLengths, "homepage", 200)
        self.verify_max_length(PersonWithDefaultMaxLengths, "avatar", 100)

    def test_custom_max_lengths(self):
        """
        Test that the custom max lengths for specific fields in the PersonWithCustomMaxLengths model are correctly enforced.

        This test case validates the maximum allowed lengths for the 'email', 'vcard', 'homepage', and 'avatar' fields, ensuring they match the expected limits of 250 characters. 

        It leverages the verify_max_length method to perform these checks, providing a comprehensive verification of the custom maximum lengths defined for these fields in the PersonWithCustomMaxLengths model.
        """
        self.verify_max_length(PersonWithCustomMaxLengths, "email", 250)
        self.verify_max_length(PersonWithCustomMaxLengths, "vcard", 250)
        self.verify_max_length(PersonWithCustomMaxLengths, "homepage", 250)
        self.verify_max_length(PersonWithCustomMaxLengths, "avatar", 250)


class MaxLengthORMTests(TestCase):
    def test_custom_max_lengths(self):
        """
        Tests the customization of maximum lengths for various profile fields.

        This function verifies that the email, vcard, homepage, and avatar fields can store values up to their customized maximum lengths.
        It creates a new profile instance with each field length set to its maximum allowed value and checks that the values are successfully saved and retrieved.
        """
        args = {
            "email": "someone@example.com",
            "vcard": "vcard",
            "homepage": "http://example.com/",
            "avatar": "me.jpg",
        }

        for field in ("email", "vcard", "homepage", "avatar"):
            new_args = args.copy()
            new_args[field] = (
                "X" * 250
            )  # a value longer than any of the default fields could hold.
            p = PersonWithCustomMaxLengths.objects.create(**new_args)
            self.assertEqual(getattr(p, field), ("X" * 250))
