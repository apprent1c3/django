"""
Helpers to manipulate deferred DDL statements that might need to be adjusted or
discarded within when executing a migration.
"""

from copy import deepcopy


class Reference:
    """Base class that defines the reference interface."""

    def references_table(self, table):
        """
        Return whether or not this instance references the specified table.
        """
        return False

    def references_column(self, table, column):
        """
        Return whether or not this instance references the specified column.
        """
        return False

    def references_index(self, table, index):
        """
        Return whether or not this instance references the specified index.
        """
        return False

    def rename_table_references(self, old_table, new_table):
        """
        Rename all references to the old_name to the new_table.
        """
        pass

    def rename_column_references(self, table, old_column, new_column):
        """
        Rename all references to the old_column to the new_column.
        """
        pass

    def __repr__(self):
        return "<%s %r>" % (self.__class__.__name__, str(self))

    def __str__(self):
        raise NotImplementedError(
            "Subclasses must define how they should be converted to string."
        )


class Table(Reference):
    """Hold a reference to a table."""

    def __init__(self, table, quote_name):
        self.table = table
        self.quote_name = quote_name

    def references_table(self, table):
        return self.table == table

    def references_index(self, table, index):
        return self.references_table(table) and str(self) == index

    def rename_table_references(self, old_table, new_table):
        """

        Renames references to a table in the current object.

        If the current object's table matches the old table name, it is updated to use the new table name instead.

        :param old_table: The existing table name to be replaced.
        :param new_table: The new table name to use in place of the old one.

        """
        if self.table == old_table:
            self.table = new_table

    def __str__(self):
        return self.quote_name(self.table)


class TableColumns(Table):
    """Base class for references to multiple columns of a table."""

    def __init__(self, table, columns):
        self.table = table
        self.columns = columns

    def references_column(self, table, column):
        return self.table == table and column in self.columns

    def rename_column_references(self, table, old_column, new_column):
        if self.table == table:
            for index, column in enumerate(self.columns):
                if column == old_column:
                    self.columns[index] = new_column


class Columns(TableColumns):
    """Hold a reference to one or many columns."""

    def __init__(self, table, columns, quote_name, col_suffixes=()):
        self.quote_name = quote_name
        self.col_suffixes = col_suffixes
        super().__init__(table, columns)

    def __str__(self):
        def col_str(column, idx):
            col = self.quote_name(column)
            try:
                suffix = self.col_suffixes[idx]
                if suffix:
                    col = "{} {}".format(col, suffix)
            except IndexError:
                pass
            return col

        return ", ".join(
            col_str(column, idx) for idx, column in enumerate(self.columns)
        )


class IndexName(TableColumns):
    """Hold a reference to an index name."""

    def __init__(self, table, columns, suffix, create_index_name):
        self.suffix = suffix
        self.create_index_name = create_index_name
        super().__init__(table, columns)

    def __str__(self):
        return self.create_index_name(self.table, self.columns, self.suffix)


class IndexColumns(Columns):
    def __init__(self, table, columns, quote_name, col_suffixes=(), opclasses=()):
        self.opclasses = opclasses
        super().__init__(table, columns, quote_name, col_suffixes)

    def __str__(self):
        def col_str(column, idx):
            # Index.__init__() guarantees that self.opclasses is the same
            # length as self.columns.
            col = "{} {}".format(self.quote_name(column), self.opclasses[idx])
            try:
                suffix = self.col_suffixes[idx]
                if suffix:
                    col = "{} {}".format(col, suffix)
            except IndexError:
                pass
            return col

        return ", ".join(
            col_str(column, idx) for idx, column in enumerate(self.columns)
        )


