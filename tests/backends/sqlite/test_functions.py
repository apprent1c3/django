from django.db.backends.sqlite3._functions import (
    _sqlite_date_trunc,
    _sqlite_datetime_trunc,
    _sqlite_time_trunc,
)
from django.test import SimpleTestCase


class FunctionTests(SimpleTestCase):
    def test_sqlite_date_trunc(self):
        msg = "Unsupported lookup type: 'unknown-lookup'"
        with self.assertRaisesMessage(ValueError, msg):
            _sqlite_date_trunc("unknown-lookup", "2005-08-11", None, None)

    def test_sqlite_datetime_trunc(self):
        msg = "Unsupported lookup type: 'unknown-lookup'"
        with self.assertRaisesMessage(ValueError, msg):
            _sqlite_datetime_trunc("unknown-lookup", "2005-08-11 1:00:00", None, None)

    def test_sqlite_time_trunc(self):
        """
        Tests that the _sqlite_time_trunc function raises a ValueError with the correct error message when an unsupported lookup type is provided.

        The test case verifies that the function correctly handles an unknown lookup type and produces the expected error message, ensuring the function's robustness and error handling capabilities.

        :param None:
        :raises ValueError: When an unsupported lookup type is provided
        :return: None
        """
        msg = "Unsupported lookup type: 'unknown-lookup'"
        with self.assertRaisesMessage(ValueError, msg):
            _sqlite_time_trunc("unknown-lookup", "2005-08-11 1:00:00", None, None)
