import decimal
from unittest import mock

from django.core.management.color import no_style
from django.db import NotSupportedError, connection, transaction
from django.db.backends.base.operations import BaseDatabaseOperations
from django.db.models import DurationField
from django.db.models.expressions import Col
from django.db.models.lookups import Exact
from django.test import (
    SimpleTestCase,
    TestCase,
    TransactionTestCase,
    override_settings,
    skipIfDBFeature,
)
from django.utils import timezone
from django.utils.deprecation import RemovedInDjango60Warning

from ..models import Author, Book


class SimpleDatabaseOperationTests(SimpleTestCase):
    may_require_msg = "subclasses of BaseDatabaseOperations may require a %s() method"

    def setUp(self):
        self.ops = BaseDatabaseOperations(connection=connection)

    def test_deferrable_sql(self):
        self.assertEqual(self.ops.deferrable_sql(), "")

    def test_end_transaction_rollback(self):
        self.assertEqual(self.ops.end_transaction_sql(success=False), "ROLLBACK;")

    def test_no_limit_value(self):
        """
        Tests that calling no_limit_value raises a NotImplementedError with a message indicating that the operation may require a 'no_limit_value' value to be set
        """
        with self.assertRaisesMessage(
            NotImplementedError, self.may_require_msg % "no_limit_value"
        ):
            self.ops.no_limit_value()

    def test_quote_name(self):
        """
        Test that the quote_name method raises a NotImplementedError.

        This test case verifies that the quote_name method is not implemented, as expected,
        and raises a NotImplementedError with a specific error message indicating that 
        the 'quote_name' operation may require implementation.

        Raises:
            NotImplementedError: if the quote_name method is not implemented.

        """
        with self.assertRaisesMessage(
            NotImplementedError, self.may_require_msg % "quote_name"
        ):
            self.ops.quote_name("a")

    def test_regex_lookup(self):
        """

        Tests that attempting to use a regex lookup raises a NotImplementedError.

        This test case verifies that the regex_lookup function is not currently implemented
        and will raise an error when called, providing a specific message indicating that
        this functionality may be required in the future.

        """
        with self.assertRaisesMessage(
            NotImplementedError, self.may_require_msg % "regex_lookup"
        ):
            self.ops.regex_lookup(lookup_type="regex")

    def test_set_time_zone_sql(self):
        self.assertEqual(self.ops.set_time_zone_sql(), "")

    def test_sql_flush(self):
        """
        Tests that subclasses of BaseDatabaseOperations implement the sql_flush method.

        This test ensures that any subclass of BaseDatabaseOperations provides a concrete
        implementation of the sql_flush method, which is required for proper database
        operations. The test verifies that attempting to call sql_flush on a subclass
        without an implementation raises a NotImplementedError with a descriptive message.

        Raises:
            NotImplementedError: If the sql_flush method is not implemented in a subclass.

        """
        msg = "subclasses of BaseDatabaseOperations must provide an sql_flush() method"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.ops.sql_flush(None, None)

    def test_pk_default_value(self):
        self.assertEqual(self.ops.pk_default_value(), "DEFAULT")

    def test_tablespace_sql(self):
        self.assertEqual(self.ops.tablespace_sql(None), "")

    def test_sequence_reset_by_name_sql(self):
        self.assertEqual(self.ops.sequence_reset_by_name_sql(None, []), [])

    def test_adapt_unknown_value_decimal(self):
        """

        Tests the adaptation of an unknown value, specifically a Decimal instance, to ensure it is handled correctly.

        The function verifies that the adapt_unknown_value method returns the same result as the adapt_decimalfield_value method when given a Decimal value, confirming that unknown Decimal values are properly adapted.

        """
        value = decimal.Decimal("3.14")
        self.assertEqual(
            self.ops.adapt_unknown_value(value),
            self.ops.adapt_decimalfield_value(value),
        )

    def test_adapt_unknown_value_date(self):
        """

        Tests that the adapt_unknown_value method correctly handles date values by comparing its output with the adapt_datefield_value method.

        The purpose of this test is to ensure that when an unknown value of date type is encountered, 
        it is correctly adapted to a format that can be processed by the database. 

        :raises AssertionError: if the adapted unknown value does not match the expected adapted datefield value.

        """
        value = timezone.now().date()
        self.assertEqual(
            self.ops.adapt_unknown_value(value), self.ops.adapt_datefield_value(value)
        )

    def test_adapt_unknown_value_time(self):
        value = timezone.now().time()
        self.assertEqual(
            self.ops.adapt_unknown_value(value), self.ops.adapt_timefield_value(value)
        )

    def test_adapt_timefield_value_none(self):
        self.assertIsNone(self.ops.adapt_timefield_value(None))

    def test_adapt_datetimefield_value_none(self):
        self.assertIsNone(self.ops.adapt_datetimefield_value(None))

    def test_adapt_timefield_value(self):
        msg = "Django does not support timezone-aware times."
        with self.assertRaisesMessage(ValueError, msg):
            self.ops.adapt_timefield_value(timezone.make_aware(timezone.now()))

    @override_settings(USE_TZ=False)
    def test_adapt_timefield_value_unaware(self):
        now = timezone.now()
        self.assertEqual(self.ops.adapt_timefield_value(now), str(now))

    def test_format_for_duration_arithmetic(self):
        """
        Tests that the format_for_duration_arithmetic method raises a NotImplementedError.

        Confirms that an attempt to format a duration for arithmetic operations without a
        proper implementation results in the correct error being raised with the expected message.

        Raises:
            NotImplementedError: When format_for_duration_arithmetic is called without implementation.

        """
        msg = self.may_require_msg % "format_for_duration_arithmetic"
        with self.assertRaisesMessage(NotImplementedError, msg):
            self.ops.format_for_duration_arithmetic(None)

    def test_date_extract_sql(self):
        """
        Tests that the date_extract_sql method raises a NotImplementedError.

        This test ensures that an error is correctly raised when attempting to extract date components using SQL, as this functionality is not implemented.

        :raises NotImplementedError: when date_extract_sql is called.
        :raises AssertionError: if the expected error message is not raised.

        """
        with self.assertRaisesMessage(
            NotImplementedError, self.may_require_msg % "date_extract_sql"
        ):
            self.ops.date_extract_sql(None, None, None)

    def test_time_extract_sql(self):
        """

        Tests that the time_extract_sql function raises a NotImplementedError.

        This test case verifies that the time_extract_sql operation is not implemented
        by checking that it raises a NotImplementedError with the expected message.
        The function is passed None values for the three required parameters to simulate
        a basic usage scenario.

        Args:
            None

        Raises:
            NotImplementedError: If the time_extract_sql function is called.

        Note:
            This test does not verify the correctness of the time_extract_sql function
            itself, but rather that it correctly reports its implementation status.

        """
        with self.assertRaisesMessage(
            NotImplementedError, self.may_require_msg % "date_extract_sql"
        ):
            self.ops.time_extract_sql(None, None, None)

    def test_date_trunc_sql(self):
        """
        Tests that the date_trunc_sql method raises a NotImplementedError.

        This test case verifies that attempting to use the date_trunc_sql method
        results in the expected error, which is typically required by certain
        database operations. The test checks that the error message includes
        the required message related to 'date_trunc_sql'.

        :raises NotImplementedError: with a message indicating that date_trunc_sql is not implemented
        """
        with self.assertRaisesMessage(
            NotImplementedError, self.may_require_msg % "date_trunc_sql"
        ):
            self.ops.date_trunc_sql(None, None, None)

    def test_time_trunc_sql(self):
        """
        Tests that the time_trunc_sql operation raises a NotImplementedError. 

        This test case verifies that the time_trunc_sql method, responsible for implementing SQL time truncation, correctly signals that it is not implemented by raising an exception with an informative message.
        """
        with self.assertRaisesMessage(
            NotImplementedError, self.may_require_msg % "time_trunc_sql"
        ):
            self.ops.time_trunc_sql(None, None, None)

    def test_datetime_trunc_sql(self):
        with self.assertRaisesMessage(
            NotImplementedError, self.may_require_msg % "datetime_trunc_sql"
        ):
            self.ops.datetime_trunc_sql(None, None, None, None)

    def test_datetime_cast_date_sql(self):
        """
        Tests that attempting to cast a datetime to a date in SQL raises a NotImplementedError.

        This test case verifies that the datetime_cast_date_sql operation is not implemented,
        as indicated by raising a NotImplementedError with a specific message.
        The error is expected when the operation is invoked with None values for the connection, field, and value parameters.
        """
        with self.assertRaisesMessage(
            NotImplementedError, self.may_require_msg % "datetime_cast_date_sql"
        ):
            self.ops.datetime_cast_date_sql(None, None, None)

    def test_datetime_cast_time_sql(self):
        """
        Test that datetime_cast_time_sql raises a NotImplementedError.

        This test case verifies that the datetime_cast_time_sql operation correctly handles the case when no inputs are provided, resulting in an error due to the lack of implementation. The expected exception message is checked to ensure it matches the predefined format.
        """
        with self.assertRaisesMessage(
            NotImplementedError, self.may_require_msg % "datetime_cast_time_sql"
        ):
            self.ops.datetime_cast_time_sql(None, None, None)

    def test_datetime_extract_sql(self):
        """
        Tests that the datetime_extract_sql method raises a NotImplementedError when invoked.

        This test case verifies that the datetime_extract_sql operation is not implemented, 
        which is indicated by raising a NotImplementedError with a specific error message.

        The test checks that the expected error message is present when the exception is raised, 
        confirming that the datetime_extract_sql method is indeed not implemented.

        :raises NotImplementedError: When datetime_extract_sql is invoked.

        """
        with self.assertRaisesMessage(
            NotImplementedError, self.may_require_msg % "datetime_extract_sql"
        ):
            self.ops.datetime_extract_sql(None, None, None, None)

    def test_prepare_join_on_clause(self):
        """

        Tests the preparation of a join on clause by the ops instance.

        This function verifies that the :meth:`prepare_join_on_clause` method correctly 
        constructs the left-hand side (LHS) and right-hand side (RHS) expressions 
        for joining two database tables based on a foreign key relationship.

        The test case checks if the resulting LHS expression corresponds to the primary key 
        column of the author table and the RHS expression corresponds to the foreign key 
        column of the book table that references the author table.

        """
        author_table = Author._meta.db_table
        author_id_field = Author._meta.get_field("id")
        book_table = Book._meta.db_table
        book_fk_field = Book._meta.get_field("author")
        lhs_expr, rhs_expr = self.ops.prepare_join_on_clause(
            author_table,
            author_id_field,
            book_table,
            book_fk_field,
        )
        self.assertEqual(lhs_expr, Col(author_table, author_id_field))
        self.assertEqual(rhs_expr, Col(book_table, book_fk_field))


