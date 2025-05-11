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
        Tests the ContentType cache to ensure it works correctly, verifying that lookups via model, ID, or natural key only hit the database on the first lookup and subsequent lookups use the cached result.
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
        state = ProjectState.from_apps(apps.get_app_config("contenttypes"))
        ContentType = state.apps.get_model("contenttypes", "ContentType")
        cts = ContentType.objects.get_for_models(ContentType)
        self.assertEqual(
            cts, {ContentType: ContentType.objects.get_for_model(ContentType)}
        )

    @isolate_apps("contenttypes_tests")
    def test_get_for_models_migrations_create_model(self):
        """

        Tests that ContentType.objects.get_for_models() returns the correct content types
        for models when migrations have created the models.

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
        """
        Tests that the get_for_models method of ContentType's manager correctly retrieves content types for multiple models, and that it uses caching to avoid repeated database queries.
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
        Tests the creation of a content type using ContentTypeManager.get_for_model() if it does not already exist in the database for a given model.
        """

        class ModelCreatedOnTheFly(models.Model):
            name = models.CharField()

        ct = ContentType.objects.get_for_model(ModelCreatedOnTheFly)
        self.assertEqual(ct.app_label, "contenttypes_tests")
        self.assertEqual(ct.model, "modelcreatedonthefly")
        self.assertEqual(str(ct), "modelcreatedonthefly")

    def test_get_for_concrete_model(self):
        """
        Tests the functionality of getting a ContentType object for a model, 
         verifying that the `for_concrete_model` keyword argument correctly 
         handles concrete, proxy, and deferred models.
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
        Verifies that the `for_concrete_models` argument functions correctly with various model types, including concrete, proxy, and deferred models, ensuring accurate content type retrieval.
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
        Tests whether the cache used by ContentType managers is isolated to each manager instance, 
        preventing cache sharing between managers. Verifies that each manager fetches data 
        independently and caches it for subsequent lookups.
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

        Tests that the system handles leftover content type records in the database for which no model is defined.
        Verifies that the functionality does not break when displaying content types, even if a corresponding model is missing.

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
        Verifies that retrieving content types does not break when a model with the same name exists in another app, but the original model is no longer defined.
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
        ct = ContentType.objects.get(app_label="contenttypes_tests", model="site")
        self.assertEqual(str(ct), "Contenttypes_Tests | site")

    def test_str_auth(self):
        ct = ContentType.objects.get(app_label="auth", model="group")
        self.assertEqual(str(ct), "Authentication and Authorization | group")

    def test_name(self):
        ct = ContentType.objects.get(app_label="contenttypes_tests", model="site")
        self.assertEqual(ct.name, "site")

    def test_app_labeled_name(self):
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
        msg = (
            "GenericPrefetch.__init__() missing 1 required "
            "positional argument: 'querysets'"
        )
        with self.assertRaisesMessage(TypeError, msg):
            GenericPrefetch("question")

    def test_values_queryset(self):
        """
        Tests that prefetch querysets do not use values() or values_list() methods, 
        raising a ValueError with a corresponding error message.
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
