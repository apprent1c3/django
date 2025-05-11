from django.db import connection
from django.test import TestCase


class SchemaLoggerTests(TestCase):
    def test_extra_args(self):
        """

        Tests the handling of extra arguments when executing SQL queries using a schema editor.

        Verifies that the SQL query and its parameters are correctly logged, taking into account
        the database backend's parameter binding behavior.

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
