from unittest import skipUnless

from django.db import connection
from django.db.models import CharField, TextField
from django.db.models import Value as V
from django.db.models.functions import Concat, ConcatPair, Upper
from django.test import TestCase
from django.utils import timezone

from ..models import Article, Author

lorem_ipsum = """
    Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod
    tempor incididunt ut labore et dolore magna aliqua."""


class ConcatTests(TestCase):
    def test_basic(self):
        Author.objects.create(name="Jayden")
        Author.objects.create(name="John Smith", alias="smithj", goes_by="John")
        Author.objects.create(name="Margaret", goes_by="Maggie")
        Author.objects.create(name="Rhonda", alias="adnohR")
        authors = Author.objects.annotate(joined=Concat("alias", "goes_by"))
        self.assertQuerySetEqual(
            authors.order_by("name"),
            [
                "",
                "smithjJohn",
                "Maggie",
                "adnohR",
            ],
            lambda a: a.joined,
        )

    def test_gt_two_expressions(self):
        """
        Tests that attempting to use the Concat function with less than two expressions raises a ValueError.

        This test case validates the minimum requirement for the Concat function, 
        ensuring it correctly handles invalid input and provides a meaningful error message 
        when the number of expressions is insufficient. The error message should indicate 
        that Concat must be used with at least two expressions.
        """
        with self.assertRaisesMessage(
            ValueError, "Concat must take at least two expressions"
        ):
            Author.objects.annotate(joined=Concat("alias"))

    def test_many(self):
        """
        Tests the concatenation of author names and aliases in a queryset.

        Checks that authors are correctly ordered by their full name and that their 
        names and aliases are concatenated as expected. The function verifies that 
        authors without an alias are still included in the results, with an empty 
        alias field in the concatenated string.

        This test ensures that the annotate function is working correctly with 
        conditional fields, such as 'goes_by', and that the results are as expected 
        when ordering by the 'name' field.
        """
        Author.objects.create(name="Jayden")
        Author.objects.create(name="John Smith", alias="smithj", goes_by="John")
        Author.objects.create(name="Margaret", goes_by="Maggie")
        Author.objects.create(name="Rhonda", alias="adnohR")
        authors = Author.objects.annotate(
            joined=Concat("name", V(" ("), "goes_by", V(")"), output_field=CharField()),
        )
        self.assertQuerySetEqual(
            authors.order_by("name"),
            [
                "Jayden ()",
                "John Smith (John)",
                "Margaret (Maggie)",
                "Rhonda ()",
            ],
            lambda a: a.joined,
        )

    def test_mixed_char_text(self):
        Article.objects.create(
            title="The Title", text=lorem_ipsum, written=timezone.now()
        )
        article = Article.objects.annotate(
            title_text=Concat("title", V(" - "), "text", output_field=TextField()),
        ).get(title="The Title")
        self.assertEqual(article.title + " - " + article.text, article.title_text)
        # Wrap the concat in something else to ensure that text is returned
        # rather than bytes.
        article = Article.objects.annotate(
            title_text=Upper(
                Concat("title", V(" - "), "text", output_field=TextField())
            ),
        ).get(title="The Title")
        expected = article.title + " - " + article.text
        self.assertEqual(expected.upper(), article.title_text)

    @skipUnless(
        connection.vendor in ("sqlite", "postgresql"),
        "SQLite and PostgreSQL specific implementation detail.",
    )
    def test_coalesce_idempotent(self):
        """

        Tests whether the coalesce method is idempotent when used with ConcatPair instances.

        This method checks that applying the coalesce method to a ConcatPair does not 
        alter the original pair's behavior when flattened, both before and after 
        coalescing. The test specifically verifies that the number of elements 
        produced by the flatten method remains consistent, before and after 
        applying coalesce, ensuring that coalescing does not have unintended side 
        effects on the original pair's state.

        Note: This test is specific to SQLite and PostgreSQL due to implementation 
        details of these databases.

        """
        pair = ConcatPair(V("a"), V("b"))
        # Check nodes counts
        self.assertEqual(len(list(pair.flatten())), 3)
        self.assertEqual(
            len(list(pair.coalesce().flatten())), 7
        )  # + 2 Coalesce + 2 Value()
        self.assertEqual(len(list(pair.flatten())), 3)

    def test_sql_generation_idempotency(self):
        """

        Tests the idempotency of SQL generation for a query with annotations.

        Verifies that generating the SQL query string for an annotated queryset is
        equivalent to generating the SQL query string for the same queryset after
        evaluating the entire result set, ensuring that the SQL generation process
        is idempotent and does not produce different results due to the evaluation
        of the queryset.

        """
        qs = Article.objects.annotate(description=Concat("title", V(": "), "summary"))
        # Multiple compilations should not alter the generated query.
        self.assertEqual(str(qs.query), str(qs.all().query))

    def test_concat_non_str(self):
        """
        Tests the concatenation of non-string fields in a Django ORM query, verifying that the output is correctly formatted and the database query is optimized to use a single query. 

        The function checks if the Concat database function is used to join name, alias, and age fields with a custom separator, and the result is of TextField type. It also ensures that the generated SQL query is vendor-specific, handling PostgreSQL's requirement for explicit type casting to text.
        """
        Author.objects.create(name="The Name", age=42)
        with self.assertNumQueries(1) as ctx:
            author = Author.objects.annotate(
                name_text=Concat(
                    "name", V(":"), "alias", V(":"), "age", output_field=TextField()
                ),
            ).get()
        self.assertEqual(author.name_text, "The Name::42")
        # Only non-string columns are casted on PostgreSQL.
        self.assertEqual(
            ctx.captured_queries[0]["sql"].count("::text"),
            1 if connection.vendor == "postgresql" else 0,
        )
