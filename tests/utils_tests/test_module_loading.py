import os
import sys
import unittest
from importlib import import_module
from zipimport import zipimporter

from django.test import SimpleTestCase, modify_settings
from django.test.utils import extend_sys_path
from django.utils.module_loading import (
    autodiscover_modules,
    import_string,
    module_has_submodule,
)


class DefaultLoader(unittest.TestCase):
    def test_loader(self):
        "Normal module existence can be tested"
        test_module = import_module("utils_tests.test_module")
        test_no_submodule = import_module("utils_tests.test_no_submodule")

        # An importable child
        self.assertTrue(module_has_submodule(test_module, "good_module"))
        mod = import_module("utils_tests.test_module.good_module")
        self.assertEqual(mod.content, "Good Module")

        # A child that exists, but will generate an import error if loaded
        self.assertTrue(module_has_submodule(test_module, "bad_module"))
        with self.assertRaises(ImportError):
            import_module("utils_tests.test_module.bad_module")

        # A child that doesn't exist
        self.assertFalse(module_has_submodule(test_module, "no_such_module"))
        with self.assertRaises(ImportError):
            import_module("utils_tests.test_module.no_such_module")

        # A child that doesn't exist, but is the name of a package on the path
        self.assertFalse(module_has_submodule(test_module, "django"))
        with self.assertRaises(ImportError):
            import_module("utils_tests.test_module.django")

        # Don't be confused by caching of import misses
        import types  # NOQA: causes attempted import of utils_tests.types

        self.assertFalse(module_has_submodule(sys.modules["utils_tests"], "types"))

        # A module which doesn't have a __path__ (so no submodules)
        self.assertFalse(module_has_submodule(test_no_submodule, "anything"))
        with self.assertRaises(ImportError):
            import_module("utils_tests.test_no_submodule.anything")

    def test_has_sumbodule_with_dotted_path(self):
        """Nested module existence can be tested."""
        test_module = import_module("utils_tests.test_module")
        # A grandchild that exists.
        self.assertIs(
            module_has_submodule(test_module, "child_module.grandchild_module"), True
        )
        # A grandchild that doesn't exist.
        self.assertIs(
            module_has_submodule(test_module, "child_module.no_such_module"), False
        )
        # A grandchild whose parent doesn't exist.
        self.assertIs(
            module_has_submodule(test_module, "no_such_module.grandchild_module"), False
        )
        # A grandchild whose parent is not a package.
        self.assertIs(
            module_has_submodule(test_module, "good_module.no_such_module"), False
        )


class EggLoader(unittest.TestCase):
    def setUp(self):
        self.egg_dir = "%s/eggs" % os.path.dirname(__file__)

    def tearDown(self):
        """
        Teardown method to clean up the system module cache and remove imported modules.

        This method is used to reset the state of the system after a test has been executed.
        It clears the system path importer cache and removes specific modules that were imported during the test,
        ensuring a clean environment for subsequent tests.

        The removed modules include various sub-modules and packages within the 'egg_module' namespace,
        preventing any potential conflicts or residual state from affecting future tests.
        """
        sys.path_importer_cache.clear()

        sys.modules.pop("egg_module.sub1.sub2.bad_module", None)
        sys.modules.pop("egg_module.sub1.sub2.good_module", None)
        sys.modules.pop("egg_module.sub1.sub2", None)
        sys.modules.pop("egg_module.sub1", None)
        sys.modules.pop("egg_module.bad_module", None)
        sys.modules.pop("egg_module.good_module", None)
        sys.modules.pop("egg_module", None)

    def test_shallow_loader(self):
        "Module existence can be tested inside eggs"
        egg_name = "%s/test_egg.egg" % self.egg_dir
        with extend_sys_path(egg_name):
            egg_module = import_module("egg_module")

            # An importable child
            self.assertTrue(module_has_submodule(egg_module, "good_module"))
            mod = import_module("egg_module.good_module")
            self.assertEqual(mod.content, "Good Module")

            # A child that exists, but will generate an import error if loaded
            self.assertTrue(module_has_submodule(egg_module, "bad_module"))
            with self.assertRaises(ImportError):
                import_module("egg_module.bad_module")

            # A child that doesn't exist
            self.assertFalse(module_has_submodule(egg_module, "no_such_module"))
            with self.assertRaises(ImportError):
                import_module("egg_module.no_such_module")

    def test_deep_loader(self):
        "Modules deep inside an egg can still be tested for existence"
        egg_name = "%s/test_egg.egg" % self.egg_dir
        with extend_sys_path(egg_name):
            egg_module = import_module("egg_module.sub1.sub2")

            # An importable child
            self.assertTrue(module_has_submodule(egg_module, "good_module"))
            mod = import_module("egg_module.sub1.sub2.good_module")
            self.assertEqual(mod.content, "Deep Good Module")

            # A child that exists, but will generate an import error if loaded
            self.assertTrue(module_has_submodule(egg_module, "bad_module"))
            with self.assertRaises(ImportError):
                import_module("egg_module.sub1.sub2.bad_module")

            # A child that doesn't exist
            self.assertFalse(module_has_submodule(egg_module, "no_such_module"))
            with self.assertRaises(ImportError):
                import_module("egg_module.sub1.sub2.no_such_module")


