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
        obj = Author.objects.annotate(json_object=JSONObject()).first()
        self.assertEqual(obj.json_object, {})

    def test_basic(self):
        """

        Tests the basic functionality of annotating a model instance with a JSON object.

        Verifies that the annotated JSON object is correctly populated with the expected data.
        In this case, it checks that the 'name' field of the annotated JSON object matches the name of the retrieved Author instance.

        """
        obj = Author.objects.annotate(json_object=JSONObject(name="name")).first()
        self.assertEqual(obj.json_object, {"name": "Ivan Ivanov"})

    def test_expressions(self):
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
        Article.objects.create(
            title="The Title",
            text="x" * 4000,
            written=timezone.now(),
        )
        obj = Article.objects.annotate(json_object=JSONObject(text=F("text"))).first()
        self.assertEqual(obj.json_object, {"text": "x" * 4000})

    def test_order_by_key(self):
        qs = Author.objects.annotate(attrs=JSONObject(alias=F("alias"))).order_by(
            "attrs__alias"
        )
        self.assertQuerySetEqual(qs, Author.objects.order_by("alias"))

    def test_order_by_nested_key(self):
        """
        Orders a queryset of Author objects by a nested key in descending order, testing that the annotated JSONObject correctly sorts the results.

        This function ensures that the order_by functionality works as expected when accessing nested keys within a JSONObject, by comparing the sorted results with the expected output.
        """
        qs = Author.objects.annotate(
            attrs=JSONObject(nested=JSONObject(alias=F("alias")))
        ).order_by("-attrs__nested__alias")
        self.assertQuerySetEqual(qs, Author.objects.order_by("-alias"))


@skipIfDBFeature("has_json_object_function")
class JSONObjectNotSupportedTests(TestCase):
    def test_not_supported(self):
        msg = "JSONObject() is not supported on this database backend."
        with self.assertRaisesMessage(NotSupportedError, msg):
            Author.objects.annotate(json_object=JSONObject()).get()
