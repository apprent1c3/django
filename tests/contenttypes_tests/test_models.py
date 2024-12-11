from django.apps import apps
from django.contrib.contenttypes.models import ContentType, ContentTypeManager
from django.contrib.contenttypes.prefetch import GenericPrefetch
from django.db import models
from django.db.migrations.state import ModelState, ProjectState
from django.test import TestCase, override_settings
from django.test.utils import isolate_apps

from .models import Author, ConcreteModel, FooWithUrl, ProxyModel


class ContentTypesTests(TestCase):
    def setUp(self):
        """

        Initializes the test environment by clearing the ContentType cache.

        This setup method is used to prepare the cache for testing by removing any existing content types.
        Additionally, it schedules a cleanup to clear the cache again after the test has finished, ensuring that
        each test starts with a clean slate and does not interfere with other tests.

        """
        ContentType.objects.clear_cache()
        self.addCleanup(ContentType.objects.clear_cache)

    def test_lookup_cache(self):
        """
        The content type cache (see ContentTypeManager) works correctly.
        Lookups for a particular content type -- by model, ID, or natural key
        -- should hit the database only on the first lookup.
        """
        # At this point, a lookup for a ContentType should hit the DB
        with self.assertNumQueries(1):
            ContentType.objects.get_for_model(ContentType)

        # A second hit, though, won't hit the DB, nor will a lookup by ID
        # or natural key
        with self.assertNumQueries(0):
            ct = ContentType.objects.get_for_model(ContentType)
        with self.assertNumQueries(0):
            ContentType.objects.get_for_id(ct.id)
        with self.assertNumQueries(0):
            ContentType.objects.get_by_natural_key("contenttypes", "contenttype")

        # Once we clear the cache, another lookup will again hit the DB
        ContentType.objects.clear_cache()
        with self.assertNumQueries(1):
            ContentType.objects.get_for_model(ContentType)

        # The same should happen with a lookup by natural key
        ContentType.objects.clear_cache()
        with self.assertNumQueries(1):
            ContentType.objects.get_by_natural_key("contenttypes", "contenttype")
        # And a second hit shouldn't hit the DB
        with self.assertNumQueries(0):
            ContentType.objects.get_by_natural_key("contenttypes", "contenttype")

    def test_get_for_models_creation(self):
        """

        Test that the get_for_models method of ContentType returns the correct content types.

        This test case checks that the get_for_models method returns a dictionary where the keys are model classes and the values are the corresponding content types.

        The test first clears all existing content types, then uses get_for_models to retrieve the content types for a set of models. It then asserts that the returned dictionary matches the expected content types for each model, which are retrieved using the get_for_model method.

        The test also verifies that the get_for_models method performs the expected number of database queries.

        """
        ContentType.objects.all().delete()
        with self.assertNumQueries(4):
            cts = ContentType.objects.get_for_models(
                ContentType, FooWithUrl, ProxyModel, ConcreteModel
            )
        self.assertEqual(
            cts,
            {
                ContentType: ContentType.objects.get_for_model(ContentType),
                FooWithUrl: ContentType.objects.get_for_model(FooWithUrl),
                ProxyModel: ContentType.objects.get_for_model(ProxyModel),
                ConcreteModel: ContentType.objects.get_for_model(ConcreteModel),
            },
        )

    def test_get_for_models_empty_cache(self):
        # Empty cache.
        """
        .. method:: test_get_for_models_empty_cache

           Tests that :meth:`get_for_models` method retrieves the correct content types from the database
           when the cache is empty. It queries the database once for the content types of multiple models 
           and verifies that the result matches the expected content types. This test ensures that the 
           :meth:`get_for_models` method behaves correctly in the absence of cached data.
        """
        with self.assertNumQueries(1):
            cts = ContentType.objects.get_for_models(
                ContentType, FooWithUrl, ProxyModel, ConcreteModel
            )
        self.assertEqual(
            cts,
            {
                ContentType: ContentType.objects.get_for_model(ContentType),
                FooWithUrl: ContentType.objects.get_for_model(FooWithUrl),
                ProxyModel: ContentType.objects.get_for_model(ProxyModel),
                ConcreteModel: ContentType.objects.get_for_model(ConcreteModel),
            },
        )

    def test_get_for_models_partial_cache(self):
        # Partial cache
        """

        Tests the retrieval of content types for specified models with partial cache.

        This test case verifies that getting content types for multiple models 
        results in a single database query and that the returned content types 
        match the expected values for each model.

        It ensures that the `get_for_models` method of `ContentType` objects 
        correctly retrieves content types with minimal database queries.

        """
        ContentType.objects.get_for_model(ContentType)
        with self.assertNumQueries(1):
            cts = ContentType.objects.get_for_models(ContentType, FooWithUrl)
        self.assertEqual(
            cts,
            {
                ContentType: ContentType.objects.get_for_model(ContentType),
                FooWithUrl: ContentType.objects.get_for_model(FooWithUrl),
            },
        )

    def test_get_for_models_migrations(self):
        """
        Tests the functionality of getting content types for models.

        This test case verifies that the get_for_models method of ContentType returns
        the correct content type instances for the given models. It checks that the
        result is a dictionary mapping each model to its corresponding content type.

        The test uses the ContentType model from the contenttypes app, ensuring that
        the function behaves as expected for this specific model. The assertEqual
        statement confirms that the result matches the expected output, providing
        confidence in the correctness of the get_for_models method.

        Note: This test is specific to the ContentType model, but the concept can be
        applied to other models as well, ensuring that the get_for_models method works
        correctly across the board.
        """
        state = ProjectState.from_apps(apps.get_app_config("contenttypes"))
        ContentType = state.apps.get_model("contenttypes", "ContentType")
        cts = ContentType.objects.get_for_models(ContentType)
        self.assertEqual(
            cts, {ContentType: ContentType.objects.get_for_model(ContentType)}
        )

    @isolate_apps("contenttypes_tests")
    def test_get_for_models_migrations_create_model(self):
        state = ProjectState.from_apps(apps.get_app_config("contenttypes"))

        class Foo(models.Model):
            class Meta:
                app_label = "contenttypes_tests"

        state.add_model(ModelState.from_model(Foo))
        ContentType = state.apps.get_model("contenttypes", "ContentType")
        cts = ContentType.objects.get_for_models(FooWithUrl, Foo)
        self.assertEqual(
            cts,
            {
                Foo: ContentType.objects.get_for_model(Foo),
                FooWithUrl: ContentType.objects.get_for_model(FooWithUrl),
            },
        )

    def test_get_for_models_full_cache(self):
        # Full cache
        """
        Tests that get_for_models utilizes the full cache when retrieving content types.

        This test checks that when get_for_model is called multiple times, 
        it populates the cache and subsequent calls to get_for_models can retrieve 
        the cached content types without executing additional database queries.

        It verifies that the cached content types match the expected values and 
        that the cache is used effectively to reduce database queries. 
        """
        ContentType.objects.get_for_model(ContentType)
        ContentType.objects.get_for_model(FooWithUrl)
        with self.assertNumQueries(0):
            cts = ContentType.objects.get_for_models(ContentType, FooWithUrl)
        self.assertEqual(
            cts,
            {
                ContentType: ContentType.objects.get_for_model(ContentType),
                FooWithUrl: ContentType.objects.get_for_model(FooWithUrl),
            },
        )

    @isolate_apps("contenttypes_tests")
    def test_get_for_model_create_contenttype(self):
        """
        ContentTypeManager.get_for_model() creates the corresponding content
        type if it doesn't exist in the database.
        """

        class ModelCreatedOnTheFly(models.Model):
            name = models.CharField()

        ct = ContentType.objects.get_for_model(ModelCreatedOnTheFly)
        self.assertEqual(ct.app_label, "contenttypes_tests")
        self.assertEqual(ct.model, "modelcreatedonthefly")
        self.assertEqual(str(ct), "modelcreatedonthefly")

    def test_get_for_concrete_model(self):
        """
        Make sure the `for_concrete_model` kwarg correctly works
        with concrete, proxy and deferred models
        """
        concrete_model_ct = ContentType.objects.get_for_model(ConcreteModel)
        self.assertEqual(
            concrete_model_ct, ContentType.objects.get_for_model(ProxyModel)
        )
        self.assertEqual(
            concrete_model_ct,
            ContentType.objects.get_for_model(ConcreteModel, for_concrete_model=False),
        )

        proxy_model_ct = ContentType.objects.get_for_model(
            ProxyModel, for_concrete_model=False
        )
        self.assertNotEqual(concrete_model_ct, proxy_model_ct)

        # Make sure deferred model are correctly handled
        ConcreteModel.objects.create(name="Concrete")
        DeferredConcreteModel = ConcreteModel.objects.only("pk").get().__class__
        DeferredProxyModel = ProxyModel.objects.only("pk").get().__class__

        self.assertEqual(
            concrete_model_ct, ContentType.objects.get_for_model(DeferredConcreteModel)
        )
        self.assertEqual(
            concrete_model_ct,
            ContentType.objects.get_for_model(
                DeferredConcreteModel, for_concrete_model=False
            ),
        )
        self.assertEqual(
            concrete_model_ct, ContentType.objects.get_for_model(DeferredProxyModel)
        )
        self.assertEqual(
            proxy_model_ct,
            ContentType.objects.get_for_model(
                DeferredProxyModel, for_concrete_model=False
            ),
        )

    def test_get_for_concrete_models(self):
        """
        Make sure the `for_concrete_models` kwarg correctly works
        with concrete, proxy and deferred models.
        """
        concrete_model_ct = ContentType.objects.get_for_model(ConcreteModel)

        cts = ContentType.objects.get_for_models(ConcreteModel, ProxyModel)
        self.assertEqual(
            cts,
            {
                ConcreteModel: concrete_model_ct,
                ProxyModel: concrete_model_ct,
            },
        )

        proxy_model_ct = ContentType.objects.get_for_model(
            ProxyModel, for_concrete_model=False
        )
        cts = ContentType.objects.get_for_models(
            ConcreteModel, ProxyModel, for_concrete_models=False
        )
        self.assertEqual(
            cts,
            {
                ConcreteModel: concrete_model_ct,
                ProxyModel: proxy_model_ct,
            },
        )

        # Make sure deferred model are correctly handled
        ConcreteModel.objects.create(name="Concrete")
        DeferredConcreteModel = ConcreteModel.objects.only("pk").get().__class__
        DeferredProxyModel = ProxyModel.objects.only("pk").get().__class__

        cts = ContentType.objects.get_for_models(
            DeferredConcreteModel, DeferredProxyModel
        )
        self.assertEqual(
            cts,
            {
                DeferredConcreteModel: concrete_model_ct,
                DeferredProxyModel: concrete_model_ct,
            },
        )

        cts = ContentType.objects.get_for_models(
            DeferredConcreteModel, DeferredProxyModel, for_concrete_models=False
        )
        self.assertEqual(
            cts,
            {
                DeferredConcreteModel: concrete_model_ct,
                DeferredProxyModel: proxy_model_ct,
            },
        )

    def test_cache_not_shared_between_managers(self):
        with self.assertNumQueries(1):
            ContentType.objects.get_for_model(ContentType)
        with self.assertNumQueries(0):
            ContentType.objects.get_for_model(ContentType)
        other_manager = ContentTypeManager()
        other_manager.model = ContentType
        with self.assertNumQueries(1):
            other_manager.get_for_model(ContentType)
        with self.assertNumQueries(0):
            other_manager.get_for_model(ContentType)

    def test_missing_model(self):
        """
        Displaying content types in admin (or anywhere) doesn't break on
        leftover content type records in the DB for which no model is defined
        anymore.
        """
        ct = ContentType.objects.create(
            app_label="contenttypes",
            model="OldModel",
        )
        self.assertEqual(str(ct), "OldModel")
        self.assertIsNone(ct.model_class())

        # Stale ContentTypes can be fetched like any other object.
        ct_fetched = ContentType.objects.get_for_id(ct.pk)
        self.assertIsNone(ct_fetched.model_class())

    def test_missing_model_with_existing_model_name(self):
        """
        Displaying content types in admin (or anywhere) doesn't break on
        leftover content type records in the DB for which no model is defined
        anymore, even if a model with the same name exists in another app.
        """
        # Create a stale ContentType that matches the name of an existing
        # model.
        ContentType.objects.create(app_label="contenttypes", model="author")
        ContentType.objects.clear_cache()
        # get_for_models() should work as expected for existing models.
        cts = ContentType.objects.get_for_models(ContentType, Author)
        self.assertEqual(
            cts,
            {
                ContentType: ContentType.objects.get_for_model(ContentType),
                Author: ContentType.objects.get_for_model(Author),
            },
        )

    def test_str(self):
        """
        Tests the string representation of a ContentType instance.

        Verifies that the string representation of a ContentType object is correctly
        formatted as \"App Label | Model Name\", ensuring proper display of content type
        information.

        Returns:
            None

        Raises:
            AssertionError: If the string representation does not match the expected format.

        """
        ct = ContentType.objects.get(app_label="contenttypes_tests", model="site")
        self.assertEqual(str(ct), "Contenttypes_Tests | site")

    def test_str_auth(self):
        """

        Tests that the string representation of a ContentType instance for the 'group' model 
        in the 'auth' app is correctly formatted.

        The expected string representation is a combination of the app name and the model name, 
        which in this case is 'Authentication and Authorization | group'. This test ensures 
        that the str method of the ContentType class returns the expected output.

        """
        ct = ContentType.objects.get(app_label="auth", model="group")
        self.assertEqual(str(ct), "Authentication and Authorization | group")

    def test_name(self):
        """
        Tests that the name of a content type is correctly retrieved.

        Verifies that the name of the content type instance associated with the model 'site'
        in the 'contenttypes_tests' app is 'site', ensuring accurate content type naming.

        """
        ct = ContentType.objects.get(app_label="contenttypes_tests", model="site")
        self.assertEqual(ct.name, "site")

    def test_app_labeled_name(self):
        """

        Tests that the app_labeled_name attribute of a ContentType object returns the correct string.

        The app_labeled_name is a concatenation of the application label and model name, 
        formatted as \"App_Label | Model_Name\". This test ensures that the string is 
        correctly generated for a ContentType instance, helping to maintain data accuracy 
        and consistency in the system.

        """
        ct = ContentType.objects.get(app_label="contenttypes_tests", model="site")
        self.assertEqual(ct.app_labeled_name, "Contenttypes_Tests | site")

    def test_name_unknown_model(self):
        """
        Tests that the name attribute of a ContentType instance is correctly set when the model is unknown.

            Verifies that a ContentType instance with an unknown model still returns the 
            expected name, demonstrating the ContentType class handles unknown models as expected.
        """
        ct = ContentType(app_label="contenttypes_tests", model="unknown")
        self.assertEqual(ct.name, "unknown")

    def test_app_labeled_name_unknown_model(self):
        ct = ContentType(app_label="contenttypes_tests", model="unknown")
        self.assertEqual(ct.app_labeled_name, "unknown")


