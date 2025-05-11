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
        """

        Tears down the test environment by deleting tables, clearing the application cache, 
        and expiring model caches. Additionally, it removes auto-created many-to-many 
        through models and the test models themselves from the app registry, 
        and removes isolated local models from the database schema. 

        This is typically used to clean up after a test has been run.

        """
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
        Maps column names in a database table to their respective field types and descriptions.

            :param model: A Django model instance
            :return: A dictionary where keys are column names and values are tuples of field type and description

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
        """
        Retrieves a list of constraints associated with a specific column in a database model.

        Returns a list of constraint names sorted alphabetically, that apply exclusively to the given column.

        :param model: Database model instance.
        :param column_name: Name of the column for which to retrieve constraints.
        :rtype: list[str]
        """
        constraints = self.get_constraints(model._meta.db_table)
        constraints_for_column = []
        for name, details in constraints.items():
            if details["columns"] == [column_name]:
                constraints_for_column.append(name)
        return sorted(constraints_for_column)

    def get_constraint_opclasses(self, constraint_name):
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
        Checks if a newly added field has the expected default value in the database.

        This function verifies that adding a field to a model results in the correct default value being stored in the database.
        It does this by executing a SQL query to retrieve the field's value and comparing it to the expected default value.

        :param schema_editor: The schema editor used to add the field
        :param model: The model to which the field was added
        :param field: The newly added field
        :param field_name: The name of the newly added field
        :param expected_default: The expected default value of the field
        :param cast_function: An optional function used to cast the database value to the expected type
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
        Tests the creation of inline foreign keys.

        Verifies that a foreign key is correctly added to a model without generating an 
        ALTER TABLE statement, instead creating the constraint inline when the field is 
        added to the model.
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
        Tests the ability to create an inline foreign key and updates its data. Verifies the index is correctly created or not created based on the database's support for indexing foreign keys.
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
        Tests the addition of an inline foreign key index and data update in the database schema.

        Verifies that creating a new model, adding a foreign key field, and updating data to reference the new field works correctly, 
        including the creation of the corresponding database index.
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
        Tests altering a CharField with a database index to a ForeignKey field.\"\"\"

         Parameters
         ----------
         None

         Returns
         -------
         None

         Notes
         -----
         Verifies that the foreign key constraint is correctly created in the database schema after the field alteration.
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
        Tests the functionality of altering a text field with a database index to a foreign key.
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
        Tests the successful alteration of a CharField primary key to an AutoField primary key in a model.
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
        """
        Tests the functionality of a many-to-many field with a disabled database constraint in a Django model, ensuring no foreign key is created for the relationship.
        """
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
        Tests the addition of a nullable one-to-one field to an existing model, ensuring the field is correctly added and its nullability is properly set.
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
        """
        Tests adding a DurationField with a default value to an existing model.\"\"\"
        ```
        """
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
        """
        Tests the addition of a generated field to a model using a Kintaro template with JSON field and stored generated column support enabled.
        """
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
        """
        Tests the addition of a generated boolean field to a model, verifying its correct behavior when the underlying value is null or non-null.
        """
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

        Tests the functionality of adding a generated field to a model.

        The test creates a model with a generated field, 'vat_price', which is calculated
        based on the 'price' field, and verifies the creation and operation of this field.

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
        """
        Tests adding a generated field that checks if a model field contains a certain value.

        This test case verifies the functionality of adding a generated field
        with a database-supported stored generated column, specifically a 'contains' operation,
        and checks that the generated field is correctly updated and returned by the database.

        """
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
        Tests the alteration of a generated field with a database index, ensuring it correctly adds the index after the alteration.
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
        Tests the addition of an AutoField to an existing model in the schema.
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

        Tests the removal of a field from a database model.

        Verifies that the field is successfully deleted from the model's database table
        and that the removal does not involve creating or dropping the entire table.

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
        """
        Tests the removal of an indexed field from a model, verifying that the field is properly dropped from the database schema.
        """
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
        """
        Tests the alteration of an AutoField to an IntegerField in a model.

        Verifies that the field can be successfully modified and that it triggers a DatabaseError
        if the database does not support unspecified primary keys, when trying to create an instance without a primary key value.
        """
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
        Checks if it's possible to alter an auto field to a char field in a model by creating a model instance with an auto field, then replacing the auto field with a char field and applying the changes to the database schema.
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
        """
        Tests altering an AutoField with a quoted database column name to a BigAutoField.
        """
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
        Tests altering a non-unique field to a primary key, verifying the resulting unique constraint count is as expected.
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

        Tests the alteration of a primary key on a database table with a quoted name.

        This test ensures that changing the primary key field of a model works correctly
        when the model's database table has a name that requires quoting.

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
        """
        Tests the alteration of a text field in the Note model, replacing the existing field with a new TextField that allows blank values.
        """
        with connection.schema_editor() as editor:
            editor.create_model(Note)
        old_field = Note._meta.get_field("info")
        new_field = TextField(blank=True)
        new_field.set_attributes_from_name("info")
        with connection.schema_editor() as editor:
            editor.alter_field(Note, old_field, new_field, strict=True)

    def test_alter_text_field_to_not_null_with_default_value(self):
        """
        Tests modifying a text field from nullable to non-nullable with a default value, ensuring existing null values are updated correctly.
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
        """
        Tests altering a field's nullability with a default value when deferred constraints are involved.

            Verifies that the database schema can be updated successfully when changing a null field to non-null with a default value,
            ensuring the new constraint is applied correctly without violating existing data integrity.

        """
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
        Tests that attempting to decrease the length of a character field in PostgreSQL results in a DataError when the new length is too small to hold existing values.
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
        Tests that altering a model field with a custom database type works correctly on PostgreSQL databases, specifically when changing the length of an ArrayField.
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
        .. function:: test_alter_array_field_decrease_base_field_length

           Tests the behavior of altering an ArrayField in a PostgreSQL database when decreasing the base field length, verifying that it raises a DataError when the new length is too small to accommodate existing data.
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
        """
        Tests altering an ArrayField with a nested ArrayField to decrease the base field length in PostgreSQL, ensuring a DataError is raised when existing data exceeds the new length.
        """
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
        """

        Creates a case-insensitive collation on the database, allowing for case-insensitive string comparisons.
        The created collation is automatically dropped when no longer needed.

        """
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
        """
        Tests the behavior of Django's ArrayField with database collation on PostgreSQL.

        Verifies that the collation of an ArrayField can be successfully set and altered
        in the database schema, ensuring correct case-insensitive sorting and comparison
        behavior for the field's elements.
        """
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
        """
        Tests the creation of a unique character field with case-insensitive collation on PostgreSQL, verifying that the collation and uniqueness constraint are correctly applied to the database column.
        """
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
        """
        Tests the behavior of a unique CharField with deterministic collation on PostgreSQL database. Verifies that the field is created with the correct collation, operator class and unique constraint.
        """
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
        Tests the correct application of a case-insensitive collation to a related CharField in a OneToOneField relationship, ensuring the collation is properly inherited and unique constraints are applied.
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
        """
        Tests the database behavior of a one-to-one relation to a CharField with a deterministic collation, ensuring the correct collation and constraint usage on PostgreSQL.
        """
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
        alteR the foreign key field in a model to a one-to-one field, ensuring the resulting database constraints are correct.
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
        Tests the conversion of an AutoField to a One-To-One field in a model, ensuring the column type is correctly updated to an IntegerField.
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
        """
        Tests that altering a ForeignKey field preserves any existing index when the underlying database supports indexes on foreign keys.
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
        """
        Tests the alteration of an one-to-one field to a foreign key field, ensuring the correct constraints are created and updated in the database.
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
        Tests that altering a One-To-One field preserves its uniqueness constraint.

        Verifies that after changing the protection level of a One-To-One field, 
        the database constraints still enforce uniqueness and the expected 
        foreign key relationships are maintained.
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
        Tests the alteration of a database table's name to have a different case, 
        ensuring the operation is successful and the table remains accessible.
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
        Tests the successful alteration of an AutoField primary key to a BigAutoField primary key on a model instance.
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
        """
        Tests the alteration of an autofield primary key to a smallautofield primary key on the Author model, ensuring a successful transition and correct sequence reset.
        """
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
        """
        Tests the alteration of a serial auto field to a big auto field and then to a regular auto field on a PostgreSQL database, verifying that the underlying sequence's data type is correctly updated.
        """
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

        Tests that renaming a referenced field in a model correctly updates the foreign key 
        in other models that reference it.

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
        Tests that adding a field with both default and db_default values to a model preserves the db_default value in the database schema.
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
        """
        Verifies that adding a text field with a database default value to a model results in the correct column default value being applied in the database.
        """
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
        """
        Tests that altering a model field with an equivalent default SQL value is a no-op operation, resulting in no database queries being executed.
        """
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
        Tests if the default output field value for a database is properly resolved, specifically for JSONField with a custom encoder and a datetime object as the default value.
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
        """
        Tests that renaming a field with a check constraint to a truncated name results in the expected single check constraint.
        """
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
        """
        Tests attempting to alter a ManyToManyField through another model to a non-through ManyToManyField raises a ValueError, as adding or removing the through model on a ManyToManyField is not supported.
        """
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
        Tests behavior of Django when a Many-To-Many field in a model references a field that has been renamed in the target model, ensuring the relationship remains intact after the alteration.
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
        Tests the addition and functionality of a check constraint with a timedelta parameter.

        Ensures that a check constraint using a timedelta comparison is correctly applied
        to a model, and that it prevents invalid data from being inserted while allowing
        valid data through.
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
        """
        Tests that check constraints on JSONFields are enforced, 
        ensuring data consistency by only allowing specific values to be stored.
        """
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
        Verifies that removing a field's check constraint does not inadvertently remove custom model metadata constraints when altering a model field using the schema editor. Ensures that custom constraints are preserved and only the automatically generated constraints are removed.
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

        Tests that unique names are correctly quoted when altering database tables and constraints.

        Verifies that the model's unique_together constraint is properly updated when the table name is changed.

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
        Tests that removing an ignored unique constraint does not create a foreign key index, 
        verifying the correct constraint removal behavior under different database backends.
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
        Tests that removing a field's unique attribute does not remove other meta constraints on the same field.
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
        """

        Tests the creation and removal of a composed index on a model with a foreign key.

        Verifies that the index is correctly added to and removed from the database schema.

        """
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
        index = Index(fields=["author", "title"], name="book_author_title_idx")
        self._test_composed_index_with_fk(index)

    def test_composed_desc_index_with_fk(self):
        index = Index(fields=["-author", "title"], name="book_author_title_idx")
        self._test_composed_index_with_fk(index)

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_composed_func_index_with_fk(self):
        index = Index(F("author"), F("title"), name="book_author_title_idx")
        self._test_composed_index_with_fk(index)

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_composed_desc_func_index_with_fk(self):
        index = Index(F("author").desc(), F("title"), name="book_author_title_idx")
        self._test_composed_index_with_fk(index)

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_composed_func_transform_index_with_fk(self):
        index = Index(F("title__lower"), name="book_title_lower_idx")
        with register_lookup(CharField, Lower):
            self._test_composed_index_with_fk(index)

    def _test_composed_constraint_with_fk(self, constraint):
        """
        Tests creating, adding, and removing a composed constraint with a foreign key on a database table. Verifies the constraint is properly registered and removed in the database schema.
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
        Tests that removing UniqueTogether constraint does not remove other custom constraints with the same fields. Ensures that custom constraints are preserved when UniqueTogether constraints are modified.
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
        Tests the creation, addition and removal of a unique constraint on the Author model.

        Verifies that the generated SQL references the correct table and column, and that the constraint is correctly added to and removed from the database schema.
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
        """

        Tests the creation and removal of a unique constraint with an expression index.

        Verifies that the constraint is correctly added to the database, enforces uniqueness,
        and is properly removed when deleted.

        """
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
        """
        Tests the creation of a unique constraint on a model using a composite function-based index, 
        verifying that the constraint is applied correctly and the generated SQL references the expected columns.
        """
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
        Tests creation of a unique constraint that includes a field and an expression.

        Verifies that a unique constraint with mixed ordering and a function (LOWER)
        can be successfully added to a model and checked for existence and properties.

        Ensures that the constraint is correctly ordered and its SQL includes the
        expected expression and references the correct columns.

        Also tests removal of the constraint and checks that it is no longer present
        after removal.
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

        Tests the creation and removal of a unique constraint with a partial index 
        and a functional condition on a model field.

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
        """

        Tests the creation and removal of a unique functional constraint with included columns.

        This test ensures that a UniqueConstraint with a functional expression (in this case, `Upper('name')`)
        and included columns can be successfully added to and removed from a model.

        """
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
        Tests the creation and removal of a unique constraint using expression lookups on a model instance.

        This test case verifies that a unique constraint can be successfully added and removed, using lookups on the 'name' and 'weight' fields of the Author model. It checks that the constraint is correctly created, the constraint name is present in the model's constraints, and that the SQL generated by the constraint references the correct columns. The test also ensures that the constraint is properly removed from the model instance after deletion.
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
        Tests the creation and behavior of a unique constraint with a case-insensitive collation on a model's fields.
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
        Tests that adding and removing a unique constraint is unsupported when 
        the database does not support expression indexes, resulting in no database queries.
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
        Tests that creating a unique constraint with a nonexistent field raises a FieldError.

        Checks that the database correctly rejects an attempt to create a unique constraint using a non-existent field in the model.
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
        """
        Tests that attempting to add a unique constraint with a non-deterministic function (in this case, a random value) raises a DatabaseError, verifying the database's handling of such constraints.
        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        constraint = UniqueConstraint(Random(), name="func_random_uq")
        with connection.schema_editor() as editor:
            with self.assertRaises(DatabaseError):
                editor.add_constraint(Author, constraint)

    @skipUnlessDBFeature("supports_nulls_distinct_unique_constraints")
    def test_unique_constraint_index_nulls_distinct(self):
        """
        Tests the functionality of unique constraints with nulls_distinct option in the database, ensuring that null values are handled correctly when adding and removing constraints.
        """
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
        Tests the behavior of unique constraints with nulls_distinct=False, ensuring duplicate rows with null values are prevented.
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
        Tests the creation and enforcement of a unique constraint with a condition, where null values are not considered distinct, ensuring data consistency and preventing duplicate entries.
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
        """
        Tests the addition and removal of unique constraints with nulls distinct option when it is unsupported by the database backend.
        """
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
        """
        Tests that adding an index containing multiple references to a function's result raises an error when the database does not support expression indexes.
        """
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
        """

        Tests the invalid usage of non-topmost expressions in an indexed expression.

        Verifies that attempting to create an index with an invalid topmost expression raises a ValueError.

        """
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
        Tests the creation and removal of a functional index with a descending ordering expression.

        Verifies that the index is correctly created, its SQL representation contains the expected expression,
        and its column ordering is as expected if supported by the database backend. Finally, checks that
        the index is properly removed and no longer present in the database schema.
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

        Verifies that the index is correctly applied to the database table and that
        the index SQL references the correct columns. Also checks that the index can
        be successfully removed from the table.
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
        Test lookups using functional indexes.

        This test case checks that indexes can be created with functions,
        added and removed from the database, and verifies that the index
        _queries reference the correct columns. It specifically tests 
        function-based indexes using the `Lower` and `Abs` functions.
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

        Tests the creation of a composite index with functional expressions.

        Verifies that an index with lower and upper case functions can be added and removed
        from the Author model, and checks that the generated SQL is correct.

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
        Tests the creation and removal of a composite index with a function field and an expression on a model field in a database, verifying the index is created correctly and its constraints are valid.
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

        Tests creation and removal of a functional index on a DecimalField in a database.

        Verifies that the index is correctly created, added to the model, and removed,
        and that the generated SQL does not include a CAST expression.

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
        Tests creation and removal of a functional index with a cast operation, 
        verifying that the index is correctly applied to and removed from the database table.
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
        Tests the creation and removal of a database index that uses a non-default collation for case-insensitive sorting, verifying that the index is correctly applied and utilized in queries.
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

        Tests the creation and removal of a functional index with a collation, 
        specifically verifying that it's correctly ordered and contains the collation in its SQL.

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
        Tests the creation and removal of a functional index, specifically an expression-based index that performs a calculation involving model fields, verifying that it is correctly applied to the database table and references the expected columns.
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
        Tests the creation and removal of a function-based index on a JSONField, verifying that the index is correctly applied and removed from the database schema.
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
        """
        Verifies that creating an index on a JSON field with a key transformation and type casting works as expected.

        Ensures the index is properly created, referenced, and removed, testing database support for expression indexes and JSON fields.
        """
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
        Tests that adding and removing a function-based index is unsupported and results in no operations when the database backend does not support expression indexes.
        """
        with connection.schema_editor() as editor:
            editor.create_model(Author)
        index = Index(F("name"), name="random_idx")
        with connection.schema_editor() as editor, self.assertNumQueries(0):
            self.assertIsNone(editor.add_index(Author, index))
            self.assertIsNone(editor.remove_index(Author, index))

    @skipUnlessDBFeature("supports_expression_indexes")
    def test_func_index_nonexistent_field(self):
        """
        Tests that adding an index with a function reference to a nonexistent field raises a FieldError.
        """
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
        Tests that an attempt to create a database index on a nondeterministic function, such as the random function, raises a DatabaseError.

        This test verifies that the database backend correctly prevents creation of indexes on functions that can return different results for the same input, ensuring data integrity and preventing unexpected query behavior.
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

        Tests altering a model field to have the same primary key name, and then reverting back to the original field.
        Verifies that the primary key name remains consistent after the alteration and reversion.

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
        Tests the creation of a foreign key referencing a model with a quoted database table name.

        This test verifies that a foreign key can be successfully established when the referenced model's
        database table name is quoted, and that the foreign key is correctly created and recognizable
        by the database backend, regardless of the database vendor being used.
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
        """
        Tests the addition of a foreign object to a model in the database schema.
        """
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
        Tests that adding a field with a default value to an existing model works correctly, 
        including the default value being applied to existing rows and being correctly 
        represented in the database schema.
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
        Tests adding a field with a default value to a model, verifying that the field is nullable and its default value is None.
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
        Tests the addition of a nullable text field with a default value to a model, 
        verifying that the field is created correctly and its nullability is properly set.
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
        Tests that altering a field's default value results in the default value being dropped from the database schema, even if the field itself is still defined with a default value in the model.
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
        Tests that altering a field's choices does not trigger a database migration when the choices do not change the underlying field type or constraints.
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
        Tests adding a text field with an unhashable default value to a model, in this case, a dictionary as the default for the 'info' field of the Author model.
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

        Verifies that the correct constraints are created for the field.
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
        Tests the addition of a unique CharField to a model in PostgreSQL.

        Verifies that the correct constraints are created for the field.
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
        Tests the addition of a database comment to a CharField model field. 
        Verifies that the comment is correctly applied to the database column when the model is created.
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
        Tests the addition of a CharField to a model with a custom database comment and default value, verifying that the comment is correctly applied and the default value is used when creating new instances.
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
        """
        Tests the alteration of a database comment for a model field, ensuring that comments can be set, updated, and removed correctly.
        """
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
        """
        Tests the ability to alter a database's foreign key comment using the schema editor.
        """
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
        """
        Tests that altering a field's type in a model preserves its comment.
        """
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
        """
        Tests that the database table comment can be correctly set and altered in the database schema. 
        Verifies that the comment is correctly created, updated and dropped for a given model.
        """
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
        Tests that altering a database table comment is not supported when the database backend does not support comments, resulting in no SQL queries being executed.
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
        Tests database comments are correctly propagated from an abstract model to its concrete subclass, both at the table and column levels.
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
        Tests altering a CharField to add an index and then removing it on a PostgreSQL database.

        This test case verifies that the database constraints are correctly updated when a CharField
        is modified to add or remove a database index, ensuring data consistency and integrity.

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
        """
        Tests the alteration of a model field to add a unique constraint to a character field in a PostgreSQL database. Verifies that the constraint is correctly added and then removed.
        """
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
        """
        Tests adding and removing a PostgreSQL index on a TextField model field.

        This test case checks that the database schema is correctly altered when changing a
        TextField to have a database index, and then reverts this change to ensure the index
        is properly removed. The test is specific to PostgreSQL databases.
        """
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
        """
        PostgreSQL-specific test case that verifies the successful alteration of a CharField to add and then remove a unique constraint with a database index.\"\"\"

         ArgumentException note the name \"test_alter_field_add_unique_to_charfield_with_db_index is describing the method because docstrings are supposed to be sentences as sphinx guidelines
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
        Tests altering a model field to remove its unique constraint and database index on a PostgreSQL database.

         Verifies that the constraints are correctly removed from the database schema after the field alteration.
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
        Tests the alteration of a model field, specifically swapping between a unique constraint and a database index on a character field, ensuring the resulting constraints are as expected.
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
        """
        Tests altering a CharField in a PostgreSQL database to add a db_index, 
        then tests altering it to remove db_index while preserving the unique constraint.
        """
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
        Tests that adding an index to an IntegerField using the alter_field method correctly 
        modifies the database constraints, and that reversing this change removes the index.
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
        """

        Tests model creation with a db_table specified in double quotes, 
        an Oracle database specific syntax requirement. 
        Ensures creation and relationship linking of models work as expected.

        """
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
        """

        Tests the creation of a foreign key reference to a namespaced db table in PostgreSQL.

        Verifies that a foreign key can be successfully created between two models, 
        one of which has its db table defined in a custom schema.

        """
        with connection.cursor() as cursor:
            cursor.execute("CREATE SCHEMA django_schema_tests")

        def delete_schema():
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
        Tests that renaming a table updates deferred SQL references accordingly, ensuring that old table names are replaced with the new ones after the rename operation.
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

        Verifies that renaming a column updates deferred SQL references.

        Tests that when a column is renamed, the references to the old column name
        are correctly updated in the deferred SQL statements generated by the schema editor.

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
        """
        Tests the database collation on a CharField in a model, verifying that the specified collation is applied correctly to the field in the database.
        """
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
        """
        Tests the creation of a model with a TextField that uses a non-default database collation.
        """
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
        """
        Tests adding a field to a model with a non-default database collation.

        Verifies that the collation of a CharField is correctly set and introspected when 
        added to a model using the database schema editor.
        """
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
        """

        Tests altering a model field's database collation.

        Verifies that changing the collation of a CharField works correctly, 
        including setting a non-default collation and later resetting it back to the default.

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
        with connection.schema_editor() as editor:
            editor.alter_field(Author, new_field, old_field, strict=True)
        self.assertIsNone(self.get_column_collation(Author._meta.db_table, "name"))

    @skipUnlessDBFeature("supports_collation_on_charfield")
    def test_alter_field_type_preserve_db_collation(self):
        """
        Tests if altering a CharField preserves the database collation when changing the field type or length, ensuring the collation remains consistent with the original setting.
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
        Tests if the primary key of a model can be altered to use a non-default database collation on a CharField.\"\"\"

        \"\"\"Checks both setting and resetting a non-default collation on the primary key field.\"\"\"

        \"\"\"Verifies the primary key and collation after applying the alteration.\"\"\"
        \"\"\"Ensures the primary key and collation return to their original state after reverting the alteration.
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
        """
        Tests altering a field type and its database collation.

        Tests that a CharField can be altered to have a non-default collation and
        then reverted to its original type (TextField) and default collation.
        """
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
        """
        Validates that changing the database collation on a CharacterField from case-insensitive to case-sensitive behavior works correctly, by testing the existence of objects in the database after altering the field's collation.
        """
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
