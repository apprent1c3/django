import unittest

from django.core.management.color import no_style
from django.db import connection
from django.test import TransactionTestCase

from ..models import Person, Tag


@unittest.skipUnless(connection.vendor == "oracle", "Oracle tests")
class OperationsTests(TransactionTestCase):
    available_apps = ["backends"]

    def test_sequence_name_truncation(self):
        """
        Tests the truncation of sequence names to ensure they do not exceed the maximum allowed length.

        The function checks that a long sequence name is correctly shortened to fit within the permitted character limit,
        while still maintaining a unique and identifiable name. It verifies that the resulting truncated name matches the expected output.
        """
        seq_name = connection.ops._get_no_autofield_sequence_name(
            "schema_authorwithevenlongee869"
        )
        self.assertEqual(seq_name, "SCHEMA_AUTHORWITHEVENLOB0B8_SQ")

    def test_bulk_batch_size(self):
        # Oracle restricts the number of parameters in a query.
        """
        Tests the calculation of the bulk batch size for a given list of objects, considering the number of fields to be updated and the database's maximum query parameters limit. The test covers scenarios with no fields, a single field, and multiple fields, verifying that the batch size is correctly determined based on the available database capacity.
        """
        objects = range(2**16)
        self.assertEqual(connection.ops.bulk_batch_size([], objects), len(objects))
        # Each field is a parameter for each object.
        self.assertEqual(
            connection.ops.bulk_batch_size(["id"], objects),
            connection.features.max_query_params,
        )
        self.assertEqual(
            connection.ops.bulk_batch_size(["id", "other"], objects),
            connection.features.max_query_params // 2,
        )

    def test_sql_flush(self):
        """
        Tests the generation of SQL statements to flush data from the database tables.

        This test case verifies that the generated SQL statements correctly disable constraints,
        truncate the specified tables, and then re-enable the constraints. The tables being tested
        are Person and Tag, and the test checks for the correct order and content of the generated
        SQL statements.

        The expected output includes disabling a constraint on the Tag table, truncating both the
        Person and Tag tables, and then re-enabling the constraint on the Tag table.

        """
        statements = connection.ops.sql_flush(
            no_style(),
            [Person._meta.db_table, Tag._meta.db_table],
        )
        # The tables and constraints are processed in an unordered set.
        self.assertEqual(
            statements[0],
            'ALTER TABLE "BACKENDS_TAG" DISABLE CONSTRAINT '
            '"BACKENDS__CONTENT_T_FD9D7A85_F" KEEP INDEX;',
        )
        self.assertEqual(
            sorted(statements[1:-1]),
            [
                'TRUNCATE TABLE "BACKENDS_PERSON";',
                'TRUNCATE TABLE "BACKENDS_TAG";',
            ],
        )
        self.assertEqual(
            statements[-1],
            'ALTER TABLE "BACKENDS_TAG" ENABLE CONSTRAINT '
            '"BACKENDS__CONTENT_T_FD9D7A85_F";',
        )

    def test_sql_flush_allow_cascade(self):
        """

        Tests that SQL flush commands are generated correctly when allow_cascade is True.

        This test case verifies that the sql_flush function returns the correct sequence of SQL statements 
        to flush the database tables while allowing cascading operations. It checks that the constraints 
        are temporarily disabled, the relevant tables are truncated, and the constraints are then re-enabled.

        The test covers the following scenarios:

        * Disabling constraints on tables with foreign key relationships
        * Truncating tables in the correct order
        * Re-enabling constraints after truncation

        By verifying the generated SQL statements, this test ensures that the database is properly reset 
        while respecting the relationships between tables.

        """
        statements = connection.ops.sql_flush(
            no_style(),
            [Person._meta.db_table, Tag._meta.db_table],
            allow_cascade=True,
        )
        # The tables and constraints are processed in an unordered set.
        self.assertEqual(
            statements[0],
            'ALTER TABLE "BACKENDS_VERYLONGMODELNAME540F" DISABLE CONSTRAINT '
            '"BACKENDS__PERSON_ID_1DD5E829_F" KEEP INDEX;',
        )
        self.assertEqual(
            sorted(statements[1:-1]),
            [
                'TRUNCATE TABLE "BACKENDS_PERSON";',
                'TRUNCATE TABLE "BACKENDS_TAG";',
                'TRUNCATE TABLE "BACKENDS_VERYLONGMODELNAME540F";',
            ],
        )
        self.assertEqual(
            statements[-1],
            'ALTER TABLE "BACKENDS_VERYLONGMODELNAME540F" ENABLE CONSTRAINT '
            '"BACKENDS__PERSON_ID_1DD5E829_F";',
        )

    def test_sql_flush_sequences(self):
        statements = connection.ops.sql_flush(
            no_style(),
            [Person._meta.db_table, Tag._meta.db_table],
            reset_sequences=True,
        )
        # The tables and constraints are processed in an unordered set.
        self.assertEqual(
            statements[0],
            'ALTER TABLE "BACKENDS_TAG" DISABLE CONSTRAINT '
            '"BACKENDS__CONTENT_T_FD9D7A85_F" KEEP INDEX;',
        )
        self.assertEqual(
            sorted(statements[1:3]),
            [
                'TRUNCATE TABLE "BACKENDS_PERSON";',
                'TRUNCATE TABLE "BACKENDS_TAG";',
            ],
        )
        self.assertEqual(
            statements[3],
            'ALTER TABLE "BACKENDS_TAG" ENABLE CONSTRAINT '
            '"BACKENDS__CONTENT_T_FD9D7A85_F";',
        )
        # Sequences.
        self.assertEqual(len(statements[4:]), 2)
        self.assertIn("BACKENDS_PERSON_SQ", statements[4])
        self.assertIn("BACKENDS_TAG_SQ", statements[5])

    def test_sql_flush_sequences_allow_cascade(self):
        """
        Tests that sql_flush generates the correct SQL statements to flush sequences, allowing cascade operations.

        This test case verifies that the sql_flush function correctly generates SQL statements to disable 
        constraints, truncate tables, re-enable constraints, and reset sequences. The test checks the 
        generated statements for correctness, ensuring that they match the expected SQL commands.

        The function is tested with a specific set of tables, including those with long names and those 
        with foreign key relationships. The test also checks that the sql_flush function correctly 
        handles the allow_cascade parameter, allowing cascade operations on related tables.

        The test includes assertions to verify the correctness of the generated SQL statements, 
        including the ordering and contents of the statements. Overall, this test case ensures that 
        sql_flush generates the correct SQL statements to flush sequences and perform other necessary 
        database operations, while also handling complex table relationships and long table names.
        """
        statements = connection.ops.sql_flush(
            no_style(),
            [Person._meta.db_table, Tag._meta.db_table],
            reset_sequences=True,
            allow_cascade=True,
        )
        # The tables and constraints are processed in an unordered set.
        self.assertEqual(
            statements[0],
            'ALTER TABLE "BACKENDS_VERYLONGMODELNAME540F" DISABLE CONSTRAINT '
            '"BACKENDS__PERSON_ID_1DD5E829_F" KEEP INDEX;',
        )
        self.assertEqual(
            sorted(statements[1:4]),
            [
                'TRUNCATE TABLE "BACKENDS_PERSON";',
                'TRUNCATE TABLE "BACKENDS_TAG";',
                'TRUNCATE TABLE "BACKENDS_VERYLONGMODELNAME540F";',
            ],
        )
        self.assertEqual(
            statements[4],
            'ALTER TABLE "BACKENDS_VERYLONGMODELNAME540F" ENABLE CONSTRAINT '
            '"BACKENDS__PERSON_ID_1DD5E829_F";',
        )
        # Sequences.
        self.assertEqual(len(statements[5:]), 3)
        self.assertIn("BACKENDS_PERSON_SQ", statements[5])
        self.assertIn("BACKENDS_VERYLONGMODELN7BE2_SQ", statements[6])
        self.assertIn("BACKENDS_TAG_SQ", statements[7])