class TestRouter:
    def db_for_read(self, model, **hints):
        return "other"

    def db_for_write(self, model, **hints):
        return "default"

    def allow_relation(self, obj1, obj2, **hints):
        return True


@override_settings(DATABASE_ROUTERS=[TestRouter()])
class ContentTypesMultidbTests(TestCase):
    databases = {"default", "other"}

    def test_multidb(self):
        """
        When using multiple databases, ContentType.objects.get_for_model() uses
        db_for_read().
        """
        ContentType.objects.clear_cache()
        with (
            self.assertNumQueries(0, using="default"),
            self.assertNumQueries(1, using="other"),
        ):
            ContentType.objects.get_for_model(Author)


class GenericPrefetchTests(TestCase):
    def test_querysets_required(self):
        """
        Tests that a TypeError is raised whenGenericPrefetch is initialized without required positional argument 'querysets'.

        Verifies that an error message is correctly displayed when the 'querysets' parameter is missing, ensuring proper handling of invalid initialization attempts.

        The expected error message indicates that the 'querysets' argument is a required positional parameter for GenericPrefetch's constructor, as defined in its __init__ method.
        """
        msg = (
            "GenericPrefetch.__init__() missing 1 required "
            "positional argument: 'querysets'"
        )
        with self.assertRaisesMessage(TypeError, msg):
            GenericPrefetch("question")

    def test_values_queryset(self):
        msg = "Prefetch querysets cannot use raw(), values(), and values_list()."
        with self.assertRaisesMessage(ValueError, msg):
            GenericPrefetch("question", [Author.objects.values("pk")])
        with self.assertRaisesMessage(ValueError, msg):
            GenericPrefetch("question", [Author.objects.values_list("pk")])

    def test_raw_queryset(self):
        """
        Tests that a ValueError is raised when attempting to prefetch a raw queryset.

        This test case checks that GenericPrefetch correctly handles querysets created using the raw() method, which is not compatible with prefetching.

        It verifies that the expected error message is raised, indicating that raw(), values(), and values_list() methods cannot be used with prefetch querysets.
        """
        msg = "Prefetch querysets cannot use raw(), values(), and values_list()."
        with self.assertRaisesMessage(ValueError, msg):
            GenericPrefetch("question", [Author.objects.raw("select pk from author")])
