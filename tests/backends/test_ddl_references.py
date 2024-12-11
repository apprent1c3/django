from django.db import connection
from django.db.backends.ddl_references import (
    Columns,
    Expressions,
    ForeignKeyName,
    IndexName,
    Statement,
    Table,
)
from django.db.models import ExpressionList, F
from django.db.models.functions import Upper
from django.db.models.indexes import IndexExpression
from django.db.models.sql import Query
from django.test import SimpleTestCase, TransactionTestCase

from .models import Person


class TableTests(SimpleTestCase):
    def setUp(self):
        self.reference = Table("table", lambda table: table.upper())

    def test_references_table(self):
        self.assertIs(self.reference.references_table("table"), True)
        self.assertIs(self.reference.references_table("other"), False)

    def test_rename_table_references(self):
        """

        Tests the functionality of renaming table references.

        This test case verifies that the rename_table_references method correctly updates the table references.
        It checks that after renaming, the original table reference is removed and the new one is added.
        The test also ensures that the changes are reversible, i.e., renaming back to the original table name
        restores the original reference.

        The test covers the following scenarios:
        - Renaming a table reference from one name to another
        - Verifying that the original reference is no longer present after renaming
        - Verifying that the new reference is present after renaming
        - Reversing the rename operation to ensure the original state is restored

        """
        self.reference.rename_table_references("other", "table")
        self.assertIs(self.reference.references_table("table"), True)
        self.assertIs(self.reference.references_table("other"), False)
        self.reference.rename_table_references("table", "other")
        self.assertIs(self.reference.references_table("table"), False)
        self.assertIs(self.reference.references_table("other"), True)

    def test_repr(self):
        self.assertEqual(repr(self.reference), "<Table 'TABLE'>")

    def test_str(self):
        self.assertEqual(str(self.reference), "TABLE")


class ColumnsTests(TableTests):
    def setUp(self):
        self.reference = Columns(
            "table", ["first_column", "second_column"], lambda column: column.upper()
        )

    def test_references_column(self):
        """
        Checks if a column in a given table is referenced by the object.

        This method determines whether a specific column within a table is used or 
        referred to by the object. It takes two parameters, the table name and the 
        column name, and returns a boolean value indicating whether the column is 
        referenced or not.

        Parameters
        ----------
        table_name : str
            The name of the table to check.
        column_name : str
            The name of the column to check.

        Returns
        -------
        bool
            True if the column is referenced, False otherwise.


        """
        self.assertIs(self.reference.references_column("other", "first_column"), False)
        self.assertIs(self.reference.references_column("table", "third_column"), False)
        self.assertIs(self.reference.references_column("table", "first_column"), True)

    def test_rename_column_references(self):
        self.reference.rename_column_references("other", "first_column", "third_column")
        self.assertIs(self.reference.references_column("table", "first_column"), True)
        self.assertIs(self.reference.references_column("table", "third_column"), False)
        self.assertIs(self.reference.references_column("other", "third_column"), False)
        self.reference.rename_column_references("table", "third_column", "first_column")
        self.assertIs(self.reference.references_column("table", "first_column"), True)
        self.assertIs(self.reference.references_column("table", "third_column"), False)
        self.reference.rename_column_references("table", "first_column", "third_column")
        self.assertIs(self.reference.references_column("table", "first_column"), False)
        self.assertIs(self.reference.references_column("table", "third_column"), True)

    def test_repr(self):
        self.assertEqual(
            repr(self.reference), "<Columns 'FIRST_COLUMN, SECOND_COLUMN'>"
        )

    def test_str(self):
        self.assertEqual(str(self.reference), "FIRST_COLUMN, SECOND_COLUMN")


class IndexNameTests(ColumnsTests):
    def setUp(self):
        def create_index_name(table_name, column_names, suffix):
            return ", ".join(
                "%s_%s_%s" % (table_name, column_name, suffix)
                for column_name in column_names
            )

        self.reference = IndexName(
            "table", ["first_column", "second_column"], "suffix", create_index_name
        )

    def test_repr(self):
        self.assertEqual(
            repr(self.reference),
            "<IndexName 'table_first_column_suffix, table_second_column_suffix'>",
        )

    def test_str(self):
        self.assertEqual(
            str(self.reference), "table_first_column_suffix, table_second_column_suffix"
        )


