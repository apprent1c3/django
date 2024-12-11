from django.db.models import CharField
from django.db.models.functions import LTrim, RTrim, Trim
from django.test import TestCase
from django.test.utils import register_lookup

from ..models import Author


class TrimTests(TestCase):
    def test_trim(self):
        """

        Tests the database functions for removing leading and trailing whitespace from strings.

        The function checks the usage of left trim (LTrim), right trim (RTrim), and trim (Trim)
        functions on a PostgreSQL database. It creates test data with leading and trailing
        whitespace and then verifies that the trim functions correctly remove the whitespace
        as expected. 

        The LTrim function removes leading whitespace, the RTrim function removes trailing
        whitespace, and the Trim function removes both leading and trailing whitespace.

        """
        Author.objects.create(name="  John ", alias="j")
        Author.objects.create(name="Rhonda", alias="r")
        authors = Author.objects.annotate(
            ltrim=LTrim("name"),
            rtrim=RTrim("name"),
            trim=Trim("name"),
        )
        self.assertQuerySetEqual(
            authors.order_by("alias"),
            [
                ("John ", "  John", "John"),
                ("Rhonda", "Rhonda", "Rhonda"),
            ],
            lambda a: (a.ltrim, a.rtrim, a.trim),
        )

    def test_trim_transform(self):
        """
        Tests the trimming functionality of string transforms (LTrim, RTrim, Trim) on the Author model's name field. 
        Verifies that each transform correctly removes leading and/or trailing whitespace from the field, 
        enabling accurate filtering of Author instances based on trimmed names.
        """
        Author.objects.create(name=" John  ")
        Author.objects.create(name="Rhonda")
        tests = (
            (LTrim, "John  "),
            (RTrim, " John"),
            (Trim, "John"),
        )
        for transform, trimmed_name in tests:
            with self.subTest(transform=transform):
                with register_lookup(CharField, transform):
                    authors = Author.objects.filter(
                        **{"name__%s" % transform.lookup_name: trimmed_name}
                    )
                    self.assertQuerySetEqual(authors, [" John  "], lambda a: a.name)
