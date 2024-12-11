from django.core.exceptions import FieldError
from django.test import TestCase

from .models import Article, Author


class CustomColumnsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """

        Sets up test data for the class.

        This method creates and stores test authors and an article, which can be used throughout the test class.
        It establishes two authors, John Smith and Peter Jones, and creates an article with John Smith as the primary author.
        Both authors are then associated with the article.

        The test data includes:
            - Two authors, accessible via the class attributes 'a1' and 'a2'
            - A list of all authors, accessible via the class attribute 'authors'
            - An article, accessible via the class attribute 'article'

        """
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
        """
        Tests that a FieldError is raised when an invalid field name is used in a query.

        The function verifies that attempting to filter objects using a non-existent field results in an error,
        with a message that provides information about the available field choices.

        This test ensures that the model's field validation is working correctly and provides useful feedback
        to developers when they attempt to use an invalid field name in their queries.
        """
        msg = (
            "Cannot resolve keyword 'firstname' into field. Choices are: "
            "Author_ID, article, first_name, last_name, primary_set"
        )
        with self.assertRaisesMessage(FieldError, msg):
            Author.objects.filter(firstname__exact="John")

    def test_attribute_error(self):
        """

        Tests that attempting to access the 'firstname' and 'lastname' attributes of an object raises an AttributeError.

        This test case ensures that the object does not have these attributes, which is the expected behavior in certain situations.

        """
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
        Tests the behavior of the filter method when attempting to filter on a non-existent field.

        Verifies that a FieldError is raised with a message indicating that the specified field cannot be resolved, 
        and provides a list of available field choices.

        Ensures that the error message accurately reflects the available fields for the model, 
        in this case, Author_ID, article, first_name, last_name, and primary_set.
        """
        msg = (
            "Cannot resolve keyword 'firstname' into field. Choices are: "
            "Author_ID, article, first_name, last_name, primary_set"
        )
        with self.assertRaisesMessage(FieldError, msg):
            Author.objects.filter(firstname__exact="John")

    def test_author_get_attributes(self):
        """

        Tests the retrieval and access of attributes for an Author object.

        This test case verifies that an Author object can be successfully retrieved from the database
        based on its last name and that its first and last name attributes can be accessed.

        Additionally, it checks that attempting to access non-existent attributes ('firstname' and 'last')
        results in an AttributeError with the expected error message, ensuring that attribute access
        is case-sensitive and follows the defined attribute names.

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

        Tests the many-to-many relationship between articles and authors.

        Verifies that the authors associated with an article are properly ordered,
        that an author's article set is correctly populated, and that filtering by
        author last name produces the expected results.

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
