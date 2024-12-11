from unittest import skipUnless

from django.db import connection
from django.db.models import Value
from django.db.models.functions import NullIf
from django.test import TestCase

from ..models import Author


class NullIfTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for the class, creating a set of predefined authors in the database.

        This method is intended to be used as a class setup method, providing a consistent set of authors for testing purposes.
        The created authors include 'John Smith' (alias 'smithj') and 'Rhonda' (alias 'Rhonda'), which can be used as test data in subsequent tests.

        """
        Author.objects.create(name="John Smith", alias="smithj")
        Author.objects.create(name="Rhonda", alias="Rhonda")

    def test_basic(self):
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
        """

        Tests the behavior of annotating query results with a NullIf expression.

        This test verifies that the NullIf function correctly identifies and handles null values.
        It checks the annotated results against expected values to ensure that the function behaves as expected.

        The NullIf function is used to replace a specified value (in this case, None) with a null value.
        In this test, it is used to check if the 'name' field of Author objects is None, and if so, replace it with null.

        The test asserts that the resulting annotated values match the expected output.

        """
        authors = Author.objects.annotate(
            nullif=NullIf("name", Value(None))
        ).values_list("nullif")
        self.assertCountEqual(authors, [("John Smith",), ("Rhonda",)])

    def test_too_few_args(self):
        """
        Tests that the NullIf function raises a TypeError when called with an insufficient number of arguments. 
        Verifies the error message is correctly formatted, specifically checking that it reports the function requires exactly 2 arguments but only received 1.
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
