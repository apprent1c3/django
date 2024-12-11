from django.db import connection
from django.test import TestCase


class SchemaLoggerTests(TestCase):
    def test_extra_args(self):
        """
        Test that the schema editor correctly handles extra arguments when executing SQL queries.

            This test case verifies that the schema editor properly logs SQL statements and their corresponding parameters.
            It checks the logged SQL query and parameters to ensure they match the expected output, considering the schema editor's
            parameter binding behavior. The test covers both cases where the schema editor uses client-side parameter binding and
            where it does not. 

            Args:
                None

            Returns:
                None

            Raises:
                AssertionError: If the logged SQL query or parameters do not match the expected output.

        """
        editor = connection.schema_editor(collect_sql=True)
        sql = "SELECT * FROM foo WHERE id in (%s, %s)"
        params = [42, 1337]
        with self.assertLogs("django.db.backends.schema", "DEBUG") as cm:
            editor.execute(sql, params)
        if connection.features.schema_editor_uses_clientside_param_binding:
            sql = "SELECT * FROM foo WHERE id in (42, 1337)"
            params = None
        self.assertEqual(cm.records[0].sql, sql)
        self.assertEqual(cm.records[0].params, params)
        self.assertEqual(cm.records[0].getMessage(), f"{sql}; (params {params})")
