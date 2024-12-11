"""Tests for django.db.backends.utils"""

from decimal import Decimal, Rounded

from django.db import NotSupportedError, connection
from django.db.backends.utils import (
    format_number,
    split_identifier,
    split_tzname_delta,
    truncate_name,
)
from django.test import (
    SimpleTestCase,
    TransactionTestCase,
    skipIfDBFeature,
    skipUnlessDBFeature,
)


class TestUtils(SimpleTestCase):
    def test_truncate_name(self):
        """

        Truncates a table name to a specified length while preserving its schema and uniqueness.

        The function takes a table name, a maximum length, and an optional prefix length.
        If the table name exceeds the maximum length, it is truncated and a unique hash is appended.
        If a prefix length is provided, the table name is truncated to that length before appending the hash.
        If the table name is already within the maximum length, it is returned unchanged.
        This function handles table names with schemas and preserves the schema during truncation.

        Args:
            table_name (str): The name of the table to truncate.
            max_length (int, optional): The maximum length of the truncated table name. Defaults to None.
            prefix_length (int, optional): The length to truncate the table name to before appending the hash. Defaults to None.

        Returns:
            str: The truncated table name.

        """
        self.assertEqual(truncate_name("some_table", 10), "some_table")
        self.assertEqual(truncate_name("some_long_table", 10), "some_la38a")
        self.assertEqual(truncate_name("some_long_table", 10, 3), "some_loa38")
        self.assertEqual(truncate_name("some_long_table"), "some_long_table")
        # "user"."table" syntax
        self.assertEqual(
            truncate_name('username"."some_table', 10), 'username"."some_table'
        )
        self.assertEqual(
            truncate_name('username"."some_long_table', 10), 'username"."some_la38a'
        )
        self.assertEqual(
            truncate_name('username"."some_long_table', 10, 3), 'username"."some_loa38'
        )

    def test_split_identifier(self):
        self.assertEqual(split_identifier("some_table"), ("", "some_table"))
        self.assertEqual(split_identifier('"some_table"'), ("", "some_table"))
        self.assertEqual(
            split_identifier('namespace"."some_table'), ("namespace", "some_table")
        )
        self.assertEqual(
            split_identifier('"namespace"."some_table"'), ("namespace", "some_table")
        )

    def test_format_number(self):
        def equal(value, max_d, places, result):
            self.assertEqual(format_number(Decimal(value), max_d, places), result)

        equal("0", 12, 3, "0.000")
        equal("0", 12, 8, "0.00000000")
        equal("1", 12, 9, "1.000000000")
        equal("0.00000000", 12, 8, "0.00000000")
        equal("0.000000004", 12, 8, "0.00000000")
        equal("0.000000008", 12, 8, "0.00000001")
        equal("0.000000000000000000999", 10, 8, "0.00000000")
        equal("0.1234567890", 12, 10, "0.1234567890")
        equal("0.1234567890", 12, 9, "0.123456789")
        equal("0.1234567890", 12, 8, "0.12345679")
        equal("0.1234567890", 12, 5, "0.12346")
        equal("0.1234567890", 12, 3, "0.123")
        equal("0.1234567890", 12, 1, "0.1")
        equal("0.1234567890", 12, 0, "0")
        equal("0.1234567890", None, 0, "0")
        equal("1234567890.1234567890", None, 0, "1234567890")
        equal("1234567890.1234567890", None, 2, "1234567890.12")
        equal("0.1234", 5, None, "0.1234")
        equal("123.12", 5, None, "123.12")

        with self.assertRaises(Rounded):
            equal("0.1234567890", 5, None, "0.12346")
        with self.assertRaises(Rounded):
            equal("1234567890.1234", 5, None, "1234600000")

    def test_split_tzname_delta(self):
        """
        Tests the split_tzname_delta function to ensure it correctly separates time zone names from their UTC offset components.

        The function is expected to extract the base time zone name, the sign of the offset (if any), and the offset value (if any) from a given time zone string.

        Examples of time zone strings include 'Asia/Ust+Nera', 'America/Coral_Harbour+02:30', and 'UTC-04:43'. The function should handle various time zone formats and return a tuple containing the base time zone name, the offset sign, and the offset value.

        The test cases cover a range of scenarios, including time zones with and without UTC offsets, and time zones with different offset formats.
        """
        tests = [
            ("Asia/Ust+Nera", ("Asia/Ust+Nera", None, None)),
            ("Asia/Ust-Nera", ("Asia/Ust-Nera", None, None)),
            ("Asia/Ust+Nera-02:00", ("Asia/Ust+Nera", "-", "02:00")),
            ("Asia/Ust-Nera+05:00", ("Asia/Ust-Nera", "+", "05:00")),
            ("America/Coral_Harbour-01:00", ("America/Coral_Harbour", "-", "01:00")),
            ("America/Coral_Harbour+02:30", ("America/Coral_Harbour", "+", "02:30")),
            ("UTC+15:00", ("UTC", "+", "15:00")),
            ("UTC-04:43", ("UTC", "-", "04:43")),
            ("UTC", ("UTC", None, None)),
            ("UTC+1", ("UTC+1", None, None)),
        ]
        for tzname, expected in tests:
            with self.subTest(tzname=tzname):
                self.assertEqual(split_tzname_delta(tzname), expected)


