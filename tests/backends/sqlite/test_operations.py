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

        Test the sql_flush function with sequence reset and cascade delete.

        This test checks that the sql_flush function generates correct SQL statements 
        to delete data from the specified tables and reset their sequences. The 
        allow_cascade parameter is set to True, allowing related objects to be 
        deleted. The function is expected to produce DELETE statements for the 
        Person, Tag, and their many-to-many relationship tables, followed by an 
        UPDATE statement to reset the sequences.

        The test verifies the generated SQL statements, checking their order, 
        structure, and content. It ensures that the sequences for all tables are 
        reset correctly.

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
