from django.db import connection
from django.test import TestCase


class SchemaLoggerTests(TestCase):
    def test_extra_args(self):
        """
        Tests the execution of SQL queries with extra arguments.

        This test case verifies that the database connection properly logs SQL queries 
        and their corresponding parameters. It checks the logged SQL query and parameters 
        when using both server-side and client-side parameter binding.

        The test executes a SQL query with parameters, captures the logged query, and 
        then asserts that the logged SQL and parameters match the expected output. This 
        ensures that the database connection is correctly logging queries and parameters 
        regardless of the parameter binding method used by the database backend.
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
