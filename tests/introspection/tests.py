from django.db import DatabaseError, connection
from django.db.models import Index
from django.test import TransactionTestCase, skipUnlessDBFeature

from .models import (
    Article,
    ArticleReporter,
    CheckConstraintModel,
    City,
    Comment,
    Country,
    DbCommentModel,
    District,
    Reporter,
    UniqueConstraintConditionModel,
)


class IntrospectionTests(TransactionTestCase):
    available_apps = ["introspection"]

    def test_table_names(self):
        tl = connection.introspection.table_names()
        self.assertEqual(tl, sorted(tl))
        self.assertIn(
            Reporter._meta.db_table,
            tl,
            "'%s' isn't in table_list()." % Reporter._meta.db_table,
        )
        self.assertIn(
            Article._meta.db_table,
            tl,
            "'%s' isn't in table_list()." % Article._meta.db_table,
        )

    def test_django_table_names(self):
        """

        Tests the django_table_names function to ensure it only returns Django model table names.

        This test creates a temporary non-Django table, checks that its name is not included in the list of table names returned by django_table_names, and then drops the temporary table.

        The purpose of this test is to verify that the django_table_names function correctly filters out non-Django tables, ensuring that only relevant table names are returned.

        """
        with connection.cursor() as cursor:
            cursor.execute("CREATE TABLE django_ixn_test_table (id INTEGER);")
            tl = connection.introspection.django_table_names()
            cursor.execute("DROP TABLE django_ixn_test_table;")
            self.assertNotIn(
                "django_ixn_test_table",
                tl,
                "django_table_names() returned a non-Django table",
            )

    def test_django_table_names_retval_type(self):
        # Table name is a list #15216
        """
        Tests the return value type of django_table_names function.

        This test case verifies that the django_table_names function returns a list, 
        regardless of whether only existing tables are considered or not. It ensures 
        the function's return type consistency, making it reliable for further processing 
        or manipulation of the table names in the application.
        """
        tl = connection.introspection.django_table_names(only_existing=True)
        self.assertIs(type(tl), list)
        tl = connection.introspection.django_table_names(only_existing=False)
        self.assertIs(type(tl), list)

    def test_table_names_with_views(self):
        """
        ..: Test that the introspection API correctly identifies table names, including views.

            This test checks if the introspection API can list views when requested to do so, 
            by creating a temporary view, checking if it is included in the list of table names 
            when views are explicitly included, and then verifying it is excluded when views are not included.
            If the test user does not have the necessary privileges to create a view, 
            the test will fail and provide a corresponding error message.
            After the test is complete, the temporary view is dropped to clean up the database.
        """
        with connection.cursor() as cursor:
            try:
                cursor.execute(
                    "CREATE VIEW introspection_article_view AS SELECT headline "
                    "from introspection_article;"
                )
            except DatabaseError as e:
                if "insufficient privileges" in str(e):
                    self.fail("The test user has no CREATE VIEW privileges")
                else:
                    raise
        try:
            self.assertIn(
                "introspection_article_view",
                connection.introspection.table_names(include_views=True),
            )
            self.assertNotIn(
                "introspection_article_view", connection.introspection.table_names()
            )
        finally:
            with connection.cursor() as cursor:
                cursor.execute("DROP VIEW introspection_article_view")

    def test_unmanaged_through_model(self):
        """

        Verifies that the ArticleReporter model is not managed by Django's database operations.

        This test checks if the database table associated with the ArticleReporter model
        does not exist in the list of tables managed by Django, confirming that it is an
        unmanaged model.

        """
        tables = connection.introspection.django_table_names()
        self.assertNotIn(ArticleReporter._meta.db_table, tables)

    def test_installed_models(self):
        """
        ..: Tests that the Article and Reporter models are correctly installed in the database.

            This test case verifies the presence of the Article and Reporter models 
            by introspecting the database tables and comparing the installed models 
            with the expected set of models.
        """
        tables = [Article._meta.db_table, Reporter._meta.db_table]
        models = connection.introspection.installed_models(tables)
        self.assertEqual(models, {Article, Reporter})

    def test_sequence_list(self):
        sequences = connection.introspection.sequence_list()
        reporter_seqs = [
            seq for seq in sequences if seq["table"] == Reporter._meta.db_table
        ]
        self.assertEqual(
            len(reporter_seqs), 1, "Reporter sequence not found in sequence_list()"
        )
        self.assertEqual(reporter_seqs[0]["column"], "id")

    def test_get_table_description_names(self):
        """
        Tests that the names of the columns in the Reporter table match the names specified in the model's fields.

        Verifies the integrity of the database table schema by comparing the column names 
        retrieved from the database with the field names defined in the Reporter model.
        This ensures that the model's configuration accurately reflects the underlying table structure.
        """
        with connection.cursor() as cursor:
            desc = connection.introspection.get_table_description(
                cursor, Reporter._meta.db_table
            )
        self.assertEqual(
            [r[0] for r in desc], [f.column for f in Reporter._meta.fields]
        )

    def test_get_table_description_types(self):
        """

        Tests the retrieval of table description types for the Reporter model.

        Verifies that the introspected field types for the Reporter model's database table
        match the expected field types. This check ensures that the database table schema
        is correctly defined and that the Django ORM is properly configured to interact
        with the table.

        """
        with connection.cursor() as cursor:
            desc = connection.introspection.get_table_description(
                cursor, Reporter._meta.db_table
            )
        self.assertEqual(
            [connection.introspection.get_field_type(r[1], r) for r in desc],
            [
                connection.features.introspected_field_types[field]
                for field in (
                    "AutoField",
                    "CharField",
                    "CharField",
                    "CharField",
                    "BigIntegerField",
                    "BinaryField",
                    "SmallIntegerField",
                    "DurationField",
                )
            ],
        )

    def test_get_table_description_col_lengths(self):
        with connection.cursor() as cursor:
            desc = connection.introspection.get_table_description(
                cursor, Reporter._meta.db_table
            )
        self.assertEqual(
            [
                r[2]
                for r in desc
                if connection.introspection.get_field_type(r[1], r) == "CharField"
            ],
            [30, 30, 254],
        )

    def test_get_table_description_nullable(self):
        """
        Tests whether the get_table_description method correctly identifies nullable columns in the Reporter table.

        Verifies that the nullability of each column matches the expected values, taking into account the database backend's interpretation of empty strings as nulls.

        The test checks all columns in the Reporter table, considering the specific nullability rules for each column, and ensures that the results from the get_table_description method match the expected values.
        """
        with connection.cursor() as cursor:
            desc = connection.introspection.get_table_description(
                cursor, Reporter._meta.db_table
            )
        nullable_by_backend = connection.features.interprets_empty_strings_as_nulls
        self.assertEqual(
            [r[6] for r in desc],
            [
                False,
                nullable_by_backend,
                nullable_by_backend,
                nullable_by_backend,
                True,
                True,
                False,
                False,
            ],
        )

    def test_bigautofield(self):
        """
        Tests the presence of a BigAutoField in the City model's corresponding database table.

        This test case verifies whether the BigAutoField is correctly introspected from the 
        database table description. It checks if the BigAutoField type is included in the 
        list of field types obtained from the database table description.

        The test ensures compatibility between the Django model definition and the 
        underlying database schema, specifically for BigAutoField instances.\"\"\"]
        """
        with connection.cursor() as cursor:
            desc = connection.introspection.get_table_description(
                cursor, City._meta.db_table
            )
        self.assertIn(
            connection.features.introspected_field_types["BigAutoField"],
            [connection.introspection.get_field_type(r[1], r) for r in desc],
        )

    def test_smallautofield(self):
        """
        Checks if the database introspection correctly identifies a SmallAutoField in the Country model's table.

        The test verifies that the introspected field types for the table match the expected SmallAutoField type, ensuring that the database connection can accurately identify and report this field type.
        """
        with connection.cursor() as cursor:
            desc = connection.introspection.get_table_description(
                cursor, Country._meta.db_table
            )
        self.assertIn(
            connection.features.introspected_field_types["SmallAutoField"],
            [connection.introspection.get_field_type(r[1], r) for r in desc],
        )

    @skipUnlessDBFeature("supports_comments")
    def test_db_comments(self):
        with connection.cursor() as cursor:
            desc = connection.introspection.get_table_description(
                cursor, DbCommentModel._meta.db_table
            )
            table_list = connection.introspection.get_table_list(cursor)
        self.assertEqual(
            ["'Name' column comment"],
            [field.comment for field in desc if field.name == "name"],
        )
        self.assertEqual(
            ["Custom table comment"],
            [
                table.comment
                for table in table_list
                if table.name == "introspection_dbcommentmodel"
            ],
        )

    # Regression test for #9991 - 'real' types in postgres
    @skipUnlessDBFeature("has_real_datatype")
    def test_postgresql_real_type(self):
        """
        Tests the PostgreSQL real data type by creating a table, introspecting its columns, and verifying that the 'REAL' type is correctly mapped to a 'FloatField'.\"\"\"

        \"\"\" 
            Verifies that the database introspection correctly handles the PostgreSQL 'REAL' data type.

            This test case checks that when a table with a 'REAL' column is created, 
            the introspection mechanism returns a 'FloatField' as the corresponding field type.

            The test covers the following scenario:
            - Creation of a test table with a 'REAL' column
            - Introspection of the created table to retrieve column descriptions
            - Verification that the 'REAL' column is correctly mapped to a 'FloatField'
            - Cleanup by dropping the test table

            This test is skipped unless the database has a 'REAL' data type.

        """
        with connection.cursor() as cursor:
            cursor.execute("CREATE TABLE django_ixn_real_test_table (number REAL);")
            desc = connection.introspection.get_table_description(
                cursor, "django_ixn_real_test_table"
            )
            cursor.execute("DROP TABLE django_ixn_real_test_table;")
        self.assertEqual(
            connection.introspection.get_field_type(desc[0][1], desc[0]), "FloatField"
        )

    @skipUnlessDBFeature("can_introspect_foreign_keys")
    def test_get_relations(self):
        with connection.cursor() as cursor:
            relations = connection.introspection.get_relations(
                cursor, Article._meta.db_table
            )

        # That's {field_name: (field_name_other_table, other_table)}
        expected_relations = {
            "reporter_id": ("id", Reporter._meta.db_table),
            "response_to_id": ("id", Article._meta.db_table),
        }
        self.assertEqual(relations, expected_relations)

        # Removing a field shouldn't disturb get_relations (#17785)
        body = Article._meta.get_field("body")
        with connection.schema_editor() as editor:
            editor.remove_field(Article, body)
        with connection.cursor() as cursor:
            relations = connection.introspection.get_relations(
                cursor, Article._meta.db_table
            )
        with connection.schema_editor() as editor:
            editor.add_field(Article, body)
        self.assertEqual(relations, expected_relations)

    def test_get_primary_key_column(self):
        """

        Test retrieving the primary key columns for Article and District tables.

        Checks that the primary key column names for the specified tables match the expected values.
        The test verifies the primary key column for the Article table is 'id' and for the District table is 'city_id'.

        """
        with connection.cursor() as cursor:
            primary_key_column = connection.introspection.get_primary_key_column(
                cursor, Article._meta.db_table
            )
            pk_fk_column = connection.introspection.get_primary_key_column(
                cursor, District._meta.db_table
            )
        self.assertEqual(primary_key_column, "id")
        self.assertEqual(pk_fk_column, "city_id")

    def test_get_constraints_index_types(self):
        """

         Tests the retrieval of constraints index types from the database.

         This test case verifies that the constraints index types for the Article model
         are correctly retrieved and match the expected index suffix type.

         The test checks the constraints for two specific column combinations:
         - 'headline' and 'pub_date'
         - 'headline', 'response_to_id', 'pub_date', and 'reporter_id'

         It then asserts that the index types for these constraints are correctly set
         to the Index suffix type.

        """
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(
                cursor, Article._meta.db_table
            )
        index = {}
        index2 = {}
        for val in constraints.values():
            if val["columns"] == ["headline", "pub_date"]:
                index = val
            if val["columns"] == [
                "headline",
                "response_to_id",
                "pub_date",
                "reporter_id",
            ]:
                index2 = val
        self.assertEqual(index["type"], Index.suffix)
        self.assertEqual(index2["type"], Index.suffix)

    @skipUnlessDBFeature("supports_index_column_ordering")
    def test_get_constraints_indexes_orders(self):
        """
        Indexes have the 'orders' key with a list of 'ASC'/'DESC' values.
        """
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(
                cursor, Article._meta.db_table
            )
        indexes_verified = 0
        expected_columns = [
            ["headline", "pub_date"],
            ["headline", "response_to_id", "pub_date", "reporter_id"],
        ]
        if connection.features.indexes_foreign_keys:
            expected_columns += [
                ["reporter_id"],
                ["response_to_id"],
            ]
        for val in constraints.values():
            if val["index"] and not (val["primary_key"] or val["unique"]):
                self.assertIn(val["columns"], expected_columns)
                self.assertEqual(val["orders"], ["ASC"] * len(val["columns"]))
                indexes_verified += 1
        self.assertEqual(indexes_verified, len(expected_columns))

    @skipUnlessDBFeature("supports_index_column_ordering", "supports_partial_indexes")
    def test_get_constraints_unique_indexes_orders(self):
        """

        Tests retrieval of unique index constraints and their column ordering.

        Verifies that the introspection mechanism correctly identifies and returns
        unique index constraints, including their names, affected columns, and
        ordering rules. Specifically, it checks that a constraint named
        'cond_name_without_color_uniq' is detected, marked as unique, and applied
        to the 'name' column with an ascending ordering. 

        This test requires the database backend to support index column ordering and
        partial indexes.

        """
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(
                cursor,
                UniqueConstraintConditionModel._meta.db_table,
            )
        self.assertIn("cond_name_without_color_uniq", constraints)
        constraint = constraints["cond_name_without_color_uniq"]
        self.assertIs(constraint["unique"], True)
        self.assertEqual(constraint["columns"], ["name"])
        self.assertEqual(constraint["orders"], ["ASC"])

    def test_get_constraints(self):
        def assertDetails(
            details,
            cols,
            primary_key=False,
            unique=False,
            index=False,
            check=False,
            foreign_key=None,
        ):
            # Different backends have different values for same constraints:
            #               PRIMARY KEY     UNIQUE CONSTRAINT    UNIQUE INDEX
            # MySQL      pk=1 uniq=1 idx=1  pk=0 uniq=1 idx=1  pk=0 uniq=1 idx=1
            # PostgreSQL pk=1 uniq=1 idx=0  pk=0 uniq=1 idx=0  pk=0 uniq=1 idx=1
            # SQLite     pk=1 uniq=0 idx=0  pk=0 uniq=1 idx=0  pk=0 uniq=1 idx=1
            """
            Asserts that the provided details match the expected column properties.

            Args:
                details (dict): The details to verify, containing column properties.
                cols (list): The expected columns.
                primary_key (bool, optional): Whether the column is a primary key. Defaults to False.
                unique (bool, optional): Whether the column has a unique constraint. Defaults to False.
                index (bool, optional): Whether the column has an index. Defaults to False.
                check (bool, optional): Whether the column has a check constraint. Defaults to False.
                foreign_key (any, optional): The foreign key constraint, if any. Defaults to None.

            This function checks the details of a column against the specified properties, 
            ensuring that primary key, unique, index, check, and foreign key constraints 
            are correctly set, and that the column names match the provided list. 
            Note that primary key implies unique, and unique implies no index. 
            All assertions must pass for the function to succeed.
            """
            if details["primary_key"]:
                details["unique"] = True
            if details["unique"]:
                details["index"] = False
            self.assertEqual(details["columns"], cols)
            self.assertEqual(details["primary_key"], primary_key)
            self.assertEqual(details["unique"], unique)
            self.assertEqual(details["index"], index)
            self.assertEqual(details["check"], check)
            self.assertEqual(details["foreign_key"], foreign_key)

        # Test custom constraints
        custom_constraints = {
            "article_email_pub_date_uniq",
            "email_pub_date_idx",
        }
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(
                cursor, Comment._meta.db_table
            )
            if (
                connection.features.supports_column_check_constraints
                and connection.features.can_introspect_check_constraints
            ):
                constraints.update(
                    connection.introspection.get_constraints(
                        cursor, CheckConstraintModel._meta.db_table
                    )
                )
                custom_constraints.add("up_votes_gte_0_check")
                assertDetails(
                    constraints["up_votes_gte_0_check"], ["up_votes"], check=True
                )
        assertDetails(
            constraints["article_email_pub_date_uniq"],
            ["article_id", "email", "pub_date"],
            unique=True,
        )
        assertDetails(
            constraints["email_pub_date_idx"], ["email", "pub_date"], index=True
        )
        # Test field constraints
        field_constraints = set()
        for name, details in constraints.items():
            if name in custom_constraints:
                continue
            elif details["columns"] == ["up_votes"] and details["check"]:
                assertDetails(details, ["up_votes"], check=True)
                field_constraints.add(name)
            elif details["columns"] == ["voting_number"] and details["check"]:
                assertDetails(details, ["voting_number"], check=True)
                field_constraints.add(name)
            elif details["columns"] == ["ref"] and details["unique"]:
                assertDetails(details, ["ref"], unique=True)
                field_constraints.add(name)
            elif details["columns"] == ["voting_number"] and details["unique"]:
                assertDetails(details, ["voting_number"], unique=True)
                field_constraints.add(name)
            elif details["columns"] == ["article_id"] and details["index"]:
                assertDetails(details, ["article_id"], index=True)
                field_constraints.add(name)
            elif details["columns"] == ["id"] and details["primary_key"]:
                assertDetails(details, ["id"], primary_key=True, unique=True)
                field_constraints.add(name)
            elif details["columns"] == ["article_id"] and details["foreign_key"]:
                assertDetails(
                    details, ["article_id"], foreign_key=("introspection_article", "id")
                )
                field_constraints.add(name)
            elif details["check"]:
                # Some databases (e.g. Oracle) include additional check
                # constraints.
                field_constraints.add(name)
        # All constraints are accounted for.
        self.assertEqual(
            constraints.keys() ^ (custom_constraints | field_constraints), set()
        )
