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
        Verify that the deconstruct method of DeconstructibleClass returns the correct path, arguments, and keyword arguments for object reconstruction.
        """
        obj = DeconstructibleClass("arg", key="value")
        path, args, kwargs = obj.deconstruct()
        self.assertEqual(path, "utils_tests.test_deconstruct.DeconstructibleClass")
        self.assertEqual(args, ("arg",))
        self.assertEqual(kwargs, {"key": "value"})

    def test_deconstruct_with_path(self):
        """
        Tests the deconstruction of an object with a specified path, ensuring it correctly decomposes into its constituent path, arguments, and keyword arguments.
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
        Tests the deconstruction of a DeconstructibleChildClass instance into path, args, and kwargs, verifying correct decomposition of object attributes.
        """
        obj = DeconstructibleChildClass("arg", key="value")
        path, args, kwargs = obj.deconstruct()
        self.assertEqual(path, "utils_tests.test_deconstruct.DeconstructibleChildClass")
        self.assertEqual(args, ("arg",))
        self.assertEqual(kwargs, {"key": "value"})

    def test_deconstruct_child_with_path(self):
        """
        Tests the deconstruction of a child class that has a defined path, verifying that the path, arguments, and keyword arguments are correctly extracted.
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
        Tests that deconstructing an object with an invalid path raises a ValueError.

        This checks that an informative error message is raised when attempting to serialize
        an object that cannot be resolved due to being defined inside another class or module.

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

        Tests the deconstruct method of DeconstructibleInvalidPathChildClass with an invalid path, 
        verifying it correctly returns the class path and original constructor arguments.

        """
        obj = DeconstructibleInvalidPathChildClass("arg", key="value")
        path, args, kwargs = obj.deconstruct()
        self.assertEqual(
            path,
            "utils_tests.test_deconstruct.DeconstructibleInvalidPathChildClass",
        )
        self.assertEqual(args, ("arg",))
        self.assertEqual(kwargs, {"key": "value"})
