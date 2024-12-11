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
        """
        Tests the deconstruction of an object with a path.

        This test case verifies that the :meth:`deconstruct` method correctly breaks down an instance of 
        :cls:`DeconstructibleWithPathClass` into its constituent parts, specifically the path, positional 
        arguments, and keyword arguments. The test checks that these components are accurately extracted 
        and match the expected values, ensuring the object can be properly rebuilt from its deconstructed 
        state. 
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
        Tests the deconstruction functionality of DeconstructibleChildClass instances.

        This test ensures that the deconstruct method correctly breaks down an instance of 
        DeconstructibleChildClass into its constituent parts, including the full path to the 
        class, positional arguments, and keyword arguments. 

        The deconstruction process is verified by asserting that the returned path, arguments, 
        and keyword arguments match the expected values, confirming that the instance can be 
        successfully reconstructed from these deconstructed parts. 

        This functionality is crucial for accurately representing and serializing instances 
        of DeconstructibleChildClass, such as when storing or transmitting their configuration.

        """
        obj = DeconstructibleChildClass("arg", key="value")
        path, args, kwargs = obj.deconstruct()
        self.assertEqual(path, "utils_tests.test_deconstruct.DeconstructibleChildClass")
        self.assertEqual(args, ("arg",))
        self.assertEqual(kwargs, {"key": "value"})

    def test_deconstruct_child_with_path(self):
        obj = DeconstructibleWithPathChildClass("arg", key="value")
        path, args, kwargs = obj.deconstruct()
        self.assertEqual(
            path,
            "utils_tests.test_deconstruct.DeconstructibleWithPathChildClass",
        )
        self.assertEqual(args, ("arg",))
        self.assertEqual(kwargs, {"key": "value"})

    def test_invalid_path(self):
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

        Tests the deconstruction of a child class with an invalid path.

        Verifies that the :meth:`deconstruct` method correctly extracts and returns the
        class path, positional arguments, and keyword arguments, even when the class
        defines an invalid path. The test checks for the correct class path and
        accurate reconstruction of the object's parameters.

        """
        obj = DeconstructibleInvalidPathChildClass("arg", key="value")
        path, args, kwargs = obj.deconstruct()
        self.assertEqual(
            path,
            "utils_tests.test_deconstruct.DeconstructibleInvalidPathChildClass",
        )
        self.assertEqual(args, ("arg",))
        self.assertEqual(kwargs, {"key": "value"})
