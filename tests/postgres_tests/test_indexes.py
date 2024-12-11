from django.contrib.postgres.indexes import (
    BloomIndex,
    BrinIndex,
    BTreeIndex,
    GinIndex,
    GistIndex,
    HashIndex,
    OpClass,
    PostgresIndex,
    SpGistIndex,
)
from django.db import connection
from django.db.models import CharField, F, Index, Q
from django.db.models.functions import Cast, Collate, Length, Lower
from django.test.utils import register_lookup

from . import PostgreSQLSimpleTestCase, PostgreSQLTestCase
from .fields import SearchVector, SearchVectorField
from .models import CharFieldModel, IntegerArrayModel, Scene, TextFieldModel


class IndexTestMixin:
    def test_name_auto_generation(self):
        index = self.index_class(fields=["field"])
        index.set_name_with_model(CharFieldModel)
        self.assertRegex(
            index.name, r"postgres_te_field_[0-9a-f]{6}_%s" % self.index_class.suffix
        )

    def test_deconstruction_no_customization(self):
        index = self.index_class(
            fields=["title"], name="test_title_%s" % self.index_class.suffix
        )
        path, args, kwargs = index.deconstruct()
        self.assertEqual(
            path, "django.contrib.postgres.indexes.%s" % self.index_class.__name__
        )
        self.assertEqual(args, ())
        self.assertEqual(
            kwargs,
            {"fields": ["title"], "name": "test_title_%s" % self.index_class.suffix},
        )

    def test_deconstruction_with_expressions_no_customization(self):
        """
        Tests the deconstruction of an index instance with an expression, 
        verifying that it correctly breaks down into its constituent components.
        The deconstruction process involves decomposing the index into its path, 
        positional arguments, and keyword arguments. 
        The path should match the module and class name of the index, 
        the positional arguments should contain the expression used in the index, 
        and the keyword arguments should include any additional parameters, 
        such as the index name.
        """
        name = f"test_title_{self.index_class.suffix}"
        index = self.index_class(Lower("title"), name=name)
        path, args, kwargs = index.deconstruct()
        self.assertEqual(
            path,
            f"django.contrib.postgres.indexes.{self.index_class.__name__}",
        )
        self.assertEqual(args, (Lower("title"),))
        self.assertEqual(kwargs, {"name": name})


class BloomIndexTests(IndexTestMixin, PostgreSQLSimpleTestCase):
    index_class = BloomIndex

    def test_suffix(self):
        self.assertEqual(BloomIndex.suffix, "bloom")

    def test_deconstruction(self):
        index = BloomIndex(fields=["title"], name="test_bloom", length=80, columns=[4])
        path, args, kwargs = index.deconstruct()
        self.assertEqual(path, "django.contrib.postgres.indexes.BloomIndex")
        self.assertEqual(args, ())
        self.assertEqual(
            kwargs,
            {
                "fields": ["title"],
                "name": "test_bloom",
                "length": 80,
                "columns": [4],
            },
        )

    def test_invalid_fields(self):
        """

        Tests that creating a BloomIndex with more than 32 fields raises a ValueError.

        The test checks that the expected error message is raised when attempting to create an index with 33 fields.

        """
        msg = "Bloom indexes support a maximum of 32 fields."
        with self.assertRaisesMessage(ValueError, msg):
            BloomIndex(fields=["title"] * 33, name="test_bloom")

    def test_invalid_columns(self):
        msg = "BloomIndex.columns must be a list or tuple."
        with self.assertRaisesMessage(ValueError, msg):
            BloomIndex(fields=["title"], name="test_bloom", columns="x")
        msg = "BloomIndex.columns cannot have more values than fields."
        with self.assertRaisesMessage(ValueError, msg):
            BloomIndex(fields=["title"], name="test_bloom", columns=[4, 3])

    def test_invalid_columns_value(self):
        """
        Checks that an error is raised when the 'columns' parameter of BloomIndex is invalid.

        This test ensures that BloomIndex.columns only accepts integers within the valid range (1 to 4095).
        It verifies that a ValueError is raised when the 'columns' parameter is set to an invalid value, 
        specifically 0 or 4096, with a corresponding error message indicating the valid range for 'columns'.
        """
        msg = "BloomIndex.columns must contain integers from 1 to 4095."
        for length in (0, 4096):
            with self.subTest(length), self.assertRaisesMessage(ValueError, msg):
                BloomIndex(fields=["title"], name="test_bloom", columns=[length])

    def test_invalid_length(self):
        """
        Tests that passing an invalid length to the BloomIndex constructor raises a ValueError.

        The BloomIndex length must be either None or an integer between 1 and 4096 (inclusive). This test ensures that invalid lengths, such as non-positive integers or integers greater than 4096, are correctly rejected.

        The test checks for the following specific invalid lengths: 0 and 4097, and verifies that the expected error message is raised in both cases.
        """
        msg = "BloomIndex.length must be None or an integer from 1 to 4096."
        for length in (0, 4097):
            with self.subTest(length), self.assertRaisesMessage(ValueError, msg):
                BloomIndex(fields=["title"], name="test_bloom", length=length)


