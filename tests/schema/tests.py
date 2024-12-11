import datetime
import itertools
import unittest
from copy import copy
from decimal import Decimal
from unittest import mock

from django.core.exceptions import FieldError
from django.core.management.color import no_style
from django.core.serializers.json import DjangoJSONEncoder
from django.db import (
    DatabaseError,
    DataError,
    IntegrityError,
    OperationalError,
    connection,
)
from django.db.backends.utils import truncate_name
from django.db.models import (
    CASCADE,
    PROTECT,
    AutoField,
    BigAutoField,
    BigIntegerField,
    BinaryField,
    BooleanField,
    CharField,
    CheckConstraint,
    DateField,
    DateTimeField,
    DecimalField,
    DurationField,
    F,
    FloatField,
    ForeignKey,
    ForeignObject,
    GeneratedField,
    Index,
    IntegerField,
    JSONField,
    ManyToManyField,
    Model,
    OneToOneField,
    OrderBy,
    PositiveIntegerField,
    Q,
    SlugField,
    SmallAutoField,
    SmallIntegerField,
    TextField,
    TimeField,
    UniqueConstraint,
    UUIDField,
    Value,
)
from django.db.models.fields.json import KT, KeyTextTransform
from django.db.models.functions import (
    Abs,
    Cast,
    Collate,
    Concat,
    Lower,
    Random,
    Round,
    Upper,
)
from django.db.models.indexes import IndexExpression
from django.db.transaction import TransactionManagementError, atomic
from django.test import TransactionTestCase, skipIfDBFeature, skipUnlessDBFeature
from django.test.utils import CaptureQueriesContext, isolate_apps, register_lookup

from .fields import CustomManyToManyField, InheritedManyToManyField, MediumBlobField
from .models import (
    Author,
    AuthorCharFieldWithIndex,
    AuthorTextFieldWithIndex,
    AuthorWithDefaultHeight,
    AuthorWithEvenLongerName,
    AuthorWithIndexedName,
    AuthorWithUniqueName,
    AuthorWithUniqueNameAndBirthday,
    Book,
    BookForeignObj,
    BookWeak,
    BookWithLongName,
    BookWithO2O,
    BookWithoutAuthor,
    BookWithSlug,
    IntegerPK,
    Node,
    Note,
    NoteRename,
    Tag,
    TagM2MTest,
    TagUniqueRename,
    Thing,
    UniqueTest,
    new_apps,
)


