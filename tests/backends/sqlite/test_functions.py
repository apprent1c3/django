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
        Tests that the _sqlite_time_trunc function correctly raises a ValueError when given an unsupported lookup type for SQLite database operations. 

        The test verifies that a ValueError is raised with the expected error message when the function is called with an 'unknown-lookup' type, ensuring proper error handling and validation of input parameters for time truncation operations.
        """
        msg = "Unsupported lookup type: 'unknown-lookup'"
        with self.assertRaisesMessage(ValueError, msg):
            _sqlite_time_trunc("unknown-lookup", "2005-08-11 1:00:00", None, None)
