from django.db import connection
from django.db.models import CharField, Value
from django.db.models.functions import Length, Reverse, Trim
from django.test import TestCase
from django.test.utils import register_lookup

from ..models import Author


class ReverseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """

        Setup test data for the class.

        This method is used to create and populate test data before running tests. 
        It creates three author instances with sample data and assigns them to class attributes.

        The authors created are:
            - John Smith, with alias 'smithj'
            - Élena Jordan, with alias 'elena'
            - パイソン (Python), with no alias

        These authors can be used throughout the class for testing purposes.

        """
        cls.john = Author.objects.create(name="John Smith", alias="smithj")
        cls.elena = Author.objects.create(name="Élena Jordan", alias="elena")
        cls.python = Author.objects.create(name="パイソン")

    def test_null(self):
        """

        Tests that the reversal of a relationship (.alias) annotated as 'backward' 
        on an Author object returns the expected value when the related object is null.

        The test verifies that the result is an empty string if the database 
        interprets empty strings as nulls, and None otherwise, ensuring consistent 
        behavior across different database backends.

        """
        author = Author.objects.annotate(backward=Reverse("alias")).get(
            pk=self.python.pk
        )
        self.assertEqual(
            author.backward,
            "" if connection.features.interprets_empty_strings_as_nulls else None,
        )

    def test_basic(self):
        """

        Tests the basic functionality of annotating database query results with reversed strings.

        This test case verifies that the 'backward' annotation correctly reverses the 'name' field of each author,
        and that the 'constant' annotation returns the expected static string for all authors.
        The function checks that the annotated results match the expected output, regardless of the order in which they are returned.

        """
        authors = Author.objects.annotate(
            backward=Reverse("name"),
            constant=Reverse(Value("static string")),
        )
        self.assertQuerySetEqual(
            authors,
            [
                ("John Smith", "htimS nhoJ", "gnirts citats"),
                ("Élena Jordan", "nadroJ anelÉ", "gnirts citats"),
                ("パイソン", "ンソイパ", "gnirts citats"),
            ],
            lambda a: (a.name, a.backward, a.constant),
            ordered=False,
        )

    def test_transform(self):
        """

        Tests the functionality of the `reverse` lookup type on a `CharField`.

        Verifies that the `reverse` lookup correctly filters objects by reversing their
        string values. This includes checking that objects with matching reversed values
        are included in the filtered results and that objects with non-matching reversed
        values are excluded.

        """
        with register_lookup(CharField, Reverse):
            authors = Author.objects.all()
            self.assertCountEqual(
                authors.filter(name__reverse=self.john.name[::-1]), [self.john]
            )
            self.assertCountEqual(
                authors.exclude(name__reverse=self.john.name[::-1]),
                [self.elena, self.python],
            )

    def test_expressions(self):
        """

        Tests the usage of custom expressions in database queries.

        This test case exercises the ``reverse`` and ``length`` lookup types on character fields.
        It verifies that the reverse of a string can be correctly annotated and filtered,
        and that combining multiple lookups yields the expected results.

        The test checks that the ``reverse`` expression produces the correct reversed string,
        and that chaining ``reverse`` and ``length`` lookups filters the results as expected.

        """
        author = Author.objects.annotate(backward=Reverse(Trim("name"))).get(
            pk=self.john.pk
        )
        self.assertEqual(author.backward, self.john.name[::-1])
        with register_lookup(CharField, Reverse), register_lookup(CharField, Length):
            authors = Author.objects.all()
            self.assertCountEqual(
                authors.filter(name__reverse__length__gt=7), [self.john, self.elena]
            )
            self.assertCountEqual(
                authors.exclude(name__reverse__length__gt=7), [self.python]
            )
