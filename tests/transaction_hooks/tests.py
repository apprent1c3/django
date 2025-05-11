from django.db import connection, transaction
from django.test import TransactionTestCase, skipUnlessDBFeature

from .models import Thing


class ForcedError(Exception):
    pass


@skipUnlessDBFeature("supports_transactions")
class TestConnectionOnCommit(TransactionTestCase):
    """
    Tests for transaction.on_commit().

    Creation/checking of database objects in parallel with callback tracking is
    to verify that the behavior of the two match in all tested cases.
    """

    available_apps = ["transaction_hooks"]

    def setUp(self):
        self.notified = []

    def notify(self, id_):
        if id_ == "error":
            raise ForcedError()
        self.notified.append(id_)

    def do(self, num):
        """Create a Thing instance and notify about it."""
        Thing.objects.create(num=num)
        transaction.on_commit(lambda: self.notify(num))

    def assertDone(self, nums):
        self.assertNotified(nums)
        self.assertEqual(sorted(t.num for t in Thing.objects.all()), sorted(nums))

    def assertNotified(self, nums):
        self.assertEqual(self.notified, nums)

    def test_executes_immediately_if_no_transaction(self):
        self.do(1)
        self.assertDone([1])

    def test_robust_if_no_transaction(self):
        """
        Tests if transaction.on_commit callbacks marked as robust handle exceptions correctly when no transaction is present.
        """
        def robust_callback():
            raise ForcedError("robust callback")

        with self.assertLogs("django.db.backends.base", "ERROR") as cm:
            transaction.on_commit(robust_callback, robust=True)
            self.do(1)

        self.assertDone([1])
        log_record = cm.records[0]
        self.assertEqual(
            log_record.getMessage(),
            "Error calling TestConnectionOnCommit.test_robust_if_no_transaction."
            "<locals>.robust_callback in on_commit() (robust callback).",
        )
        self.assertIsNotNone(log_record.exc_info)
        raised_exception = log_record.exc_info[1]
        self.assertIsInstance(raised_exception, ForcedError)
        self.assertEqual(str(raised_exception), "robust callback")

    def test_robust_transaction(self):
        """
        Tests the robust transaction functionality, ensuring that a raised exception within an on_commit callback does not prevent the transaction from committing and that the error is properly logged.
        """
        def robust_callback():
            raise ForcedError("robust callback")

        with self.assertLogs("django.db.backends", "ERROR") as cm:
            with transaction.atomic():
                transaction.on_commit(robust_callback, robust=True)
                self.do(1)

        self.assertDone([1])
        log_record = cm.records[0]
        self.assertEqual(
            log_record.getMessage(),
            "Error calling TestConnectionOnCommit.test_robust_transaction.<locals>."
            "robust_callback in on_commit() during transaction (robust callback).",
        )
        self.assertIsNotNone(log_record.exc_info)
        raised_exception = log_record.exc_info[1]
        self.assertIsInstance(raised_exception, ForcedError)
        self.assertEqual(str(raised_exception), "robust callback")

    def test_delays_execution_until_after_transaction_commit(self):
        with transaction.atomic():
            self.do(1)
            self.assertNotified([])
        self.assertDone([1])

    def test_does_not_execute_if_transaction_rolled_back(self):
        """
        Tests that the function does not execute when a transaction is rolled back, ensuring database consistency and preventing unwanted actions in case of errors or exceptions.
        """
        try:
            with transaction.atomic():
                self.do(1)
                raise ForcedError()
        except ForcedError:
            pass

        self.assertDone([])

    def test_executes_only_after_final_transaction_committed(self):
        """
        Verify that certain operations are executed only after the outermost database transaction is committed, ensuring data consistency and atomicity.
        """
        with transaction.atomic():
            with transaction.atomic():
                self.do(1)
                self.assertNotified([])
            self.assertNotified([])
        self.assertDone([1])

    def test_discards_hooks_from_rolled_back_savepoint(self):
        """

        Verifies that hooks are properly discarded when a savepoint is rolled back, 
        ensuring only successfully committed actions are retained.

        """
        with transaction.atomic():
            # one successful savepoint
            with transaction.atomic():
                self.do(1)
            # one failed savepoint
            try:
                with transaction.atomic():
                    self.do(2)
                    raise ForcedError()
            except ForcedError:
                pass
            # another successful savepoint
            with transaction.atomic():
                self.do(3)

        # only hooks registered during successful savepoints execute
        self.assertDone([1, 3])

    def test_no_hooks_run_from_failed_transaction(self):
        """If outer transaction fails, no hooks from within it run."""
        try:
            with transaction.atomic():
                with transaction.atomic():
                    self.do(1)
                raise ForcedError()
        except ForcedError:
            pass

        self.assertDone([])

    def test_inner_savepoint_rolled_back_with_outer(self):
        """
        Tests that when an inner savepoint is rolled back due to an exception, 
         the outer transaction remains active, allowing subsequent operations to proceed.
        """
        with transaction.atomic():
            try:
                with transaction.atomic():
                    with transaction.atomic():
                        self.do(1)
                    raise ForcedError()
            except ForcedError:
                pass
            self.do(2)

        self.assertDone([2])

    def test_no_savepoints_atomic_merged_with_outer(self):
        """
        Tests that an inner transaction with no savepoint is properly handled when merged with an outer transaction and an exception occurs, verifying that no intermediate work is saved.
        """
        with transaction.atomic():
            with transaction.atomic():
                self.do(1)
                try:
                    with transaction.atomic(savepoint=False):
                        raise ForcedError()
                except ForcedError:
                    pass

        self.assertDone([])

    def test_inner_savepoint_does_not_affect_outer(self):
        """
        Tests that an inner savepoint does not affect the outer transaction, 
        ensuring that database operations are committed correctly even when an error occurs in a nested transaction.
        """
        with transaction.atomic():
            with transaction.atomic():
                self.do(1)
                try:
                    with transaction.atomic():
                        raise ForcedError()
                except ForcedError:
                    pass

        self.assertDone([1])

    def test_runs_hooks_in_order_registered(self):
        """
        Verifies that hooks are executed in the order they were registered, even when nested transactions are involved.
        """
        with transaction.atomic():
            self.do(1)
            with transaction.atomic():
                self.do(2)
            self.do(3)

        self.assertDone([1, 2, 3])

    def test_hooks_cleared_after_successful_commit(self):
        """
        Tests that hooks are properly cleared after a successful commit, ensuring that hooks from previous transactions do not interfere with subsequent ones.
        """
        with transaction.atomic():
            self.do(1)
        with transaction.atomic():
            self.do(2)

        self.assertDone([1, 2])  # not [1, 1, 2]

    def test_hooks_cleared_after_rollback(self):
        """
        Verifies that hooks are properly cleared after a database transaction rollbacks.

        Ensures that any side effects from a previous failed transaction are discarded, and subsequent transactions start with a clean state.
        """
        try:
            with transaction.atomic():
                self.do(1)
                raise ForcedError()
        except ForcedError:
            pass

        with transaction.atomic():
            self.do(2)

        self.assertDone([2])

    @skipUnlessDBFeature("test_db_allows_multiple_connections")
    def test_hooks_cleared_on_reconnect(self):
        """
        Tests whether hooks are properly cleared after reconnecting to the database.

        Verifies that after reconnecting, only the actions from the new transaction are executed, 
        and any actions from the previous transaction are discarded. This ensures the hooks 
        do not retain state across multiple connections.
        """
        with transaction.atomic():
            self.do(1)
            connection.close()

        connection.connect()

        with transaction.atomic():
            self.do(2)

        self.assertDone([2])

    def test_error_in_hook_doesnt_prevent_clearing_hooks(self):
        """

        Tests that an error in a database hook does not prevent other hooks from being cleared.

        Verifies that when an error occurs in a hook, the hook is still properly removed after the transaction is committed.

        """
        try:
            with transaction.atomic():
                transaction.on_commit(lambda: self.notify("error"))
        except ForcedError:
            pass

        with transaction.atomic():
            self.do(1)

        self.assertDone([1])

    def test_db_query_in_hook(self):
        with transaction.atomic():
            Thing.objects.create(num=1)
            transaction.on_commit(
                lambda: [self.notify(t.num) for t in Thing.objects.all()]
            )

        self.assertDone([1])

    def test_transaction_in_hook(self):
        """

        Tests that a transaction is correctly handled inside a hook.

        Verifies that the on_commit hook is triggered after the transaction is committed,
        and that the expected notification is sent.

        """
        def on_commit():
            with transaction.atomic():
                t = Thing.objects.create(num=1)
                self.notify(t.num)

        with transaction.atomic():
            transaction.on_commit(on_commit)

        self.assertDone([1])

    def test_hook_in_hook(self):
        """
        Tests the functionality of hooking into the commit process, specifically nesting hooks within each other and verifying the correct order of execution and notification of created objects.
        """
        def on_commit(i, add_hook):
            """
            Schedules a series of database transactions to create new Thing objects with incrementing numbers, 
            notifying after each creation, and automatically triggering subsequent transactions after each commit.
            """
            with transaction.atomic():
                if add_hook:
                    transaction.on_commit(lambda: on_commit(i + 10, False))
                t = Thing.objects.create(num=i)
                self.notify(t.num)

        with transaction.atomic():
            transaction.on_commit(lambda: on_commit(1, True))
            transaction.on_commit(lambda: on_commit(2, True))

        self.assertDone([1, 11, 2, 12])

    def test_raises_exception_non_autocommit_mode(self):
        """
        Tests that attempting to use on_commit() when the database connection is in manual transaction management mode raises a TransactionManagementError.
        """
        def should_never_be_called():
            raise AssertionError("this function should never be called")

        try:
            connection.set_autocommit(False)
            msg = "on_commit() cannot be used in manual transaction management"
            with self.assertRaisesMessage(transaction.TransactionManagementError, msg):
                transaction.on_commit(should_never_be_called)
        finally:
            connection.set_autocommit(True)

    def test_raises_exception_non_callable(self):
        msg = "on_commit()'s callback must be a callable."
        with self.assertRaisesMessage(TypeError, msg):
            transaction.on_commit(None)
