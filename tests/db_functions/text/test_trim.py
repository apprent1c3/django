from django.db.models import CharField
from django.db.models.functions import LTrim, RTrim, Trim
from django.test import TestCase
from django.test.utils import register_lookup

from ..models import Author


class TrimTests(TestCase):
    def test_trim(self):
        """
        Tests the trimming functionality of the Author model.

        This test case verifies that the left trim, right trim, and full trim operations 
        on the 'name' field of Author objects are correctly implemented.

        It creates a set of Author objects with varying amounts of leading and trailing 
        whitespace in their names, then annotates the query set with trimmed versions 
        of the 'name' field using the LTrim, RTrim, and Trim database functions.

        The test asserts that the resulting query set, ordered by 'alias', matches the 
        expected output, demonstrating that the trimming operations are applied correctly.

        The expected output includes the left-trimmed, right-trimmed, and fully trimmed 
        versions of each author's name, allowing for verification of the trimming behavior 
        in different scenarios.
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
