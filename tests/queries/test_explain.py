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
        with self.assertRaisesMessage(ValueError, "Unknown options: TEST, TEST2"):
            Tag.objects.explain(**{"TEST": 1, "TEST2": 1})

    def test_unknown_format(self):
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
        if "TEXT" not in connection.features.supported_explain_formats:
            self.skipTest("This backend does not support TEXT format.")

        base_qs = Tag.objects.order_by()
        qs = base_qs.filter(name="test").union(*[base_qs for _ in range(100)])
        result = qs.explain(format="text")
        self.assertGreaterEqual(result.count("\n"), 100)

    def test_option_sql_injection(self):
        qs = Tag.objects.filter(name="test")
        options = {"SUMMARY true) SELECT 1; --": True}
        msg = "Invalid option name: 'SUMMARY true) SELECT 1; --'"
        with self.assertRaisesMessage(ValueError, msg):
            qs.explain(**options)

    def test_invalid_option_names(self):
        """
        Tests that specifying invalid option names raises a ValueError.

        This test case checks that the function correctly identifies and handles
        option names that contain invalid characters, such as quotation marks,
        backticks, whitespace, semicolons, and non-ASCII characters.

        The test validates the function's error handling by checking that a
        ValueError is raised with a descriptive error message when an invalid option
        name is provided. This ensures that the function behaves as expected and
        provides informative error messages in case of invalid input.
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
        Tests that the MySQL database connection uses the traditional format when 
        explaining a query with the 'text' format.

        This test case checks if the database connection correctly interprets the 'text' 
        format as the traditional format when generating an explanation for a query. It 
        verifies that the resulting SQL query includes the 'FORMAT=TRADITIONAL' keyword.

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
        Tests that explaining query execution on a backend that does not support it raises a NotSupportedError.

        This test case checks that when attempting to explain query execution on a database backend
        without the necessary support, a NotSupportedError exception is correctly raised with a
        meaningful error message, indicating the limitation of the backend in question.
        """
        msg = "This backend does not support explaining query execution."
        with self.assertRaisesMessage(NotSupportedError, msg):
            Tag.objects.filter(name="test").explain()
