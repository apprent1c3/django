"""Tests related to django.db.backends that haven't been organized."""

import datetime
import threading
import unittest
import warnings
from unittest import mock

from django.core.management.color import no_style
from django.db import (
    DEFAULT_DB_ALIAS,
    DatabaseError,
    IntegrityError,
    connection,
    connections,
    reset_queries,
    transaction,
)
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.backends.signals import connection_created
from django.db.backends.utils import CursorWrapper
from django.db.models.sql.constants import CURSOR
from django.test import (
    TestCase,
    TransactionTestCase,
    override_settings,
    skipIfDBFeature,
    skipUnlessDBFeature,
)

from .models import (
    Article,
    Object,
    ObjectReference,
    Person,
    Post,
    RawData,
    Reporter,
    ReporterProxy,
    SchoolClass,
    SQLKeywordsModel,
    Square,
    VeryLongModelNameZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ,
)


class DateQuotingTest(TestCase):
    def test_django_date_trunc(self):
        """
        Test the custom ``django_date_trunc method``, in particular against
        fields which clash with strings passed to it (e.g. 'year') (#12818).
        """
        updated = datetime.datetime(2010, 2, 20)
        SchoolClass.objects.create(year=2009, last_updated=updated)
        years = SchoolClass.objects.dates("last_updated", "year")
        self.assertEqual(list(years), [datetime.date(2010, 1, 1)])

    def test_django_date_extract(self):
        """
        Test the custom ``django_date_extract method``, in particular against fields
        which clash with strings passed to it (e.g. 'day') (#12818).
        """
        updated = datetime.datetime(2010, 2, 20)
        SchoolClass.objects.create(year=2009, last_updated=updated)
        classes = SchoolClass.objects.filter(last_updated__day=20)
        self.assertEqual(len(classes), 1)


@override_settings(DEBUG=True)
class LastExecutedQueryTest(TestCase):
    def test_last_executed_query_without_previous_query(self):
        """
        last_executed_query should not raise an exception even if no previous
        query has been run.
        """
        with connection.cursor() as cursor:
            connection.ops.last_executed_query(cursor, "", ())

    def test_debug_sql(self):
        """
        Test that a SQL query is generated correctly when retrieving Reporter objects.

        This function checks if a database query to retrieve Reporter objects results in a SQL statement that contains the expected 'SELECT' keyword and the Reporter table name. It verifies that the generated SQL query is valid and correctly references the Reporter table.
        """
        list(Reporter.objects.filter(first_name="test"))
        sql = connection.queries[-1]["sql"].lower()
        self.assertIn("select", sql)
        self.assertIn(Reporter._meta.db_table, sql)

    def test_query_encoding(self):
        """last_executed_query() returns a string."""
        data = RawData.objects.filter(raw_data=b"\x00\x46  \xFE").extra(
            select={"föö": 1}
        )
        sql, params = data.query.sql_with_params()
        with data.query.get_compiler("default").execute_sql(CURSOR) as cursor:
            last_sql = cursor.db.ops.last_executed_query(cursor, sql, params)
        self.assertIsInstance(last_sql, str)

    def test_last_executed_query(self):
        # last_executed_query() interpolate all parameters, in most cases it is
        # not equal to QuerySet.query.
        """

        Test that the last executed SQL query on the database matches the expected query.

        This test checks the last executed query for various test cases, including
        queries with filters, exclude clauses, and bulk ID filtering. It ensures
        that the actual SQL query executed on the database matches the query
        constructed by the ORM.

        The test uses a variety of queries to cover different scenarios, and then
        compares the actual query executed with the expected query string.

        """
        for qs in (
            Article.objects.filter(pk=1),
            Article.objects.filter(pk__in=(1, 2), reporter__pk=3),
            Article.objects.filter(
                pk=1,
                reporter__pk=9,
            ).exclude(reporter__pk__in=[2, 1]),
            Article.objects.filter(pk__in=list(range(20, 31))),
        ):
            sql, params = qs.query.sql_with_params()
            with qs.query.get_compiler(DEFAULT_DB_ALIAS).execute_sql(CURSOR) as cursor:
                self.assertEqual(
                    cursor.db.ops.last_executed_query(cursor, sql, params),
                    str(qs.query),
                )

    @skipUnlessDBFeature("supports_paramstyle_pyformat")
    def test_last_executed_query_dict(self):
        """

        Tests the last executed query dictionary when using parameterized queries.

        This test case verifies that the database's last executed query is correctly
        retrieved and matches the expected query string when parameter values are replaced.
        The test inserts data into a table using a dictionary of parameters and then
        compares the database's last executed query with the expected query string.

        """
        square_opts = Square._meta
        sql = "INSERT INTO %s (%s, %s) VALUES (%%(root)s, %%(square)s)" % (
            connection.introspection.identifier_converter(square_opts.db_table),
            connection.ops.quote_name(square_opts.get_field("root").column),
            connection.ops.quote_name(square_opts.get_field("square").column),
        )
        with connection.cursor() as cursor:
            params = {"root": 2, "square": 4}
            cursor.execute(sql, params)
            self.assertEqual(
                cursor.db.ops.last_executed_query(cursor, sql, params),
                sql % params,
            )

    @skipUnlessDBFeature("supports_paramstyle_pyformat")
    def test_last_executed_query_dict_overlap_keys(self):
        """

        Tests that the last executed query is correctly retrieved from the database cursor
        when dictionary-style parameter overlap is used.

        In this scenario, parameter names may be reused in the SQL query, and the function
        must correctly handle such overlaps. The test verifies that the last executed query
        string is accurately reconstructed with the provided parameter values.

        """
        square_opts = Square._meta
        sql = "INSERT INTO %s (%s, %s) VALUES (%%(root)s, %%(root2)s)" % (
            connection.introspection.identifier_converter(square_opts.db_table),
            connection.ops.quote_name(square_opts.get_field("root").column),
            connection.ops.quote_name(square_opts.get_field("square").column),
        )
        with connection.cursor() as cursor:
            params = {"root": 2, "root2": 4}
            cursor.execute(sql, params)
            self.assertEqual(
                cursor.db.ops.last_executed_query(cursor, sql, params),
                sql % params,
            )

    def test_last_executed_query_with_duplicate_params(self):
        """

        Tests that the last executed query with duplicate parameters is correctly resolved.

        The test checks if the last SQL query executed, which contains duplicate parameter values,
        is accurately reconstructed and returned, without duplicates, in its final executed form.

        """
        square_opts = Square._meta
        table = connection.introspection.identifier_converter(square_opts.db_table)
        id_column = connection.ops.quote_name(square_opts.get_field("id").column)
        root_column = connection.ops.quote_name(square_opts.get_field("root").column)
        sql = f"UPDATE {table} SET {root_column} = %s + %s WHERE {id_column} = %s"
        with connection.cursor() as cursor:
            params = [42, 42, 1]
            cursor.execute(sql, params)
            last_executed_query = connection.ops.last_executed_query(
                cursor, sql, params
            )
            self.assertEqual(
                last_executed_query,
                f"UPDATE {table} SET {root_column} = 42 + 42 WHERE {id_column} = 1",
            )


