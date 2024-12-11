import unittest

from django.db import connection
from django.test import TestCase


@unittest.skipUnless(connection.vendor == "mysql", "MySQL tests")
class SchemaEditorTests(TestCase):
    def test_quote_value(self):
        """

        Tests the quote_value method of the schema editor to ensure it correctly 
        formats different data types as MySQL-compatible strings.

        The function verifies the output for various input types, including strings, 
        bytes, integers, floats, and boolean values. It checks for proper quoting and 
        escaping of special characters, as well as version-specific formatting for 
        floats and boolean values in MySQL.

        """
        import MySQLdb

        editor = connection.schema_editor()
        tested_values = [
            ("string", "'string'"),
            ("¿Tú hablas inglés?", "'¿Tú hablas inglés?'"),
            (b"bytes", b"'bytes'"),
            (42, "42"),
            (1.754, "1.754e0" if MySQLdb.version_info >= (1, 3, 14) else "1.754"),
            (False, b"0" if MySQLdb.version_info >= (1, 4, 0) else "0"),
        ]
        for value, expected in tested_values:
            with self.subTest(value=value):
                self.assertEqual(editor.quote_value(value), expected)
