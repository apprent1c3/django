# RemovedInDjango60Warning: Remove this entire module.

from django.test import SimpleTestCase
from django.utils.deprecation import RemovedInDjango60Warning
from django.utils.itercompat import is_iterable


class TestIterCompat(SimpleTestCase):
    def test_is_iterable_deprecation(self):
        """
        Tests that the deprecated is_iterable function raises a RemovedInDjango60Warning.

        The test checks if calling the is_iterable function with an iterable argument
        triggers the expected deprecation warning, reminding users to switch to the
        recommended isinstance(..., collections.abc.Iterable) approach instead.

        This test ensures the deprecation notice is correctly issued, guiding developers
        to update their code for future compatibility with Django 6.0 and beyond.
        """
        msg = (
            "django.utils.itercompat.is_iterable() is deprecated. "
            "Use isinstance(..., collections.abc.Iterable) instead."
        )
        with self.assertWarnsMessage(RemovedInDjango60Warning, msg):
            is_iterable([])
