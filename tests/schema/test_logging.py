from django.db import connection
from django.test import TestCase


class SchemaLoggerTests(TestCase):
    def test_extra_args(self):
        """

        Test the execution of a SQL query with extra arguments.

        This test ensures that a SQL query with parameters is executed correctly,
        and that the resulting SQL query and parameters are logged as expected.
        It checks the logged SQL query and parameters for both cases where
        the schema editor uses client-side parameter binding and where it doesn't.

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
