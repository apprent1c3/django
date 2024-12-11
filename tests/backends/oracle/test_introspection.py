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

        Verifies that the sequence associated with the Square model's primary key
        is correctly identified and its properties match the expected values.

        The test checks the following:
            - A single sequence is returned for the Square model.
            - The sequence has a non-null name.
            - The sequence is associated with the correct database table.
            - The sequence corresponds to the 'id' column of the Square model.

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
        Tests that the default collation is None for a view with a single character field.

        This test case creates a temporary view based on a character field from the Person model, 
        then uses the database connection's introspection capabilities to retrieve the table description 
        of the view. It verifies that the collation for the character field in the view is None, 
        as expected when no explicit collation is specified.

        The test is only executed if the database backend supports collation on character fields.

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
