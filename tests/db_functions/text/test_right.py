from django.db import connection
from django.db.models import IntegerField, Value
from django.db.models.functions import Length, Lower, Right
from django.test import TestCase

from ..models import Author


class RightTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Set up test data for the application.

        This class method creates a set of predefined authors in the database, 
        which can be used for testing purposes. The authors created include 
        'John Smith' with an alias 'smithj' and 'Rhonda'. This method is 
        typically called once before running a series of tests to ensure 
        a consistent set of test data is available.

        Returns:
            None

        Note:
            This method should be used in conjunction with a testing framework,
            and is not intended for use in production environments.
        """
        Author.objects.create(name="John Smith", alias="smithj")
        Author.objects.create(name="Rhonda")

    def test_basic(self):
        """

        Tests basic database operations involving author data.

        This test case checks the functionality of annotating author objects with a part of their name and 
        ordering them accordingly. It also verifies the update operation on author aliases based on their names.

        The following scenarios are covered:

        * Annotating author names with a right part of the string (5 characters)
        * Ordering authors by their names and verifying the result
        * Updating author aliases based on their names when the alias is null
        * Verifying the updated author aliases

        """
        authors = Author.objects.annotate(name_part=Right("name", 5))
        self.assertQuerySetEqual(
            authors.order_by("name"), ["Smith", "honda"], lambda a: a.name_part
        )
        # If alias is null, set it to the first 2 lower characters of the name.
        Author.objects.filter(alias__isnull=True).update(alias=Lower(Right("name", 2)))
        self.assertQuerySetEqual(
            authors.order_by("name"), ["smithj", "da"], lambda a: a.alias
        )

    def test_invalid_length(self):
        """
        Tests that an exception is raised when the 'length' parameter is invalid.

        This test verifies that a ValueError is raised with a specific error message
        when attempting to use the Right function with a 'length' value less than or equal to 0.

        """
        with self.assertRaisesMessage(ValueError, "'length' must be greater than 0"):
            Author.objects.annotate(raises=Right("name", 0))

    def test_zero_length(self):
        """
        Tests the behavior of the Author model when the length of an annotated field 
        ('name_part') is zero.

        Verifies that the 'name_part' annotation, which is calculated by taking the 
        difference in length between the 'name' and 'alias' fields, handles cases where 
        this difference is zero or results in an empty string, depending on the database 
        backend's interpretation of empty strings.
        """
        Author.objects.create(name="Tom", alias="tom")
        authors = Author.objects.annotate(
            name_part=Right("name", Length("name") - Length("alias"))
        )
        self.assertQuerySetEqual(
            authors.order_by("name"),
            [
                "mith",
                "" if connection.features.interprets_empty_strings_as_nulls else None,
                "",
            ],
            lambda a: a.name_part,
        )

    def test_expressions(self):
        authors = Author.objects.annotate(
            name_part=Right("name", Value(3, output_field=IntegerField()))
        )
        self.assertQuerySetEqual(
            authors.order_by("name"), ["ith", "nda"], lambda a: a.name_part
        )
