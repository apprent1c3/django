from django.db.models import Subquery, TextField
from django.db.models.functions import Coalesce, Lower
from django.test import TestCase
from django.utils import timezone

from ..models import Article, Author

lorem_ipsum = """
    Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod
    tempor incididunt ut labore et dolore magna aliqua."""


class CoalesceTests(TestCase):
    def test_basic(self):
        """

        Tests the basic functionality of annotating authors with a display name.

        This test ensures that the display name annotation successfully combines the 
        'alias' and 'name' fields, prioritizing the 'alias' field if it exists. It 
        verifies the expected ordering of authors by their name and checks that the 
        display name is correctly assigned to each author.

        """
        Author.objects.create(name="John Smith", alias="smithj")
        Author.objects.create(name="Rhonda")
        authors = Author.objects.annotate(display_name=Coalesce("alias", "name"))
        self.assertQuerySetEqual(
            authors.order_by("name"), ["smithj", "Rhonda"], lambda a: a.display_name
        )

    def test_gt_two_expressions(self):
        """
        Tests that using the Coalesce function with only one expression raises a ValueError.

        This test case checks that attempting to annotate an Author object with the Coalesce function, 
        passing only a single expression ('alias'), correctly raises a ValueError with a message 
        indicating that Coalesce must take at least two expressions.
        """
        with self.assertRaisesMessage(
            ValueError, "Coalesce must take at least two expressions"
        ):
            Author.objects.annotate(display_name=Coalesce("alias"))

    def test_mixed_values(self):
        """
        Test that the Coalesce database function can successfully mix values from different fields.

        This test case verifies that when both 'summary' and 'text' are present, the value from 'summary' will be selected.
        If 'summary' is missing, it will fall back to 'text'. Additionally, it checks that the function works correctly 
        with different cases (lowercase and original) to ensure the output is as expected.

        The test creates authors and an article with multiple authors, then uses the Coalesce function to create a new 'headline' 
        field that selects the first non-null value from 'summary' or 'text' fields, and checks that the correct headline is 
        returned in the result set when ordered by title.
        """
        a1 = Author.objects.create(name="John Smith", alias="smithj")
        a2 = Author.objects.create(name="Rhonda")
        ar1 = Article.objects.create(
            title="How to Django",
            text=lorem_ipsum,
            written=timezone.now(),
        )
        ar1.authors.add(a1)
        ar1.authors.add(a2)
        # mixed Text and Char
        article = Article.objects.annotate(
            headline=Coalesce("summary", "text", output_field=TextField()),
        )
        self.assertQuerySetEqual(
            article.order_by("title"), [lorem_ipsum], lambda a: a.headline
        )
        # mixed Text and Char wrapped
        article = Article.objects.annotate(
            headline=Coalesce(
                Lower("summary"), Lower("text"), output_field=TextField()
            ),
        )
        self.assertQuerySetEqual(
            article.order_by("title"), [lorem_ipsum.lower()], lambda a: a.headline
        )

    def test_ordering(self):
        Author.objects.create(name="John Smith", alias="smithj")
        Author.objects.create(name="Rhonda")
        authors = Author.objects.order_by(Coalesce("alias", "name"))
        self.assertQuerySetEqual(authors, ["Rhonda", "John Smith"], lambda a: a.name)
        authors = Author.objects.order_by(Coalesce("alias", "name").asc())
        self.assertQuerySetEqual(authors, ["Rhonda", "John Smith"], lambda a: a.name)
        authors = Author.objects.order_by(Coalesce("alias", "name").desc())
        self.assertQuerySetEqual(authors, ["John Smith", "Rhonda"], lambda a: a.name)

    def test_empty_queryset(self):
        """
        Tests the behavior of the Coalesce function when used with empty querysets.

        This function verifies that when an empty queryset is used as an argument to Coalesce,
        the function correctly returns the default value (in this case, 42) instead of None.
        The test covers various ways to create an empty queryset, including using QuerySet.none(),
        QuerySet.filter() with a non-matching condition, and Subquery with an empty queryset.
        Each test case is run in a separate subtest, and the number of database queries is verified to be 1.

        The test assumes the existence of an Author model with a name field, and creates a single author
        instance for the purpose of the test. The Coalesce function is used to annotate a queryset of authors
        with a value that is either the result of the empty queryset or the default value.
        The test then asserts that the annotated value of the first author in the queryset is equal to the default value.
        """
        Author.objects.create(name="John Smith")
        queryset = Author.objects.values("id")
        tests = [
            (queryset.none(), "QuerySet.none()"),
            (queryset.filter(id=0), "QuerySet.filter(id=0)"),
            (Subquery(queryset.none()), "Subquery(QuerySet.none())"),
            (Subquery(queryset.filter(id=0)), "Subquery(Queryset.filter(id=0)"),
        ]
        for empty_query, description in tests:
            with self.subTest(description), self.assertNumQueries(1):
                qs = Author.objects.annotate(annotation=Coalesce(empty_query, 42))
                self.assertEqual(qs.first().annotation, 42)
