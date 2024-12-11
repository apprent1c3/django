from django.db import NotSupportedError
from django.db.models import F, Value
from django.db.models.functions import JSONObject, Lower
from django.test import TestCase
from django.test.testcases import skipIfDBFeature, skipUnlessDBFeature
from django.utils import timezone

from ..models import Article, Author


@skipUnlessDBFeature("has_json_object_function")
class JSONObjectTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Author.objects.bulk_create(
            [
                Author(name="Ivan Ivanov", alias="iivanov"),
                Author(name="Bertha Berthy", alias="bberthy"),
            ]
        )

    def test_empty(self):
        """
        Tests that an empty JSONObject annotation returns an empty dictionary.

        This test case checks that when a JSONObject annotation is applied to an Author object
        without any properties, the resulting JSON object is an empty dictionary. The test
        verifies this by comparing the annotated object's JSON content to an empty dictionary.

        Validates the correct behavior of JSONObject annotation in the absence of any data.
        """
        obj = Author.objects.annotate(json_object=JSONObject()).first()
        self.assertEqual(obj.json_object, {})

    def test_basic(self):
        """

        Tests the basic functionality of annotating database objects with JSON data.

        This test case verifies that a database object can be successfully annotated with a JSON object containing the 'name' field, 
        and that the resulting JSON object is correctly retrieved and matches the expected values.

        """
        obj = Author.objects.annotate(json_object=JSONObject(name="name")).first()
        self.assertEqual(obj.json_object, {"name": "Ivan Ivanov"})

    def test_expressions(self):
        """

        Tests the functionality of creating JSON objects from Django model instances using the annotate method.

        Verifies that the resulting JSON object contains the expected key-value pairs, including the application of database functions such as Lower and F expressions.

        """
        obj = Author.objects.annotate(
            json_object=JSONObject(
                name=Lower("name"),
                alias="alias",
                goes_by="goes_by",
                salary=Value(30000.15),
                age=F("age") * 2,
            )
        ).first()
        self.assertEqual(
            obj.json_object,
            {
                "name": "ivan ivanov",
                "alias": "iivanov",
                "goes_by": None,
                "salary": 30000.15,
                "age": 60,
            },
        )

    def test_nested_json_object(self):
        """
        Tests the annotation of a model instance with a nested JSON object.

        Verifies that the JSONObject annotation can correctly extract and structure nested data,
        creating a hierarchical JSON object that matches the expected output.

        The test checks the annotation of an Author model instance, extracting 'name'
        and a nested JSON object containing 'alias' and 'age', ensuring the result
        matches the predefined structure and values.
        """
        obj = Author.objects.annotate(
            json_object=JSONObject(
                name="name",
                nested_json_object=JSONObject(
                    alias="alias",
                    age="age",
                ),
            )
        ).first()
        self.assertEqual(
            obj.json_object,
            {
                "name": "Ivan Ivanov",
                "nested_json_object": {
                    "alias": "iivanov",
                    "age": 30,
                },
            },
        )

    def test_nested_empty_json_object(self):
        """
        Tests the creation and retrieval of a JSON object with nested empty JSON object.

        This test case verifies that a JSON object with a nested empty JSON object can be successfully created and retrieved from the database.
        The test checks if the resulting JSON object matches the expected structure, containing a 'name' and an empty 'nested_json_object' key.
        It ensures the correct annotation and serialization of nested JSON objects within the Author model.
        """
        obj = Author.objects.annotate(
            json_object=JSONObject(
                name="name",
                nested_json_object=JSONObject(),
            )
        ).first()
        self.assertEqual(
            obj.json_object,
            {
                "name": "Ivan Ivanov",
                "nested_json_object": {},
            },
        )

    def test_textfield(self):
        """
        Tests the conversion of the text field in the Article model to a JSON object.

        This test creates an Article instance with a large text field, annotates the text field as a JSON object, and then verifies that the resulting JSON object matches the original text field contents.

        The purpose of this test is to ensure that the text field can be successfully converted to a JSON object, even with large text values, and that the conversion process preserves the original data. 
        """
        Article.objects.create(
            title="The Title",
            text="x" * 4000,
            written=timezone.now(),
        )
        obj = Article.objects.annotate(json_object=JSONObject(text=F("text"))).first()
        self.assertEqual(obj.json_object, {"text": "x" * 4000})

    def test_order_by_key(self):
        """

        Tests that the order_by method produces the same results as the built-in order_by when ordering by a key in a JSONObject.

        The test case uses the Author model and orders the queryset by the 'alias' key inside a JSONObject.
        It then compares the resulting queryset with one ordered by the 'alias' field directly, asserting that they are equal.

        """
        qs = Author.objects.annotate(attrs=JSONObject(alias=F("alias"))).order_by(
            "attrs__alias"
        )
        self.assertQuerySetEqual(qs, Author.objects.order_by("alias"))

    def test_order_by_nested_key(self):
        """

        Tests the ordering of a queryset by a nested key within a JSON object.

        This test case verifies that the ordering of a queryset annotated with a JSON object
        is correctly applied to a nested key within that object. It checks that the resulting
        queryset is equivalent to a queryset ordered by the corresponding top-level key.

        """
        qs = Author.objects.annotate(
            attrs=JSONObject(nested=JSONObject(alias=F("alias")))
        ).order_by("-attrs__nested__alias")
        self.assertQuerySetEqual(qs, Author.objects.order_by("-alias"))


@skipIfDBFeature("has_json_object_function")
class JSONObjectNotSupportedTests(TestCase):
    def test_not_supported(self):
        """
        Tests that using JSONObject() on this database backend raises a NotSupportedError.

        Confirms that attempting to annotate a queryset with a JSONObject() expression results
        in an error, indicating the feature is not supported by the underlying database.

        """
        msg = "JSONObject() is not supported on this database backend."
        with self.assertRaisesMessage(NotSupportedError, msg):
            Author.objects.annotate(json_object=JSONObject()).get()
