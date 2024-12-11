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

        Tests the get_for_models method of the ContentTypeManager.

        This test case verifies that the get_for_models method correctly retrieves
        ContentType instances for the given models in a single database query.
        It deletes all existing ContentType instances and then checks that the 
        method returns the correct instances for multiple models. 

        The test also checks that the method executes only a single database 
        query when fetching ContentType instances for multiple models, 
        which is important for optimizing database performance.

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

        Tests the get_for_models method of ContentType when the cache is empty.

        Verifies that the method retrieves the correct content types for a list of models,
        including the models themselves, in a single database query. The resulting
        content types are then compared to the expected content types, which are
        obtained individually using the get_for_model method.

        The test checks that the method can handle various types of models, including
        proxies, and that the returned content types are correct. This ensures that
        the get_for_models method is functioning as expected, even when the cache is empty.

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
        Tests the get_for_models method of the ContentType model to ensure it correctly retrieves the content type instances for the given model.

        This test verifies that the get_for_models method returns a dictionary mapping each model to its corresponding content type instance, 
        and that this result matches the expected output from calling get_for_model directly on the ContentType model.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the result of get_for_models does not match the expected output.
        """
        state = ProjectState.from_apps(apps.get_app_config("contenttypes"))
        ContentType = state.apps.get_model("contenttypes", "ContentType")
        cts = ContentType.objects.get_for_models(ContentType)
        self.assertEqual(
            cts, {ContentType: ContentType.objects.get_for_model(ContentType)}
        )

    @isolate_apps("contenttypes_tests")
    def test_get_for_models_migrations_create_model(self):
        """

        Tests the functionality of the get_for_models method for creating ContentType objects.

        This test ensures that the get_for_models method correctly retrieves ContentType objects 
        for given models, specifically after model creation through migrations. 

        It verifies that the method returns a dictionary mapping each model to its corresponding 
        ContentType object, checking that the returned ContentType objects match the ones 
        retrieved using the get_for_model method for individual models.

        """
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
        """

        Tests that the cache is not shared between different managers.

        Verifies that the cache is correctly isolated to each manager instance,
        by checking the number of queries made when retrieving content types
        using the same and different managers. This ensures that the cache is
        not accidentally shared, which could lead to incorrect results or
        unexpected behavior.

        The test covers the scenario where the same manager instance is used
        to retrieve content types, and then checks that a different manager
        instance does not reuse the cache from the first manager.

        """
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
        Tests the string representation of a ContentType object.

        Verifies that the string representation of a ContentType instance is correctly
        formatted as 'App Label | Model Name'.
        """
        ct = ContentType.objects.get(app_label="contenttypes_tests", model="site")
        self.assertEqual(str(ct), "Contenttypes_Tests | site")

    def test_str_auth(self):
        """
        Tests the string representation of a ContentType object for the 'group' model in the 'auth' app.

         The test verifies that the string representation of the ContentType object is correctly formatted, 
         returning a string that includes the app label and model name, separated by a vertical bar and 
         prefixed with 'Authentication and Authorization'.
        """
        ct = ContentType.objects.get(app_label="auth", model="group")
        self.assertEqual(str(ct), "Authentication and Authorization | group")

    def test_name(self):
        """

        Checks if the name of a content type matches its expected value.

        This test function verifies that the content type with the model 'site' in the 
        'contenttypes_tests' app has the correct name.

        Returns:
            None

        Raises:
            AssertionError: If the content type name does not match 'site'.

        """
        ct = ContentType.objects.get(app_label="contenttypes_tests", model="site")
        self.assertEqual(ct.name, "site")

    def test_app_labeled_name(self):
        """
        Tests the retrieval of an app-labeled name for a given content type.

        Verifies that the app_labeled_name property returns the correct string,
        which includes the app label and model name, separated by a vertical bar.
        The format of the app-labeled name is '<app_label> | <model_name>', with the
        app label being the name of the application that the content type belongs to,
        and the model name being the name of the model that the content type represents.

        This test case ensures that the app_labeled_name property is correctly
        formatted and contains the expected information for a given content type.
        """
        ct = ContentType.objects.get(app_label="contenttypes_tests", model="site")
        self.assertEqual(ct.app_labeled_name, "Contenttypes_Tests | site")

    def test_name_unknown_model(self):
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
        Checks that GenericPrefetch initialization raises a TypeError when the required 'querysets' argument is missing, ensuring proper error handling for invalid class instantiation.
        """
        msg = (
            "GenericPrefetch.__init__() missing 1 required "
            "positional argument: 'querysets'"
        )
        with self.assertRaisesMessage(TypeError, msg):
            GenericPrefetch("question")

    def test_values_queryset(self):
        """
        Tests that the GenericPrefetch class raises a ValueError when attempting to prefetch querysets 
        using the values() or values_list() methods.

        This test ensures that the GenericPrefetch class correctly handles and rejects querysets 
        that use raw(), values(), or values_list() methods, which are not compatible with prefetching.

        Raises:
            ValueError: If the queryset uses values() or values_list() methods.

        """
        msg = "Prefetch querysets cannot use raw(), values(), and values_list()."
        with self.assertRaisesMessage(ValueError, msg):
            GenericPrefetch("question", [Author.objects.values("pk")])
        with self.assertRaisesMessage(ValueError, msg):
            GenericPrefetch("question", [Author.objects.values_list("pk")])

    def test_raw_queryset(self):
        msg = "Prefetch querysets cannot use raw(), values(), and values_list()."
        with self.assertRaisesMessage(ValueError, msg):
            GenericPrefetch("question", [Author.objects.raw("select pk from author")])
