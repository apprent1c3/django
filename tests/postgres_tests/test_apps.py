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
        """
        Tests that installing an app without any warnings results in at least one database query.

        This test case ensures that when an app is installed without raising any warnings, 
        the installation process executes a certain number of database queries, 
        indicating the successful execution of necessary setup operations.

        The test covers the scenario where the 'django.contrib.postgres' app is installed, 
        and verifies that the installation triggers the expected database interactions.
        """
        get_hstore_oids.cache_clear()
        with CaptureQueriesContext(connection) as captured_queries:
            with override_settings(INSTALLED_APPS=["django.contrib.postgres"]):
                pass
        self.assertGreaterEqual(len(captured_queries), 1)

    def test_register_type_handlers_connection(self):
        """
        Tests the registration of type handlers for PostgreSQL database connections.

        This test ensures that the register_type_handlers function is properly connected 
        to and disconnected from the connection_created signal when the 'django.contrib.postgres' 
        app is installed or uninstalled. The test verifies that the signal receiver is 
        added when the app is installed and removed when it is uninstalled, confirming 
        the correct functionality of the type handler registration mechanism.
        """
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
        """
        Tests the registration of serializers for PostgreSQL range fields in Django migrations.

        This test function checks whether the `MigrationWriter` class is able to serialize various PostgreSQL range field types (e.g. DateRange, DateTimeRange, NumericRange) when the required PostgreSQL support app is installed.

        It first verifies that attempting to serialize these fields without the PostgreSQL app installed raises a `ValueError`.

        Then, it tests that installing the PostgreSQL app allows successful serialization of the range fields, generating the correct import statements and field representations in the serialized output. 

        Finally, it re-verifies that uninstalling the PostgreSQL app reverts the serialization behavior back to raising a `ValueError`.
        """
        tests = (
            (DateRange(empty=True), DateRangeField),
            (DateTimeRange(empty=True), DateRangeField),
            (DateTimeTZRange(None, None, "[]"), DateTimeRangeField),
            (NumericRange(Decimal("1.0"), Decimal("5.0"), "()"), DecimalRangeField),
            (NumericRange(1, 10), IntegerRangeField),
        )

        def assertNotSerializable():
            """
            Asserts that certain test fields are not serializable.

            Checks that an error is raised when attempting to serialize each field in the tests list.
            The error message must include the name of the non-serializable default value's class.

            This test case covers multiple test fields, each with different default values, 
            to verify that the serialization mechanism correctly identifies non-serializable values.

            Raises:
                AssertionError: If a test field is unexpectedly serializable.

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
