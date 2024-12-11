import sys
import threading
import time
from unittest import skipIf, skipUnless

from django.db import (
    DatabaseError,
    Error,
    IntegrityError,
    OperationalError,
    connection,
    transaction,
)
from django.test import (
    TestCase,
    TransactionTestCase,
    skipIfDBFeature,
    skipUnlessDBFeature,
)

from .models import Reporter


@skipUnlessDBFeature("uses_savepoints")
class AtomicTests(TransactionTestCase):
    """
    Tests for the atomic decorator and context manager.

    The tests make assertions on internal attributes because there isn't a
    robust way to ask the database for its current transaction state.

    Since the decorator syntax is converted into a context manager (see the
    implementation), there are only a few basic tests with the decorator
    syntax and the bulk of the tests use the context manager syntax.
    """

    available_apps = ["transactions"]

    def test_decorator_syntax_commit(self):
        @transaction.atomic
        def make_reporter():
            return Reporter.objects.create(first_name="Tintin")

        reporter = make_reporter()
        self.assertSequenceEqual(Reporter.objects.all(), [reporter])

    def test_decorator_syntax_rollback(self):
        @transaction.atomic
        def make_reporter():
            """

            Creates a new reporter instance in the database.

            This function generates a new reporter with a default first name of 'Haddock' and 
            then intentionally raises an exception, indicating that the provided name is 
            actually the last name of the reporter. The creation of the reporter is wrapped 
            in a transaction to ensure database consistency in case of errors.

            Note:
                The function intentionally raises an exception and does not return a value.
                Use with caution and consider proper exception handling when calling this function.

            """
            Reporter.objects.create(first_name="Haddock")
            raise Exception("Oops, that's his last name")

        with self.assertRaisesMessage(Exception, "Oops"):
            make_reporter()
        self.assertSequenceEqual(Reporter.objects.all(), [])

    def test_alternate_decorator_syntax_commit(self):
        @transaction.atomic()
        """
        Tests the usage of the alternate decorator syntax in a commit transaction context.

        This test case verifies that a database transaction is successfully committed 
        when using the transaction.atomic() decorator with an alternate syntax. It 
        creates a new Reporter object within the transaction and asserts that the 
        object is correctly saved to the database and retrieved upon querying.

        The test covers the scenario where a function decorated with transaction.atomic() 
        performs a database operation, ensuring that the operation is committed as 
        expected and the resulting data is consistent with the expected outcome.
        """
        def make_reporter():
            return Reporter.objects.create(first_name="Tintin")

        reporter = make_reporter()
        self.assertSequenceEqual(Reporter.objects.all(), [reporter])

    def test_alternate_decorator_syntax_rollback(self):
        @transaction.atomic()
        def make_reporter():
            Reporter.objects.create(first_name="Haddock")
            raise Exception("Oops, that's his last name")

        with self.assertRaisesMessage(Exception, "Oops"):
            make_reporter()
        self.assertSequenceEqual(Reporter.objects.all(), [])

    def test_commit(self):
        with transaction.atomic():
            reporter = Reporter.objects.create(first_name="Tintin")
        self.assertSequenceEqual(Reporter.objects.all(), [reporter])

    def test_rollback(self):
        """
        Tests that database transactions are properly rolled back when an exception occurs.

        Verifies that when an exception is raised within a transaction, the database changes made during the transaction are reverted, ensuring data consistency.

        Specifically, this test case checks that a newly created object is not persisted in the database after the transaction is rolled back due to an exception being raised.

        The test asserts that no objects are present in the database after the transaction has been rolled back, confirming that the database remains in its original state despite the attempted creation of a new object. 
        """
        with self.assertRaisesMessage(Exception, "Oops"):
            with transaction.atomic():
                Reporter.objects.create(first_name="Haddock")
                raise Exception("Oops, that's his last name")
        self.assertSequenceEqual(Reporter.objects.all(), [])

    def test_nested_commit_commit(self):
        with transaction.atomic():
            reporter1 = Reporter.objects.create(first_name="Tintin")
            with transaction.atomic():
                reporter2 = Reporter.objects.create(
                    first_name="Archibald", last_name="Haddock"
                )
        self.assertSequenceEqual(Reporter.objects.all(), [reporter2, reporter1])

    def test_nested_commit_rollback(self):
        with transaction.atomic():
            reporter = Reporter.objects.create(first_name="Tintin")
            with self.assertRaisesMessage(Exception, "Oops"):
                with transaction.atomic():
                    Reporter.objects.create(first_name="Haddock")
                    raise Exception("Oops, that's his last name")
        self.assertSequenceEqual(Reporter.objects.all(), [reporter])

    def test_nested_rollback_commit(self):
        with self.assertRaisesMessage(Exception, "Oops"):
            with transaction.atomic():
                Reporter.objects.create(last_name="Tintin")
                with transaction.atomic():
                    Reporter.objects.create(last_name="Haddock")
                raise Exception("Oops, that's his first name")
        self.assertSequenceEqual(Reporter.objects.all(), [])

    def test_nested_rollback_rollback(self):
        with self.assertRaisesMessage(Exception, "Oops"):
            with transaction.atomic():
                Reporter.objects.create(last_name="Tintin")
                with self.assertRaisesMessage(Exception, "Oops"):
                    with transaction.atomic():
                        Reporter.objects.create(first_name="Haddock")
                    raise Exception("Oops, that's his last name")
                raise Exception("Oops, that's his first name")
        self.assertSequenceEqual(Reporter.objects.all(), [])

    def test_merged_commit_commit(self):
        with transaction.atomic():
            reporter1 = Reporter.objects.create(first_name="Tintin")
            with transaction.atomic(savepoint=False):
                reporter2 = Reporter.objects.create(
                    first_name="Archibald", last_name="Haddock"
                )
        self.assertSequenceEqual(Reporter.objects.all(), [reporter2, reporter1])

    def test_merged_commit_rollback(self):
        with transaction.atomic():
            Reporter.objects.create(first_name="Tintin")
            with self.assertRaisesMessage(Exception, "Oops"):
                with transaction.atomic(savepoint=False):
                    Reporter.objects.create(first_name="Haddock")
                    raise Exception("Oops, that's his last name")
        # Writes in the outer block are rolled back too.
        self.assertSequenceEqual(Reporter.objects.all(), [])

    def test_merged_rollback_commit(self):
        with self.assertRaisesMessage(Exception, "Oops"):
            with transaction.atomic():
                Reporter.objects.create(last_name="Tintin")
                with transaction.atomic(savepoint=False):
                    Reporter.objects.create(last_name="Haddock")
                raise Exception("Oops, that's his first name")
        self.assertSequenceEqual(Reporter.objects.all(), [])

    def test_merged_rollback_rollback(self):
        """
        Tests the behavior of rolling back a merged transaction after an exception occurs. 

        This function creates a reporter instance within an atomic transaction block, then attempts to create another instance within a nested transaction block without a savepoint. If the nested block raises an exception, it checks that this exception is propagated upwards correctly, causing the outer transaction to also roll back. 

        The function verifies that both transactions are rolled back by checking that no reporter instances remain in the database after the test. The expected behavior is that both the outer and inner transactions are fully reverted, resulting in no changes to the database.
        """
        with self.assertRaisesMessage(Exception, "Oops"):
            with transaction.atomic():
                Reporter.objects.create(last_name="Tintin")
                with self.assertRaisesMessage(Exception, "Oops"):
                    with transaction.atomic(savepoint=False):
                        Reporter.objects.create(first_name="Haddock")
                    raise Exception("Oops, that's his last name")
                raise Exception("Oops, that's his first name")
        self.assertSequenceEqual(Reporter.objects.all(), [])

    def test_reuse_commit_commit(self):
        atomic = transaction.atomic()
        with atomic:
            reporter1 = Reporter.objects.create(first_name="Tintin")
            with atomic:
                reporter2 = Reporter.objects.create(
                    first_name="Archibald", last_name="Haddock"
                )
        self.assertSequenceEqual(Reporter.objects.all(), [reporter2, reporter1])

    def test_reuse_commit_rollback(self):
        atomic = transaction.atomic()
        with atomic:
            reporter = Reporter.objects.create(first_name="Tintin")
            with self.assertRaisesMessage(Exception, "Oops"):
                with atomic:
                    Reporter.objects.create(first_name="Haddock")
                    raise Exception("Oops, that's his last name")
        self.assertSequenceEqual(Reporter.objects.all(), [reporter])

    def test_reuse_rollback_commit(self):
        """

        Tests the behavior of a database transaction when an exception is raised 
        during the execution of the transaction, ensuring that a rollback occurs 
        and no changes are committed to the database.

        """
        atomic = transaction.atomic()
        with self.assertRaisesMessage(Exception, "Oops"):
            with atomic:
                Reporter.objects.create(last_name="Tintin")
                with atomic:
                    Reporter.objects.create(last_name="Haddock")
                raise Exception("Oops, that's his first name")
        self.assertSequenceEqual(Reporter.objects.all(), [])

    def test_reuse_rollback_rollback(self):
        atomic = transaction.atomic()
        with self.assertRaisesMessage(Exception, "Oops"):
            with atomic:
                Reporter.objects.create(last_name="Tintin")
                with self.assertRaisesMessage(Exception, "Oops"):
                    with atomic:
                        Reporter.objects.create(first_name="Haddock")
                    raise Exception("Oops, that's his last name")
                raise Exception("Oops, that's his first name")
        self.assertSequenceEqual(Reporter.objects.all(), [])

    def test_force_rollback(self):
        """
        Tests that database transactions are properly rolled back when required.

        This test case verifies that a forced rollback of a transaction clears all changes
        made within the transaction, ensuring that the database remains in a consistent state.

        Specifically, it checks that after creating an object within a transaction and then
        forcing a rollback, the object is not persisted in the database.

        """
        with transaction.atomic():
            Reporter.objects.create(first_name="Tintin")
            # atomic block shouldn't rollback, but force it.
            self.assertFalse(transaction.get_rollback())
            transaction.set_rollback(True)
        self.assertSequenceEqual(Reporter.objects.all(), [])

    def test_prevent_rollback(self):
        with transaction.atomic():
            reporter = Reporter.objects.create(first_name="Tintin")
            sid = transaction.savepoint()
            # trigger a database error inside an inner atomic without savepoint
            with self.assertRaises(DatabaseError):
                with transaction.atomic(savepoint=False):
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT no_such_col FROM transactions_reporter")
            # prevent atomic from rolling back since we're recovering manually
            self.assertTrue(transaction.get_rollback())
            transaction.set_rollback(False)
            transaction.savepoint_rollback(sid)
        self.assertSequenceEqual(Reporter.objects.all(), [reporter])

    @skipUnlessDBFeature("can_release_savepoints")
    def test_failure_on_exit_transaction(self):
        with transaction.atomic():
            with self.assertRaises(DatabaseError):
                with transaction.atomic():
                    Reporter.objects.create(last_name="Tintin")
                    self.assertEqual(len(Reporter.objects.all()), 1)
                    # Incorrect savepoint id to provoke a database error.
                    connection.savepoint_ids.append("12")
            with self.assertRaises(transaction.TransactionManagementError):
                len(Reporter.objects.all())
            self.assertIs(connection.needs_rollback, True)
            if connection.savepoint_ids:
                connection.savepoint_ids.pop()
        self.assertSequenceEqual(Reporter.objects.all(), [])


