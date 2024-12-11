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

        Sets up test data for the class.

        This class method creates initial data in the database, including two authors:
        John Smith (with alias 'smithj') and Rhonda (with alias 'Rhonda').
        The method is intended to be used in a testing context to provide a common set of data for test cases.

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

        Tests that a NullIf annotation correctly handles null arguments.

        This test verifies that when the 'name' field is null, the NullIf annotation
        returns the alternative value instead of null, and checks the annotated 
        results against an expected list of authors.

        """
        authors = Author.objects.annotate(
            nullif=NullIf("name", Value(None))
        ).values_list("nullif")
        self.assertCountEqual(authors, [("John Smith",), ("Rhonda",)])

    def test_too_few_args(self):
        """
        Tests that the NullIf function raises a TypeError when too few arguments are provided.

        Checks that a TypeError is raised with a specific error message when NullIf is called with only one argument, instead of the required two.

        The expected error message indicates that NullIf must be given exactly two arguments. This test ensures that the function properly handles invalid input and provides a clear error message to the user.
        """
        msg = "'NullIf' takes exactly 2 arguments (1 given)"
        with self.assertRaisesMessage(TypeError, msg):
            NullIf("name")

    @skipUnless(connection.vendor == "oracle", "Oracle specific test for NULL-literal")
    def test_null_literal(self):
        """

        Tests the handling of NULL literals in Oracle databases.

        This test case verifies that attempting to use a Value(None) expression
        in an Oracle database raises a ValueError, as Oracle does not support
        this syntax. Specifically, it checks that annotating a query with a
        NullIf expression containing a Value(None) raises the expected error
        message when the query is executed.

        """
        msg = "Oracle does not allow Value(None) for expression1."
        with self.assertRaisesMessage(ValueError, msg):
            list(
                Author.objects.annotate(nullif=NullIf(Value(None), "name")).values_list(
                    "nullif"
                )
            )
