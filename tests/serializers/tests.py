from datetime import datetime
from functools import partialmethod
from io import StringIO
from unittest import mock, skipIf

from django.core import serializers
from django.core.serializers import SerializerDoesNotExist
from django.core.serializers.base import ProgressBar
from django.db import connection, transaction
from django.http import HttpResponse
from django.test import SimpleTestCase, override_settings, skipUnlessDBFeature
from django.test.utils import Approximate

from .models import (
    Actor,
    Article,
    Author,
    AuthorProfile,
    BaseModel,
    Category,
    Child,
    ComplexModel,
    Movie,
    Player,
    ProxyBaseModel,
    ProxyProxyBaseModel,
    Score,
    Team,
)


@override_settings(
    SERIALIZATION_MODULES={
        "json2": "django.core.serializers.json",
    }
)
class SerializerRegistrationTests(SimpleTestCase):
    def setUp(self):
        self.old_serializers = serializers._serializers
        serializers._serializers = {}

    def tearDown(self):
        serializers._serializers = self.old_serializers

    def test_register(self):
        """
        Tests the registration of a new serializer, verifying that it appears in the list of publicly available formats.
        """
        serializers.register_serializer("json3", "django.core.serializers.json")

        public_formats = serializers.get_public_serializer_formats()
        self.assertIn("json3", public_formats)
        self.assertIn("json2", public_formats)
        self.assertIn("xml", public_formats)

    def test_unregister(self):
        """
        Unregister a serializer and verify that the registry is updated correctly, checking that the unregistered serializer is no longer available and a newly registered serializer is included in the list of public formats.
        """
        serializers.unregister_serializer("xml")
        serializers.register_serializer("json3", "django.core.serializers.json")

        public_formats = serializers.get_public_serializer_formats()

        self.assertNotIn("xml", public_formats)
        self.assertIn("json3", public_formats)

    def test_unregister_unknown_serializer(self):
        with self.assertRaises(SerializerDoesNotExist):
            serializers.unregister_serializer("nonsense")

    def test_builtin_serializers(self):
        """
        Checks that the built-in serializers are properly registered and listed, including xml, json2, and python formats, with python being non-public.
        """
        all_formats = set(serializers.get_serializer_formats())
        public_formats = set(serializers.get_public_serializer_formats())

        self.assertIn("xml", all_formats)
        self.assertIn("xml", public_formats)

        self.assertIn("json2", all_formats)
        self.assertIn("json2", public_formats)

        self.assertIn("python", all_formats)
        self.assertNotIn("python", public_formats)

    def test_get_unknown_serializer(self):
        """
        Test that attempting to retrieve a non-existent serializer raises the expected SerializerDoesNotExist exception.
        """
        with self.assertRaises(SerializerDoesNotExist):
            serializers.get_serializer("nonsense")

        with self.assertRaises(KeyError):
            serializers.get_serializer("nonsense")

        # SerializerDoesNotExist is instantiated with the nonexistent format
        with self.assertRaisesMessage(SerializerDoesNotExist, "nonsense"):
            serializers.get_serializer("nonsense")

    def test_get_unknown_deserializer(self):
        with self.assertRaises(SerializerDoesNotExist):
            serializers.get_deserializer("nonsense")


