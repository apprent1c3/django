from django.core.exceptions import FieldError
from django.test import TestCase

from .models import Article, Author


class CustomColumnsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """

        Set up test data for the test class.

        This method creates common test data that can be used across multiple test cases.
        It populates the database with two authors and one article, and assigns both authors to the article.

        The created data includes:

        * Two authors with first and last names
        * A list of all created authors
        * An article with a headline and primary author, as well as multiple authors assigned to it

        The test data is stored as class attributes, making it easily accessible to all test methods within the class.

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
        Tests that a FieldError is raised when using an invalid field name in a query.

        Verifies that the ORM correctly identifies and reports fields that do not exist on the model,
        providing a helpful error message with available field choices.

        :raises: FieldError
        """
        msg = (
            "Cannot resolve keyword 'firstname' into field. Choices are: "
            "Author_ID, article, first_name, last_name, primary_set"
        )
        with self.assertRaisesMessage(FieldError, msg):
            Author.objects.filter(firstname__exact="John")

    def test_attribute_error(self):
        """
        Tests that accessing certain attributes raises an AttributeError.

        This test case verifies that attempting to access the 'firstname' and partial 'last'
        attributes on an object results in an AttributeError, indicating that these attributes
        do not exist or are not accessible.

        Raises:
            AssertionError: If accessing the attributes does not raise an AttributeError.

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
        Tests that a FieldError is raised when attempting to filter on a non-existent field.

        This test case verifies that the ORM correctly handles invalid field names by raising
        an exception with a descriptive error message, including the available field choices.

        Args: None

        Raises: FieldError

        Returns: None
        """
        msg = (
            "Cannot resolve keyword 'firstname' into field. Choices are: "
            "Author_ID, article, first_name, last_name, primary_set"
        )
        with self.assertRaisesMessage(FieldError, msg):
            Author.objects.filter(firstname__exact="John")

    def test_author_get_attributes(self):
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
        Tests the many-to-many relationship table between articles and authors.

        Verifies that authors are correctly associated with articles and that 
        articles can be correctly filtered by author properties. The test checks 
        the order of authors, ensures that an author is associated with the 
        correct article, and confirms that articles can be filtered by author 
        last name.

        The test case covers the following scenarios:

        * Authors are ordered by last name in the correct sequence.
        * An author's article set contains the expected article.
        * Filtering articles by author last name returns the expected author instance.
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
