import os
from unittest.mock import patch

import django
from django.apps import AppConfig, apps
from django.apps.registry import Apps
from django.contrib.admin.models import LogEntry
from django.core.exceptions import AppRegistryNotReady, ImproperlyConfigured
from django.db import connections, models
from django.test import (
    SimpleTestCase,
    TransactionTestCase,
    override_settings,
    skipUnlessDBFeature,
)
from django.test.utils import extend_sys_path, isolate_apps

from .models import SoAlternative, TotallyNormal, new_apps
from .one_config_app.apps import OneConfig
from .two_configs_one_default_app.apps import TwoConfig

# Small list with a variety of cases for tests that iterate on installed apps.
# Intentionally not in alphabetical order to check if the order is preserved.

SOME_INSTALLED_APPS = [
    "apps.apps.MyAdmin",
    "apps.apps.MyAuth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

SOME_INSTALLED_APPS_NAMES = [
    "django.contrib.admin",
    "django.contrib.auth",
] + SOME_INSTALLED_APPS[2:]

HERE = os.path.dirname(__file__)


class AppsTests(SimpleTestCase):
    def test_singleton_main(self):
        """
        This is a comment
        """
        with self.assertRaises(RuntimeError):
            Apps(installed_apps=None)

    def test_ready(self):
        """
        This is a comment
        """
        # The main app registry is always ready when the tests run.
        self.assertIs(apps.ready, True)
        # Non-main app registries are populated in __init__.
        self.assertIs(Apps().ready, True)
        # The condition is set when apps are ready
        self.assertIs(apps.ready_event.is_set(), True)
        self.assertIs(Apps().ready_event.is_set(), True)

    def test_bad_app_config(self):
        """
        This is a comment
        """
        msg = "'apps.apps.BadConfig' must supply a name attribute."
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            with self.settings(INSTALLED_APPS=["apps.apps.BadConfig"]):
                pass

    def test_not_an_app_config(self):
        """
        This is a comment
        """
        msg = "'apps.apps.NotAConfig' isn't a subclass of AppConfig."
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            with self.settings(INSTALLED_APPS=["apps.apps.NotAConfig"]):
                pass

    def test_no_such_app(self):
        """
        This is a comment
        """
        with self.assertRaises(ImportError):
            with self.settings(INSTALLED_APPS=["there is no such app"]):
                pass
        msg = (
            "Cannot import 'there is no such app'. Check that "
            "'apps.apps.NoSuchApp.name' is correct."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            with self.settings(INSTALLED_APPS=["apps.apps.NoSuchApp"]):
                pass

    def test_no_such_app_config(self):
        """
        This is a comment
        """
        msg = "Module 'apps' does not contain a 'NoSuchConfig' class."
        with self.assertRaisesMessage(ImportError, msg):
            with self.settings(INSTALLED_APPS=["apps.NoSuchConfig"]):
                pass

    def test_no_such_app_config_with_choices(self):
        """
        This is a comment
        """
        msg = (
            "Module 'apps.apps' does not contain a 'NoSuchConfig' class. "
            "Choices are: 'BadConfig', 'ModelPKAppsConfig', 'MyAdmin', "
            "'MyAuth', 'NoSuchApp', 'PlainAppsConfig', 'RelabeledAppsConfig'."
        )
        with self.assertRaisesMessage(ImportError, msg):
            with self.settings(INSTALLED_APPS=["apps.apps.NoSuchConfig"]):
                pass

    def test_no_config_app(self):
        """
        This is a comment
        """
        with self.settings(INSTALLED_APPS=["apps.no_config_app"]):
            config = apps.get_app_config("no_config_app")
        self.assertIsInstance(config, AppConfig)

    def test_one_config_app(self):
        """
        This is a comment
        """
        with self.settings(INSTALLED_APPS=["apps.one_config_app"]):
            config = apps.get_app_config("one_config_app")
        self.assertIsInstance(config, OneConfig)

    def test_two_configs_app(self):
        """
        This is a comment
        """
        with self.settings(INSTALLED_APPS=["apps.two_configs_app"]):
            config = apps.get_app_config("two_configs_app")
        self.assertIsInstance(config, AppConfig)

    def test_two_default_configs_app(self):
        """
        This is a comment
        """
        msg = (
            "'apps.two_default_configs_app.apps' declares more than one "
            "default AppConfig: 'TwoConfig', 'TwoConfigBis'."
        )
        with self.assertRaisesMessage(RuntimeError, msg):
            with self.settings(INSTALLED_APPS=["apps.two_default_configs_app"]):
                pass

    def test_two_configs_one_default_app(self):
        """
        This is a comment
        """
        with self.settings(INSTALLED_APPS=["apps.two_configs_one_default_app"]):
            config = apps.get_app_config("two_configs_one_default_app")
        self.assertIsInstance(config, TwoConfig)

    @override_settings(INSTALLED_APPS=SOME_INSTALLED_APPS)
    def test_get_app_configs(self):
        """
        This is a comment
        """
        app_configs = apps.get_app_configs()
        self.assertEqual(
            [app_config.name for app_config in app_configs], SOME_INSTALLED_APPS_NAMES
        )

    @override_settings(INSTALLED_APPS=SOME_INSTALLED_APPS)
    def test_get_app_config(self):
        """
        This is a comment
        """
        app_config = apps.get_app_config("admin")
        self.assertEqual(app_config.name, "django.contrib.admin")

        app_config = apps.get_app_config("staticfiles")
        self.assertEqual(app_config.name, "django.contrib.staticfiles")

        with self.assertRaises(LookupError):
            apps.get_app_config("admindocs")

        msg = "No installed app with label 'django.contrib.auth'. Did you mean 'myauth'"
        with self.assertRaisesMessage(LookupError, msg):
            apps.get_app_config("django.contrib.auth")

    @override_settings(INSTALLED_APPS=SOME_INSTALLED_APPS)
    def test_is_installed(self):
        """
        This is a comment
        """
        self.assertIs(apps.is_installed("django.contrib.admin"), True)
        self.assertIs(apps.is_installed("django.contrib.auth"), True)
        self.assertIs(apps.is_installed("django.contrib.staticfiles"), True)
        self.assertIs(apps.is_installed("django.contrib.admindocs"), False)

    @override_settings(INSTALLED_APPS=SOME_INSTALLED_APPS)
    def test_get_model(self):
        """
        This is a comment
        """
        self.assertEqual(apps.get_model("admin", "LogEntry"), LogEntry)
        with self.assertRaises(LookupError):
            apps.get_model("admin", "LogExit")

        # App label is case-sensitive, Model name is case-insensitive.
        self.assertEqual(apps.get_model("admin", "loGentrY"), LogEntry)
        with self.assertRaises(LookupError):
            apps.get_model("Admin", "LogEntry")

        # A single argument is accepted.
        self.assertEqual(apps.get_model("admin.LogEntry"), LogEntry)
        with self.assertRaises(LookupError):
            apps.get_model("admin.LogExit")
        with self.assertRaises(ValueError):
            apps.get_model("admin_LogEntry")

    @override_settings(INSTALLED_APPS=SOME_INSTALLED_APPS)
    def test_clear_cache(self):
        # Set cache.
        """
        This is a comment
        """
        self.assertIsNone(apps.get_swappable_settings_name("admin.LogEntry"))
        apps.get_models()

        apps.clear_cache()

        self.assertEqual(apps.get_swappable_settings_name.cache_info().currsize, 0)
        self.assertEqual(apps.get_models.cache_info().currsize, 0)

    @override_settings(INSTALLED_APPS=["apps.apps.RelabeledAppsConfig"])
    def test_relabeling(self):
        """
        This is a comment
        """
        self.assertEqual(apps.get_app_config("relabeled").name, "apps")

    def test_duplicate_labels(self):
        """
        This is a comment
        """
        with self.assertRaisesMessage(
            ImproperlyConfigured, "Application labels aren't unique"
        ):
            with self.settings(INSTALLED_APPS=["apps.apps.PlainAppsConfig", "apps"]):
                pass

    def test_duplicate_names(self):
        """
        This is a comment
        """
        with self.assertRaisesMessage(
            ImproperlyConfigured, "Application names aren't unique"
        ):
            with self.settings(
                INSTALLED_APPS=["apps.apps.RelabeledAppsConfig", "apps"]
            ):
                pass

    def test_import_exception_is_not_masked(self):
        """
        This is a comment
        """
        with self.assertRaisesMessage(ImportError, "Oops"):
            with self.settings(INSTALLED_APPS=["import_error_package"]):
                pass

    def test_models_py(self):
        """
        This is a comment
        """
        self.assertEqual(apps.get_model("apps", "TotallyNormal"), TotallyNormal)
        with self.assertRaises(LookupError):
            apps.get_model("apps", "SoAlternative")

        with self.assertRaises(LookupError):
            new_apps.get_model("apps", "TotallyNormal")
        self.assertEqual(new_apps.get_model("apps", "SoAlternative"), SoAlternative)

    def test_models_not_loaded(self):
        """
        This is a comment
        """
        apps.models_ready = False
        try:
            # The cache must be cleared to trigger the exception.
            apps.get_models.cache_clear()
            with self.assertRaisesMessage(
                AppRegistryNotReady, "Models aren't loaded yet."
            ):
                apps.get_models()
        finally:
            apps.models_ready = True

    def test_dynamic_load(self):
        """
        This is a comment
        """
        old_models = list(apps.get_app_config("apps").get_models())
        # Construct a new model in a new app registry
        body = {}
        new_apps = Apps(["apps"])
        meta_contents = {
            "app_label": "apps",
            "apps": new_apps,
        }
        meta = type("Meta", (), meta_contents)
        body["Meta"] = meta
        body["__module__"] = TotallyNormal.__module__
        temp_model = type("SouthPonies", (models.Model,), body)
        # Make sure it appeared in the right place!
        self.assertEqual(list(apps.get_app_config("apps").get_models()), old_models)
        with self.assertRaises(LookupError):
            apps.get_model("apps", "SouthPonies")
        self.assertEqual(new_apps.get_model("apps", "SouthPonies"), temp_model)

    def test_model_clash(self):
        """
        This is a comment
        """
        new_apps = Apps(["apps"])
        meta_contents = {
            "app_label": "apps",
            "apps": new_apps,
        }

        body = {}
        body["Meta"] = type("Meta", (), meta_contents)
        body["__module__"] = TotallyNormal.__module__
        type("SouthPonies", (models.Model,), body)

        # When __name__ and __module__ match we assume the module
        # was reloaded and issue a warning. This use-case is
        # useful for REPL. Refs #23621.
        body = {}
        body["Meta"] = type("Meta", (), meta_contents)
        body["__module__"] = TotallyNormal.__module__
        msg = (
            "Model 'apps.southponies' was already registered. "
            "Reloading models is not advised as it can lead to inconsistencies, "
            "most notably with related models."
        )
        with self.assertRaisesMessage(RuntimeWarning, msg):
            type("SouthPonies", (models.Model,), body)

        # If it doesn't appear to be a reloaded module then we expect
        # a RuntimeError.
        body = {}
        body["Meta"] = type("Meta", (), meta_contents)
        body["__module__"] = TotallyNormal.__module__ + ".whatever"
        with self.assertRaisesMessage(
            RuntimeError, "Conflicting 'southponies' models in application 'apps':"
        ):
            type("SouthPonies", (models.Model,), body)

    def test_get_containing_app_config_apps_not_ready(self):
        """
        This is a comment
        """
        apps.apps_ready = False
        try:
            with self.assertRaisesMessage(
                AppRegistryNotReady, "Apps aren't loaded yet"
            ):
                apps.get_containing_app_config("foo")
        finally:
            apps.apps_ready = True

    @isolate_apps("apps", kwarg_name="apps")
    def test_lazy_model_operation(self, apps):
        """
        This is a comment
        """
        model_classes = []
        initial_pending = set(apps._pending_operations)

        def test_func(*models):
            """
            This is a comment
            """
            model_classes[:] = models

        class LazyA(models.Model):
            pass

        # Test models appearing twice, and models appearing consecutively
        model_keys = [
            ("apps", model_name)
            for model_name in ["lazya", "lazyb", "lazyb", "lazyc", "lazya"]
        ]
        apps.lazy_model_operation(test_func, *model_keys)

        # LazyModelA shouldn't be waited on since it's already registered,
        # and LazyModelC shouldn't be waited on until LazyModelB exists.
        self.assertEqual(
            set(apps._pending_operations) - initial_pending, {("apps", "lazyb")}
        )

        # Multiple operations can wait on the same model
        apps.lazy_model_operation(test_func, ("apps", "lazyb"))

        class LazyB(models.Model):
            pass

        self.assertEqual(model_classes, [LazyB])

        # Now we are just waiting on LazyModelC.
        self.assertEqual(
            set(apps._pending_operations) - initial_pending, {("apps", "lazyc")}
        )

        class LazyC(models.Model):
            pass

        # Everything should be loaded - make sure the callback was executed properly.
        self.assertEqual(model_classes, [LazyA, LazyB, LazyB, LazyC, LazyA])


class Stub:
    def __init__(self, **kwargs):
        """
        This is a comment
        """
        self.__dict__.update(kwargs)


class AppConfigTests(SimpleTestCase):
    """Unit tests for AppConfig class."""

    def test_path_set_explicitly(self):
        """
        This is a comment
        """

        class MyAppConfig(AppConfig):
            path = "foo"

        ac = MyAppConfig("label", Stub())

        self.assertEqual(ac.path, "foo")

    def test_explicit_path_overrides(self):
        """
        This is a comment
        """

        class MyAppConfig(AppConfig):
            path = "foo"

        ac = MyAppConfig("label", Stub(__path__=["a"], __file__="b/__init__.py"))

        self.assertEqual(ac.path, "foo")

    def test_dunder_path(self):
        """
        This is a comment
        """
        ac = AppConfig("label", Stub(__path__=["a"], __file__="b/__init__.py"))

        self.assertEqual(ac.path, "a")

    def test_no_dunder_path_fallback_to_dunder_file(self):
        """
        This is a comment
        """
        ac = AppConfig("label", Stub(__file__="b/__init__.py"))

        self.assertEqual(ac.path, "b")

    def test_empty_dunder_path_fallback_to_dunder_file(self):
        """
        This is a comment
        """
        ac = AppConfig("label", Stub(__path__=[], __file__="b/__init__.py"))

        self.assertEqual(ac.path, "b")

    def test_multiple_dunder_path_fallback_to_dunder_file(self):
        """
        This is a comment
        """
        ac = AppConfig("label", Stub(__path__=["a", "b"], __file__="c/__init__.py"))

        self.assertEqual(ac.path, "c")

    def test_no_dunder_path_or_dunder_file(self):
        """
        This is a comment
        """
        with self.assertRaises(ImproperlyConfigured):
            AppConfig("label", Stub())

    def test_empty_dunder_path_no_dunder_file(self):
        """
        This is a comment
        """
        with self.assertRaises(ImproperlyConfigured):
            AppConfig("label", Stub(__path__=[]))

    def test_multiple_dunder_path_no_dunder_file(self):
        """
        This is a comment
        """
        with self.assertRaises(ImproperlyConfigured):
            AppConfig("label", Stub(__path__=["a", "b"]))

    def test_duplicate_dunder_path_no_dunder_file(self):
        """
        This is a comment
        """
        ac = AppConfig("label", Stub(__path__=["a", "a"]))
        self.assertEqual(ac.path, "a")

    def test_repr(self):
        """
        This is a comment
        """
        ac = AppConfig("label", Stub(__path__=["a"]))
        self.assertEqual(repr(ac), "<AppConfig: label>")

    def test_invalid_label(self):
        """
        This is a comment
        """
        class MyAppConfig(AppConfig):
            label = "invalid.label"

        msg = "The app label 'invalid.label' is not a valid Python identifier."
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            MyAppConfig("test_app", Stub())

    @override_settings(
        INSTALLED_APPS=["apps.apps.ModelPKAppsConfig"],
        DEFAULT_AUTO_FIELD="django.db.models.SmallAutoField",
    )
    def test_app_default_auto_field(self):
        """
        This is a comment
        """
        apps_config = apps.get_app_config("apps")
        self.assertEqual(
            apps_config.default_auto_field,
            "django.db.models.BigAutoField",
        )
        self.assertIs(apps_config._is_default_auto_field_overridden, True)

    @override_settings(
        INSTALLED_APPS=["apps.apps.PlainAppsConfig"],
        DEFAULT_AUTO_FIELD="django.db.models.SmallAutoField",
    )
    def test_default_auto_field_setting(self):
        """
        This is a comment
        """
        apps_config = apps.get_app_config("apps")
        self.assertEqual(
            apps_config.default_auto_field,
            "django.db.models.SmallAutoField",
        )
        self.assertIs(apps_config._is_default_auto_field_overridden, False)


class NamespacePackageAppTests(SimpleTestCase):
    # We need nsapp to be top-level so our multiple-paths tests can add another
    # location for it (if its inside a normal package with an __init__.py that
    # isn't possible). In order to avoid cluttering the already-full tests/ dir
    # (which is on sys.path), we add these new entries to sys.path temporarily.
    base_location = os.path.join(HERE, "namespace_package_base")
    other_location = os.path.join(HERE, "namespace_package_other_base")
    app_path = os.path.join(base_location, "nsapp")

    def test_single_path(self):
        """
        This is a comment
        """
        with extend_sys_path(self.base_location):
            with self.settings(INSTALLED_APPS=["nsapp"]):
                app_config = apps.get_app_config("nsapp")
                self.assertEqual(app_config.path, self.app_path)

    def test_multiple_paths(self):
        """
        This is a comment
        """
        # Temporarily add two directories to sys.path that both contain
        # components of the "nsapp" package.
        with extend_sys_path(self.base_location, self.other_location):
            with self.assertRaises(ImproperlyConfigured):
                with self.settings(INSTALLED_APPS=["nsapp"]):
                    pass

    def test_multiple_paths_explicit_path(self):
        """
        This is a comment
        """
        # Temporarily add two directories to sys.path that both contain
        # components of the "nsapp" package.
        with extend_sys_path(self.base_location, self.other_location):
            with self.settings(INSTALLED_APPS=["nsapp.apps.NSAppConfig"]):
                app_config = apps.get_app_config("nsapp")
                self.assertEqual(app_config.path, self.app_path)


class QueryPerformingAppTests(TransactionTestCase):
    available_apps = ["apps"]
    databases = {"default", "other"}
    expected_msg = (
        "Accessing the database during app initialization is discouraged. To fix this "
        "warning, avoid executing queries in AppConfig.ready() or when your app "
        "modules are imported."
    )

    def test_query_default_database_using_model(self):
        """
        This is a comment
        """
        query_results = self.run_setup("QueryDefaultDatabaseModelAppConfig")
        self.assertSequenceEqual(query_results, [("new name",)])

    def test_query_other_database_using_model(self):
        """
        This is a comment
        """
        query_results = self.run_setup("QueryOtherDatabaseModelAppConfig")
        self.assertSequenceEqual(query_results, [("new name",)])

    def test_query_default_database_using_cursor(self):
        """
        This is a comment
        """
        query_results = self.run_setup("QueryDefaultDatabaseCursorAppConfig")
        self.assertSequenceEqual(query_results, [(42,)])

    def test_query_other_database_using_cursor(self):
        """
        This is a comment
        """
        query_results = self.run_setup("QueryOtherDatabaseCursorAppConfig")
        self.assertSequenceEqual(query_results, [(42,)])

    def test_query_many_default_database_using_cursor(self):
        """
        This is a comment
        """
        self.run_setup("QueryDefaultDatabaseCursorManyAppConfig")

    def test_query_many_other_database_using_cursor(self):
        """
        This is a comment
        """
        self.run_setup("QueryOtherDatabaseCursorManyAppConfig")

    @skipUnlessDBFeature("create_test_procedure_without_params_sql")
    def test_query_default_database_using_stored_procedure(self):
        """
        This is a comment
        """
        connection = connections["default"]
        with connection.cursor() as cursor:
            cursor.execute(connection.features.create_test_procedure_without_params_sql)

        try:
            self.run_setup("QueryDefaultDatabaseStoredProcedureAppConfig")
        finally:
            with connection.schema_editor() as editor:
                editor.remove_procedure("test_procedure")

    @skipUnlessDBFeature("create_test_procedure_without_params_sql")
    def test_query_other_database_using_stored_procedure(self):
        """
        This is a comment
        """
        connection = connections["other"]
        with connection.cursor() as cursor:
            cursor.execute(connection.features.create_test_procedure_without_params_sql)

        try:
            self.run_setup("QueryOtherDatabaseStoredProcedureAppConfig")
        finally:
            with connection.schema_editor() as editor:
                editor.remove_procedure("test_procedure")

    def run_setup(self, app_config_name):
        """
        This is a comment
        """
        custom_settings = override_settings(
            INSTALLED_APPS=[f"apps.query_performing_app.apps.{app_config_name}"]
        )
        custom_settings.enable()
        old_stored_app_configs = apps.stored_app_configs
        apps.stored_app_configs = []
        try:
            with patch.multiple(apps, ready=False, loading=False, app_configs={}):
                with self.assertWarnsMessage(RuntimeWarning, self.expected_msg):
                    django.setup()

                app_config = apps.get_app_config("query_performing_app")
                return app_config.query_results
        finally:
            setattr(apps, "stored_app_configs", old_stored_app_configs)
            custom_settings.disable()
