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
        """

        Checks if a given table is referenced by the object.

        This method tests the functionality of determining whether a specific table
        is referenced by the current object. It returns True if the table is referenced
        and False otherwise.

        :param None:
        :returns: Boolean values indicating whether the tables are referenced
        :rtype: bool

        """
        self.assertIs(self.reference.references_table("table"), True)
        self.assertIs(self.reference.references_table("other"), False)

    def test_rename_table_references(self):
        """

        Tests the renaming of table references within the data structure.

        This function checks the correct behavior of the rename_table_references method by 
        performing a series of renames and asserting the resulting references are as expected.

        The test covers the following scenarios:
        - Renaming a table reference from 'other' to 'table' and verifying the references.
        - Reversing the rename operation and verifying the references again.

        The goal of this test is to ensure the rename_table_references method correctly updates 
        the internal state of the object to reflect the new table names and maintain consistency.

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

        Checks if a column is referenced by the given table or alias.

        This method determines whether a specific column is referenced by a table or alias.
        It helps to identify if a column is being used or referred to in a particular context.

        The method takes two parameters: the table or alias name and the column name to check.
        It returns True if the column is referenced and False otherwise.

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
        """

        Setup method to initialize ForeignKeyName object.

        This method creates a ForeignKeyName object, specifying the local table, its columns, 
        the referenced table, and its columns. It also defines a custom naming convention 
        for foreign keys by using the create_foreign_key_name function, which generates a 
        string based on the table name, column names, and a given suffix.

        The generated ForeignKeyName object can be used to define foreign key constraints 
        in a database schema, helping to establish relationships between different tables.

        """
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
        super().test_references_table()
        self.assertIs(self.reference.references_table("to_table"), True)

    def test_references_column(self):
        """
        Tests that the references_column method correctly identifies column references.

        This test verifies the functionality of the references_column method, 
        checking that it returns False for columns that are not referenced and 
        True for columns that are referenced. The test case covers scenarios 
        where a column is referenced from another table, ensuring the method 
        accurately handles different column names and table relationships.
        """
        super().test_references_column()
        self.assertIs(
            self.reference.references_column("to_table", "second_column"), False
        )
        self.assertIs(
            self.reference.references_column("to_table", "to_second_column"), True
        )

    def test_rename_table_references(self):
        """
        Tests the rename_table_references method of the class.

        This test case verifies that the rename_table_references method successfully renames table references.
        It checks if the references to the original table name are updated to the new table name,
        and that the original table name is no longer referenced after the rename operation.

        The test also ensures that the correct new table name is being referenced after the rename operation.

        """
        super().test_rename_table_references()
        self.reference.rename_table_references("to_table", "other_to_table")
        self.assertIs(self.reference.references_table("other_to_table"), True)
        self.assertIs(self.reference.references_table("to_table"), False)

    def test_rename_column_references(self):
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

        Initializes a representation object with relevant metadata.

        The object is initialized with a representation, which can be thought of as a high-level description or identifier.
        It also tracks references to various database components, including tables, columns, and indexes.
        These referenced components are stored in separate attributes, making it easy to access and manipulate them.
        The referenced tables, columns, and indexes are expected to be provided as separate collections.

        :param representation: A high-level description or identifier of the object
        :param referenced_tables: A collection of tables that the object references
        :param referenced_columns: A collection of columns that the object references
        :param referenced_indexes: A collection of indexes that the object references

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
        """

        Renew a reference to a table by replacing the old table name with a new one.

        This method updates the set of referenced tables by removing the old table name and adding the new one, if the old table name is present.

        :param old_table: The name of the table to be replaced.
        :param new_table: The name of the table to replace with.

        """
        if old_table in self.referenced_tables:
            self.referenced_tables.remove(old_table)
            self.referenced_tables.add(new_table)

    def rename_column_references(self, table, old_column, new_column):
        column = (table, old_column)
        if column in self.referenced_columns:
            self.referenced_columns.remove(column)
            self.referenced_columns.add((table, new_column))

    def __str__(self):
        return self.representation


class StatementTests(SimpleTestCase):
    def test_references_table(self):
        """

        Checks if a statement references a specific table.

        This method determines whether a given table name is referenced within a statement.
        It returns True if the statement contains a reference to the specified table, and False otherwise.

        :param str table_name: The name of the table to check for references.
        :return: bool indicating whether the statement references the table.

        """
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
        """
        Check if a statement references a specific database index.

        This method verifies whether a given statement contains a reference to a particular database index.
        It takes two parameters, the name of the table and the name of the index, and returns True if the statement references the index and False otherwise.

        The method is useful for identifying potential database queries that may impact performance or for validating the correctness of a statement's references to database indexes.

        Parameters
        ----------
        table : str
            The name of the table to check for index references.
        index : str
            The name of the index to check for references.

        Returns
        -------
        bool
            True if the statement references the specified index, False otherwise.
        """
        statement = Statement(
            "",
            reference=MockReference("", {}, {}, {("table", "index")}),
            non_reference="",
        )
        self.assertIs(statement.references_index("table", "index"), True)
        self.assertIs(statement.references_index("other", "index"), False)

    def test_rename_table_references(self):
        """

        Tests the renaming of table references within a statement.

        This test case verifies that when the :meth:`rename_table_references` method is called on a statement,
        all occurrences of the original table name are correctly replaced with the new table name.

        The test covers the scenario where the statement contains a reference to a table, and checks that
        after renaming, the reference points to the new table name.

        """
        reference = MockReference("", {"table"}, {}, {})
        statement = Statement("", reference=reference, non_reference="")
        statement.rename_table_references("table", "other")
        self.assertEqual(reference.referenced_tables, {"other"})

    def test_rename_column_references(self):
        """
        Tests the renaming of column references within a statement.

        This function verifies that column references are correctly updated when a column is renamed.
        It checks that the referenced columns are properly replaced with the new column name, 
        ensuring data consistency and integrity after the renaming operation.

        :raises: AssertionError if the column references are not correctly renamed
        :return: None
        """
        reference = MockReference("", {}, {("table", "column")}, {})
        statement = Statement("", reference=reference, non_reference="")
        statement.rename_column_references("table", "column", "other")
        self.assertEqual(reference.referenced_columns, {("table", "other")})

    def test_repr(self):
        """
        Test the repr function of the Statement class.

        Verifies that the repr function returns a string with the expected format, 
        containing the Statement's reference and non-reference values.

        This test ensures the class's representation is human-readable and provides 
        useful information about the Statement instance, making it easier to debug 
        and inspect the object's state.
        """
        reference = MockReference("reference", {}, {}, {})
        statement = Statement(
            "%(reference)s - %(non_reference)s",
            reference=reference,
            non_reference="non_reference",
        )
        self.assertEqual(repr(statement), "<Statement 'reference - non_reference'>")

    def test_str(self):
        """

        Tests the string representation of a Statement object.

        Verifies that when a Statement object is converted to a string, it correctly
        replaces placeholders with actual values from its attributes. In this case, the 
        string representation should include the reference and non-reference values.

        The expected output of this function is a string that combines the reference and 
        non-reference values with a hyphen in between, demonstrating that the Statement 
        object's string representation is correctly formatted.

        """
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
        """
        Sets up the necessary components for creating and managing database schema expressions.

        This function initializes a database compiler, schema editor, and a set of expressions for the Person model. The expressions include indexing for the first name, last name in descending order, and the upper case value of the last name. The compiler and editor are used to generate and manipulate these expressions, allowing for the creation and modification of database schema elements.
        """
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
        self.assertIs(self.expressions.references_table(Person._meta.db_table), True)
        self.assertIs(self.expressions.references_table("other"), False)

    def test_references_column(self):
        table = Person._meta.db_table
        self.assertIs(self.expressions.references_column(table, "first_name"), True)
        self.assertIs(self.expressions.references_column(table, "last_name"), True)
        self.assertIs(self.expressions.references_column(table, "other"), False)

    def test_rename_table_references(self):
        """

        Tests the ability to rename table references in expressions.

        This test case verifies that renaming a table reference correctly updates the 
        expression to reference the new table name. It checks that the original table name 
        is no longer referenced and the new table name is correctly used in the expression.

        The test uses a Person table as an example, renaming its reference to 'other' and 
        then asserting that the expression no longer references the original table name 
        and correctly references the new table name, including the quoted column names.

        """
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
        """

        Tests the renaming of table references in a query expression without aliasing columns.

        This test case verifies that the `rename_table_references` method correctly updates 
        the table references in the expression and that the resulting string representation 
        of the expression is as expected.

        The test covers the following scenarios:
        - The original table reference is no longer present in the expression after renaming.
        - The new table reference is present in the expression after renaming.
        - The string representation of the expression contains the expected columns and 
          functions, properly quoted and formatted.

        """
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
        """
        Tests the string representation of an instance's expressions.

        This method verifies that the string conversion of the instance's expressions
        matches an expected format. The expected format includes the fully qualified
        table name, column names, and a specific ordering and case expression.

        The test covers the correct quoting of table and column names, as well as the
        construction of a more complex expression involving the UPPER function.

        """
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
