from django.apps import apps
from django.conf import settings
from django.db import connection
from django.test import TransactionTestCase, skipIfDBFeature, skipUnlessDBFeature

from .models.tablespaces import (
    Article,
    ArticleRef,
    Authors,
    Reviewers,
    Scientist,
    ScientistRef,
)


def sql_for_table(model):
    """
    Generates the SQL command required to create a database table for the given model.

    This function emulates the creation of a database table by the model, capturing the SQL command that would be executed. 
    It returns the SQL command as a string, allowing for examination or further processing of the generated SQL.

    :param model: The model for which the SQL command should be generated.
    :return: The SQL command to create the table for the given model as a string.

    """
    with connection.schema_editor(collect_sql=True) as editor:
        editor.create_model(model)
    return editor.collected_sql[0]


def sql_for_index(model):
    return "\n".join(
        str(sql) for sql in connection.schema_editor()._model_indexes_sql(model)
    )


# We can't test the DEFAULT_TABLESPACE and DEFAULT_INDEX_TABLESPACE settings
# because they're evaluated when the model class is defined. As a consequence,
# @override_settings doesn't work, and the tests depend
class TablespacesTests(TransactionTestCase):
    available_apps = ["model_options"]

    def setUp(self):
        # The unmanaged models need to be removed after the test in order to
        # prevent bad interactions with the flush operation in other tests.
        self._old_models = apps.app_configs["model_options"].models.copy()

        for model in Article, Authors, Reviewers, Scientist:
            model._meta.managed = True

    def tearDown(self):
        """
        Teardown method to restore the original state of the application after a test.

        This method reverses the modifications made to the database models and application configurations.
        It disables model management for specific models and resets the application's model configurations to their original state.
        Additionally, it clears the application's cache to ensure a clean slate for subsequent tests.
        This method is typically called after a test to prevent any side effects from interfering with other tests.
        """
        for model in Article, Authors, Reviewers, Scientist:
            model._meta.managed = False

        apps.app_configs["model_options"].models = self._old_models
        apps.all_models["model_options"] = self._old_models
        apps.clear_cache()

    def assertNumContains(self, haystack, needle, count):
        """
        Verifies that a given substring appears a specified number of times within a larger string.

        Args:
            haystack (str): The string to search within.
            needle (str): The substring to search for.
            count (int): The expected number of occurrences of the substring.

        Raises:
            AssertionError: If the actual number of occurrences does not match the expected count.

        Note:
            This method is useful for testing the presence and frequency of specific patterns within strings, 
            such as substrings, phrases, or keywords.

        """
        real_count = haystack.count(needle)
        self.assertEqual(
            real_count,
            count,
            "Found %d instances of '%s', expected %d" % (real_count, needle, count),
        )

    @skipUnlessDBFeature("supports_tablespaces")
    def test_tablespace_for_model(self):
        """

        Tests whether the tablespace for a model is correctly generated in the SQL query.

        This test checks if the SQL query for creating a table includes the default index
        tablespace as specified in the settings. If a default index tablespace is defined,
        it verifies that the query contains the tablespace name only once. If no default
        index tablespace is defined, it checks that the query contains a generic
        tablespace name twice.

        The test uses the :class:`Scientist` model as an example to generate the SQL
        query and asserts that the query contains the expected tablespace name or count.

        """
        sql = sql_for_table(Scientist).lower()
        if settings.DEFAULT_INDEX_TABLESPACE:
            # 1 for the table
            self.assertNumContains(sql, "tbl_tbsp", 1)
            # 1 for the index on the primary key
            self.assertNumContains(sql, settings.DEFAULT_INDEX_TABLESPACE, 1)
        else:
            # 1 for the table + 1 for the index on the primary key
            self.assertNumContains(sql, "tbl_tbsp", 2)

    @skipIfDBFeature("supports_tablespaces")
    def test_tablespace_ignored_for_model(self):
        # No tablespace-related SQL
        self.assertEqual(sql_for_table(Scientist), sql_for_table(ScientistRef))

    @skipUnlessDBFeature("supports_tablespaces")
    def test_tablespace_for_indexed_field(self):
        """

        Tests the functionality of setting the tablespace for an indexed field.

        This test case checks if the tablespace for an indexed field is correctly set in the SQL query.
        It verifies that the default index tablespace, as specified in the settings, is used in the query.
        The test covers two scenarios: when a default index tablespace is specified and when it is not.
        It asserts that the tablespace names ('tbl_tbsp' and 'idx_tbsp') appear the expected number of times in the SQL query.

        """
        sql = sql_for_table(Article).lower()
        if settings.DEFAULT_INDEX_TABLESPACE:
            # 1 for the table
            self.assertNumContains(sql, "tbl_tbsp", 1)
            # 1 for the primary key + 1 for the index on code
            self.assertNumContains(sql, settings.DEFAULT_INDEX_TABLESPACE, 2)
        else:
            # 1 for the table + 1 for the primary key + 1 for the index on code
            self.assertNumContains(sql, "tbl_tbsp", 3)

        # 1 for the index on reference
        self.assertNumContains(sql, "idx_tbsp", 1)

    @skipIfDBFeature("supports_tablespaces")
    def test_tablespace_ignored_for_indexed_field(self):
        # No tablespace-related SQL
        self.assertEqual(sql_for_table(Article), sql_for_table(ArticleRef))

    @skipUnlessDBFeature("supports_tablespaces")
    def test_tablespace_for_many_to_many_field(self):
        """

        Tests the tablespace configuration for many-to-many fields in the database.

        Verifies that the correct tablespaces are used for tables and indexes, taking into account the 
        DEFAULT_INDEX_TABLESPACE setting. The test checks the SQL generated for tables and indexes 
        on the Authors and Reviewers models to ensure that the expected tablespaces are included 
        in the SQL commands.

        The test covers scenarios where a default index tablespace is set and where it is not set, 
        ensuring that the database configuration is correctly applied in both cases.

        """
        sql = sql_for_table(Authors).lower()
        # The join table of the ManyToManyField goes to the model's tablespace,
        # and its indexes too, unless DEFAULT_INDEX_TABLESPACE is set.
        if settings.DEFAULT_INDEX_TABLESPACE:
            # 1 for the table
            self.assertNumContains(sql, "tbl_tbsp", 1)
            # 1 for the primary key
            self.assertNumContains(sql, settings.DEFAULT_INDEX_TABLESPACE, 1)
        else:
            # 1 for the table + 1 for the index on the primary key
            self.assertNumContains(sql, "tbl_tbsp", 2)
        self.assertNumContains(sql, "idx_tbsp", 0)

        sql = sql_for_index(Authors).lower()
        # The ManyToManyField declares no db_tablespace, its indexes go to
        # the model's tablespace, unless DEFAULT_INDEX_TABLESPACE is set.
        if settings.DEFAULT_INDEX_TABLESPACE:
            self.assertNumContains(sql, settings.DEFAULT_INDEX_TABLESPACE, 2)
        else:
            self.assertNumContains(sql, "tbl_tbsp", 2)
        self.assertNumContains(sql, "idx_tbsp", 0)

        sql = sql_for_table(Reviewers).lower()
        # The join table of the ManyToManyField goes to the model's tablespace,
        # and its indexes too, unless DEFAULT_INDEX_TABLESPACE is set.
        if settings.DEFAULT_INDEX_TABLESPACE:
            # 1 for the table
            self.assertNumContains(sql, "tbl_tbsp", 1)
            # 1 for the primary key
            self.assertNumContains(sql, settings.DEFAULT_INDEX_TABLESPACE, 1)
        else:
            # 1 for the table + 1 for the index on the primary key
            self.assertNumContains(sql, "tbl_tbsp", 2)
        self.assertNumContains(sql, "idx_tbsp", 0)

        sql = sql_for_index(Reviewers).lower()
        # The ManyToManyField declares db_tablespace, its indexes go there.
        self.assertNumContains(sql, "tbl_tbsp", 0)
        self.assertNumContains(sql, "idx_tbsp", 2)