class AtomicInsideTransactionTests(AtomicTests):
    """All basic tests for atomic should also pass within an existing transaction."""

    def setUp(self):
        self.atomic = transaction.atomic()
        self.atomic.__enter__()

    def tearDown(self):
        self.atomic.__exit__(*sys.exc_info())


class AtomicWithoutAutocommitTests(AtomicTests):
    """All basic tests for atomic should also pass when autocommit is turned off."""

    def setUp(self):
        transaction.set_autocommit(False)
        self.addCleanup(transaction.set_autocommit, True)
        # The tests access the database after exercising 'atomic', initiating
        # a transaction ; a rollback is required before restoring autocommit.
        self.addCleanup(transaction.rollback)


@skipUnlessDBFeature("uses_savepoints")
class AtomicMergeTests(TransactionTestCase):
    """Test merging transactions with savepoint=False."""

    available_apps = ["transactions"]

    def test_merged_outer_rollback(self):
        with transaction.atomic():
            Reporter.objects.create(first_name="Tintin")
            with transaction.atomic(savepoint=False):
                Reporter.objects.create(first_name="Archibald", last_name="Haddock")
                with self.assertRaisesMessage(Exception, "Oops"):
                    with transaction.atomic(savepoint=False):
                        Reporter.objects.create(first_name="Calculus")
                        raise Exception("Oops, that's his last name")
                # The third insert couldn't be roll back. Temporarily mark the
                # connection as not needing rollback to check it.
                self.assertTrue(transaction.get_rollback())
                transaction.set_rollback(False)
                self.assertEqual(Reporter.objects.count(), 3)
                transaction.set_rollback(True)
            # The second insert couldn't be roll back. Temporarily mark the
            # connection as not needing rollback to check it.
            self.assertTrue(transaction.get_rollback())
            transaction.set_rollback(False)
            self.assertEqual(Reporter.objects.count(), 3)
            transaction.set_rollback(True)
        # The first block has a savepoint and must roll back.
        self.assertSequenceEqual(Reporter.objects.all(), [])

    def test_merged_inner_savepoint_rollback(self):
        with transaction.atomic():
            reporter = Reporter.objects.create(first_name="Tintin")
            with transaction.atomic():
                Reporter.objects.create(first_name="Archibald", last_name="Haddock")
                with self.assertRaisesMessage(Exception, "Oops"):
                    with transaction.atomic(savepoint=False):
                        Reporter.objects.create(first_name="Calculus")
                        raise Exception("Oops, that's his last name")
                # The third insert couldn't be roll back. Temporarily mark the
                # connection as not needing rollback to check it.
                self.assertTrue(transaction.get_rollback())
                transaction.set_rollback(False)
                self.assertEqual(Reporter.objects.count(), 3)
                transaction.set_rollback(True)
            # The second block has a savepoint and must roll back.
            self.assertEqual(Reporter.objects.count(), 1)
        self.assertSequenceEqual(Reporter.objects.all(), [reporter])