class ForeignKeyName(TableColumns):
    """Hold a reference to a foreign key name."""

    def __init__(
        self,
        from_table,
        from_columns,
        to_table,
        to_columns,
        suffix_template,
        create_fk_name,
    ):
        """

        Initializes a relationship between two tables in a database.

        This initializer sets up a relationship by defining the columns in the source table (:param from_table) 
        and the columns in the destination table (:param to_table) that participate in this relationship.
        The :param from_columns and :param to_columns parameters specify the respective columns involved.
        A suffix template (:param suffix_template) can be used to customize the naming of the foreign key columns.
        Additionally, a flag (:param create_fk_name) is used to control the creation of a foreign key name.

        The resulting relationship object encapsulates the source and destination tables and their respective columns,
        as well as the suffix template and foreign key creation flag.

        """
        self.to_reference = TableColumns(to_table, to_columns)
        self.suffix_template = suffix_template
        self.create_fk_name = create_fk_name
        super().__init__(
            from_table,
            from_columns,
        )

    def references_table(self, table):
        return super().references_table(table) or self.to_reference.references_table(
            table
        )

    def references_column(self, table, column):
        return super().references_column(
            table, column
        ) or self.to_reference.references_column(table, column)

    def rename_table_references(self, old_table, new_table):
        """
        Rename all references to an old table name with a new table name.

        This method updates all references to the specified old table name with the new table name.
        It ensures that all dependencies and related objects, including the 'to_reference' object,
        are updated to reflect the new table name, maintaining data consistency.

        :param old_table: The current name of the table to be renamed.
        :param new_table: The new name for the table.

        """
        super().rename_table_references(old_table, new_table)
        self.to_reference.rename_table_references(old_table, new_table)

    def rename_column_references(self, table, old_column, new_column):
        super().rename_column_references(table, old_column, new_column)
        self.to_reference.rename_column_references(table, old_column, new_column)

    def __str__(self):
        """
        Returns a string representation of the foreign key constraint.

        This method generates a unique and descriptive name for the foreign key based on the table, columns, and referenced table and column. The name is constructed by combining the table and column names with a suffix that includes the referenced table and column, providing a clear and concise identification of the foreign key constraint. The generated name follows a standardized format to facilitate readability and maintainability of the database schema.
        """
        suffix = self.suffix_template % {
            "to_table": self.to_reference.table,
            "to_column": self.to_reference.columns[0],
        }
        return self.create_fk_name(self.table, self.columns, suffix)


class Statement(Reference):
    """
    Statement template and formatting parameters container.

    Allows keeping a reference to a statement without interpolating identifiers
    that might have to be adjusted if they're referencing a table or column
    that is removed
    """

    def __init__(self, template, **parts):
        self.template = template
        self.parts = parts

    def references_table(self, table):
        return any(
            hasattr(part, "references_table") and part.references_table(table)
            for part in self.parts.values()
        )

    def references_column(self, table, column):
        return any(
            hasattr(part, "references_column") and part.references_column(table, column)
            for part in self.parts.values()
        )

    def references_index(self, table, index):
        return any(
            hasattr(part, "references_index") and part.references_index(table, index)
            for part in self.parts.values()
        )

    def rename_table_references(self, old_table, new_table):
        """

        Recursively rename references to a database table in the object's components.

        This method updates all occurrences of the old table name to the new table name 
        in the object's parts and their sub-parts. It is used to maintain data integrity 
        and consistency after renaming a database table.

        :param old_table: The current name of the table to be renamed.
        :param new_table: The new name for the table.

        """
        for part in self.parts.values():
            if hasattr(part, "rename_table_references"):
                part.rename_table_references(old_table, new_table)

    def rename_column_references(self, table, old_column, new_column):
        for part in self.parts.values():
            if hasattr(part, "rename_column_references"):
                part.rename_column_references(table, old_column, new_column)

    def __str__(self):
        return self.template % self.parts


class Expressions(TableColumns):
    def __init__(self, table, expressions, compiler, quote_value):
        self.compiler = compiler
        self.expressions = expressions
        self.quote_value = quote_value
        columns = [
            col.target.column
            for col in self.compiler.query._gen_cols([self.expressions])
        ]
        super().__init__(table, columns)

    def rename_table_references(self, old_table, new_table):
        if self.table != old_table:
            return
        self.expressions = self.expressions.relabeled_clone({old_table: new_table})
        super().rename_table_references(old_table, new_table)

    def rename_column_references(self, table, old_column, new_column):
        if self.table != table:
            return
        expressions = deepcopy(self.expressions)
        self.columns = []
        for col in self.compiler.query._gen_cols([expressions]):
            if col.target.column == old_column:
                col.target.column = new_column
            self.columns.append(col.target.column)
        self.expressions = expressions

    def __str__(self):
        sql, params = self.compiler.compile(self.expressions)
        params = map(self.quote_value, params)
        return sql % tuple(params)
