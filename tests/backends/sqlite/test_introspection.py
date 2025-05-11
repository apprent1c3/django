import unittest

import sqlparse

from django.db import connection
from django.test import TestCase


@unittest.skipUnless(connection.vendor == "sqlite", "SQLite tests")
class IntrospectionTests(TestCase):
    def test_get_primary_key_column(self):
        """

        Test the ability to retrieve the primary key column from a database table,
        regardless of whether the column name is quoted or not.

        """
        testable_column_strings = (
            ("id", "id"),
            ("[id]", "id"),
            ("`id`", "id"),
            ('"id"', "id"),
            ("[id col]", "id col"),
            ("`id col`", "id col"),
            ('"id col"', "id col"),
        )
        with connection.cursor() as cursor:
            for column, expected_string in testable_column_strings:
                sql = "CREATE TABLE test_primary (%s int PRIMARY KEY NOT NULL)" % column
                with self.subTest(column=column):
                    try:
                        cursor.execute(sql)
                        field = connection.introspection.get_primary_key_column(
                            cursor, "test_primary"
                        )
                        self.assertEqual(field, expected_string)
                    finally:
                        cursor.execute("DROP TABLE test_primary")

    def test_get_primary_key_column_pk_constraint(self):
        """
        Tests the retrieval of the primary key column for a given table, verifying that the introspection correctly identifies the column defined with a PRIMARY KEY constraint.
        """
        sql = """
            CREATE TABLE test_primary(
                id INTEGER NOT NULL,
                created DATE,
                PRIMARY KEY(id)
            )
        """
        with connection.cursor() as cursor:
            try:
                cursor.execute(sql)
                field = connection.introspection.get_primary_key_column(
                    cursor,
                    "test_primary",
                )
                self.assertEqual(field, "id")
            finally:
                cursor.execute("DROP TABLE test_primary")


