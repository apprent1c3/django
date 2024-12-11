from django.db.models import F, Value
from django.db.models.functions import Concat, Replace
from django.test import TestCase

from ..models import Author


class ReplaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for the class, creating instances of Author objects with predefined names.

        This method is used to populate the database with initial data for testing purposes,
        providing a consistent starting point for subsequent tests. The authors 'George R. R. Martin'
        and 'J. R. R. Tolkien' are added to the database by default.

        """
        Author.objects.create(name="George R. R. Martin")
        Author.objects.create(name="J. R. R. Tolkien")

    def test_replace_with_empty_string(self):
        """

        Tests the replacement of a substring with an empty string in a queryset.

        This function verifies that the Replace database function can be used to remove
        a specific substring from a field, in this case, the 'name' field of Author objects.
        The test checks that the replacement is correctly applied to the queryset, 
        resulting in the expected output without the specified substring.

        """
        qs = Author.objects.annotate(
            without_middlename=Replace(F("name"), Value("R. R. "), Value("")),
        )
        self.assertQuerySetEqual(
            qs,
            [
                ("George R. R. Martin", "George Martin"),
                ("J. R. R. Tolkien", "J. Tolkien"),
            ],
            transform=lambda x: (x.name, x.without_middlename),
            ordered=False,
        )

    def test_case_sensitive(self):
        qs = Author.objects.annotate(
            same_name=Replace(F("name"), Value("r. r."), Value(""))
        )
        self.assertQuerySetEqual(
            qs,
            [
                ("George R. R. Martin", "George R. R. Martin"),
                ("J. R. R. Tolkien", "J. R. R. Tolkien"),
            ],
            transform=lambda x: (x.name, x.same_name),
            ordered=False,
        )

    def test_replace_expression(self):
        qs = Author.objects.annotate(
            same_name=Replace(
                Concat(Value("Author: "), F("name")), Value("Author: "), Value("")
            ),
        )
        self.assertQuerySetEqual(
            qs,
            [
                ("George R. R. Martin", "George R. R. Martin"),
                ("J. R. R. Tolkien", "J. R. R. Tolkien"),
            ],
            transform=lambda x: (x.name, x.same_name),
            ordered=False,
        )

    def test_update(self):
        """

        Tests the update functionality by replacing a prefix in author names.

        Replaces the prefix 'R. R. ' with an empty string in all author names and 
        verifies that the updated names match the expected values.

        """
        Author.objects.update(
            name=Replace(F("name"), Value("R. R. "), Value("")),
        )
        self.assertQuerySetEqual(
            Author.objects.all(),
            [
                ("George Martin"),
                ("J. Tolkien"),
            ],
            transform=lambda x: x.name,
            ordered=False,
        )

    def test_replace_with_default_arg(self):
        # The default replacement is an empty string.
        qs = Author.objects.annotate(same_name=Replace(F("name"), Value("R. R. ")))
        self.assertQuerySetEqual(
            qs,
            [
                ("George R. R. Martin", "George Martin"),
                ("J. R. R. Tolkien", "J. Tolkien"),
            ],
            transform=lambda x: (x.name, x.same_name),
            ordered=False,
        )
