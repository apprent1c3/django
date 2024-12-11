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
        """
        Tests that using a decorator to create a database transaction results in the expected database state.

        Verifies that when a reporter object is created within a transaction, it is properly committed to the database, and the database state is updated accordingly.

        The test checks that the created reporter object is correctly added to the database by asserting that the sequence of all reporter objects in the database matches the expected sequence containing the created object.
        """
        def make_reporter():
            return Reporter.objects.create(first_name="Tintin")

        reporter = make_reporter()
        self.assertSequenceEqual(Reporter.objects.all(), [reporter])

    def test_decorator_syntax_rollback(self):
        @transaction.atomic
        def make_reporter():
            """
            ..: Creates a new Reporter object with a predefined first name and attempts to save it to the database.

                The function is designed to be executed within a database transaction, ensuring that either all changes are committed or none are, in case of an error.

                :raises Exception: If the function completes its task, it will intentionally raise an exception with a message indicating that the provided name is actually a last name, not a first name.
                :note: The function does not take any parameters and does not return any values.
            """
            Reporter.objects.create(first_name="Haddock")
            raise Exception("Oops, that's his last name")

        with self.assertRaisesMessage(Exception, "Oops"):
            make_reporter()
        self.assertSequenceEqual(Reporter.objects.all(), [])

    def test_alternate_decorator_syntax_commit(self):
        @transaction.atomic()
        """
        ^{
            :param self: Test case instance
            :return: None

            Tests the alternate decorator syntax for database transactions.
            This test creates a new reporter object within a transactional block,
            ensuring that the object is committed to the database.
            It then verifies that the created reporter is the only object in the database.
         }
        """
        def make_reporter():
            return Reporter.objects.create(first_name="Tintin")

        reporter = make_reporter()
        self.assertSequenceEqual(Reporter.objects.all(), [reporter])

    def test_alternate_decorator_syntax_rollback(self):
        @transaction.atomic()
        """
        Tests the behavior of the atomic transaction decorator when an exception is raised within the decorated function, ensuring that the database remains in a consistent state after a rollback. 

        The test verifies that the creation of a Reporter object is successfully rolled back when an exception occurs within the atomic block, resulting in no objects being persisted in the database.
        """
        def make_reporter():
            """

            Create a new reporter instance in the database.

            This function attempts to create a new reporter with a hardcoded first name.
            However, it intentionally raises an exception after the database transaction has started,
            resulting in the transaction being rolled back and the reporter not being created.
            The purpose of this function appears to be testing or demonstrating error handling in database transactions.

            """
            Reporter.objects.create(first_name="Haddock")
            raise Exception("Oops, that's his last name")

        with self.assertRaisesMessage(Exception, "Oops"):
            make_reporter()
        self.assertSequenceEqual(Reporter.objects.all(), [])

    def test_commit(self):
        """
        Tests that a reporter object is correctly committed to the database.

        This test case verifies that a newly created reporter object is successfully
        saved and retrieved from the database, ensuring data consistency and integrity.

        The test uses a transaction to isolate the database operations, allowing for a
        clean and predictable environment to verify the expected behavior.

        After creating a reporter object, it checks that the object is the only one
        present in the database, confirming that the commit operation was successful.
        """
        with transaction.atomic():
            reporter = Reporter.objects.create(first_name="Tintin")
        self.assertSequenceEqual(Reporter.objects.all(), [reporter])

    def test_rollback(self):
        """

        Tests the rollback functionality of database transactions.

        Verifies that when an exception occurs within a transaction, all changes are rolled back, 
        leaving the database in its original state. In this case, it checks that a newly created 
        Reporter object is not persisted after the transaction is rolled back due to an exception.

        The test expects the database to be empty at the end, confirming that the rollback was successful.

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
        """
        Tests the behavior of nested database transactions.

        Verifies that if an inner transaction raises an exception, the changes made 
        by the inner transaction are rolled back, and the outer transaction remains 
        intact. In this case, it checks that a reporter is successfully created in 
        the outer transaction and that a subsequent reporter creation in the inner 
        transaction is rolled back when an exception is raised.

        The test expects the database to be left in a state where only the initially 
        created reporter exists after the inner transaction has been rolled back due 
        to the exception.
        """
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
        """
        Tests that nested atomic transactions properly roll back when exceptions are raised.

        The test creates a reporter object within a transaction, then within another nested transaction,
        it attempts to create another reporter object, but raises an exception. Upon catching the exception,
        it raises another exception, and verifies that both transactions are properly rolled back,
        leaving no reporter objects in the database.

        Validates the atomicity of database transactions in the face of nested exceptions.
        """
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
        """

        Tests the behavior of transaction atomicity when merging and rolling back commits.
        Verifies that when an inner transaction raises an exception, the outer transaction is also rolled back,
        resulting in no changes being persisted to the database. In this case, Reporter objects created within
        the transaction are expected to be deleted when the exception occurs.

        """
        with self.assertRaisesMessage(Exception, "Oops"):
            with transaction.atomic():
                Reporter.objects.create(last_name="Tintin")
                with transaction.atomic(savepoint=False):
                    Reporter.objects.create(last_name="Haddock")
                raise Exception("Oops, that's his first name")
        self.assertSequenceEqual(Reporter.objects.all(), [])

    def test_merged_rollback_rollback(self):
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
        Tests the behavior of database transactions when an exception occurs within a nested transaction block. 

        Verifies that after raising an exception, the outer transaction is properly rolled back, ensuring that no partial changes are committed to the database. 

        In this case, it checks that creating a `Reporter` object within a nested transaction block does not persist when an exception is raised, resulting in an empty list of `Reporter` objects after the transaction has been rolled back.
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
        """
        Tests the behavior of transactions when multiple rollbacks are triggered.

        Verifies that when a nested transaction raises an exception and rolls back, the outer transaction is also rolled back.
        Ensures that no database changes are committed when an exception occurs in either the inner or outer transaction.

        Specifically, this test checks that an attempt to create a Reporter object within a nested transaction that raises an exception
        will result in no objects being created in the database, even if the outer transaction also raises an exception.

        The expected outcome is that the Reporter table remains empty, with no objects created despite the attempts to create them within the transactions.
        """
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
        with transaction.atomic():
            Reporter.objects.create(first_name="Tintin")
            # atomic block shouldn't rollback, but force it.
            self.assertFalse(transaction.get_rollback())
            transaction.set_rollback(True)
        self.assertSequenceEqual(Reporter.objects.all(), [])

    def test_prevent_rollback(self):
        """

        Tests the prevention of database transaction rollback in case of an error.

        This test simulates a scenario where a database error occurs during a nested 
        transaction. It verifies that the outer transaction is not rolled back, allowing 
        the changes made before the error to be persisted. The test ensures that the 
        database remains in a consistent state, with the created reporter instance 
        remaining in the database after the error has been handled.

        The test covers the following key aspects:

        * Creation of a database transaction and a savepoint
        * Simulation of a database error using a non-existent column
        * Verification of the rollback status after the error
        * Reverting the rollback status and rolling back to the savepoint
        * Validation of the database state after the error has been handled

        """
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
        """

        Tests the behavior of a merged outer rollback in the context of nested transactions.

        Verifies that when an exception occurs within a nested transaction, and savepoints are
        disabled, the entire transaction is rolled back, resulting in no objects being persisted.

        Also checks that the rollback flag can be manipulated to control the outcome of the
        transaction, ensuring that the expected state is achieved.

        The test case covers the following scenarios:

        * Successful creation of objects within the outer transaction
        * Failed creation of objects within a nested transaction due to an exception
        * Verification of the rollback flag and its impact on the transaction outcome
        * Validation of the final state, ensuring that no objects are persisted after the transaction is rolled back.

        """
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

        This test ensures that attempts to modify the autocommit setting while an atomic
        transaction is in progress result in a TransactionManagementError, and that
        the original autocommit setting is preserved.

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
        Test that transaction methods cannot be called within an atomic transaction block.

            Verify that attempting to commit or rollback a transaction while inside an
            atomic transaction block raises a TransactionManagementError with the expected message.

            This ensures that the atomic transaction context is properly enforced,
            preventing manual transaction management attempts within the block.
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
        """
        Tests that after an IntegrityError within an atomic transaction is handled, 
        it is possible to perform further database operations.

        This test verifies that a transaction can be fixed and continue to execute 
        queries against the database, allowing for atomic updates to be performed 
        even when initial operations fail due to integrity constraints.

        The test scenario simulates a situation where an attempt to insert a new 
        record with an existing primary key fails, and then the transaction is 
        recovered to update the existing record instead, ensuring data consistency 
        and atomicity in the presence of errors.
        """
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
        """

        Tests that atomic transactions prevent further queries from being executed 
        after the database connection has been closed, ensuring data consistency.

        Verifies that when a transaction is marked as atomic and the database connection 
        is closed within that transaction, any subsequent queries will raise an error, 
        thus preventing potential data corruption.

        The test case also checks that the database remains in a consistent state 
        after the failed transaction, with no partial changes committed.

        """
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
        """

        Tests the behavior of marking a transaction for rollback when an error occurs within it.

        This function verifies that when an exception is raised within a transaction marked for rollback,
        the transaction is indeed marked for rollback and that no further database queries can be executed
        until the transaction is committed or rolled back. It also ensures that once the transaction is
        rolled back, normal database operations can resume.

        The test covers two main scenarios:

        *   An exception is raised within a transaction marked for rollback, and the transaction is
            correctly marked for rollback.
        *   After an exception occurs and the transaction is marked for rollback, attempting to execute a
            database query results in a TransactionManagementError.

        """
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
        Sets up the database transaction environment for testing.

        Disables autocommit mode to allow for manual transaction control and
        ensures that any changes made during the test are rolled back after
        completion, maintaining a clean database state. The autocommit mode
        is restored to its original state after the test finishes.
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
        """
        Tests that a newly created Reporter object is correctly persisted to the database.

        Verifies that after a successful database transaction, the persisted Reporter object 
        can be retrieved from the database and matches the originally created object.

        Ensures data consistency by checking that the created and retrieved objects are 
        the same instance, guaranteeing the correctness of the database operations. 
        """
        with transaction.atomic(durable=True):
            reporter = Reporter.objects.create(first_name="Tintin")
        self.assertEqual(Reporter.objects.get(), reporter)

    def test_nested_outer_durable(self):
        """

        Tests the behavior of nested transactions with an outer durable transaction.

        This test case verifies that when a durable outer transaction is nested with a non-durable inner transaction,
        the changes made in the inner transaction are committed to the database before the outer transaction is committed.
        The test ensures that the order of objects in the database reflects the sequence of commits, with objects from the inner transaction appearing before objects from the outer transaction.


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
        """
        Tests that a durable atomic block cannot be nested within another atomic block.

        Verifies that attempting to nest two durable atomic blocks raises a RuntimeError 
        with a specific error message, ensuring that the transaction handling mechanism 
        prevents such invalid nesting scenarios.

        :raises: RuntimeError if a durable atomic block is nested within another atomic block
        """
        msg = "A durable atomic block cannot be nested within another atomic block."
        with transaction.atomic(durable=True):
            with self.assertRaisesMessage(RuntimeError, msg):
                with transaction.atomic(durable=True):
                    pass

    def test_nested_inner_durable(self):
        """

        Tests that a durable atomic block cannot be nested within another atomic block.

        This test ensures that attempting to create a durable atomic block inside an existing
        atomic block raises a RuntimeError, as this is not a supported operation.

        """
        msg = "A durable atomic block cannot be nested within another atomic block."
        with transaction.atomic():
            with self.assertRaisesMessage(RuntimeError, msg):
                with transaction.atomic(durable=True):
                    pass

    def test_sequence_of_durables(self):
        """

        Tests the creation of Reporter objects within atomic transactions with durable mode enabled.

        This test case ensures that new Reporter instances are correctly persisted to the database
        and can be retrieved after the transaction has been committed. It verifies the object's identity
        by comparing the original instance with the one retrieved from the database.

        """
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
