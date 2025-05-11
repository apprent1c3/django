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
        Tests that a decorator syntax commit correctly creates a new Reporter object in the database.
        """
        def make_reporter():
            return Reporter.objects.create(first_name="Tintin")

        reporter = make_reporter()
        self.assertSequenceEqual(Reporter.objects.all(), [reporter])

    def test_decorator_syntax_rollback(self):
        @transaction.atomic
        """
        Tests that a database transaction is properly rolled back when an exception is raised within a decorated atomic block.\"\"\"

         \"\"\"Checks that after raising an exception in the transaction, no changes are committed to the database, ensuring data consistency.
        """
        def make_reporter():
            Reporter.objects.create(first_name="Haddock")
            raise Exception("Oops, that's his last name")

        with self.assertRaisesMessage(Exception, "Oops"):
            make_reporter()
        self.assertSequenceEqual(Reporter.objects.all(), [])

    def test_alternate_decorator_syntax_commit(self):
        @transaction.atomic()
        """
        Verifies that the transaction.atomic decorator works correctly with an alternate syntax, ensuring database transactions are handled properly when creating a new Reporter object.
        """
        def make_reporter():
            return Reporter.objects.create(first_name="Tintin")

        reporter = make_reporter()
        self.assertSequenceEqual(Reporter.objects.all(), [reporter])

    def test_alternate_decorator_syntax_rollback(self):
        @transaction.atomic()
        """
        Tests the atomic transaction decorator to ensure it rolls back database changes when an exception is raised, resulting in no data persisted.
        """
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
        Tests that a database transaction is properly rolled back when an exception occurs, 
        ensuring that no changes are committed to the database.\"\"\"
        ```
        """
        with self.assertRaisesMessage(Exception, "Oops"):
            with transaction.atomic():
                Reporter.objects.create(first_name="Haddock")
                raise Exception("Oops, that's his last name")
        self.assertSequenceEqual(Reporter.objects.all(), [])

    def test_nested_commit_commit(self):
        """
        Tests nested database transactions to ensure that commits are handled correctly, verifying the order in which objects are persisted.
        """
        with transaction.atomic():
            reporter1 = Reporter.objects.create(first_name="Tintin")
            with transaction.atomic():
                reporter2 = Reporter.objects.create(
                    first_name="Archibald", last_name="Haddock"
                )
        self.assertSequenceEqual(Reporter.objects.all(), [reporter2, reporter1])

    def test_nested_commit_rollback(self):
        """

        Verifies that a nested database transaction rolls back correctly when an exception occurs.

        This test ensures that the outer transaction remains intact and only the inner transaction is rolled back,
        preventing partial changes from being committed to the database.

        """
        with transaction.atomic():
            reporter = Reporter.objects.create(first_name="Tintin")
            with self.assertRaisesMessage(Exception, "Oops"):
                with transaction.atomic():
                    Reporter.objects.create(first_name="Haddock")
                    raise Exception("Oops, that's his last name")
        self.assertSequenceEqual(Reporter.objects.all(), [reporter])

    def test_nested_rollback_commit(self):
        """

        Tests the behavior of nested transactions, specifically that both inner and outer
        transactions are rolled back when an exception occurs in the inner transaction.

        """
        with self.assertRaisesMessage(Exception, "Oops"):
            with transaction.atomic():
                Reporter.objects.create(last_name="Tintin")
                with transaction.atomic():
                    Reporter.objects.create(last_name="Haddock")
                raise Exception("Oops, that's his first name")
        self.assertSequenceEqual(Reporter.objects.all(), [])

    def test_nested_rollback_rollback(self):
        """

        Verifies that multiple nested atomic transactions are properly rolled back in case of exceptions.

        Ensures that no data is persisted when an exception is raised within nested transactions.

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
        """
        Tests whether Reporter objects are properly ordered after being committed in a merged transaction.
        """
        with transaction.atomic():
            reporter1 = Reporter.objects.create(first_name="Tintin")
            with transaction.atomic(savepoint=False):
                reporter2 = Reporter.objects.create(
                    first_name="Archibald", last_name="Haddock"
                )
        self.assertSequenceEqual(Reporter.objects.all(), [reporter2, reporter1])

    def test_merged_commit_rollback(self):
        """
        Tests that a database transaction correctly rolls back when an exception is raised, ensuring that no changes are committed to the database. Verifies that all created objects are removed after a failed transaction.
        """
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

        Tests that a merged rollback properly reverts changes made in a nested transaction,
        ensuring that no database modifications persist after an exception is raised.

        """
        with self.assertRaisesMessage(Exception, "Oops"):
            with transaction.atomic():
                Reporter.objects.create(last_name="Tintin")
                with transaction.atomic(savepoint=False):
                    Reporter.objects.create(last_name="Haddock")
                raise Exception("Oops, that's his first name")
        self.assertSequenceEqual(Reporter.objects.all(), [])

    def test_merged_rollback_rollback(self):
        """
        Tests that a nested database transaction rollbacks correctly, ensuring no changes persist when an exception occurs within the transaction, and verifying that the outer transaction also rolls back when a subsequent exception is raised.
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
        """

        Checks the behavior of database transactions when creating new objects within nested atomic blocks.
        Verifies that the order of persisted objects is maintained correctly after commit.

        """
        atomic = transaction.atomic()
        with atomic:
            reporter1 = Reporter.objects.create(first_name="Tintin")
            with atomic:
                reporter2 = Reporter.objects.create(
                    first_name="Archibald", last_name="Haddock"
                )
        self.assertSequenceEqual(Reporter.objects.all(), [reporter2, reporter1])

    def test_reuse_commit_rollback(self):
        """
        Tests that a database transaction is properly rolled back when an exception occurs within a nested transaction, ensuring that only the original changes are committed.
        """
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
        Tests that database transactions are properly rolled back in the event of an exception, ensuring that no partial changes are committed to the database, and the database state remains consistent.
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
        Tests that after a nested atomic block raises an exception and rolls back, 
        the outer block also rolls back when it raises an exception, ensuring that 
        no database transactions are committed in case of errors.
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
        """
        Tests that the database transaction is rolled back when an error occurs, ensuring that no data is persisted to the database. This is particularly important in a testing context where data integrity and isolation are crucial.
        """
        with transaction.atomic():
            Reporter.objects.create(first_name="Tintin")
            # atomic block shouldn't rollback, but force it.
            self.assertFalse(transaction.get_rollback())
            transaction.set_rollback(True)
        self.assertSequenceEqual(Reporter.objects.all(), [])

    def test_prevent_rollback(self):
        """
        Test that a rollback is prevented for the outer transaction 
        when an inner transaction encounters a database error and rolls back.
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
        """
        Tests that a transaction is properly rolled back when an exception occurs within a nested transaction.
        Verifies that the database is left in a consistent state after an error, ensuring that no partial changes are committed.
        """
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
        Tests the behavior of a nested transaction with outer rollback.

        Verifies that changes made within an outer transaction are committed when an inner transaction is rolled back due to an exception, but are ultimately rolled back when the outer transaction is rolled back.
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
        """
        Tests that an inner transaction savepoint rollback correctly handles database state, 
        ensuring the outer transaction remains intact when an exception occurs within the inner transaction.
        """
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
        Tests that setting autocommit within an atomic transaction is prevented, ensuring the original autocommit state is preserved at the end of the transaction.
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
        Tests that attempting to call transaction management methods (commit, rollback) within an atomic transaction block raises a TransactionManagementError, as these methods are not allowed in this context.
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
        """
        Tests that an atomic transaction is rolled back and no further queries can be executed when an IntegrityError occurs within the block, ensuring data consistency by preventing partial changes from being committed.
        """
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
        Tests that atomic transactions allow queries to be executed after a failed save operation is recovered from, by successfully updating a model instance after an IntegrityError.
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

        Verifies that Django's atomic transaction functionality prevents database queries 
        from executing after the client connection has been closed in the context of a 
        broken transaction. Ensures that the database state remains consistent in such 
        scenarios by confirming that no objects are created.

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
        """
        Tests that MySQL implicitly rolls back savepoints when a deadlock occurs, reproducing the scenario described in bug #22291.
        """
        Reporter.objects.create(id=1)
        Reporter.objects.create(id=2)

        main_thread_ready = threading.Event()

        def other_thread():
            """
            ..:func other_thread():
                Synchronizes with the main thread to update Reporter objects in the database.

                This function waits for the main thread to signal readiness, then atomically updates the id of all Reporter objects (excluding the one with id=1) to 2, ensuring data integrity and consistency.
            """
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
        """
        Tests that transaction.atomic can successfully wrap callable instances, ensuring support for atomic operations with callable objects.
        """

        class Callable:
            def __call__(self):
                pass

        # Must not raise an exception
        transaction.atomic(Callable())

    @skipUnlessDBFeature("can_release_savepoints")
    def test_atomic_does_not_leak_savepoints_on_failure(self):
        """
        Verifies that atomic transactions do not leak savepoints after a failure, ensuring savepoints are properly released upon rollback.
        """

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
        Tests that transactions are marked for rollback when an error occurs and verifies that no queries can be executed until the end of the 'atomic' block.
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
        """
        Tests that transaction is marked for rollback when an error occurs in autocommit mode. Verifies that the transaction is rolled back and the autocommit state is preserved after an exception is raised.
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
        transaction.set_autocommit(False)
        self.addCleanup(transaction.set_autocommit, True)
        self.addCleanup(transaction.rollback)

    def test_orm_query_after_error_and_rollback(self):
        """
        Tests that ORM queries can be executed after an error occurs and a rollback is performed, even when autocommit mode is disabled, ensuring database consistency and functionality.
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
        Tests the behavior of nested database transactions with a durable outer transaction, verifying that changes made within the inner transaction are correctly committed and visible after the inner transaction is closed, but the order of objects in the database reflects the order of their creation within the transactions.
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
        Checks that a durable atomic block cannot be nested within another atomic block, ensuring database transaction integrity by raising a RuntimeError.
        """
        msg = "A durable atomic block cannot be nested within another atomic block."
        with transaction.atomic(durable=True):
            with self.assertRaisesMessage(RuntimeError, msg):
                with transaction.atomic(durable=True):
                    pass

    def test_nested_inner_durable(self):
        """
        Tests that a durable atomic block cannot be nested within another atomic block, ensuring proper transaction handling and raising a RuntimeError with a descriptive message when such nesting is attempted.
        """
        msg = "A durable atomic block cannot be nested within another atomic block."
        with transaction.atomic():
            with self.assertRaisesMessage(RuntimeError, msg):
                with transaction.atomic(durable=True):
                    pass

    def test_sequence_of_durables(self):
        """
        Tests the creation of a sequence of durable database transactions.

        Verifies that objects created within each transaction are persisted and 
        match the expected instances after transaction completion.
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
