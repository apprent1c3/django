from django.test import SimpleTestCase
from django.test.testcases import SerializeMixin


class TestSerializeMixin(SimpleTestCase):
    def test_init_without_lockfile(self):
        """
        Tests the initialization of a subclass without a lockfile.

        Checks that a ValueError is raised when a subclass of SerializeMixin 
        does not define a lockfile attribute, with a message indicating the 
        need for a unique lockfile value in the base class.

        Verifies the correct handling of missing lockfile configuration to 
        prevent potential serialization issues.

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
