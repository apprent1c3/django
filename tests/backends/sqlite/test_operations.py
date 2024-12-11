import unittest

from django.core.management.color import no_style
from django.db import connection
from django.test import TestCase

from ..models import Person, Tag


@unittest.skipUnless(connection.vendor == "sqlite", "SQLite tests.")
class SQLiteOperationsTests(TestCase):
    def test_sql_flush(self):
        self.assertEqual(
            connection.ops.sql_flush(
                no_style(),
                [Person._meta.db_table, Tag._meta.db_table],
            ),
            [
                'DELETE FROM "backends_person";',
                'DELETE FROM "backends_tag";',
            ],
        )

    def test_sql_flush_allow_cascade(self):
        """

        Tests the sql_flush function to ensure it produces the correct SQL commands 
        to flush data from the database tables while allowing cascade deletion.

        This test case specifically checks that the produced SQL commands correctly 
        delete data from the 'Person', 'Tag', and the many-to-many relationship table 
        in the correct order when allow_cascade is set to True.

        """
        statements = connection.ops.sql_flush(
            no_style(),
            [Person._meta.db_table, Tag._meta.db_table],
            allow_cascade=True,
        )
        self.assertEqual(
            # The tables are processed in an unordered set.
            sorted(statements),
            [
                'DELETE FROM "backends_person";',
                'DELETE FROM "backends_tag";',
                'DELETE FROM "backends_verylongmodelnamezzzzzzzzzzzzzzzzzzzzzz'
                "zzzzzzzzzzzzzzzzzzzz_m2m_also_quite_long_zzzzzzzzzzzzzzzzzzzz"
                'zzzzzzzzzzzzzzzzzzzzzzz";',
            ],
        )

    def test_sql_flush_sequences(self):
        self.assertEqual(
            connection.ops.sql_flush(
                no_style(),
                [Person._meta.db_table, Tag._meta.db_table],
                reset_sequences=True,
            ),
            [
                'DELETE FROM "backends_person";',
                'DELETE FROM "backends_tag";',
                'UPDATE "sqlite_sequence" SET "seq" = 0 WHERE "name" IN '
                "('backends_person', 'backends_tag');",
            ],
        )

    def test_sql_flush_sequences_allow_cascade(self):
        """
        Tests the generation of SQL statements to flush sequences, allowing cascading deletes.

        This test case verifies that the correct SQL statements are produced to delete data from the specified tables and reset sequences. It checks that the generated statements include DELETE commands for the relevant tables and an UPDATE command to reset the sequence values. The test also ensures that the UPDATE command correctly references the names of the tables involved.

        The test case covers the scenario where cascading deletes are allowed, and it verifies that the generated SQL statements accurately reflect this configuration. The test results provide assurance that the database operations will be correctly executed to maintain data consistency and integrity.
        """
        statements = connection.ops.sql_flush(
            no_style(),
            [Person._meta.db_table, Tag._meta.db_table],
            reset_sequences=True,
            allow_cascade=True,
        )
        self.assertEqual(
            # The tables are processed in an unordered set.
            sorted(statements[:-1]),
            [
                'DELETE FROM "backends_person";',
                'DELETE FROM "backends_tag";',
                'DELETE FROM "backends_verylongmodelnamezzzzzzzzzzzzzzzzzzzzzz'
                "zzzzzzzzzzzzzzzzzzzz_m2m_also_quite_long_zzzzzzzzzzzzzzzzzzzz"
                'zzzzzzzzzzzzzzzzzzzzzzz";',
            ],
        )
        self.assertIs(
            statements[-1].startswith(
                'UPDATE "sqlite_sequence" SET "seq" = 0 WHERE "name" IN ('
            ),
            True,
        )
        self.assertIn("'backends_person'", statements[-1])
        self.assertIn("'backends_tag'", statements[-1])
        self.assertIn(
            "'backends_verylongmodelnamezzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"
            "zzzz_m2m_also_quite_long_zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"
            "zzz'",
            statements[-1],
        )
