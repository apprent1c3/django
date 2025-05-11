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
        """
        Tests the deconstruction of a database index into its path, arguments, and keyword arguments without any customization. Verifies that the deconstructed components match the expected values.
        """
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
        Verifies that the deconstruction of an index with an expression works as expected, without any customization, by checking the resulting path, arguments, and keyword arguments.
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
        """
        Tests the deconstruction of a BloomIndex instance into its constituent parts, verifying that the resulting path, arguments, and keyword arguments match the expected values.
        """
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
        Tests the validation of columns in a BloomIndex.

        Verifies that the columns parameter must be a list or tuple and that its length does not exceed the number of fields.
        """
        msg = "BloomIndex.columns must be a list or tuple."
        with self.assertRaisesMessage(ValueError, msg):
            BloomIndex(fields=["title"], name="test_bloom", columns="x")
        msg = "BloomIndex.columns cannot have more values than fields."
        with self.assertRaisesMessage(ValueError, msg):
            BloomIndex(fields=["title"], name="test_bloom", columns=[4, 3])

    def test_invalid_columns_value(self):
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
        Tests the deconstruction of a BrinIndex instance, verifying that its path, arguments, and keyword arguments are properly extracted.
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
        Tests deconstruction of a BTreeIndex, ensuring that its path and keyword arguments are correctly reconstructed.
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
        Tests the deconstruction of a GinIndex instance into its constituent path, arguments, and keyword arguments.
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
        """
        Tests the deconstruction of a GistIndex into its path, arguments, and keyword arguments.
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
        """
        Checks if the deconstruction of a HashIndex instance returns the expected path, arguments, and keyword arguments, ensuring correct serialization and deserialization of the index.
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
        Tests that the deconstruct method of SpGistIndex correctly breaks down the index into its path, arguments and keyword arguments.
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
        """
        Tests the addition and removal of a GIN index on the 'field' column of the IntegerArrayModel table.
        """
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
        Tests the creation and removal of a GiST index with fastupdate option disabled on an integer array field.
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
        Tests the creation and removal of a partial Gin index on a CharField with a custom condition
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
        Tests creation and removal of a partial GIN index on a specified field with a given tablespace.\"\"\"

        \"\"\" 
            Verifies that the index is created with the specified tablespace and that its type is correctly identified as 'gin'. 
            Also checks that the index is successfully removed and no longer exists in the database.

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
        """
        Tests the creation and removal of a GiST index with custom parameters.

        Verifies that the 'fastupdate' and 'gin_pending_list_limit' parameters are correctly applied and that the index is properly removed after creation.
        """
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
        Tests the creation and removal of a GIN index with a trigram operator class on the Scene model.\"\"\"

         Parameters
            ----------
            None

         Returns
            -------
            None

         Notes
            -----
            Verifies that the index is correctly added to and removed from the database schema.
            Confirms the index's operator class and type are as expected.
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
        """
        Tests the creation and removal of a GIN index on a search vector field using the GinIndex class.

        Verifies that the index is successfully added to the database table, that its type is correct, 
        and that the underlying SQL query references the correct column and uses the tsvector data type.

        Also checks that the index is properly removed from the database table after deletion.
        """
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

        Tests the creation and removal of a Bloom index with custom parameters.

        Verifies that a Bloom index with specified length and column options can be successfully added to and removed from a database table.

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
        """
        Tests the creation and removal of a BRIN index on a model field, verifying its type and options are correctly set.
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
        """
        Tests the creation and removal of a BRIN index with autosummarize option on a model field, verifying that the index is correctly generated in the database and its options are properly set.
        """
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
        Tests the creation and removal of a BTree index on a model's field.

        Verifies that the index is correctly added to and removed from the database schema,
        and that its type is correctly identified as a BTree index.
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
        Tests the creation and removal of a BTree index with custom parameters on a database table, verifying that the index type and options are correctly applied and reflected in the database schema.
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
        Tests the creation and removal of a GIST index on a model field.

        Verifies that the index is correctly added and removed from the database schema,
        and that its type is properly identified as a GIST index.
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
        Tests the creation and removal of a GiST index with custom buffering and fillfactor settings, verifying that the index is correctly added to and removed from the database schema.
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
        """
        Tests the creation and removal of a GiST index on the Scene model, verifying its presence and correctness in the database schema.
        """
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
        Tests the creation and removal of a GiST index on a tsvector operation class, verifying the index is correctly added and removed from the database schema.
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
        """
        Tests the creation and removal of a SearchVector index in the database, verifying that the index is properly added and removed, and that it is correctly identified as an index in the schema constraints.
        """
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

        Test the creation and removal of a hash index on a model field.

        This test case verifies that a hash index can be successfully added and removed
        from a model's database table, and that the index is correctly configured.

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
        Tests the creation and removal of a hash index with specified fill factor on a model field, verifying that the index is correctly created and its options are properly set in the database schema.
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
        """
        .Tests the creation and removal of a GiST index on a text field in the database.
        """
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
        Tests creation of an SpGist index on a model field with specified parameters.

        Verifies the index is created correctly with the given fillfactor and can be removed.

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

        Tests adding and removing a GIST index with an include clause to a database table.

        Verifies that the index is correctly created with the specified columns and type,
        and that it can be successfully removed from the table.

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
        Tests the functionality of creating a custom index with a specified suffix.\"\"\"

         \"\"\"Verifies the custom suffix is correctly applied and the index creation SQL uses the expected method.
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
        """
        Tests the creation of an OpClass index on a TextField, verifying it is successfully added and recognized by the database
        """
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
        Tests the creation and removal of a descending index with a non-default collation on a text field, verifying that the index uses the specified collation and ordering.
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
        -checks that a descending partial index using text pattern ops for a text field can be successfully created and its properties are correctly reflected in the database schema.
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
        Tests that an OpClass index with a descending order and partial tablespace is created correctly,
        covering its SQL creation, OpClass assignment, and constraint registration.
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