class DatabaseOperationTests(TestCase):
    def setUp(self):
        self.ops = BaseDatabaseOperations(connection=connection)

    @skipIfDBFeature("supports_over_clause")
    def test_window_frame_raise_not_supported_error(self):
        msg = "This backend does not support window expressions."
        with self.assertRaisesMessage(NotSupportedError, msg):
            self.ops.window_frame_rows_start_end()

    @skipIfDBFeature("can_distinct_on_fields")
    def test_distinct_on_fields(self):
        msg = "DISTINCT ON fields is not supported by this database backend"
        with self.assertRaisesMessage(NotSupportedError, msg):
            self.ops.distinct_sql(["a", "b"], None)

    @skipIfDBFeature("supports_temporal_subtraction")
    def test_subtract_temporals(self):
        """
        Tests subtraction of temporal fields is not supported by the current database backend.

        Checks that attempting to subtract temporal values results in a NotSupportedError,
        confirming the database backend does not support subtraction operations on temporal fields.
        The test ensures that an expected error message is raised with a clear description of the unsupported operation.

        """
        duration_field = DurationField()
        duration_field_internal_type = duration_field.get_internal_type()
        msg = (
            "This backend does not support %s subtraction."
            % duration_field_internal_type
        )
        with self.assertRaisesMessage(NotSupportedError, msg):
            self.ops.subtract_temporals(duration_field_internal_type, None, None)


