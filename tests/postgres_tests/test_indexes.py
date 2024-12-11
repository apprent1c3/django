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

        Tests the deconstruction of an index class with expressions, without any customization.

        This test ensures that the index class can be properly deconstructed into its constituent parts,
        including the path to the index class, the positional arguments, and the keyword arguments.

        The deconstruction process is verified by checking that the resulting path, arguments, and keyword
        arguments match the expected values, including the class name and the provided name and expression.

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
        msg = "Bloom indexes support a maximum of 32 fields."
        with self.assertRaisesMessage(ValueError, msg):
            BloomIndex(fields=["title"] * 33, name="test_bloom")

    def test_invalid_columns(self):
        """
        Checks that BloomIndex.columns is valid. The columns must be a list or tuple and its length cannot exceed the number of fields. If the columns are invalid, this test ensures that a ValueError is raised with a descriptive error message.
        """
        msg = "BloomIndex.columns must be a list or tuple."
        with self.assertRaisesMessage(ValueError, msg):
            BloomIndex(fields=["title"], name="test_bloom", columns="x")
        msg = "BloomIndex.columns cannot have more values than fields."
        with self.assertRaisesMessage(ValueError, msg):
            BloomIndex(fields=["title"], name="test_bloom", columns=[4, 3])

    def test_invalid_columns_value(self):
        """
        Tests that invalid column values for BloomIndex raise a ValueError.

        Verifies that a ValueError is raised when the columns value is outside the
        valid range of 1 to 4095, specifically testing for values of 0 and 4096.

        Raises:
            ValueError: If the columns value is not within the valid range.

        """
        msg = "BloomIndex.columns must contain integers from 1 to 4095."
        for length in (0, 4096):
            with self.subTest(length), self.assertRaisesMessage(ValueError, msg):
                BloomIndex(fields=["title"], name="test_bloom", columns=[length])

    def test_invalid_length(self):
        msg = "BloomIndex.length must be None or an integer from 1 to 4096."
        for length in (0, 4097):
            with self.subTest(length), self.assertRaisesMessage(ValueError, msg):
                BloomIndex(fields=["title"], name="test_bloom", length=length)


class BrinIndexTests(IndexTestMixin, PostgreSQLSimpleTestCase):
    index_class = BrinIndex

    def test_suffix(self):
        self.assertEqual(BrinIndex.suffix, "brin")

    def test_deconstruction(self):
        """
        Tests the deconstruction of a BrinIndex instance into its constituent parts.

        The deconstruction process breaks down the index into a path, positional arguments, and keyword arguments, 
        which can be used to reconstruct the index. This function verifies that the deconstruction is performed correctly,
        ensuring that the resulting path and arguments accurately represent the original index.

        The test case checks the deconstruction of a BrinIndex with a single field, autosummarization, and a specified 
        range size, validating the output against the expected path, positional arguments, and keyword arguments.
        """
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
        """
        Tests that creating a BrinIndex with an invalid pages_per_range value raises a ValueError. 
        The pages_per_range parameter must be either None or a positive integer; otherwise, 
        an error is raised to prevent the creation of an invalid index configuration.
        """
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
        Deconstructs a BTreeIndex instance into its constituent parts, consisting of the path to the index class, and arguments and keyword arguments used to construct it. The deconstruction process breaks down the index into its essential components, including the index class, fields, name, and optional parameters such as fillfactor and deduplicate_items. This allows for the index to be recreated or serialized, making it useful for saving or loading index configurations. The returned values include the path to the BTreeIndex class, and dictionaries of keyword arguments used to instantiate the index.
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
        """
        Deconstructs a GinIndex instance into its constituent parts.

        This method breaks down the index into a path, positional arguments, and keyword arguments. The path represents the full import path of the GinIndex class. The positional arguments are empty in this case. The keyword arguments include the fields, name, fastupdate, and gin_pending_list_limit parameters used to create the GinIndex instance.

        Returns:
            tuple: A tuple containing the path, args, and kwargs of the deconstructed GinIndex instance.
        """
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
        """

        Tests the deconstruction of a HashIndex instance into its path, arguments, and keyword arguments.

        The deconstruction process breaks down the HashIndex instance into its constituent parts, 
        allowing for serialization or reconstruction of the index. This test verifies that the 
        deconstruction results in the expected path, arguments, and keyword arguments.

        """
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
        """
        Tests the deconstruction of a SpGistIndex instance.

        Verifies that the deconstruct method correctly breaks down the index into its constituent parts,
        including the path to the class, positional arguments, and keyword arguments. This ensures that the
        index can be properly serialized and recreated in other contexts, such as in database migrations.

        """
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

        Test the creation and removal of a partial GIN index on a CharField.

        This test case verifies the functionality of a partial GIN index, 
        which is a type of index that is applied to a subset of data in a table, 
        based on a specific condition. In this case, the condition is that 
        the length of the 'field' column is 40 characters.

        The test adds a GIN index with the specified condition to the model, 
        verifies that the index is created successfully, and then removes it.

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
        """

        Tests the creation and removal of a BRIN index.

        This test case verifies that a BRIN index can be successfully added to a model and
        later removed. It checks the index properties, including the index type and options,
        to ensure they match the expected values.

        The test uses a CharFieldModel and creates a BRIN index on one of its fields with
        a specified name and pages per range. The index is then added and removed from the
        database using a schema editor, and the constraints are checked after each operation
        to confirm the index has been correctly added or removed.

        """
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

        Tests the creation and removal of a GIST index on a model's field.

        This function ensures that a GIST index can be successfully added to and removed from
        a model's database table. It verifies the index's existence and type before and after
        its creation and removal.

        The testing process involves the following steps:

        - Checks if the index does not initially exist on the model's field.
        - Creates a new GIST index on the field and verifies its successful creation.
        - Removes the GIST index and confirms its removal.

        The function uses a schema editor to interact with the database schema, ensuring that
        the changes are properly committed or rolled back.

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

        This test case verifies that a GIST index can be successfully added to a model
        with buffering enabled and a custom fill factor, and that the index is correctly
        removed afterwards. It checks that the index's type and options are correctly
        set and reflected in the database constraints.

        The test covers the following scenarios:
        - Creating a GIST index with buffering and a custom fill factor
        - Verifying the index's type and options in the database constraints
        - Removing the index and verifying its absence in the database constraints
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

        Tests the creation and removal of a GiST index on a tsvector operation class.

        This test case checks the following:
        - That a GiST index can be successfully added to a model.
        - That the index is correctly created in the database.
        - That the index references the expected columns.
        - That the index can be successfully removed from the model.

        The test uses the Scene model and creates a GiST index on a tsvector operation class
        covering the 'scene' and 'setting' fields with the 'english' configuration.

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

        Test the creation and removal of a SpGist index with included fields.

        This test case verifies that a SpGist index can be successfully added to a model,
        that the index is correctly defined with the specified fields and included fields,
        and that the index can be removed without leaving any residual effects.

        The test creates a SpGist index on the 'scene' field of the Scene model, including
        the 'setting' field, and checks that the index is properly created and removed.

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

            Test that a custom suffix can be applied to a PostgresIndex.

            This test case verifies that a custom suffix is correctly set and used when
            creating the SQL for the index. It checks that the suffix is included in
            the generated SQL and that it matches the expected value.

            The test creates a custom index class with a specified suffix and then
            instantiates an index object using this class. It then checks the suffix
            property of the index object and verifies that the suffix is included in
            the generated SQL.

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