class BrinIndexTests(IndexTestMixin, PostgreSQLSimpleTestCase):
    index_class = BrinIndex

    def test_suffix(self):
        self.assertEqual(BrinIndex.suffix, "brin")

    def test_deconstruction(self):
        index = BrinIndex(
            fields=["title"],
            name="test_title_brin",
            autosummarize=True,
            pages_per_range=16,
        )
        path, args, kwargs = index.deconstruct()
        self.assertEqual(path, "django.contrib.postgres.indexes.BrinIndex")
        self.assertEqual(args, ())
        self.assertEqual(
            kwargs,
            {
                "fields": ["title"],
                "name": "test_title_brin",
                "autosummarize": True,
                "pages_per_range": 16,
            },
        )

    def test_invalid_pages_per_range(self):
        with self.assertRaisesMessage(
            ValueError, "pages_per_range must be None or a positive integer"
        ):
            BrinIndex(fields=["title"], name="test_title_brin", pages_per_range=0)


class BTreeIndexTests(IndexTestMixin, PostgreSQLSimpleTestCase):
    index_class = BTreeIndex

    def test_suffix(self):
        self.assertEqual(BTreeIndex.suffix, "btree")

    def test_deconstruction(self):
        """
        Deconstructs a BTreeIndex instance into its constituent parts.

        This method returns a tuple of path, args, and kwargs that can be used to reconstruct the BTreeIndex instance. The path is the dotted path to the BTreeIndex class, args is a tuple of positional arguments (which is always empty in this case), and kwargs is a dictionary of keyword arguments that were used to create the BTreeIndex instance.

        The deconstruction process includes all attributes of the BTreeIndex instance, such as the fields to index, the name of the index, and any additional options like fillfactor and deduplicate_items. The returned kwargs dictionary will contain all of these attributes, allowing for easy reconstruction of the BTreeIndex instance.
        """
        index = BTreeIndex(fields=["title"], name="test_title_btree")
        path, args, kwargs = index.deconstruct()
        self.assertEqual(path, "django.contrib.postgres.indexes.BTreeIndex")
        self.assertEqual(args, ())
        self.assertEqual(kwargs, {"fields": ["title"], "name": "test_title_btree"})

        index = BTreeIndex(
            fields=["title"],
            name="test_title_btree",
            fillfactor=80,
            deduplicate_items=False,
        )
        path, args, kwargs = index.deconstruct()
        self.assertEqual(path, "django.contrib.postgres.indexes.BTreeIndex")
        self.assertEqual(args, ())
        self.assertEqual(
            kwargs,
            {
                "fields": ["title"],
                "name": "test_title_btree",
                "fillfactor": 80,
                "deduplicate_items": False,
            },
        )


class GinIndexTests(IndexTestMixin, PostgreSQLSimpleTestCase):
    index_class = GinIndex

    def test_suffix(self):
        self.assertEqual(GinIndex.suffix, "gin")

    def test_deconstruction(self):
        index = GinIndex(
            fields=["title"],
            name="test_title_gin",
            fastupdate=True,
            gin_pending_list_limit=128,
        )
        path, args, kwargs = index.deconstruct()
        self.assertEqual(path, "django.contrib.postgres.indexes.GinIndex")
        self.assertEqual(args, ())
        self.assertEqual(
            kwargs,
            {
                "fields": ["title"],
                "name": "test_title_gin",
                "fastupdate": True,
                "gin_pending_list_limit": 128,
            },
        )


class GistIndexTests(IndexTestMixin, PostgreSQLSimpleTestCase):
    index_class = GistIndex

    def test_suffix(self):
        self.assertEqual(GistIndex.suffix, "gist")

    def test_deconstruction(self):
        """

        Tests the deconstruction of a GistIndex object into its constituent parts.

        This method verifies that a GistIndex instance can be successfully broken down
        into its path, arguments, and keyword arguments, allowing it to be reconstructed
        later. The test checks that the deconstructed path points to the correct class,
        and that the arguments and keyword arguments are correctly extracted and passed
        through. The keyword arguments include the fields, name, buffering, and fillfactor
        parameters of the original GistIndex object.

        """
        index = GistIndex(
            fields=["title"], name="test_title_gist", buffering=False, fillfactor=80
        )
        path, args, kwargs = index.deconstruct()
        self.assertEqual(path, "django.contrib.postgres.indexes.GistIndex")
        self.assertEqual(args, ())
        self.assertEqual(
            kwargs,
            {
                "fields": ["title"],
                "name": "test_title_gist",
                "buffering": False,
                "fillfactor": 80,
            },
        )


class HashIndexTests(IndexTestMixin, PostgreSQLSimpleTestCase):
    index_class = HashIndex

    def test_suffix(self):
        self.assertEqual(HashIndex.suffix, "hash")

    def test_deconstruction(self):
        index = HashIndex(fields=["title"], name="test_title_hash", fillfactor=80)
        path, args, kwargs = index.deconstruct()
        self.assertEqual(path, "django.contrib.postgres.indexes.HashIndex")
        self.assertEqual(args, ())
        self.assertEqual(
            kwargs, {"fields": ["title"], "name": "test_title_hash", "fillfactor": 80}
        )


