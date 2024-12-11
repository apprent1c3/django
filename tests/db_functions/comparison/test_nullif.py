from unittest import skipUnless

from django.db import connection
from django.db.models import Value
from django.db.models.functions import NullIf
from django.test import TestCase

from ..models import Author


class NullIfTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Author.objects.create(name="John Smith", alias="smithj")
        Author.objects.create(name="Rhonda", alias="Rhonda")

    def test_basic(self):
        """
        Tests the basic functionality of annotating authors with a nullif condition.

        This test checks if the 'nullif' annotation correctly handles the case where an author's alias is equal to their name.
        The expected output is a list of tuples containing the 'nullif' values, which are either the author's alias or an empty string/None, 
        depending on the database backend's interpretation of empty strings as nulls.
        """
        authors = Author.objects.annotate(nullif=NullIf("alias", "name")).values_list(
            "nullif"
        )
        self.assertCountEqual(
            authors,
            [
                ("smithj",),
                (
                    (
                        ""
                        if connection.features.interprets_empty_strings_as_nulls
                        else None
                    ),
                ),
            ],
        )

    def test_null_argument(self):
        authors = Author.objects.annotate(
            nullif=NullIf("name", Value(None))
        ).values_list("nullif")
        self.assertCountEqual(authors, [("John Smith",), ("Rhonda",)])

    def test_too_few_args(self):
        """
        Tests that the NullIf class raises a TypeError when instantiated with too few arguments, specifically one argument instead of the required two. The error message checks for the exact string exception \"'NullIf' takes exactly 2 arguments (1 given)\" to ensure the error is correctly identified and reported.
        """
        msg = "'NullIf' takes exactly 2 arguments (1 given)"
        with self.assertRaisesMessage(TypeError, msg):
            NullIf("name")

    @skipUnless(connection.vendor == "oracle", "Oracle specific test for NULL-literal")
    def test_null_literal(self):
        msg = "Oracle does not allow Value(None) for expression1."
        with self.assertRaisesMessage(ValueError, msg):
            list(
                Author.objects.annotate(nullif=NullIf(Value(None), "name")).values_list(
                    "nullif"
                )
            )
