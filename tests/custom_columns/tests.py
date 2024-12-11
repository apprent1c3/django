from django.core.exceptions import FieldError
from django.test import TestCase

from .models import Article, Author


class CustomColumnsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for the class.

        This method creates a set of authors and an article, which are then stored as class attributes. The authors and article are used to populate the test database, allowing for more comprehensive testing of the application's functionality.

        The test data includes two authors and one article, with the article being associated with both authors. The authors and article are created using the application's ORM, ensuring that the test data is consistent with the application's data model.

        The following attributes are set by this method:

        * authors: a list of authors created for testing
        * a1: the first author created for testing
        * a2: the second author created for testing
        * article: an article created for testing, associated with the authors
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
        Tests that Django's ORM raises a FieldError when attempting to filter on a non-existent field of a model instance. 

        The function verifies that the correct error message is raised, including the list of valid fields that can be used for filtering. This ensures that Django's ORM correctly handles invalid field names and provides informative error messages.
        """
        msg = (
            "Cannot resolve keyword 'firstname' into field. Choices are: "
            "Author_ID, article, first_name, last_name, primary_set"
        )
        with self.assertRaisesMessage(FieldError, msg):
            Author.objects.filter(firstname__exact="John")

    def test_author_get_attributes(self):
        """

        Tests fetching an author object and verifies its attributes.

        Checks if the author's first name and last name are correctly retrieved.
        Additionally, ensures that attempting to access non-existent attributes,
        such as 'firstname' and 'last', raises an AttributeError with the expected message.

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

        Verifies that articles can be ordered by author's last name, 
        and that an author's article set is correctly updated. 
        Additionally, checks that filtering authors by last name returns the expected results.

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