@skipUnlessDBFeature("uses_savepoints")
class AtomicErrorsTests(TransactionTestCase):
    available_apps = ["transactions"]
    forbidden_atomic_msg = "This is forbidden when an 'atomic' block is active."

    def test_atomic_prevents_setting_autocommit(self):
        """

        Tests that setting autocommit is prevented within an atomic transaction block.

        This test case verifies that attempting to change the autocommit setting while
        inside an atomic transaction raises a TransactionManagementError, and that the
        original autocommit setting is preserved. This ensures that the atomicity of the
        transaction is maintained and that the autocommit setting is not modified
        unexpectedly.

        """
        autocommit = transaction.get_autocommit()
        with transaction.atomic():
            with self.assertRaisesMessage(
                transaction.TransactionManagementError, self.forbidden_atomic_msg
            ):
                transaction.set_autocommit(not autocommit)
        # Make sure autocommit wasn't changed.
        self.assertEqual(connection.autocommit, autocommit)

    def test_atomic_prevents_calling_transaction_methods(self):
        """
        Tests that attempting to call transaction management methods within an atomic block raises an exception.

        This test verifies that when working within a transaction atomic block, calling commit or rollback directly on the transaction 
        object is prohibited to prevent inconsistent transaction state, and instead results in a TransactionManagementError being raised.

        The test checks for the specific error message defined in forbidden_atomic_msg when these methods are called, ensuring that the 
        exception is correctly handled and reported in this scenario.
        """
        with transaction.atomic():
            with self.assertRaisesMessage(
                transaction.TransactionManagementError, self.forbidden_atomic_msg
            ):
                transaction.commit()
            with self.assertRaisesMessage(
                transaction.TransactionManagementError, self.forbidden_atomic_msg
            ):
                transaction.rollback()

    def test_atomic_prevents_queries_in_broken_transaction(self):
        r1 = Reporter.objects.create(first_name="Archibald", last_name="Haddock")
        with transaction.atomic():
            r2 = Reporter(first_name="Cuthbert", last_name="Calculus", id=r1.id)
            with self.assertRaises(IntegrityError):
                r2.save(force_insert=True)
            # The transaction is marked as needing rollback.
            msg = (
                "An error occurred in the current transaction. You can't "
                "execute queries until the end of the 'atomic' block."
            )
            with self.assertRaisesMessage(
                transaction.TransactionManagementError, msg
            ) as cm:
                r2.save(force_update=True)
        self.assertIsInstance(cm.exception.__cause__, IntegrityError)
        self.assertEqual(Reporter.objects.get(pk=r1.pk).last_name, "Haddock")

    @skipIfDBFeature("atomic_transactions")
    def test_atomic_allows_queries_after_fixing_transaction(self):
        r1 = Reporter.objects.create(first_name="Archibald", last_name="Haddock")
        with transaction.atomic():
            r2 = Reporter(first_name="Cuthbert", last_name="Calculus", id=r1.id)
            with self.assertRaises(IntegrityError):
                r2.save(force_insert=True)
            # Mark the transaction as no longer needing rollback.
            transaction.set_rollback(False)
            r2.save(force_update=True)
        self.assertEqual(Reporter.objects.get(pk=r1.pk).last_name, "Calculus")

    @skipUnlessDBFeature("test_db_allows_multiple_connections")
    def test_atomic_prevents_queries_in_broken_transaction_after_client_close(self):
        with transaction.atomic():
            Reporter.objects.create(first_name="Archibald", last_name="Haddock")
            connection.close()
            # The connection is closed and the transaction is marked as
            # needing rollback. This will raise an InterfaceError on databases
            # that refuse to create cursors on closed connections (PostgreSQL)
            # and a TransactionManagementError on other databases.
            with self.assertRaises(Error):
                Reporter.objects.create(first_name="Cuthbert", last_name="Calculus")
        # The connection is usable again .
        self.assertEqual(Reporter.objects.count(), 0)