class ParameterHandlingTest(TestCase):
    def test_bad_parameter_count(self):
        """
        An executemany call with too many/not enough parameters will raise an
        exception.
        """
        with connection.cursor() as cursor:
            query = "INSERT INTO %s (%s, %s) VALUES (%%s, %%s)" % (
                connection.introspection.identifier_converter("backends_square"),
                connection.ops.quote_name("root"),
                connection.ops.quote_name("square"),
            )
            with self.assertRaises(Exception):
                cursor.executemany(query, [(1, 2, 3)])
            with self.assertRaises(Exception):
                cursor.executemany(query, [(1,)])


class LongNameTest(TransactionTestCase):
    """Long primary keys and model names can result in a sequence name
    that exceeds the database limits, which will result in truncation
    on certain databases (e.g., Postgres). The backend needs to use
    the correct sequence name in last_insert_id and other places, so
    check it is. Refs #8901.
    """

    available_apps = ["backends"]

    def test_sequence_name_length_limits_create(self):
        """Creation of model with long name and long pk name doesn't error."""
        VeryLongModelNameZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ.objects.create()

    def test_sequence_name_length_limits_m2m(self):
        """
        An m2m save of a model with a long name and a long m2m field name
        doesn't error (#8901).
        """
        obj = (
            VeryLongModelNameZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ.objects.create()
        )
        rel_obj = Person.objects.create(first_name="Django", last_name="Reinhardt")
        obj.m2m_also_quite_long_zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz.add(rel_obj)

    def test_sequence_name_length_limits_flush(self):
        """
        Sequence resetting as part of a flush with model with long name and
        long pk name doesn't error (#8901).
        """
        # A full flush is expensive to the full test, so we dig into the
        # internals to generate the likely offending SQL and run it manually

        # Some convenience aliases
        VLM = VeryLongModelNameZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ
        VLM_m2m = (
            VLM.m2m_also_quite_long_zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz.through
        )
        tables = [
            VLM._meta.db_table,
            VLM_m2m._meta.db_table,
        ]
        sql_list = connection.ops.sql_flush(no_style(), tables, reset_sequences=True)
        connection.ops.execute_sql_flush(sql_list)


class SequenceResetTest(TestCase):
    def test_generic_relation(self):
        "Sequence names are correct when resetting generic relations (Ref #13941)"
        # Create an object with a manually specified PK
        Post.objects.create(id=10, name="1st post", text="hello world")

        # Reset the sequences for the database
        commands = connections[DEFAULT_DB_ALIAS].ops.sequence_reset_sql(
            no_style(), [Post]
        )
        with connection.cursor() as cursor:
            for sql in commands:
                cursor.execute(sql)

        # If we create a new object now, it should have a PK greater
        # than the PK we specified manually.
        obj = Post.objects.create(name="New post", text="goodbye world")
        self.assertGreater(obj.pk, 10)


# This test needs to run outside of a transaction, otherwise closing the
# connection would implicitly rollback and cause problems during teardown.
class ConnectionCreatedSignalTest(TransactionTestCase):
    available_apps = []

    # Unfortunately with sqlite3 the in-memory test database cannot be closed,
    # and so it cannot be re-opened during testing.
    @skipUnlessDBFeature("test_db_allows_multiple_connections")
    def test_signal(self):
        """

        Tests the behavior of the connection_created signal.

        This test checks if the connection_created signal is sent with the correct connection
        when a new cursor is created, and if the signal is properly disconnected.

        It verifies that the connection provided to the signal receiver matches the expected
        connection. The test also ensures that the signal is properly cleaned up after
        disconnection, resulting in no unexpected signal emissions.

        """
        data = {}

        def receiver(sender, connection, **kwargs):
            data["connection"] = connection

        connection_created.connect(receiver)
        connection.close()
        with connection.cursor():
            pass
        self.assertIs(data["connection"].connection, connection.connection)

        connection_created.disconnect(receiver)
        data.clear()
        with connection.cursor():
            pass
        self.assertEqual(data, {})


