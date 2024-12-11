from django.test import SimpleTestCase
from django.test.testcases import SerializeMixin


class TestSerializeMixin(SimpleTestCase):
    def test_init_without_lockfile(self):
        """
        Tests the initialization of a test class without a lockfile.

        This test verifies that a ValueError is raised when a subclass of SerializeMixin 
        does not define a lockfile attribute. The error message indicates that the 
        lockfile attribute is required to be set to a unique value in the base class.

        The test case checks for the correct exception message, ensuring that the error 
        is properly handled and reported when the lockfile attribute is missing.
        """
        msg = (
            "ExampleTests.lockfile isn't set. Set it to a unique value in the "
            "base class."
        )
        with self.assertRaisesMessage(ValueError, msg):

            class ExampleTests(SerializeMixin, SimpleTestCase):
                pass


class TestSerializeMixinUse(SerializeMixin, SimpleTestCase):
    lockfile = __file__

    def test_usage(self):
        # Running this test ensures that the lock/unlock functions have passed.
        pass