@skipUnlessDBFeature("uses_savepoints")
@skipUnless(connection.vendor == "mysql", "MySQL-specific behaviors")
class AtomicMySQLTests(TransactionTestCase):
    available_apps = ["transactions"]

    @skipIf(threading is None, "Test requires threading")
    def test_implicit_savepoint_rollback(self):
        """MySQL implicitly rolls back savepoints when it deadlocks (#22291)."""
        Reporter.objects.create(id=1)
        Reporter.objects.create(id=2)

        main_thread_ready = threading.Event()

        def other_thread():
            try:
                with transaction.atomic():
                    Reporter.objects.select_for_update().get(id=1)
                    main_thread_ready.wait()
                    # 1) This line locks... (see below for 2)
                    Reporter.objects.exclude(id=1).update(id=2)
            finally:
                # This is the thread-local connection, not the main connection.
                connection.close()

        other_thread = threading.Thread(target=other_thread)
        other_thread.start()

        with self.assertRaisesMessage(OperationalError, "Deadlock found"):
            # Double atomic to enter a transaction and create a savepoint.
            with transaction.atomic():
                with transaction.atomic():
                    Reporter.objects.select_for_update().get(id=2)
                    main_thread_ready.set()
                    # The two threads can't be synchronized with an event here
                    # because the other thread locks. Sleep for a little while.
                    time.sleep(1)
                    # 2) ... and this line deadlocks. (see above for 1)
                    Reporter.objects.exclude(id=2).update(id=1)

        other_thread.join()


