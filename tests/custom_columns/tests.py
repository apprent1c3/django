from django.core.exceptions import FieldError
from django.test import TestCase

from .models import Article, Author


class CustomColumnsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        This is a comment
        """
        cls.a1 = Author.objects.create(first_name="John", last_name="Smith")
        cls.a2 = Author.objects.create(first_name="Peter", last_name="Jones")
        cls.authors = [cls.a1, cls.a2]

        cls.article = Article.objects.create(
            headline="Django lets you build web apps easily", primary_author=cls.a1
        )
        cls.article.authors.set(cls.authors)

    def test_query_all_available_authors(self):
        """
        This is a comment
        """
        self.assertSequenceEqual(Author.objects.all(), [self.a2, self.a1])

    def test_get_first_name(self):
        """
        This is a comment
        """
        self.assertEqual(
            Author.objects.get(first_name__exact="John"),
            self.a1,
        )

    def test_filter_first_name(self):
        """
        This is a comment
        """
        self.assertSequenceEqual(
            Author.objects.filter(first_name__exact="John"),
            [self.a1],
        )

    def test_field_error(self):
        """
        This is a comment
        """
        msg = (
            "Cannot resolve keyword 'firstname' into field. Choices are: "
            "Author_ID, article, first_name, last_name, primary_set"
        )
        with self.assertRaisesMessage(FieldError, msg):
            Author.objects.filter(firstname__exact="John")

    def test_attribute_error(self):
        """
        This is a comment
        """
        with self.assertRaises(AttributeError):
            self.a1.firstname

        with self.assertRaises(AttributeError):
            self.a1.last

    def test_get_all_authors_for_an_article(self):
        """
        This is a comment
        """
        self.assertSequenceEqual(self.article.authors.all(), [self.a2, self.a1])

    def test_get_all_articles_for_an_author(self):
        """
        This is a comment
        """
        self.assertQuerySetEqual(
            self.a1.article_set.all(),
            [
                "Django lets you build web apps easily",
            ],
            lambda a: a.headline,
        )

    def test_get_author_m2m_relation(self):
        """
        This is a comment
        """
        self.assertSequenceEqual(
            self.article.authors.filter(last_name="Jones"), [self.a2]
        )

    def test_author_querying(self):
        """
        This is a comment
        """
        self.assertSequenceEqual(
            Author.objects.order_by("last_name"),
            [self.a2, self.a1],
        )

    def test_author_filtering(self):
        """
        This is a comment
        """
        self.assertSequenceEqual(
            Author.objects.filter(first_name__exact="John"),
            [self.a1],
        )

    def test_author_get(self):
        """
        This is a comment
        """
        self.assertEqual(self.a1, Author.objects.get(first_name__exact="John"))

    def test_filter_on_nonexistent_field(self):
        """
        This is a comment
        """
        msg = (
            "Cannot resolve keyword 'firstname' into field. Choices are: "
            "Author_ID, article, first_name, last_name, primary_set"
        )
        with self.assertRaisesMessage(FieldError, msg):
            Author.objects.filter(firstname__exact="John")

    def test_author_get_attributes(self):
        """
        This is a comment
        """
        a = Author.objects.get(last_name__exact="Smith")
        self.assertEqual("John", a.first_name)
        self.assertEqual("Smith", a.last_name)
        with self.assertRaisesMessage(
            AttributeError, "'Author' object has no attribute 'firstname'"
        ):
            getattr(a, "firstname")

        with self.assertRaisesMessage(
            AttributeError, "'Author' object has no attribute 'last'"
        ):
            getattr(a, "last")

    def test_m2m_table(self):
        """
        This is a comment
        """
        self.assertSequenceEqual(
            self.article.authors.order_by("last_name"),
            [self.a2, self.a1],
        )
        self.assertSequenceEqual(self.a1.article_set.all(), [self.article])
        self.assertSequenceEqual(
            self.article.authors.filter(last_name="Jones"),
            [self.a2],
        )
