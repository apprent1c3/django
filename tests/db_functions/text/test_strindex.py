from django.db.models import Value
from django.db.models.functions import StrIndex
from django.test import TestCase
from django.utils import timezone

from ..models import Article, Author


class StrIndexTests(TestCase):
    def test_annotate_charfield(self):
        """

        Tests the usage of StrIndex annotation on a CharacterField to find the index of a substring.

        This test case creates a set of authors, annotates their names with the index of 'R.', 
        and then verifies that the results are correct when ordered by the author's name.

        The test checks if the annotation correctly identifies the index of 'R.' in each author's name, 
        providing a way to verify the functionality of StrIndex with CharacterFields in queries.

        """
        Author.objects.create(name="George. R. R. Martin")
        Author.objects.create(name="J. R. R. Tolkien")
        Author.objects.create(name="Terry Pratchett")
        authors = Author.objects.annotate(fullstop=StrIndex("name", Value("R.")))
        self.assertQuerySetEqual(
            authors.order_by("name"), [9, 4, 0], lambda a: a.fullstop
        )

    def test_annotate_textfield(self):
        Article.objects.create(
            title="How to Django",
            text="This is about How to Django.",
            written=timezone.now(),
        )
        Article.objects.create(
            title="How to Tango",
            text="Won't find anything here.",
            written=timezone.now(),
        )
        articles = Article.objects.annotate(title_pos=StrIndex("text", "title"))
        self.assertQuerySetEqual(
            articles.order_by("title"), [15, 0], lambda a: a.title_pos
        )

    def test_order_by(self):
        """
        Tests the order_by functionality with StrIndex lookup on the 'name' field of the Author model.

        This test case verifies that authors are correctly ordered based on the presence of a substring ('R.') in their names.
        The test checks both ascending and descending order, ensuring that the results are as expected.

        Args:
            None

        Returns:
            None

        Notes:
            The test creates several Author instances, then queries the database to retrieve them in order of the 'R.' substring's presence in their names.
            The ordering is checked in both ascending and descending directions, and the results are compared to the expected output.
        """
        Author.objects.create(name="Terry Pratchett")
        Author.objects.create(name="J. R. R. Tolkien")
        Author.objects.create(name="George. R. R. Martin")
        self.assertQuerySetEqual(
            Author.objects.order_by(StrIndex("name", Value("R.")).asc()),
            [
                "Terry Pratchett",
                "J. R. R. Tolkien",
                "George. R. R. Martin",
            ],
            lambda a: a.name,
        )
        self.assertQuerySetEqual(
            Author.objects.order_by(StrIndex("name", Value("R.")).desc()),
            [
                "George. R. R. Martin",
                "J. R. R. Tolkien",
                "Terry Pratchett",
            ],
            lambda a: a.name,
        )

    def test_unicode_values(self):
        """

        Tests the handling of Unicode values in the Author model's name field.

        This test creates several authors with names containing Japanese characters,
        and then uses the StrIndex annotation to find the index of a specific character ('リ') within each author's name.
        The results are then ordered by the author's name and compared to the expected indices.

        The purpose of this test is to ensure that the model correctly handles Unicode strings and can accurately find character indices within them.

        """
        Author.objects.create(name="ツリー")
        Author.objects.create(name="皇帝")
        Author.objects.create(name="皇帝 ツリー")
        authors = Author.objects.annotate(sb=StrIndex("name", Value("リ")))
        self.assertQuerySetEqual(authors.order_by("name"), [2, 0, 5], lambda a: a.sb)

    def test_filtering(self):
        """
        Tests filtering of authors based on the presence of a middle name.

        This test case creates sample authors and then filters them based on whether their name contains a middle name.
        The filter uses a database function to extract the index of a specific middle name substring, and then applies a comparison filter to retrieve authors with a matching middle name.
        The expected result is verified using an assertion that checks the query set for the correct author names.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the filtered query set does not match the expected result.
        """
        Author.objects.create(name="George. R. R. Martin")
        Author.objects.create(name="Terry Pratchett")
        self.assertQuerySetEqual(
            Author.objects.annotate(middle_name=StrIndex("name", Value("R."))).filter(
                middle_name__gt=0
            ),
            ["George. R. R. Martin"],
            lambda a: a.name,
        )