class EscapingChecks(TestCase):
    """
    All tests in this test case are also run with settings.DEBUG=True in
    EscapingChecksDebug test case, to also test CursorDebugWrapper.
    """

    bare_select_suffix = connection.features.bare_select_suffix

    def test_paramless_no_escaping(self):
        """
        Tests that a parameterless SQL query with a literal string containing a percent sign is executed correctly without escaping the percent sign, verifying that the query result matches the expected output.
        """
        with connection.cursor() as cursor:
            cursor.execute("SELECT '%s'" + self.bare_select_suffix)
            self.assertEqual(cursor.fetchall()[0][0], "%s")

    def test_parameter_escaping(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT '%%', %s" + self.bare_select_suffix, ("%d",))
            self.assertEqual(cursor.fetchall()[0], ("%", "%d"))


@override_settings(DEBUG=True)
class EscapingChecksDebug(EscapingChecks):
    pass


class BackendTestCase(TransactionTestCase):
    available_apps = ["backends"]

    def create_squares_with_executemany(self, args):
        self.create_squares(args, "format", True)

    def create_squares(self, args, paramstyle, multiple):
        opts = Square._meta
        tbl = connection.introspection.identifier_converter(opts.db_table)
        f1 = connection.ops.quote_name(opts.get_field("root").column)
        f2 = connection.ops.quote_name(opts.get_field("square").column)
        if paramstyle == "format":
            query = "INSERT INTO %s (%s, %s) VALUES (%%s, %%s)" % (tbl, f1, f2)
        elif paramstyle == "pyformat":
            query = "INSERT INTO %s (%s, %s) VALUES (%%(root)s, %%(square)s)" % (
                tbl,
                f1,
                f2,
            )
        else:
            raise ValueError("unsupported paramstyle in test")
        with connection.cursor() as cursor:
            if multiple:
                cursor.executemany(query, args)
            else:
                cursor.execute(query, args)

    def test_cursor_executemany(self):
        # Test cursor.executemany #4896
        """

        Test bulk execution of SQL queries using the cursor's executemany method.

        This test case verifies the successful creation of Square objects in the database
        using the executemany method. It checks that the correct number of objects are
        created and that each object's attributes are accurately populated.

        The test covers the insertion of values ranging from -5 to 5, including both
        negative and positive numbers, as well as zero. It ensures that the square of
        each number is correctly calculated and stored in the corresponding object.

        The test uses the following steps:
        - Prepare a list of tuples containing the values to be inserted
        - Use the executemany method to insert the values into the database
        - Verify that the expected number of objects are created
        - Check that each object's attributes match the expected values

        """
        args = [(i, i**2) for i in range(-5, 6)]
        self.create_squares_with_executemany(args)
        self.assertEqual(Square.objects.count(), 11)
        for i in range(-5, 6):
            square = Square.objects.get(root=i)
            self.assertEqual(square.square, i**2)

    def test_cursor_executemany_with_empty_params_list(self):
        # Test executemany with params=[] does nothing #4765
        """
        Tests the execution of the executemany query with an empty list of parameters.

        Verifies that when no parameters are provided, the database operation does not create any new records.

        This test case ensures the robustness of the code by handling edge cases, such as empty input data, and confirms that the database state remains unchanged in such scenarios.
        """
        args = []
        self.create_squares_with_executemany(args)
        self.assertEqual(Square.objects.count(), 0)

    def test_cursor_executemany_with_iterator(self):
        # Test executemany accepts iterators #10320
        """

        Tests the ability to execute many SQL queries in a single call using a iterator.

        The function checks if the executemany method can successfully create multiple records
        in the database using an iterator of tuples as input arguments. It also verifies the
        functionality of this method under different settings, specifically when DEBUG mode is
        enabled. The test case asserts that the total count of records in the database matches
        the expected number after executing the queries.

        This test covers the scenario where the input iterator contains a sequence of values,
        and the executemany method is called with this iterator to create multiple records.
        The function also tests the behavior of the executemany method when the DEBUG setting
        is overridden, ensuring that the method works correctly in different environments.

        """
        args = ((i, i**2) for i in range(-3, 2))
        self.create_squares_with_executemany(args)
        self.assertEqual(Square.objects.count(), 5)

        args = ((i, i**2) for i in range(3, 7))
        with override_settings(DEBUG=True):
            # same test for DebugCursorWrapper
            self.create_squares_with_executemany(args)
        self.assertEqual(Square.objects.count(), 9)

    @skipUnlessDBFeature("supports_paramstyle_pyformat")
    def test_cursor_execute_with_pyformat(self):
        # Support pyformat style passing of parameters #10070
        """
        Test the execution of a database cursor using the 'pyformat' parameter style, 
        creating a single Square object and verifying that the database query results 
        match the expected outcome.
        """
        args = {"root": 3, "square": 9}
        self.create_squares(args, "pyformat", multiple=False)
        self.assertEqual(Square.objects.count(), 1)

    @skipUnlessDBFeature("supports_paramstyle_pyformat")
    def test_cursor_executemany_with_pyformat(self):
        # Support pyformat style passing of parameters #10070
        """

        Tests the execution of a SQL query using the cursor's executemany method with the 'pyformat' parameter style.

        This test verifies that executing multiple queries at once with the 'pyformat' style correctly inserts data into the database.
        It checks the successful insertion of 11 rows and ensures that the data is correctly retrieved from the database.

        The test case covers the following scenarios:
            - Successful execution of multiple queries using the 'pyformat' style.
            - Correct insertion of data into the database.
            - Correct retrieval of data from the database.

        """
        args = [{"root": i, "square": i**2} for i in range(-5, 6)]
        self.create_squares(args, "pyformat", multiple=True)
        self.assertEqual(Square.objects.count(), 11)
        for i in range(-5, 6):
            square = Square.objects.get(root=i)
            self.assertEqual(square.square, i**2)

    @skipUnlessDBFeature("supports_paramstyle_pyformat")
    def test_cursor_executemany_with_pyformat_iterator(self):
        args = ({"root": i, "square": i**2} for i in range(-3, 2))
        self.create_squares(args, "pyformat", multiple=True)
        self.assertEqual(Square.objects.count(), 5)

        args = ({"root": i, "square": i**2} for i in range(3, 7))
        with override_settings(DEBUG=True):
            # same test for DebugCursorWrapper
            self.create_squares(args, "pyformat", multiple=True)
        self.assertEqual(Square.objects.count(), 9)

    def test_unicode_fetches(self):
        # fetchone, fetchmany, fetchall return strings as Unicode objects.
        """
        Test that Unicode data can be correctly fetched from the database.

        This test case creates several Person objects with different first and last names, 
        saves them to the database, and then uses a raw SQL query to retrieve the data.
        It verifies that the data is fetched correctly, checking the order of the results 
        and the values of specific fields. The test ensures that the database operations 
        are working as expected and that the Person model's fields are correctly mapped 
        to the database columns.

        The test covers the following scenarios:
        - Saving multiple objects to the database
        - Executing a raw SQL query to retrieve data
        - Fetching data using the cursor's fetchone, fetchmany, and fetchall methods
        - Verifying the order and values of the fetched data
        """
        qn = connection.ops.quote_name
        Person(first_name="John", last_name="Doe").save()
        Person(first_name="Jane", last_name="Doe").save()
        Person(first_name="Mary", last_name="Agnelline").save()
        Person(first_name="Peter", last_name="Parker").save()
        Person(first_name="Clark", last_name="Kent").save()
        opts2 = Person._meta
        f3, f4 = opts2.get_field("first_name"), opts2.get_field("last_name")
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT %s, %s FROM %s ORDER BY %s"
                % (
                    qn(f3.column),
                    qn(f4.column),
                    connection.introspection.identifier_converter(opts2.db_table),
                    qn(f3.column),
                )
            )
            self.assertEqual(cursor.fetchone(), ("Clark", "Kent"))
            self.assertEqual(
                list(cursor.fetchmany(2)), [("Jane", "Doe"), ("John", "Doe")]
            )
            self.assertEqual(
                list(cursor.fetchall()), [("Mary", "Agnelline"), ("Peter", "Parker")]
            )

    def test_unicode_password(self):
        """
        Tests the ability to connect to a database with a Unicode password.

        Verifies that the application can establish a database connection when the 
        password contains non-ASCII characters, ensuring proper handling of Unicode 
        input in the connection settings.

        The test connects to the database using a password containing a Unicode 
        character, then reverts the password to its original value.

        Any unexpected errors raised during this process are reported and cause the 
        test to fail, while DatabaseErrors are expected and do not result in test 
        failure.
        """
        old_password = connection.settings_dict["PASSWORD"]
        connection.settings_dict["PASSWORD"] = "françois"
        try:
            with connection.cursor():
                pass
        except DatabaseError:
            # As password is probably wrong, a database exception is expected
            pass
        except Exception as e:
            self.fail("Unexpected error raised with Unicode password: %s" % e)
        finally:
            connection.settings_dict["PASSWORD"] = old_password

    def test_database_operations_helper_class(self):
        # Ticket #13630
        """
        Tests the helper class for database operations, ensuring it has the necessary attributes and that the connection is properly set.

        This test checks if the connection object has an 'ops' attribute, and if the 'ops' object has a 'connection' attribute. It also verifies that the connection referenced by the 'ops' object is the same as the original connection.

        This test is important to guarantee that the database operations helper class is correctly initialized and configured, allowing for reliable database interactions.
        """
        self.assertTrue(hasattr(connection, "ops"))
        self.assertTrue(hasattr(connection.ops, "connection"))
        self.assertEqual(connection, connection.ops.connection)

    def test_database_operations_init(self):
        """
        DatabaseOperations initialization doesn't query the database.
        See #17656.
        """
        with self.assertNumQueries(0):
            connection.ops.__class__(connection)

    def test_cached_db_features(self):
        self.assertIn(connection.features.supports_transactions, (True, False))
        self.assertIn(connection.features.can_introspect_foreign_keys, (True, False))

    def test_duplicate_table_error(self):
        """Creating an existing table returns a DatabaseError"""
        query = "CREATE TABLE %s (id INTEGER);" % Article._meta.db_table
        with connection.cursor() as cursor:
            with self.assertRaises(DatabaseError):
                cursor.execute(query)

    def test_cursor_contextmanager(self):
        """
        Cursors can be used as a context manager
        """
        with connection.cursor() as cursor:
            self.assertIsInstance(cursor, CursorWrapper)
        # Both InterfaceError and ProgrammingError seem to be used when
        # accessing closed cursor (psycopg has InterfaceError, rest seem
        # to use ProgrammingError).
        with self.assertRaises(connection.features.closed_cursor_error_class):
            # cursor should be closed, so no queries should be possible.
            cursor.execute("SELECT 1" + connection.features.bare_select_suffix)

    @unittest.skipUnless(
        connection.vendor == "postgresql",
        "Psycopg specific cursor.closed attribute needed",
    )
    def test_cursor_contextmanager_closing(self):
        # There isn't a generic way to test that cursors are closed, but
        # psycopg offers us a way to check that by closed attribute.
        # So, run only on psycopg for that reason.
        """
        Tests that the cursor context manager properly closes the cursor after use.

        This test is specific to PostgreSQL databases and verifies that the cursor is 
        correctly closed when exiting the 'with' block, regardless of whether an exception 
        is thrown or not.

        The test checks that the cursor object is an instance of CursorWrapper and 
        subsequently confirms that the cursor's 'closed' attribute is set to True, 
        indicating successful closure.

        Note: This test is skipped for non-PostgreSQL databases, as it relies on the 
        Psycopg-specific 'closed' attribute of the cursor object.
        """
        with connection.cursor() as cursor:
            self.assertIsInstance(cursor, CursorWrapper)
        self.assertTrue(cursor.closed)

    # Unfortunately with sqlite3 the in-memory test database cannot be closed.
    @skipUnlessDBFeature("test_db_allows_multiple_connections")
    def test_is_usable_after_database_disconnects(self):
        """
        is_usable() doesn't crash when the database disconnects (#21553).
        """
        # Open a connection to the database.
        with connection.cursor():
            pass
        # Emulate a connection close by the database.
        connection._close()
        # Even then is_usable() should not raise an exception.
        try:
            self.assertFalse(connection.is_usable())
        finally:
            # Clean up the mess created by connection._close(). Since the
            # connection is already closed, this crashes on some backends.
            try:
                connection.close()
            except Exception:
                pass

    @override_settings(DEBUG=True)
    def test_queries(self):
        """
        Test the documented API of connection.queries.
        """
        sql = "SELECT 1" + connection.features.bare_select_suffix
        with connection.cursor() as cursor:
            reset_queries()
            cursor.execute(sql)
        self.assertEqual(1, len(connection.queries))
        self.assertIsInstance(connection.queries, list)
        self.assertIsInstance(connection.queries[0], dict)
        self.assertEqual(list(connection.queries[0]), ["sql", "time"])
        self.assertEqual(connection.queries[0]["sql"], sql)

        reset_queries()
        self.assertEqual(0, len(connection.queries))

        sql = "INSERT INTO %s (%s, %s) VALUES (%%s, %%s)" % (
            connection.introspection.identifier_converter("backends_square"),
            connection.ops.quote_name("root"),
            connection.ops.quote_name("square"),
        )
        with connection.cursor() as cursor:
            cursor.executemany(sql, [(1, 1), (2, 4)])
        self.assertEqual(1, len(connection.queries))
        self.assertIsInstance(connection.queries, list)
        self.assertIsInstance(connection.queries[0], dict)
        self.assertEqual(list(connection.queries[0]), ["sql", "time"])
        self.assertEqual(connection.queries[0]["sql"], "2 times: %s" % sql)

    # Unfortunately with sqlite3 the in-memory test database cannot be closed.
    @skipUnlessDBFeature("test_db_allows_multiple_connections")
    @override_settings(DEBUG=True)
    def test_queries_limit(self):
        """
        The backend doesn't store an unlimited number of queries (#12581).
        """
        old_queries_limit = BaseDatabaseWrapper.queries_limit
        BaseDatabaseWrapper.queries_limit = 3
        new_connection = connection.copy()

        # Initialize the connection and clear initialization statements.
        with new_connection.cursor():
            pass
        new_connection.queries_log.clear()

        try:
            with new_connection.cursor() as cursor:
                cursor.execute("SELECT 1" + new_connection.features.bare_select_suffix)
                cursor.execute("SELECT 2" + new_connection.features.bare_select_suffix)

            with warnings.catch_warnings(record=True) as w:
                self.assertEqual(2, len(new_connection.queries))
                self.assertEqual(0, len(w))

            with new_connection.cursor() as cursor:
                cursor.execute("SELECT 3" + new_connection.features.bare_select_suffix)
                cursor.execute("SELECT 4" + new_connection.features.bare_select_suffix)

            msg = (
                "Limit for query logging exceeded, only the last 3 queries will be "
                "returned."
            )
            with self.assertWarnsMessage(UserWarning, msg):
                self.assertEqual(3, len(new_connection.queries))

        finally:
            BaseDatabaseWrapper.queries_limit = old_queries_limit
            new_connection.close()

    @mock.patch("django.db.backends.utils.logger")
    @override_settings(DEBUG=True)
    def test_queries_logger(self, mocked_logger):
        sql = "SELECT 1" + connection.features.bare_select_suffix
        with connection.cursor() as cursor:
            cursor.execute(sql)
        params, kwargs = mocked_logger.debug.call_args
        self.assertIn("; alias=%s", params[0])
        self.assertEqual(params[2], sql)
        self.assertIsNone(params[3])
        self.assertEqual(params[4], connection.alias)
        self.assertEqual(
            list(kwargs["extra"]),
            ["duration", "sql", "params", "alias"],
        )
        self.assertEqual(tuple(kwargs["extra"].values()), params[1:])

    def test_queries_bare_where(self):
        """
        Tests the ability to execute SQL queries with a bare 'WHERE' clause.

        Verifies that a query with a 'WHERE' clause containing a condition that is always true
        returns the expected result without raising any errors. This ensures compatibility with
        the database backend's SQL syntax and the connection's features.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the query result does not match the expected output.
        """
        sql = f"SELECT 1{connection.features.bare_select_suffix} WHERE 1=1"
        with connection.cursor() as cursor:
            cursor.execute(sql)
            self.assertEqual(cursor.fetchone(), (1,))

    def test_timezone_none_use_tz_false(self):
        connection.ensure_connection()
        with self.settings(TIME_ZONE=None, USE_TZ=False):
            connection.init_connection_state()