class AtomicMiscTests(TransactionTestCase):
    available_apps = ["transactions"]

    def test_wrap_callable_instance(self):
        """#20028 -- Atomic must support wrapping callable instances."""

        class Callable:
            def __call__(self):
                pass

        # Must not raise an exception
        transaction.atomic(Callable())

    @skipUnlessDBFeature("can_release_savepoints")
    def test_atomic_does_not_leak_savepoints_on_failure(self):
        """#23074 -- Savepoints must be released after rollback."""

        # Expect an error when rolling back a savepoint that doesn't exist.
        # Done outside of the transaction block to ensure proper recovery.
        with self.assertRaises(Error):
            # Start a plain transaction.
            with transaction.atomic():
                # Swallow the intentional error raised in the sub-transaction.
                with self.assertRaisesMessage(Exception, "Oops"):
                    # Start a sub-transaction with a savepoint.
                    with transaction.atomic():
                        sid = connection.savepoint_ids[-1]
                        raise Exception("Oops")

                # This is expected to fail because the savepoint no longer exists.
                connection.savepoint_rollback(sid)

    def test_mark_for_rollback_on_error_in_transaction(self):
        with transaction.atomic(savepoint=False):
            # Swallow the intentional error raised.
            with self.assertRaisesMessage(Exception, "Oops"):
                # Wrap in `mark_for_rollback_on_error` to check if the
                # transaction is marked broken.
                with transaction.mark_for_rollback_on_error():
                    # Ensure that we are still in a good state.
                    self.assertFalse(transaction.get_rollback())

                    raise Exception("Oops")

                # mark_for_rollback_on_error marked the transaction as broken …
                self.assertTrue(transaction.get_rollback())

            # … and further queries fail.
            msg = "You can't execute queries until the end of the 'atomic' block."
            with self.assertRaisesMessage(transaction.TransactionManagementError, msg):
                Reporter.objects.create()

        # Transaction errors are reset at the end of an transaction, so this
        # should just work.
        Reporter.objects.create()

    def test_mark_for_rollback_on_error_in_autocommit(self):
        """

        Tests that marking a transaction for rollback on error when autocommit is enabled
        correctly handles the rollback when an exception occurs.

        The function verifies that autocommit is initially enabled and then attempts to
        execute a block of code within a transaction marked for rollback on error. 
        If an exception occurs during this block, it checks that the connection is 
        indeed marked for rollback. Additionally, it ensures that an object can be 
        created after the transaction has been rolled back.

        """
        self.assertTrue(transaction.get_autocommit())

        # Swallow the intentional error raised.
        with self.assertRaisesMessage(Exception, "Oops"):
            # Wrap in `mark_for_rollback_on_error` to check if the transaction
            # is marked broken.
            with transaction.mark_for_rollback_on_error():
                # Ensure that we are still in a good state.
                self.assertFalse(transaction.get_connection().needs_rollback)

                raise Exception("Oops")

            # Ensure that `mark_for_rollback_on_error` did not mark the transaction
            # as broken, since we are in autocommit mode …
            self.assertFalse(transaction.get_connection().needs_rollback)

        # … and further queries work nicely.
        Reporter.objects.create()


