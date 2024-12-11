import unittest
from decimal import Decimal

from django.db import connection
from django.db.backends.signals import connection_created
from django.db.migrations.writer import MigrationWriter
from django.test import TestCase
from django.test.utils import CaptureQueriesContext, modify_settings, override_settings

try:
    from django.contrib.postgres.fields import (
        DateRangeField,
        DateTimeRangeField,
        DecimalRangeField,
        IntegerRangeField,
    )
    from django.contrib.postgres.signals import get_hstore_oids
    from django.db.backends.postgresql.psycopg_any import (
        DateRange,
        DateTimeRange,
        DateTimeTZRange,
        NumericRange,
        is_psycopg3,
    )
except ImportError:
    pass


@unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific tests")
class PostgresConfigTests(TestCase):
    def test_install_app_no_warning(self):
        # Clear cache to force queries when (re)initializing the
        # "django.contrib.postgres" app.
        get_hstore_oids.cache_clear()
        with CaptureQueriesContext(connection) as captured_queries:
            with override_settings(INSTALLED_APPS=["django.contrib.postgres"]):
                pass
        self.assertGreaterEqual(len(captured_queries), 1)

    def test_register_type_handlers_connection(self):
        from django.contrib.postgres.signals import register_type_handlers

        self.assertNotIn(
            register_type_handlers, connection_created._live_receivers(None)[0]
        )
        with modify_settings(INSTALLED_APPS={"append": "django.contrib.postgres"}):
            self.assertIn(
                register_type_handlers, connection_created._live_receivers(None)[0]
            )
        self.assertNotIn(
            register_type_handlers, connection_created._live_receivers(None)[0]
        )

    def test_register_serializer_for_migrations(self):
        tests = (
            (DateRange(empty=True), DateRangeField),
            (DateTimeRange(empty=True), DateRangeField),
            (DateTimeTZRange(None, None, "[]"), DateTimeRangeField),
            (NumericRange(Decimal("1.0"), Decimal("5.0"), "()"), DecimalRangeField),
            (NumericRange(1, 10), IntegerRangeField),
        )

        def assertNotSerializable():
            """
            Tests that certain objects are not serializable.

            This function iterates over a set of test cases and attempts to serialize each one using the MigrationWriter.
            It checks that a ValueError is raised for each non-serializable object, with a message indicating the specific object type that cannot be serialized.

            The test cases are expected to be provided in the 'tests' variable, where each case is a tuple containing a default value and a function that generates a test field based on the default value.

            The function uses sub-tests to provide more detailed information about the test results, making it easier to identify which specific test cases failed or passed.
            """
            for default, test_field in tests:
                with self.subTest(default=default):
                    field = test_field(default=default)
                    with self.assertRaisesMessage(
                        ValueError, "Cannot serialize: %s" % default.__class__.__name__
                    ):
                        MigrationWriter.serialize(field)

        assertNotSerializable()
        import_name = "psycopg.types.range" if is_psycopg3 else "psycopg2.extras"
        with self.modify_settings(INSTALLED_APPS={"append": "django.contrib.postgres"}):
            for default, test_field in tests:
                with self.subTest(default=default):
                    field = test_field(default=default)
                    serialized_field, imports = MigrationWriter.serialize(field)
                    self.assertEqual(
                        imports,
                        {
                            "import django.contrib.postgres.fields.ranges",
                            f"import {import_name}",
                        },
                    )
                    self.assertIn(
                        f"{field.__module__}.{field.__class__.__name__}"
                        f"(default={import_name}.{default!r})",
                        serialized_field,
                    )
        assertNotSerializable()
