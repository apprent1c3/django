import json
import unittest
import xml.etree.ElementTree

from django.db import NotSupportedError, connection, transaction
from django.db.models import Count
from django.test import TestCase, skipIfDBFeature, skipUnlessDBFeature
from django.test.utils import CaptureQueriesContext

from .models import Tag


@skipUnlessDBFeature("supports_explaining_query_execution")
class ExplainTests(TestCase):
    def test_basic(self):
        querysets = [
            Tag.objects.filter(name="test"),
            Tag.objects.filter(name="test").select_related("parent"),
            Tag.objects.filter(name="test").prefetch_related("children"),
            Tag.objects.filter(name="test").annotate(Count("children")),
            Tag.objects.filter(name="test").values_list("name"),
            Tag.objects.order_by().union(Tag.objects.order_by().filter(name="test")),
        ]
        if connection.features.has_select_for_update:
            querysets.append(Tag.objects.select_for_update().filter(name="test"))
        supported_formats = connection.features.supported_explain_formats
        all_formats = (
            (None,)
            + tuple(supported_formats)
            + tuple(f.lower() for f in supported_formats)
        )
        for idx, queryset in enumerate(querysets):
            for format in all_formats:
                with self.subTest(format=format, queryset=idx):
                    with self.assertNumQueries(1) as captured_queries:
                        result = queryset.explain(format=format)
                        self.assertTrue(
                            captured_queries[0]["sql"].startswith(
                                connection.ops.explain_prefix
                            )
                        )
                        self.assertIsInstance(result, str)
                        self.assertTrue(result)
                        if not format:
                            continue
                        if format.lower() == "xml":
                            try:
                                xml.etree.ElementTree.fromstring(result)
                            except xml.etree.ElementTree.ParseError as e:
                                self.fail(
                                    f"QuerySet.explain() result is not valid XML: {e}"
                                )
                        elif format.lower() == "json":
                            try:
                                json.loads(result)
                            except json.JSONDecodeError as e:
                                self.fail(
                                    f"QuerySet.explain() result is not valid JSON: {e}"
                                )

    def test_unknown_options(self):
        """
        Tests that using unknown options when explaining tags raises a ValueError.

        This test verifies that passing unrecognized keyword arguments to the explain
        method of Tag objects results in an informative error message, specifically a
        ValueError listing the unknown options.

        Validates the error handling mechanism to ensure that it correctly identifies
        and reports invalid options, helping to prevent unexpected behavior and aid in
        debugging when using the explain method with unsupported parameters.
        """
        with self.assertRaisesMessage(ValueError, "Unknown options: TEST, TEST2"):
            Tag.objects.explain(**{"TEST": 1, "TEST2": 1})

    def test_unknown_format(self):
        """
        Tests the behavior of the explain method when an unknown format is specified.

        This function verifies that a ValueError is raised when an unrecognized format is
        passed to the explain method. It also checks that the error message includes the
        list of supported formats, if any, or a message indicating that the database does
        not support any formats. This ensures that users receive informative error messages
        when using the explain method with invalid formats.
        """
        msg = "DOES NOT EXIST is not a recognized format."
        if connection.features.supported_explain_formats:
            msg += " Allowed formats: %s" % ", ".join(
                sorted(connection.features.supported_explain_formats)
            )
        else:
            msg += f" {connection.display_name} does not support any formats."
        with self.assertRaisesMessage(ValueError, msg):
            Tag.objects.explain(format="does not exist")

    @unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific")
    def test_postgres_options(self):
        qs = Tag.objects.filter(name="test")
        test_options = [
            {"COSTS": False, "BUFFERS": True, "ANALYZE": True},
            {"costs": False, "buffers": True, "analyze": True},
            {"verbose": True, "timing": True, "analyze": True},
            {"verbose": False, "timing": False, "analyze": True},
            {"summary": True},
            {"settings": True},
            {"analyze": True, "wal": True},
        ]
        if connection.features.is_postgresql_16:
            test_options.append({"generic_plan": True})
        for options in test_options:
            with self.subTest(**options), transaction.atomic():
                with CaptureQueriesContext(connection) as captured_queries:
                    qs.explain(format="text", **options)
                self.assertEqual(len(captured_queries), 1)
                for name, value in options.items():
                    option = "{} {}".format(name.upper(), "true" if value else "false")
                    self.assertIn(option, captured_queries[0]["sql"])

    def test_multi_page_text_explain(self):
        """

        Tests the explain functionality for multi-page text output.

        This test case verifies that the explain method returns a text output with at least 
        100 lines for a query that combines multiple pages of results using union operations. 

        The test first checks if the database backend supports the TEXT format for explain 
        output. If not, the test is skipped. 

        The test then constructs a query that filters a large number of tags and combines 
        them using union operations, and uses the explain method to get the query plan. 

        Finally, it asserts that the explain output has at least 100 lines, indicating that 
        the query plan has been correctly generated for the multi-page text output.

        """
        if "TEXT" not in connection.features.supported_explain_formats:
            self.skipTest("This backend does not support TEXT format.")

        base_qs = Tag.objects.order_by()
        qs = base_qs.filter(name="test").union(*[base_qs for _ in range(100)])
        result = qs.explain(format="text")
        self.assertGreaterEqual(result.count("\n"), 100)

    def test_option_sql_injection(self):
        """
        Tests that an SQL injection attempt is properly prevented by validating option names.

        This test case attempts to pass a malicious option to the explain method of a QuerySet, 
        which would normally be vulnerable to SQL injection attacks. It checks that a ValueError 
        is raised with a message indicating that the provided option name is invalid, 
        preventing the potential SQL injection attack.\"
        """
        qs = Tag.objects.filter(name="test")
        options = {"SUMMARY true) SELECT 1; --": True}
        msg = "Invalid option name: 'SUMMARY true) SELECT 1; --'"
        with self.assertRaisesMessage(ValueError, msg):
            qs.explain(**options)

    def test_invalid_option_names(self):
        """

        Test that supplying invalid option names to the explain method of a queryset raises a ValueError.

        The test checks a variety of invalid option names, including those containing special characters, whitespace, and non-ASCII characters, to ensure that the explain method correctly identifies and rejects them.

        Args:
            None

        Returns:
            None

        Raises:
            ValueError: If an invalid option name is provided to the explain method.

        """
        qs = Tag.objects.filter(name="test")
        tests = [
            'opt"ion',
            "o'ption",
            "op`tion",
            "opti on",
            "option--",
            "optio\tn",
            "o\nption",
            "option;",
            "你 好",
            # [] are used by MSSQL.
            "option[",
            "option]",
        ]
        for invalid_option in tests:
            with self.subTest(invalid_option):
                msg = f"Invalid option name: {invalid_option!r}"
                with self.assertRaisesMessage(ValueError, msg):
                    qs.explain(**{invalid_option: True})

    @unittest.skipUnless(connection.vendor == "mysql", "MySQL specific")
    def test_mysql_text_to_traditional(self):
        # Ensure these cached properties are initialized to prevent queries for
        # the MariaDB or MySQL version during the QuerySet evaluation.
        """
        Tests the MySQL-specific behavior of converting EXPLAIN output to traditional format.

        This test case verifies that when the EXPLAIN format is set to 'text' on a MySQL database,
        the generated SQL query uses the 'FORMAT=TRADITIONAL' syntax.

        It checks that only one query is executed and that the query contains the 'FORMAT=TRADITIONAL' string,
        ensuring that the traditional format is correctly applied to the EXPLAIN output.
        """
        connection.features.supported_explain_formats
        with CaptureQueriesContext(connection) as captured_queries:
            Tag.objects.filter(name="test").explain(format="text")
        self.assertEqual(len(captured_queries), 1)
        self.assertIn("FORMAT=TRADITIONAL", captured_queries[0]["sql"])

    @unittest.skipUnless(
        connection.vendor == "mysql", "MariaDB and MySQL >= 8.0.18 specific."
    )
    def test_mysql_analyze(self):
        """
        Tests the MySQL-specific functionality of the explain method with analyze option.

        This test case checks if the explain method on a QuerySet generates the correct
        SQL query with the ANALYZE option when run on a MySQL or MariaDB database.
        It verifies that the query is generated correctly in two formats: the default
        format and the JSON format.

        The test is skipped unless the database vendor is MySQL. It covers the behavior
        of MySQL and MariaDB versions 8.0.18 and above, where the EXPLAIN ANALYZE
        command is supported.

        The following scenarios are checked:
        - The ANALYZE option is correctly added to the SQL query.
        - The query is correctly formatted in JSON when the format parameter is set to 'JSON'.
        - The correct SQL syntax is used depending on whether the database is MySQL or MariaDB.

        """
        qs = Tag.objects.filter(name="test")
        with CaptureQueriesContext(connection) as captured_queries:
            qs.explain(analyze=True)
        self.assertEqual(len(captured_queries), 1)
        prefix = "ANALYZE " if connection.mysql_is_mariadb else "EXPLAIN ANALYZE "
        self.assertTrue(captured_queries[0]["sql"].startswith(prefix))
        with CaptureQueriesContext(connection) as captured_queries:
            qs.explain(analyze=True, format="JSON")
        self.assertEqual(len(captured_queries), 1)
        if connection.mysql_is_mariadb:
            self.assertIn("FORMAT=JSON", captured_queries[0]["sql"])
        else:
            self.assertNotIn("FORMAT=JSON", captured_queries[0]["sql"])


@skipIfDBFeature("supports_explaining_query_execution")
class ExplainUnsupportedTests(TestCase):
    def test_message(self):
        """
        Tests that the explain method raises a NotSupportedError.

        This test checks that the explain method is not supported by this backend,
        which should result in a NotSupportedError with a descriptive message.

        The test queries the database for objects with name 'test' using the explain method,
        verifying that the expected error is raised with the correct error message.
        """
        msg = "This backend does not support explaining query execution."
        with self.assertRaisesMessage(NotSupportedError, msg):
            Tag.objects.filter(name="test").explain()