# These tests aren't conditional because it would require differentiating
# between MySQL+InnoDB and MySQL+MYISAM (something we currently can't do).
class FkConstraintsTests(TransactionTestCase):
    available_apps = ["backends"]

    def setUp(self):
        # Create a Reporter.
        self.r = Reporter.objects.create(first_name="John", last_name="Smith")

    def test_integrity_checks_on_creation(self):
        """
        Try to create a model instance that violates a FK constraint. If it
        fails it should fail with IntegrityError.
        """
        a1 = Article(
            headline="This is a test",
            pub_date=datetime.datetime(2005, 7, 27),
            reporter_id=30,
        )
        try:
            a1.save()
        except IntegrityError:
            pass
        else:
            self.skipTest("This backend does not support integrity checks.")
        # Now that we know this backend supports integrity checks we make sure
        # constraints are also enforced for proxy  Refs #17519
        a2 = Article(
            headline="This is another test",
            reporter=self.r,
            pub_date=datetime.datetime(2012, 8, 3),
            reporter_proxy_id=30,
        )
        with self.assertRaises(IntegrityError):
            a2.save()

    def test_integrity_checks_on_update(self):
        """
        Try to update a model instance introducing a FK constraint violation.
        If it fails it should fail with IntegrityError.
        """
        # Create an Article.
        Article.objects.create(
            headline="Test article",
            pub_date=datetime.datetime(2010, 9, 4),
            reporter=self.r,
        )
        # Retrieve it from the DB
        a1 = Article.objects.get(headline="Test article")
        a1.reporter_id = 30
        try:
            a1.save()
        except IntegrityError:
            pass
        else:
            self.skipTest("This backend does not support integrity checks.")
        # Now that we know this backend supports integrity checks we make sure
        # constraints are also enforced for proxy  Refs #17519
        # Create another article
        r_proxy = ReporterProxy.objects.get(pk=self.r.pk)
        Article.objects.create(
            headline="Another article",
            pub_date=datetime.datetime(1988, 5, 15),
            reporter=self.r,
            reporter_proxy=r_proxy,
        )
        # Retrieve the second article from the DB
        a2 = Article.objects.get(headline="Another article")
        a2.reporter_proxy_id = 30
        with self.assertRaises(IntegrityError):
            a2.save()

    def test_disable_constraint_checks_manually(self):
        """
        When constraint checks are disabled, should be able to write bad data
        without IntegrityErrors.
        """
        with transaction.atomic():
            # Create an Article.
            Article.objects.create(
                headline="Test article",
                pub_date=datetime.datetime(2010, 9, 4),
                reporter=self.r,
            )
            # Retrieve it from the DB
            a = Article.objects.get(headline="Test article")
            a.reporter_id = 30
            try:
                connection.disable_constraint_checking()
                a.save()
                connection.enable_constraint_checking()
            except IntegrityError:
                self.fail("IntegrityError should not have occurred.")
            transaction.set_rollback(True)

    def test_disable_constraint_checks_context_manager(self):
        """
        When constraint checks are disabled (using context manager), should be
        able to write bad data without IntegrityErrors.
        """
        with transaction.atomic():
            # Create an Article.
            Article.objects.create(
                headline="Test article",
                pub_date=datetime.datetime(2010, 9, 4),
                reporter=self.r,
            )
            # Retrieve it from the DB
            a = Article.objects.get(headline="Test article")
            a.reporter_id = 30
            try:
                with connection.constraint_checks_disabled():
                    a.save()
            except IntegrityError:
                self.fail("IntegrityError should not have occurred.")
            transaction.set_rollback(True)

    def test_check_constraints(self):
        """
        Constraint checks should raise an IntegrityError when bad data is in the DB.
        """
        with transaction.atomic():
            # Create an Article.
            Article.objects.create(
                headline="Test article",
                pub_date=datetime.datetime(2010, 9, 4),
                reporter=self.r,
            )
            # Retrieve it from the DB
            a = Article.objects.get(headline="Test article")
            a.reporter_id = 30
            with connection.constraint_checks_disabled():
                a.save()
                try:
                    connection.check_constraints(table_names=[Article._meta.db_table])
                except IntegrityError:
                    pass
                else:
                    self.skipTest("This backend does not support integrity checks.")
            transaction.set_rollback(True)

    def test_check_constraints_sql_keywords(self):
        with transaction.atomic():
            obj = SQLKeywordsModel.objects.create(reporter=self.r)
            obj.refresh_from_db()
            obj.reporter_id = 30
            with connection.constraint_checks_disabled():
                obj.save()
                try:
                    connection.check_constraints(table_names=["order"])
                except IntegrityError:
                    pass
                else:
                    self.skipTest("This backend does not support integrity checks.")
            transaction.set_rollback(True)


