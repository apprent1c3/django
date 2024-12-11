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
        obj = DeconstructibleClass("arg", key="value")
        path, args, kwargs = obj.deconstruct()
        self.assertEqual(path, "utils_tests.test_deconstruct.DeconstructibleClass")
        self.assertEqual(args, ("arg",))
        self.assertEqual(kwargs, {"key": "value"})

    def test_deconstruct_with_path(self):
        obj = DeconstructibleWithPathClass("arg", key="value")
        path, args, kwargs = obj.deconstruct()
        self.assertEqual(
            path,
            "utils_tests.deconstructible_classes.DeconstructibleWithPathClass",
        )
        self.assertEqual(args, ("arg",))
        self.assertEqual(kwargs, {"key": "value"})

    def test_deconstruct_child(self):
        obj = DeconstructibleChildClass("arg", key="value")
        path, args, kwargs = obj.deconstruct()
        self.assertEqual(path, "utils_tests.test_deconstruct.DeconstructibleChildClass")
        self.assertEqual(args, ("arg",))
        self.assertEqual(kwargs, {"key": "value"})

    def test_deconstruct_child_with_path(self):
        """

        Tests the deconstruction of a child class instance with a path.

        This test case verifies that the deconstruct method correctly extracts the path,
        positional arguments, and keyword arguments from a DeconstructibleWithPathChildClass instance.
        The test checks that the deconstructed path matches the expected full path to the class,
        and that the positional and keyword arguments are correctly identified and returned.

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
        Tests that attempting to deconstruct an object with an invalid path raises a ValueError.

        This test case verifies that a ValueError is raised when trying to deconstruct an object that 
        cannot be serialized due to its location (e.g. an inner class). It checks that the error message 
        includes relevant information about the issue, such as the object name and the recommended 
        solution, as well as a link to the Django documentation for further details.

        The test ensures that the error handling for object deconstruction is correct and provides 
        useful feedback to the user when an invalid object is encountered.
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
        obj = DeconstructibleInvalidPathChildClass("arg", key="value")
        path, args, kwargs = obj.deconstruct()
        self.assertEqual(
            path,
            "utils_tests.test_deconstruct.DeconstructibleInvalidPathChildClass",
        )
        self.assertEqual(args, ("arg",))
        self.assertEqual(kwargs, {"key": "value"})
