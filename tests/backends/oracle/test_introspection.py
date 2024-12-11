import unittest

from django.db import connection
from django.test import TransactionTestCase, skipUnlessDBFeature

from ..models import Person, Square


@unittest.skipUnless(connection.vendor == "oracle", "Oracle tests")
class DatabaseSequenceTests(TransactionTestCase):
    available_apps = []

    def test_get_sequences(self):
        """


        Tests the retrieval of sequences for the Square model.

        This test case verifies that the correct sequence information is obtained from the database
        for the Square model's table. It checks the following:
        - That exactly one sequence is returned.
        - That the sequence has a valid name.
        - That the sequence is associated with the correct table.
        - That the sequence corresponds to the 'id' column of the table.


        """
        with connection.cursor() as cursor:
            seqs = connection.introspection.get_sequences(
                cursor, Square._meta.db_table, Square._meta.local_fields
            )
            self.assertEqual(len(seqs), 1)
            self.assertIsNotNone(seqs[0]["name"])
            self.assertEqual(seqs[0]["table"], Square._meta.db_table)
            self.assertEqual(seqs[0]["column"], "id")

    def test_get_sequences_manually_created_index(self):
        with connection.cursor() as cursor:
            with connection.schema_editor() as editor:
                editor._drop_identity(Square._meta.db_table, "id")
                seqs = connection.introspection.get_sequences(
                    cursor, Square._meta.db_table, Square._meta.local_fields
                )
                self.assertEqual(
                    seqs, [{"table": Square._meta.db_table, "column": "id"}]
                )
                # Recreate model, because adding identity is impossible.
                editor.delete_model(Square)
                editor.create_model(Square)

    @skipUnlessDBFeature("supports_collation_on_charfield")
    def test_get_table_description_view_default_collation(self):
        """

        Tests the behavior of getting table description for a database view with default collation.

        This test checks that when a view is created without specifying a collation,
        the resulting table description does not include a collation for the view's columns.

        It verifies that the column description contains the expected number of columns
        and that the collation attribute is None, as expected for a view with default collation.

        """
        person_table = connection.introspection.identifier_converter(
            Person._meta.db_table
        )
        first_name_column = connection.ops.quote_name(
            Person._meta.get_field("first_name").column
        )
        person_view = connection.introspection.identifier_converter("TEST_PERSON_VIEW")
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE VIEW {person_view} "
                f"AS SELECT {first_name_column} FROM {person_table}"
            )
            try:
                columns = connection.introspection.get_table_description(
                    cursor, person_view
                )
                self.assertEqual(len(columns), 1)
                self.assertIsNone(columns[0].collation)
            finally:
                cursor.execute(f"DROP VIEW {person_view}")

    @skipUnlessDBFeature("supports_collation_on_charfield")
    def test_get_table_description_materialized_view_non_default_collation(self):
        """
        Test the table description of a materialized view with non-default collation.

        This test checks if the table description of a materialized view correctly reflects the collation of its columns,
        even when the materialized view itself has a non-default collation. The test creates a materialized view with a
        specific collation, retrieves its table description, and verifies that the collation of the columns is correctly
        reported.

        The test covers the following cases:
        - Creation of a materialized view with a non-default collation
        - Retrieval of the table description of the materialized view
        - Verification of the collation of the columns in the table description

        This test requires a database backend that supports collation on char fields.
        """
        person_table = connection.introspection.identifier_converter(
            Person._meta.db_table
        )
        first_name_column = connection.ops.quote_name(
            Person._meta.get_field("first_name").column
        )
        person_mview = connection.introspection.identifier_converter(
            "TEST_PERSON_MVIEW"
        )
        collation = connection.features.test_collations.get("ci")
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE MATERIALIZED VIEW {person_mview} "
                f"DEFAULT COLLATION {collation} "
                f"AS SELECT {first_name_column} FROM {person_table}"
            )
            try:
                columns = connection.introspection.get_table_description(
                    cursor, person_mview
                )
                self.assertEqual(len(columns), 1)
                self.assertIsNotNone(columns[0].collation)
                self.assertNotEqual(columns[0].collation, collation)
            finally:
                cursor.execute(f"DROP MATERIALIZED VIEW {person_mview}")