@unittest.skipUnless(connection.vendor == "sqlite", "SQLite tests")
class ParsingTests(TestCase):
    def parse_definition(self, sql, columns):
        """
        Parse a column or constraint definition from SQL.

        This function takes a SQL statement and a set of column names, and returns a parsed representation of the definition.
        It handles the complexities of SQL syntax, allowing for accurate interpretation of column and constraint definitions.
        Used internally for database introspection and schema analysis.
        """
        statement = sqlparse.parse(sql)[0]
        tokens = (token for token in statement.flatten() if not token.is_whitespace)
        with connection.cursor():
            return connection.introspection._parse_column_or_constraint_definition(
                tokens, set(columns)
            )

    def assertConstraint(self, constraint_details, cols, unique=False, check=False):
        self.assertEqual(
            constraint_details,
            {
                "unique": unique,
                "columns": cols,
                "primary_key": False,
                "foreign_key": None,
                "check": check,
                "index": False,
            },
        )

    def test_unique_column(self):
        """
        Tests that the :meth:`parse_definition` method correctly handles SQL definitions of columns with a UNIQUE constraint, verifying that the constraint is identified and that no additional constraints are reported.
        """
        tests = (
            ('"ref" integer UNIQUE,', ["ref"]),
            ("ref integer UNIQUE,", ["ref"]),
            ('"customname" integer UNIQUE,', ["customname"]),
            ("customname integer UNIQUE,", ["customname"]),
        )
        for sql, columns in tests:
            with self.subTest(sql=sql):
                constraint, details, check, _ = self.parse_definition(sql, columns)
                self.assertIsNone(constraint)
                self.assertConstraint(details, columns, unique=True)
                self.assertIsNone(check)

    def test_unique_constraint(self):
        """
        Tests the parser's ability to extract unique constraints from SQL definitions, verifying that the constraint name, columns, and uniqueness are correctly identified.
        """
        tests = (
            ('CONSTRAINT "ref" UNIQUE ("ref"),', "ref", ["ref"]),
            ("CONSTRAINT ref UNIQUE (ref),", "ref", ["ref"]),
            (
                'CONSTRAINT "customname1" UNIQUE ("customname2"),',
                "customname1",
                ["customname2"],
            ),
            (
                "CONSTRAINT customname1 UNIQUE (customname2),",
                "customname1",
                ["customname2"],
            ),
        )
        for sql, constraint_name, columns in tests:
            with self.subTest(sql=sql):
                constraint, details, check, _ = self.parse_definition(sql, columns)
                self.assertEqual(constraint, constraint_name)
                self.assertConstraint(details, columns, unique=True)
                self.assertIsNone(check)

    def test_unique_constraint_multicolumn(self):
        """
        Tests that unique constraints across multiple columns are correctly parsed and validated.

        Verifies that the constraint name and referenced columns are accurately extracted from the SQL definition,
        and that the constraint is properly identified as a unique constraint with no check condition.
        """
        tests = (
            (
                'CONSTRAINT "ref" UNIQUE ("ref", "customname"),',
                "ref",
                ["ref", "customname"],
            ),
            ("CONSTRAINT ref UNIQUE (ref, customname),", "ref", ["ref", "customname"]),
        )
        for sql, constraint_name, columns in tests:
            with self.subTest(sql=sql):
                constraint, details, check, _ = self.parse_definition(sql, columns)
                self.assertEqual(constraint, constraint_name)
                self.assertConstraint(details, columns, unique=True)
                self.assertIsNone(check)

    def test_check_column(self):
        """
        Checks that the parser correctly handles CHECK constraints on columns in SQL definitions.

        Verifies that no error is raised when parsing CHECK constraints with different naming conventions and formats, 
        and that the check constraint and affected columns are correctly identified.
        """
        tests = (
            ('"ref" varchar(255) CHECK ("ref" != \'test\'),', ["ref"]),
            ("ref varchar(255) CHECK (ref != 'test'),", ["ref"]),
            (
                '"customname1" varchar(255) CHECK ("customname2" != \'test\'),',
                ["customname2"],
            ),
            (
                "customname1 varchar(255) CHECK (customname2 != 'test'),",
                ["customname2"],
            ),
        )
        for sql, columns in tests:
            with self.subTest(sql=sql):
                constraint, details, check, _ = self.parse_definition(sql, columns)
                self.assertIsNone(constraint)
                self.assertIsNone(details)
                self.assertConstraint(check, columns, check=True)

    def test_check_constraint(self):
        """
        ..: 
            Tests the parsing of SQL CHECK constraints and verifies that the constraint name and referenced columns are correctly extracted.
        """
        tests = (
            ('CONSTRAINT "ref" CHECK ("ref" != \'test\'),', "ref", ["ref"]),
            ("CONSTRAINT ref CHECK (ref != 'test'),", "ref", ["ref"]),
            (
                'CONSTRAINT "customname1" CHECK ("customname2" != \'test\'),',
                "customname1",
                ["customname2"],
            ),
            (
                "CONSTRAINT customname1 CHECK (customname2 != 'test'),",
                "customname1",
                ["customname2"],
            ),
        )
        for sql, constraint_name, columns in tests:
            with self.subTest(sql=sql):
                constraint, details, check, _ = self.parse_definition(sql, columns)
                self.assertEqual(constraint, constraint_name)
                self.assertIsNone(details)
                self.assertConstraint(check, columns, check=True)

    def test_check_column_with_operators_and_functions(self):
        """
        Tests the parsing of SQL columns with CHECK constraints containing operators and functions.

        Verifies that the parser correctly identifies the column names and checks the constraint definition
        in various scenarios, including range checks and string pattern matching.
        """
        tests = (
            ('"ref" integer CHECK ("ref" BETWEEN 1 AND 10),', ["ref"]),
            ('"ref" varchar(255) CHECK ("ref" LIKE \'test%\'),', ["ref"]),
            (
                '"ref" varchar(255) CHECK (LENGTH(ref) > "max_length"),',
                ["ref", "max_length"],
            ),
        )
        for sql, columns in tests:
            with self.subTest(sql=sql):
                constraint, details, check, _ = self.parse_definition(sql, columns)
                self.assertIsNone(constraint)
                self.assertIsNone(details)
                self.assertConstraint(check, columns, check=True)

    def test_check_and_unique_column(self):
        """
        Tests the parsing of SQL definitions containing both a UNIQUE constraint and a CHECK constraint on a single column to ensure that both constraints are correctly identified and their details are properly extracted.
        """
        tests = (
            ('"ref" varchar(255) CHECK ("ref" != \'test\') UNIQUE,', ["ref"]),
            ("ref varchar(255) UNIQUE CHECK (ref != 'test'),", ["ref"]),
        )
        for sql, columns in tests:
            with self.subTest(sql=sql):
                constraint, details, check, _ = self.parse_definition(sql, columns)
                self.assertIsNone(constraint)
                self.assertConstraint(details, columns, unique=True)
                self.assertConstraint(check, columns, check=True)
