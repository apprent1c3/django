from unittest import mock

from django.conf import settings
from django.db import connection, models
from django.db.models.functions import Lower, Upper
from django.test import SimpleTestCase, TestCase, override_settings, skipUnlessDBFeature
from django.test.utils import isolate_apps

from .models import Book, ChildModel1, ChildModel2


class SimpleIndexesTests(SimpleTestCase):
    def test_suffix(self):
        self.assertEqual(models.Index.suffix, "idx")

    def test_repr(self):
        """
        Tests the string representation of various Index instances.

        This method verifies that the repr function correctly returns a string representation
        of Index objects, including those with single fields, named indexes, multiple fields,
        partial indexes, covering indexes, indexes with specific operator classes, function-based
        indexes, and indexes stored in specific tablespaces.

        The tests ensure that the repr output accurately reflects the attributes of each Index
        instance, including fields, name, condition, include, opclasses, and db_tablespace.

        """
        index = models.Index(fields=["title"])
        named_index = models.Index(fields=["title"], name="title_idx")
        multi_col_index = models.Index(fields=["title", "author"])
        partial_index = models.Index(
            fields=["title"], name="long_books_idx", condition=models.Q(pages__gt=400)
        )
        covering_index = models.Index(
            fields=["title"],
            name="include_idx",
            include=["author", "pages"],
        )
        opclasses_index = models.Index(
            fields=["headline", "body"],
            name="opclasses_idx",
            opclasses=["varchar_pattern_ops", "text_pattern_ops"],
        )
        func_index = models.Index(Lower("title"), "subtitle", name="book_func_idx")
        tablespace_index = models.Index(
            fields=["title"],
            db_tablespace="idx_tbls",
            name="book_tablespace_idx",
        )
        self.assertEqual(repr(index), "<Index: fields=['title']>")
        self.assertEqual(
            repr(named_index),
            "<Index: fields=['title'] name='title_idx'>",
        )
        self.assertEqual(repr(multi_col_index), "<Index: fields=['title', 'author']>")
        self.assertEqual(
            repr(partial_index),
            "<Index: fields=['title'] name='long_books_idx' "
            "condition=(AND: ('pages__gt', 400))>",
        )
        self.assertEqual(
            repr(covering_index),
            "<Index: fields=['title'] name='include_idx' "
            "include=('author', 'pages')>",
        )
        self.assertEqual(
            repr(opclasses_index),
            "<Index: fields=['headline', 'body'] name='opclasses_idx' "
            "opclasses=['varchar_pattern_ops', 'text_pattern_ops']>",
        )
        self.assertEqual(
            repr(func_index),
            "<Index: expressions=(Lower(F(title)), F(subtitle)) "
            "name='book_func_idx'>",
        )
        self.assertEqual(
            repr(tablespace_index),
            "<Index: fields=['title'] name='book_tablespace_idx' "
            "db_tablespace='idx_tbls'>",
        )

    def test_eq(self):
        """

        Tests the equality of Index instances.

        Checks that two Index instances are considered equal if they have the same fields,
        regardless of their order, and are associated with the same model.

        Also verifies that an Index instance is not equal to another Index instance with
        different fields, even if they are associated with the same model.

        This method ensures that the equality comparison of Index instances behaves as expected.

        """
        index = models.Index(fields=["title"])
        same_index = models.Index(fields=["title"])
        another_index = models.Index(fields=["title", "author"])
        index.model = Book
        same_index.model = Book
        another_index.model = Book
        self.assertEqual(index, same_index)
        self.assertEqual(index, mock.ANY)
        self.assertNotEqual(index, another_index)

    def test_eq_func(self):
        index = models.Index(Lower("title"), models.F("author"), name="book_func_idx")
        same_index = models.Index(Lower("title"), "author", name="book_func_idx")
        another_index = models.Index(Lower("title"), name="book_func_idx")
        self.assertEqual(index, same_index)
        self.assertEqual(index, mock.ANY)
        self.assertNotEqual(index, another_index)

    def test_index_fields_type(self):
        with self.assertRaisesMessage(
            ValueError, "Index.fields must be a list or tuple."
        ):
            models.Index(fields="title")

    def test_index_fields_strings(self):
        msg = "Index.fields must contain only strings with field names."
        with self.assertRaisesMessage(ValueError, msg):
            models.Index(fields=[models.F("title")])

    def test_fields_tuple(self):
        self.assertEqual(models.Index(fields=("title",)).fields, ["title"])

    def test_requires_field_or_expression(self):
        msg = "At least one field or expression is required to define an index."
        with self.assertRaisesMessage(ValueError, msg):
            models.Index()

    def test_expressions_and_fields_mutually_exclusive(self):
        """
        Verifies that Index expressions and fields are mutually exclusive.

        Checks that attempting to create an Index with both an expression and a list of fields raises a ValueError with an appropriate error message.

        The test ensures that Index initialization enforces the constraint that expressions and fields cannot be used together, promoting correct and consistent Index configuration.

        Args: None

        Returns: None

        Raises: ValueError if Index expressions and fields are used together.
        """
        msg = "Index.fields and expressions are mutually exclusive."
        with self.assertRaisesMessage(ValueError, msg):
            models.Index(Upper("foo"), fields=["field"])

    def test_opclasses_requires_index_name(self):
        """
        Tests that creating an index with opclasses requires a named index.

        Verifies that a ValueError is raised when attempting to create an index using opclasses
        without providing a name for the index. This ensures that opclasses, which are used to
        optimize index queries, are not applied to unnamed indexes, which could lead to incorrect
        or inefficient query execution. The test expects a specific error message indicating that
        an index name is required to use opclasses.
        """
        with self.assertRaisesMessage(
            ValueError, "An index must be named to use opclasses."
        ):
            models.Index(opclasses=["jsonb_path_ops"])

    def test_opclasses_requires_list_or_tuple(self):
        """
        Tests that creating an Index with opclasses specified as a single value raises a ValueError, ensuring that opclasses is either a list or tuple as required.
        """
        with self.assertRaisesMessage(
            ValueError, "Index.opclasses must be a list or tuple."
        ):
            models.Index(
                name="test_opclass", fields=["field"], opclasses="jsonb_path_ops"
            )

    def test_opclasses_and_fields_same_length(self):
        msg = "Index.fields and Index.opclasses must have the same number of elements."
        with self.assertRaisesMessage(ValueError, msg):
            models.Index(
                name="test_opclass",
                fields=["field", "other"],
                opclasses=["jsonb_path_ops"],
            )

    def test_condition_requires_index_name(self):
        """

        Tests that creating an Index instance with a condition requires a name to be specified.

        :raises ValueError: If no name is provided when creating an Index with a condition.

        """
        with self.assertRaisesMessage(
            ValueError, "An index must be named to use condition."
        ):
            models.Index(condition=models.Q(pages__gt=400))

    def test_expressions_requires_index_name(self):
        msg = "An index must be named to use expressions."
        with self.assertRaisesMessage(ValueError, msg):
            models.Index(Lower("field"))

    def test_expressions_with_opclasses(self):
        """
        Tests that using opclasses with expressions in Index objects raises a ValueError.

        When an expression, such as a database function, is used in an Index object,
        it is not compatible with the opclasses parameter. Instead, the OpClass class
        from django.contrib.postgres.indexes should be used to specify the opclass for 
        the expression in the index.

        Raises:
            ValueError: With a message indicating that Index.opclasses cannot be used with expressions.

        """
        msg = (
            "Index.opclasses cannot be used with expressions. Use "
            "django.contrib.postgres.indexes.OpClass() instead."
        )
        with self.assertRaisesMessage(ValueError, msg):
            models.Index(
                Lower("field"),
                name="test_func_opclass",
                opclasses=["jsonb_path_ops"],
            )

    def test_condition_must_be_q(self):
        """
        Tests that creating an Index with a non-Q condition raises a ValueError.

        Verifies that the `condition` parameter must be an instance of Q, ensuring that
        only valid query conditions are accepted.

        :raises ValueError: If `condition` is not a Q instance.

        """
        with self.assertRaisesMessage(
            ValueError, "Index.condition must be a Q instance."
        ):
            models.Index(condition="invalid", name="long_book_idx")

    def test_include_requires_list_or_tuple(self):
        msg = "Index.include must be a list or tuple."
        with self.assertRaisesMessage(ValueError, msg):
            models.Index(name="test_include", fields=["field"], include="other")

    def test_include_requires_index_name(self):
        """

        Verifies that creating an index with included fields requires an index name.

        This test case ensures that attempting to create a covering index without specifying
        a name raises a ValueError with a descriptive error message.

        """
        msg = "A covering index must be named."
        with self.assertRaisesMessage(ValueError, msg):
            models.Index(fields=["field"], include=["other"])

    def test_name_auto_generation(self):
        """

        Tests the automatic generation of names for database indexes in the context of the Book model.

        This test suite checks how index names are generated when the model and field names are used,
        including cases with descending order fields and long field names. It also verifies that an
        error is raised when the generated index name exceeds the maximum allowed length for
        multiple database support, considering any additional suffixes that may be applied.

        The expected naming convention is verified, including the use of a hashed value to ensure
        unique names. The test covers various scenarios, ensuring that the index name generation is
        correct and consistent, and that appropriate error messages are raised when necessary.

        """
        index = models.Index(fields=["author"])
        index.set_name_with_model(Book)
        self.assertEqual(index.name, "model_index_author_0f5565_idx")

        # '-' for DESC columns should be accounted for in the index name.
        index = models.Index(fields=["-author"])
        index.set_name_with_model(Book)
        self.assertEqual(index.name, "model_index_author_708765_idx")

        # fields may be truncated in the name. db_column is used for naming.
        long_field_index = models.Index(fields=["pages"])
        long_field_index.set_name_with_model(Book)
        self.assertEqual(long_field_index.name, "model_index_page_co_69235a_idx")

        # suffix can't be longer than 3 characters.
        long_field_index.suffix = "suff"
        msg = (
            "Index too long for multiple database support. Is self.suffix "
            "longer than 3 characters?"
        )
        with self.assertRaisesMessage(ValueError, msg):
            long_field_index.set_name_with_model(Book)

    @isolate_apps("model_indexes")
    def test_name_auto_generation_with_quoted_db_table(self):
        """

        Tests the automatic generation of index names when the database table name is quoted.

        This test case verifies that the index name is correctly generated when the model's
        database table name is enclosed in quotes. It checks that the generated index name
        follows the expected format and includes the quoted table name.

        The test covers the scenario where a model has a quoted database table name and
        an index is created on one of its fields. The expected index name is then compared
        with the actual generated name to ensure they match.

        """
        class QuotedDbTable(models.Model):
            name = models.CharField(max_length=50)

            class Meta:
                db_table = '"t_quoted"'

        index = models.Index(fields=["name"])
        index.set_name_with_model(QuotedDbTable)
        self.assertEqual(index.name, "t_quoted_name_e4ed1b_idx")

    def test_deconstruction(self):
        """
        Tests the deconstruction of a database index into its constituent parts.

        This test ensures that an :class:`~django.db.models.Index` instance can be properly
        broken down into its path, arguments, and keyword arguments, which can then be
        used to recreate the index.

        The test covers the validation of the deconstructed path, arguments, and keyword
        arguments, including the name of the index, which is automatically generated
        based on the associated model and field names.

        It verifies that the path points to the correct :class:`~django.db.models.Index`
        class, and that the keyword arguments include the correct field names, index
        name, and database tablespace.

        """
        index = models.Index(fields=["title"], db_tablespace="idx_tbls")
        index.set_name_with_model(Book)
        path, args, kwargs = index.deconstruct()
        self.assertEqual(path, "django.db.models.Index")
        self.assertEqual(args, ())
        self.assertEqual(
            kwargs,
            {
                "fields": ["title"],
                "name": "model_index_title_196f42_idx",
                "db_tablespace": "idx_tbls",
            },
        )

    def test_deconstruct_with_condition(self):
        index = models.Index(
            name="big_book_index",
            fields=["title"],
            condition=models.Q(pages__gt=400),
        )
        index.set_name_with_model(Book)
        path, args, kwargs = index.deconstruct()
        self.assertEqual(path, "django.db.models.Index")
        self.assertEqual(args, ())
        self.assertEqual(
            kwargs,
            {
                "fields": ["title"],
                "name": "model_index_title_196f42_idx",
                "condition": models.Q(pages__gt=400),
            },
        )

    def test_deconstruct_with_include(self):
        index = models.Index(
            name="book_include_idx",
            fields=["title"],
            include=["author"],
        )
        index.set_name_with_model(Book)
        path, args, kwargs = index.deconstruct()
        self.assertEqual(path, "django.db.models.Index")
        self.assertEqual(args, ())
        self.assertEqual(
            kwargs,
            {
                "fields": ["title"],
                "name": "model_index_title_196f42_idx",
                "include": ("author",),
            },
        )

    def test_deconstruct_with_expressions(self):
        """
        Tests the deconstruction of an Index instance with expressions.

        This test case ensures that an Index instance containing an expression, 
        such as Upper('title'), can be successfully deconstructed into its 
        constituent parts, including the path to the Index class, arguments, 
        and keyword arguments.

        The deconstruction process is verified by checking the path to the 
        Index class, the arguments (in this case, an Upper expression), and 
        the keyword arguments (such as the index name).

        The test passes if the deconstructed path, arguments, and keyword 
        arguments match the expected values, confirming the correct 
        deconstruction of the Index instance with expressions.

        """
        index = models.Index(Upper("title"), name="book_func_idx")
        path, args, kwargs = index.deconstruct()
        self.assertEqual(path, "django.db.models.Index")
        self.assertEqual(args, (Upper("title"),))
        self.assertEqual(kwargs, {"name": "book_func_idx"})

    def test_clone(self):
        """
        Tests the cloning functionality of an Index object.

        Verifies that a cloned Index object is a separate instance from the original,
        while still maintaining the same fields and properties. This ensures that 
        modifications made to the cloned index do not affect the original index.

        """
        index = models.Index(fields=["title"])
        new_index = index.clone()
        self.assertIsNot(index, new_index)
        self.assertEqual(index.fields, new_index.fields)

    def test_clone_with_expressions(self):
        """
        Test that cloning an index preserves its expression while creating a new index object.

        This test case verifies that the clone method of an index creates a new, independent index object, and that the cloned index has the same expressions as the original index.
        """
        index = models.Index(Upper("title"), name="book_func_idx")
        new_index = index.clone()
        self.assertIsNot(index, new_index)
        self.assertEqual(index.expressions, new_index.expressions)

    def test_name_set(self):
        """
        Tests that the Book model has the correct set of index names.

        Verifies that the index names match the expected names, ensuring that the database indexes are correctly defined for the Book model.

        Expected index names:
            - model_index_title_196f42_idx
            - model_index_isbn_34f975_idx
            - model_indexes_book_barcode_idx

        This check is crucial for maintaining the performance and data integrity of the database, as indexes play a significant role in query optimization and data retrieval speed.
        """
        index_names = [index.name for index in Book._meta.indexes]
        self.assertCountEqual(
            index_names,
            [
                "model_index_title_196f42_idx",
                "model_index_isbn_34f975_idx",
                "model_indexes_book_barcode_idx",
            ],
        )

    def test_abstract_children(self):
        index_names = [index.name for index in ChildModel1._meta.indexes]
        self.assertEqual(
            index_names,
            ["model_index_name_440998_idx", "model_indexes_childmodel1_idx"],
        )
        index_names = [index.name for index in ChildModel2._meta.indexes]
        self.assertEqual(
            index_names,
            ["model_index_name_b6c374_idx", "model_indexes_childmodel2_idx"],
        )


