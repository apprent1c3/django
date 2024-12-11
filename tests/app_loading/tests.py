import os

from django.apps import apps
from django.test import SimpleTestCase
from django.test.utils import extend_sys_path


class EggLoadingTest(SimpleTestCase):
    def setUp(self):
        """
        Setup method executed prior to running tests, preparing the environment.

            Initializes the directory path for eggs, relative to the current file's location.
            Additionally, schedules a cleanup action to clear the cache after the test completion,
            ensuring a clean state for subsequent tests.
        """
        self.egg_dir = "%s/eggs" % os.path.dirname(__file__)
        self.addCleanup(apps.clear_cache)

    def test_egg1(self):
        """Models module can be loaded from an app in an egg"""
        egg_name = "%s/modelapp.egg" % self.egg_dir
        with extend_sys_path(egg_name):
            with self.settings(INSTALLED_APPS=["app_with_models"]):
                models_module = apps.get_app_config("app_with_models").models_module
                self.assertIsNotNone(models_module)
        del apps.all_models["app_with_models"]

    def test_egg2(self):
        """
        Loading an app from an egg that has no models returns no models (and no
        error).
        """
        egg_name = "%s/nomodelapp.egg" % self.egg_dir
        with extend_sys_path(egg_name):
            with self.settings(INSTALLED_APPS=["app_no_models"]):
                models_module = apps.get_app_config("app_no_models").models_module
                self.assertIsNone(models_module)
        del apps.all_models["app_no_models"]

    def test_egg3(self):
        """
        Models module can be loaded from an app located under an egg's
        top-level package.
        """
        egg_name = "%s/omelet.egg" % self.egg_dir
        with extend_sys_path(egg_name):
            with self.settings(INSTALLED_APPS=["omelet.app_with_models"]):
                models_module = apps.get_app_config("app_with_models").models_module
                self.assertIsNotNone(models_module)
        del apps.all_models["app_with_models"]

    def test_egg4(self):
        """
        Loading an app with no models from under the top-level egg package
        generates no error.
        """
        egg_name = "%s/omelet.egg" % self.egg_dir
        with extend_sys_path(egg_name):
            with self.settings(INSTALLED_APPS=["omelet.app_no_models"]):
                models_module = apps.get_app_config("app_no_models").models_module
                self.assertIsNone(models_module)
        del apps.all_models["app_no_models"]

    def test_egg5(self):
        """
        Loading an app from an egg that has an import error in its models
        module raises that error.
        """
        egg_name = "%s/brokenapp.egg" % self.egg_dir
        with extend_sys_path(egg_name):
            with self.assertRaisesMessage(ImportError, "modelz"):
                with self.settings(INSTALLED_APPS=["broken_app"]):
                    pass


class GetModelsTest(SimpleTestCase):
    def setUp(self):
        """
        Sets up the test environment by importing the necessary models from the not_installed module.

        This method initializes the not_installed_module attribute with the imported models, making them available for use in subsequent tests.

        Note: This method is intended to be called before executing tests to ensure proper setup of the testing environment.
        """
        from .not_installed import models

        self.not_installed_module = models

    def test_get_model_only_returns_installed_models(self):
        with self.assertRaises(LookupError):
            apps.get_model("not_installed", "NotInstalledModel")

    def test_get_models_only_returns_installed_models(self):
        self.assertNotIn("NotInstalledModel", [m.__name__ for m in apps.get_models()])
