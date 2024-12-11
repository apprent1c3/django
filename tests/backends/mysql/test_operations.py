import unittest

from django.core.management.color import no_style
from django.db import connection
from django.test import SimpleTestCase

from ..models import Person, Tag


@unittest.skipUnless(connection.vendor == "mysql", "MySQL tests.")
class MySQLOperationsTests(SimpleTestCase):
    def test_sql_flush(self):
        # allow_cascade doesn't change statements on MySQL.
        """
        Tests the SQL flush command generation for the database.

        This test case checks the sql_flush method of the database connection's operations,
        verifying it produces the correct SQL commands to clear data from the Person and Tag tables.
        The test covers both cases where foreign key constraints are allowed to cascade and where they are not.

        It ensures the generated SQL commands include disabling foreign key checks, deleting data from both tables, and re-enabling foreign key checks afterwards, regardless of the cascade setting.

        The expected output consists of a sequence of SQL commands: 
        - Disabling foreign key checks,
        - Deleting data from the Person table,
        - Deleting data from the Tag table, and
        - Re-enabling foreign key checks.

        The test utilizes a subtest for each allow_cascade setting to ensure both scenarios are thoroughly validated.
        """
        for allow_cascade in [False, True]:
            with self.subTest(allow_cascade=allow_cascade):
                self.assertEqual(
                    connection.ops.sql_flush(
                        no_style(),
                        [Person._meta.db_table, Tag._meta.db_table],
                        allow_cascade=allow_cascade,
                    ),
                    [
                        "SET FOREIGN_KEY_CHECKS = 0;",
                        "DELETE FROM `backends_person`;",
                        "DELETE FROM `backends_tag`;",
                        "SET FOREIGN_KEY_CHECKS = 1;",
                    ],
                )

    def test_sql_flush_sequences(self):
        # allow_cascade doesn't change statements on MySQL.
        for allow_cascade in [False, True]:
            with self.subTest(allow_cascade=allow_cascade):
                self.assertEqual(
                    connection.ops.sql_flush(
                        no_style(),
                        [Person._meta.db_table, Tag._meta.db_table],
                        reset_sequences=True,
                        allow_cascade=allow_cascade,
                    ),
                    [
                        "SET FOREIGN_KEY_CHECKS = 0;",
                        "TRUNCATE `backends_person`;",
                        "TRUNCATE `backends_tag`;",
                        "SET FOREIGN_KEY_CHECKS = 1;",
                    ],
                )