@override_settings(DEFAULT_TABLESPACE=None)
class IndexesTests(TestCase):
    @skipUnlessDBFeature("supports_tablespaces")
    def test_db_tablespace(self):
        """
        Tests the creation of indexes with specified tablespace.

        This test checks that indexes are created with the correct tablespace when 
        the db_tablespace parameter is provided. It also verifies that the 
        DEFAULT_INDEX_TABLESPACE setting is used when no tablespace is specified.

        The test covers different scenarios, including indexes with single and 
        multiple fields, to ensure that the correct tablespace is included in 
        the generated SQL. If no default tablespace is set, it checks that the 
        TABLESPACE clause is not included in the SQL. 

        The test requires a database that supports tablespaces. 

        The `Book` model is used as the base model for the index creation tests. 

        The test consists of two main parts: one that checks the creation of 
        indexes with specified tablespaces, and another that checks the usage 
        of the DEFAULT_INDEX_TABLESPACE setting. 

        The test uses the `schema_editor` to create the indexes and the 
        `create_sql` method to generate the SQL for the index creation. 

        The result of each test is verified by checking that the expected 
        tablespace is included in the generated SQL. 

        If the test fails, it may indicate that the database does not support 
        tablespaces, or that there is an issue with the index creation logic. 

        This test is decorated with `@skipUnlessDBFeature('supports_tablespaces')` 
        to ensure it is only run on databases that support tablespaces. 

        Additionally, subtests are used to group related test cases, making it 
        easier to identify the specific test that failed. 

        By running this test, you can ensure that your database correctly creates 
        indexes with the specified tablespace, and that the DEFAULT_INDEX_TABLESPACE 
        setting is used when no tablespace is provided. 

        If you encounter issues with this test, you may need to adjust your 
        database configuration or the index creation logic to ensure that 
        indexes are created correctly. 
        """
        editor = connection.schema_editor()
        # Index with db_tablespace attribute.
        for fields in [
            # Field with db_tablespace specified on model.
            ["shortcut"],
            # Field without db_tablespace specified on model.
            ["author"],
            # Multi-column with db_tablespaces specified on model.
            ["shortcut", "isbn"],
            # Multi-column without db_tablespace specified on model.
            ["title", "author"],
        ]:
            with self.subTest(fields=fields):
                index = models.Index(fields=fields, db_tablespace="idx_tbls2")
                self.assertIn(
                    '"idx_tbls2"', str(index.create_sql(Book, editor)).lower()
                )
        # Indexes without db_tablespace attribute.
        for fields in [["author"], ["shortcut", "isbn"], ["title", "author"]]:
            with self.subTest(fields=fields):
                index = models.Index(fields=fields)
                # The DEFAULT_INDEX_TABLESPACE setting can't be tested because
                # it's evaluated when the model class is defined. As a
                # consequence, @override_settings doesn't work.
                if settings.DEFAULT_INDEX_TABLESPACE:
                    self.assertIn(
                        '"%s"' % settings.DEFAULT_INDEX_TABLESPACE,
                        str(index.create_sql(Book, editor)).lower(),
                    )
                else:
                    self.assertNotIn("TABLESPACE", str(index.create_sql(Book, editor)))
        # Field with db_tablespace specified on the model and an index without
        # db_tablespace.
        index = models.Index(fields=["shortcut"])
        self.assertIn('"idx_tbls"', str(index.create_sql(Book, editor)).lower())

    @skipUnlessDBFeature("supports_tablespaces")
    def test_func_with_tablespace(self):
        # Functional index with db_tablespace attribute.
        """

        Tests the creation of a database index with a specified tablespace.

        The function verifies that the generated SQL for creating an index includes the
        specified tablespace name when provided. It also checks the default behavior when
        no tablespace is specified, ensuring that the default index tablespace setting is
        applied if available.

        The test case covers two scenarios:

        * Creating an index with an explicitly defined tablespace.
        * Creating an index without a specified tablespace, relying on the default setting.

        This test requires a database feature that supports tablespaces.

        """
        index = models.Index(
            Lower("shortcut").desc(),
            name="functional_tbls",
            db_tablespace="idx_tbls2",
        )
        with connection.schema_editor() as editor:
            sql = str(index.create_sql(Book, editor))
            self.assertIn(editor.quote_name("idx_tbls2"), sql)
        # Functional index without db_tablespace attribute.
        index = models.Index(Lower("shortcut").desc(), name="functional_no_tbls")
        with connection.schema_editor() as editor:
            sql = str(index.create_sql(Book, editor))
            # The DEFAULT_INDEX_TABLESPACE setting can't be tested because it's
            # evaluated when the model class is defined. As a consequence,
            # @override_settings doesn't work.
            if settings.DEFAULT_INDEX_TABLESPACE:
                self.assertIn(
                    editor.quote_name(settings.DEFAULT_INDEX_TABLESPACE),
                    sql,
                )
            else:
                self.assertNotIn("TABLESPACE", sql)