class ThreadTests(TransactionTestCase):
    available_apps = ["backends"]

    def test_default_connection_thread_local(self):
        """
        The default connection (i.e. django.db.connection) is different for
        each thread (#17258).
        """
        # Map connections by id because connections with identical aliases
        # have the same hash.
        connections_dict = {}
        with connection.cursor():
            pass
        connections_dict[id(connection)] = connection

        def runner():
            # Passing django.db.connection between threads doesn't work while
            # connections[DEFAULT_DB_ALIAS] does.
            """

            Establishes a database connection for thread-safe execution.

            This function sets up a database connection using the default database alias, 
            enables thread sharing for the connection, and creates a cursor object. 
            The established connection is stored in a connections dictionary for future use.

            Note: The connection is managed properly to prevent data corruption and ensure 
            thread safety, making it suitable for use in multi-threaded environments.

            """
            from django.db import connections

            connection = connections[DEFAULT_DB_ALIAS]
            # Allow thread sharing so the connection can be closed by the
            # main thread.
            connection.inc_thread_sharing()
            with connection.cursor():
                pass
            connections_dict[id(connection)] = connection

        try:
            for x in range(2):
                t = threading.Thread(target=runner)
                t.start()
                t.join()
            # Each created connection got different inner connection.
            self.assertEqual(
                len({conn.connection for conn in connections_dict.values()}), 3
            )
        finally:
            # Finish by closing the connections opened by the other threads
            # (the connection opened in the main thread will automatically be
            # closed on teardown).
            for conn in connections_dict.values():
                if conn is not connection and conn.allow_thread_sharing:
                    conn.validate_thread_sharing()
                    conn._close()
                    conn.dec_thread_sharing()

    def test_connections_thread_local(self):
        """
        The connections are different for each thread (#17258).
        """
        # Map connections by id because connections with identical aliases
        # have the same hash.
        connections_dict = {}
        for conn in connections.all():
            connections_dict[id(conn)] = conn

        def runner():
            """

            Initializes and configures Django database connections for thread sharing.

            This function iterates over all available Django database connections, increments
            their thread sharing counters, and stores them in a dictionary for later use.
            The dictionary keys are based on the unique identifiers of the connections.

            Note:
                The connections_dict is not defined within this function and should be
                accessible in the same scope where this function is called.

            """
            from django.db import connections

            for conn in connections.all():
                # Allow thread sharing so the connection can be closed by the
                # main thread.
                conn.inc_thread_sharing()
                connections_dict[id(conn)] = conn

        try:
            num_new_threads = 2
            for x in range(num_new_threads):
                t = threading.Thread(target=runner)
                t.start()
                t.join()
            self.assertEqual(
                len(connections_dict),
                len(connections.all()) * (num_new_threads + 1),
            )
        finally:
            # Finish by closing the connections opened by the other threads
            # (the connection opened in the main thread will automatically be
            # closed on teardown).
            for conn in connections_dict.values():
                if conn is not connection and conn.allow_thread_sharing:
                    conn.close()
                    conn.dec_thread_sharing()

    def test_pass_connection_between_threads(self):
        """
        A connection can be passed from one thread to the other (#17258).
        """
        Person.objects.create(first_name="John", last_name="Doe")

        def do_thread():
            """

            Executes a database query in a separate thread.

            This function creates a new thread that runs a query to retrieve a Person object
            from the database. The query is executed using the default database connection.
            If any exceptions occur during the query execution, they are caught and stored
            for further handling.

            The function starts the thread and waits for it to finish before returning.

            """
            def runner(main_thread_connection):
                """

                Establishes a database connection for a runner process and attempts to query the database for a specific person.

                This function takes a database connection from the main thread and sets it as the default connection for the current process.
                It then tries to retrieve a person record with the first name 'John' and last name 'Doe' from the database.
                If any exceptions occur during this process, they are caught and added to the exceptions list.

                :param main_thread_connection: A database connection object from the main thread.

                """
                from django.db import connections

                connections["default"] = main_thread_connection
                try:
                    Person.objects.get(first_name="John", last_name="Doe")
                except Exception as e:
                    exceptions.append(e)

            t = threading.Thread(target=runner, args=[connections["default"]])
            t.start()
            t.join()

        # Without touching thread sharing, which should be False by default.
        exceptions = []
        do_thread()
        # Forbidden!
        self.assertIsInstance(exceptions[0], DatabaseError)
        connections["default"].close()

        # After calling inc_thread_sharing() on the connection.
        connections["default"].inc_thread_sharing()
        try:
            exceptions = []
            do_thread()
            # All good
            self.assertEqual(exceptions, [])
        finally:
            connections["default"].dec_thread_sharing()

    def test_closing_non_shared_connections(self):
        """
        A connection that is not explicitly shareable cannot be closed by
        another thread (#17258).
        """
        # First, without explicitly enabling the connection for sharing.
        exceptions = set()

        def runner1():
            def runner2(other_thread_connection):
                try:
                    other_thread_connection.close()
                except DatabaseError as e:
                    exceptions.add(e)

            t2 = threading.Thread(target=runner2, args=[connections["default"]])
            t2.start()
            t2.join()

        t1 = threading.Thread(target=runner1)
        t1.start()
        t1.join()
        # The exception was raised
        self.assertEqual(len(exceptions), 1)

        # Then, with explicitly enabling the connection for sharing.
        exceptions = set()

        def runner1():
            """

            Executes a database connection closure operation in a separate thread.

            This function creates a new thread that attempts to close the default database connection.
            If an error occurs during the closure process, the exception is caught and stored.
            The function ensures that thread sharing is properly incremented before creating the new thread
            and decremented after the thread finishes execution, regardless of the outcome.

             Args:
                None

             Returns:
                None

             Raises:
                No exceptions are raised by this function, but any DatabaseError that occurs during
                the closure process is stored and can be accessed separately.

            """
            def runner2(other_thread_connection):
                """
                Closes a connection to another thread and handles potential database errors.

                Parameters
                ----------
                other_thread_connection : connection object
                    The connection to be closed.

                Notes
                -----
                If an error occurs during connection closure, it is caught and added to the exceptions collection for further handling. This ensures that the program can continue running without interruption, while still keeping track of any issues that may have arisen during connection closure.
                """
                try:
                    other_thread_connection.close()
                except DatabaseError as e:
                    exceptions.add(e)

            # Enable thread sharing
            connections["default"].inc_thread_sharing()
            try:
                t2 = threading.Thread(target=runner2, args=[connections["default"]])
                t2.start()
                t2.join()
            finally:
                connections["default"].dec_thread_sharing()

        t1 = threading.Thread(target=runner1)
        t1.start()
        t1.join()
        # No exception was raised
        self.assertEqual(len(exceptions), 0)

    def test_thread_sharing_count(self):
        """
        Tests the thread sharing count mechanism to ensure it correctly enables and disables thread sharing.

        This test verifies that the thread sharing count is initially set to False and that incrementing the count sets it to True.
        It also checks that decrementing the count below zero raises a RuntimeError with the expected error message.

        The test covers the following scenarios:
        - Initial state of thread sharing count
        - Incrementing the count to enable thread sharing
        - Decrementing the count to disable thread sharing
        - Attempting to decrement the count below zero
        """
        self.assertIs(connection.allow_thread_sharing, False)
        connection.inc_thread_sharing()
        self.assertIs(connection.allow_thread_sharing, True)
        connection.inc_thread_sharing()
        self.assertIs(connection.allow_thread_sharing, True)
        connection.dec_thread_sharing()
        self.assertIs(connection.allow_thread_sharing, True)
        connection.dec_thread_sharing()
        self.assertIs(connection.allow_thread_sharing, False)
        msg = "Cannot decrement the thread sharing count below zero."
        with self.assertRaisesMessage(RuntimeError, msg):
            connection.dec_thread_sharing()