class ModuleImportTests(SimpleTestCase):
    def test_import_string(self):
        cls = import_string("django.utils.module_loading.import_string")
        self.assertEqual(cls, import_string)

        # Test exceptions raised
        with self.assertRaises(ImportError):
            import_string("no_dots_in_path")
        msg = 'Module "utils_tests" does not define a "unexistent" attribute'
        with self.assertRaisesMessage(ImportError, msg):
            import_string("utils_tests.unexistent")


@modify_settings(INSTALLED_APPS={"append": "utils_tests.test_module"})
class AutodiscoverModulesTestCase(SimpleTestCase):
    def tearDown(self):
        sys.path_importer_cache.clear()

        sys.modules.pop("utils_tests.test_module.another_bad_module", None)
        sys.modules.pop("utils_tests.test_module.another_good_module", None)
        sys.modules.pop("utils_tests.test_module.bad_module", None)
        sys.modules.pop("utils_tests.test_module.good_module", None)
        sys.modules.pop("utils_tests.test_module", None)

    def test_autodiscover_modules_found(self):
        autodiscover_modules("good_module")

    def test_autodiscover_modules_not_found(self):
        autodiscover_modules("missing_module")

    def test_autodiscover_modules_found_but_bad_module(self):
        with self.assertRaisesMessage(
            ImportError, "No module named 'a_package_name_that_does_not_exist'"
        ):
            autodiscover_modules("bad_module")

    def test_autodiscover_modules_several_one_bad_module(self):
        """
        Tests that autodiscover_modules function correctly handles the case where multiple modules are provided, and one of them does not exist. 
        It verifies that an ImportError is raised with the expected message when trying to import a non-existent module.
        """
        with self.assertRaisesMessage(
            ImportError, "No module named 'a_package_name_that_does_not_exist'"
        ):
            autodiscover_modules("good_module", "bad_module")

    def test_autodiscover_modules_several_found(self):
        autodiscover_modules("good_module", "another_good_module")

    def test_autodiscover_modules_several_found_with_registry(self):
        from .test_module import site

        autodiscover_modules("good_module", "another_good_module", register_to=site)
        self.assertEqual(site._registry, {"lorem": "ipsum"})

    def test_validate_registry_keeps_intact(self):
        """
        Tests that the registry remains intact when an exception occurs during autodiscovery.

        Verifies that an exception is raised when attempting to autodiscover a module and 
        that the registry is not modified as a result of the exception.

        Ensures the registry's state is preserved, even in the event of an error, to 
        prevent unintended changes or corruption of the registry's data.
        """
        from .test_module import site

        with self.assertRaisesMessage(Exception, "Some random exception."):
            autodiscover_modules("another_bad_module", register_to=site)
        self.assertEqual(site._registry, {})

    def test_validate_registry_resets_after_erroneous_module(self):
        """

        Test that the internal registry is properly reset after encountering an erroneous module during autodiscovery.

        This test ensures that when an exception occurs during the registration of a module, the internal registry is restored to its original state, preventing any partial or corrupted updates.

        It verifies that the registry is reset by checking its contents after the exception has been raised, confirming that it matches the expected initial state.

        """
        from .test_module import site

        with self.assertRaisesMessage(Exception, "Some random exception."):
            autodiscover_modules(
                "another_good_module", "another_bad_module", register_to=site
            )
        self.assertEqual(site._registry, {"lorem": "ipsum"})

    def test_validate_registry_resets_after_missing_module(self):
        """
        Validate that the registry resets to its default state after attempting to auto-discover non-existent modules.

        This test checks that when the autodiscover_modules function is called with a mix of existing and non-existing modules, 
        the registry returns to its expected initial state, despite encountering missing modules during the discovery process.
        """
        from .test_module import site

        autodiscover_modules(
            "does_not_exist", "another_good_module", "does_not_exist2", register_to=site
        )
        self.assertEqual(site._registry, {"lorem": "ipsum"})


class TestFinder:
    def __init__(self, *args, **kwargs):
        self.importer = zipimporter(*args, **kwargs)

    def find_spec(self, path, target=None):
        return self.importer.find_spec(path, target)


class CustomLoader(EggLoader):
    """The Custom Loader test is exactly the same as the EggLoader, but
    it uses a custom defined Loader class. Although the EggLoader combines both
    functions into one class, this isn't required.
    """

    def setUp(self):
        """
        Sets up the test environment by modifying the system path hooks and importer cache.

        This method prepares the environment for testing by inserting a custom finder
        at the beginning of the system path hooks and clearing the importer cache. This
        ensures that the test setup can control the import process and provide the
        necessary test fixtures.

        The custom finder, TestFinder, is inserted at the beginning of the system path
        hooks to allow it to take precedence over other finders. The importer cache is
        cleared to prevent any stale imports from interfering with the test setup.

        This method is intended to be called at the start of each test case to ensure a
        clean and consistent environment for testing.
        """
        super().setUp()
        sys.path_hooks.insert(0, TestFinder)
        sys.path_importer_cache.clear()

    def tearDown(self):
        super().tearDown()
        sys.path_hooks.pop(0)
