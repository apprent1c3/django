from django.test import SimpleTestCase
from django.utils.deconstruct import deconstructible
from django.utils.version import get_docs_version


@deconstructible()
class DeconstructibleClass:
    pass


class DeconstructibleChildClass(DeconstructibleClass):
    pass


@deconstructible(
    path="utils_tests.deconstructible_classes.DeconstructibleWithPathClass"
)
class DeconstructibleWithPathClass:
    pass


class DeconstructibleWithPathChildClass(DeconstructibleWithPathClass):
    pass


@deconstructible(
    path="utils_tests.deconstructible_classes.DeconstructibleInvalidPathClass",
)
class DeconstructibleInvalidPathClass:
    pass


class DeconstructibleInvalidPathChildClass(DeconstructibleInvalidPathClass):
    pass


class DeconstructibleTests(SimpleTestCase):
    def test_deconstruct(self):
        """
        Tests the deconstruction of a DeconstructibleClass instance into its path, positional arguments, and keyword arguments.
        """
        obj = DeconstructibleClass("arg", key="value")
        path, args, kwargs = obj.deconstruct()
        self.assertEqual(path, "utils_tests.test_deconstruct.DeconstructibleClass")
        self.assertEqual(args, ("arg",))
        self.assertEqual(kwargs, {"key": "value"})

    def test_deconstruct_with_path(self):
        """
        Tests the deconstruction of a DeconstructibleWithPathClass instance.

        Verifies that the deconstruct method correctly extracts the class path, positional arguments, and keyword arguments from the instance.
        """
        obj = DeconstructibleWithPathClass("arg", key="value")
        path, args, kwargs = obj.deconstruct()
        self.assertEqual(
            path,
            "utils_tests.deconstructible_classes.DeconstructibleWithPathClass",
        )
        self.assertEqual(args, ("arg",))
        self.assertEqual(kwargs, {"key": "value"})

    def test_deconstruct_child(self):
        """
        Tests the deconstruction of a DeconstructibleChildClass instance, verifying that the resulting path, positional arguments, and keyword arguments are correctly generated.
        """
        obj = DeconstructibleChildClass("arg", key="value")
        path, args, kwargs = obj.deconstruct()
        self.assertEqual(path, "utils_tests.test_deconstruct.DeconstructibleChildClass")
        self.assertEqual(args, ("arg",))
        self.assertEqual(kwargs, {"key": "value"})

    def test_deconstruct_child_with_path(self):
        """
        Tests the deconstruction of a child object with a specified path, verifying that the path, arguments, and keyword arguments are correctly extracted from the object.
        """
        obj = DeconstructibleWithPathChildClass("arg", key="value")
        path, args, kwargs = obj.deconstruct()
        self.assertEqual(
            path,
            "utils_tests.test_deconstruct.DeconstructibleWithPathChildClass",
        )
        self.assertEqual(args, ("arg",))
        self.assertEqual(kwargs, {"key": "value"})

    def test_invalid_path(self):
        """
        Tests that attempting to deconstruct an object with an invalid path raises a ValueError with an informative error message, guiding the user to move the object to the main module body to enable serialization.
        """
        obj = DeconstructibleInvalidPathClass()
        docs_version = get_docs_version()
        msg = (
            f"Could not find object DeconstructibleInvalidPathClass in "
            f"utils_tests.deconstructible_classes.\n"
            f"Please note that you cannot serialize things like inner "
            f"classes. Please move the object into the main module body to "
            f"use migrations.\n"
            f"For more information, see "
            f"https://docs.djangoproject.com/en/{docs_version}/topics/"
            f"migrations/#serializing-values"
        )
        with self.assertRaisesMessage(ValueError, msg):
            obj.deconstruct()

    def test_parent_invalid_path(self):
        """
        Tests deconstruction of an object with an invalid path, verifying correct handling and extraction of path, positional arguments, and keyword arguments.
        """
        obj = DeconstructibleInvalidPathChildClass("arg", key="value")
        path, args, kwargs = obj.deconstruct()
        self.assertEqual(
            path,
            "utils_tests.test_deconstruct.DeconstructibleInvalidPathChildClass",
        )
        self.assertEqual(args, ("arg",))
        self.assertEqual(kwargs, {"key": "value"})
