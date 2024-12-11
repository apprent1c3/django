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
        """

        Verifies that all Things have been processed and their numbers match the expected values.

        Args:
            nums (list): A list of numbers representing the expected values of Thing instances.

        This assertion checks two conditions:
        1. That all Things have been properly notified.
        2. That the numbers of all Things in the database match the provided list of numbers.
        The numbers are compared after sorting to ensure the comparison is order-independent.

        """
        self.assertNotified(nums)
        self.assertEqual(sorted(t.num for t in Thing.objects.all()), sorted(nums))

    def assertNotified(self, nums):
        self.assertEqual(self.notified, nums)

    def test_executes_immediately_if_no_transaction(self):
        self.do(1)
        self.assertDone([1])

    def test_robust_if_no_transaction(self):
        """
        Tests that a robust callback in the on_commit queue is handled correctly when there is no active transaction.

        This function verifies that an exception raised in a robust callback is properly logged and handled, even if no transaction is currently active. The test checks for the correct log message, exception type, and exception message to ensure robust behavior in the absence of a transaction.

        The test case covers the following scenarios:
        - The callback raises an exception when executed.
        - The exception is logged with the correct message and error level.
        - The logged exception matches the type and message of the raised exception.
        - The test's operations are properly executed and recorded despite the exception in the callback.

        By verifying the behavior of robust callbacks without an active transaction, this test ensures that the application remains stable and handles unexpected errors correctly in various scenarios.
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
        """
        Tests that the execution of a task is delayed until after a transaction is committed.

        This test case verifies that tasks are not executed until the enclosing transaction has been successfully committed.
        It checks that no tasks are executed while the transaction is still active, and that they are executed after the transaction is committed.

        The test scenario involves performing an action within a transaction, verifying that no notifications are sent during the transaction,
        and then checking that the expected task is executed after the transaction is committed.
        """
        with transaction.atomic():
            self.do(1)
            self.assertNotified([])
        self.assertDone([1])

    def test_does_not_execute_if_transaction_rolled_back(self):
        """

        Tests that an action is not executed when a transaction is rolled back.

        This test case simulates a scenario where an action is attempted within a transaction,
        but the transaction is subsequently rolled back due to an error. It verifies that
        the action is not actually executed in this case, ensuring that the system maintains
        a consistent state even in the presence of failures.

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

        Tests if an inner savepoint is properly rolled back when an exception occurs, 
        while the outer transaction remains intact.

        Verifies that when an exception is raised within a nested transaction, 
        the effects of the inner transaction are rolled back, and the outer transaction 
        continues normally, allowing further operations to succeed.

        In this scenario, the inner operation is rolled back due to the raised exception, 
        and only the outer operation is committed.

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

        Tests that no savepoints are created when an inner atomic block is merged with its outer atomic block.

        This test case simulates a scenario where an inner atomic block is used within an outer atomic block, 
        and an exception is raised within the inner block. It verifies that no savepoints are created in this 
        scenario, resulting in no partial changes being committed to the database.

        The test asserts that no operations are recorded after the outer atomic block is completed.

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
        Checks if hooks are executed in the correct order they were registered. The function verifies that the execution of the hooks respects the sequence of operations, even when nested transactions are involved. It ensures the hooks are run in a linear and predictable manner, maintaining the integrity of the system under test.
        """
        with transaction.atomic():
            self.do(1)
            with transaction.atomic():
                self.do(2)
            self.do(3)

        self.assertDone([1, 2, 3])

    def test_hooks_cleared_after_successful_commit(self):
        """
        Verifies that hooks are properly cleared after a successful commit operation.

        This test case ensures that the system correctly resets and cleans up any temporary hooks 
        or modifications made during a transaction, allowing for subsequent operations to proceed 
        without interference from previous transactions.

        It validates the behavior by performing two separate transactions, each with a distinct 
        input, and then asserts that both transactions were successfully processed and their results 
        are correctly reflected in the system's state.
        """
        with transaction.atomic():
            self.do(1)
        with transaction.atomic():
            self.do(2)

        self.assertDone([1, 2])  # not [1, 1, 2]

    def test_hooks_cleared_after_rollback(self):
        """
        Tests that hooks are properly cleared after a transaction rollback.

        This test case verifies that any hooks set up during a transaction are
        removed when the transaction is rolled back due to an exception. It
        ensures that subsequent transactions start with a clean slate and are
        not affected by previously set hooks.

        It checks the hooks are cleared correctly by performing two separate
        transactions: the first one sets up a hook and raises an exception to
        trigger a rollback, and the second one sets up a new hook and checks
        that only the new hook is executed.
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

        Tests thathooks are properly cleared after reconnecting to the database.

        This test case verifies the behavior of the system when the database connection
        is closed and reopened. It checks that any existing hooks are cleared after
        reconnection, ensuring that only the most recent operations are processed.

        The test covers a scenario where a connection is established, an operation is
        performed, the connection is closed, and then reopened. After reconnection, the
        test performs another operation and verifies that the system only processes the
        latest operation.

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

        Tests that an error occurring in a hook does not prevent subsequent hooks from being cleared.

        This test ensures that even if an error is triggered during the execution of a hook,
        it does not interfere with the ability to clear hooks for future transactions.

        It verifies that after an error occurs in a hook, a new transaction can still be executed successfully,
        and that the expected outcome is achieved.

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
        def on_commit():
            with transaction.atomic():
                t = Thing.objects.create(num=1)
                self.notify(t.num)

        with transaction.atomic():
            transaction.on_commit(on_commit)

        self.assertDone([1])

    def test_hook_in_hook(self):
        def on_commit(i, add_hook):
            """

            Trigger an on-commit operation to create a new Thing instance and notify with its number.

            The function takes two parameters:
                i (int): The number to be associated with the Thing instance.
                add_hook (bool): A flag to indicate whether to add a hook to trigger the function recursively on commit.

            On execution, the function creates a new Thing instance with the provided number, and notifies with the number.
            If the add_hook flag is set to True, it also schedules the function to be triggered again on commit, with an incremented number, allowing for recursive operation.

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
        Tests that calling on_commit with a non-callable argument raises a TypeError exception with a specific error message, ensuring that the callback provided must be a function or other callable object.
        """
        msg = "on_commit()'s callback must be a callable."
        with self.assertRaisesMessage(TypeError, msg):
            transaction.on_commit(None)
