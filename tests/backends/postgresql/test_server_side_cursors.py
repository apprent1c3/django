import operator
import unittest
from collections import namedtuple
from contextlib import contextmanager

from django.db import connection, models
from django.db.utils import ProgrammingError
from django.test import TestCase
from django.test.utils import garbage_collect
from django.utils.version import PYPY

from ..models import Person

try:
    from django.db.backends.postgresql.psycopg_any import is_psycopg3
except ImportError:
    is_psycopg3 = False


@unittest.skipUnless(connection.vendor == "postgresql", "PostgreSQL tests")
class ServerSideCursorsPostgres(TestCase):
    cursor_fields = (
        "name, statement, is_holdable, is_binary, is_scrollable, creation_time"
    )
    PostgresCursor = namedtuple("PostgresCursor", cursor_fields)

    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for the class, creating two test Person objects.

        This class method is used to establish a common set of data that can be shared across all tests in the class.
        It creates two Person instances, 'p0' and 'p1', with sample first and last names, making them available as class attributes for use in subsequent tests.

        Returns:
            None

        """
        cls.p0 = Person.objects.create(first_name="a", last_name="a")
        cls.p1 = Person.objects.create(first_name="b", last_name="b")

    def inspect_cursors(self):
        """
        Inspect the current cursors in the PostgreSQL database.

        This method retrieves information about all open cursors in the database and returns a list of :class:`PostgresCursor` objects, each representing a single cursor.

        The returned list includes details such as the cursor's properties and status, providing insight into the current database operations.

        :returns: A list of :class:`PostgresCursor` objects representing the open cursors in the database.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT {fields} FROM pg_cursors;".format(fields=self.cursor_fields)
            )
            cursors = cursor.fetchall()
        return [self.PostgresCursor._make(cursor) for cursor in cursors]

    @contextmanager
    def override_db_setting(self, **kwargs):
        """

        Temporarily overrides database settings for the duration of a context.

        This context manager allows you to modify database settings and automatically
        reverts them to their original values when the context is exited.

        The settings to override are specified as keyword arguments, where the key is
        the name of the setting and the value is the new value to use.

        For example, you can override the database host and port like this:
            with obj.override_db_setting(host='new_host', port=1234):
                # code that uses the overridden settings

        When the context is exited, the original values of the overridden settings
        will be restored. If a setting was not previously set, it will be removed
        when the context is exited.

        """
        for setting in kwargs:
            original_value = connection.settings_dict.get(setting)
            if setting in connection.settings_dict:
                self.addCleanup(
                    operator.setitem, connection.settings_dict, setting, original_value
                )
            else:
                self.addCleanup(operator.delitem, connection.settings_dict, setting)

            connection.settings_dict[setting] = kwargs[setting]
            yield

    def assertUsesCursor(self, queryset, num_expected=1):
        """

        Asserts that a given queryset utilizes the expected number of database cursors.

        This function verifies that the execution of the provided queryset results in the
        creation of a specified number of cursors. It checks that each cursor's name
        contains a specific suffix, and that the cursors are not scrollable, holdable, or
        binary.

        :param queryset: The queryset to be executed for cursor inspection.
        :param num_expected: The expected number of cursors to be created (default is 1).

        """
        next(queryset)  # Open a server-side cursor
        cursors = self.inspect_cursors()
        self.assertEqual(len(cursors), num_expected)
        for cursor in cursors:
            self.assertIn("_django_curs_", cursor.name)
            self.assertFalse(cursor.is_scrollable)
            self.assertFalse(cursor.is_holdable)
            self.assertFalse(cursor.is_binary)

    def assertNotUsesCursor(self, queryset):
        self.assertUsesCursor(queryset, num_expected=0)

    def test_server_side_cursor(self):
        self.assertUsesCursor(Person.objects.iterator())

    def test_values(self):
        self.assertUsesCursor(Person.objects.values("first_name").iterator())

    def test_values_list(self):
        self.assertUsesCursor(Person.objects.values_list("first_name").iterator())

    def test_values_list_flat(self):
        self.assertUsesCursor(
            Person.objects.values_list("first_name", flat=True).iterator()
        )

    def test_values_list_fields_not_equal_to_names(self):
        """

        Tests if values_list fields are not equal to names.

        This test case verifies that using an annotation with a count expression
        in a values_list query does not return the same value for both the annotation
        and the field name, when using the iterator method.

        It checks the behavior of the ORM when using the values_list method with
        an annotated field, ensuring that the annotated values and the field names
        are correctly distinguished.

        """
        expr = models.Count("id")
        self.assertUsesCursor(
            Person.objects.annotate(id__count=expr)
            .values_list(expr, "id__count")
            .iterator()
        )

    def test_server_side_cursor_many_cursors(self):
        persons = Person.objects.iterator()
        persons2 = Person.objects.iterator()
        next(persons)  # Open a server-side cursor
        self.assertUsesCursor(persons2, num_expected=2)

    def test_closed_server_side_cursor(self):
        """

        Tests that a server-side cursor is properly closed after it has been used and deleted.

        This test case verifies that the database connection is cleaned up and no cursors remain open
        after an iterator is used to fetch data and then discarded. The test checks for the presence
        of any remaining cursors after the iterator has been deleted and garbage collection has occurred.

        """
        persons = Person.objects.iterator()
        next(persons)  # Open a server-side cursor
        del persons
        garbage_collect()
        cursors = self.inspect_cursors()
        self.assertEqual(len(cursors), 0)

    @unittest.skipIf(
        PYPY,
        reason="Cursor not closed properly due to differences in garbage collection.",
    )
    def test_server_side_cursors_setting(self):
        """

        Tests the functionality of server-side cursors.

        This test case verifies the correct usage of server-side cursors when the
        DISABLE_SERVER_SIDE_CURSORS database setting is enabled or disabled. It checks
        that when server-side cursors are enabled, the database query utilizes a cursor,
        and when disabled, the query does not use a cursor. The test uses the Person
        model to perform the queries and checks the cursor usage accordingly.

        """
        with self.override_db_setting(DISABLE_SERVER_SIDE_CURSORS=False):
            persons = Person.objects.iterator()
            self.assertUsesCursor(persons)
            del persons  # Close server-side cursor

        # On PyPy, the cursor is left open here and attempting to force garbage
        # collection breaks the transaction wrapping the test.
        with self.override_db_setting(DISABLE_SERVER_SIDE_CURSORS=True):
            self.assertNotUsesCursor(Person.objects.iterator())

    @unittest.skipUnless(
        is_psycopg3, "The server_side_binding option is only effective on psycopg >= 3."
    )
    def test_server_side_binding(self):
        """
        The ORM still generates SQL that is not suitable for usage as prepared
        statements but psycopg >= 3 defaults to using server-side bindings for
        server-side cursors which requires some specialized logic when the
        `server_side_binding` setting is disabled (default).
        """

        def perform_query():
            # Generates SQL that is known to be problematic from a server-side
            # binding perspective as the parametrized ORDER BY clause doesn't
            # use the same binding parameter as the SELECT clause.
            """
            Performs a database query to retrieve a list of Person objects.

            The query orders the results by the 'first_name' field, using an empty string as a fallback for null values, 
            and returns a distinct list of objects. The results are then compared to an expected sequence to verify correctness.

            Returns:
                None

            Note:
                This function asserts that the query results match the expected sequence, raising an AssertionError if they do not match.

            """
            qs = (
                Person.objects.order_by(
                    models.functions.Coalesce("first_name", models.Value(""))
                )
                .distinct()
                .iterator()
            )
            self.assertSequenceEqual(list(qs), [self.p0, self.p1])

        with self.override_db_setting(OPTIONS={}):
            perform_query()

        with self.override_db_setting(OPTIONS={"server_side_binding": False}):
            perform_query()

        with self.override_db_setting(OPTIONS={"server_side_binding": True}):
            # This assertion could start failing the moment the ORM generates
            # SQL suitable for usage as prepared statements (#20516) or if
            # psycopg >= 3 adapts psycopg.Connection(cursor_factory) machinery
            # to allow client-side bindings for named cursors. In the first
            # case this whole test could be removed, in the second one it would
            # most likely need to be adapted.
            with self.assertRaises(ProgrammingError):
                perform_query()