class ForeignKeyNameTests(IndexNameTests):
    def setUp(self):
        def create_foreign_key_name(table_name, column_names, suffix):
            return ", ".join(
                "%s_%s_%s" % (table_name, column_name, suffix)
                for column_name in column_names
            )

        self.reference = ForeignKeyName(
            "table",
            ["first_column", "second_column"],
            "to_table",
            ["to_first_column", "to_second_column"],
            "%(to_table)s_%(to_column)s_fk",
            create_foreign_key_name,
        )

    def test_references_table(self):
        """
        Overrides the base test for the :meth:`references_table` method to verify its correctness in the context of this class.

        This test checks if the :meth:`references_table` method correctly returns True when the reference is indeed to 'to_table', ensuring proper functionality of the references table mechanism.

        Note: This test relies on the setup provided by the parent class's :meth:`test_references_table` method, which is called at the beginning of this test to establish a common testing framework.
        """
        super().test_references_table()
        self.assertIs(self.reference.references_table("to_table"), True)

    def test_references_column(self):
        super().test_references_column()
        self.assertIs(
            self.reference.references_column("to_table", "second_column"), False
        )
        self.assertIs(
            self.reference.references_column("to_table", "to_second_column"), True
        )

    def test_rename_table_references(self):
        super().test_rename_table_references()
        self.reference.rename_table_references("to_table", "other_to_table")
        self.assertIs(self.reference.references_table("other_to_table"), True)
        self.assertIs(self.reference.references_table("to_table"), False)

    def test_rename_column_references(self):
        """

        Tests the functionality of renaming column references within a reference object.

        This method checks that column references are correctly renamed for a given table.
        It verifies that after renaming, the original column references are no longer valid,
        and the new column references are correctly registered.

        The test covers the following scenarios:
        - Renaming a column reference to a new name within the same table.
        - Checking if the original column reference is still valid after renaming.
        - Verifying if the new column reference is correctly registered after renaming.
        - Attempting to rename a column reference that does not exist.

        It ensures that the `rename_column_references` method works as expected and updates
        the internal references accordingly.

        """
        super().test_rename_column_references()
        self.reference.rename_column_references(
            "to_table", "second_column", "third_column"
        )
        self.assertIs(self.reference.references_column("table", "second_column"), True)
        self.assertIs(
            self.reference.references_column("to_table", "to_second_column"), True
        )
        self.reference.rename_column_references(
            "to_table", "to_first_column", "to_third_column"
        )
        self.assertIs(
            self.reference.references_column("to_table", "to_first_column"), False
        )
        self.assertIs(
            self.reference.references_column("to_table", "to_third_column"), True
        )

    def test_repr(self):
        self.assertEqual(
            repr(self.reference),
            "<ForeignKeyName 'table_first_column_to_table_to_first_column_fk, "
            "table_second_column_to_table_to_first_column_fk'>",
        )

    def test_str(self):
        self.assertEqual(
            str(self.reference),
            "table_first_column_to_table_to_first_column_fk, "
            "table_second_column_to_table_to_first_column_fk",
        )


class MockReference:
    def __init__(
        self, representation, referenced_tables, referenced_columns, referenced_indexes
    ):
        """

        Initializes an object representing a database query or statement.

        :param representation: A string or object that represents the query or statement.
        :param referenced_tables: A list of table names that are referenced in the query.
        :param referenced_columns: A list of column names that are referenced in the query.
        :param referenced_indexes: A list of index names that are referenced in the query.

        This object provides a structured way to store and manipulate information about a database query, 
        including the query representation and the tables, columns, and indexes it references.

        """
        self.representation = representation
        self.referenced_tables = referenced_tables
        self.referenced_columns = referenced_columns
        self.referenced_indexes = referenced_indexes

    def references_table(self, table):
        return table in self.referenced_tables

    def references_column(self, table, column):
        return (table, column) in self.referenced_columns

    def references_index(self, table, index):
        return (table, index) in self.referenced_indexes

    def rename_table_references(self, old_table, new_table):
        if old_table in self.referenced_tables:
            self.referenced_tables.remove(old_table)
            self.referenced_tables.add(new_table)

    def rename_column_references(self, table, old_column, new_column):
        """
        Renames a column reference in the tracked references.

        Updates the internal mapping of referenced columns when a column name has been changed.
        The function takes the table and old column name as input and replaces any existing references
        with the new column name. This ensures that any downstream operations using the referenced
        columns remain valid after a column rename operation.

        Args:
            table (str): The name of the table containing the column to rename.
            old_column (str): The current name of the column to rename.
            new_column (str): The new name for the column.

        Note:
            This function does not modify the actual table or column, only the internal tracking of
            referenced columns.
        """
        column = (table, old_column)
        if column in self.referenced_columns:
            self.referenced_columns.remove(column)
            self.referenced_columns.add((table, new_column))

    def __str__(self):
        return self.representation


