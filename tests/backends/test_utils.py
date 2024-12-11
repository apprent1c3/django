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

        Truncates a database table name to a specified length.

        The truncation process aims to preserve the most meaningful part of the name, 
        typically the prefix. If the input name is shorter than or equal to the 
        specified length, it is returned unchanged.

        When a length and an optional prefix length are provided, the function 
        applies a hashing algorithm to the truncated part of the name, replacing 
        it with a shorter hash value and prefix. This approach helps to avoid 
        name collisions while preserving some of the original name's context.

        The function also handles names that include a schema or username prefix, 
        ensuring the truncation process does not interfere with these prefixes.

        :param name: The database table name to be truncated
        :param length: The maximum allowed length for the truncated name
        :param prefix_length: The length of the prefix to preserve during truncation (optional)
        :rtype: str

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
        """

        Split a fully qualified identifier into its namespace and table name components.

        This function takes an identifier string as input and returns a tuple containing
        the namespace and table name. If the identifier does not contain a namespace,
        the namespace is returned as an empty string. The function supports identifiers
        that are optionally quoted with double quotes.

        Returns:
            tuple: A tuple containing the namespace and table name.

        """
        self.assertEqual(split_identifier("some_table"), ("", "some_table"))
        self.assertEqual(split_identifier('"some_table"'), ("", "some_table"))
        self.assertEqual(
            split_identifier('namespace"."some_table'), ("namespace", "some_table")
        )
        self.assertEqual(
            split_identifier('"namespace"."some_table"'), ("namespace", "some_table")
        )

    def test_format_number(self):
        """
        Tests the format_number function to ensure it correctly formats decimal numbers.

        The format_number function is evaluated with various inputs, including different decimal values, maximum digits, and decimal places.
        The test cases cover a range of scenarios, such as rounding to a specified number of decimal places, handling numbers with many decimal places, and formatting numbers with varying maximum digits.
        The test also checks that the function raises a Rounded exception when the formatting operation would result in a loss of precision due to a maximum digits constraint.
        The goal of these tests is to ensure that the format_number function behaves as expected and produces the correct formatted output for different input values and formatting parameters.
        """
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

        Execute and test a stored procedure on a database.

        This method executes a given SQL procedure, calls the procedure with provided parameters,
        and then removes the procedure from the database schema.

        :param procedure_sql: The SQL string defining the procedure to be tested.
        :param params: A list of parameter values to be passed to the procedure.
        :param param_types: A list of parameter types corresponding to the values in params.
        :param kparams: Optional keyword parameters to be passed to the procedure.

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
        Tests if calling a stored procedure with keyword parameters raises an error.

        This test checks the behavior of the database backend when using keyword parameters with the callproc method.
        It verifies that a NotSupportedError is raised with a specific error message when keyword parameters are used,
        as they are not supported on this particular database backend. 
        """
        msg = (
            "Keyword parameters for callproc are not supported on this database "
            "backend."
        )
        with self.assertRaisesMessage(NotSupportedError, msg):
            with connection.cursor() as cursor:
                cursor.callproc("test_procedure", [], {"P_I": 1})
