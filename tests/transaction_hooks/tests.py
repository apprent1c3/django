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
        """
        Notifies the system of an event or status identified by the given ID.

        Args:
            id_ (str): The identifier of the event or status to notify about.

        Raises:
            ForcedError: If the provided ID is 'error', indicating a forced error condition.

        Notes:
            The notified event or status ID is recorded for later reference.

        """
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
        """
        Tests that the function executes immediately if no transaction is present.

        Verifies that when no transaction is in progress, the function will execute and
        complete without delay, resulting in the expected outcome being observed.

        The test checks for immediate execution by performing a single operation and then
        asserting that the operation has been successfully completed, as evidenced by the
        presence of the operation result in the completion list.
        """
        self.do(1)
        self.assertDone([1])

    def test_robust_if_no_transaction(self):
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

        Tests the behavior of a robust transaction when an on-commit callback raises an exception.

        The test verifies that the transaction is still committed successfully, even if an on-commit
        callback fails with an exception. It also checks that the exception is properly logged and
        its message is as expected. The log record is inspected to ensure it contains the correct
        exception information, including the exception instance and its message.

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
        Tests that no execution occurs when a transaction is rolled back.

        This test case verifies that the function being tested does not execute if the transaction is rolled back due to an error.
        It simulates a scenario where an exception is raised within a transaction, causing it to be rolled back, and checks that no side effects occur.
        The test confirms that the system behaves as expected in the event of a transaction failure, ensuring data consistency and preventing partial execution of operations.
        """
        try:
            with transaction.atomic():
                self.do(1)
                raise ForcedError()
        except ForcedError:
            pass

        self.assertDone([])

    def test_executes_only_after_final_transaction_committed(self):
        with transaction.atomic():
            with transaction.atomic():
                self.do(1)
                self.assertNotified([])
            self.assertNotified([])
        self.assertDone([1])

    def test_discards_hooks_from_rolled_back_savepoint(self):
        """

        Tests that hooks are properly discarded after a savepoint is rolled back.

        This test case simulates a scenario where a series of operations are attempted,
        with a midpoint failure that triggers a rollback. It verifies that any hooks
        registered during the failed operation are subsequently discarded, and only
        the successfully completed operations are retained.

        The test case confirms that the system correctly handles nested transactions
        and ensures data consistency by only committing changes that were successfully
        executed.

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
        Tests the behavior of nested database transactions when an inner savepoint is rolled back due to an exception, while the outer transaction remains active.

         The test verifies that changes made within the inner transaction are properly rolled back, while changes made after the exception is caught are committed.

         This ensures that database consistency is maintained even when errors occur within nested transactions, and that the expected outcome is achieved.
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

        Test that no savepoints are created when an inner atomic transaction is merged with an outer one.

        This test case verifies the behavior of nested atomic transactions. It checks that when an inner transaction is merged with an outer one (i.e., no savepoint is created), the expected outcome is achieved.

        The test simulates a scenario where an operation is performed within a nested transaction. A forced error is then raised within the inner transaction, which is caught and ignored. Finally, the test asserts that no operations are recorded, confirming that the outer transaction's atomicity is preserved.

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
        Tests if registered hooks are executed in the correct order.

        This test case simulates a sequence of actions within database transactions 
        and verifies that the corresponding hooks are triggered in the order they were registered.

        The test covers nested transactions, ensuring that hooks are run consistently 
        even when transactions are nested. The expected outcome is that all hooks are 
        executed in the order they were triggered, resulting in a specific sequence of actions.

        The test confirms that the system can correctly manage the order of hook execution, 
        even in complex scenarios involving transaction nesting.
        """
        with transaction.atomic():
            self.do(1)
            with transaction.atomic():
                self.do(2)
            self.do(3)

        self.assertDone([1, 2, 3])

    def test_hooks_cleared_after_successful_commit(self):
        """
        Tests that hooks are properly cleared after a successful commit operation.

        This test case verifies that hooks are reset after each atomic transaction, 
        ensuring that the state is properly cleaned up after a successful commit. 

        It performs two separate atomic transactions, executing the 'do' operation 
        with different parameters, and then asserts that both operations were successfully 
        completed. 

        The purpose of this test is to guarantee the reliability and consistency of 
        the transactional behavior, particularly in regards to hook management.
        """
        with transaction.atomic():
            self.do(1)
        with transaction.atomic():
            self.do(2)

        self.assertDone([1, 2])  # not [1, 1, 2]

    def test_hooks_cleared_after_rollback(self):
        """
        Tests that hooks are properly cleared after a rollback occurs.

        Verifies that when an error is raised within a transaction, causing it to roll back,
        any side effects from that transaction are fully reversed and do not interfere
        with subsequent transactions. In this case, it checks that only the second
        operation is successfully executed and reflected in the final state.

        The test simulates an error in the first transaction, rolls it back, and then
        executes a second transaction to ensure that the hooks from the first transaction
        do not affect the outcome of the second transaction.
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
        Test that hooks are properly cleaned up when reconnecting to the database.

        This test case verifies that any hooks set up during a previous database connection
        are cleared after the connection is closed and a new connection is established.
        It ensures that the hooks do not interfere with subsequent database operations.

        The test connects to the database, performs an action, closes the connection, 
        reconnects, and then performs another action to verify that the correct outcome 
        occurs without any residual effects from the previous connection. 

        The expected result is that only the hooks from the second action are executed, 
        demonstrating that the hooks from the first action were successfully cleared 
        upon reconnecting to the database.
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
        Verifies that an error occurring in a transaction hook does not prevent the hooks from being properly cleared.

        This test ensures that even if an exception is raised within a transaction hook, the hooks are still removed after the transaction is committed, allowing for subsequent transactions to proceed without interference from previous hook errors.

        The test checks for this behavior by intentionally triggering an error in a hook, then verifying that a subsequent transaction completes successfully and that the expected work is done, as indicated by the correct done status of the transaction.

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
        """
        Tests that a query executed within a database hook produces the expected results.

        This test ensures that when a query is executed within a hook (in this case, after a transaction commit), 
        it returns the correct data. Specifically, it verifies that after creating a new object and notifying 
        on commit, the expected notifications are received.

        Args: None

        Returns: None

        Asserts: The test checks that the expected notifications are received after the transaction is committed.

        """
        with transaction.atomic():
            Thing.objects.create(num=1)
            transaction.on_commit(
                lambda: [self.notify(t.num) for t in Thing.objects.all()]
            )

        self.assertDone([1])

    def test_transaction_in_hook(self):
        """

        Tests the transaction_in_hook functionality by creating a new Thing object 
        with a specific number and verifying that a notification is sent after the 
        transaction is committed.

        The test uses a hook function, on_commit, which is triggered when the 
        transaction is successfully committed. This hook creates a new Thing object 
        and notifies the result. The test then asserts that the notification was 
        sent as expected, ensuring that the transaction_in_hook functions correctly.

        """
        def on_commit():
            """

            Trigger an action after a successful database commit.

            This function creates a new instance of the Thing model with a specific attribute value,
            and then notifies a listener with the newly created value.

            The operation is executed within a database transaction to ensure atomicity.

            """
            with transaction.atomic():
                t = Thing.objects.create(num=1)
                self.notify(t.num)

        with transaction.atomic():
            transaction.on_commit(on_commit)

        self.assertDone([1])

    def test_hook_in_hook(self):
        def on_commit(i, add_hook):
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
        """
        Tests that on_commit raises a TypeError when the provided callback is not callable.

        Verifies that attempting to pass a non-callable object to transaction.on_commit results in the correct exception being raised with a descriptive error message.

        Parameters
        ----------
        None

        Raises
        ------
        TypeError
            If the callback is not callable.

        Returns
        -------
        None

        Note
        ----
        This test ensures that the on_commit function enforces the requirement that its callback must be a callable, preventing potential runtime errors due to invalid inputs.
        """
        msg = "on_commit()'s callback must be a callable."
        with self.assertRaisesMessage(TypeError, msg):
            transaction.on_commit(None)