class StatementTests(SimpleTestCase):
    def test_references_table(self):
        statement = Statement(
            "", reference=MockReference("", {"table"}, {}, {}), non_reference=""
        )
        self.assertIs(statement.references_table("table"), True)
        self.assertIs(statement.references_table("other"), False)

    def test_references_column(self):
        statement = Statement(
            "",
            reference=MockReference("", {}, {("table", "column")}, {}),
            non_reference="",
        )
        self.assertIs(statement.references_column("table", "column"), True)
        self.assertIs(statement.references_column("other", "column"), False)

    def test_references_index(self):
        statement = Statement(
            "",
            reference=MockReference("", {}, {}, {("table", "index")}),
            non_reference="",
        )
        self.assertIs(statement.references_index("table", "index"), True)
        self.assertIs(statement.references_index("other", "index"), False)

    def test_rename_table_references(self):
        reference = MockReference("", {"table"}, {}, {})
        statement = Statement("", reference=reference, non_reference="")
        statement.rename_table_references("table", "other")
        self.assertEqual(reference.referenced_tables, {"other"})

    def test_rename_column_references(self):
        reference = MockReference("", {}, {("table", "column")}, {})
        statement = Statement("", reference=reference, non_reference="")
        statement.rename_column_references("table", "column", "other")
        self.assertEqual(reference.referenced_columns, {("table", "other")})

    def test_repr(self):
        reference = MockReference("reference", {}, {}, {})
        statement = Statement(
            "%(reference)s - %(non_reference)s",
            reference=reference,
            non_reference="non_reference",
        )
        self.assertEqual(repr(statement), "<Statement 'reference - non_reference'>")

    def test_str(self):
        reference = MockReference("reference", {}, {}, {})
        statement = Statement(
            "%(reference)s - %(non_reference)s",
            reference=reference,
            non_reference="non_reference",
        )
        self.assertEqual(str(statement), "reference - non_reference")


class ExpressionsTests(TransactionTestCase):
    available_apps = []

    def setUp(self):
        compiler = Person.objects.all().query.get_compiler(connection.alias)
        self.editor = connection.schema_editor()
        self.expressions = Expressions(
            table=Person._meta.db_table,
            expressions=ExpressionList(
                IndexExpression(F("first_name")),
                IndexExpression(F("last_name").desc()),
                IndexExpression(Upper("last_name")),
            ).resolve_expression(compiler.query),
            compiler=compiler,
            quote_value=self.editor.quote_value,
        )

    def test_references_table(self):
        """

        Checks if a given table is referenced by the expression.

        This test case verifies that the :meth:`references_table` method of the expression
        correctly identifies whether a specified table is being referenced. It tests both a
        positive case, where the table name matches the one defined in the Person model's
        meta information, and a negative case, where the table name does not match.

        The purpose of this test is to ensure the expression's ability to recognize and
        correctly report references to specific tables, which is essential for various
        database operations and query processing.

        """
        self.assertIs(self.expressions.references_table(Person._meta.db_table), True)
        self.assertIs(self.expressions.references_table("other"), False)

    def test_references_column(self):
        table = Person._meta.db_table
        self.assertIs(self.expressions.references_column(table, "first_name"), True)
        self.assertIs(self.expressions.references_column(table, "last_name"), True)
        self.assertIs(self.expressions.references_column(table, "other"), False)

    def test_rename_table_references(self):
        table = Person._meta.db_table
        self.expressions.rename_table_references(table, "other")
        self.assertIs(self.expressions.references_table(table), False)
        self.assertIs(self.expressions.references_table("other"), True)
        self.assertIn(
            "%s.%s"
            % (
                self.editor.quote_name("other"),
                self.editor.quote_name("first_name"),
            ),
            str(self.expressions),
        )

    def test_rename_table_references_without_alias(self):
        compiler = Query(Person, alias_cols=False).get_compiler(connection=connection)
        table = Person._meta.db_table
        expressions = Expressions(
            table=table,
            expressions=ExpressionList(
                IndexExpression(Upper("last_name")),
                IndexExpression(F("first_name")),
            ).resolve_expression(compiler.query),
            compiler=compiler,
            quote_value=self.editor.quote_value,
        )
        expressions.rename_table_references(table, "other")
        self.assertIs(expressions.references_table(table), False)
        self.assertIs(expressions.references_table("other"), True)
        expected_str = "(UPPER(%s)), %s" % (
            self.editor.quote_name("last_name"),
            self.editor.quote_name("first_name"),
        )
        self.assertEqual(str(expressions), expected_str)

    def test_rename_column_references(self):
        table = Person._meta.db_table
        self.expressions.rename_column_references(table, "first_name", "other")
        self.assertIs(self.expressions.references_column(table, "other"), True)
        self.assertIs(self.expressions.references_column(table, "first_name"), False)
        self.assertIn(
            "%s.%s" % (self.editor.quote_name(table), self.editor.quote_name("other")),
            str(self.expressions),
        )

    def test_str(self):
        table_name = self.editor.quote_name(Person._meta.db_table)
        expected_str = "%s.%s, %s.%s DESC, (UPPER(%s.%s))" % (
            table_name,
            self.editor.quote_name("first_name"),
            table_name,
            self.editor.quote_name("last_name"),
            table_name,
            self.editor.quote_name("last_name"),
        )
        self.assertEqual(str(self.expressions), expected_str)