class SpGistIndexTests(IndexTestMixin, PostgreSQLSimpleTestCase):
    index_class = SpGistIndex

    def test_suffix(self):
        self.assertEqual(SpGistIndex.suffix, "spgist")

    def test_deconstruction(self):
        index = SpGistIndex(fields=["title"], name="test_title_spgist", fillfactor=80)
        path, args, kwargs = index.deconstruct()
        self.assertEqual(path, "django.contrib.postgres.indexes.SpGistIndex")
        self.assertEqual(args, ())
        self.assertEqual(
            kwargs, {"fields": ["title"], "name": "test_title_spgist", "fillfactor": 80}
        )


class SchemaTests(PostgreSQLTestCase):
    get_opclass_query = """
        SELECT opcname, c.relname FROM pg_opclass AS oc
        JOIN pg_index as i on oc.oid = ANY(i.indclass)
        JOIN pg_class as c on c.oid = i.indexrelid
        WHERE c.relname = %s
    """

    def get_constraints(self, table):
        """
        Get the indexes on the table using a new cursor.
        """
        with connection.cursor() as cursor:
            return connection.introspection.get_constraints(cursor, table)

    def test_gin_index(self):
        # Ensure the table is there and doesn't have an index.
        self.assertNotIn(
            "field", self.get_constraints(IntegerArrayModel._meta.db_table)
        )
        # Add the index
        index_name = "integer_array_model_field_gin"
        index = GinIndex(fields=["field"], name=index_name)
        with connection.schema_editor() as editor:
            editor.add_index(IntegerArrayModel, index)
        constraints = self.get_constraints(IntegerArrayModel._meta.db_table)
        # Check gin index was added
        self.assertEqual(constraints[index_name]["type"], GinIndex.suffix)
        # Drop the index
        with connection.schema_editor() as editor:
            editor.remove_index(IntegerArrayModel, index)
        self.assertNotIn(
            index_name, self.get_constraints(IntegerArrayModel._meta.db_table)
        )

    def test_gin_fastupdate(self):
        """
        Tests the creation and removal of a GIN index with fastupdate option disabled.

        This test case verifies that a GIN index is correctly created and removed from the database.
        It checks the index type and options, specifically ensuring that the fastupdate option is set to 'off'.
        The test covers the entire lifecycle of the index, from creation to removal, and validates the resulting database state.

        :raises AssertionError: If the index type or options do not match the expected values, or if the index is not properly removed from the database.
        """
        index_name = "integer_array_gin_fastupdate"
        index = GinIndex(fields=["field"], name=index_name, fastupdate=False)
        with connection.schema_editor() as editor:
            editor.add_index(IntegerArrayModel, index)
        constraints = self.get_constraints(IntegerArrayModel._meta.db_table)
        self.assertEqual(constraints[index_name]["type"], "gin")
        self.assertEqual(constraints[index_name]["options"], ["fastupdate=off"])
        with connection.schema_editor() as editor:
            editor.remove_index(IntegerArrayModel, index)
        self.assertNotIn(
            index_name, self.get_constraints(IntegerArrayModel._meta.db_table)
        )

    def test_partial_gin_index(self):
        """

        Test the creation and removal of a partial GIN index on a model field.

        This test case verifies that a partial GIN index can be successfully added to and removed from a model,
        with a specific condition applied to the indexed field. It checks the type of the created index and
        ensures that the index is properly dropped after removal.

        Checks that the index is correctly created with the specified condition, and that the index type is 'gin'.
        Also verifies that the index is removed and no longer exists in the database after removal.

        """
        with register_lookup(CharField, Length):
            index_name = "char_field_gin_partial_idx"
            index = GinIndex(
                fields=["field"], name=index_name, condition=Q(field__length=40)
            )
            with connection.schema_editor() as editor:
                editor.add_index(CharFieldModel, index)
            constraints = self.get_constraints(CharFieldModel._meta.db_table)
            self.assertEqual(constraints[index_name]["type"], "gin")
            with connection.schema_editor() as editor:
                editor.remove_index(CharFieldModel, index)
            self.assertNotIn(
                index_name, self.get_constraints(CharFieldModel._meta.db_table)
            )

    def test_partial_gin_index_with_tablespace(self):
        """
        Tests the creation of a partial GIN index with a specified tablespace on a model field.

        This test ensures that a GIN index can be successfully created on a model field with a partial filter condition,
        and that the index is created in the specified tablespace. Additionally, it validates that the index is properly removed
        after creation.

        The test covers the following scenarios:
        - The index is created with the correct type (GIN) and tablespace.
        - The index is correctly added to the model.
        - The index is properly removed from the model.

        The test uses a CharField model and creates a GIN index on the field with a length condition of 40 characters.
        It verifies that the index creation SQL includes the specified tablespace and that the index type is correct.
        After successful creation, the test removes the index and confirms that it is no longer present in the model's constraints.
        """
        with register_lookup(CharField, Length):
            index_name = "char_field_gin_partial_idx"
            index = GinIndex(
                fields=["field"],
                name=index_name,
                condition=Q(field__length=40),
                db_tablespace="pg_default",
            )
            with connection.schema_editor() as editor:
                editor.add_index(CharFieldModel, index)
                self.assertIn(
                    'TABLESPACE "pg_default" ',
                    str(index.create_sql(CharFieldModel, editor)),
                )
            constraints = self.get_constraints(CharFieldModel._meta.db_table)
            self.assertEqual(constraints[index_name]["type"], "gin")
            with connection.schema_editor() as editor:
                editor.remove_index(CharFieldModel, index)
            self.assertNotIn(
                index_name, self.get_constraints(CharFieldModel._meta.db_table)
            )

    def test_gin_parameters(self):
        index_name = "integer_array_gin_params"
        index = GinIndex(
            fields=["field"],
            name=index_name,
            fastupdate=True,
            gin_pending_list_limit=64,
            db_tablespace="pg_default",
        )
        with connection.schema_editor() as editor:
            editor.add_index(IntegerArrayModel, index)
            self.assertIn(
                ") WITH (gin_pending_list_limit = 64, fastupdate = on) TABLESPACE",
                str(index.create_sql(IntegerArrayModel, editor)),
            )
        constraints = self.get_constraints(IntegerArrayModel._meta.db_table)
        self.assertEqual(constraints[index_name]["type"], "gin")
        self.assertEqual(
            constraints[index_name]["options"],
            ["gin_pending_list_limit=64", "fastupdate=on"],
        )
        with connection.schema_editor() as editor:
            editor.remove_index(IntegerArrayModel, index)
        self.assertNotIn(
            index_name, self.get_constraints(IntegerArrayModel._meta.db_table)
        )

    def test_trigram_op_class_gin_index(self):
        """
        Tests the creation and removal of a trigram GIN index on the 'scene' table using the 'gin_trgm_ops' operator class.

        The test creates a GIN index with the specified operator class, adds it to the table, and then verifies its existence in the database. It checks the index's type and ensures it is correctly associated with the 'gin_trgm_ops' operator class.

        Afterwards, the test removes the index and confirms its successful removal by checking the updated constraints on the table. 

        This test case covers the end-to-end functionality of adding and removing a GIN index with a trigram operator class, including verification of its properties and its removal from the database schema.
        """
        index_name = "trigram_op_class_gin"
        index = GinIndex(OpClass(F("scene"), name="gin_trgm_ops"), name=index_name)
        with connection.schema_editor() as editor:
            editor.add_index(Scene, index)
        with editor.connection.cursor() as cursor:
            cursor.execute(self.get_opclass_query, [index_name])
            self.assertCountEqual(cursor.fetchall(), [("gin_trgm_ops", index_name)])
        constraints = self.get_constraints(Scene._meta.db_table)
        self.assertIn(index_name, constraints)
        self.assertIn(constraints[index_name]["type"], GinIndex.suffix)
        with connection.schema_editor() as editor:
            editor.remove_index(Scene, index)
        self.assertNotIn(index_name, self.get_constraints(Scene._meta.db_table))

    def test_cast_search_vector_gin_index(self):
        index_name = "cast_search_vector_gin"
        index = GinIndex(Cast("field", SearchVectorField()), name=index_name)
        with connection.schema_editor() as editor:
            editor.add_index(TextFieldModel, index)
            sql = index.create_sql(TextFieldModel, editor)
        table = TextFieldModel._meta.db_table
        constraints = self.get_constraints(table)
        self.assertIn(index_name, constraints)
        self.assertIn(constraints[index_name]["type"], GinIndex.suffix)
        self.assertIs(sql.references_column(table, "field"), True)
        self.assertIn("::tsvector", str(sql))
        with connection.schema_editor() as editor:
            editor.remove_index(TextFieldModel, index)
        self.assertNotIn(index_name, self.get_constraints(table))

    def test_bloom_index(self):
        """

        Tests the creation and removal of a Bloom index on a model field.

        Verifies that the index is correctly added to the database schema and that its
        properties match the expected Bloom index suffix. Additionally, it checks that
        the index is properly removed from the schema after deletion.

        """
        index_name = "char_field_model_field_bloom"
        index = BloomIndex(fields=["field"], name=index_name)
        with connection.schema_editor() as editor:
            editor.add_index(CharFieldModel, index)
        constraints = self.get_constraints(CharFieldModel._meta.db_table)
        self.assertEqual(constraints[index_name]["type"], BloomIndex.suffix)
        with connection.schema_editor() as editor:
            editor.remove_index(CharFieldModel, index)
        self.assertNotIn(
            index_name, self.get_constraints(CharFieldModel._meta.db_table)
        )

    def test_bloom_parameters(self):
        """

        Tests the creation and removal of a Bloom index on a model field.

        This test case verifies that a Bloom index can be successfully added to a model,
        and that its parameters (length and columns) are correctly applied. It also checks
        that the index can be removed, leaving no residual constraints in the database.

        The test covers the following scenarios:
        - Adding a Bloom index to a model field
        - Verifying the index type and options
        - Removing the Bloom index
        - Ensuring the index removal leaves no residual constraints

        """
        index_name = "char_field_model_field_bloom_params"
        index = BloomIndex(fields=["field"], name=index_name, length=512, columns=[3])
        with connection.schema_editor() as editor:
            editor.add_index(CharFieldModel, index)
        constraints = self.get_constraints(CharFieldModel._meta.db_table)
        self.assertEqual(constraints[index_name]["type"], BloomIndex.suffix)
        self.assertEqual(constraints[index_name]["options"], ["length=512", "col1=3"])
        with connection.schema_editor() as editor:
            editor.remove_index(CharFieldModel, index)
        self.assertNotIn(
            index_name, self.get_constraints(CharFieldModel._meta.db_table)
        )

    def test_brin_index(self):
        index_name = "char_field_model_field_brin"
        index = BrinIndex(fields=["field"], name=index_name, pages_per_range=4)
        with connection.schema_editor() as editor:
            editor.add_index(CharFieldModel, index)
        constraints = self.get_constraints(CharFieldModel._meta.db_table)
        self.assertEqual(constraints[index_name]["type"], BrinIndex.suffix)
        self.assertEqual(constraints[index_name]["options"], ["pages_per_range=4"])
        with connection.schema_editor() as editor:
            editor.remove_index(CharFieldModel, index)
        self.assertNotIn(
            index_name, self.get_constraints(CharFieldModel._meta.db_table)
        )

    def test_brin_parameters(self):
        index_name = "char_field_brin_params"
        index = BrinIndex(fields=["field"], name=index_name, autosummarize=True)
        with connection.schema_editor() as editor:
            editor.add_index(CharFieldModel, index)
        constraints = self.get_constraints(CharFieldModel._meta.db_table)
        self.assertEqual(constraints[index_name]["type"], BrinIndex.suffix)
        self.assertEqual(constraints[index_name]["options"], ["autosummarize=on"])
        with connection.schema_editor() as editor:
            editor.remove_index(CharFieldModel, index)
        self.assertNotIn(
            index_name, self.get_constraints(CharFieldModel._meta.db_table)
        )

    def test_btree_index(self):
        # Ensure the table is there and doesn't have an index.
        """

        Tests the creation and removal of a B-tree index on a model field.

        Verifies that the index is successfully added to the database table, 
        and that its type is correctly identified as a B-tree index. 
        Additionally, checks that the index is properly removed from the table.

        This test ensures that the B-tree index functionality is working as expected,
        and that the index can be correctly created and deleted from the database schema.

        """
        self.assertNotIn("field", self.get_constraints(CharFieldModel._meta.db_table))
        # Add the index.
        index_name = "char_field_model_field_btree"
        index = BTreeIndex(fields=["field"], name=index_name)
        with connection.schema_editor() as editor:
            editor.add_index(CharFieldModel, index)
        constraints = self.get_constraints(CharFieldModel._meta.db_table)
        # The index was added.
        self.assertEqual(constraints[index_name]["type"], BTreeIndex.suffix)
        # Drop the index.
        with connection.schema_editor() as editor:
            editor.remove_index(CharFieldModel, index)
        self.assertNotIn(
            index_name, self.get_constraints(CharFieldModel._meta.db_table)
        )

    def test_btree_parameters(self):
        """

        Tests the creation and removal of a BTree index on a model field with custom parameters.

        This test case verifies that a BTree index with specified parameters (fillfactor and deduplicate items) 
        is correctly created and stored in the database schema. It also checks that the index is properly removed 
        when requested.

        The test covers the following scenarios:
        - Index creation with custom parameters.
        - Verification of index type and options in the database schema.
        - Index removal and schema update.

        """
        index_name = "integer_array_btree_parameters"
        index = BTreeIndex(
            fields=["field"], name=index_name, fillfactor=80, deduplicate_items=False
        )
        with connection.schema_editor() as editor:
            editor.add_index(CharFieldModel, index)
        constraints = self.get_constraints(CharFieldModel._meta.db_table)
        self.assertEqual(constraints[index_name]["type"], BTreeIndex.suffix)
        self.assertEqual(
            constraints[index_name]["options"],
            ["fillfactor=80", "deduplicate_items=off"],
        )
        with connection.schema_editor() as editor:
            editor.remove_index(CharFieldModel, index)
        self.assertNotIn(
            index_name, self.get_constraints(CharFieldModel._meta.db_table)
        )

    def test_gist_index(self):
        # Ensure the table is there and doesn't have an index.
        """

        Test the creation and deletion of a GIST index on a model field.

        This function verifies that a GIST index can be successfully added to and removed from a model field.
        It checks that the index is not initially present, adds it, confirms its presence and type, removes it, and then checks that it is no longer present.

        The test covers the following scenarios:
        - The index is not present on the model field initially
        - The index can be created on the model field
        - The index is correctly identified as a GIST index
        - The index can be removed from the model field
        - The index is no longer present after removal

        """
        self.assertNotIn("field", self.get_constraints(CharFieldModel._meta.db_table))
        # Add the index.
        index_name = "char_field_model_field_gist"
        index = GistIndex(fields=["field"], name=index_name)
        with connection.schema_editor() as editor:
            editor.add_index(CharFieldModel, index)
        constraints = self.get_constraints(CharFieldModel._meta.db_table)
        # The index was added.
        self.assertEqual(constraints[index_name]["type"], GistIndex.suffix)
        # Drop the index.
        with connection.schema_editor() as editor:
            editor.remove_index(CharFieldModel, index)
        self.assertNotIn(
            index_name, self.get_constraints(CharFieldModel._meta.db_table)
        )

    def test_gist_parameters(self):
        """

        Tests the creation and removal of a GIST index with custom parameters.

        Verifies that a GIST index is successfully added to the database with the specified
        fields, name, and options (buffering and fillfactor), and that the index is correctly
        removed from the database.

        Checks the following conditions:
        - The index is created with the correct type (GIST) and options.
        - The index is removed from the database, and its presence is no longer detected.

        """
        index_name = "integer_array_gist_buffering"
        index = GistIndex(
            fields=["field"], name=index_name, buffering=True, fillfactor=80
        )
        with connection.schema_editor() as editor:
            editor.add_index(CharFieldModel, index)
        constraints = self.get_constraints(CharFieldModel._meta.db_table)
        self.assertEqual(constraints[index_name]["type"], GistIndex.suffix)
        self.assertEqual(
            constraints[index_name]["options"], ["buffering=on", "fillfactor=80"]
        )
        with connection.schema_editor() as editor:
            editor.remove_index(CharFieldModel, index)
        self.assertNotIn(
            index_name, self.get_constraints(CharFieldModel._meta.db_table)
        )

    def test_gist_include(self):
        index_name = "scene_gist_include_setting"
        index = GistIndex(name=index_name, fields=["scene"], include=["setting"])
        with connection.schema_editor() as editor:
            editor.add_index(Scene, index)
        constraints = self.get_constraints(Scene._meta.db_table)
        self.assertIn(index_name, constraints)
        self.assertEqual(constraints[index_name]["type"], GistIndex.suffix)
        self.assertEqual(constraints[index_name]["columns"], ["scene", "setting"])
        with connection.schema_editor() as editor:
            editor.remove_index(Scene, index)
        self.assertNotIn(index_name, self.get_constraints(Scene._meta.db_table))

    def test_tsvector_op_class_gist_index(self):
        """

        Tests the creation and removal of a GiST index on a tsvector op class, 
        specifically verifying the index's existence, type, and referenced columns.

        The test covers the following aspects:
        - Creates a GiST index on a tsvector op class using the 'english' configuration.
        - Verifies that the index is successfully added to the database schema.
        - Checks the index's type and ensures it references the expected columns.
        - Removes the index and confirms its removal from the database schema.

        """
        index_name = "tsvector_op_class_gist"
        index = GistIndex(
            OpClass(
                SearchVector("scene", "setting", config="english"),
                name="tsvector_ops",
            ),
            name=index_name,
        )
        with connection.schema_editor() as editor:
            editor.add_index(Scene, index)
            sql = index.create_sql(Scene, editor)
        table = Scene._meta.db_table
        constraints = self.get_constraints(table)
        self.assertIn(index_name, constraints)
        self.assertIn(constraints[index_name]["type"], GistIndex.suffix)
        self.assertIs(sql.references_column(table, "scene"), True)
        self.assertIs(sql.references_column(table, "setting"), True)
        with connection.schema_editor() as editor:
            editor.remove_index(Scene, index)
        self.assertNotIn(index_name, self.get_constraints(table))

    def test_search_vector(self):
        """SearchVector generates IMMUTABLE SQL in order to be indexable."""
        index_name = "test_search_vector"
        index = Index(SearchVector("id", "scene", config="english"), name=index_name)
        # Indexed function must be IMMUTABLE.
        with connection.schema_editor() as editor:
            editor.add_index(Scene, index)
        constraints = self.get_constraints(Scene._meta.db_table)
        self.assertIn(index_name, constraints)
        self.assertIs(constraints[index_name]["index"], True)

        with connection.schema_editor() as editor:
            editor.remove_index(Scene, index)
        self.assertNotIn(index_name, self.get_constraints(Scene._meta.db_table))

    def test_hash_index(self):
        # Ensure the table is there and doesn't have an index.
        """

        Tests the creation and removal of a hash index on a model field.

        Verifies that the hash index does not exist initially, creates the index,
        checks that the index has been successfully added, and then removes the index,
        confirming its removal. 

        The test covers the full lifecycle of a hash index, ensuring that it can be 
        properly added to and removed from a model's database table.

        """
        self.assertNotIn("field", self.get_constraints(CharFieldModel._meta.db_table))
        # Add the index.
        index_name = "char_field_model_field_hash"
        index = HashIndex(fields=["field"], name=index_name)
        with connection.schema_editor() as editor:
            editor.add_index(CharFieldModel, index)
        constraints = self.get_constraints(CharFieldModel._meta.db_table)
        # The index was added.
        self.assertEqual(constraints[index_name]["type"], HashIndex.suffix)
        # Drop the index.
        with connection.schema_editor() as editor:
            editor.remove_index(CharFieldModel, index)
        self.assertNotIn(
            index_name, self.get_constraints(CharFieldModel._meta.db_table)
        )

    def test_hash_parameters(self):
        """
        Tests the creation and removal of a hash index with custom parameters.

        This test case verifies that a hash index can be successfully added to a model
        with a specified fill factor, and that the index is correctly reflected in the
        database constraints. It also checks that the index can be removed without
        leaving any residual constraints.

        The test covers the following scenarios:
        - Creating a hash index with a custom fill factor
        - Verifying the index type and options in the database constraints
        - Removing the index and checking that it no longer exists in the constraints
        """
        index_name = "integer_array_hash_fillfactor"
        index = HashIndex(fields=["field"], name=index_name, fillfactor=80)
        with connection.schema_editor() as editor:
            editor.add_index(CharFieldModel, index)
        constraints = self.get_constraints(CharFieldModel._meta.db_table)
        self.assertEqual(constraints[index_name]["type"], HashIndex.suffix)
        self.assertEqual(constraints[index_name]["options"], ["fillfactor=80"])
        with connection.schema_editor() as editor:
            editor.remove_index(CharFieldModel, index)
        self.assertNotIn(
            index_name, self.get_constraints(CharFieldModel._meta.db_table)
        )

    def test_spgist_index(self):
        # Ensure the table is there and doesn't have an index.
        self.assertNotIn("field", self.get_constraints(TextFieldModel._meta.db_table))
        # Add the index.
        index_name = "text_field_model_field_spgist"
        index = SpGistIndex(fields=["field"], name=index_name)
        with connection.schema_editor() as editor:
            editor.add_index(TextFieldModel, index)
        constraints = self.get_constraints(TextFieldModel._meta.db_table)
        # The index was added.
        self.assertEqual(constraints[index_name]["type"], SpGistIndex.suffix)
        # Drop the index.
        with connection.schema_editor() as editor:
            editor.remove_index(TextFieldModel, index)
        self.assertNotIn(
            index_name, self.get_constraints(TextFieldModel._meta.db_table)
        )

    def test_spgist_parameters(self):
        """
        Tests the creation and removal of a SpGist index on a TextFieldModel with a specified fill factor.

        The function creates a SpGist index with the name 'text_field_model_spgist_fillfactor' and a fill factor of 80 on the 'field' column of the TextFieldModel table. 
        It then verifies that the index is correctly created by checking its type and options. 
        After verification, the index is removed and the function checks that it no longer exists in the table constraints.
        """
        index_name = "text_field_model_spgist_fillfactor"
        index = SpGistIndex(fields=["field"], name=index_name, fillfactor=80)
        with connection.schema_editor() as editor:
            editor.add_index(TextFieldModel, index)
        constraints = self.get_constraints(TextFieldModel._meta.db_table)
        self.assertEqual(constraints[index_name]["type"], SpGistIndex.suffix)
        self.assertEqual(constraints[index_name]["options"], ["fillfactor=80"])
        with connection.schema_editor() as editor:
            editor.remove_index(TextFieldModel, index)
        self.assertNotIn(
            index_name, self.get_constraints(TextFieldModel._meta.db_table)
        )

    def test_spgist_include(self):
        """
        Tests the creation and deletion of a SpGist index with include clause on the Scene model.

        Verifies that the index can be successfully added to the database, its properties are correctly defined,
        and that it can be removed without leaving any residual effects.

        The test case checks for the index existence, its type, and columns after creation, and its absence after deletion.
        """
        index_name = "scene_spgist_include_setting"
        index = SpGistIndex(name=index_name, fields=["scene"], include=["setting"])
        with connection.schema_editor() as editor:
            editor.add_index(Scene, index)
        constraints = self.get_constraints(Scene._meta.db_table)
        self.assertIn(index_name, constraints)
        self.assertEqual(constraints[index_name]["type"], SpGistIndex.suffix)
        self.assertEqual(constraints[index_name]["columns"], ["scene", "setting"])
        with connection.schema_editor() as editor:
            editor.remove_index(Scene, index)
        self.assertNotIn(index_name, self.get_constraints(Scene._meta.db_table))

    def test_custom_suffix(self):
        """
        Tests the customization of index suffixes in PostgreSQL indexes.

        This test case verifies that a custom suffix can be defined for an index and
        that it is correctly used when generating the SQL to create the index. The test
        covers the creation of a custom index class with a specified suffix and checks
        that the suffix is applied when creating the index SQL statement. It also
        confirms that the suffix is correctly set as an attribute of the index instance.
        """
        class CustomSuffixIndex(PostgresIndex):
            suffix = "sfx"

            def create_sql(self, model, schema_editor, using="gin", **kwargs):
                return super().create_sql(model, schema_editor, using=using, **kwargs)

        index = CustomSuffixIndex(fields=["field"], name="custom_suffix_idx")
        self.assertEqual(index.suffix, "sfx")
        with connection.schema_editor() as editor:
            self.assertIn(
                " USING gin ",
                str(index.create_sql(CharFieldModel, editor)),
            )

    def test_op_class(self):
        index_name = "test_op_class"
        index = Index(
            OpClass(Lower("field"), name="text_pattern_ops"),
            name=index_name,
        )
        with connection.schema_editor() as editor:
            editor.add_index(TextFieldModel, index)
        with editor.connection.cursor() as cursor:
            cursor.execute(self.get_opclass_query, [index_name])
            self.assertCountEqual(cursor.fetchall(), [("text_pattern_ops", index_name)])

    def test_op_class_descending_collation(self):
        """

        Tests creating a descending index with a case-insensitive collation on the TextFieldModel.

        Specifically, it checks that the index is correctly created with the non-default collation,
        and that it uses the 'text_pattern_ops' opclass in descending order with nulls last.

        The test includes verifying the index creation SQL, the index metadata in the database
        constraints, and that the index can be successfully removed.

        """
        collation = connection.features.test_collations.get("non_default")
        if not collation:
            self.skipTest("This backend does not support case-insensitive collations.")
        index_name = "test_op_class_descending_collation"
        index = Index(
            Collate(
                OpClass(Lower("field"), name="text_pattern_ops").desc(nulls_last=True),
                collation=collation,
            ),
            name=index_name,
        )
        with connection.schema_editor() as editor:
            editor.add_index(TextFieldModel, index)
            self.assertIn(
                "COLLATE %s" % editor.quote_name(collation),
                str(index.create_sql(TextFieldModel, editor)),
            )
        with editor.connection.cursor() as cursor:
            cursor.execute(self.get_opclass_query, [index_name])
            self.assertCountEqual(cursor.fetchall(), [("text_pattern_ops", index_name)])
        table = TextFieldModel._meta.db_table
        constraints = self.get_constraints(table)
        self.assertIn(index_name, constraints)
        self.assertEqual(constraints[index_name]["orders"], ["DESC"])
        with connection.schema_editor() as editor:
            editor.remove_index(TextFieldModel, index)
        self.assertNotIn(index_name, self.get_constraints(table))

    def test_op_class_descending_partial(self):
        """
        Tests the creation of a partial index with a descending order on a text pattern ops class.

        The test verifies that a partial index can be successfully added to a TextFieldModel
        instance, and that the index uses the 'text_pattern_ops' operator class to enable pattern
        matching queries on the indexed field. The index is created with a descending order,
        and the test checks that the index is correctly reflected in the database schema and
        constrains the data as expected.

        The test also confirms that the index can be retrieved from the database and that its
        properties, including the order, are correctly set.

        The test case covers creating a partial index with a specific operator class and order,
        and verifying its correctness through database queries and constraint checks.
        """
        index_name = "test_op_class_descending_partial"
        index = Index(
            OpClass(Lower("field"), name="text_pattern_ops").desc(),
            name=index_name,
            condition=Q(field__contains="China"),
        )
        with connection.schema_editor() as editor:
            editor.add_index(TextFieldModel, index)
        with editor.connection.cursor() as cursor:
            cursor.execute(self.get_opclass_query, [index_name])
            self.assertCountEqual(cursor.fetchall(), [("text_pattern_ops", index_name)])
        constraints = self.get_constraints(TextFieldModel._meta.db_table)
        self.assertIn(index_name, constraints)
        self.assertEqual(constraints[index_name]["orders"], ["DESC"])

    def test_op_class_descending_partial_tablespace(self):
        """
        <|reserved_special_token_116|>\"\"\"
        Tests creation of a descending partial tablespace index on a TextField model.

        Verifies that a tablespace index with the specified operator class is 
        successfully created and that the index definition includes the correct 
        tablespace and descending order specification. 

        The test checks the creation SQL statement, the actual operator class used 
        by the index, and the index constraints to ensure they match the expected 
        values.

        """
        index_name = "test_op_class_descending_partial_tablespace"
        index = Index(
            OpClass(Lower("field").desc(), name="text_pattern_ops"),
            name=index_name,
            condition=Q(field__contains="China"),
            db_tablespace="pg_default",
        )
        with connection.schema_editor() as editor:
            editor.add_index(TextFieldModel, index)
            self.assertIn(
                'TABLESPACE "pg_default" ',
                str(index.create_sql(TextFieldModel, editor)),
            )
        with editor.connection.cursor() as cursor:
            cursor.execute(self.get_opclass_query, [index_name])
            self.assertCountEqual(cursor.fetchall(), [("text_pattern_ops", index_name)])
        constraints = self.get_constraints(TextFieldModel._meta.db_table)
        self.assertIn(index_name, constraints)
        self.assertEqual(constraints[index_name]["orders"], ["DESC"])