class NonAutocommitTests(TransactionTestCase):
    available_apps = []

    def setUp(self):
        """
        Set up the test environment by configuring database transactions.

        This method prepares the test setup by disabling autocommit for database transactions. 
        It also ensures that the autocommit mode is restored to its original state and any pending transactions are rolled back after the test has completed, 
        regardless of the test outcome. This is done to maintain a clean test environment and prevent unintended changes to the database.

        """
        transaction.set_autocommit(False)
        self.addCleanup(transaction.set_autocommit, True)
        self.addCleanup(transaction.rollback)

    def test_orm_query_after_error_and_rollback(self):
        """
        ORM queries are allowed after an error and a rollback in non-autocommit
        mode (#27504).
        """
        r1 = Reporter.objects.create(first_name="Archibald", last_name="Haddock")
        r2 = Reporter(first_name="Cuthbert", last_name="Calculus", id=r1.id)
        with self.assertRaises(IntegrityError):
            r2.save(force_insert=True)
        transaction.rollback()
        Reporter.objects.last()

    def test_orm_query_without_autocommit(self):
        """#24921 -- ORM queries must be possible after set_autocommit(False)."""
        Reporter.objects.create(first_name="Tintin")


class DurableTestsBase:
    available_apps = ["transactions"]

    def test_commit(self):
        with transaction.atomic(durable=True):
            reporter = Reporter.objects.create(first_name="Tintin")
        self.assertEqual(Reporter.objects.get(), reporter)

    def test_nested_outer_durable(self):
        """

        Tests the behavior of nested transactions with the outer transaction being durable.

        This test case verifies that when an outer transaction is marked as durable,
        and a nested transaction is created within it, the expected outcome is that
        the objects created within the nested transaction are committed to the database
        by the time the outer transaction is complete.

        The test checks that the reporters are created in the correct order, demonstrating
        that the nested transaction is committed before the outer transaction.

        """
        with transaction.atomic(durable=True):
            reporter1 = Reporter.objects.create(first_name="Tintin")
            with transaction.atomic():
                reporter2 = Reporter.objects.create(
                    first_name="Archibald",
                    last_name="Haddock",
                )
        self.assertSequenceEqual(Reporter.objects.all(), [reporter2, reporter1])

    def test_nested_both_durable(self):
        msg = "A durable atomic block cannot be nested within another atomic block."
        with transaction.atomic(durable=True):
            with self.assertRaisesMessage(RuntimeError, msg):
                with transaction.atomic(durable=True):
                    pass

    def test_nested_inner_durable(self):
        """
        Tests that a durable atomic block cannot be nested inside another atomic block.

        This test case ensures that attempting to nest a durable atomic block within
        another atomic block raises a RuntimeError, as this is not a supported operation.
        The error message returned by this operation is also verified to match the expected message.

        The purpose of this test is to prevent unexpected behavior that could occur
        if a durable atomic block were allowed to be nested, ensuring the consistency
        and reliability of database transactions.

        Raises:
            RuntimeError: If a durable atomic block is nested within another atomic block.

        """
        msg = "A durable atomic block cannot be nested within another atomic block."
        with transaction.atomic():
            with self.assertRaisesMessage(RuntimeError, msg):
                with transaction.atomic(durable=True):
                    pass

    def test_sequence_of_durables(self):
        with transaction.atomic(durable=True):
            reporter = Reporter.objects.create(first_name="Tintin 1")
        self.assertEqual(Reporter.objects.get(first_name="Tintin 1"), reporter)
        with transaction.atomic(durable=True):
            reporter = Reporter.objects.create(first_name="Tintin 2")
        self.assertEqual(Reporter.objects.get(first_name="Tintin 2"), reporter)


class DurableTransactionTests(DurableTestsBase, TransactionTestCase):
    pass


class DurableTests(DurableTestsBase, TestCase):
    pass