class SchemaTests(TransactionTestCase):
    """
    Tests for the schema-alteration code.

    Be aware that these tests are more liable than most to false results,
    as sometimes the code to check if a test has worked is almost as complex
    as the code it is testing.
    """

    available_apps = []

    models = [
        Author,
        AuthorCharFieldWithIndex,
        AuthorTextFieldWithIndex,
        AuthorWithDefaultHeight,
        AuthorWithEvenLongerName,
        Book,
        BookWeak,
        BookWithLongName,
        BookWithO2O,
        BookWithSlug,
        IntegerPK,
        Node,
        Note,
        Tag,
        TagM2MTest,
        TagUniqueRename,
        Thing,
        UniqueTest,
    ]

    # Utility functions

    def setUp(self):
        # local_models should contain test dependent model classes that will be
        # automatically removed from the app cache on test tear down.
        self.local_models = []
        # isolated_local_models contains models that are in test methods
        # decorated with @isolate_apps.
        self.isolated_local_models = []

    def tearDown(self):
        # Delete any tables made for our models
        self.delete_tables()
        new_apps.clear_cache()
        for model in new_apps.get_models():
            model._meta._expire_cache()
        if "schema" in new_apps.all_models:
            for model in self.local_models:
                for many_to_many in model._meta.many_to_many:
                    through = many_to_many.remote_field.through
                    if through and through._meta.auto_created:
                        del new_apps.all_models["schema"][through._meta.model_name]
                del new_apps.all_models["schema"][model._meta.model_name]
        if self.isolated_local_models:
            with connection.schema_editor() as editor:
                for model in self.isolated_local_models:
                    editor.delete_model(model)

    def delete_tables(self):
        "Deletes all model tables for our models for a clean test environment"
        converter = connection.introspection.identifier_converter
        with connection.schema_editor() as editor:
            connection.disable_constraint_checking()
            table_names = connection.introspection.table_names()
            if connection.features.ignores_table_name_case:
                table_names = [table_name.lower() for table_name in table_names]
            for model in itertools.chain(SchemaTests.models, self.local_models):
                tbl = converter(model._meta.db_table)
                if connection.features.ignores_table_name_case:
                    tbl = tbl.lower()
                if tbl in table_names:
                    editor.delete_model(model)
                    table_names.remove(tbl)
            connection.enable_constraint_checking()

    def column_classes(self, model):
        """

        Returns a dictionary of column names to their respective database field types 
        and descriptions for a given Django model.

        The dictionary maps each column name in the model's database table to a tuple 
        containing the field type and a description of the column.

        The resulting dictionary can be used to inspect the database schema of the model, 
        providing key information about the columns that comprise the model's table.

        :arg model: A Django model instance
        :rtype: dict

        """
        with connection.cursor() as cursor:
            columns = {
                d[0]: (connection.introspection.get_field_type(d[1], d), d)
                for d in connection.introspection.get_table_description(
                    cursor,
                    model._meta.db_table,
                )
            }
        # SQLite has a different format for field_type
        for name, (type, desc) in columns.items():
            if isinstance(type, tuple):
                columns[name] = (type[0], desc)
        return columns

    def get_primary_key(self, table):
        with connection.cursor() as cursor:
            return connection.introspection.get_primary_key_column(cursor, table)

    def get_indexes(self, table):
        """
        Get the indexes on the table using a new cursor.
        """
        with connection.cursor() as cursor:
            return [
                c["columns"][0]
                for c in connection.introspection.get_constraints(
                    cursor, table
                ).values()
                if c["index"] and len(c["columns"]) == 1
            ]

    def get_uniques(self, table):
        with connection.cursor() as cursor:
            return [
                c["columns"][0]
                for c in connection.introspection.get_constraints(
                    cursor, table
                ).values()
                if c["unique"] and len(c["columns"]) == 1
            ]

    def get_constraints(self, table):
        """
        Get the constraints on a table using a new cursor.
        """
        with connection.cursor() as cursor:
            return connection.introspection.get_constraints(cursor, table)

    def get_constraints_for_column(self, model, column_name):
        constraints = self.get_constraints(model._meta.db_table)
        constraints_for_column = []
        for name, details in constraints.items():
            if details["columns"] == [column_name]:
                constraints_for_column.append(name)
        return sorted(constraints_for_column)

    def get_constraint_opclasses(self, constraint_name):
        """
        Returns a list of operator classes associated with the given constraint.

        This function queries the database to retrieve the operator classes used by the
        index associated with the specified constraint name. It joins the necessary
        PostgreSQL system catalogs to fetch the required information.

        The result is a list of operator class names (opcname) as strings.

        :param constraint_name: The name of the constraint to retrieve operator classes for
        :returns: A list of operator class names
        :rtype: list[str]
        """
        with connection.cursor() as cursor:
            sql = """
                SELECT opcname
                FROM pg_opclass AS oc
                JOIN pg_index as i on oc.oid = ANY(i.indclass)
                JOIN pg_class as c on c.oid = i.indexrelid
                WHERE c.relname = %s
            """
            cursor.execute(sql, [constraint_name])
            return [row[0] for row in cursor.fetchall()]

    def check_added_field_default(
        self,
        schema_editor,
        model,
        field,
        field_name,
        expected_default,
        cast_function=None,
    ):
        """
        Checks if the default value of a newly added field in a database matches the expected value.

        This function adds a field to a model using the provided schema editor, then queries the database to retrieve the default value of the newly added field. It compares this value to the expected default, optionally applying a casting function to ensure the types match. The function asserts that the retrieved default value matches the expected value.
        """
        with connection.cursor() as cursor:
            schema_editor.add_field(model, field)
            cursor.execute(
                "SELECT {} FROM {};".format(field_name, model._meta.db_table)
            )
            database_default = cursor.fetchall()[0][0]
            if cast_function and type(database_default) is not type(expected_default):
                database_default = cast_function(database_default)
            self.assertEqual(database_default, expected_default)

    def get_constraints_count(self, table, column, fk_to):
        """
        Return a dict with keys 'fks', 'uniques, and 'indexes' indicating the
        number of foreign keys, unique constraints, and indexes on
        `table`.`column`. The `fk_to` argument is a 2-tuple specifying the
        expected foreign key relationship's (table, column).
        """
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, table)
        counts = {"fks": 0, "uniques": 0, "indexes": 0}
        for c in constraints.values():
            if c["columns"] == [column]:
                if c["foreign_key"] == fk_to:
                    counts["fks"] += 1
                if c["unique"]:
                    counts["uniques"] += 1
                elif c["index"]:
                    counts["indexes"] += 1
        return counts

    def get_column_collation(self, table, column):
        """

        Get the collation of a specified column in a database table.

        Parameters
        ----------
        table : str
            The name of the database table.
        column : str
            The name of the column.

        Returns
        -------
        str
            The collation of the specified column, or None if the column is not found.

        Notes
        -----
        This method uses the database connection's introspection capabilities to retrieve
        the table description and then extracts the collation of the specified column.

        """
        with connection.cursor() as cursor:
            return next(
                f.collation
                for f in connection.introspection.get_table_description(cursor, table)
                if f.name == column
            )

    def get_column_comment(self, table, column):
        with connection.cursor() as cursor:
            return next(
                f.comment
                for f in connection.introspection.get_table_description(cursor, table)
                if f.name == column
            )

    def get_table_comment(self, table):
        """
        )..Get the comment associated with a specific database table.

            :param table: The name of the table for which to retrieve the comment.
            :return: The comment associated with the specified table.
            :rtype: str
            :raises: StopIteration if the table does not exist in the database. 

            Retrieves the comment associated with a specific database table. 
            This is useful for understanding the purpose or contents of a table. 
            If the table does not exist in the database, a StopIteration exception is raised.
        """
        with connection.cursor() as cursor:
            return next(
                t.comment
                for t in connection.introspection.get_table_list(cursor)
                if t.name == table
            )

    def assert_column_comment_not_exists(self, table, column):
        with connection.cursor() as cursor:
            columns = connection.introspection.get_table_description(cursor, table)
        self.assertFalse(any([c.name == column and c.comment for c in columns]))

    def assertIndexOrder(self, table, index, order):
        constraints = self.get_constraints(table)
        self.assertIn(index, constraints)
        index_orders = constraints[index]["orders"]
        self.assertTrue(
            all(val == expected for val, expected in zip(index_orders, order))
        )

    def assertForeignKeyExists(self, model, column, expected_fk_table, field="id"):
        """
        Fail if the FK constraint on `model.Meta.db_table`.`column` to
        `expected_fk_table`.id doesn't exist.
        """
        if not connection.features.can_introspect_foreign_keys:
            return
        constraints = self.get_constraints(model._meta.db_table)
        constraint_fk = None
        for details in constraints.values():
            if details["columns"] == [column] and details["foreign_key"]:
                constraint_fk = details["foreign_key"]
                break
        self.assertEqual(constraint_fk, (expected_fk_table, field))

    def assertForeignKeyNotExists(self, model, column, expected_fk_table):
        """

        Asserts that a foreign key does not exist on the specified column of a model.

        This method checks if a foreign key relationship is present on the given model and column.
        If the foreign key exists and points to the expected table, it raises an AssertionError.

        :param model: The model to check for the foreign key
        :param column: The column to check for the foreign key
        :param expected_fk_table: The expected table that the foreign key should point to

        """
        if not connection.features.can_introspect_foreign_keys:
            return
        with self.assertRaises(AssertionError):
            self.assertForeignKeyExists(model, column, expected_fk_table)

    # Tests
    def test_creation_deletion(self):
        """
        Tries creating a model's table, and then deleting it.
        """
        with connection.schema_editor() as editor:
            # Create the table
            editor.create_model(Author)
            # The table is there
            list(Author.objects.all())
            # Clean up that table
            editor.delete_model(Author)
            # No deferred SQL should be left over.
            self.assertEqual(editor.deferred_sql, [])
        # The table is gone
        with self.assertRaises(DatabaseError):
            list(Author.objects.all())

    @skipUnlessDBFeature("supports_foreign_keys")
    def test_fk(self):
        "Creating tables out of FK order, then repointing, works"
        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(Book)
            editor.create_model(Author)
            editor.create_model(Tag)
        # Initial tables are there
        list(Author.objects.all())
        list(Book.objects.all())
        # Make sure the FK constraint is present
        with self.assertRaises(IntegrityError):
            Book.objects.create(
                author_id=1,
                title="Much Ado About Foreign Keys",
                pub_date=datetime.datetime.now(),
            )
        # Repoint the FK constraint
        old_field = Book._meta.get_field("author")
        new_field = ForeignKey(Tag, CASCADE)
        new_field.set_attributes_from_name("author")
        with connection.schema_editor() as editor:
            editor.alter_field(Book, old_field, new_field, strict=True)
        self.assertForeignKeyExists(Book, "author_id", "schema_tag")

    @skipUnlessDBFeature("can_create_inline_fk")
    def test_inline_fk(self):
        # Create some tables.
        """

        Tests the creation of an inline foreign key.

        This test case verifies that a foreign key can be added to a model without
        the need for an additional migration to add a constraint. It creates the
        necessary models, adds a foreign key field to one of the models, and then
        checks that the foreign key exists in the database schema.

        The test also ensures that no additional ALTER TABLE statements are
        generated to add the constraint, confirming that the foreign key is created
        inline.

        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(Book)
            editor.create_model(Note)
        self.assertForeignKeyNotExists(Note, "book_id", "schema_book")
        # Add a foreign key from one to the other.
        with connection.schema_editor() as editor:
            new_field = ForeignKey(Book, CASCADE)
            new_field.set_attributes_from_name("book")
            editor.add_field(Note, new_field)
        self.assertForeignKeyExists(Note, "book_id", "schema_book")
        # Creating a FK field with a constraint uses a single statement without
        # a deferred ALTER TABLE.
        self.assertFalse(
            [
                sql
                for sql in (str(statement) for statement in editor.deferred_sql)
                if sql.startswith("ALTER TABLE") and "ADD CONSTRAINT" in sql
            ]
        )

    @skipUnlessDBFeature("can_create_inline_fk")
    def test_add_inline_fk_update_data(self):
        """
        Tests the addition of an inline foreign key and subsequent data update.

        This test case verifies the correct creation of a foreign key field, 
        adds it to an existing model, and then updates the associated data.
        It also checks that the corresponding index is created or not, 
        depending on the database's capability to index foreign keys.
        """
        with connection.schema_editor() as editor:
            editor.create_model(Node)
        # Add an inline foreign key and update data in the same transaction.
        new_field = ForeignKey(Node, CASCADE, related_name="new_fk", null=True)
        new_field.set_attributes_from_name("new_parent_fk")
        parent = Node.objects.create()
        with connection.schema_editor() as editor:
            editor.add_field(Node, new_field)
            editor.execute("UPDATE schema_node SET new_parent_fk_id = %s;", [parent.pk])
        assertIndex = (
            self.assertIn
            if connection.features.indexes_foreign_keys
            else self.assertNotIn
        )
        assertIndex("new_parent_fk_id", self.get_indexes(Node._meta.db_table))

    @skipUnlessDBFeature(
        "can_create_inline_fk",
        "allows_multiple_constraints_on_same_fields",
    )
    @isolate_apps("schema")
    def test_add_inline_fk_index_update_data(self):
        """

        Tests the addition of an inline foreign key index and updates the related data.

        This test case verifies that a foreign key field can be added to a model with an
        inline index, and that the related data can be updated successfully.

        The test creates a new model, adds a foreign key field to it, and then updates the
        related data using a schema editor. Finally, it checks that the updated index is
        present in the database.

        This test requires a database feature that allows creating inline foreign keys and
        multiple constraints on the same fields.

        """
        class Node(Model):
            class Meta:
                app_label = "schema"

        with connection.schema_editor() as editor:
            editor.create_model(Node)
        # Add an inline foreign key, update data, and an index in the same
        # transaction.
        new_field = ForeignKey(Node, CASCADE, related_name="new_fk", null=True)
        new_field.set_attributes_from_name("new_parent_fk")
        parent = Node.objects.create()
        with connection.schema_editor() as editor:
            editor.add_field(Node, new_field)
            Node._meta.add_field(new_field)
            editor.execute("UPDATE schema_node SET new_parent_fk_id = %s;", [parent.pk])
            editor.add_index(
                Node, Index(fields=["new_parent_fk"], name="new_parent_inline_fk_idx")
            )
        self.assertIn("new_parent_fk_id", self.get_indexes(Node._meta.db_table))

    @skipUnlessDBFeature("supports_foreign_keys")
    def test_char_field_with_db_index_to_fk(self):
        # Create the table
        """
        Tests the behavior of a CharField with a database index when it is altered to a ForeignKey.

        This test case covers the scenario where a CharField with an existing database index
        is modified to become a ForeignKey field that references another model.
        The test ensures that the database schema is updated correctly and that the foreign key
        constraint is created successfully.

        The test uses a temporary schema editor to create and modify the necessary models,
        and then verifies that the foreign key exists in the database schema after the
        alteration. The test also checks that the database constraints are applied correctly
        when the CharField is converted to a ForeignKey with a cascade deletion behavior.

        The test requires a database that supports foreign keys, and it skips the test if this
        feature is not available.

        It covers the edge case where the original field has a database index, which is an
        important consideration for database schema maintenance and evolution.
        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(AuthorCharFieldWithIndex)
        # Change CharField to FK
        old_field = AuthorCharFieldWithIndex._meta.get_field("char_field")
        new_field = ForeignKey(Author, CASCADE, blank=True)
        new_field.set_attributes_from_name("char_field")
        with connection.schema_editor() as editor:
            editor.alter_field(
                AuthorCharFieldWithIndex, old_field, new_field, strict=True
            )
        self.assertForeignKeyExists(
            AuthorCharFieldWithIndex, "char_field_id", "schema_author"
        )

    @skipUnlessDBFeature("supports_foreign_keys")
    @skipUnlessDBFeature("supports_index_on_text_field")
    def test_text_field_with_db_index_to_fk(self):
        # Create the table
        """
        Tests the creation of a text field with a database index that references a foreign key.

        This test case checks the support for foreign keys and indexing on text fields in the database.
        It creates two models, Author and AuthorTextFieldWithIndex, and then alters the text field in 
        AuthorTextFieldWithIndex to be a foreign key referencing the Author model, while maintaining 
        the existing database index. The test verifies that the foreign key is correctly established 
        and the corresponding index is present in the database schema.
        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(AuthorTextFieldWithIndex)
        # Change TextField to FK
        old_field = AuthorTextFieldWithIndex._meta.get_field("text_field")
        new_field = ForeignKey(Author, CASCADE, blank=True)
        new_field.set_attributes_from_name("text_field")
        with connection.schema_editor() as editor:
            editor.alter_field(
                AuthorTextFieldWithIndex, old_field, new_field, strict=True
            )
        self.assertForeignKeyExists(
            AuthorTextFieldWithIndex, "text_field_id", "schema_author"
        )

    @isolate_apps("schema")
    def test_char_field_pk_to_auto_field(self):
        """

        Tests the alteration of a CharField primary key to an AutoField primary key.

        This test case creates a model with a CharField primary key, then alters the field to an AutoField primary key using the Django schema editor.
        The test validates the process of replacing an existing primary key field with a new AutoField, checking that the field alteration is successful and accurate.

        """
        class Foo(Model):
            id = CharField(max_length=255, primary_key=True)

            class Meta:
                app_label = "schema"

        with connection.schema_editor() as editor:
            editor.create_model(Foo)
        self.isolated_local_models = [Foo]
        old_field = Foo._meta.get_field("id")
        new_field = AutoField(primary_key=True)
        new_field.set_attributes_from_name("id")
        new_field.model = Foo
        with connection.schema_editor() as editor:
            editor.alter_field(Foo, old_field, new_field, strict=True)

    @skipUnlessDBFeature("supports_foreign_keys")
    def test_fk_to_proxy(self):
        "Creating a FK to a proxy model creates database constraints."

        class AuthorProxy(Author):
            class Meta:
                app_label = "schema"
                apps = new_apps
                proxy = True

        class AuthorRef(Model):
            author = ForeignKey(AuthorProxy, on_delete=CASCADE)

            class Meta:
                app_label = "schema"
                apps = new_apps

        self.local_models = [AuthorProxy, AuthorRef]

        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(AuthorRef)
        self.assertForeignKeyExists(AuthorRef, "author_id", "schema_author")

    @skipUnlessDBFeature("supports_foreign_keys", "can_introspect_foreign_keys")
    def test_fk_db_constraint(self):
        "The db_constraint parameter is respected"
        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(Tag)
            editor.create_model(Author)
            editor.create_model(BookWeak)
        # Initial tables are there
        list(Author.objects.all())
        list(Tag.objects.all())
        list(BookWeak.objects.all())
        self.assertForeignKeyNotExists(BookWeak, "author_id", "schema_author")
        # Make a db_constraint=False FK
        new_field = ForeignKey(Tag, CASCADE, db_constraint=False)
        new_field.set_attributes_from_name("tag")
        with connection.schema_editor() as editor:
            editor.add_field(Author, new_field)
        self.assertForeignKeyNotExists(Author, "tag_id", "schema_tag")
        # Alter to one with a constraint
        new_field2 = ForeignKey(Tag, CASCADE)
        new_field2.set_attributes_from_name("tag")
        with connection.schema_editor() as editor:
            editor.alter_field(Author, new_field, new_field2, strict=True)
        self.assertForeignKeyExists(Author, "tag_id", "schema_tag")
        # Alter to one without a constraint again
        new_field2 = ForeignKey(Tag, CASCADE)
        new_field2.set_attributes_from_name("tag")
        with connection.schema_editor() as editor:
            editor.alter_field(Author, new_field2, new_field, strict=True)
        self.assertForeignKeyNotExists(Author, "tag_id", "schema_tag")

    @isolate_apps("schema")
    def test_no_db_constraint_added_during_primary_key_change(self):
        """
        When a primary key that's pointed to by a ForeignKey with
        db_constraint=False is altered, a foreign key constraint isn't added.
        """

        class Author(Model):
            class Meta:
                app_label = "schema"

        class BookWeak(Model):
            author = ForeignKey(Author, CASCADE, db_constraint=False)

            class Meta:
                app_label = "schema"

        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(BookWeak)
        self.assertForeignKeyNotExists(BookWeak, "author_id", "schema_author")
        old_field = Author._meta.get_field("id")
        new_field = BigAutoField(primary_key=True)
        new_field.model = Author
        new_field.set_attributes_from_name("id")
        # @isolate_apps() and inner models are needed to have the model
        # relations populated, otherwise this doesn't act as a regression test.
        self.assertEqual(len(new_field.model._meta.related_objects), 1)
        with connection.schema_editor() as editor:
            editor.alter_field(Author, old_field, new_field, strict=True)
        self.assertForeignKeyNotExists(BookWeak, "author_id", "schema_author")

    def _test_m2m_db_constraint(self, M2MFieldClass):
        class LocalAuthorWithM2M(Model):
            name = CharField(max_length=255)

            class Meta:
                app_label = "schema"
                apps = new_apps

        self.local_models = [LocalAuthorWithM2M]

        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(Tag)
            editor.create_model(LocalAuthorWithM2M)
        # Initial tables are there
        list(LocalAuthorWithM2M.objects.all())
        list(Tag.objects.all())
        # Make a db_constraint=False FK
        new_field = M2MFieldClass(Tag, related_name="authors", db_constraint=False)
        new_field.contribute_to_class(LocalAuthorWithM2M, "tags")
        # Add the field
        with connection.schema_editor() as editor:
            editor.add_field(LocalAuthorWithM2M, new_field)
        self.assertForeignKeyNotExists(
            new_field.remote_field.through, "tag_id", "schema_tag"
        )

    @skipUnlessDBFeature("supports_foreign_keys")
    def test_m2m_db_constraint(self):
        self._test_m2m_db_constraint(ManyToManyField)

    @skipUnlessDBFeature("supports_foreign_keys")
    def test_m2m_db_constraint_custom(self):
        self._test_m2m_db_constraint(CustomManyToManyField)

    @skipUnlessDBFeature("supports_foreign_keys")
    def test_m2m_db_constraint_inherited(self):
        self._test_m2m_db_constraint(InheritedManyToManyField)

    def test_add_field(self):
        """
        Tests adding fields to models
        """
        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        # Ensure there's no age field
        columns = self.column_classes(Author)
        self.assertNotIn("age", columns)
        # Add the new field
        new_field = IntegerField(null=True)
        new_field.set_attributes_from_name("age")
        with (
            CaptureQueriesContext(connection) as ctx,
            connection.schema_editor() as editor,
        ):
            editor.add_field(Author, new_field)
        drop_default_sql = editor.sql_alter_column_no_default % {
            "column": editor.quote_name(new_field.name),
        }
        self.assertFalse(
            any(drop_default_sql in query["sql"] for query in ctx.captured_queries)
        )
        # Table is not rebuilt.
        self.assertIs(
            any("CREATE TABLE" in query["sql"] for query in ctx.captured_queries), False
        )
        self.assertIs(
            any("DROP TABLE" in query["sql"] for query in ctx.captured_queries), False
        )
        columns = self.column_classes(Author)
        self.assertEqual(
            columns["age"][0],
            connection.features.introspected_field_types["IntegerField"],
        )
        self.assertTrue(columns["age"][1][6])

    def test_add_field_remove_field(self):
        """
        Adding a field and removing it removes all deferred sql referring to it.
        """
        with connection.schema_editor() as editor:
            # Create a table with a unique constraint on the slug field.
            editor.create_model(Tag)
            # Remove the slug column.
            editor.remove_field(Tag, Tag._meta.get_field("slug"))
        self.assertEqual(editor.deferred_sql, [])

    def test_add_field_temp_default(self):
        """
        Tests adding fields to models with a temporary default
        """
        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        # Ensure there's no age field
        columns = self.column_classes(Author)
        self.assertNotIn("age", columns)
        # Add some rows of data
        Author.objects.create(name="Andrew", height=30)
        Author.objects.create(name="Andrea")
        # Add a not-null field
        new_field = CharField(max_length=30, default="Godwin")
        new_field.set_attributes_from_name("surname")
        with connection.schema_editor() as editor:
            editor.add_field(Author, new_field)
        columns = self.column_classes(Author)
        self.assertEqual(
            columns["surname"][0],
            connection.features.introspected_field_types["CharField"],
        )
        self.assertEqual(
            columns["surname"][1][6],
            connection.features.interprets_empty_strings_as_nulls,
        )

    def test_add_field_temp_default_boolean(self):
        """
        Tests adding fields to models with a temporary default where
        the default is False. (#21783)
        """
        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        # Ensure there's no age field
        columns = self.column_classes(Author)
        self.assertNotIn("age", columns)
        # Add some rows of data
        Author.objects.create(name="Andrew", height=30)
        Author.objects.create(name="Andrea")
        # Add a not-null field
        new_field = BooleanField(default=False)
        new_field.set_attributes_from_name("awesome")
        with connection.schema_editor() as editor:
            editor.add_field(Author, new_field)
        columns = self.column_classes(Author)
        # BooleanField are stored as TINYINT(1) on MySQL.
        field_type = columns["awesome"][0]
        self.assertEqual(
            field_type, connection.features.introspected_field_types["BooleanField"]
        )

    def test_add_field_default_transform(self):
        """
        Tests adding fields to models with a default that is not directly
        valid in the database (#22581)
        """

        class TestTransformField(IntegerField):
            # Weird field that saves the count of items in its value
            def get_default(self):
                return self.default

            def get_prep_value(self, value):
                if value is None:
                    return 0
                return len(value)

        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        # Add some rows of data
        Author.objects.create(name="Andrew", height=30)
        Author.objects.create(name="Andrea")
        # Add the field with a default it needs to cast (to string in this case)
        new_field = TestTransformField(default={1: 2})
        new_field.set_attributes_from_name("thing")
        with connection.schema_editor() as editor:
            editor.add_field(Author, new_field)
        # Ensure the field is there
        columns = self.column_classes(Author)
        field_type, field_info = columns["thing"]
        self.assertEqual(
            field_type, connection.features.introspected_field_types["IntegerField"]
        )
        # Make sure the values were transformed correctly
        self.assertEqual(Author.objects.extra(where=["thing = 1"]).count(), 2)

    def test_add_field_o2o_nullable(self):
        """

        Test adding a one-to-one nullable field to a model.

        This test case verifies the process of dynamically adding a one-to-one field 
        to an existing model, specifically handling the case where the field is nullable.

        The test covers creating the necessary models, adding the one-to-one field to 
        the target model, and confirming that the corresponding database column is 
        successfully created and denoted as nullable.

        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(Note)
        new_field = OneToOneField(Note, CASCADE, null=True)
        new_field.set_attributes_from_name("note")
        with connection.schema_editor() as editor:
            editor.add_field(Author, new_field)
        columns = self.column_classes(Author)
        self.assertIn("note_id", columns)
        self.assertTrue(columns["note_id"][1][6])

    def test_add_field_binary(self):
        """
        Tests binary fields get a sane default (#22851)
        """
        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        # Add the new field
        new_field = BinaryField(blank=True)
        new_field.set_attributes_from_name("bits")
        with connection.schema_editor() as editor:
            editor.add_field(Author, new_field)
        columns = self.column_classes(Author)
        # MySQL annoyingly uses the same backend, so it'll come back as one of
        # these two types.
        self.assertIn(columns["bits"][0], ("BinaryField", "TextField"))

    def test_add_field_durationfield_with_default(self):
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        new_field = DurationField(default=datetime.timedelta(minutes=10))
        new_field.set_attributes_from_name("duration")
        with connection.schema_editor() as editor:
            editor.add_field(Author, new_field)
        columns = self.column_classes(Author)
        self.assertEqual(
            columns["duration"][0],
            connection.features.introspected_field_types["DurationField"],
        )

    @unittest.skipUnless(connection.vendor == "mysql", "MySQL specific")
    def test_add_binaryfield_mediumblob(self):
        """
        Test adding a custom-sized binary field on MySQL (#24846).
        """
        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        # Add the new field with default
        new_field = MediumBlobField(blank=True, default=b"123")
        new_field.set_attributes_from_name("bits")
        with connection.schema_editor() as editor:
            editor.add_field(Author, new_field)
        columns = self.column_classes(Author)
        # Introspection treats BLOBs as TextFields
        self.assertEqual(columns["bits"][0], "TextField")

    @isolate_apps("schema")
    @skipUnlessDBFeature("supports_json_field", "supports_stored_generated_columns")
    def test_add_generated_field_with_kt_model(self):
        class GeneratedFieldKTModel(Model):
            data = JSONField()
            status = GeneratedField(
                expression=KT("data__status"),
                output_field=TextField(),
                db_persist=True,
            )

            class Meta:
                app_label = "schema"

        with CaptureQueriesContext(connection) as ctx:
            with connection.schema_editor() as editor:
                editor.create_model(GeneratedFieldKTModel)
        self.assertIs(
            any("None" in query["sql"] for query in ctx.captured_queries),
            False,
        )

    @isolate_apps("schema")
    @skipUnlessDBFeature("supports_virtual_generated_columns")
    def test_add_generated_boolean_field(self):
        class GeneratedBooleanFieldModel(Model):
            value = IntegerField(null=True)
            has_value = GeneratedField(
                expression=Q(value__isnull=False),
                output_field=BooleanField(),
                db_persist=False,
            )

            class Meta:
                app_label = "schema"

        with connection.schema_editor() as editor:
            editor.create_model(GeneratedBooleanFieldModel)
        obj = GeneratedBooleanFieldModel.objects.create()
        self.assertIs(obj.has_value, False)
        obj = GeneratedBooleanFieldModel.objects.create(value=1)
        self.assertIs(obj.has_value, True)

    @isolate_apps("schema")
    @skipUnlessDBFeature("supports_stored_generated_columns")
    def test_add_generated_field(self):
        """

        Tests the addition of a generated field to a model.

        This test case creates a model with a 'vat_price' field that is generated
        based on the value of the 'price' field. The generated field is persisted
        in the database and its value is computed using a stored generated column
        expression. The test ensures that the generated field is correctly added
        to the model and its value is calculated as expected.

        The test requires a database that supports stored generated columns.

        """
        class GeneratedFieldOutputFieldModel(Model):
            price = DecimalField(max_digits=7, decimal_places=2)
            vat_price = GeneratedField(
                expression=Round(F("price") * Value(Decimal("1.22")), 2),
                db_persist=True,
                output_field=DecimalField(max_digits=8, decimal_places=2),
            )

            class Meta:
                app_label = "schema"

        with connection.schema_editor() as editor:
            editor.create_model(GeneratedFieldOutputFieldModel)

    @isolate_apps("schema")
    @skipUnlessDBFeature("supports_stored_generated_columns")
    def test_add_generated_field_contains(self):
        class GeneratedFieldContainsModel(Model):
            text = TextField(default="foo")
            generated = GeneratedField(
                expression=Concat("text", Value("%")),
                db_persist=True,
                output_field=TextField(),
            )

            class Meta:
                app_label = "schema"

        with connection.schema_editor() as editor:
            editor.create_model(GeneratedFieldContainsModel)

        field = GeneratedField(
            expression=Q(text__contains="foo"),
            db_persist=True,
            output_field=BooleanField(),
        )
        field.contribute_to_class(GeneratedFieldContainsModel, "contains_foo")

        with connection.schema_editor() as editor:
            editor.add_field(GeneratedFieldContainsModel, field)

        obj = GeneratedFieldContainsModel.objects.create()
        obj.refresh_from_db()
        self.assertEqual(obj.text, "foo")
        self.assertEqual(obj.generated, "foo%")
        self.assertIs(obj.contains_foo, True)

    @isolate_apps("schema")
    @skipUnlessDBFeature("supports_stored_generated_columns")
    def test_alter_generated_field(self):
        """

        Tests the alteration of a generated field to add an index.

        This test case creates a model with a generated field and then modifies the field
        to add a database index. It checks that the index is successfully added to the
        database.

        The test requires a database that supports stored generated columns.

        """
        class GeneratedFieldIndexedModel(Model):
            number = IntegerField(default=1)
            generated = GeneratedField(
                expression=F("number"),
                db_persist=True,
                output_field=IntegerField(),
            )

            class Meta:
                app_label = "schema"

        with connection.schema_editor() as editor:
            editor.create_model(GeneratedFieldIndexedModel)

        old_field = GeneratedFieldIndexedModel._meta.get_field("generated")
        new_field = GeneratedField(
            expression=F("number"),
            db_persist=True,
            db_index=True,
            output_field=IntegerField(),
        )
        new_field.contribute_to_class(GeneratedFieldIndexedModel, "generated")

        with connection.schema_editor() as editor:
            editor.alter_field(GeneratedFieldIndexedModel, old_field, new_field)

        self.assertIn(
            "generated", self.get_indexes(GeneratedFieldIndexedModel._meta.db_table)
        )

    @isolate_apps("schema")
    def test_add_auto_field(self):
        """

        Test adding an auto field to a model.

        This test case covers the scenario where an auto field is added to an existing model.
        It creates a model with a character field as the primary key, then alters the field to
        remove the primary key attribute, and finally adds a new auto field as the primary key.

        The test verifies that the model can still be used to create instances after the field
        changes, ensuring that the database schema updates correctly.

        """
        class AddAutoFieldModel(Model):
            name = CharField(max_length=255, primary_key=True)

            class Meta:
                app_label = "schema"

        with connection.schema_editor() as editor:
            editor.create_model(AddAutoFieldModel)
        self.isolated_local_models = [AddAutoFieldModel]
        old_field = AddAutoFieldModel._meta.get_field("name")
        new_field = CharField(max_length=255)
        new_field.set_attributes_from_name("name")
        new_field.model = AddAutoFieldModel
        with connection.schema_editor() as editor:
            editor.alter_field(AddAutoFieldModel, old_field, new_field)
        new_auto_field = AutoField(primary_key=True)
        new_auto_field.set_attributes_from_name("id")
        new_auto_field.model = AddAutoFieldModel()
        with connection.schema_editor() as editor:
            editor.add_field(AddAutoFieldModel, new_auto_field)
        # Crashes on PostgreSQL when the GENERATED BY suffix is missing.
        AddAutoFieldModel.objects.create(name="test")

    def test_remove_field(self):
        """
        Tests the removal of a field from a model.

        This test case verifies that a field can be successfully removed from a model
        using the schema editor. It creates a model, removes a specified field, and then
        checks that the field is no longer present in the model's columns. Additionally,
        it ensures that no unnecessary SQL queries are executed during the field removal
        process, such as creating or dropping tables, if supported by the database backend.
        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            with CaptureQueriesContext(connection) as ctx:
                editor.remove_field(Author, Author._meta.get_field("name"))
        columns = self.column_classes(Author)
        self.assertNotIn("name", columns)
        if getattr(connection.features, "can_alter_table_drop_column", True):
            # Table is not rebuilt.
            self.assertIs(
                any("CREATE TABLE" in query["sql"] for query in ctx.captured_queries),
                False,
            )
            self.assertIs(
                any("DROP TABLE" in query["sql"] for query in ctx.captured_queries),
                False,
            )

    def test_remove_indexed_field(self):
        with connection.schema_editor() as editor:
            editor.create_model(AuthorCharFieldWithIndex)
        with connection.schema_editor() as editor:
            editor.remove_field(
                AuthorCharFieldWithIndex,
                AuthorCharFieldWithIndex._meta.get_field("char_field"),
            )
        columns = self.column_classes(AuthorCharFieldWithIndex)
        self.assertNotIn("char_field", columns)

    def test_alter(self):
        """
        Tests simple altering of fields
        """
        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        # Ensure the field is right to begin with
        columns = self.column_classes(Author)
        self.assertEqual(
            columns["name"][0],
            connection.features.introspected_field_types["CharField"],
        )
        self.assertEqual(
            bool(columns["name"][1][6]),
            bool(connection.features.interprets_empty_strings_as_nulls),
        )
        # Alter the name field to a TextField
        old_field = Author._meta.get_field("name")
        new_field = TextField(null=True)
        new_field.set_attributes_from_name("name")
        with connection.schema_editor() as editor:
            editor.alter_field(Author, old_field, new_field, strict=True)
        columns = self.column_classes(Author)
        self.assertEqual(columns["name"][0], "TextField")
        self.assertTrue(columns["name"][1][6])
        # Change nullability again
        new_field2 = TextField(null=False)
        new_field2.set_attributes_from_name("name")
        with connection.schema_editor() as editor:
            editor.alter_field(Author, new_field, new_field2, strict=True)
        columns = self.column_classes(Author)
        self.assertEqual(columns["name"][0], "TextField")
        self.assertEqual(
            bool(columns["name"][1][6]),
            bool(connection.features.interprets_empty_strings_as_nulls),
        )

    def test_alter_auto_field_to_integer_field(self):
        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        # Change AutoField to IntegerField
        old_field = Author._meta.get_field("id")
        new_field = IntegerField(primary_key=True)
        new_field.set_attributes_from_name("id")
        new_field.model = Author
        with connection.schema_editor() as editor:
            editor.alter_field(Author, old_field, new_field, strict=True)
        # Now that ID is an IntegerField, the database raises an error if it
        # isn't provided.
        if not connection.features.supports_unspecified_pk:
            with self.assertRaises(DatabaseError):
                Author.objects.create()

    def test_alter_auto_field_to_char_field(self):
        # Create the table
        """

        Tests the alteration of an auto field to a character field in a database model.

        This test case simulates the process of changing the primary key of the Author model 
        from an auto-incrementing integer field to a character field. The test verifies 
        that the Database schema can be successfully modified to accommodate this change.

        The test creates an instance of the Author model, retrieves its current primary key 
        field, defines a new character field with the same name and primary key properties, 
        and then uses the schema editor to alter the existing field to the new character field.

        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        # Change AutoField to CharField
        old_field = Author._meta.get_field("id")
        new_field = CharField(primary_key=True, max_length=50)
        new_field.set_attributes_from_name("id")
        new_field.model = Author
        with connection.schema_editor() as editor:
            editor.alter_field(Author, old_field, new_field, strict=True)

    @isolate_apps("schema")
    def test_alter_auto_field_quoted_db_column(self):
        class Foo(Model):
            id = AutoField(primary_key=True, db_column='"quoted_id"')

            class Meta:
                app_label = "schema"

        with connection.schema_editor() as editor:
            editor.create_model(Foo)
        self.isolated_local_models = [Foo]
        old_field = Foo._meta.get_field("id")
        new_field = BigAutoField(primary_key=True)
        new_field.model = Foo
        new_field.db_column = '"quoted_id"'
        new_field.set_attributes_from_name("id")
        with connection.schema_editor() as editor:
            editor.alter_field(Foo, old_field, new_field, strict=True)
        Foo.objects.create()

    def test_alter_not_unique_field_to_primary_key(self):
        # Create the table.
        """
        Tests the alteration of a non-unique field to a primary key field.

        This test case verifies that a field can be successfully modified to become a primary key,
        replacing the existing primary key in the process. It checks the resulting database constraints
        to ensure that the new primary key has the correct uniqueness properties.

        The test involves creating a model, altering an existing field to have primary key properties,
        and then verifying the outcome by checking the constraint counts on the affected database table.

        The expected outcome is that the altered field will have at most one uniqueness constraint,
        indicating that it has become the new primary key for the model.
        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        # Change UUIDField to primary key.
        old_field = Author._meta.get_field("uuid")
        new_field = UUIDField(primary_key=True)
        new_field.set_attributes_from_name("uuid")
        new_field.model = Author
        with connection.schema_editor() as editor:
            editor.remove_field(Author, Author._meta.get_field("id"))
            editor.alter_field(Author, old_field, new_field, strict=True)
        # Redundant unique constraint is not added.
        count = self.get_constraints_count(
            Author._meta.db_table,
            Author._meta.get_field("uuid").column,
            None,
        )
        self.assertLessEqual(count["uniques"], 1)

    @isolate_apps("schema")
    def test_alter_primary_key_quoted_db_table(self):
        """

        Tests altering the primary key of a model on a quoted database table.

        This test case creates a model `Foo` with a quoted database table name and an auto-incrementing primary key.
        It then alters the primary key field to use a `BigAutoField`, simulating a change in the primary key type.
        The test ensures that the schema alteration is applied successfully to the quoted database table.

        """
        class Foo(Model):
            class Meta:
                app_label = "schema"
                db_table = '"foo"'

        with connection.schema_editor() as editor:
            editor.create_model(Foo)
        self.isolated_local_models = [Foo]
        old_field = Foo._meta.get_field("id")
        new_field = BigAutoField(primary_key=True)
        new_field.model = Foo
        new_field.set_attributes_from_name("id")
        with connection.schema_editor() as editor:
            editor.alter_field(Foo, old_field, new_field, strict=True)
        Foo.objects.create()

    def test_alter_text_field(self):
        # Regression for "BLOB/TEXT column 'info' can't have a default value")
        # on MySQL.
        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(Note)
        old_field = Note._meta.get_field("info")
        new_field = TextField(blank=True)
        new_field.set_attributes_from_name("info")
        with connection.schema_editor() as editor:
            editor.alter_field(Note, old_field, new_field, strict=True)

    def test_alter_text_field_to_not_null_with_default_value(self):
        """

        Tests the altering of a text field in a database model to have a default value and not allow null values.

        This test case creates a Note object with an address field initially set to null.
        It then modifies the address field to have a default value and not allow null values.
        The test verifies that the existing Note object's address field is updated to the default value after the schema change.

        This ensures that when a text field is altered to have a default value and not allow null values, 
        existing null values are correctly replaced with the default value.

        """
        with connection.schema_editor() as editor:
            editor.create_model(Note)
        note = Note.objects.create(address=None)
        old_field = Note._meta.get_field("address")
        new_field = TextField(blank=True, default="", null=False)
        new_field.set_attributes_from_name("address")
        with connection.schema_editor() as editor:
            editor.alter_field(Note, old_field, new_field, strict=True)
        note.refresh_from_db()
        self.assertEqual(note.address, "")

    @skipUnlessDBFeature("can_defer_constraint_checks", "can_rollback_ddl")
    def test_alter_fk_checks_deferred_constraints(self):
        """
        #25492 - Altering a foreign key's structure and data in the same
        transaction.
        """
        with connection.schema_editor() as editor:
            editor.create_model(Node)
        old_field = Node._meta.get_field("parent")
        new_field = ForeignKey(Node, CASCADE)
        new_field.set_attributes_from_name("parent")
        parent = Node.objects.create()
        with connection.schema_editor() as editor:
            # Update the parent FK to create a deferred constraint check.
            Node.objects.update(parent=parent)
            editor.alter_field(Node, old_field, new_field, strict=True)

    @isolate_apps("schema")
    def test_alter_null_with_default_value_deferred_constraints(self):
        class Publisher(Model):
            class Meta:
                app_label = "schema"

        class Article(Model):
            publisher = ForeignKey(Publisher, CASCADE)
            title = CharField(max_length=50, null=True)
            description = CharField(max_length=100, null=True)

            class Meta:
                app_label = "schema"

        with connection.schema_editor() as editor:
            editor.create_model(Publisher)
            editor.create_model(Article)
        self.isolated_local_models = [Article, Publisher]

        publisher = Publisher.objects.create()
        Article.objects.create(publisher=publisher)

        old_title = Article._meta.get_field("title")
        new_title = CharField(max_length=50, null=False, default="")
        new_title.set_attributes_from_name("title")
        old_description = Article._meta.get_field("description")
        new_description = CharField(max_length=100, null=False, default="")
        new_description.set_attributes_from_name("description")
        with connection.schema_editor() as editor:
            editor.alter_field(Article, old_title, new_title, strict=True)
            editor.alter_field(Article, old_description, new_description, strict=True)

    def test_alter_text_field_to_date_field(self):
        """
        #25002 - Test conversion of text field to date field.
        """
        with connection.schema_editor() as editor:
            editor.create_model(Note)
        Note.objects.create(info="1988-05-05")
        old_field = Note._meta.get_field("info")
        new_field = DateField(blank=True)
        new_field.set_attributes_from_name("info")
        with connection.schema_editor() as editor:
            editor.alter_field(Note, old_field, new_field, strict=True)
        # Make sure the field isn't nullable
        columns = self.column_classes(Note)
        self.assertFalse(columns["info"][1][6])

    def test_alter_text_field_to_datetime_field(self):
        """
        #25002 - Test conversion of text field to datetime field.
        """
        with connection.schema_editor() as editor:
            editor.create_model(Note)
        Note.objects.create(info="1988-05-05 3:16:17.4567")
        old_field = Note._meta.get_field("info")
        new_field = DateTimeField(blank=True)
        new_field.set_attributes_from_name("info")
        with connection.schema_editor() as editor:
            editor.alter_field(Note, old_field, new_field, strict=True)
        # Make sure the field isn't nullable
        columns = self.column_classes(Note)
        self.assertFalse(columns["info"][1][6])

    def test_alter_text_field_to_time_field(self):
        """
        #25002 - Test conversion of text field to time field.
        """
        with connection.schema_editor() as editor:
            editor.create_model(Note)
        Note.objects.create(info="3:16:17.4567")
        old_field = Note._meta.get_field("info")
        new_field = TimeField(blank=True)
        new_field.set_attributes_from_name("info")
        with connection.schema_editor() as editor:
            editor.alter_field(Note, old_field, new_field, strict=True)
        # Make sure the field isn't nullable
        columns = self.column_classes(Note)
        self.assertFalse(columns["info"][1][6])

    @skipIfDBFeature("interprets_empty_strings_as_nulls")
    def test_alter_textual_field_keep_null_status(self):
        """
        Changing a field type shouldn't affect the not null status.
        """
        with connection.schema_editor() as editor:
            editor.create_model(Note)
        with self.assertRaises(IntegrityError):
            Note.objects.create(info=None)
        old_field = Note._meta.get_field("info")
        new_field = CharField(max_length=50)
        new_field.set_attributes_from_name("info")
        with connection.schema_editor() as editor:
            editor.alter_field(Note, old_field, new_field, strict=True)
        with self.assertRaises(IntegrityError):
            Note.objects.create(info=None)

    @skipUnlessDBFeature("interprets_empty_strings_as_nulls")
    def test_alter_textual_field_not_null_to_null(self):
        """
        Nullability for textual fields is preserved on databases that
        interpret empty strings as NULLs.
        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        columns = self.column_classes(Author)
        # Field is nullable.
        self.assertTrue(columns["uuid"][1][6])
        # Change to NOT NULL.
        old_field = Author._meta.get_field("uuid")
        new_field = SlugField(null=False, blank=True)
        new_field.set_attributes_from_name("uuid")
        with connection.schema_editor() as editor:
            editor.alter_field(Author, old_field, new_field, strict=True)
        columns = self.column_classes(Author)
        # Nullability is preserved.
        self.assertTrue(columns["uuid"][1][6])

    def test_alter_numeric_field_keep_null_status(self):
        """
        Changing a field type shouldn't affect the not null status.
        """
        with connection.schema_editor() as editor:
            editor.create_model(UniqueTest)
        with self.assertRaises(IntegrityError):
            UniqueTest.objects.create(year=None, slug="aaa")
        old_field = UniqueTest._meta.get_field("year")
        new_field = BigIntegerField()
        new_field.set_attributes_from_name("year")
        with connection.schema_editor() as editor:
            editor.alter_field(UniqueTest, old_field, new_field, strict=True)
        with self.assertRaises(IntegrityError):
            UniqueTest.objects.create(year=None, slug="bbb")

    def test_alter_null_to_not_null(self):
        """
        #23609 - Tests handling of default values when altering from NULL to NOT NULL.
        """
        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        # Ensure the field is right to begin with
        columns = self.column_classes(Author)
        self.assertTrue(columns["height"][1][6])
        # Create some test data
        Author.objects.create(name="Not null author", height=12)
        Author.objects.create(name="Null author")
        # Verify null value
        self.assertEqual(Author.objects.get(name="Not null author").height, 12)
        self.assertIsNone(Author.objects.get(name="Null author").height)
        # Alter the height field to NOT NULL with default
        old_field = Author._meta.get_field("height")
        new_field = PositiveIntegerField(default=42)
        new_field.set_attributes_from_name("height")
        with connection.schema_editor() as editor:
            editor.alter_field(Author, old_field, new_field, strict=True)
        columns = self.column_classes(Author)
        self.assertFalse(columns["height"][1][6])
        # Verify default value
        self.assertEqual(Author.objects.get(name="Not null author").height, 12)
        self.assertEqual(Author.objects.get(name="Null author").height, 42)

    def test_alter_charfield_to_null(self):
        """
        #24307 - Should skip an alter statement on databases with
        interprets_empty_strings_as_nulls when changing a CharField to null.
        """
        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        # Change the CharField to null
        old_field = Author._meta.get_field("name")
        new_field = copy(old_field)
        new_field.null = True
        with connection.schema_editor() as editor:
            editor.alter_field(Author, old_field, new_field, strict=True)

    @unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific")
    def test_alter_char_field_decrease_length(self):
        # Create the table.
        """

        Tests that attempting to alter a CharField to decrease its length results in an error when 
        there are existing rows with values that exceed the new length.

        This test is specific to PostgreSQL and checks that a DataError is raised when the 
        alter_field method is called with strict=True, ensuring data integrity.

        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        Author.objects.create(name="x" * 255)
        # Change max_length of CharField.
        old_field = Author._meta.get_field("name")
        new_field = CharField(max_length=254)
        new_field.set_attributes_from_name("name")
        with connection.schema_editor() as editor:
            msg = "value too long for type character varying(254)"
            with self.assertRaisesMessage(DataError, msg):
                editor.alter_field(Author, old_field, new_field, strict=True)

    @unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific")
    def test_alter_field_with_custom_db_type(self):
        """

        Tests the alteration of a model field with a custom database type.

        This test case specifically targets PostgreSQL databases and verifies the behavior
        of altering a field in a model using a custom database type, in this instance an
        ArrayField with a nested CharField. The test creates a temporary model, alters the
        field, and checks for the correct modification.

        The test covers the scenario of reducing the maximum length of the CharField within
        the ArrayField from 255 characters to 16 characters, ensuring that the database
        schema is updated correctly and the model's field is altered as expected.

        """
        from django.contrib.postgres.fields import ArrayField

        class Foo(Model):
            field = ArrayField(CharField(max_length=255))

            class Meta:
                app_label = "schema"

        with connection.schema_editor() as editor:
            editor.create_model(Foo)
        self.isolated_local_models = [Foo]
        old_field = Foo._meta.get_field("field")
        new_field = ArrayField(CharField(max_length=16))
        new_field.set_attributes_from_name("field")
        new_field.model = Foo
        with connection.schema_editor() as editor:
            editor.alter_field(Foo, old_field, new_field, strict=True)

    @isolate_apps("schema")
    @unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific")
    def test_alter_array_field_decrease_base_field_length(self):
        """
        Test that decreasing the base field length of an array field with existing data raises an error.

        This test checks the behavior of Django's schema editor when attempting to alter an array field
        to decrease the length of its base field, after the model has been created and populated with data.
        It verifies that the expected DataError is raised when the new field length is too small to accommodate
        the existing data, and that the error message matches the expected PostgreSQL error message.

        The test is specific to PostgreSQL and requires a PostgreSQL database connection to run.
        """
        from django.contrib.postgres.fields import ArrayField

        class ArrayModel(Model):
            field = ArrayField(CharField(max_length=16))

            class Meta:
                app_label = "schema"

        with connection.schema_editor() as editor:
            editor.create_model(ArrayModel)
        self.isolated_local_models = [ArrayModel]
        ArrayModel.objects.create(field=["x" * 16])
        old_field = ArrayModel._meta.get_field("field")
        new_field = ArrayField(CharField(max_length=15))
        new_field.set_attributes_from_name("field")
        new_field.model = ArrayModel
        with connection.schema_editor() as editor:
            msg = "value too long for type character varying(15)"
            with self.assertRaisesMessage(DataError, msg):
                editor.alter_field(ArrayModel, old_field, new_field, strict=True)

    @isolate_apps("schema")
    @unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific")
    def test_alter_array_field_decrease_nested_base_field_length(self):
        from django.contrib.postgres.fields import ArrayField

        class ArrayModel(Model):
            field = ArrayField(ArrayField(CharField(max_length=16)))

            class Meta:
                app_label = "schema"

        with connection.schema_editor() as editor:
            editor.create_model(ArrayModel)
        self.isolated_local_models = [ArrayModel]
        ArrayModel.objects.create(field=[["x" * 16]])
        old_field = ArrayModel._meta.get_field("field")
        new_field = ArrayField(ArrayField(CharField(max_length=15)))
        new_field.set_attributes_from_name("field")
        new_field.model = ArrayModel
        with connection.schema_editor() as editor:
            msg = "value too long for type character varying(15)"
            with self.assertRaisesMessage(DataError, msg):
                editor.alter_field(ArrayModel, old_field, new_field, strict=True)

    def _add_ci_collation(self):
        ci_collation = "case_insensitive"

        def drop_collation():
            with connection.cursor() as cursor:
                cursor.execute(f"DROP COLLATION IF EXISTS {ci_collation}")

        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE COLLATION IF NOT EXISTS {ci_collation} (provider=icu, "
                f"locale='und-u-ks-level2', deterministic=false)"
            )
        self.addCleanup(drop_collation)
        return ci_collation

    @isolate_apps("schema")
    @unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific")
    @skipUnlessDBFeature(
        "supports_collation_on_charfield",
        "supports_non_deterministic_collations",
    )
    def test_db_collation_arrayfield(self):
        from django.contrib.postgres.fields import ArrayField

        ci_collation = self._add_ci_collation()
        cs_collation = "en-x-icu"

        class ArrayModel(Model):
            field = ArrayField(CharField(max_length=16, db_collation=ci_collation))

            class Meta:
                app_label = "schema"

        # Create the table.
        with connection.schema_editor() as editor:
            editor.create_model(ArrayModel)
        self.isolated_local_models = [ArrayModel]
        self.assertEqual(
            self.get_column_collation(ArrayModel._meta.db_table, "field"),
            ci_collation,
        )
        # Alter collation.
        old_field = ArrayModel._meta.get_field("field")
        new_field_cs = ArrayField(CharField(max_length=16, db_collation=cs_collation))
        new_field_cs.set_attributes_from_name("field")
        new_field_cs.model = ArrayField
        with connection.schema_editor() as editor:
            editor.alter_field(ArrayModel, old_field, new_field_cs, strict=True)
        self.assertEqual(
            self.get_column_collation(ArrayModel._meta.db_table, "field"),
            cs_collation,
        )

    @isolate_apps("schema")
    @unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific")
    @skipUnlessDBFeature(
        "supports_collation_on_charfield",
        "supports_non_deterministic_collations",
    )
    def test_unique_with_collation_charfield(self):
        ci_collation = self._add_ci_collation()

        class CiCharModel(Model):
            field = CharField(max_length=16, db_collation=ci_collation, unique=True)

            class Meta:
                app_label = "schema"

        # Create the table.
        with connection.schema_editor() as editor:
            editor.create_model(CiCharModel)
        self.isolated_local_models = [CiCharModel]
        self.assertEqual(
            self.get_column_collation(CiCharModel._meta.db_table, "field"),
            ci_collation,
        )
        self.assertIn("field", self.get_uniques(CiCharModel._meta.db_table))

    @isolate_apps("schema")
    @unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific")
    @skipUnlessDBFeature("supports_collation_on_charfield")
    def test_unique_with_deterministic_collation_charfield(self):
        deterministic_collation = connection.features.test_collations.get(
            "deterministic"
        )
        if not deterministic_collation:
            self.skipTest("This backend does not support deterministic collations.")

        class CharModel(Model):
            field = CharField(db_collation=deterministic_collation, unique=True)

            class Meta:
                app_label = "schema"

        # Create the table.
        with connection.schema_editor() as editor:
            editor.create_model(CharModel)
        self.isolated_local_models = [CharModel]
        constraints = self.get_constraints_for_column(
            CharModel, CharModel._meta.get_field("field").column
        )
        self.assertIn("schema_charmodel_field_8b338dea_like", constraints)
        self.assertIn(
            "varchar_pattern_ops",
            self.get_constraint_opclasses("schema_charmodel_field_8b338dea_like"),
        )
        self.assertEqual(
            self.get_column_collation(CharModel._meta.db_table, "field"),
            deterministic_collation,
        )
        self.assertIn("field", self.get_uniques(CharModel._meta.db_table))

    @isolate_apps("schema")
    @unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific")
    @skipUnlessDBFeature(
        "supports_collation_on_charfield",
        "supports_non_deterministic_collations",
    )
    def test_relation_to_collation_charfield(self):
        """
        .Tests the behavior of a One-To-One relation with a CharField that uses a case-insensitive collation 
        on PostgreSQL databases, specifically checking that the collation is properly applied 
        to both the original field and the relation field. It verifies that the collation is set 
        correctly on both fields and that the relation field is included in the unique constraints.
        """
        ci_collation = self._add_ci_collation()

        class CiCharModel(Model):
            field = CharField(max_length=16, db_collation=ci_collation, unique=True)

            class Meta:
                app_label = "schema"

        class RelationModel(Model):
            field = OneToOneField(CiCharModel, CASCADE, to_field="field")

            class Meta:
                app_label = "schema"

        # Create the table.
        with connection.schema_editor() as editor:
            editor.create_model(CiCharModel)
            editor.create_model(RelationModel)
        self.isolated_local_models = [CiCharModel, RelationModel]
        self.assertEqual(
            self.get_column_collation(RelationModel._meta.db_table, "field_id"),
            ci_collation,
        )
        self.assertEqual(
            self.get_column_collation(CiCharModel._meta.db_table, "field"),
            ci_collation,
        )
        self.assertIn("field_id", self.get_uniques(RelationModel._meta.db_table))

    @isolate_apps("schema")
    @unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific")
    @skipUnlessDBFeature("supports_collation_on_charfield")
    def test_relation_to_deterministic_collation_charfield(self):
        deterministic_collation = connection.features.test_collations.get(
            "deterministic"
        )
        if not deterministic_collation:
            self.skipTest("This backend does not support deterministic collations.")

        class CharModel(Model):
            field = CharField(db_collation=deterministic_collation, unique=True)

            class Meta:
                app_label = "schema"

        class RelationModel(Model):
            field = OneToOneField(CharModel, CASCADE, to_field="field")

            class Meta:
                app_label = "schema"

        # Create the table.
        with connection.schema_editor() as editor:
            editor.create_model(CharModel)
            editor.create_model(RelationModel)
        self.isolated_local_models = [CharModel, RelationModel]
        constraints = self.get_constraints_for_column(
            CharModel, CharModel._meta.get_field("field").column
        )
        self.assertIn("schema_charmodel_field_8b338dea_like", constraints)
        self.assertIn(
            "varchar_pattern_ops",
            self.get_constraint_opclasses("schema_charmodel_field_8b338dea_like"),
        )
        rel_constraints = self.get_constraints_for_column(
            RelationModel, RelationModel._meta.get_field("field").column
        )
        self.assertIn("schema_relationmodel_field_id_395fbb08_like", rel_constraints)
        self.assertIn(
            "varchar_pattern_ops",
            self.get_constraint_opclasses(
                "schema_relationmodel_field_id_395fbb08_like"
            ),
        )
        self.assertEqual(
            self.get_column_collation(RelationModel._meta.db_table, "field_id"),
            deterministic_collation,
        )
        self.assertEqual(
            self.get_column_collation(CharModel._meta.db_table, "field"),
            deterministic_collation,
        )
        self.assertIn("field_id", self.get_uniques(RelationModel._meta.db_table))

    def test_alter_textfield_to_null(self):
        """
        #24307 - Should skip an alter statement on databases with
        interprets_empty_strings_as_nulls when changing a TextField to null.
        """
        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(Note)
        # Change the TextField to null
        old_field = Note._meta.get_field("info")
        new_field = copy(old_field)
        new_field.null = True
        with connection.schema_editor() as editor:
            editor.alter_field(Note, old_field, new_field, strict=True)

    def test_alter_null_to_not_null_keeping_default(self):
        """
        #23738 - Can change a nullable field with default to non-nullable
        with the same default.
        """
        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(AuthorWithDefaultHeight)
        # Ensure the field is right to begin with
        columns = self.column_classes(AuthorWithDefaultHeight)
        self.assertTrue(columns["height"][1][6])
        # Alter the height field to NOT NULL keeping the previous default
        old_field = AuthorWithDefaultHeight._meta.get_field("height")
        new_field = PositiveIntegerField(default=42)
        new_field.set_attributes_from_name("height")
        with connection.schema_editor() as editor:
            editor.alter_field(
                AuthorWithDefaultHeight, old_field, new_field, strict=True
            )
        columns = self.column_classes(AuthorWithDefaultHeight)
        self.assertFalse(columns["height"][1][6])

    @skipUnlessDBFeature("supports_foreign_keys")
    def test_alter_fk(self):
        """
        Tests altering of FKs
        """
        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(Book)
        # Ensure the field is right to begin with
        columns = self.column_classes(Book)
        self.assertEqual(
            columns["author_id"][0],
            connection.features.introspected_field_types["IntegerField"],
        )
        self.assertForeignKeyExists(Book, "author_id", "schema_author")
        # Alter the FK
        old_field = Book._meta.get_field("author")
        new_field = ForeignKey(Author, CASCADE, editable=False)
        new_field.set_attributes_from_name("author")
        with connection.schema_editor() as editor:
            editor.alter_field(Book, old_field, new_field, strict=True)
        columns = self.column_classes(Book)
        self.assertEqual(
            columns["author_id"][0],
            connection.features.introspected_field_types["IntegerField"],
        )
        self.assertForeignKeyExists(Book, "author_id", "schema_author")

    @skipUnlessDBFeature("supports_foreign_keys")
    def test_alter_to_fk(self):
        """
        #24447 - Tests adding a FK constraint for an existing column
        """

        class LocalBook(Model):
            author = IntegerField()
            title = CharField(max_length=100, db_index=True)
            pub_date = DateTimeField()

            class Meta:
                app_label = "schema"
                apps = new_apps

        self.local_models = [LocalBook]

        # Create the tables
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(LocalBook)
        # Ensure no FK constraint exists
        constraints = self.get_constraints(LocalBook._meta.db_table)
        for details in constraints.values():
            if details["foreign_key"]:
                self.fail(
                    "Found an unexpected FK constraint to %s" % details["columns"]
                )
        old_field = LocalBook._meta.get_field("author")
        new_field = ForeignKey(Author, CASCADE)
        new_field.set_attributes_from_name("author")
        with connection.schema_editor() as editor:
            editor.alter_field(LocalBook, old_field, new_field, strict=True)
        self.assertForeignKeyExists(LocalBook, "author_id", "schema_author")

    @skipUnlessDBFeature("supports_foreign_keys", "can_introspect_foreign_keys")
    def test_alter_o2o_to_fk(self):
        """
        #24163 - Tests altering of OneToOneField to ForeignKey
        """
        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(BookWithO2O)
        # Ensure the field is right to begin with
        columns = self.column_classes(BookWithO2O)
        self.assertEqual(
            columns["author_id"][0],
            connection.features.introspected_field_types["IntegerField"],
        )
        # Ensure the field is unique
        author = Author.objects.create(name="Joe")
        BookWithO2O.objects.create(
            author=author, title="Django 1", pub_date=datetime.datetime.now()
        )
        with self.assertRaises(IntegrityError):
            BookWithO2O.objects.create(
                author=author, title="Django 2", pub_date=datetime.datetime.now()
            )
        BookWithO2O.objects.all().delete()
        self.assertForeignKeyExists(BookWithO2O, "author_id", "schema_author")
        # Alter the OneToOneField to ForeignKey
        old_field = BookWithO2O._meta.get_field("author")
        new_field = ForeignKey(Author, CASCADE)
        new_field.set_attributes_from_name("author")
        with connection.schema_editor() as editor:
            editor.alter_field(BookWithO2O, old_field, new_field, strict=True)
        columns = self.column_classes(Book)
        self.assertEqual(
            columns["author_id"][0],
            connection.features.introspected_field_types["IntegerField"],
        )
        # Ensure the field is not unique anymore
        Book.objects.create(
            author=author, title="Django 1", pub_date=datetime.datetime.now()
        )
        Book.objects.create(
            author=author, title="Django 2", pub_date=datetime.datetime.now()
        )
        self.assertForeignKeyExists(Book, "author_id", "schema_author")

    @skipUnlessDBFeature("supports_foreign_keys", "can_introspect_foreign_keys")
    def test_alter_fk_to_o2o(self):
        """
        #24163 - Tests altering of ForeignKey to OneToOneField
        """
        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(Book)
        # Ensure the field is right to begin with
        columns = self.column_classes(Book)
        self.assertEqual(
            columns["author_id"][0],
            connection.features.introspected_field_types["IntegerField"],
        )
        # Ensure the field is not unique
        author = Author.objects.create(name="Joe")
        Book.objects.create(
            author=author, title="Django 1", pub_date=datetime.datetime.now()
        )
        Book.objects.create(
            author=author, title="Django 2", pub_date=datetime.datetime.now()
        )
        Book.objects.all().delete()
        self.assertForeignKeyExists(Book, "author_id", "schema_author")
        # Alter the ForeignKey to OneToOneField
        old_field = Book._meta.get_field("author")
        new_field = OneToOneField(Author, CASCADE)
        new_field.set_attributes_from_name("author")
        with connection.schema_editor() as editor:
            editor.alter_field(Book, old_field, new_field, strict=True)
        columns = self.column_classes(BookWithO2O)
        self.assertEqual(
            columns["author_id"][0],
            connection.features.introspected_field_types["IntegerField"],
        )
        # Ensure the field is unique now
        BookWithO2O.objects.create(
            author=author, title="Django 1", pub_date=datetime.datetime.now()
        )
        with self.assertRaises(IntegrityError):
            BookWithO2O.objects.create(
                author=author, title="Django 2", pub_date=datetime.datetime.now()
            )
        self.assertForeignKeyExists(BookWithO2O, "author_id", "schema_author")

    def test_alter_field_fk_to_o2o(self):
        """

        Tests the alteration of a foreign key field to a one-to-one field in the database schema.

        The test creates models for Author and Book, then verifies the initial database constraints 
        associated with the foreign key. It then alters the foreign key field to a one-to-one field 
        and checks that the resulting database constraints are correct.

        The expected constraints depend on the database features, specifically whether it supports 
        foreign keys, can introspect foreign keys, and indexes foreign keys.

        The test ensures that the one-to-one field is correctly established with a unique constraint 
        and that any indexes on the foreign key are removed.

        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(Book)
        expected_fks = (
            1
            if connection.features.supports_foreign_keys
            and connection.features.can_introspect_foreign_keys
            else 0
        )
        expected_indexes = 1 if connection.features.indexes_foreign_keys else 0

        # Check the index is right to begin with.
        counts = self.get_constraints_count(
            Book._meta.db_table,
            Book._meta.get_field("author").column,
            (Author._meta.db_table, Author._meta.pk.column),
        )
        self.assertEqual(
            counts,
            {"fks": expected_fks, "uniques": 0, "indexes": expected_indexes},
        )

        old_field = Book._meta.get_field("author")
        new_field = OneToOneField(Author, CASCADE)
        new_field.set_attributes_from_name("author")
        with connection.schema_editor() as editor:
            editor.alter_field(Book, old_field, new_field)

        counts = self.get_constraints_count(
            Book._meta.db_table,
            Book._meta.get_field("author").column,
            (Author._meta.db_table, Author._meta.pk.column),
        )
        # The index on ForeignKey is replaced with a unique constraint for
        # OneToOneField.
        self.assertEqual(counts, {"fks": expected_fks, "uniques": 1, "indexes": 0})

    def test_autofield_to_o2o(self):
        """

        Tests the conversion of an AutoField to a OneToOneField.

        This test case covers the scenario where an AutoField (primary key) is altered to a OneToOneField.
        It verifies that the field type is correctly changed and that the resulting field is an IntegerField.
        The test involves creating models, altering fields using the schema editor, and checking the resulting field types.

        The test includes the following steps:
        - Create the Author and Note models
        - Replace the primary key (id) of the Author model with a new AutoField
        - Convert the new AutoField to a OneToOneField referencing the Note model
        - Verify that the resulting field is an IntegerField

        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(Note)

        # Rename the field.
        old_field = Author._meta.get_field("id")
        new_field = AutoField(primary_key=True)
        new_field.set_attributes_from_name("note_ptr")
        new_field.model = Author

        with connection.schema_editor() as editor:
            editor.alter_field(Author, old_field, new_field, strict=True)
        # Alter AutoField to OneToOneField.
        new_field_o2o = OneToOneField(Note, CASCADE)
        new_field_o2o.set_attributes_from_name("note_ptr")
        new_field_o2o.model = Author

        with connection.schema_editor() as editor:
            editor.alter_field(Author, new_field, new_field_o2o, strict=True)
        columns = self.column_classes(Author)
        field_type, _ = columns["note_ptr_id"]
        self.assertEqual(
            field_type, connection.features.introspected_field_types["IntegerField"]
        )

    def test_alter_field_fk_keeps_index(self):
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(Book)
        expected_fks = (
            1
            if connection.features.supports_foreign_keys
            and connection.features.can_introspect_foreign_keys
            else 0
        )
        expected_indexes = 1 if connection.features.indexes_foreign_keys else 0

        # Check the index is right to begin with.
        counts = self.get_constraints_count(
            Book._meta.db_table,
            Book._meta.get_field("author").column,
            (Author._meta.db_table, Author._meta.pk.column),
        )
        self.assertEqual(
            counts,
            {"fks": expected_fks, "uniques": 0, "indexes": expected_indexes},
        )

        old_field = Book._meta.get_field("author")
        # on_delete changed from CASCADE.
        new_field = ForeignKey(Author, PROTECT)
        new_field.set_attributes_from_name("author")
        with connection.schema_editor() as editor:
            editor.alter_field(Book, old_field, new_field, strict=True)

        counts = self.get_constraints_count(
            Book._meta.db_table,
            Book._meta.get_field("author").column,
            (Author._meta.db_table, Author._meta.pk.column),
        )
        # The index remains.
        self.assertEqual(
            counts,
            {"fks": expected_fks, "uniques": 0, "indexes": expected_indexes},
        )

    def test_alter_field_o2o_to_fk(self):
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(BookWithO2O)
        expected_fks = (
            1
            if connection.features.supports_foreign_keys
            and connection.features.can_introspect_foreign_keys
            else 0
        )

        # Check the unique constraint is right to begin with.
        counts = self.get_constraints_count(
            BookWithO2O._meta.db_table,
            BookWithO2O._meta.get_field("author").column,
            (Author._meta.db_table, Author._meta.pk.column),
        )
        self.assertEqual(counts, {"fks": expected_fks, "uniques": 1, "indexes": 0})

        old_field = BookWithO2O._meta.get_field("author")
        new_field = ForeignKey(Author, CASCADE)
        new_field.set_attributes_from_name("author")
        with connection.schema_editor() as editor:
            editor.alter_field(BookWithO2O, old_field, new_field)

        counts = self.get_constraints_count(
            BookWithO2O._meta.db_table,
            BookWithO2O._meta.get_field("author").column,
            (Author._meta.db_table, Author._meta.pk.column),
        )
        # The unique constraint on OneToOneField is replaced with an index for
        # ForeignKey.
        self.assertEqual(counts, {"fks": expected_fks, "uniques": 0, "indexes": 1})

    def test_alter_field_o2o_keeps_unique(self):
        """

        Tests that altering an one-to-one field keeps its unique constraint.

        Verifies that when an one-to-one field in a model is altered, the unique constraint
        is preserved. The test checks for the presence of foreign keys, unique constraints,
        and indexes on the altered field before and after the alteration.

        This ensures that the database schema remains consistent after modifying the model,
        and that data integrity is maintained by preserving the unique constraint.

        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(BookWithO2O)
        expected_fks = (
            1
            if connection.features.supports_foreign_keys
            and connection.features.can_introspect_foreign_keys
            else 0
        )

        # Check the unique constraint is right to begin with.
        counts = self.get_constraints_count(
            BookWithO2O._meta.db_table,
            BookWithO2O._meta.get_field("author").column,
            (Author._meta.db_table, Author._meta.pk.column),
        )
        self.assertEqual(counts, {"fks": expected_fks, "uniques": 1, "indexes": 0})

        old_field = BookWithO2O._meta.get_field("author")
        # on_delete changed from CASCADE.
        new_field = OneToOneField(Author, PROTECT)
        new_field.set_attributes_from_name("author")
        with connection.schema_editor() as editor:
            editor.alter_field(BookWithO2O, old_field, new_field, strict=True)

        counts = self.get_constraints_count(
            BookWithO2O._meta.db_table,
            BookWithO2O._meta.get_field("author").column,
            (Author._meta.db_table, Author._meta.pk.column),
        )
        # The unique constraint remains.
        self.assertEqual(counts, {"fks": expected_fks, "uniques": 1, "indexes": 0})

    @skipUnlessDBFeature("ignores_table_name_case")
    def test_alter_db_table_case(self):
        # Create the table
        """
        Tests the alteration of a database table name to uppercase, verifying that the operation is successful when the database ignores table name case sensitivity.
        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        # Alter the case of the table
        old_table_name = Author._meta.db_table
        with connection.schema_editor() as editor:
            editor.alter_db_table(Author, old_table_name, old_table_name.upper())

    def test_alter_implicit_id_to_explicit(self):
        """
        Should be able to convert an implicit "id" field to an explicit "id"
        primary key field.
        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)

        old_field = Author._meta.get_field("id")
        new_field = AutoField(primary_key=True)
        new_field.set_attributes_from_name("id")
        new_field.model = Author
        with connection.schema_editor() as editor:
            editor.alter_field(Author, old_field, new_field, strict=True)
        # This will fail if DROP DEFAULT is inadvertently executed on this
        # field which drops the id sequence, at least on PostgreSQL.
        Author.objects.create(name="Foo")
        Author.objects.create(name="Bar")

    def test_alter_autofield_pk_to_bigautofield_pk(self):
        """

        Tests the alteration of an AutoField primary key to a BigAutoField primary key.

        This test case covers the scenario where an existing model's AutoField primary key
        is modified to a BigAutoField primary key. It creates an Author model with an AutoField
        primary key, alters the field to a BigAutoField, and then checks that new instances
        can still be created successfully.

        The test also verifies that the primary key sequence is properly reset after the
        alteration, ensuring that new instances receive valid primary key values.

        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        old_field = Author._meta.get_field("id")
        new_field = BigAutoField(primary_key=True)
        new_field.set_attributes_from_name("id")
        new_field.model = Author
        with connection.schema_editor() as editor:
            editor.alter_field(Author, old_field, new_field, strict=True)

        Author.objects.create(name="Foo", pk=1)
        with connection.cursor() as cursor:
            sequence_reset_sqls = connection.ops.sequence_reset_sql(
                no_style(), [Author]
            )
            if sequence_reset_sqls:
                cursor.execute(sequence_reset_sqls[0])
        self.assertIsNotNone(Author.objects.create(name="Bar"))

    def test_alter_autofield_pk_to_smallautofield_pk(self):
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        old_field = Author._meta.get_field("id")
        new_field = SmallAutoField(primary_key=True)
        new_field.set_attributes_from_name("id")
        new_field.model = Author
        with connection.schema_editor() as editor:
            editor.alter_field(Author, old_field, new_field, strict=True)

        Author.objects.create(name="Foo", pk=1)
        with connection.cursor() as cursor:
            sequence_reset_sqls = connection.ops.sequence_reset_sql(
                no_style(), [Author]
            )
            if sequence_reset_sqls:
                cursor.execute(sequence_reset_sqls[0])
        self.assertIsNotNone(Author.objects.create(name="Bar"))

    def test_alter_int_pk_to_autofield_pk(self):
        """
        Should be able to rename an IntegerField(primary_key=True) to
        AutoField(primary_key=True).
        """
        with connection.schema_editor() as editor:
            editor.create_model(IntegerPK)

        old_field = IntegerPK._meta.get_field("i")
        new_field = AutoField(primary_key=True)
        new_field.model = IntegerPK
        new_field.set_attributes_from_name("i")

        with connection.schema_editor() as editor:
            editor.alter_field(IntegerPK, old_field, new_field, strict=True)

        # A model representing the updated model.
        class IntegerPKToAutoField(Model):
            i = AutoField(primary_key=True)
            j = IntegerField(unique=True)

            class Meta:
                app_label = "schema"
                apps = new_apps
                db_table = IntegerPK._meta.db_table

        # An id (i) is generated by the database.
        obj = IntegerPKToAutoField.objects.create(j=1)
        self.assertIsNotNone(obj.i)

    def test_alter_int_pk_to_bigautofield_pk(self):
        """
        Should be able to rename an IntegerField(primary_key=True) to
        BigAutoField(primary_key=True).
        """
        with connection.schema_editor() as editor:
            editor.create_model(IntegerPK)

        old_field = IntegerPK._meta.get_field("i")
        new_field = BigAutoField(primary_key=True)
        new_field.model = IntegerPK
        new_field.set_attributes_from_name("i")

        with connection.schema_editor() as editor:
            editor.alter_field(IntegerPK, old_field, new_field, strict=True)

        # A model representing the updated model.
        class IntegerPKToBigAutoField(Model):
            i = BigAutoField(primary_key=True)
            j = IntegerField(unique=True)

            class Meta:
                app_label = "schema"
                apps = new_apps
                db_table = IntegerPK._meta.db_table

        # An id (i) is generated by the database.
        obj = IntegerPKToBigAutoField.objects.create(j=1)
        self.assertIsNotNone(obj.i)

    @isolate_apps("schema")
    def test_alter_smallint_pk_to_smallautofield_pk(self):
        """
        Should be able to rename an SmallIntegerField(primary_key=True) to
        SmallAutoField(primary_key=True).
        """

        class SmallIntegerPK(Model):
            i = SmallIntegerField(primary_key=True)

            class Meta:
                app_label = "schema"

        with connection.schema_editor() as editor:
            editor.create_model(SmallIntegerPK)
        self.isolated_local_models = [SmallIntegerPK]
        old_field = SmallIntegerPK._meta.get_field("i")
        new_field = SmallAutoField(primary_key=True)
        new_field.model = SmallIntegerPK
        new_field.set_attributes_from_name("i")
        with connection.schema_editor() as editor:
            editor.alter_field(SmallIntegerPK, old_field, new_field, strict=True)

    @isolate_apps("schema")
    @unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific")
    def test_alter_serial_auto_field_to_bigautofield(self):
        class SerialAutoField(Model):
            id = SmallAutoField(primary_key=True)

            class Meta:
                app_label = "schema"

        table = SerialAutoField._meta.db_table
        column = SerialAutoField._meta.get_field("id").column
        with connection.cursor() as cursor:
            cursor.execute(
                f'CREATE TABLE "{table}" '
                f'("{column}" smallserial NOT NULL PRIMARY KEY)'
            )
        try:
            old_field = SerialAutoField._meta.get_field("id")
            new_field = BigAutoField(primary_key=True)
            new_field.model = SerialAutoField
            new_field.set_attributes_from_name("id")
            with connection.schema_editor() as editor:
                editor.alter_field(SerialAutoField, old_field, new_field, strict=True)
            sequence_name = f"{table}_{column}_seq"
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT data_type FROM pg_sequences WHERE sequencename = %s",
                    [sequence_name],
                )
                row = cursor.fetchone()
                sequence_data_type = row[0] if row and row[0] else None
                self.assertEqual(sequence_data_type, "bigint")
            # Rename the column.
            old_field = new_field
            new_field = AutoField(primary_key=True)
            new_field.model = SerialAutoField
            new_field.set_attributes_from_name("renamed_id")
            with connection.schema_editor() as editor:
                editor.alter_field(SerialAutoField, old_field, new_field, strict=True)
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT data_type FROM pg_sequences WHERE sequencename = %s",
                    [sequence_name],
                )
                row = cursor.fetchone()
                sequence_data_type = row[0] if row and row[0] else None
                self.assertEqual(sequence_data_type, "integer")
        finally:
            with connection.cursor() as cursor:
                cursor.execute(f'DROP TABLE "{table}"')

    def test_alter_int_pk_to_int_unique(self):
        """
        Should be able to rename an IntegerField(primary_key=True) to
        IntegerField(unique=True).
        """
        with connection.schema_editor() as editor:
            editor.create_model(IntegerPK)
        # Delete the old PK
        old_field = IntegerPK._meta.get_field("i")
        new_field = IntegerField(unique=True)
        new_field.model = IntegerPK
        new_field.set_attributes_from_name("i")
        with connection.schema_editor() as editor:
            editor.alter_field(IntegerPK, old_field, new_field, strict=True)
        # The primary key constraint is gone. Result depends on database:
        # 'id' for SQLite, None for others (must not be 'i').
        self.assertIn(self.get_primary_key(IntegerPK._meta.db_table), ("id", None))

        # Set up a model class as it currently stands. The original IntegerPK
        # class is now out of date and some backends make use of the whole
        # model class when modifying a field (such as sqlite3 when remaking a
        # table) so an outdated model class leads to incorrect results.
        class Transitional(Model):
            i = IntegerField(unique=True)
            j = IntegerField(unique=True)

            class Meta:
                app_label = "schema"
                apps = new_apps
                db_table = "INTEGERPK"

        # model requires a new PK
        old_field = Transitional._meta.get_field("j")
        new_field = IntegerField(primary_key=True)
        new_field.model = Transitional
        new_field.set_attributes_from_name("j")

        with connection.schema_editor() as editor:
            editor.alter_field(Transitional, old_field, new_field, strict=True)

        # Create a model class representing the updated model.
        class IntegerUnique(Model):
            i = IntegerField(unique=True)
            j = IntegerField(primary_key=True)

            class Meta:
                app_label = "schema"
                apps = new_apps
                db_table = "INTEGERPK"

        # Ensure unique constraint works.
        IntegerUnique.objects.create(i=1, j=1)
        with self.assertRaises(IntegrityError):
            IntegerUnique.objects.create(i=1, j=2)

    def test_rename(self):
        """
        Tests simple altering of fields
        """
        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        # Ensure the field is right to begin with
        columns = self.column_classes(Author)
        self.assertEqual(
            columns["name"][0],
            connection.features.introspected_field_types["CharField"],
        )
        self.assertNotIn("display_name", columns)
        # Alter the name field's name
        old_field = Author._meta.get_field("name")
        new_field = CharField(max_length=254)
        new_field.set_attributes_from_name("display_name")
        with connection.schema_editor() as editor:
            editor.alter_field(Author, old_field, new_field, strict=True)
        columns = self.column_classes(Author)
        self.assertEqual(
            columns["display_name"][0],
            connection.features.introspected_field_types["CharField"],
        )
        self.assertNotIn("name", columns)

    @isolate_apps("schema")
    def test_rename_referenced_field(self):
        """

        Tests the renaming of a field referenced by a foreign key.

        This test case covers the scenario where a field is renamed in a model,
        and that field is referenced by a foreign key in another model.
        It verifies that the foreign key is correctly updated to reference the new field name.

        The test creates two models, `Author` and `Book`, where `Book` has a foreign key to `Author`.
        It then renames the `name` field in `Author` to `renamed`, and checks that the foreign key in `Book` is updated accordingly.

        """
        class Author(Model):
            name = CharField(max_length=255, unique=True)

            class Meta:
                app_label = "schema"

        class Book(Model):
            author = ForeignKey(Author, CASCADE, to_field="name")

            class Meta:
                app_label = "schema"

        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(Book)
        new_field = CharField(max_length=255, unique=True)
        new_field.set_attributes_from_name("renamed")
        with connection.schema_editor() as editor:
            editor.alter_field(Author, Author._meta.get_field("name"), new_field)
        # Ensure the foreign key reference was updated.
        self.assertForeignKeyExists(Book, "author_id", "schema_author", "renamed")

    @skipIfDBFeature("interprets_empty_strings_as_nulls")
    def test_rename_keep_null_status(self):
        """
        Renaming a field shouldn't affect the not null status.
        """
        with connection.schema_editor() as editor:
            editor.create_model(Note)
        with self.assertRaises(IntegrityError):
            Note.objects.create(info=None)
        old_field = Note._meta.get_field("info")
        new_field = TextField()
        new_field.set_attributes_from_name("detail_info")
        with connection.schema_editor() as editor:
            editor.alter_field(Note, old_field, new_field, strict=True)
        columns = self.column_classes(Note)
        self.assertEqual(columns["detail_info"][0], "TextField")
        self.assertNotIn("info", columns)
        with self.assertRaises(IntegrityError):
            NoteRename.objects.create(detail_info=None)

    @isolate_apps("schema")
    def test_rename_keep_db_default(self):
        """Renaming a field shouldn't affect a database default."""

        class AuthorDbDefault(Model):
            birth_year = IntegerField(db_default=1985)

            class Meta:
                app_label = "schema"

        self.isolated_local_models = [AuthorDbDefault]
        with connection.schema_editor() as editor:
            editor.create_model(AuthorDbDefault)
        columns = self.column_classes(AuthorDbDefault)
        self.assertEqual(columns["birth_year"][1].default, "1985")

        old_field = AuthorDbDefault._meta.get_field("birth_year")
        new_field = IntegerField(db_default=1985)
        new_field.set_attributes_from_name("renamed_year")
        new_field.model = AuthorDbDefault
        with connection.schema_editor() as editor:
            editor.alter_field(AuthorDbDefault, old_field, new_field, strict=True)
        columns = self.column_classes(AuthorDbDefault)
        self.assertEqual(columns["renamed_year"][1].default, "1985")

    @isolate_apps("schema")
    def test_add_field_both_defaults_preserves_db_default(self):
        """
        Tests that adding a field with both Python default and database default values to a model preserves the database default value when creating the field in the database.

        The test case verifies that when a field is added to a model using the `add_field` method of a schema editor, and the field has both a default value defined in Python and a database default value, the database default value is used as the default value for the column in the database. This ensures that the database column is created with the correct default value, even if the Python default value is different.
        """
        class Author(Model):
            class Meta:
                app_label = "schema"

        with connection.schema_editor() as editor:
            editor.create_model(Author)

        field = IntegerField(default=1985, db_default=1988)
        field.set_attributes_from_name("birth_year")
        field.model = Author
        with connection.schema_editor() as editor:
            editor.add_field(Author, field)
        columns = self.column_classes(Author)
        self.assertEqual(columns["birth_year"][1].default, "1988")

    @isolate_apps("schema")
    def test_add_text_field_with_db_default(self):
        class Author(Model):
            description = TextField(db_default="(missing)")

            class Meta:
                app_label = "schema"

        with connection.schema_editor() as editor:
            editor.create_model(Author)
        columns = self.column_classes(Author)
        self.assertIn("(missing)", columns["description"][1].default)

    @isolate_apps("schema")
    def test_db_default_equivalent_sql_noop(self):
        class Author(Model):
            name = TextField(db_default=Value("foo"))

            class Meta:
                app_label = "schema"

        with connection.schema_editor() as editor:
            editor.create_model(Author)

        new_field = TextField(db_default="foo")
        new_field.set_attributes_from_name("name")
        new_field.model = Author
        with connection.schema_editor() as editor, self.assertNumQueries(0):
            editor.alter_field(Author, Author._meta.get_field("name"), new_field)

    @isolate_apps("schema")
    def test_db_default_output_field_resolving(self):
        """
        Tests that the default output field for a JSONField is correctly resolved in the database.

        This test case creates a model with a JSONField that has a default value, creates an instance of this model,
        and then checks that the default value is correctly stored in and retrieved from the database.

        The test ensures that the default value is resolved to the expected output format, which in this case is
        a string representation of a datetime object in ISO 8601 format.
        """
        class Author(Model):
            data = JSONField(
                encoder=DjangoJSONEncoder,
                db_default={
                    "epoch": datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
                },
            )

            class Meta:
                app_label = "schema"

        with connection.schema_editor() as editor:
            editor.create_model(Author)

        author = Author.objects.create()
        author.refresh_from_db()
        self.assertEqual(author.data, {"epoch": "1970-01-01T00:00:00Z"})

    @skipUnlessDBFeature(
        "supports_column_check_constraints", "can_introspect_check_constraints"
    )
    @isolate_apps("schema")
    def test_rename_field_with_check_to_truncated_name(self):
        class AuthorWithLongColumn(Model):
            field_with_very_looooooong_name = PositiveIntegerField(null=True)

            class Meta:
                app_label = "schema"

        self.isolated_local_models = [AuthorWithLongColumn]
        with connection.schema_editor() as editor:
            editor.create_model(AuthorWithLongColumn)
        old_field = AuthorWithLongColumn._meta.get_field(
            "field_with_very_looooooong_name"
        )
        new_field = PositiveIntegerField(null=True)
        new_field.set_attributes_from_name("renamed_field_with_very_long_name")
        with connection.schema_editor() as editor:
            editor.alter_field(AuthorWithLongColumn, old_field, new_field, strict=True)

        new_field_name = truncate_name(
            new_field.column, connection.ops.max_name_length()
        )
        constraints = self.get_constraints(AuthorWithLongColumn._meta.db_table)
        check_constraints = [
            name
            for name, details in constraints.items()
            if details["columns"] == [new_field_name] and details["check"]
        ]
        self.assertEqual(len(check_constraints), 1)

    def _test_m2m_create(self, M2MFieldClass):
        """
        Tests M2M fields on models during creation
        """

        class LocalBookWithM2M(Model):
            author = ForeignKey(Author, CASCADE)
            title = CharField(max_length=100, db_index=True)
            pub_date = DateTimeField()
            tags = M2MFieldClass("TagM2MTest", related_name="books")

            class Meta:
                app_label = "schema"
                apps = new_apps

        self.local_models = [LocalBookWithM2M]
        # Create the tables
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(TagM2MTest)
            editor.create_model(LocalBookWithM2M)
        # Ensure there is now an m2m table there
        columns = self.column_classes(
            LocalBookWithM2M._meta.get_field("tags").remote_field.through
        )
        self.assertEqual(
            columns["tagm2mtest_id"][0],
            connection.features.introspected_field_types["IntegerField"],
        )

    def test_m2m_create(self):
        self._test_m2m_create(ManyToManyField)

    def test_m2m_create_custom(self):
        self._test_m2m_create(CustomManyToManyField)

    def test_m2m_create_inherited(self):
        self._test_m2m_create(InheritedManyToManyField)

    def _test_m2m_create_through(self, M2MFieldClass):
        """
        Tests M2M fields on models during creation with through models
        """

        class LocalTagThrough(Model):
            book = ForeignKey("schema.LocalBookWithM2MThrough", CASCADE)
            tag = ForeignKey("schema.TagM2MTest", CASCADE)

            class Meta:
                app_label = "schema"
                apps = new_apps

        class LocalBookWithM2MThrough(Model):
            tags = M2MFieldClass(
                "TagM2MTest", related_name="books", through=LocalTagThrough
            )

            class Meta:
                app_label = "schema"
                apps = new_apps

        self.local_models = [LocalTagThrough, LocalBookWithM2MThrough]

        # Create the tables
        with connection.schema_editor() as editor:
            editor.create_model(LocalTagThrough)
            editor.create_model(TagM2MTest)
            editor.create_model(LocalBookWithM2MThrough)
        # Ensure there is now an m2m table there
        columns = self.column_classes(LocalTagThrough)
        self.assertEqual(
            columns["book_id"][0],
            connection.features.introspected_field_types["IntegerField"],
        )
        self.assertEqual(
            columns["tag_id"][0],
            connection.features.introspected_field_types["IntegerField"],
        )

    def test_m2m_create_through(self):
        self._test_m2m_create_through(ManyToManyField)

    def test_m2m_create_through_custom(self):
        self._test_m2m_create_through(CustomManyToManyField)

    def test_m2m_create_through_inherited(self):
        self._test_m2m_create_through(InheritedManyToManyField)

    def test_m2m_through_remove(self):
        class LocalAuthorNoteThrough(Model):
            book = ForeignKey("schema.Author", CASCADE)
            tag = ForeignKey("self", CASCADE)

            class Meta:
                app_label = "schema"
                apps = new_apps

        class LocalNoteWithM2MThrough(Model):
            authors = ManyToManyField("schema.Author", through=LocalAuthorNoteThrough)

            class Meta:
                app_label = "schema"
                apps = new_apps

        self.local_models = [LocalAuthorNoteThrough, LocalNoteWithM2MThrough]
        # Create the tables.
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(LocalAuthorNoteThrough)
            editor.create_model(LocalNoteWithM2MThrough)
        # Remove the through parameter.
        old_field = LocalNoteWithM2MThrough._meta.get_field("authors")
        new_field = ManyToManyField("Author")
        new_field.set_attributes_from_name("authors")
        msg = (
            f"Cannot alter field {old_field} into {new_field} - they are not "
            f"compatible types (you cannot alter to or from M2M fields, or add or "
            f"remove through= on M2M fields)"
        )
        with connection.schema_editor() as editor:
            with self.assertRaisesMessage(ValueError, msg):
                editor.alter_field(LocalNoteWithM2MThrough, old_field, new_field)

    def _test_m2m(self, M2MFieldClass):
        """
        Tests adding/removing M2M fields on models
        """

        class LocalAuthorWithM2M(Model):
            name = CharField(max_length=255)

            class Meta:
                app_label = "schema"
                apps = new_apps

        self.local_models = [LocalAuthorWithM2M]

        # Create the tables
        with connection.schema_editor() as editor:
            editor.create_model(LocalAuthorWithM2M)
            editor.create_model(TagM2MTest)
        # Create an M2M field
        new_field = M2MFieldClass("schema.TagM2MTest", related_name="authors")
        new_field.contribute_to_class(LocalAuthorWithM2M, "tags")
        # Ensure there's no m2m table there
        with self.assertRaises(DatabaseError):
            self.column_classes(new_field.remote_field.through)
        # Add the field
        with (
            CaptureQueriesContext(connection) as ctx,
            connection.schema_editor() as editor,
        ):
            editor.add_field(LocalAuthorWithM2M, new_field)
        # Table is not rebuilt.
        self.assertEqual(
            len(
                [
                    query["sql"]
                    for query in ctx.captured_queries
                    if "CREATE TABLE" in query["sql"]
                ]
            ),
            1,
        )
        self.assertIs(
            any("DROP TABLE" in query["sql"] for query in ctx.captured_queries),
            False,
        )
        # Ensure there is now an m2m table there
        columns = self.column_classes(new_field.remote_field.through)
        self.assertEqual(
            columns["tagm2mtest_id"][0],
            connection.features.introspected_field_types["IntegerField"],
        )

        # "Alter" the field. This should not rename the DB table to itself.
        with connection.schema_editor() as editor:
            editor.alter_field(LocalAuthorWithM2M, new_field, new_field, strict=True)

        # Remove the M2M table again
        with connection.schema_editor() as editor:
            editor.remove_field(LocalAuthorWithM2M, new_field)
        # Ensure there's no m2m table there
        with self.assertRaises(DatabaseError):
            self.column_classes(new_field.remote_field.through)

        # Make sure the model state is coherent with the table one now that
        # we've removed the tags field.
        opts = LocalAuthorWithM2M._meta
        opts.local_many_to_many.remove(new_field)
        del new_apps.all_models["schema"][
            new_field.remote_field.through._meta.model_name
        ]
        opts._expire_cache()

    def test_m2m(self):
        self._test_m2m(ManyToManyField)

    def test_m2m_custom(self):
        self._test_m2m(CustomManyToManyField)

    def test_m2m_inherited(self):
        self._test_m2m(InheritedManyToManyField)

    def _test_m2m_through_alter(self, M2MFieldClass):
        """
        Tests altering M2Ms with explicit through models (should no-op)
        """

        class LocalAuthorTag(Model):
            author = ForeignKey("schema.LocalAuthorWithM2MThrough", CASCADE)
            tag = ForeignKey("schema.TagM2MTest", CASCADE)

            class Meta:
                app_label = "schema"
                apps = new_apps

        class LocalAuthorWithM2MThrough(Model):
            name = CharField(max_length=255)
            tags = M2MFieldClass(
                "schema.TagM2MTest", related_name="authors", through=LocalAuthorTag
            )

            class Meta:
                app_label = "schema"
                apps = new_apps

        self.local_models = [LocalAuthorTag, LocalAuthorWithM2MThrough]

        # Create the tables
        with connection.schema_editor() as editor:
            editor.create_model(LocalAuthorTag)
            editor.create_model(LocalAuthorWithM2MThrough)
            editor.create_model(TagM2MTest)
        # Ensure the m2m table is there
        self.assertEqual(len(self.column_classes(LocalAuthorTag)), 3)
        # "Alter" the field's blankness. This should not actually do anything.
        old_field = LocalAuthorWithM2MThrough._meta.get_field("tags")
        new_field = M2MFieldClass(
            "schema.TagM2MTest", related_name="authors", through=LocalAuthorTag
        )
        new_field.contribute_to_class(LocalAuthorWithM2MThrough, "tags")
        with connection.schema_editor() as editor:
            editor.alter_field(
                LocalAuthorWithM2MThrough, old_field, new_field, strict=True
            )
        # Ensure the m2m table is still there
        self.assertEqual(len(self.column_classes(LocalAuthorTag)), 3)

    def test_m2m_through_alter(self):
        self._test_m2m_through_alter(ManyToManyField)

    def test_m2m_through_alter_custom(self):
        self._test_m2m_through_alter(CustomManyToManyField)

    def test_m2m_through_alter_inherited(self):
        self._test_m2m_through_alter(InheritedManyToManyField)

    def _test_m2m_repoint(self, M2MFieldClass):
        """
        Tests repointing M2M fields
        """

        class LocalBookWithM2M(Model):
            author = ForeignKey(Author, CASCADE)
            title = CharField(max_length=100, db_index=True)
            pub_date = DateTimeField()
            tags = M2MFieldClass("TagM2MTest", related_name="books")

            class Meta:
                app_label = "schema"
                apps = new_apps

        self.local_models = [LocalBookWithM2M]
        # Create the tables
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(LocalBookWithM2M)
            editor.create_model(TagM2MTest)
            editor.create_model(UniqueTest)
        # Ensure the M2M exists and points to TagM2MTest
        if connection.features.supports_foreign_keys:
            self.assertForeignKeyExists(
                LocalBookWithM2M._meta.get_field("tags").remote_field.through,
                "tagm2mtest_id",
                "schema_tagm2mtest",
            )
        # Repoint the M2M
        old_field = LocalBookWithM2M._meta.get_field("tags")
        new_field = M2MFieldClass(UniqueTest)
        new_field.contribute_to_class(LocalBookWithM2M, "uniques")
        with connection.schema_editor() as editor:
            editor.alter_field(LocalBookWithM2M, old_field, new_field, strict=True)
        # Ensure old M2M is gone
        with self.assertRaises(DatabaseError):
            self.column_classes(
                LocalBookWithM2M._meta.get_field("tags").remote_field.through
            )

        # This model looks like the new model and is used for teardown.
        opts = LocalBookWithM2M._meta
        opts.local_many_to_many.remove(old_field)
        # Ensure the new M2M exists and points to UniqueTest
        if connection.features.supports_foreign_keys:
            self.assertForeignKeyExists(
                new_field.remote_field.through, "uniquetest_id", "schema_uniquetest"
            )

    def test_m2m_repoint(self):
        self._test_m2m_repoint(ManyToManyField)

    def test_m2m_repoint_custom(self):
        self._test_m2m_repoint(CustomManyToManyField)

    def test_m2m_repoint_inherited(self):
        self._test_m2m_repoint(InheritedManyToManyField)

    @isolate_apps("schema")
    def test_m2m_rename_field_in_target_model(self):
        """

        Tests the renaming of a field in a target model of a many-to-many relationship.

        This test case checks if the field in the target model can be renamed without
        breaking the many-to-many relationship. It creates two local models, 
        LocalM2M and LocalTagM2MTest, where LocalM2M has a many-to-many field 
        'tags' referencing LocalTagM2MTest. The 'title' field in LocalTagM2MTest 
        is then renamed to 'title1', and the test asserts that the many-to-many 
        relationship remains intact.

        """
        class LocalTagM2MTest(Model):
            title = CharField(max_length=255)

            class Meta:
                app_label = "schema"

        class LocalM2M(Model):
            tags = ManyToManyField(LocalTagM2MTest)

            class Meta:
                app_label = "schema"

        # Create the tables.
        with connection.schema_editor() as editor:
            editor.create_model(LocalM2M)
            editor.create_model(LocalTagM2MTest)
        self.isolated_local_models = [LocalM2M, LocalTagM2MTest]
        # Ensure the m2m table is there.
        self.assertEqual(len(self.column_classes(LocalM2M)), 1)
        # Alter a field in LocalTagM2MTest.
        old_field = LocalTagM2MTest._meta.get_field("title")
        new_field = CharField(max_length=254)
        new_field.contribute_to_class(LocalTagM2MTest, "title1")
        # @isolate_apps() and inner models are needed to have the model
        # relations populated, otherwise this doesn't act as a regression test.
        self.assertEqual(len(new_field.model._meta.related_objects), 1)
        with connection.schema_editor() as editor:
            editor.alter_field(LocalTagM2MTest, old_field, new_field, strict=True)
        # Ensure the m2m table is still there.
        self.assertEqual(len(self.column_classes(LocalM2M)), 1)

    @skipUnlessDBFeature(
        "supports_column_check_constraints", "can_introspect_check_constraints"
    )
    def test_check_constraints(self):
        """
        Tests creating/deleting CHECK constraints
        """
        # Create the tables
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        # Ensure the constraint exists
        constraints = self.get_constraints(Author._meta.db_table)
        if not any(
            details["columns"] == ["height"] and details["check"]
            for details in constraints.values()
        ):
            self.fail("No check constraint for height found")
        # Alter the column to remove it
        old_field = Author._meta.get_field("height")
        new_field = IntegerField(null=True, blank=True)
        new_field.set_attributes_from_name("height")
        with connection.schema_editor() as editor:
            editor.alter_field(Author, old_field, new_field, strict=True)
        constraints = self.get_constraints(Author._meta.db_table)
        for details in constraints.values():
            if details["columns"] == ["height"] and details["check"]:
                self.fail("Check constraint for height found")
        # Alter the column to re-add it
        new_field2 = Author._meta.get_field("height")
        with connection.schema_editor() as editor:
            editor.alter_field(Author, new_field, new_field2, strict=True)
        constraints = self.get_constraints(Author._meta.db_table)
        if not any(
            details["columns"] == ["height"] and details["check"]
            for details in constraints.values()
        ):
            self.fail("No check constraint for height found")

    @skipUnlessDBFeature(
        "supports_column_check_constraints", "can_introspect_check_constraints"
    )
    @isolate_apps("schema")
    def test_check_constraint_timedelta_param(self):
        """

        Tests the creation and enforcement of a check constraint on a model field with a timedelta parameter.

        This test ensures that a check constraint can be successfully added to a model field to enforce a condition,
        in this case, that the duration is greater than 5 minutes. It also verifies that attempting to create an instance
        of the model with a duration that does not meet the condition raises an IntegrityError.

        The test covers the following scenarios:

        * Creating a model with a DurationField and adding a check constraint to it
        * Verifying that the constraint is successfully added to the database
        * Testing that creating an instance of the model with a valid duration is successful
        * Testing that creating an instance of the model with an invalid duration raises an IntegrityError

        """
        class DurationModel(Model):
            duration = DurationField()

            class Meta:
                app_label = "schema"

        with connection.schema_editor() as editor:
            editor.create_model(DurationModel)
        self.isolated_local_models = [DurationModel]
        constraint_name = "duration_gte_5_minutes"
        constraint = CheckConstraint(
            condition=Q(duration__gt=datetime.timedelta(minutes=5)),
            name=constraint_name,
        )
        DurationModel._meta.constraints = [constraint]
        with connection.schema_editor() as editor:
            editor.add_constraint(DurationModel, constraint)
        constraints = self.get_constraints(DurationModel._meta.db_table)
        self.assertIn(constraint_name, constraints)
        with self.assertRaises(IntegrityError), atomic():
            DurationModel.objects.create(duration=datetime.timedelta(minutes=4))
        DurationModel.objects.create(duration=datetime.timedelta(minutes=10))

    @skipUnlessDBFeature(
        "supports_column_check_constraints",
        "can_introspect_check_constraints",
        "supports_json_field",
    )
    @isolate_apps("schema")
    def test_check_constraint_exact_jsonfield(self):
        class JSONConstraintModel(Model):
            data = JSONField()

            class Meta:
                app_label = "schema"

        with connection.schema_editor() as editor:
            editor.create_model(JSONConstraintModel)
        self.isolated_local_models = [JSONConstraintModel]
        constraint_name = "check_only_stable_version"
        constraint = CheckConstraint(
            condition=Q(data__version="stable"),
            name=constraint_name,
        )
        JSONConstraintModel._meta.constraints = [constraint]
        with connection.schema_editor() as editor:
            editor.add_constraint(JSONConstraintModel, constraint)
        constraints = self.get_constraints(JSONConstraintModel._meta.db_table)
        self.assertIn(constraint_name, constraints)
        with self.assertRaises(IntegrityError), atomic():
            JSONConstraintModel.objects.create(
                data={"release": "5.0.2dev", "version": "dev"}
            )
        JSONConstraintModel.objects.create(
            data={"release": "5.0.3", "version": "stable"}
        )

    @skipUnlessDBFeature(
        "supports_column_check_constraints", "can_introspect_check_constraints"
    )
    def test_remove_field_check_does_not_remove_meta_constraints(self):
        """
        Tests that removing a field does not remove user-defined meta constraints.

        Checks that when a field is altered or removed, custom column check constraints
        added via model meta are preserved. This ensures that custom validation rules
        defined on model fields are not inadvertently deleted.

        The test verifies that custom constraints remain in place after:
        - Adding a custom check constraint to a model field
        - Altering the field's properties (e.g., making it nullable)
        - Reverting the field's properties back to their original state
        - Removing the custom check constraint via the model's meta
        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        # Add the custom check constraint
        constraint = CheckConstraint(
            condition=Q(height__gte=0), name="author_height_gte_0_check"
        )
        custom_constraint_name = constraint.name
        Author._meta.constraints = [constraint]
        with connection.schema_editor() as editor:
            editor.add_constraint(Author, constraint)
        # Ensure the constraints exist
        constraints = self.get_constraints(Author._meta.db_table)
        self.assertIn(custom_constraint_name, constraints)
        other_constraints = [
            name
            for name, details in constraints.items()
            if details["columns"] == ["height"]
            and details["check"]
            and name != custom_constraint_name
        ]
        self.assertEqual(len(other_constraints), 1)
        # Alter the column to remove field check
        old_field = Author._meta.get_field("height")
        new_field = IntegerField(null=True, blank=True)
        new_field.set_attributes_from_name("height")
        with connection.schema_editor() as editor:
            editor.alter_field(Author, old_field, new_field, strict=True)
        constraints = self.get_constraints(Author._meta.db_table)
        self.assertIn(custom_constraint_name, constraints)
        other_constraints = [
            name
            for name, details in constraints.items()
            if details["columns"] == ["height"]
            and details["check"]
            and name != custom_constraint_name
        ]
        self.assertEqual(len(other_constraints), 0)
        # Alter the column to re-add field check
        new_field2 = Author._meta.get_field("height")
        with connection.schema_editor() as editor:
            editor.alter_field(Author, new_field, new_field2, strict=True)
        constraints = self.get_constraints(Author._meta.db_table)
        self.assertIn(custom_constraint_name, constraints)
        other_constraints = [
            name
            for name, details in constraints.items()
            if details["columns"] == ["height"]
            and details["check"]
            and name != custom_constraint_name
        ]
        self.assertEqual(len(other_constraints), 1)
        # Drop the check constraint
        with connection.schema_editor() as editor:
            Author._meta.constraints = []
            editor.remove_constraint(Author, constraint)

    def test_unique(self):
        """
        Tests removing and adding unique constraints to a single column.
        """
        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(Tag)
        # Ensure the field is unique to begin with
        Tag.objects.create(title="foo", slug="foo")
        with self.assertRaises(IntegrityError):
            Tag.objects.create(title="bar", slug="foo")
        Tag.objects.all().delete()
        # Alter the slug field to be non-unique
        old_field = Tag._meta.get_field("slug")
        new_field = SlugField(unique=False)
        new_field.set_attributes_from_name("slug")
        with connection.schema_editor() as editor:
            editor.alter_field(Tag, old_field, new_field, strict=True)
        # Ensure the field is no longer unique
        Tag.objects.create(title="foo", slug="foo")
        Tag.objects.create(title="bar", slug="foo")
        Tag.objects.all().delete()
        # Alter the slug field to be unique
        new_field2 = SlugField(unique=True)
        new_field2.set_attributes_from_name("slug")
        with connection.schema_editor() as editor:
            editor.alter_field(Tag, new_field, new_field2, strict=True)
        # Ensure the field is unique again
        Tag.objects.create(title="foo", slug="foo")
        with self.assertRaises(IntegrityError):
            Tag.objects.create(title="bar", slug="foo")
        Tag.objects.all().delete()
        # Rename the field
        new_field3 = SlugField(unique=True)
        new_field3.set_attributes_from_name("slug2")
        with connection.schema_editor() as editor:
            editor.alter_field(Tag, new_field2, new_field3, strict=True)
        # Ensure the field is still unique
        TagUniqueRename.objects.create(title="foo", slug2="foo")
        with self.assertRaises(IntegrityError):
            TagUniqueRename.objects.create(title="bar", slug2="foo")
        Tag.objects.all().delete()

    def test_unique_name_quoting(self):
        """
        Tests that unique name quoting works correctly by simulating a database table rename operation.
        The function creates a test model, renames its database table, and then alters the unique_together constraint, 
        verifying that the unique name quoting mechanism handles these changes as expected. 
        Once the test is complete, the original table name is restored and the test model is deleted.
        """
        old_table_name = TagUniqueRename._meta.db_table
        try:
            with connection.schema_editor() as editor:
                editor.create_model(TagUniqueRename)
                editor.alter_db_table(TagUniqueRename, old_table_name, "unique-table")
                TagUniqueRename._meta.db_table = "unique-table"
                # This fails if the unique index name isn't quoted.
                editor.alter_unique_together(TagUniqueRename, [], (("title", "slug2"),))
        finally:
            with connection.schema_editor() as editor:
                editor.delete_model(TagUniqueRename)
            TagUniqueRename._meta.db_table = old_table_name

    @isolate_apps("schema")
    @skipUnlessDBFeature("supports_foreign_keys")
    def test_unique_no_unnecessary_fk_drops(self):
        """
        If AlterField isn't selective about dropping foreign key constraints
        when modifying a field with a unique constraint, the AlterField
        incorrectly drops and recreates the Book.author foreign key even though
        it doesn't restrict the field being changed (#29193).
        """

        class Author(Model):
            name = CharField(max_length=254, unique=True)

            class Meta:
                app_label = "schema"

        class Book(Model):
            author = ForeignKey(Author, CASCADE)

            class Meta:
                app_label = "schema"

        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(Book)
        new_field = CharField(max_length=255, unique=True)
        new_field.model = Author
        new_field.set_attributes_from_name("name")
        with self.assertLogs("django.db.backends.schema", "DEBUG") as cm:
            with connection.schema_editor() as editor:
                editor.alter_field(Author, Author._meta.get_field("name"), new_field)
        # One SQL statement is executed to alter the field.
        self.assertEqual(len(cm.records), 1)

    @isolate_apps("schema")
    def test_unique_and_reverse_m2m(self):
        """
        AlterField can modify a unique field when there's a reverse M2M
        relation on the model.
        """

        class Tag(Model):
            title = CharField(max_length=255)
            slug = SlugField(unique=True)

            class Meta:
                app_label = "schema"

        class Book(Model):
            tags = ManyToManyField(Tag, related_name="books")

            class Meta:
                app_label = "schema"

        self.isolated_local_models = [Book._meta.get_field("tags").remote_field.through]
        with connection.schema_editor() as editor:
            editor.create_model(Tag)
            editor.create_model(Book)
        new_field = SlugField(max_length=75, unique=True)
        new_field.model = Tag
        new_field.set_attributes_from_name("slug")
        with self.assertLogs("django.db.backends.schema", "DEBUG") as cm:
            with connection.schema_editor() as editor:
                editor.alter_field(Tag, Tag._meta.get_field("slug"), new_field)
        # One SQL statement is executed to alter the field.
        self.assertEqual(len(cm.records), 1)
        # Ensure that the field is still unique.
        Tag.objects.create(title="foo", slug="foo")
        with self.assertRaises(IntegrityError):
            Tag.objects.create(title="bar", slug="foo")

    def test_remove_ignored_unique_constraint_not_create_fk_index(self):
        """

        Checks that removing an ignored unique constraint with a conditional expression 
        does not create a foreign key index.

        This test case creates models for Author and Book, adds a unique constraint 
        to the Book model with a specific condition, and then removes the constraint.
        The assertion checks that the number of constraints after removal is correct, 
        depending on whether the database supports partial indexes.

        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(Book)
        constraint = UniqueConstraint(
            "author",
            condition=Q(title__in=["tHGttG", "tRatEotU"]),
            name="book_author_condition_uniq",
        )
        # Add unique constraint.
        with connection.schema_editor() as editor:
            editor.add_constraint(Book, constraint)
        old_constraints = self.get_constraints_for_column(
            Book,
            Book._meta.get_field("author").column,
        )
        # Remove unique constraint.
        with connection.schema_editor() as editor:
            editor.remove_constraint(Book, constraint)
        new_constraints = self.get_constraints_for_column(
            Book,
            Book._meta.get_field("author").column,
        )
        # Redundant foreign key index is not added.
        self.assertEqual(
            (
                len(old_constraints) - 1
                if connection.features.supports_partial_indexes
                else len(old_constraints)
            ),
            len(new_constraints),
        )

    @skipUnlessDBFeature("allows_multiple_constraints_on_same_fields")
    def test_remove_field_unique_does_not_remove_meta_constraints(self):
        """
        Tests if removing a unique field from a model does not inadvertently remove 
        meta constraints that have been manually defined for the same fields.

        Ensures that when a field with a unique constraint is altered, the 
        manually specified unique constraints on the same field are preserved. 

        Checks the database after altering the field to verify that the custom
        unique constraint still exists, while any automatically created unique 
        constraints on the same field are removed or preserved as expected.
        """
        with connection.schema_editor() as editor:
            editor.create_model(AuthorWithUniqueName)
        self.local_models = [AuthorWithUniqueName]
        # Add the custom unique constraint
        constraint = UniqueConstraint(fields=["name"], name="author_name_uniq")
        custom_constraint_name = constraint.name
        AuthorWithUniqueName._meta.constraints = [constraint]
        with connection.schema_editor() as editor:
            editor.add_constraint(AuthorWithUniqueName, constraint)
        # Ensure the constraints exist
        constraints = self.get_constraints(AuthorWithUniqueName._meta.db_table)
        self.assertIn(custom_constraint_name, constraints)
        other_constraints = [
            name
            for name, details in constraints.items()
            if details["columns"] == ["name"]
            and details["unique"]
            and name != custom_constraint_name
        ]
        self.assertEqual(len(other_constraints), 1)
        # Alter the column to remove field uniqueness
        old_field = AuthorWithUniqueName._meta.get_field("name")
        new_field = CharField(max_length=255)
        new_field.set_attributes_from_name("name")
        with connection.schema_editor() as editor:
            editor.alter_field(AuthorWithUniqueName, old_field, new_field, strict=True)
        constraints = self.get_constraints(AuthorWithUniqueName._meta.db_table)
        self.assertIn(custom_constraint_name, constraints)
        other_constraints = [
            name
            for name, details in constraints.items()
            if details["columns"] == ["name"]
            and details["unique"]
            and name != custom_constraint_name
        ]
        self.assertEqual(len(other_constraints), 0)
        # Alter the column to re-add field uniqueness
        new_field2 = AuthorWithUniqueName._meta.get_field("name")
        with connection.schema_editor() as editor:
            editor.alter_field(AuthorWithUniqueName, new_field, new_field2, strict=True)
        constraints = self.get_constraints(AuthorWithUniqueName._meta.db_table)
        self.assertIn(custom_constraint_name, constraints)
        other_constraints = [
            name
            for name, details in constraints.items()
            if details["columns"] == ["name"]
            and details["unique"]
            and name != custom_constraint_name
        ]
        self.assertEqual(len(other_constraints), 1)
        # Drop the unique constraint
        with connection.schema_editor() as editor:
            AuthorWithUniqueName._meta.constraints = []
            editor.remove_constraint(AuthorWithUniqueName, constraint)

    def test_unique_together(self):
        """
        Tests removing and adding unique_together constraints on a model.
        """
        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(UniqueTest)
        # Ensure the fields are unique to begin with
        UniqueTest.objects.create(year=2012, slug="foo")
        UniqueTest.objects.create(year=2011, slug="foo")
        UniqueTest.objects.create(year=2011, slug="bar")
        with self.assertRaises(IntegrityError):
            UniqueTest.objects.create(year=2012, slug="foo")
        UniqueTest.objects.all().delete()
        # Alter the model to its non-unique-together companion
        with connection.schema_editor() as editor:
            editor.alter_unique_together(
                UniqueTest, UniqueTest._meta.unique_together, []
            )
        # Ensure the fields are no longer unique
        UniqueTest.objects.create(year=2012, slug="foo")
        UniqueTest.objects.create(year=2012, slug="foo")
        UniqueTest.objects.all().delete()
        # Alter it back
        new_field2 = SlugField(unique=True)
        new_field2.set_attributes_from_name("slug")
        with connection.schema_editor() as editor:
            editor.alter_unique_together(
                UniqueTest, [], UniqueTest._meta.unique_together
            )
        # Ensure the fields are unique again
        UniqueTest.objects.create(year=2012, slug="foo")
        with self.assertRaises(IntegrityError):
            UniqueTest.objects.create(year=2012, slug="foo")
        UniqueTest.objects.all().delete()

    def test_unique_together_with_fk(self):
        """
        Tests removing and adding unique_together constraints that include
        a foreign key.
        """
        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(Book)
        # Ensure the fields are unique to begin with
        self.assertEqual(Book._meta.unique_together, ())
        # Add the unique_together constraint
        with connection.schema_editor() as editor:
            editor.alter_unique_together(Book, [], [["author", "title"]])
        # Alter it back
        with connection.schema_editor() as editor:
            editor.alter_unique_together(Book, [["author", "title"]], [])

    def test_unique_together_with_fk_with_existing_index(self):
        """
        Tests removing and adding unique_together constraints that include
        a foreign key, where the foreign key is added after the model is
        created.
        """
        # Create the tables
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(BookWithoutAuthor)
            new_field = ForeignKey(Author, CASCADE)
            new_field.set_attributes_from_name("author")
            editor.add_field(BookWithoutAuthor, new_field)
        # Ensure the fields aren't unique to begin with
        self.assertEqual(Book._meta.unique_together, ())
        # Add the unique_together constraint
        with connection.schema_editor() as editor:
            editor.alter_unique_together(Book, [], [["author", "title"]])
        # Alter it back
        with connection.schema_editor() as editor:
            editor.alter_unique_together(Book, [["author", "title"]], [])

    def _test_composed_index_with_fk(self, index):
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(Book)
        table = Book._meta.db_table
        self.assertEqual(Book._meta.indexes, [])
        Book._meta.indexes = [index]
        with connection.schema_editor() as editor:
            editor.add_index(Book, index)
        self.assertIn(index.name, self.get_constraints(table))
        Book._meta.indexes = []
        with connection.schema_editor() as editor:
            editor.remove_index(Book, index)
        self.assertNotIn(index.name, self.get_constraints(table))

    def test_composed_index_with_fk(self):
        """
        Tests a composed index that includes foreign key fields.

        This test case creates a composite index on 'author' and 'title' fields
        with the name 'book_author_title_idx', and then tests its functionality
        using the _test_composed_index_with_fk method.

        :raises: AssertionError if the composed index with foreign key does not work as expected
        """
        index = Index(fields=["author", "title"], name="book_author_title_idx")
        self._test_composed_index_with_fk(index)

    def test_composed_desc_index_with_fk(self):
        """
        Tests a composed index with a foreign key, specifically verifying the functionality of an index named 'book_author_title_idx' that is composed of the 'author' field in descending order and the 'title' field.
        """
        index = Index(fields=["-author", "title"], name="book_author_title_idx")
        self._test_composed_index_with_fk(index)

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_composed_func_index_with_fk(self):
        index = Index(F("author"), F("title"), name="book_author_title_idx")
        self._test_composed_index_with_fk(index)

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_composed_desc_func_index_with_fk(self):
        """

        Tests the creation and functionality of a composed index with a foreign key 
        that includes a descending function, particularly confirming support for 
        expression indexes.

        This test case verifies that an index can be successfully created with 
        a combination of a descending function and other fields, and that it 
        functions as expected in the presence of a foreign key.

        The test index includes fields for 'author' (in descending order) and 'title', 
        and is named 'book_author_title_idx'. The test evaluates the index's 
        behavior and ensures that it is properly utilized when querying the database.

        """
        index = Index(F("author").desc(), F("title"), name="book_author_title_idx")
        self._test_composed_index_with_fk(index)

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_composed_func_transform_index_with_fk(self):
        index = Index(F("title__lower"), name="book_title_lower_idx")
        with register_lookup(CharField, Lower):
            self._test_composed_index_with_fk(index)

    def _test_composed_constraint_with_fk(self, constraint):
        """

        Tests adding and removing a composed constraint with a foreign key to a model.

        Verifies that the constraint is successfully added to the model's table and then
        removed, by checking the constraint's presence in the table's constraints before
        and after the add and remove operations. This ensures that the constraint is
        properly installed and uninstalled in the database.

        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(Book)
        table = Book._meta.db_table
        self.assertEqual(Book._meta.constraints, [])
        Book._meta.constraints = [constraint]
        with connection.schema_editor() as editor:
            editor.add_constraint(Book, constraint)
        self.assertIn(constraint.name, self.get_constraints(table))
        Book._meta.constraints = []
        with connection.schema_editor() as editor:
            editor.remove_constraint(Book, constraint)
        self.assertNotIn(constraint.name, self.get_constraints(table))

    def test_composed_constraint_with_fk(self):
        constraint = UniqueConstraint(
            fields=["author", "title"],
            name="book_author_title_uniq",
        )
        self._test_composed_constraint_with_fk(constraint)

    @skipUnlessDBFeature(
        "supports_column_check_constraints", "can_introspect_check_constraints"
    )
    def test_composed_check_constraint_with_fk(self):
        constraint = CheckConstraint(
            condition=Q(author__gt=0), name="book_author_check"
        )
        self._test_composed_constraint_with_fk(constraint)

    @skipUnlessDBFeature("allows_multiple_constraints_on_same_fields")
    def test_remove_unique_together_does_not_remove_meta_constraints(self):
        """
        Tests that removing the unique_together meta option on a model does not remove any explicit UniqueConstraint instances that were previously applied to the model. This ensures that custom constraints are preserved when unique_together options are modified. The test creates a model with a unique constraint, checks that the constraint exists, removes the unique_together meta option, and then verifies that the custom constraint remains in place. It also checks that adding the unique_together meta option back to the model does not re-create any automatically generated constraints that were previously removed. Finally, it removes the custom constraint and verifies that it is properly deleted.
        """
        with connection.schema_editor() as editor:
            editor.create_model(AuthorWithUniqueNameAndBirthday)
        self.local_models = [AuthorWithUniqueNameAndBirthday]
        # Add the custom unique constraint
        constraint = UniqueConstraint(
            fields=["name", "birthday"], name="author_name_birthday_uniq"
        )
        custom_constraint_name = constraint.name
        AuthorWithUniqueNameAndBirthday._meta.constraints = [constraint]
        with connection.schema_editor() as editor:
            editor.add_constraint(AuthorWithUniqueNameAndBirthday, constraint)
        # Ensure the constraints exist
        constraints = self.get_constraints(
            AuthorWithUniqueNameAndBirthday._meta.db_table
        )
        self.assertIn(custom_constraint_name, constraints)
        other_constraints = [
            name
            for name, details in constraints.items()
            if details["columns"] == ["name", "birthday"]
            and details["unique"]
            and name != custom_constraint_name
        ]
        self.assertEqual(len(other_constraints), 1)
        # Remove unique together
        unique_together = AuthorWithUniqueNameAndBirthday._meta.unique_together
        with connection.schema_editor() as editor:
            editor.alter_unique_together(
                AuthorWithUniqueNameAndBirthday, unique_together, []
            )
        constraints = self.get_constraints(
            AuthorWithUniqueNameAndBirthday._meta.db_table
        )
        self.assertIn(custom_constraint_name, constraints)
        other_constraints = [
            name
            for name, details in constraints.items()
            if details["columns"] == ["name", "birthday"]
            and details["unique"]
            and name != custom_constraint_name
        ]
        self.assertEqual(len(other_constraints), 0)
        # Re-add unique together
        with connection.schema_editor() as editor:
            editor.alter_unique_together(
                AuthorWithUniqueNameAndBirthday, [], unique_together
            )
        constraints = self.get_constraints(
            AuthorWithUniqueNameAndBirthday._meta.db_table
        )
        self.assertIn(custom_constraint_name, constraints)
        other_constraints = [
            name
            for name, details in constraints.items()
            if details["columns"] == ["name", "birthday"]
            and details["unique"]
            and name != custom_constraint_name
        ]
        self.assertEqual(len(other_constraints), 1)
        # Drop the unique constraint
        with connection.schema_editor() as editor:
            AuthorWithUniqueNameAndBirthday._meta.constraints = []
            editor.remove_constraint(AuthorWithUniqueNameAndBirthday, constraint)

    def test_unique_constraint(self):
        """
        Test the creation and removal of a unique constraint on a model's field.

        This test case verifies that a unique constraint can be successfully added to and removed from a model's field, 
        ensuring data integrity by preventing duplicate values. It checks the generated SQL to confirm that it references 
        the correct table and column, and that the constraint is correctly removed after addition.

        The test involves creating a model, adding a unique constraint to one of its fields, and then removing the constraint.
        The expected outcomes are that the generated SQL correctly references the model's table and column, 
        and that the constraint is successfully added and then removed from the model's fields.
        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        constraint = UniqueConstraint(fields=["name"], name="name_uq")
        # Add constraint.
        with connection.schema_editor() as editor:
            editor.add_constraint(Author, constraint)
            sql = constraint.create_sql(Author, editor)
        table = Author._meta.db_table
        self.assertIs(sql.references_table(table), True)
        self.assertIs(sql.references_column(table, "name"), True)
        # Remove constraint.
        with connection.schema_editor() as editor:
            editor.remove_constraint(Author, constraint)
        self.assertNotIn(constraint.name, self.get_constraints(table))

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_func_unique_constraint(self):
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        constraint = UniqueConstraint(Upper("name").desc(), name="func_upper_uq")
        # Add constraint.
        with connection.schema_editor() as editor:
            editor.add_constraint(Author, constraint)
            sql = constraint.create_sql(Author, editor)
        table = Author._meta.db_table
        constraints = self.get_constraints(table)
        if connection.features.supports_index_column_ordering:
            self.assertIndexOrder(table, constraint.name, ["DESC"])
        self.assertIn(constraint.name, constraints)
        self.assertIs(constraints[constraint.name]["unique"], True)
        # SQL contains a database function.
        self.assertIs(sql.references_column(table, "name"), True)
        self.assertIn("UPPER(%s)" % editor.quote_name("name"), str(sql))
        # Remove constraint.
        with connection.schema_editor() as editor:
            editor.remove_constraint(Author, constraint)
        self.assertNotIn(constraint.name, self.get_constraints(table))

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_composite_func_unique_constraint(self):
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(BookWithSlug)
        constraint = UniqueConstraint(
            Upper("title"),
            Lower("slug"),
            name="func_upper_lower_unq",
        )
        # Add constraint.
        with connection.schema_editor() as editor:
            editor.add_constraint(BookWithSlug, constraint)
            sql = constraint.create_sql(BookWithSlug, editor)
        table = BookWithSlug._meta.db_table
        constraints = self.get_constraints(table)
        self.assertIn(constraint.name, constraints)
        self.assertIs(constraints[constraint.name]["unique"], True)
        # SQL contains database functions.
        self.assertIs(sql.references_column(table, "title"), True)
        self.assertIs(sql.references_column(table, "slug"), True)
        sql = str(sql)
        self.assertIn("UPPER(%s)" % editor.quote_name("title"), sql)
        self.assertIn("LOWER(%s)" % editor.quote_name("slug"), sql)
        self.assertLess(sql.index("UPPER"), sql.index("LOWER"))
        # Remove constraint.
        with connection.schema_editor() as editor:
            editor.remove_constraint(BookWithSlug, constraint)
        self.assertNotIn(constraint.name, self.get_constraints(table))

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_unique_constraint_field_and_expression(self):
        """

        Tests the creation and removal of a unique constraint on a model field and expressions.

        This test case ensures that a unique constraint can be successfully added to a model,
        with the constraint spanning multiple fields and database expressions, including
        ordering and function application. It verifies that the constraint is correctly
        applied to the model's database table, that the constraint's metadata is accurate,
        and that the constraint can be properly removed.

        The test covers the following scenarios:
        - Creating a unique constraint with field and expression references.
        - Verifying the constraint's ordering and uniqueness.
        - Checking the constraint's references to model fields and expressions.
        - Removing the constraint and verifying its deletion.

        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        constraint = UniqueConstraint(
            F("height").desc(),
            "uuid",
            Lower("name").asc(),
            name="func_f_lower_field_unq",
        )
        # Add constraint.
        with connection.schema_editor() as editor:
            editor.add_constraint(Author, constraint)
            sql = constraint.create_sql(Author, editor)
        table = Author._meta.db_table
        if connection.features.supports_index_column_ordering:
            self.assertIndexOrder(table, constraint.name, ["DESC", "ASC", "ASC"])
        constraints = self.get_constraints(table)
        self.assertIs(constraints[constraint.name]["unique"], True)
        self.assertEqual(len(constraints[constraint.name]["columns"]), 3)
        self.assertEqual(constraints[constraint.name]["columns"][1], "uuid")
        # SQL contains database functions and columns.
        self.assertIs(sql.references_column(table, "height"), True)
        self.assertIs(sql.references_column(table, "name"), True)
        self.assertIs(sql.references_column(table, "uuid"), True)
        self.assertIn("LOWER(%s)" % editor.quote_name("name"), str(sql))
        # Remove constraint.
        with connection.schema_editor() as editor:
            editor.remove_constraint(Author, constraint)
        self.assertNotIn(constraint.name, self.get_constraints(table))

    @skipUnlessDBFeature("supports_expression_indexes", "supports_partial_indexes")
    def test_func_unique_constraint_partial(self):
        """
        Tests the creation and removal of a unique constraint with a partial index.

        This test case verifies that a unique constraint with a functional index (in
        this case, the \"UPPER\" function) and a condition (in this case, a \"NOT NULL\"
        check on the \"weight\" column) can be successfully created and removed from a
        database table.

        The test checks that the constraint is properly added to the table,
        that the generated SQL references the correct columns, and that the constraint
        is enforced as expected. Finally, the test removes the constraint and verifies
        that it is no longer present in the table's constraints.

        Requires a database that supports expression indexes and partial indexes.
        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        constraint = UniqueConstraint(
            Upper("name"),
            name="func_upper_cond_weight_uq",
            condition=Q(weight__isnull=False),
        )
        # Add constraint.
        with connection.schema_editor() as editor:
            editor.add_constraint(Author, constraint)
            sql = constraint.create_sql(Author, editor)
        table = Author._meta.db_table
        constraints = self.get_constraints(table)
        self.assertIn(constraint.name, constraints)
        self.assertIs(constraints[constraint.name]["unique"], True)
        self.assertIs(sql.references_column(table, "name"), True)
        self.assertIn("UPPER(%s)" % editor.quote_name("name"), str(sql))
        self.assertIn(
            "WHERE %s IS NOT NULL" % editor.quote_name("weight"),
            str(sql),
        )
        # Remove constraint.
        with connection.schema_editor() as editor:
            editor.remove_constraint(Author, constraint)
        self.assertNotIn(constraint.name, self.get_constraints(table))

    @skipUnlessDBFeature("supports_expression_indexes", "supports_covering_indexes")
    def test_func_unique_constraint_covering(self):
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        constraint = UniqueConstraint(
            Upper("name"),
            name="func_upper_covering_uq",
            include=["weight", "height"],
        )
        # Add constraint.
        with connection.schema_editor() as editor:
            editor.add_constraint(Author, constraint)
            sql = constraint.create_sql(Author, editor)
        table = Author._meta.db_table
        constraints = self.get_constraints(table)
        self.assertIn(constraint.name, constraints)
        self.assertIs(constraints[constraint.name]["unique"], True)
        self.assertEqual(
            constraints[constraint.name]["columns"],
            [None, "weight", "height"],
        )
        self.assertIs(sql.references_column(table, "name"), True)
        self.assertIs(sql.references_column(table, "weight"), True)
        self.assertIs(sql.references_column(table, "height"), True)
        self.assertIn("UPPER(%s)" % editor.quote_name("name"), str(sql))
        self.assertIn(
            "INCLUDE (%s, %s)"
            % (
                editor.quote_name("weight"),
                editor.quote_name("height"),
            ),
            str(sql),
        )
        # Remove constraint.
        with connection.schema_editor() as editor:
            editor.remove_constraint(Author, constraint)
        self.assertNotIn(constraint.name, self.get_constraints(table))

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_func_unique_constraint_lookups(self):
        """

        Tests the creation, validation, and removal of a unique constraint with function-based lookups.

        This test case verifies that a unique constraint can be successfully applied to a model using
        lookup functions (in this case, 'Lower' and 'Abs') and that the constraint is properly enforced.
        It also checks that the constraint is correctly removed from the model.

        The test includes the following steps:

        * Creates a model and applies a unique constraint with function-based lookups.
        * Verifies that the constraint is applied and that the table's constraints include the unique constraint.
        * Checks that the SQL generated by the constraint references the correct columns.
        * Removes the constraint and verifies that it is no longer present in the table's constraints.

        This test ensures that the framework correctly handles unique constraints with function-based lookups.

        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        with register_lookup(CharField, Lower), register_lookup(IntegerField, Abs):
            constraint = UniqueConstraint(
                F("name__lower"),
                F("weight__abs"),
                name="func_lower_abs_lookup_uq",
            )
            # Add constraint.
            with connection.schema_editor() as editor:
                editor.add_constraint(Author, constraint)
                sql = constraint.create_sql(Author, editor)
            table = Author._meta.db_table
            constraints = self.get_constraints(table)
            self.assertIn(constraint.name, constraints)
            self.assertIs(constraints[constraint.name]["unique"], True)
            # SQL contains columns.
            self.assertIs(sql.references_column(table, "name"), True)
            self.assertIs(sql.references_column(table, "weight"), True)
            # Remove constraint.
            with connection.schema_editor() as editor:
                editor.remove_constraint(Author, constraint)
        self.assertNotIn(constraint.name, self.get_constraints(table))

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_func_unique_constraint_collate(self):
        """
        .. function:: test_func_unique_constraint_collate
            :noindex:

            Tests the creation and removal of a unique constraint that utilizes a database
            collation for case-insensitive comparison. The test covers the following scenarios:

            * Creation of a unique constraint with a custom collation.
            * Verification that the constraint is applied correctly to the model.
            * Removal of the constraint.

            This test requires a database backend that supports expression indexes and custom
            collations. If the backend does not support these features, the test will be skipped.
        """
        collation = connection.features.test_collations.get("non_default")
        if not collation:
            self.skipTest("This backend does not support case-insensitive collations.")
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(BookWithSlug)
        constraint = UniqueConstraint(
            Collate(F("title"), collation=collation).desc(),
            Collate("slug", collation=collation),
            name="func_collate_uq",
        )
        # Add constraint.
        with connection.schema_editor() as editor:
            editor.add_constraint(BookWithSlug, constraint)
            sql = constraint.create_sql(BookWithSlug, editor)
        table = BookWithSlug._meta.db_table
        constraints = self.get_constraints(table)
        self.assertIn(constraint.name, constraints)
        self.assertIs(constraints[constraint.name]["unique"], True)
        if connection.features.supports_index_column_ordering:
            self.assertIndexOrder(table, constraint.name, ["DESC", "ASC"])
        # SQL contains columns and a collation.
        self.assertIs(sql.references_column(table, "title"), True)
        self.assertIs(sql.references_column(table, "slug"), True)
        self.assertIn("COLLATE %s" % editor.quote_name(collation), str(sql))
        # Remove constraint.
        with connection.schema_editor() as editor:
            editor.remove_constraint(BookWithSlug, constraint)
        self.assertNotIn(constraint.name, self.get_constraints(table))

    @skipIfDBFeature("supports_expression_indexes")
    def test_func_unique_constraint_unsupported(self):
        # UniqueConstraint is ignored on databases that don't support indexes on
        # expressions.
        """

        Tests the functionality of adding and removing a unique constraint to a model 
        when the database does not support expression indexes.

        This test case creates an instance of the Author model and attempts to add 
        a unique constraint to the 'name' field. Since the underlying database does 
        not support expression indexes, the addition of the constraint is expected 
        to be a no-op. The test then proceeds to remove the constraint, also expected 
        to be a no-op.

        The test validates that both the add_constraint and remove_constraint methods 
        return None in this scenario, indicating that the operations were successfully 
        skipped without raising any errors or making any actual changes to the model 
        schema.

        The test also verifies that no database queries are executed during the 
        addition and removal of the constraint.

        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        constraint = UniqueConstraint(F("name"), name="func_name_uq")
        with connection.schema_editor() as editor, self.assertNumQueries(0):
            self.assertIsNone(editor.add_constraint(Author, constraint))
            self.assertIsNone(editor.remove_constraint(Author, constraint))

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_func_unique_constraint_nonexistent_field(self):
        """
        Tests adding a unique constraint with a non-existent field to a model.

        Verifies that attempting to create a unique constraint on a non-existent field
        raises a FieldError with a descriptive message, helping to prevent incorrect
        model configurations.

        The test case checks the error message to ensure it includes the expected
        choices of existing fields, providing useful feedback for model administrators.

        """
        constraint = UniqueConstraint(Lower("nonexistent"), name="func_nonexistent_uq")
        msg = (
            "Cannot resolve keyword 'nonexistent' into field. Choices are: "
            "height, id, name, uuid, weight"
        )
        with self.assertRaisesMessage(FieldError, msg):
            with connection.schema_editor() as editor:
                editor.add_constraint(Author, constraint)

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_func_unique_constraint_nondeterministic(self):
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        constraint = UniqueConstraint(Random(), name="func_random_uq")
        with connection.schema_editor() as editor:
            with self.assertRaises(DatabaseError):
                editor.add_constraint(Author, constraint)

    @skipUnlessDBFeature("supports_nulls_distinct_unique_constraints")
    def test_unique_constraint_index_nulls_distinct(self):
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        nulls_distinct = UniqueConstraint(
            F("height"), name="distinct_height", nulls_distinct=True
        )
        nulls_not_distinct = UniqueConstraint(
            F("weight"), name="not_distinct_weight", nulls_distinct=False
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(Author, nulls_distinct)
            editor.add_constraint(Author, nulls_not_distinct)
        Author.objects.create(name="", height=None, weight=None)
        Author.objects.create(name="", height=None, weight=1)
        with self.assertRaises(IntegrityError):
            Author.objects.create(name="", height=1, weight=None)
        with connection.schema_editor() as editor:
            editor.remove_constraint(Author, nulls_distinct)
            editor.remove_constraint(Author, nulls_not_distinct)
        constraints = self.get_constraints(Author._meta.db_table)
        self.assertNotIn(nulls_distinct.name, constraints)
        self.assertNotIn(nulls_not_distinct.name, constraints)

    @skipUnlessDBFeature("supports_nulls_distinct_unique_constraints")
    def test_unique_constraint_nulls_distinct(self):
        """
        Tests the creation and enforcement of a unique constraint with nulls not distinct.

        This test creates a unique constraint on a model's fields where null values are considered equal.
        It verifies that the constraint prevents duplicate rows with null values in the constrained fields.
        The test also ensures that the constraint is properly removed after it is no longer needed.

        The unique constraint is defined with the 'nulls_distinct=False' option, which means that null values will be considered as equal for the purposes of the uniqueness check.
        This test case requires a database that supports nulls distinct unique constraints, as indicated by the 'supports_nulls_distinct_unique_constraints' feature.

        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        constraint = UniqueConstraint(
            fields=["height", "weight"], name="constraint", nulls_distinct=False
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(Author, constraint)
        Author.objects.create(name="", height=None, weight=None)
        Author.objects.create(name="", height=1, weight=None)
        Author.objects.create(name="", height=None, weight=1)
        with self.assertRaises(IntegrityError):
            Author.objects.create(name="", height=None, weight=None)
        with self.assertRaises(IntegrityError):
            Author.objects.create(name="", height=1, weight=None)
        with self.assertRaises(IntegrityError):
            Author.objects.create(name="", height=None, weight=1)
        with connection.schema_editor() as editor:
            editor.remove_constraint(Author, constraint)
        constraints = self.get_constraints(Author._meta.db_table)
        self.assertNotIn(constraint.name, constraints)

    @skipUnlessDBFeature(
        "supports_nulls_distinct_unique_constraints",
        "supports_partial_indexes",
    )
    def test_unique_constraint_nulls_distinct_condition(self):
        """

        Tests the creation and application of a unique constraint with a condition,
        focusing on the behavior when null values are considered distinct.

        This test case covers the scenario where a unique constraint is applied to
        specific columns of a model, with a condition that filters the scope of the
        constraint. It verifies that the constraint is enforced correctly, including
        the handling of null values.

        The test involves creating a model instance with a unique constraint, then
        attempting to create additional instances that violate the constraint. It
        checks that an IntegrityError is raised when the constraint is violated, and
        that the constraint is properly removed when no longer needed.

        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        constraint = UniqueConstraint(
            fields=["height", "weight"],
            name="un_height_weight_start_A",
            condition=Q(name__startswith="A"),
            nulls_distinct=False,
        )
        with connection.schema_editor() as editor:
            editor.add_constraint(Author, constraint)
        Author.objects.create(name="Adam", height=None, weight=None)
        Author.objects.create(name="Avocado", height=1, weight=None)
        Author.objects.create(name="Adrian", height=None, weight=1)
        with self.assertRaises(IntegrityError):
            Author.objects.create(name="Alex", height=None, weight=None)
        Author.objects.create(name="Bob", height=None, weight=None)
        with self.assertRaises(IntegrityError):
            Author.objects.create(name="Alex", height=1, weight=None)
        Author.objects.create(name="Bill", height=None, weight=None)
        with self.assertRaises(IntegrityError):
            Author.objects.create(name="Alex", height=None, weight=1)
        Author.objects.create(name="Celine", height=None, weight=1)
        with connection.schema_editor() as editor:
            editor.remove_constraint(Author, constraint)
        constraints = self.get_constraints(Author._meta.db_table)
        self.assertNotIn(constraint.name, constraints)

    @skipIfDBFeature("supports_nulls_distinct_unique_constraints")
    def test_unique_constraint_nulls_distinct_unsupported(self):
        # UniqueConstraint is ignored on databases that don't support
        # NULLS [NOT] DISTINCT.
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        constraint = UniqueConstraint(
            F("name"), name="func_name_uq", nulls_distinct=True
        )
        with connection.schema_editor() as editor, self.assertNumQueries(0):
            self.assertIsNone(editor.add_constraint(Author, constraint))
            self.assertIsNone(editor.remove_constraint(Author, constraint))

    def test_index_together(self):
        """
        Tests removing and adding index_together constraints on a model.
        """
        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(Tag)
        # Ensure there's no index on the year/slug columns first
        self.assertIs(
            any(
                c["index"]
                for c in self.get_constraints("schema_tag").values()
                if c["columns"] == ["slug", "title"]
            ),
            False,
        )
        # Alter the model to add an index
        with connection.schema_editor() as editor:
            editor.alter_index_together(Tag, [], [("slug", "title")])
        # Ensure there is now an index
        self.assertIs(
            any(
                c["index"]
                for c in self.get_constraints("schema_tag").values()
                if c["columns"] == ["slug", "title"]
            ),
            True,
        )
        # Alter it back
        new_field2 = SlugField(unique=True)
        new_field2.set_attributes_from_name("slug")
        with connection.schema_editor() as editor:
            editor.alter_index_together(Tag, [("slug", "title")], [])
        # Ensure there's no index
        self.assertIs(
            any(
                c["index"]
                for c in self.get_constraints("schema_tag").values()
                if c["columns"] == ["slug", "title"]
            ),
            False,
        )

    @isolate_apps("schema")
    def test_db_table(self):
        """
        Tests renaming of the table
        """

        class Author(Model):
            name = CharField(max_length=255)

            class Meta:
                app_label = "schema"

        class Book(Model):
            author = ForeignKey(Author, CASCADE)

            class Meta:
                app_label = "schema"

        # Create the table and one referring it.
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(Book)
        # Ensure the table is there to begin with
        columns = self.column_classes(Author)
        self.assertEqual(
            columns["name"][0],
            connection.features.introspected_field_types["CharField"],
        )
        # Alter the table
        with connection.schema_editor() as editor:
            editor.alter_db_table(Author, "schema_author", "schema_otherauthor")
        Author._meta.db_table = "schema_otherauthor"
        columns = self.column_classes(Author)
        self.assertEqual(
            columns["name"][0],
            connection.features.introspected_field_types["CharField"],
        )
        # Ensure the foreign key reference was updated
        self.assertForeignKeyExists(Book, "author_id", "schema_otherauthor")
        # Alter the table again
        with connection.schema_editor() as editor:
            editor.alter_db_table(Author, "schema_otherauthor", "schema_author")
        # Ensure the table is still there
        Author._meta.db_table = "schema_author"
        columns = self.column_classes(Author)
        self.assertEqual(
            columns["name"][0],
            connection.features.introspected_field_types["CharField"],
        )

    def test_add_remove_index(self):
        """
        Tests index addition and removal
        """
        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        # Ensure the table is there and has no index
        self.assertNotIn("title", self.get_indexes(Author._meta.db_table))
        # Add the index
        index = Index(fields=["name"], name="author_title_idx")
        with connection.schema_editor() as editor:
            editor.add_index(Author, index)
        self.assertIn("name", self.get_indexes(Author._meta.db_table))
        # Drop the index
        with connection.schema_editor() as editor:
            editor.remove_index(Author, index)
        self.assertNotIn("name", self.get_indexes(Author._meta.db_table))

    def test_remove_db_index_doesnt_remove_custom_indexes(self):
        """
        Changing db_index to False doesn't remove indexes from Meta.indexes.
        """
        with connection.schema_editor() as editor:
            editor.create_model(AuthorWithIndexedName)
        self.local_models = [AuthorWithIndexedName]
        # Ensure the table has its index
        self.assertIn("name", self.get_indexes(AuthorWithIndexedName._meta.db_table))

        # Add the custom index
        index = Index(fields=["-name"], name="author_name_idx")
        author_index_name = index.name
        with connection.schema_editor() as editor:
            db_index_name = editor._create_index_name(
                table_name=AuthorWithIndexedName._meta.db_table,
                column_names=("name",),
            )
        try:
            AuthorWithIndexedName._meta.indexes = [index]
            with connection.schema_editor() as editor:
                editor.add_index(AuthorWithIndexedName, index)
            old_constraints = self.get_constraints(AuthorWithIndexedName._meta.db_table)
            self.assertIn(author_index_name, old_constraints)
            self.assertIn(db_index_name, old_constraints)
            # Change name field to db_index=False
            old_field = AuthorWithIndexedName._meta.get_field("name")
            new_field = CharField(max_length=255)
            new_field.set_attributes_from_name("name")
            with connection.schema_editor() as editor:
                editor.alter_field(
                    AuthorWithIndexedName, old_field, new_field, strict=True
                )
            new_constraints = self.get_constraints(AuthorWithIndexedName._meta.db_table)
            self.assertNotIn(db_index_name, new_constraints)
            # The index from Meta.indexes is still in the database.
            self.assertIn(author_index_name, new_constraints)
            # Drop the index
            with connection.schema_editor() as editor:
                editor.remove_index(AuthorWithIndexedName, index)
        finally:
            AuthorWithIndexedName._meta.indexes = []

    def test_order_index(self):
        """
        Indexes defined with ordering (ASC/DESC) defined on column
        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        # The table doesn't have an index
        self.assertNotIn("title", self.get_indexes(Author._meta.db_table))
        index_name = "author_name_idx"
        # Add the index
        index = Index(fields=["name", "-weight"], name=index_name)
        with connection.schema_editor() as editor:
            editor.add_index(Author, index)
        if connection.features.supports_index_column_ordering:
            self.assertIndexOrder(Author._meta.db_table, index_name, ["ASC", "DESC"])
        # Drop the index
        with connection.schema_editor() as editor:
            editor.remove_index(Author, index)

    def test_indexes(self):
        """
        Tests creation/altering of indexes
        """
        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(Book)
        # Ensure the table is there and has the right index
        self.assertIn(
            "title",
            self.get_indexes(Book._meta.db_table),
        )
        # Alter to remove the index
        old_field = Book._meta.get_field("title")
        new_field = CharField(max_length=100, db_index=False)
        new_field.set_attributes_from_name("title")
        with connection.schema_editor() as editor:
            editor.alter_field(Book, old_field, new_field, strict=True)
        # Ensure the table is there and has no index
        self.assertNotIn(
            "title",
            self.get_indexes(Book._meta.db_table),
        )
        # Alter to re-add the index
        new_field2 = Book._meta.get_field("title")
        with connection.schema_editor() as editor:
            editor.alter_field(Book, new_field, new_field2, strict=True)
        # Ensure the table is there and has the index again
        self.assertIn(
            "title",
            self.get_indexes(Book._meta.db_table),
        )
        # Add a unique column, verify that creates an implicit index
        new_field3 = BookWithSlug._meta.get_field("slug")
        with connection.schema_editor() as editor:
            editor.add_field(Book, new_field3)
        self.assertIn(
            "slug",
            self.get_uniques(Book._meta.db_table),
        )
        # Remove the unique, check the index goes with it
        new_field4 = CharField(max_length=20, unique=False)
        new_field4.set_attributes_from_name("slug")
        with connection.schema_editor() as editor:
            editor.alter_field(BookWithSlug, new_field3, new_field4, strict=True)
        self.assertNotIn(
            "slug",
            self.get_uniques(Book._meta.db_table),
        )

    def test_text_field_with_db_index(self):
        """
        Tests the creation of a text field with a database index.

        Verifies that a text field is correctly indexed in the database. The test checks
        if the 'text_field' is present in the database indexes if the database backend
        supports indexing on text fields, otherwise it checks that 'text_field' is not
        present in the database indexes.

        The test creates a model 'AuthorTextFieldWithIndex' using the schema editor and
        then retrieves the indexes for the model's database table to perform the assertion. 
        """
        with connection.schema_editor() as editor:
            editor.create_model(AuthorTextFieldWithIndex)
        # The text_field index is present if the database supports it.
        assertion = (
            self.assertIn
            if connection.features.supports_index_on_text_field
            else self.assertNotIn
        )
        assertion(
            "text_field", self.get_indexes(AuthorTextFieldWithIndex._meta.db_table)
        )

    def _index_expressions_wrappers(self):
        index_expression = IndexExpression()
        index_expression.set_wrapper_classes(connection)
        return ", ".join(
            [
                wrapper_cls.__qualname__
                for wrapper_cls in index_expression.wrapper_classes
            ]
        )

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_func_index_multiple_wrapper_references(self):
        index = Index(OrderBy(F("name").desc(), descending=True), name="name")
        msg = (
            "Multiple references to %s can't be used in an indexed expression."
            % self._index_expressions_wrappers()
        )
        with connection.schema_editor() as editor:
            with self.assertRaisesMessage(ValueError, msg):
                editor.add_index(Author, index)

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_func_index_invalid_topmost_expressions(self):
        index = Index(Upper(F("name").desc()), name="name")
        msg = (
            "%s must be topmost expressions in an indexed expression."
            % self._index_expressions_wrappers()
        )
        with connection.schema_editor() as editor:
            with self.assertRaisesMessage(ValueError, msg):
                editor.add_index(Author, index)

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_func_index(self):
        """

        Test that a functional index can be created on a model field.

        This test case verifies that a database index using a function (in this case, 
        the LOWER() function) can be successfully created and added to a model.

        It checks that the created index has the correct column ordering, that the 
        generated SQL references the correct column, and that the index is properly 
        removed after creation.

        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        index = Index(Lower("name").desc(), name="func_lower_idx")
        # Add index.
        with connection.schema_editor() as editor:
            editor.add_index(Author, index)
            sql = index.create_sql(Author, editor)
        table = Author._meta.db_table
        if connection.features.supports_index_column_ordering:
            self.assertIndexOrder(table, index.name, ["DESC"])
        # SQL contains a database function.
        self.assertIs(sql.references_column(table, "name"), True)
        self.assertIn("LOWER(%s)" % editor.quote_name("name"), str(sql))
        # Remove index.
        with connection.schema_editor() as editor:
            editor.remove_index(Author, index)
        self.assertNotIn(index.name, self.get_constraints(table))

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_func_index_f(self):
        """
        Tests the creation and removal of a functional index on a model field.

        This test case verifies that a functional index can be successfully added to a model,
        and that the index is properly referenced in the underlying database schema.
        It also checks that the index can be removed without leaving any remnants in the schema.

        The test covers the following scenarios:
        - Creation of a model with a functional index
        - Verification that the index exists in the database schema
        - Verification that the index references the correct columns
        - Removal of the index and verification that it no longer exists in the schema

        Note: This test is skipped unless the database backend supports expression indexes.
        """
        with connection.schema_editor() as editor:
            editor.create_model(Tag)
        index = Index("slug", F("title").desc(), name="func_f_idx")
        # Add index.
        with connection.schema_editor() as editor:
            editor.add_index(Tag, index)
            sql = index.create_sql(Tag, editor)
        table = Tag._meta.db_table
        self.assertIn(index.name, self.get_constraints(table))
        if connection.features.supports_index_column_ordering:
            self.assertIndexOrder(Tag._meta.db_table, index.name, ["ASC", "DESC"])
        # SQL contains columns.
        self.assertIs(sql.references_column(table, "slug"), True)
        self.assertIs(sql.references_column(table, "title"), True)
        # Remove index.
        with connection.schema_editor() as editor:
            editor.remove_index(Tag, index)
        self.assertNotIn(index.name, self.get_constraints(table))

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_func_index_lookups(self):
        """

        Tests the creation and usage of functional index lookups.

        This test case covers the scenario where an index is created on a model using
        functional lookups (in this case, Lower and Abs functions). It checks if the
        functional index is correctly added to the database, and if it references the
        expected columns.

        It also verifies that the index can be removed from the database, and that the
        database constraints are updated accordingly.

        The test uses the Author model as an example, creating a functional index on the
        name and weight fields, and then checking the resulting SQL and database state.

        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        with register_lookup(CharField, Lower), register_lookup(IntegerField, Abs):
            index = Index(
                F("name__lower"),
                F("weight__abs"),
                name="func_lower_abs_lookup_idx",
            )
            # Add index.
            with connection.schema_editor() as editor:
                editor.add_index(Author, index)
                sql = index.create_sql(Author, editor)
        table = Author._meta.db_table
        self.assertIn(index.name, self.get_constraints(table))
        # SQL contains columns.
        self.assertIs(sql.references_column(table, "name"), True)
        self.assertIs(sql.references_column(table, "weight"), True)
        # Remove index.
        with connection.schema_editor() as editor:
            editor.remove_index(Author, index)
        self.assertNotIn(index.name, self.get_constraints(table))

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_composite_func_index(self):
        """
        Tests the creation and removal of a composite index that uses database functions, specifically lower and upper case functions, on a model field. 

        The test checks if the index is successfully created, referenced in the SQL query, and removed. 

        It verifies that the index name is added to the list of constraints on the table, and that the SQL query generated to create the index contains the expected function calls. 

        The order of the functions in the SQL query is also checked to ensure it matches the order specified in the index definition. 

        After the index is removed, the test ensures that the index name is no longer in the list of constraints on the table.
        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        index = Index(Lower("name"), Upper("name"), name="func_lower_upper_idx")
        # Add index.
        with connection.schema_editor() as editor:
            editor.add_index(Author, index)
            sql = index.create_sql(Author, editor)
        table = Author._meta.db_table
        self.assertIn(index.name, self.get_constraints(table))
        # SQL contains database functions.
        self.assertIs(sql.references_column(table, "name"), True)
        sql = str(sql)
        self.assertIn("LOWER(%s)" % editor.quote_name("name"), sql)
        self.assertIn("UPPER(%s)" % editor.quote_name("name"), sql)
        self.assertLess(sql.index("LOWER"), sql.index("UPPER"))
        # Remove index.
        with connection.schema_editor() as editor:
            editor.remove_index(Author, index)
        self.assertNotIn(index.name, self.get_constraints(table))

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_composite_func_index_field_and_expression(self):
        """
        Tests the creation of a composite index on a model field and an expression.

        This test case covers the scenario where an index is created on a model that
        includes a combination of a field, an expression (e.g., a function applied to a
        field), and a normal field. The test verifies that the index is created correctly,
        with the correct column order and references to the underlying table columns.

        It checks the generated SQL for the correct syntax, including the use of a function
        (e.g., LOWER) on a field, and ensures that the index is properly removed after the
        test is completed.

        The test also takes into account the database feature support for index column
        ordering, and adjusts its assertions accordingly.
        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(Book)
        index = Index(
            F("author").desc(),
            Lower("title").asc(),
            "pub_date",
            name="func_f_lower_field_idx",
        )
        # Add index.
        with connection.schema_editor() as editor:
            editor.add_index(Book, index)
            sql = index.create_sql(Book, editor)
        table = Book._meta.db_table
        constraints = self.get_constraints(table)
        if connection.features.supports_index_column_ordering:
            self.assertIndexOrder(table, index.name, ["DESC", "ASC", "ASC"])
        self.assertEqual(len(constraints[index.name]["columns"]), 3)
        self.assertEqual(constraints[index.name]["columns"][2], "pub_date")
        # SQL contains database functions and columns.
        self.assertIs(sql.references_column(table, "author_id"), True)
        self.assertIs(sql.references_column(table, "title"), True)
        self.assertIs(sql.references_column(table, "pub_date"), True)
        self.assertIn("LOWER(%s)" % editor.quote_name("title"), str(sql))
        # Remove index.
        with connection.schema_editor() as editor:
            editor.remove_index(Book, index)
        self.assertNotIn(index.name, self.get_constraints(table))

    @skipUnlessDBFeature("supports_expression_indexes")
    @isolate_apps("schema")
    def test_func_index_f_decimalfield(self):
        """
        Tests the creation and removal of a functional index on a DecimalField.

        This test case checks that an index can be correctly created and added to a model
        using a DecimalField, and then subsequently removed. It verifies the index is
        listed in the table constraints and that the generated SQL references the
        correct column without unnecessary casting.

        The test also confirms that the index is properly removed from the table
        constraints after deletion.

        Note: This test requires a database backend that supports expression indexes.
        """
        class Node(Model):
            value = DecimalField(max_digits=5, decimal_places=2)

            class Meta:
                app_label = "schema"

        with connection.schema_editor() as editor:
            editor.create_model(Node)
        index = Index(F("value"), name="func_f_decimalfield_idx")
        # Add index.
        with connection.schema_editor() as editor:
            editor.add_index(Node, index)
            sql = index.create_sql(Node, editor)
        table = Node._meta.db_table
        self.assertIn(index.name, self.get_constraints(table))
        self.assertIs(sql.references_column(table, "value"), True)
        # SQL doesn't contain casting.
        self.assertNotIn("CAST", str(sql))
        # Remove index.
        with connection.schema_editor() as editor:
            editor.remove_index(Node, index)
        self.assertNotIn(index.name, self.get_constraints(table))

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_func_index_cast(self):
        """

         Tests the creation and removal of a function-based index with a cast operation.

         This test case verifies the support for creating an index based on a database function,
         specifically a cast operation, and then checks for its presence in the database schema.
         It also tests the removal of the created index and ensures it is no longer present in the schema.

         The test covers the following scenarios:
          - Successful creation of a function-based index with a cast operation
          - Verification of the index's presence in the database schema
          - Successful removal of the created index
          - Verification of the index's absence in the database schema after removal

        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        index = Index(Cast("weight", FloatField()), name="func_cast_idx")
        # Add index.
        with connection.schema_editor() as editor:
            editor.add_index(Author, index)
            sql = index.create_sql(Author, editor)
        table = Author._meta.db_table
        self.assertIn(index.name, self.get_constraints(table))
        self.assertIs(sql.references_column(table, "weight"), True)
        # Remove index.
        with connection.schema_editor() as editor:
            editor.remove_index(Author, index)
        self.assertNotIn(index.name, self.get_constraints(table))

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_func_index_collate(self):
        """

        Tests the creation and removal of a database index using a function-based collation.

        This test case creates a database index on the `title` and `slug` fields of the `BookWithSlug` model.
        The index uses a non-default collation, which is case-insensitive. It verifies that the index is correctly created,
        and that the collation is applied correctly. The test also checks that the index is removed successfully.

        The test requires a database backend that supports expression indexes and case-insensitive collations.

        """
        collation = connection.features.test_collations.get("non_default")
        if not collation:
            self.skipTest("This backend does not support case-insensitive collations.")
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(BookWithSlug)
        index = Index(
            Collate(F("title"), collation=collation).desc(),
            Collate("slug", collation=collation),
            name="func_collate_idx",
        )
        # Add index.
        with connection.schema_editor() as editor:
            editor.add_index(BookWithSlug, index)
            sql = index.create_sql(BookWithSlug, editor)
        table = Book._meta.db_table
        self.assertIn(index.name, self.get_constraints(table))
        if connection.features.supports_index_column_ordering:
            self.assertIndexOrder(table, index.name, ["DESC", "ASC"])
        # SQL contains columns and a collation.
        self.assertIs(sql.references_column(table, "title"), True)
        self.assertIs(sql.references_column(table, "slug"), True)
        self.assertIn("COLLATE %s" % editor.quote_name(collation), str(sql))
        # Remove index.
        with connection.schema_editor() as editor:
            editor.remove_index(Book, index)
        self.assertNotIn(index.name, self.get_constraints(table))

    @skipUnlessDBFeature("supports_expression_indexes")
    @skipIfDBFeature("collate_as_index_expression")
    def test_func_index_collate_f_ordered(self):
        """

        Tests the functionality of creating a database index with a collated function.

        This test case checks the creation, validation, and removal of a database index
        that utilizes a case-insensitive collation on a model field. It verifies that
        the index is correctly created, that the column ordering is properly set if
        supported by the database, and that the index references the correct column.
        The test also checks that the index is correctly removed after creation.

        """
        collation = connection.features.test_collations.get("non_default")
        if not collation:
            self.skipTest("This backend does not support case-insensitive collations.")
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        index = Index(
            Collate(F("name").desc(), collation=collation),
            name="func_collate_f_desc_idx",
        )
        # Add index.
        with connection.schema_editor() as editor:
            editor.add_index(Author, index)
            sql = index.create_sql(Author, editor)
        table = Author._meta.db_table
        self.assertIn(index.name, self.get_constraints(table))
        if connection.features.supports_index_column_ordering:
            self.assertIndexOrder(table, index.name, ["DESC"])
        # SQL contains columns and a collation.
        self.assertIs(sql.references_column(table, "name"), True)
        self.assertIn("COLLATE %s" % editor.quote_name(collation), str(sql))
        # Remove index.
        with connection.schema_editor() as editor:
            editor.remove_index(Author, index)
        self.assertNotIn(index.name, self.get_constraints(table))

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_func_index_calc(self):
        """

        Test creating and validating a functional index on a model.

        Verifies that a functional index with a custom calculation can be successfully
        created, added to a model, and properly referenced in the underlying SQL.
        Additionally, ensures the index is correctly removed and its existence is
        validated throughout the test process.

        Specifically, this test covers the creation of an index that calculates the
        result of a division operation involving model fields and a constant value.

        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        index = Index(F("height") / (F("weight") + Value(5)), name="func_calc_idx")
        # Add index.
        with connection.schema_editor() as editor:
            editor.add_index(Author, index)
            sql = index.create_sql(Author, editor)
        table = Author._meta.db_table
        self.assertIn(index.name, self.get_constraints(table))
        # SQL contains columns and expressions.
        self.assertIs(sql.references_column(table, "height"), True)
        self.assertIs(sql.references_column(table, "weight"), True)
        sql = str(sql)
        self.assertIs(
            sql.index(editor.quote_name("height"))
            < sql.index("/")
            < sql.index(editor.quote_name("weight"))
            < sql.index("+")
            < sql.index("5"),
            True,
        )
        # Remove index.
        with connection.schema_editor() as editor:
            editor.remove_index(Author, index)
        self.assertNotIn(index.name, self.get_constraints(table))

    @skipUnlessDBFeature("supports_expression_indexes", "supports_json_field")
    @isolate_apps("schema")
    def test_func_index_json_key_transform(self):
        """
        Tests the creation and removal of a functional index on a JSON field with a key transform.

        This test case ensures that a database index can be successfully added to a JSON field
        with a specific key transform and subsequently removed. It validates the index creation
        SQL and verifies that the index is properly added to and removed from the database table.

        The test creates a model with a JSON field, adds an index to the field with a key transform,
        and checks that the index is correctly created and referenced in the database schema.
        It then removes the index and confirms that it is no longer present in the schema.

        This test requires a database that supports expression indexes and JSON fields.

        """
        class JSONModel(Model):
            field = JSONField()

            class Meta:
                app_label = "schema"

        with connection.schema_editor() as editor:
            editor.create_model(JSONModel)
        self.isolated_local_models = [JSONModel]
        index = Index("field__some_key", name="func_json_key_idx")
        with connection.schema_editor() as editor:
            editor.add_index(JSONModel, index)
            sql = index.create_sql(JSONModel, editor)
        table = JSONModel._meta.db_table
        self.assertIn(index.name, self.get_constraints(table))
        self.assertIs(sql.references_column(table, "field"), True)
        with connection.schema_editor() as editor:
            editor.remove_index(JSONModel, index)
        self.assertNotIn(index.name, self.get_constraints(table))

    @skipUnlessDBFeature("supports_expression_indexes", "supports_json_field")
    @isolate_apps("schema")
    def test_func_index_json_key_transform_cast(self):
        class JSONModel(Model):
            field = JSONField()

            class Meta:
                app_label = "schema"

        with connection.schema_editor() as editor:
            editor.create_model(JSONModel)
        self.isolated_local_models = [JSONModel]
        index = Index(
            Cast(KeyTextTransform("some_key", "field"), IntegerField()),
            name="func_json_key_cast_idx",
        )
        with connection.schema_editor() as editor:
            editor.add_index(JSONModel, index)
            sql = index.create_sql(JSONModel, editor)
        table = JSONModel._meta.db_table
        self.assertIn(index.name, self.get_constraints(table))
        self.assertIs(sql.references_column(table, "field"), True)
        with connection.schema_editor() as editor:
            editor.remove_index(JSONModel, index)
        self.assertNotIn(index.name, self.get_constraints(table))

    @skipIfDBFeature("supports_expression_indexes")
    def test_func_index_unsupported(self):
        # Index is ignored on databases that don't support indexes on
        # expressions.
        """
        Skips test if the database supports expression indexes. Tests the behavior of 
        the schema editor when attempting to add and remove an index on a model, specifically 
        when the database does not support expression indexes. The test asserts that adding 
        and removing the index does not generate any database queries, and that the 
        operations return None when the index is not supported by the database.
        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        index = Index(F("name"), name="random_idx")
        with connection.schema_editor() as editor, self.assertNumQueries(0):
            self.assertIsNone(editor.add_index(Author, index))
            self.assertIsNone(editor.remove_index(Author, index))

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_func_index_nonexistent_field(self):
        index = Index(Lower("nonexistent"), name="func_nonexistent_idx")
        msg = (
            "Cannot resolve keyword 'nonexistent' into field. Choices are: "
            "height, id, name, uuid, weight"
        )
        with self.assertRaisesMessage(FieldError, msg):
            with connection.schema_editor() as editor:
                editor.add_index(Author, index)

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_func_index_nondeterministic(self):
        """
        Tests the creation of a functional index with a non-deterministic expression.

        This test case checks if the database correctly handles an attempt to create an index
        based on a non-deterministic function, specifically the 'Random' function.

        It verifies that a DatabaseError is raised when trying to add such an index to the 'Author' model.

        The test requires the database backend to support expression indexes.

        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        index = Index(Random(), name="func_random_idx")
        with connection.schema_editor() as editor:
            with self.assertRaises(DatabaseError):
                editor.add_index(Author, index)

    def test_primary_key(self):
        """
        Tests altering of the primary key
        """
        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(Tag)
        # Ensure the table is there and has the right PK
        self.assertEqual(self.get_primary_key(Tag._meta.db_table), "id")
        # Alter to change the PK
        id_field = Tag._meta.get_field("id")
        old_field = Tag._meta.get_field("slug")
        new_field = SlugField(primary_key=True)
        new_field.set_attributes_from_name("slug")
        new_field.model = Tag
        with connection.schema_editor() as editor:
            editor.remove_field(Tag, id_field)
            editor.alter_field(Tag, old_field, new_field)
        # Ensure the PK changed
        self.assertNotIn(
            "id",
            self.get_indexes(Tag._meta.db_table),
        )
        self.assertEqual(self.get_primary_key(Tag._meta.db_table), "slug")

    def test_alter_primary_key_the_same_name(self):
        """
        Tests altering a primary key field to have the same name.

        Verifies that the primary key attribute is correctly updated when a field 
        with the same name as the original primary key is used to replace it. The 
        test first creates the model and then swaps the primary key field with a 
        new one with the same name, verifying that the primary key is preserved. 
        The test then reverts the changes, swapping the fields back, and checks 
        that the primary key attribute remains unchanged. This test ensures that 
        the database schema is correctly updated when altering primary key fields 
        with the same name, maintaining data integrity and consistency.
        """
        with connection.schema_editor() as editor:
            editor.create_model(Thing)

        old_field = Thing._meta.get_field("when")
        new_field = CharField(max_length=2, primary_key=True)
        new_field.set_attributes_from_name("when")
        new_field.model = Thing
        with connection.schema_editor() as editor:
            editor.alter_field(Thing, old_field, new_field, strict=True)
        self.assertEqual(self.get_primary_key(Thing._meta.db_table), "when")
        with connection.schema_editor() as editor:
            editor.alter_field(Thing, new_field, old_field, strict=True)
        self.assertEqual(self.get_primary_key(Thing._meta.db_table), "when")

    def test_context_manager_exit(self):
        """
        Ensures transaction is correctly closed when an error occurs
        inside a SchemaEditor context.
        """

        class SomeError(Exception):
            pass

        try:
            with connection.schema_editor():
                raise SomeError
        except SomeError:
            self.assertFalse(connection.in_atomic_block)

    @skipIfDBFeature("can_rollback_ddl")
    def test_unsupported_transactional_ddl_disallowed(self):
        message = (
            "Executing DDL statements while in a transaction on databases "
            "that can't perform a rollback is prohibited."
        )
        with atomic(), connection.schema_editor() as editor:
            with self.assertRaisesMessage(TransactionManagementError, message):
                editor.execute(
                    editor.sql_create_table % {"table": "foo", "definition": ""}
                )

    @skipUnlessDBFeature("supports_foreign_keys", "indexes_foreign_keys")
    def test_foreign_key_index_long_names_regression(self):
        """
        Regression test for #21497.
        Only affects databases that supports foreign keys.
        """
        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(AuthorWithEvenLongerName)
            editor.create_model(BookWithLongName)
        # Find the properly shortened column name
        column_name = connection.ops.quote_name(
            "author_foreign_key_with_really_long_field_name_id"
        )
        column_name = column_name[1:-1].lower()  # unquote, and, for Oracle, un-upcase
        # Ensure the table is there and has an index on the column
        self.assertIn(
            column_name,
            self.get_indexes(BookWithLongName._meta.db_table),
        )

    @skipUnlessDBFeature("supports_foreign_keys")
    def test_add_foreign_key_long_names(self):
        """
        Regression test for #23009.
        Only affects databases that supports foreign keys.
        """
        # Create the initial tables
        with connection.schema_editor() as editor:
            editor.create_model(AuthorWithEvenLongerName)
            editor.create_model(BookWithLongName)
        # Add a second FK, this would fail due to long ref name before the fix
        new_field = ForeignKey(
            AuthorWithEvenLongerName, CASCADE, related_name="something"
        )
        new_field.set_attributes_from_name(
            "author_other_really_long_named_i_mean_so_long_fk"
        )
        with connection.schema_editor() as editor:
            editor.add_field(BookWithLongName, new_field)

    @isolate_apps("schema")
    @skipUnlessDBFeature("supports_foreign_keys")
    def test_add_foreign_key_quoted_db_table(self):
        """

        Tests the addition of a foreign key to a model where the database table name is quoted.

        This test ensures that a foreign key can be successfully created when the referenced
        database table has a name that is wrapped in double quotes. It verifies the existence
        of the foreign key constraint in the database, taking into account differences in how
        various database vendors handle quoted table names.

        The test covers the creation of two models, Author and Book, where Book has a foreign key
        to Author. It uses the connection's schema editor to create the models and then checks
        for the presence of the foreign key constraint.

        """
        class Author(Model):
            class Meta:
                db_table = '"table_author_double_quoted"'
                app_label = "schema"

        class Book(Model):
            author = ForeignKey(Author, CASCADE)

            class Meta:
                app_label = "schema"

        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(Book)
        self.isolated_local_models = [Author]
        if connection.vendor == "mysql":
            self.assertForeignKeyExists(
                Book, "author_id", '"table_author_double_quoted"'
            )
        else:
            self.assertForeignKeyExists(Book, "author_id", "table_author_double_quoted")

    def test_add_foreign_object(self):
        with connection.schema_editor() as editor:
            editor.create_model(BookForeignObj)
        self.local_models = [BookForeignObj]

        new_field = ForeignObject(
            Author, on_delete=CASCADE, from_fields=["author_id"], to_fields=["id"]
        )
        new_field.set_attributes_from_name("author")
        with connection.schema_editor() as editor:
            editor.add_field(BookForeignObj, new_field)

    def test_creation_deletion_reserved_names(self):
        """
        Tries creating a model's table, and then deleting it when it has a
        SQL reserved name.
        """
        # Create the table
        with connection.schema_editor() as editor:
            try:
                editor.create_model(Thing)
            except OperationalError as e:
                self.fail(
                    "Errors when applying initial migration for a model "
                    "with a table named after an SQL reserved word: %s" % e
                )
        # The table is there
        list(Thing.objects.all())
        # Clean up that table
        with connection.schema_editor() as editor:
            editor.delete_model(Thing)
        # The table is gone
        with self.assertRaises(DatabaseError):
            list(Thing.objects.all())

    def test_remove_constraints_capital_letters(self):
        """
        #23065 - Constraint names must be quoted if they contain capital letters.
        """

        def get_field(*args, field_class=IntegerField, **kwargs):
            kwargs["db_column"] = "CamelCase"
            field = field_class(*args, **kwargs)
            field.set_attributes_from_name("CamelCase")
            return field

        model = Author
        field = get_field()
        table = model._meta.db_table
        column = field.column
        identifier_converter = connection.introspection.identifier_converter

        with connection.schema_editor() as editor:
            editor.create_model(model)
            editor.add_field(model, field)

            constraint_name = "CamelCaseIndex"
            expected_constraint_name = identifier_converter(constraint_name)
            editor.execute(
                editor.sql_create_index
                % {
                    "table": editor.quote_name(table),
                    "name": editor.quote_name(constraint_name),
                    "using": "",
                    "columns": editor.quote_name(column),
                    "extra": "",
                    "condition": "",
                    "include": "",
                }
            )
            self.assertIn(
                expected_constraint_name, self.get_constraints(model._meta.db_table)
            )
            editor.alter_field(model, get_field(db_index=True), field, strict=True)
            self.assertNotIn(
                expected_constraint_name, self.get_constraints(model._meta.db_table)
            )

            constraint_name = "CamelCaseUniqConstraint"
            expected_constraint_name = identifier_converter(constraint_name)
            editor.execute(editor._create_unique_sql(model, [field], constraint_name))
            self.assertIn(
                expected_constraint_name, self.get_constraints(model._meta.db_table)
            )
            editor.alter_field(model, get_field(unique=True), field, strict=True)
            self.assertNotIn(
                expected_constraint_name, self.get_constraints(model._meta.db_table)
            )

            if editor.sql_create_fk and connection.features.can_introspect_foreign_keys:
                constraint_name = "CamelCaseFKConstraint"
                expected_constraint_name = identifier_converter(constraint_name)
                editor.execute(
                    editor.sql_create_fk
                    % {
                        "table": editor.quote_name(table),
                        "name": editor.quote_name(constraint_name),
                        "column": editor.quote_name(column),
                        "to_table": editor.quote_name(table),
                        "to_column": editor.quote_name(model._meta.auto_field.column),
                        "deferrable": connection.ops.deferrable_sql(),
                    }
                )
                self.assertIn(
                    expected_constraint_name, self.get_constraints(model._meta.db_table)
                )
                editor.alter_field(
                    model,
                    get_field(Author, CASCADE, field_class=ForeignKey),
                    field,
                    strict=True,
                )
                self.assertNotIn(
                    expected_constraint_name, self.get_constraints(model._meta.db_table)
                )

    def test_add_field_use_effective_default(self):
        """
        #23987 - effective_default() should be used as the field default when
        adding a new field.
        """
        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        # Ensure there's no surname field
        columns = self.column_classes(Author)
        self.assertNotIn("surname", columns)
        # Create a row
        Author.objects.create(name="Anonymous1")
        # Add new CharField to ensure default will be used from effective_default
        new_field = CharField(max_length=15, blank=True)
        new_field.set_attributes_from_name("surname")
        with connection.schema_editor() as editor:
            editor.add_field(Author, new_field)
        # Ensure field was added with the right default
        with connection.cursor() as cursor:
            cursor.execute("SELECT surname FROM schema_author;")
            item = cursor.fetchall()[0]
            self.assertEqual(
                item[0],
                None if connection.features.interprets_empty_strings_as_nulls else "",
            )

    def test_add_field_default_dropped(self):
        # Create the table
        """

        Tests adding a field to a model with a default value.

        This test case verifies that when a new field is added to an existing model, 
        the default value specified for the field is correctly applied to the existing 
        rows in the database table. It also checks that the default value is not 
        persisted in the database schema, in accordance with Django's behavior of 
        dropping default values when adding fields to existing tables.

        The test uses the Author model and adds a new CharField named 'surname' with 
        a default value. It then checks that the default value is correctly applied 
        to an existing row in the database table, and that the default value is not 
        introspected from the database schema.

        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        # Ensure there's no surname field
        columns = self.column_classes(Author)
        self.assertNotIn("surname", columns)
        # Create a row
        Author.objects.create(name="Anonymous1")
        # Add new CharField with a default
        new_field = CharField(max_length=15, blank=True, default="surname default")
        new_field.set_attributes_from_name("surname")
        with connection.schema_editor() as editor:
            editor.add_field(Author, new_field)
        # Ensure field was added with the right default
        with connection.cursor() as cursor:
            cursor.execute("SELECT surname FROM schema_author;")
            item = cursor.fetchall()[0]
            self.assertEqual(item[0], "surname default")
            # And that the default is no longer set in the database.
            field = next(
                f
                for f in connection.introspection.get_table_description(
                    cursor, "schema_author"
                )
                if f.name == "surname"
            )
            if connection.features.can_introspect_default:
                self.assertIsNone(field.default)

    def test_add_field_default_nullable(self):
        """

        Tests the addition of a new field to a model with default and nullable settings.

        Verifies that a new field with a default value and nullable set to True can be added
        to an existing model. The test checks that the field is successfully created with the
        correct attributes and that the default value is correctly set to None when an instance
        of the model is created without specifying a value for the new field. The test also
        verifies that the field's nullable property is correctly set and that the default value
        is correctly introspected from the database.

        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        # Add new nullable CharField with a default.
        new_field = CharField(max_length=15, blank=True, null=True, default="surname")
        new_field.set_attributes_from_name("surname")
        with connection.schema_editor() as editor:
            editor.add_field(Author, new_field)
        Author.objects.create(name="Anonymous1")
        with connection.cursor() as cursor:
            cursor.execute("SELECT surname FROM schema_author;")
            item = cursor.fetchall()[0]
            self.assertIsNone(item[0])
            field = next(
                f
                for f in connection.introspection.get_table_description(
                    cursor,
                    "schema_author",
                )
                if f.name == "surname"
            )
            # Field is still nullable.
            self.assertTrue(field.null_ok)
            # The database default is no longer set.
            if connection.features.can_introspect_default:
                self.assertIn(field.default, ["NULL", None])

    def test_add_textfield_default_nullable(self):
        """
        Tests the addition of a TextField to a model with default nullable settings.

        This test checks that when a TextField with blank=True, null=True, and a default
        value is added to a model, the field is created correctly in the database and
        behaves as expected. Specifically, it verifies that the field allows null values,
        and that the default value is correctly set to null when an instance of the model
        is created without specifying a value for the field.

        The test also checks the introspection capabilities of the database connection,
        ensuring that the field's nullability and default value are correctly reported.
        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        # Add new nullable TextField with a default.
        new_field = TextField(blank=True, null=True, default="text")
        new_field.set_attributes_from_name("description")
        with connection.schema_editor() as editor:
            editor.add_field(Author, new_field)
        Author.objects.create(name="Anonymous1")
        with connection.cursor() as cursor:
            cursor.execute("SELECT description FROM schema_author;")
            item = cursor.fetchall()[0]
            self.assertIsNone(item[0])
            field = next(
                f
                for f in connection.introspection.get_table_description(
                    cursor,
                    "schema_author",
                )
                if f.name == "description"
            )
            # Field is still nullable.
            self.assertTrue(field.null_ok)
            # The database default is no longer set.
            if connection.features.can_introspect_default:
                self.assertIn(field.default, ["NULL", None])

    def test_alter_field_default_dropped(self):
        # Create the table
        """
        Tests that altering a field to add a default value does not result in the default value being applied to existing rows.

        This test ensures that when a field without a default value is altered to have a default value, existing rows in the database table
        do not have this default value applied. The test also verifies that the database schema is updated correctly after the alteration.

        The test case covers the following scenarios:
        - Creating a model instance before altering the field
        - Altering the field to add a default value
        - Verifying that existing model instances do not have the default value applied
        - Verifying that the database schema reflects the changes made to the field
        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        # Create a row
        Author.objects.create(name="Anonymous1")
        self.assertIsNone(Author.objects.get().height)
        old_field = Author._meta.get_field("height")
        # The default from the new field is used in updating existing rows.
        new_field = IntegerField(blank=True, default=42)
        new_field.set_attributes_from_name("height")
        with connection.schema_editor() as editor:
            editor.alter_field(Author, old_field, new_field, strict=True)
        self.assertEqual(Author.objects.get().height, 42)
        # The database default should be removed.
        with connection.cursor() as cursor:
            field = next(
                f
                for f in connection.introspection.get_table_description(
                    cursor, "schema_author"
                )
                if f.name == "height"
            )
            if connection.features.can_introspect_default:
                self.assertIsNone(field.default)

    def test_alter_field_default_doesnt_perform_queries(self):
        """
        No queries are performed if a field default changes and the field's
        not changing from null to non-null.
        """
        with connection.schema_editor() as editor:
            editor.create_model(AuthorWithDefaultHeight)
        old_field = AuthorWithDefaultHeight._meta.get_field("height")
        new_default = old_field.default * 2
        new_field = PositiveIntegerField(null=True, blank=True, default=new_default)
        new_field.set_attributes_from_name("height")
        with connection.schema_editor() as editor, self.assertNumQueries(0):
            editor.alter_field(
                AuthorWithDefaultHeight, old_field, new_field, strict=True
            )

    @skipUnlessDBFeature("supports_foreign_keys")
    def test_alter_field_fk_attributes_noop(self):
        """
        No queries are performed when changing field attributes that don't
        affect the schema.
        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(Book)
        old_field = Book._meta.get_field("author")
        new_field = ForeignKey(
            Author,
            blank=True,
            editable=False,
            error_messages={"invalid": "error message"},
            help_text="help text",
            limit_choices_to={"limit": "choice"},
            on_delete=PROTECT,
            related_name="related_name",
            related_query_name="related_query_name",
            validators=[lambda x: x],
            verbose_name="verbose name",
        )
        new_field.set_attributes_from_name("author")
        with connection.schema_editor() as editor, self.assertNumQueries(0):
            editor.alter_field(Book, old_field, new_field, strict=True)
        with connection.schema_editor() as editor, self.assertNumQueries(0):
            editor.alter_field(Book, new_field, old_field, strict=True)

    def test_alter_field_choices_noop(self):
        """

        Tests that altering a field's choices does not result in any database operations when the underlying field type and attributes remain unchanged.

        This test case ensures that the schema editor correctly determines that no changes are needed when the field's choices are updated, but its type, name, and other attributes remain the same.

        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        old_field = Author._meta.get_field("name")
        new_field = CharField(
            choices=(("Jane", "Jane"), ("Joe", "Joe")),
            max_length=255,
        )
        new_field.set_attributes_from_name("name")
        with connection.schema_editor() as editor, self.assertNumQueries(0):
            editor.alter_field(Author, old_field, new_field, strict=True)
        with connection.schema_editor() as editor, self.assertNumQueries(0):
            editor.alter_field(Author, new_field, old_field, strict=True)

    def test_add_textfield_unhashable_default(self):
        # Create the table
        """
        Tests adding a text field with an unhashable default value to the Author model.

        This test creates an instance of the Author model, then attempts to add a new text field with a default value of an empty dictionary (an unhashable type). The test verifies that the addition of the text field is handled correctly, despite the default value being unhashable, which would normally cause issues in Django models. 

        The test covers the database schema modification and the creation of a new instance of the Author model with the added text field. 

        :raises: Any exception raised during the execution of the test, such as those related to database schema modifications or model instance creation.
        \"\"\"
        ```
        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        # Create a row
        Author.objects.create(name="Anonymous1")
        # Create a field that has an unhashable default
        new_field = TextField(default={})
        new_field.set_attributes_from_name("info")
        with connection.schema_editor() as editor:
            editor.add_field(Author, new_field)

    @unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific")
    def test_add_indexed_charfield(self):
        """

        Tests the addition of an indexed CharField to a model in a PostgreSQL database.

        This test case verifies that when a CharField with db_index=True is added to a model,
        the correct constraints are created in the database. Specifically, it checks for the
        presence of a btree index and a gist index for full-text search.

        The test scenario involves creating a model with the indexed CharField and then
        checking the constraints generated for the corresponding column in the database.

        """
        field = CharField(max_length=255, db_index=True)
        field.set_attributes_from_name("nom_de_plume")
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.add_field(Author, field)
        # Should create two indexes; one for like operator.
        self.assertEqual(
            self.get_constraints_for_column(Author, "nom_de_plume"),
            [
                "schema_author_nom_de_plume_7570a851",
                "schema_author_nom_de_plume_7570a851_like",
            ],
        )

    @unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific")
    def test_add_unique_charfield(self):
        """
        Tests the addition of a unique CharField to a model.

        This test case verifies that a CharField with the 'unique' constraint is correctly added to a model and that the resulting constraints are as expected.

        The test creates a CharField with a maximum length of 255 characters and sets it as unique. It then creates a model and adds the field to it using the schema editor. Finally, it checks that the constraints for the column are correctly set.

        The test is specific to PostgreSQL databases and is skipped if the connection vendor is not PostgreSQL.

        :raises: AssertionError if the constraints for the column are not as expected
        """
        field = CharField(max_length=255, unique=True)
        field.set_attributes_from_name("nom_de_plume")
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.add_field(Author, field)
        # Should create two indexes; one for like operator.
        self.assertEqual(
            self.get_constraints_for_column(Author, "nom_de_plume"),
            [
                "schema_author_nom_de_plume_7570a851_like",
                "schema_author_nom_de_plume_key",
            ],
        )

    @skipUnlessDBFeature("supports_comments")
    def test_add_db_comment_charfield(self):
        """
        Tests the ability to add a database comment to a CharField.

        This test case verifies that a custom comment can be successfully added to a CharField
        and stored in the database. It checks that the comment is correctly set and retrieved
        from the database column.

        The test covers the following scenario:
        - A CharField is created with a custom comment.
        - The field is added to a model using the schema editor.
        - The comment is verified to be correctly stored in the database column.

        """
        comment = "Custom comment"
        field = CharField(max_length=255, db_comment=comment)
        field.set_attributes_from_name("name_with_comment")
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.add_field(Author, field)
        self.assertEqual(
            self.get_column_comment(Author._meta.db_table, "name_with_comment"),
            comment,
        )

    @skipUnlessDBFeature("supports_comments")
    def test_add_db_comment_and_default_charfield(self):
        """
        Tests if a CharField with a custom database comment and default value can be added to a model. 

         The test checks the following conditions: 
         - The custom comment is correctly set for the field in the database.
         - The default value for the field is used when a new instance of the model is created without specifying a value for the field. 

         This test requires a database that supports comments, as indicated by the 'supports_comments' feature.
        """
        comment = "Custom comment with default"
        field = CharField(max_length=255, default="Joe Doe", db_comment=comment)
        field.set_attributes_from_name("name_with_comment_default")
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            Author.objects.create(name="Before adding a new field")
            editor.add_field(Author, field)

        self.assertEqual(
            self.get_column_comment(Author._meta.db_table, "name_with_comment_default"),
            comment,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT name_with_comment_default FROM {Author._meta.db_table};"
            )
            for row in cursor.fetchall():
                self.assertEqual(row[0], "Joe Doe")

    @skipUnlessDBFeature("supports_comments")
    def test_alter_db_comment(self):
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        # Add comment.
        old_field = Author._meta.get_field("name")
        new_field = CharField(max_length=255, db_comment="Custom comment")
        new_field.set_attributes_from_name("name")
        with connection.schema_editor() as editor:
            editor.alter_field(Author, old_field, new_field, strict=True)
        self.assertEqual(
            self.get_column_comment(Author._meta.db_table, "name"),
            "Custom comment",
        )
        # Alter comment.
        old_field = new_field
        new_field = CharField(max_length=255, db_comment="New custom comment")
        new_field.set_attributes_from_name("name")
        with connection.schema_editor() as editor:
            editor.alter_field(Author, old_field, new_field, strict=True)
        self.assertEqual(
            self.get_column_comment(Author._meta.db_table, "name"),
            "New custom comment",
        )
        # Remove comment.
        old_field = new_field
        new_field = CharField(max_length=255)
        new_field.set_attributes_from_name("name")
        with connection.schema_editor() as editor:
            editor.alter_field(Author, old_field, new_field, strict=True)
        self.assertIn(
            self.get_column_comment(Author._meta.db_table, "name"),
            [None, ""],
        )

    @skipUnlessDBFeature("supports_comments", "supports_foreign_keys")
    def test_alter_db_comment_foreign_key(self):
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(Book)

        comment = "FK custom comment"
        old_field = Book._meta.get_field("author")
        new_field = ForeignKey(Author, CASCADE, db_comment=comment)
        new_field.set_attributes_from_name("author")
        with connection.schema_editor() as editor:
            editor.alter_field(Book, old_field, new_field, strict=True)
        self.assertEqual(
            self.get_column_comment(Book._meta.db_table, "author_id"),
            comment,
        )

    @skipUnlessDBFeature("supports_comments")
    def test_alter_field_type_preserve_comment(self):
        with connection.schema_editor() as editor:
            editor.create_model(Author)

        comment = "This is the name."
        old_field = Author._meta.get_field("name")
        new_field = CharField(max_length=255, db_comment=comment)
        new_field.set_attributes_from_name("name")
        new_field.model = Author
        with connection.schema_editor() as editor:
            editor.alter_field(Author, old_field, new_field, strict=True)
        self.assertEqual(
            self.get_column_comment(Author._meta.db_table, "name"),
            comment,
        )
        # Changing a field type should preserve the comment.
        old_field = new_field
        new_field = CharField(max_length=511, db_comment=comment)
        new_field.set_attributes_from_name("name")
        new_field.model = Author
        with connection.schema_editor() as editor:
            editor.alter_field(Author, new_field, old_field, strict=True)
        # Comment is preserved.
        self.assertEqual(
            self.get_column_comment(Author._meta.db_table, "name"),
            comment,
        )

    @isolate_apps("schema")
    @skipUnlessDBFeature("supports_comments")
    def test_db_comment_table(self):
        class ModelWithDbTableComment(Model):
            class Meta:
                app_label = "schema"
                db_table_comment = "Custom table comment"

        with connection.schema_editor() as editor:
            editor.create_model(ModelWithDbTableComment)
        self.isolated_local_models = [ModelWithDbTableComment]
        self.assertEqual(
            self.get_table_comment(ModelWithDbTableComment._meta.db_table),
            "Custom table comment",
        )
        # Alter table comment.
        old_db_table_comment = ModelWithDbTableComment._meta.db_table_comment
        with connection.schema_editor() as editor:
            editor.alter_db_table_comment(
                ModelWithDbTableComment, old_db_table_comment, "New table comment"
            )
        self.assertEqual(
            self.get_table_comment(ModelWithDbTableComment._meta.db_table),
            "New table comment",
        )
        # Remove table comment.
        old_db_table_comment = ModelWithDbTableComment._meta.db_table_comment
        with connection.schema_editor() as editor:
            editor.alter_db_table_comment(
                ModelWithDbTableComment, old_db_table_comment, None
            )
        self.assertIn(
            self.get_table_comment(ModelWithDbTableComment._meta.db_table),
            [None, ""],
        )

    @isolate_apps("schema")
    @skipIfDBFeature("supports_comments")
    def test_db_comment_table_unsupported(self):
        """

        Tests creating a model with a custom database table comment on a database backend that does not support comments.

        Verifies that the model is created successfully with a single database query, and then checks that attempting to alter the table comment does not result in any additional queries, as the operation is not supported by the backend.

        """
        class ModelWithDbTableComment(Model):
            class Meta:
                app_label = "schema"
                db_table_comment = "Custom table comment"

        # Table comments are ignored on databases that don't support them.
        with connection.schema_editor() as editor, self.assertNumQueries(1):
            editor.create_model(ModelWithDbTableComment)
        self.isolated_local_models = [ModelWithDbTableComment]
        with connection.schema_editor() as editor, self.assertNumQueries(0):
            editor.alter_db_table_comment(
                ModelWithDbTableComment, "Custom table comment", "New table comment"
            )

    @isolate_apps("schema")
    @skipUnlessDBFeature("supports_comments", "supports_foreign_keys")
    def test_db_comments_from_abstract_model(self):
        """

        Tests the creation of database comments from an abstract model.

        This test case verifies that when an abstract model is used to create a concrete model,
        the database comments defined on the fields and tables of the abstract model are properly applied.

        The test checks that both column comments and table comments are correctly created in the database.

        """
        class AbstractModelWithDbComments(Model):
            name = CharField(
                max_length=255, db_comment="Custom comment", null=True, blank=True
            )

            class Meta:
                app_label = "schema"
                abstract = True
                db_table_comment = "Custom table comment"

        class ModelWithDbComments(AbstractModelWithDbComments):
            pass

        with connection.schema_editor() as editor:
            editor.create_model(ModelWithDbComments)
        self.isolated_local_models = [ModelWithDbComments]

        self.assertEqual(
            self.get_column_comment(ModelWithDbComments._meta.db_table, "name"),
            "Custom comment",
        )
        self.assertEqual(
            self.get_table_comment(ModelWithDbComments._meta.db_table),
            "Custom table comment",
        )

    @unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific")
    def test_alter_field_add_index_to_charfield(self):
        # Create the table and verify no initial indexes.
        """
        Tests the alteration of a model field to add an index to a CharField in a PostgreSQL database.

        This test ensures that adding a db_index to an existing CharField correctly creates the necessary index in the database,
        and that removing the db_index correctly removes the index. The test uses a model named Author with a field named 'name'
        to verify this behavior.

        It covers the following scenarios:
        - Initial state: Verify that no index exists for the 'name' field.
        - Altering the field to add an index: Verify that the index is created after altering the field.
        - Altering the field to remove the index: Verify that the index is removed after altering the field back to its original state.

        The test is PostgreSQL specific due to its reliance on PostgreSQL's indexing behavior.
        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        self.assertEqual(self.get_constraints_for_column(Author, "name"), [])
        # Alter to add db_index=True and create 2 indexes.
        old_field = Author._meta.get_field("name")
        new_field = CharField(max_length=255, db_index=True)
        new_field.set_attributes_from_name("name")
        with connection.schema_editor() as editor:
            editor.alter_field(Author, old_field, new_field, strict=True)
        self.assertEqual(
            self.get_constraints_for_column(Author, "name"),
            ["schema_author_name_1fbc5617", "schema_author_name_1fbc5617_like"],
        )
        # Remove db_index=True to drop both indexes.
        with connection.schema_editor() as editor:
            editor.alter_field(Author, new_field, old_field, strict=True)
        self.assertEqual(self.get_constraints_for_column(Author, "name"), [])

    @unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific")
    def test_alter_field_add_unique_to_charfield(self):
        # Create the table and verify no initial indexes.
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        self.assertEqual(self.get_constraints_for_column(Author, "name"), [])
        # Alter to add unique=True and create 2 indexes.
        old_field = Author._meta.get_field("name")
        new_field = CharField(max_length=255, unique=True)
        new_field.set_attributes_from_name("name")
        with connection.schema_editor() as editor:
            editor.alter_field(Author, old_field, new_field, strict=True)
        self.assertEqual(
            self.get_constraints_for_column(Author, "name"),
            ["schema_author_name_1fbc5617_like", "schema_author_name_1fbc5617_uniq"],
        )
        # Remove unique=True to drop both indexes.
        with connection.schema_editor() as editor:
            editor.alter_field(Author, new_field, old_field, strict=True)
        self.assertEqual(self.get_constraints_for_column(Author, "name"), [])

    @unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific")
    def test_alter_field_add_index_to_textfield(self):
        # Create the table and verify no initial indexes.
        with connection.schema_editor() as editor:
            editor.create_model(Note)
        self.assertEqual(self.get_constraints_for_column(Note, "info"), [])
        # Alter to add db_index=True and create 2 indexes.
        old_field = Note._meta.get_field("info")
        new_field = TextField(db_index=True)
        new_field.set_attributes_from_name("info")
        with connection.schema_editor() as editor:
            editor.alter_field(Note, old_field, new_field, strict=True)
        self.assertEqual(
            self.get_constraints_for_column(Note, "info"),
            ["schema_note_info_4b0ea695", "schema_note_info_4b0ea695_like"],
        )
        # Remove db_index=True to drop both indexes.
        with connection.schema_editor() as editor:
            editor.alter_field(Note, new_field, old_field, strict=True)
        self.assertEqual(self.get_constraints_for_column(Note, "info"), [])

    @unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific")
    def test_alter_field_add_unique_to_charfield_with_db_index(self):
        # Create the table and verify initial indexes.
        with connection.schema_editor() as editor:
            editor.create_model(BookWithoutAuthor)
        self.assertEqual(
            self.get_constraints_for_column(BookWithoutAuthor, "title"),
            ["schema_book_title_2dfb2dff", "schema_book_title_2dfb2dff_like"],
        )
        # Alter to add unique=True (should replace the index)
        old_field = BookWithoutAuthor._meta.get_field("title")
        new_field = CharField(max_length=100, db_index=True, unique=True)
        new_field.set_attributes_from_name("title")
        with connection.schema_editor() as editor:
            editor.alter_field(BookWithoutAuthor, old_field, new_field, strict=True)
        self.assertEqual(
            self.get_constraints_for_column(BookWithoutAuthor, "title"),
            ["schema_book_title_2dfb2dff_like", "schema_book_title_2dfb2dff_uniq"],
        )
        # Alter to remove unique=True (should drop unique index)
        new_field2 = CharField(max_length=100, db_index=True)
        new_field2.set_attributes_from_name("title")
        with connection.schema_editor() as editor:
            editor.alter_field(BookWithoutAuthor, new_field, new_field2, strict=True)
        self.assertEqual(
            self.get_constraints_for_column(BookWithoutAuthor, "title"),
            ["schema_book_title_2dfb2dff", "schema_book_title_2dfb2dff_like"],
        )

    @unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific")
    def test_alter_field_remove_unique_and_db_index_from_charfield(self):
        # Create the table and verify initial indexes.
        """
        Tests altering a CharField to remove its unique constraint and database index.

        This test case checks the process of modifying an existing CharField model field,
        specifically by altering its unique and db_index attributes. It first creates a
        model instance and verifies the initial constraints on the field. Then, it
        alters the field to add a unique constraint and db_index, and checks the updated
        constraints. Finally, it re-alters the field to remove these constraints and
        verifies that they are successfully removed from the database.

        This test is specific to PostgreSQL databases and ensures the correct behavior
        of Django's schema editor when modifying field attributes on this database
        backend.
        """
        with connection.schema_editor() as editor:
            editor.create_model(BookWithoutAuthor)
        self.assertEqual(
            self.get_constraints_for_column(BookWithoutAuthor, "title"),
            ["schema_book_title_2dfb2dff", "schema_book_title_2dfb2dff_like"],
        )
        # Alter to add unique=True (should replace the index)
        old_field = BookWithoutAuthor._meta.get_field("title")
        new_field = CharField(max_length=100, db_index=True, unique=True)
        new_field.set_attributes_from_name("title")
        with connection.schema_editor() as editor:
            editor.alter_field(BookWithoutAuthor, old_field, new_field, strict=True)
        self.assertEqual(
            self.get_constraints_for_column(BookWithoutAuthor, "title"),
            ["schema_book_title_2dfb2dff_like", "schema_book_title_2dfb2dff_uniq"],
        )
        # Alter to remove both unique=True and db_index=True (should drop all indexes)
        new_field2 = CharField(max_length=100)
        new_field2.set_attributes_from_name("title")
        with connection.schema_editor() as editor:
            editor.alter_field(BookWithoutAuthor, new_field, new_field2, strict=True)
        self.assertEqual(
            self.get_constraints_for_column(BookWithoutAuthor, "title"), []
        )

    @unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific")
    def test_alter_field_swap_unique_and_db_index_with_charfield(self):
        # Create the table and verify initial indexes.
        """

        Tests the alteration of a model field, swapping its unique and database index constraints.

        This test case specifically checks the scenario where a CharField is altered to have a unique constraint and then swapped back to have a database index.
        The test validates that the constraints are correctly updated in the database after each alteration.

        """
        with connection.schema_editor() as editor:
            editor.create_model(BookWithoutAuthor)
        self.assertEqual(
            self.get_constraints_for_column(BookWithoutAuthor, "title"),
            ["schema_book_title_2dfb2dff", "schema_book_title_2dfb2dff_like"],
        )
        # Alter to set unique=True and remove db_index=True (should replace the index)
        old_field = BookWithoutAuthor._meta.get_field("title")
        new_field = CharField(max_length=100, unique=True)
        new_field.set_attributes_from_name("title")
        with connection.schema_editor() as editor:
            editor.alter_field(BookWithoutAuthor, old_field, new_field, strict=True)
        self.assertEqual(
            self.get_constraints_for_column(BookWithoutAuthor, "title"),
            ["schema_book_title_2dfb2dff_like", "schema_book_title_2dfb2dff_uniq"],
        )
        # Alter to set db_index=True and remove unique=True (should restore index)
        new_field2 = CharField(max_length=100, db_index=True)
        new_field2.set_attributes_from_name("title")
        with connection.schema_editor() as editor:
            editor.alter_field(BookWithoutAuthor, new_field, new_field2, strict=True)
        self.assertEqual(
            self.get_constraints_for_column(BookWithoutAuthor, "title"),
            ["schema_book_title_2dfb2dff", "schema_book_title_2dfb2dff_like"],
        )

    @unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL specific")
    def test_alter_field_add_db_index_to_charfield_with_unique(self):
        # Create the table and verify initial indexes.
        with connection.schema_editor() as editor:
            editor.create_model(Tag)
        self.assertEqual(
            self.get_constraints_for_column(Tag, "slug"),
            ["schema_tag_slug_2c418ba3_like", "schema_tag_slug_key"],
        )
        # Alter to add db_index=True
        old_field = Tag._meta.get_field("slug")
        new_field = SlugField(db_index=True, unique=True)
        new_field.set_attributes_from_name("slug")
        with connection.schema_editor() as editor:
            editor.alter_field(Tag, old_field, new_field, strict=True)
        self.assertEqual(
            self.get_constraints_for_column(Tag, "slug"),
            ["schema_tag_slug_2c418ba3_like", "schema_tag_slug_key"],
        )
        # Alter to remove db_index=True
        new_field2 = SlugField(unique=True)
        new_field2.set_attributes_from_name("slug")
        with connection.schema_editor() as editor:
            editor.alter_field(Tag, new_field, new_field2, strict=True)
        self.assertEqual(
            self.get_constraints_for_column(Tag, "slug"),
            ["schema_tag_slug_2c418ba3_like", "schema_tag_slug_key"],
        )

    def test_alter_field_add_index_to_integerfield(self):
        # Create the table and verify no initial indexes.
        """
        .. function:: test_alter_field_add_index_to_integerfield

            Tests the addition and removal of an index on an IntegerField in a model.

            This test case verifies that an index can be successfully added to an existing IntegerField in a model, and then removed. It checks the constraints on the column before and after the index is added and removed, ensuring that the database schema is updated correctly. The test covers both the creation and reversal of the index operation.
        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        self.assertEqual(self.get_constraints_for_column(Author, "weight"), [])

        # Alter to add db_index=True and create index.
        old_field = Author._meta.get_field("weight")
        new_field = IntegerField(null=True, db_index=True)
        new_field.set_attributes_from_name("weight")
        with connection.schema_editor() as editor:
            editor.alter_field(Author, old_field, new_field, strict=True)
        self.assertEqual(
            self.get_constraints_for_column(Author, "weight"),
            ["schema_author_weight_587740f9"],
        )

        # Remove db_index=True to drop index.
        with connection.schema_editor() as editor:
            editor.alter_field(Author, new_field, old_field, strict=True)
        self.assertEqual(self.get_constraints_for_column(Author, "weight"), [])

    def test_alter_pk_with_self_referential_field(self):
        """
        Changing the primary key field name of a model with a self-referential
        foreign key (#26384).
        """
        with connection.schema_editor() as editor:
            editor.create_model(Node)
        old_field = Node._meta.get_field("node_id")
        new_field = AutoField(primary_key=True)
        new_field.set_attributes_from_name("id")
        with connection.schema_editor() as editor:
            editor.alter_field(Node, old_field, new_field, strict=True)
        self.assertForeignKeyExists(Node, "parent_id", Node._meta.db_table)

    @mock.patch("django.db.backends.base.schema.datetime")
    @mock.patch("django.db.backends.base.schema.timezone")
    def test_add_datefield_and_datetimefield_use_effective_default(
        self, mocked_datetime, mocked_tz
    ):
        """
        effective_default() should be used for DateField, DateTimeField, and
        TimeField if auto_now or auto_now_add is set (#25005).
        """
        now = datetime.datetime(month=1, day=1, year=2000, hour=1, minute=1)
        now_tz = datetime.datetime(
            month=1, day=1, year=2000, hour=1, minute=1, tzinfo=datetime.timezone.utc
        )
        mocked_datetime.now = mock.MagicMock(return_value=now)
        mocked_tz.now = mock.MagicMock(return_value=now_tz)
        # Create the table
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        # Check auto_now/auto_now_add attributes are not defined
        columns = self.column_classes(Author)
        self.assertNotIn("dob_auto_now", columns)
        self.assertNotIn("dob_auto_now_add", columns)
        self.assertNotIn("dtob_auto_now", columns)
        self.assertNotIn("dtob_auto_now_add", columns)
        self.assertNotIn("tob_auto_now", columns)
        self.assertNotIn("tob_auto_now_add", columns)
        # Create a row
        Author.objects.create(name="Anonymous1")
        # Ensure fields were added with the correct defaults
        dob_auto_now = DateField(auto_now=True)
        dob_auto_now.set_attributes_from_name("dob_auto_now")
        self.check_added_field_default(
            editor,
            Author,
            dob_auto_now,
            "dob_auto_now",
            now.date(),
            cast_function=lambda x: x.date(),
        )
        dob_auto_now_add = DateField(auto_now_add=True)
        dob_auto_now_add.set_attributes_from_name("dob_auto_now_add")
        self.check_added_field_default(
            editor,
            Author,
            dob_auto_now_add,
            "dob_auto_now_add",
            now.date(),
            cast_function=lambda x: x.date(),
        )
        dtob_auto_now = DateTimeField(auto_now=True)
        dtob_auto_now.set_attributes_from_name("dtob_auto_now")
        self.check_added_field_default(
            editor,
            Author,
            dtob_auto_now,
            "dtob_auto_now",
            now,
        )
        dt_tm_of_birth_auto_now_add = DateTimeField(auto_now_add=True)
        dt_tm_of_birth_auto_now_add.set_attributes_from_name("dtob_auto_now_add")
        self.check_added_field_default(
            editor,
            Author,
            dt_tm_of_birth_auto_now_add,
            "dtob_auto_now_add",
            now,
        )
        tob_auto_now = TimeField(auto_now=True)
        tob_auto_now.set_attributes_from_name("tob_auto_now")
        self.check_added_field_default(
            editor,
            Author,
            tob_auto_now,
            "tob_auto_now",
            now.time(),
            cast_function=lambda x: x.time(),
        )
        tob_auto_now_add = TimeField(auto_now_add=True)
        tob_auto_now_add.set_attributes_from_name("tob_auto_now_add")
        self.check_added_field_default(
            editor,
            Author,
            tob_auto_now_add,
            "tob_auto_now_add",
            now.time(),
            cast_function=lambda x: x.time(),
        )

    def test_namespaced_db_table_create_index_name(self):
        """
        Table names are stripped of their namespace/schema before being used to
        generate index names.
        """
        with connection.schema_editor() as editor:
            max_name_length = connection.ops.max_name_length() or 200
            namespace = "n" * max_name_length
            table_name = "t" * max_name_length
            namespaced_table_name = '"%s"."%s"' % (namespace, table_name)
            self.assertEqual(
                editor._create_index_name(table_name, []),
                editor._create_index_name(namespaced_table_name, []),
            )

    @unittest.skipUnless(
        connection.vendor == "oracle", "Oracle specific db_table syntax"
    )
    def test_creation_with_db_table_double_quotes(self):
        oracle_user = connection.creation._test_database_user()

        class Student(Model):
            name = CharField(max_length=30)

            class Meta:
                app_label = "schema"
                apps = new_apps
                db_table = '"%s"."DJANGO_STUDENT_TABLE"' % oracle_user

        class Document(Model):
            name = CharField(max_length=30)
            students = ManyToManyField(Student)

            class Meta:
                app_label = "schema"
                apps = new_apps
                db_table = '"%s"."DJANGO_DOCUMENT_TABLE"' % oracle_user

        self.isolated_local_models = [Student, Document]

        with connection.schema_editor() as editor:
            editor.create_model(Student)
            editor.create_model(Document)

        doc = Document.objects.create(name="Test Name")
        student = Student.objects.create(name="Some man")
        doc.students.add(student)

    @isolate_apps("schema")
    @unittest.skipUnless(
        connection.vendor == "postgresql", "PostgreSQL specific db_table syntax."
    )
    def test_namespaced_db_table_foreign_key_reference(self):
        with connection.cursor() as cursor:
            cursor.execute("CREATE SCHEMA django_schema_tests")

        def delete_schema():
            """
            \\":/cpu\\": Deletes the 'django_schema_tests' schema from the database, including all contained objects, tables, and relationships. This function is a one-step operation that effectively removes the entire schema and its dependencies, allowing for a fresh start or cleanup of the database.
            """
            with connection.cursor() as cursor:
                cursor.execute("DROP SCHEMA django_schema_tests CASCADE")

        self.addCleanup(delete_schema)

        class Author(Model):
            class Meta:
                app_label = "schema"

        class Book(Model):
            class Meta:
                app_label = "schema"
                db_table = '"django_schema_tests"."schema_book"'

        author = ForeignKey(Author, CASCADE)
        author.set_attributes_from_name("author")

        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(Book)
            editor.add_field(Book, author)

    def test_rename_table_renames_deferred_sql_references(self):
        """

        Tests that renaming a table updates deferred SQL references.

        This test case creates two models, Author and Book, and renames their tables.
        It then verifies that the deferred SQL statements no longer reference the original table names.
        The test ensures that the deferred SQL is updated correctly after a table rename operation.

        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(Book)
            editor.alter_db_table(Author, "schema_author", "schema_renamed_author")
            editor.alter_db_table(Author, "schema_book", "schema_renamed_book")
            try:
                self.assertGreater(len(editor.deferred_sql), 0)
                for statement in editor.deferred_sql:
                    self.assertIs(statement.references_table("schema_author"), False)
                    self.assertIs(statement.references_table("schema_book"), False)
            finally:
                editor.alter_db_table(Author, "schema_renamed_author", "schema_author")
                editor.alter_db_table(Author, "schema_renamed_book", "schema_book")

    def test_rename_column_renames_deferred_sql_references(self):
        """

        Tests that renaming a column in a model also updates any deferred SQL references.

        Checks that after renaming columns in the Book model, any deferred SQL statements
        generated by the schema editor no longer reference the old column names. This
        ensures that the renamed columns are correctly reflected in any subsequent SQL
        operations. The test specifically verifies that the 'title' and 'author' columns
        are correctly renamed to 'renamed_title' and 'renamed_author' respectively, and
        that the deferred SQL statements do not reference the old column names.

        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(Book)
            old_title = Book._meta.get_field("title")
            new_title = CharField(max_length=100, db_index=True)
            new_title.set_attributes_from_name("renamed_title")
            editor.alter_field(Book, old_title, new_title)
            old_author = Book._meta.get_field("author")
            new_author = ForeignKey(Author, CASCADE)
            new_author.set_attributes_from_name("renamed_author")
            editor.alter_field(Book, old_author, new_author)
            self.assertGreater(len(editor.deferred_sql), 0)
            for statement in editor.deferred_sql:
                self.assertIs(statement.references_column("book", "title"), False)
                self.assertIs(statement.references_column("book", "author_id"), False)

    @isolate_apps("schema")
    def test_referenced_field_without_constraint_rename_inside_atomic_block(self):
        """
        Foreign keys without database level constraint don't prevent the field
        they reference from being renamed in an atomic block.
        """

        class Foo(Model):
            field = CharField(max_length=255, unique=True)

            class Meta:
                app_label = "schema"

        class Bar(Model):
            foo = ForeignKey(Foo, CASCADE, to_field="field", db_constraint=False)

            class Meta:
                app_label = "schema"

        self.isolated_local_models = [Foo, Bar]
        with connection.schema_editor() as editor:
            editor.create_model(Foo)
            editor.create_model(Bar)

        new_field = CharField(max_length=255, unique=True)
        new_field.set_attributes_from_name("renamed")
        with connection.schema_editor(atomic=True) as editor:
            editor.alter_field(Foo, Foo._meta.get_field("field"), new_field)

    @isolate_apps("schema")
    def test_referenced_table_without_constraint_rename_inside_atomic_block(self):
        """
        Foreign keys without database level constraint don't prevent the table
        they reference from being renamed in an atomic block.
        """

        class Foo(Model):
            field = CharField(max_length=255, unique=True)

            class Meta:
                app_label = "schema"

        class Bar(Model):
            foo = ForeignKey(Foo, CASCADE, to_field="field", db_constraint=False)

            class Meta:
                app_label = "schema"

        self.isolated_local_models = [Foo, Bar]
        with connection.schema_editor() as editor:
            editor.create_model(Foo)
            editor.create_model(Bar)

        new_field = CharField(max_length=255, unique=True)
        new_field.set_attributes_from_name("renamed")
        with connection.schema_editor(atomic=True) as editor:
            editor.alter_db_table(Foo, Foo._meta.db_table, "renamed_table")
        Foo._meta.db_table = "renamed_table"

    @isolate_apps("schema")
    @skipUnlessDBFeature("supports_collation_on_charfield")
    def test_db_collation_charfield(self):
        collation = connection.features.test_collations.get("non_default")
        if not collation:
            self.skipTest("Language collations are not supported.")

        class Foo(Model):
            field = CharField(max_length=255, db_collation=collation)

            class Meta:
                app_label = "schema"

        self.isolated_local_models = [Foo]
        with connection.schema_editor() as editor:
            editor.create_model(Foo)

        self.assertEqual(
            self.get_column_collation(Foo._meta.db_table, "field"),
            collation,
        )

    @isolate_apps("schema")
    @skipUnlessDBFeature("supports_collation_on_textfield")
    def test_db_collation_textfield(self):
        collation = connection.features.test_collations.get("non_default")
        if not collation:
            self.skipTest("Language collations are not supported.")

        class Foo(Model):
            field = TextField(db_collation=collation)

            class Meta:
                app_label = "schema"

        self.isolated_local_models = [Foo]
        with connection.schema_editor() as editor:
            editor.create_model(Foo)

        self.assertEqual(
            self.get_column_collation(Foo._meta.db_table, "field"),
            collation,
        )

    @skipUnlessDBFeature("supports_collation_on_charfield")
    def test_add_field_db_collation(self):
        collation = connection.features.test_collations.get("non_default")
        if not collation:
            self.skipTest("Language collations are not supported.")

        with connection.schema_editor() as editor:
            editor.create_model(Author)

        new_field = CharField(max_length=255, db_collation=collation)
        new_field.set_attributes_from_name("alias")
        with connection.schema_editor() as editor:
            editor.add_field(Author, new_field)
        columns = self.column_classes(Author)
        self.assertEqual(
            columns["alias"][0],
            connection.features.introspected_field_types["CharField"],
        )
        self.assertEqual(columns["alias"][1][8], collation)

    @skipUnlessDBFeature("supports_collation_on_charfield")
    def test_alter_field_db_collation(self):
        collation = connection.features.test_collations.get("non_default")
        if not collation:
            self.skipTest("Language collations are not supported.")

        with connection.schema_editor() as editor:
            editor.create_model(Author)

        old_field = Author._meta.get_field("name")
        new_field = CharField(max_length=255, db_collation=collation)
        new_field.set_attributes_from_name("name")
        new_field.model = Author
        with connection.schema_editor() as editor:
            editor.alter_field(Author, old_field, new_field, strict=True)
        self.assertEqual(
            self.get_column_collation(Author._meta.db_table, "name"),
            collation,
        )
        with connection.schema_editor() as editor:
            editor.alter_field(Author, new_field, old_field, strict=True)
        self.assertIsNone(self.get_column_collation(Author._meta.db_table, "name"))

    @skipUnlessDBFeature("supports_collation_on_charfield")
    def test_alter_field_type_preserve_db_collation(self):
        """
        Test that altering a CharField's type preserves the database collation.

        This test ensures that when the type of a CharField is altered, the collation
        defined in the database is maintained. It checks for cases where the field is
        changed from one CharField type to another, and verifies that the collation
        remains consistent throughout the alteration process.

        The test uses a non-default collation to verify the correctness of the
        alteration operation. If the non-default collation is not supported by the
        database, the test is skipped.

        The test covers two scenarios: altering the field type from one CharField to
        another with the same collation, and altering the field type with a new max
        length while preserving the existing collation. In both cases, the test checks
        that the database column's collation matches the expected collation after the
        alteration operation. 
        """
        collation = connection.features.test_collations.get("non_default")
        if not collation:
            self.skipTest("Language collations are not supported.")

        with connection.schema_editor() as editor:
            editor.create_model(Author)

        old_field = Author._meta.get_field("name")
        new_field = CharField(max_length=255, db_collation=collation)
        new_field.set_attributes_from_name("name")
        new_field.model = Author
        with connection.schema_editor() as editor:
            editor.alter_field(Author, old_field, new_field, strict=True)
        self.assertEqual(
            self.get_column_collation(Author._meta.db_table, "name"),
            collation,
        )
        # Changing a field type should preserve the collation.
        old_field = new_field
        new_field = CharField(max_length=511, db_collation=collation)
        new_field.set_attributes_from_name("name")
        new_field.model = Author
        with connection.schema_editor() as editor:
            editor.alter_field(Author, new_field, old_field, strict=True)
        # Collation is preserved.
        self.assertEqual(
            self.get_column_collation(Author._meta.db_table, "name"),
            collation,
        )

    @skipUnlessDBFeature("supports_collation_on_charfield")
    def test_alter_primary_key_db_collation(self):
        """

        Test altering a model's primary key to use a non-default database collation.

        This test case verifies that it is possible to change the collation of a CharField
        primary key on a model. It first creates a model with a default collation primary
        key, alters the field to use a non-default collation, and then checks if the
        collation has been successfully applied. The test also covers reverting the field
        back to its original state.

        The test requires the database backend to support collation on character fields.
        If this feature is not supported, the test will be skipped.

        """
        collation = connection.features.test_collations.get("non_default")
        if not collation:
            self.skipTest("Language collations are not supported.")

        with connection.schema_editor() as editor:
            editor.create_model(Thing)

        old_field = Thing._meta.get_field("when")
        new_field = CharField(max_length=1, db_collation=collation, primary_key=True)
        new_field.set_attributes_from_name("when")
        new_field.model = Thing
        with connection.schema_editor() as editor:
            editor.alter_field(Thing, old_field, new_field, strict=True)
        self.assertEqual(self.get_primary_key(Thing._meta.db_table), "when")
        self.assertEqual(
            self.get_column_collation(Thing._meta.db_table, "when"),
            collation,
        )
        with connection.schema_editor() as editor:
            editor.alter_field(Thing, new_field, old_field, strict=True)
        self.assertEqual(self.get_primary_key(Thing._meta.db_table), "when")
        self.assertIsNone(self.get_column_collation(Thing._meta.db_table, "when"))

    @skipUnlessDBFeature(
        "supports_collation_on_charfield", "supports_collation_on_textfield"
    )
    def test_alter_field_type_and_db_collation(self):
        collation = connection.features.test_collations.get("non_default")
        if not collation:
            self.skipTest("Language collations are not supported.")

        with connection.schema_editor() as editor:
            editor.create_model(Note)

        old_field = Note._meta.get_field("info")
        new_field = CharField(max_length=255, db_collation=collation)
        new_field.set_attributes_from_name("info")
        new_field.model = Note
        with connection.schema_editor() as editor:
            editor.alter_field(Note, old_field, new_field, strict=True)
        columns = self.column_classes(Note)
        self.assertEqual(
            columns["info"][0],
            connection.features.introspected_field_types["CharField"],
        )
        self.assertEqual(columns["info"][1][8], collation)
        with connection.schema_editor() as editor:
            editor.alter_field(Note, new_field, old_field, strict=True)
        columns = self.column_classes(Note)
        self.assertEqual(columns["info"][0], "TextField")
        self.assertIsNone(columns["info"][1][8])

    @skipUnlessDBFeature(
        "supports_collation_on_charfield",
        "supports_non_deterministic_collations",
    )
    def test_ci_cs_db_collation(self):
        cs_collation = connection.features.test_collations.get("cs")
        ci_collation = connection.features.test_collations.get("ci")
        try:
            if connection.vendor == "mysql":
                cs_collation = "latin1_general_cs"
            elif connection.vendor == "postgresql":
                cs_collation = "en-x-icu"
                with connection.cursor() as cursor:
                    cursor.execute(
                        "CREATE COLLATION IF NOT EXISTS case_insensitive "
                        "(provider = icu, locale = 'und-u-ks-level2', "
                        "deterministic = false)"
                    )
                    ci_collation = "case_insensitive"
            # Create the table.
            with connection.schema_editor() as editor:
                editor.create_model(Author)
            # Case-insensitive collation.
            old_field = Author._meta.get_field("name")
            new_field_ci = CharField(max_length=255, db_collation=ci_collation)
            new_field_ci.set_attributes_from_name("name")
            new_field_ci.model = Author
            with connection.schema_editor() as editor:
                editor.alter_field(Author, old_field, new_field_ci, strict=True)
            Author.objects.create(name="ANDREW")
            self.assertIs(Author.objects.filter(name="Andrew").exists(), True)
            # Case-sensitive collation.
            new_field_cs = CharField(max_length=255, db_collation=cs_collation)
            new_field_cs.set_attributes_from_name("name")
            new_field_cs.model = Author
            with connection.schema_editor() as editor:
                editor.alter_field(Author, new_field_ci, new_field_cs, strict=True)
            self.assertIs(Author.objects.filter(name="Andrew").exists(), False)
        finally:
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("DROP COLLATION IF EXISTS case_insensitive")