class SerializersTestBase:
    serializer_name = None  # Set by subclasses to the serialization format name

    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for articles and their categories, creating sample categories, authors, and articles with predefined properties to facilitate testing.
        """
        sports = Category.objects.create(name="Sports")
        music = Category.objects.create(name="Music")
        op_ed = Category.objects.create(name="Op-Ed")

        cls.joe = Author.objects.create(name="Joe")
        cls.jane = Author.objects.create(name="Jane")

        cls.a1 = Article(
            author=cls.jane,
            headline="Poker has no place on ESPN",
            pub_date=datetime(2006, 6, 16, 11, 00),
        )
        cls.a1.save()
        cls.a1.categories.set([sports, op_ed])

        cls.a2 = Article(
            author=cls.joe,
            headline="Time to reform copyright",
            pub_date=datetime(2006, 6, 16, 13, 00, 11, 345),
        )
        cls.a2.save()
        cls.a2.categories.set([music, op_ed])

    def test_serialize(self):
        """Basic serialization works."""
        serial_str = serializers.serialize(self.serializer_name, Article.objects.all())
        self.assertTrue(self._validate_output(serial_str))

    def test_serializer_roundtrip(self):
        """Serialized content can be deserialized."""
        serial_str = serializers.serialize(self.serializer_name, Article.objects.all())
        models = list(serializers.deserialize(self.serializer_name, serial_str))
        self.assertEqual(len(models), 2)

    def test_serialize_to_stream(self):
        """
        Tests the serialization of a ComplexModel instance to various stream types.

        Verifies that the serialized data is identical when written to an in-memory StringIO object and an HttpResponse object.
        """
        obj = ComplexModel(field1="first", field2="second", field3="third")
        obj.save_base(raw=True)

        # Serialize the test database to a stream
        for stream in (StringIO(), HttpResponse()):
            serializers.serialize(self.serializer_name, [obj], indent=2, stream=stream)

            # Serialize normally for a comparison
            string_data = serializers.serialize(self.serializer_name, [obj], indent=2)

            # The two are the same
            if isinstance(stream, StringIO):
                self.assertEqual(string_data, stream.getvalue())
            else:
                self.assertEqual(string_data, stream.content.decode())

    def test_serialize_specific_fields(self):
        """

        Tests that specific fields of an object are correctly serialized and deserialized.

        Verifies that only the specified fields ('field1' and 'field3') are preserved during the serialization and deserialization process,
        while other fields ('field2') are reset to their default values.

        """
        obj = ComplexModel(field1="first", field2="second", field3="third")
        obj.save_base(raw=True)

        # Serialize then deserialize the test database
        serialized_data = serializers.serialize(
            self.serializer_name, [obj], indent=2, fields=("field1", "field3")
        )
        result = next(serializers.deserialize(self.serializer_name, serialized_data))

        # The deserialized object contains data in only the serialized fields.
        self.assertEqual(result.object.field1, "first")
        self.assertEqual(result.object.field2, "")
        self.assertEqual(result.object.field3, "third")

    def test_altering_serialized_output(self):
        """

        Test the ability to modify serialized model data and successfully save the changes to the database.

        Verifies that altering the serialized output of a model instance results in the creation of a new object with the updated data, replacing the original object.

        """
        old_headline = "Poker has no place on ESPN"
        new_headline = "Poker has no place on television"
        serial_str = serializers.serialize(self.serializer_name, Article.objects.all())
        serial_str = serial_str.replace(old_headline, new_headline)
        models = list(serializers.deserialize(self.serializer_name, serial_str))

        # Prior to saving, old headline is in place
        self.assertTrue(Article.objects.filter(headline=old_headline))
        self.assertFalse(Article.objects.filter(headline=new_headline))

        for model in models:
            model.save()

        # After saving, new headline is in place
        self.assertTrue(Article.objects.filter(headline=new_headline))
        self.assertFalse(Article.objects.filter(headline=old_headline))

    def test_one_to_one_as_pk(self):
        """
        Test that a custom primary key field, such as a OneToOneField, replaces the pk identifier in serialization.
        """
        AuthorProfile.objects.create(
            author=self.joe, date_of_birth=datetime(1970, 1, 1)
        )
        serial_str = serializers.serialize(
            self.serializer_name, AuthorProfile.objects.all()
        )
        self.assertFalse(self._get_field_values(serial_str, "author"))

        for obj in serializers.deserialize(self.serializer_name, serial_str):
            self.assertEqual(obj.object.pk, self.joe.pk)

    def test_serialize_field_subset(self):
        """
        Tests that theserialization of model instances can be limited to a specified subset of fields, ensuring that only the requested fields are included in the serialized output and all other fields are excluded.
        """
        valid_fields = ("headline", "pub_date")
        invalid_fields = ("author", "categories")
        serial_str = serializers.serialize(
            self.serializer_name, Article.objects.all(), fields=valid_fields
        )
        for field_name in invalid_fields:
            self.assertFalse(self._get_field_values(serial_str, field_name))

        for field_name in valid_fields:
            self.assertTrue(self._get_field_values(serial_str, field_name))

    def test_serialize_unicode_roundtrip(self):
        """
        Tests that serialization and deserialization of objects containing Unicode characters preserves their original values.
        """
        actor_name = "Za\u017c\u00f3\u0142\u0107"
        movie_title = "G\u0119\u015bl\u0105 ja\u017a\u0144"
        ac = Actor(name=actor_name)
        mv = Movie(title=movie_title, actor=ac)
        ac.save()
        mv.save()

        serial_str = serializers.serialize(self.serializer_name, [mv])
        self.assertEqual(self._get_field_values(serial_str, "title")[0], movie_title)
        self.assertEqual(self._get_field_values(serial_str, "actor")[0], actor_name)

        obj_list = list(serializers.deserialize(self.serializer_name, serial_str))
        mv_obj = obj_list[0].object
        self.assertEqual(mv_obj.title, movie_title)

    def test_unicode_serialization(self):
        """
        Tests that unicode data can be successfully serialized and deserialized using the specified serializer.
        """
        unicode_name = "יוניקוד"
        data = serializers.serialize(self.serializer_name, [Author(name=unicode_name)])
        self.assertIn(unicode_name, data)
        objs = list(serializers.deserialize(self.serializer_name, data))
        self.assertEqual(objs[0].object.name, unicode_name)

    def test_serialize_progressbar(self):
        fake_stdout = StringIO()
        serializers.serialize(
            self.serializer_name,
            Article.objects.all(),
            progress_output=fake_stdout,
            object_count=Article.objects.count(),
        )
        self.assertTrue(
            fake_stdout.getvalue().endswith(
                "[" + "." * ProgressBar.progress_width + "]\n"
            )
        )

    def test_serialize_superfluous_queries(self):
        """
        Tests that serializing models with ForeignKeys does not result in unnecessary database queries.
        """
        ac = Actor(name="Actor name")
        ac.save()
        mv = Movie(title="Movie title", actor_id=ac.pk)
        mv.save()

        with self.assertNumQueries(0):
            serializers.serialize(self.serializer_name, [mv])

    def test_serialize_prefetch_related_m2m(self):
        # One query for the Article table and one for each prefetched m2m
        # field.
        with self.assertNumQueries(4):
            serializers.serialize(
                self.serializer_name,
                Article.objects.prefetch_related("categories", "meta_data", "topics"),
            )
        # One query for the Article table, and three m2m queries for each
        # article.
        with self.assertNumQueries(7):
            serializers.serialize(self.serializer_name, Article.objects.all())

    def test_serialize_with_null_pk(self):
        """
        Verifies that serializing a model instance without a primary key results in deserialized data with a null id.
        """
        category = Category(name="Reference")
        serial_str = serializers.serialize(self.serializer_name, [category])
        pk_value = self._get_pk_values(serial_str)[0]
        self.assertFalse(pk_value)

        cat_obj = list(serializers.deserialize(self.serializer_name, serial_str))[
            0
        ].object
        self.assertIsNone(cat_obj.id)

    def test_float_serialization(self):
        """
        Checks that floating point values are correctly serialized and deserialized without losing precision.
        """
        sc = Score(score=3.4)
        sc.save()
        serial_str = serializers.serialize(self.serializer_name, [sc])
        deserial_objs = list(serializers.deserialize(self.serializer_name, serial_str))
        self.assertEqual(deserial_objs[0].object.score, Approximate(3.4, places=1))

    def test_deferred_field_serialization(self):
        """
        Tests serialization of a model instance with deferred fields.

        Verifies that a model instance with a deferred field can be successfully 
        serialized and deserialized, resulting in a valid model instance.
        """
        author = Author.objects.create(name="Victor Hugo")
        author = Author.objects.defer("name").get(pk=author.pk)
        serial_str = serializers.serialize(self.serializer_name, [author])
        deserial_objs = list(serializers.deserialize(self.serializer_name, serial_str))
        self.assertIsInstance(deserial_objs[0].object, Author)

    def test_custom_field_serialization(self):
        """
        Tests that custom fields are correctly serialized and deserialized, ensuring data integrity during this process.
        """
        team_str = "Spartak Moskva"
        player = Player()
        player.name = "Soslan Djanaev"
        player.rank = 1
        player.team = Team(team_str)
        player.save()
        serial_str = serializers.serialize(self.serializer_name, Player.objects.all())
        team = self._get_field_values(serial_str, "team")
        self.assertTrue(team)
        self.assertEqual(team[0], team_str)

        deserial_objs = list(serializers.deserialize(self.serializer_name, serial_str))
        self.assertEqual(
            deserial_objs[0].object.team.to_string(), player.team.to_string()
        )

    def test_pre_1000ad_date(self):
        """
        Verifies that publication dates prior to the year 1000 AD are correctly serialized by the serializer.
        """
        # Regression for #12524 -- dates before 1000AD get prefixed
        # 0's on the year
        a = Article.objects.create(
            author=self.jane,
            headline="Nobody remembers the early years",
            pub_date=datetime(1, 2, 3, 4, 5, 6),
        )

        serial_str = serializers.serialize(self.serializer_name, [a])
        date_values = self._get_field_values(serial_str, "pub_date")
        self.assertEqual(date_values[0].replace("T", " "), "0001-02-03 04:05:06")

    def test_pkless_serialized_strings(self):
        """
        Tests the ability to deserialize and save model instances from serialized strings that do not contain primary keys.
        """
        deserial_objs = list(
            serializers.deserialize(self.serializer_name, self.pkless_str)
        )
        for obj in deserial_objs:
            self.assertFalse(obj.object.id)
            obj.save()
        self.assertEqual(Category.objects.count(), 5)

    def test_deterministic_mapping_ordering(self):
        """Mapping such as fields should be deterministically ordered. (#24558)"""
        output = serializers.serialize(self.serializer_name, [self.a1], indent=2)
        categories = self.a1.categories.values_list("pk", flat=True)
        self.assertEqual(
            output,
            self.mapping_ordering_str
            % {
                "article_pk": self.a1.pk,
                "author_pk": self.a1.author_id,
                "first_category_pk": categories[0],
                "second_category_pk": categories[1],
            },
        )

    def test_deserialize_force_insert(self):
        """
        Tests that deserialized model instances can be saved with the force_insert parameter, ensuring the correct database behavior.
        """
        serial_str = serializers.serialize(self.serializer_name, [self.a1])
        deserial_obj = list(serializers.deserialize(self.serializer_name, serial_str))[
            0
        ]
        with mock.patch("django.db.models.Model") as mock_model:
            deserial_obj.save(force_insert=False)
            mock_model.save_base.assert_called_with(
                deserial_obj.object, raw=True, using=None, force_insert=False
            )

    @skipUnlessDBFeature("can_defer_constraint_checks")
    def test_serialize_proxy_model(self):
        """
        Tests the serialization of proxy models to ensure consistency with their base models.

        Verifies that proxy models can be serialized to JSON and that the output matches the base model's serialization,
        with the exception of the model name, which is expected to contain 'proxy'.
        """
        BaseModel.objects.create(parent_data=1)
        base_objects = BaseModel.objects.all()
        proxy_objects = ProxyBaseModel.objects.all()
        proxy_proxy_objects = ProxyProxyBaseModel.objects.all()
        base_data = serializers.serialize("json", base_objects)
        proxy_data = serializers.serialize("json", proxy_objects)
        proxy_proxy_data = serializers.serialize("json", proxy_proxy_objects)
        self.assertEqual(base_data, proxy_data.replace("proxy", ""))
        self.assertEqual(base_data, proxy_proxy_data.replace("proxy", ""))

    def test_serialize_inherited_fields(self):
        """

        Verifies that inherited fields are correctly excluded from serialization.

        Tests the serialization of model instances with inherited fields, ensuring that 
        the resulting serialized data does not contain the inherited field values.

        """
        child_1 = Child.objects.create(parent_data="a", child_data="b")
        child_2 = Child.objects.create(parent_data="c", child_data="d")
        child_1.parent_m2m.add(child_2)
        child_data = serializers.serialize(self.serializer_name, [child_1, child_2])
        self.assertEqual(self._get_field_values(child_data, "parent_m2m"), [])
        self.assertEqual(self._get_field_values(child_data, "parent_data"), [])

    def test_serialize_only_pk(self):
        """
        Tests serialization of models with the given serializer, verifying that 
        foreign keys are serialized as numeric IDs when use_natural_foreign_keys is False.
        """
        with self.assertNumQueries(7) as ctx:
            serializers.serialize(
                self.serializer_name,
                Article.objects.all(),
                use_natural_foreign_keys=False,
            )

        categories_sql = ctx[1]["sql"]
        self.assertNotIn(connection.ops.quote_name("meta_data_id"), categories_sql)
        meta_data_sql = ctx[2]["sql"]
        self.assertNotIn(connection.ops.quote_name("kind"), meta_data_sql)
        topics_data_sql = ctx[3]["sql"]
        self.assertNotIn(connection.ops.quote_name("category_id"), topics_data_sql)

    def test_serialize_no_only_pk_with_natural_keys(self):
        """
        Tests serialization of model instances without primary keys when using natural foreign keys. Verifies that related models are correctly serialized and their queries do not reference primary keys.
        """
        with self.assertNumQueries(7) as ctx:
            serializers.serialize(
                self.serializer_name,
                Article.objects.all(),
                use_natural_foreign_keys=True,
            )

        categories_sql = ctx[1]["sql"]
        self.assertNotIn(connection.ops.quote_name("meta_data_id"), categories_sql)
        # CategoryMetaData has natural_key().
        meta_data_sql = ctx[2]["sql"]
        self.assertIn(connection.ops.quote_name("kind"), meta_data_sql)
        topics_data_sql = ctx[3]["sql"]
        self.assertNotIn(connection.ops.quote_name("category_id"), topics_data_sql)


class SerializerAPITests(SimpleTestCase):
    def test_stream_class(self):
        """
        ::

            Tests the usage of a custom stream class in a Serializer instance.
            Verifies that the serializer correctly utilizes the custom stream class
            and produces the expected serialized data.
        """
        class File:
            def __init__(self):
                self.lines = []

            def write(self, line):
                self.lines.append(line)

            def getvalue(self):
                return "".join(self.lines)

        class Serializer(serializers.json.Serializer):
            stream_class = File

        serializer = Serializer()
        data = serializer.serialize([Score(id=1, score=3.4)])
        self.assertIs(serializer.stream_class, File)
        self.assertIsInstance(serializer.stream, File)
        self.assertEqual(
            data, '[{"model": "serializers.score", "pk": 1, "fields": {"score": 3.4}}]'
        )


class SerializersTransactionTestBase:
    available_apps = ["serializers"]

    @skipUnlessDBFeature("supports_forward_references")
    def test_forward_refs(self):
        """
        Tests the forward references functionality in the serialization data, ensuring that object IDs can be referenced before they are defined and correctly resolved during deserialization and object creation.
        """
        # The deserialization process needs to run in a transaction in order
        # to test forward reference handling.
        with transaction.atomic():
            objs = serializers.deserialize(self.serializer_name, self.fwd_ref_str)
            with connection.constraint_checks_disabled():
                for obj in objs:
                    obj.save()

        for model_cls in (Category, Author, Article):
            self.assertEqual(model_cls.objects.count(), 1)
        art_obj = Article.objects.all()[0]
        self.assertEqual(art_obj.categories.count(), 1)
        self.assertEqual(art_obj.author.name, "Agnes")


def register_tests(test_class, method_name, test_func, exclude=()):
    """
    Registers test methods for various serializer formats, automatically testing all registered serializers.
    """
    for format_ in serializers.get_serializer_formats():
        if format_ == "geojson" or format_ in exclude:
            continue
        decorated_func = skipIf(
            isinstance(serializers.get_serializer(format_), serializers.BadSerializer),
            "The Python library for the %s serializer is not installed." % format_,
        )(test_func)
        setattr(
            test_class, method_name % format_, partialmethod(decorated_func, format_)
        )
