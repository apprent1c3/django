from django.core.exceptions import FieldError
from django.test import TestCase

from .models import Article, Author


class CustomColumnsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a1 = Author.objects.create(first_name="John", last_name="Smith")
        cls.a2 = Author.objects.create(first_name="Peter", last_name="Jones")
        cls.authors = [cls.a1, cls.a2]

        cls.article = Article.objects.create(
            headline="Django lets you build web apps easily", primary_author=cls.a1
        )
        cls.article.authors.set(cls.authors)

    def test_query_all_available_authors(self):
        self.assertSequenceEqual(Author.objects.all(), [self.a2, self.a1])

    def test_get_first_name(self):
        self.assertEqual(
            Author.objects.get(first_name__exact="John"),
            self.a1,
        )

    def test_filter_first_name(self):
        self.assertSequenceEqual(
            Author.objects.filter(first_name__exact="John"),
            [self.a1],
        )

    def test_field_error(self):
        msg = (
            "Cannot resolve keyword 'firstname' into field. Choices are: "
            "Author_ID, article, first_name, last_name, primary_set"
        )
        with self.assertRaisesMessage(FieldError, msg):
            Author.objects.filter(firstname__exact="John")

    def test_attribute_error(self):
        with self.assertRaises(AttributeError):
            self.a1.firstname

        with self.assertRaises(AttributeError):
            self.a1.last

    def test_get_all_authors_for_an_article(self):
        self.assertSequenceEqual(self.article.authors.all(), [self.a2, self.a1])

    def test_get_all_articles_for_an_author(self):
        self.assertQuerySetEqual(
            self.a1.article_set.all(),
            [
                "Django lets you build web apps easily",
            ],
            lambda a: a.headline,
        )

    def test_get_author_m2m_relation(self):
        self.assertSequenceEqual(
            self.article.authors.filter(last_name="Jones"), [self.a2]
        )

    def test_author_querying(self):
        self.assertSequenceEqual(
            Author.objects.order_by("last_name"),
            [self.a2, self.a1],
        )

    def test_author_filtering(self):
        self.assertSequenceEqual(
            Author.objects.filter(first_name__exact="John"),
            [self.a1],
        )

    def test_author_get(self):
        self.assertEqual(self.a1, Author.objects.get(first_name__exact="John"))

    def test_filter_on_nonexistent_field(self):
        """
        Tests that a FieldError is raised when attempting to filter on a non-existent field.

        The function verifies that Django's ORM correctly handles an invalid field name in a filter query.
        It checks that the error message includes the valid field choices, helping with error diagnosis and debugging.
        This test ensures that the application behaves as expected when encountering invalid field names in filter operations.
        """
        msg = (
            "Cannot resolve keyword 'firstname' into field. Choices are: "
            "Author_ID, article, first_name, last_name, primary_set"
        )
        with self.assertRaisesMessage(FieldError, msg):
            Author.objects.filter(firstname__exact="John")

    def test_author_get_attributes(self):
        """
        .tests for getting attributes from an Author object.

        Checks if the 'first_name' and 'last_name' attributes of an Author instance are correctly retrieved.
        Also verifies that attempting to access non-existent attributes ('firstname', 'last') raises an AttributeError with the expected error message, ensuring case sensitivity and exact attribute naming.
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
        Tests the many-to-many relationship between articles and authors, verifying that authors are ordered correctly and that the relationship is properly established in both directions. Specifically, it checks that authors are ordered by last name and that filtering by last name returns the correct author.
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