class SqlFlushTests(TransactionTestCase):
    available_apps = ["backends"]

    def test_sql_flush_no_tables(self):
        self.assertEqual(connection.ops.sql_flush(no_style(), []), [])

    def test_execute_sql_flush_statements(self):
        """

        Tests the execution of SQL flush statements, ensuring that all data is properly removed 
        from the database and that auto-incrementing primary keys are reset to their initial values.

        Verifies the existence of data in the Author and Book models before and after flushing 
        the database, and checks that the primary key sequence is reset correctly after flushing, 
        if the database backend supports sequence reset.

        """
        with transaction.atomic():
            author = Author.objects.create(name="George Orwell")
            Book.objects.create(author=author)
            author = Author.objects.create(name="Harper Lee")
            Book.objects.create(author=author)
            Book.objects.create(author=author)
            self.assertIs(Author.objects.exists(), True)
            self.assertIs(Book.objects.exists(), True)

        sql_list = connection.ops.sql_flush(
            no_style(),
            [Author._meta.db_table, Book._meta.db_table],
            reset_sequences=True,
            allow_cascade=True,
        )
        connection.ops.execute_sql_flush(sql_list)

        with transaction.atomic():
            self.assertIs(Author.objects.exists(), False)
            self.assertIs(Book.objects.exists(), False)
            if connection.features.supports_sequence_reset:
                author = Author.objects.create(name="F. Scott Fitzgerald")
                self.assertEqual(author.pk, 1)
                book = Book.objects.create(author=author)
                self.assertEqual(book.pk, 1)


class DeprecationTests(TestCase):
    def test_field_cast_sql_warning(self):
        """
        Tests that calling :meth:`DatabaseOperations.field_cast_sql` raises a 
        :exc:`RemovedInDjango60Warning` as it is deprecated in favor of 
        :meth:`DatabaseOperations.lookup_cast`.

        This test case helps ensure that users are properly warned when using the 
        deprecated method, encouraging them to update their code to use the 
        recommended replacement for future compatibility.

        The warning message includes instructions on how to update the code, citing 
        the recommended use of :meth:`DatabaseOperations.lookup_cast` instead of 
        :meth:`DatabaseOperations.field_cast_sql`.

        """
        base_ops = BaseDatabaseOperations(connection=connection)
        msg = (
            "DatabaseOperations.field_cast_sql() is deprecated use "
            "DatabaseOperations.lookup_cast() instead."
        )
        with self.assertRaisesMessage(RemovedInDjango60Warning, msg):
            base_ops.field_cast_sql("integer", "IntegerField")

    def test_field_cast_sql_usage_warning(self):
        compiler = Author.objects.all().query.get_compiler(connection.alias)
        msg = (
            "The usage of DatabaseOperations.field_cast_sql() is deprecated. Implement "
            "DatabaseOperations.lookup_cast() instead."
        )
        with mock.patch.object(connection.ops.__class__, "field_cast_sql"):
            with self.assertRaisesMessage(RemovedInDjango60Warning, msg):
                Exact("name", "book__author__name").as_sql(compiler, connection)