class CursorWrapperTests(TransactionTestCase):
    available_apps = []

    def _test_procedure(self, procedure_sql, params, param_types, kparams=None):
        """
        Tests a database procedure by executing it, calling it with provided parameters, and then removing it.

        :param procedure_sql: The SQL statement used to create the procedure.
        :param params: A list of parameters to pass to the procedure when it's called.
        :param param_types: A list of data types corresponding to the parameters, used when removing the procedure.
        :param kparams: Optional keyword parameters to pass to the procedure when it's called.
        :note: This function assumes a connection to the database has already been established.

        """
        with connection.cursor() as cursor:
            cursor.execute(procedure_sql)
        # Use a new cursor because in MySQL a procedure can't be used in the
        # same cursor in which it was created.
        with connection.cursor() as cursor:
            cursor.callproc("test_procedure", params, kparams)
        with connection.schema_editor() as editor:
            editor.remove_procedure("test_procedure", param_types)

    @skipUnlessDBFeature("create_test_procedure_without_params_sql")
    def test_callproc_without_params(self):
        self._test_procedure(
            connection.features.create_test_procedure_without_params_sql, [], []
        )

    @skipUnlessDBFeature("create_test_procedure_with_int_param_sql")
    def test_callproc_with_int_params(self):
        self._test_procedure(
            connection.features.create_test_procedure_with_int_param_sql,
            [1],
            ["INTEGER"],
        )

    @skipUnlessDBFeature(
        "create_test_procedure_with_int_param_sql", "supports_callproc_kwargs"
    )
    def test_callproc_kparams(self):
        self._test_procedure(
            connection.features.create_test_procedure_with_int_param_sql,
            [],
            ["INTEGER"],
            {"P_I": 1},
        )

    @skipIfDBFeature("supports_callproc_kwargs")
    def test_unsupported_callproc_kparams_raises_error(self):
        """
        Tests that calling a stored procedure with keyword parameters raises a NotSupportedError.

        This test verifies that the database backend correctly handles the case where keyword
        parameters are passed to the callproc method, which is not supported by all database
        backends. The expected error message is checked to ensure it matches the expected
        behavior.

        :raises: NotSupportedError if the database backend does not support keyword parameters
            for stored procedures.
        """
        msg = (
            "Keyword parameters for callproc are not supported on this database "
            "backend."
        )
        with self.assertRaisesMessage(NotSupportedError, msg):
            with connection.cursor() as cursor:
                cursor.callproc("test_procedure", [], {"P_I": 1})
