from django.db.models import Value
from django.db.models.functions import StrIndex
from django.test import TestCase
from django.utils import timezone

from ..models import Article, Author


class StrIndexTests(TestCase):
    def test_annotate_charfield(self):
        Author.objects.create(name="George. R. R. Martin")
        Author.objects.create(name="J. R. R. Tolkien")
        Author.objects.create(name="Terry Pratchett")
        authors = Author.objects.annotate(fullstop=StrIndex("name", Value("R.")))
        self.assertQuerySetEqual(
            authors.order_by("name"), [9, 4, 0], lambda a: a.fullstop
        )

    def test_annotate_textfield(self):
        """

        Tests the annotation of a queryset of articles to include the position of the article title in the text.

        The test creates two sample articles and then annotates the queryset of articles with the position of the title in the text.
        It then checks that the resulting queryset has the correct title positions, ensuring the annotation has been applied correctly.

        The purpose of this test is to verify that the annotation functionality is working as expected, allowing for the retrieval of
        article title positions within their corresponding text fields.

        """
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

        Test the ordering of Author objects by the index of a specific substring within their names.

        This test case creates a set of Author objects and verifies that they can be sorted
        in ascending and descending order based on the position of the substring 'R.' within
        their names. The sorting is performed using the StrIndex function, which returns the
        position of the substring within the string. The test cases cover both ascending and
        descending ordering, ensuring that the results are as expected.

        The test verifies the correctness of the ordering by comparing the results with the
        expected lists of author names, using the name attribute of each Author object.

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
        Author.objects.create(name="ツリー")
        Author.objects.create(name="皇帝")
        Author.objects.create(name="皇帝 ツリー")
        authors = Author.objects.annotate(sb=StrIndex("name", Value("リ")))
        self.assertQuerySetEqual(authors.order_by("name"), [2, 0, 5], lambda a: a.sb)

    def test_filtering(self):
        Author.objects.create(name="George. R. R. Martin")
        Author.objects.create(name="Terry Pratchett")
        self.assertQuerySetEqual(
            Author.objects.annotate(middle_name=StrIndex("name", Value("R."))).filter(
                middle_name__gt=0
            ),
            ["George. R. R. Martin"],
            lambda a: a.name,
        )
