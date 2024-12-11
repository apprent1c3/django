# RemovedInDjango60Warning: Remove this entire module.

from django.test import SimpleTestCase
from django.utils.deprecation import RemovedInDjango60Warning
from django.utils.itercompat import is_iterable


class TestIterCompat(SimpleTestCase):
    def test_is_iterable_deprecation(self):
        """
        Tests the deprecation of the is_iterable function from django.utils.itercompat.

        This function checks that using is_iterable raises a RemovedInDjango60Warning, 
        indicating its impending removal in Django 6.0. The recommended replacement 
        is to use isinstance with collections.abc.Iterable for iterable checks.

        The test case verifies the correct warning message is raised when calling 
        the deprecated function with an iterable object, such as a list.

        Returns:
            None

        """
        msg = (
            "django.utils.itercompat.is_iterable() is deprecated. "
            "Use isinstance(..., collections.abc.Iterable) instead."
        )
        with self.assertWarnsMessage(RemovedInDjango60Warning, msg):
            is_iterable([])
