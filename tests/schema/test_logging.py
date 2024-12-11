from django.db import connection
from django.test import TestCase


class SchemaLoggerTests(TestCase):
    def test_extra_args(self):
        """

        Tests the execution of a SQL query with extra arguments using the schema editor.

        This test case verifies that the schema editor correctly handles SQL queries 
        with parameters and logs the executed query with the correct parameter values. 
        It also checks for the correct behavior when using client-side parameter binding.

        The test covers the following scenarios:
        - Execution of a SQL query with parameters
        - Logging of the executed query with parameter values
        - Handling of client-side parameter binding

        It asserts that the logged SQL query and parameters match the expected values.

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