class MySQLPKZeroTests(TestCase):
    """
    Zero as id for AutoField should raise exception in MySQL, because MySQL
    does not allow zero for autoincrement primary key if the
    NO_AUTO_VALUE_ON_ZERO SQL mode is not enabled.
    """

    @skipIfDBFeature("allows_auto_pk_0")
    def test_zero_as_autoval(self):
        with self.assertRaises(ValueError):
            Square.objects.create(id=0, root=0, square=1)


class DBConstraintTestCase(TestCase):
    def test_can_reference_existent(self):
        obj = Object.objects.create()
        ref = ObjectReference.objects.create(obj=obj)
        self.assertEqual(ref.obj, obj)

        ref = ObjectReference.objects.get(obj=obj)
        self.assertEqual(ref.obj, obj)

    def test_can_reference_non_existent(self):
        """
        Checks if the ObjectReference model can successfully create and retrieve a reference to a non-existent object in the database. 

        The function verifies that the referenced object does not exist, creates a new ObjectReference with the non-existent object's ID, retrieves the reference, and checks that it matches the originally created reference. 

        Additionally, it confirms that attempting to access the actual object (not just its reference) raises an Object.DoesNotExist exception, as expected when the object does not exist in the database.
        """
        self.assertFalse(Object.objects.filter(id=12345).exists())
        ref = ObjectReference.objects.create(obj_id=12345)
        ref_new = ObjectReference.objects.get(obj_id=12345)
        self.assertEqual(ref, ref_new)

        with self.assertRaises(Object.DoesNotExist):
            ref.obj

    def test_many_to_many(self):
        """
        Tests the many-to-many relationship between objects.

        Verifies that creating an object and its related object increases the respective counts.
        It also checks the creation of an intermediary model instance and its effect on the counts.
        The test covers both the object and its related objects, ensuring the many-to-many relationship is correctly established and updated.
        """
        obj = Object.objects.create()
        obj.related_objects.create()
        self.assertEqual(Object.objects.count(), 2)
        self.assertEqual(obj.related_objects.count(), 1)

        intermediary_model = Object._meta.get_field(
            "related_objects"
        ).remote_field.through
        intermediary_model.objects.create(from_object_id=obj.id, to_object_id=12345)
        self.assertEqual(obj.related_objects.count(), 1)
        self.assertEqual(intermediary_model.objects.count(), 2)
