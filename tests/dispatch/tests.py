import weakref
from types import TracebackType

from django.dispatch import Signal, receiver
from django.test import SimpleTestCase
from django.test.utils import garbage_collect, override_settings


def receiver_1_arg(val, **kwargs):
    return val


class Callable:
    def __call__(self, val, **kwargs):
        return val

    def a(self, val, **kwargs):
        return val


a_signal = Signal()
b_signal = Signal()
c_signal = Signal()
d_signal = Signal(use_caching=True)


class DispatcherTests(SimpleTestCase):
    def assertTestIsClean(self, signal):
        """Assert that everything has been cleaned up automatically"""
        # Note that dead weakref cleanup happens as side effect of using
        # the signal's receivers through the signals API. So, first do a
        # call to an API method to force cleanup.
        self.assertFalse(signal.has_listeners())
        self.assertEqual(signal.receivers, [])

    @override_settings(DEBUG=True)
    def test_cannot_connect_no_kwargs(self):
        def receiver_no_kwargs(sender):
            pass

        msg = "Signal receivers must accept keyword arguments (**kwargs)."
        with self.assertRaisesMessage(ValueError, msg):
            a_signal.connect(receiver_no_kwargs)
        self.assertTestIsClean(a_signal)

    @override_settings(DEBUG=True)
    def test_cannot_connect_non_callable(self):
        """
        Tests that attempting to connect a non-callable object to a signal results in a TypeError.

        The function verifies that the signal connection mechanism correctly identifies and raises an error when a non-callable object is provided as a receiver.

        Validates that the error message indicates the reason for the failure, which is that signal receivers must be callable. Ensures the test leaves the signal in a clean state after the test execution.

        Parameters: None
        Returns: None
        Raises: TypeError with a message specifying that signal receivers must be callable.
        """
        msg = "Signal receivers must be callable."
        with self.assertRaisesMessage(TypeError, msg):
            a_signal.connect(object())
        self.assertTestIsClean(a_signal)

    def test_send(self):
        a_signal.connect(receiver_1_arg, sender=self)
        result = a_signal.send(sender=self, val="test")
        self.assertEqual(result, [(receiver_1_arg, "test")])
        a_signal.disconnect(receiver_1_arg, sender=self)
        self.assertTestIsClean(a_signal)

    def test_send_no_receivers(self):
        result = a_signal.send(sender=self, val="test")
        self.assertEqual(result, [])

    def test_send_connected_no_sender(self):
        """

        Tests the send functionality of a signal when connected without a sender.

        Verifies that the signal is properly sent to the connected receiver, 
        and that the result is as expected. Also ensures that the signal is 
        correctly disconnected after the test, leaving the test environment clean.

        """
        a_signal.connect(receiver_1_arg)
        result = a_signal.send(sender=self, val="test")
        self.assertEqual(result, [(receiver_1_arg, "test")])
        a_signal.disconnect(receiver_1_arg)
        self.assertTestIsClean(a_signal)

    def test_send_different_no_sender(self):
        a_signal.connect(receiver_1_arg, sender=object)
        result = a_signal.send(sender=self, val="test")
        self.assertEqual(result, [])
        a_signal.disconnect(receiver_1_arg, sender=object)
        self.assertTestIsClean(a_signal)

    def test_garbage_collected(self):
        """
        Tests if a Callable instance's signal handler is properly garbage collected when the instance is deleted.

        Verifies that after deleting the Callable instance and forcing garbage collection, 
        the signal handler is no longer active and does not receive the signal. 

        The test checks the signal's result to ensure it contains no handlers.
        Additionally, it verifies the test's cleanliness by asserting the signal's state.

        """
        a = Callable()
        a_signal.connect(a.a, sender=self)
        del a
        garbage_collect()
        result = a_signal.send(sender=self, val="test")
        self.assertEqual(result, [])
        self.assertTestIsClean(a_signal)

    def test_cached_garbaged_collected(self):
        """
        Make sure signal caching sender receivers don't prevent garbage
        collection of senders.
        """

        class sender:
            pass

        wref = weakref.ref(sender)
        d_signal.connect(receiver_1_arg)
        d_signal.send(sender, val="garbage")
        del sender
        garbage_collect()
        try:
            self.assertIsNone(wref())
        finally:
            # Disconnect after reference check since it flushes the tested cache.
            d_signal.disconnect(receiver_1_arg)

    def test_multiple_registration(self):
        """

        Verify that connecting the same callable multiple times to a signal results in it being called only once.

        This test checks the signal's behavior when a single callable is connected multiple times, and then the signal is sent. It asserts that the callable is only invoked once, and that the signal's internal state is correct after the callable is garbage collected.

        """
        a = Callable()
        a_signal.connect(a)
        a_signal.connect(a)
        a_signal.connect(a)
        a_signal.connect(a)
        a_signal.connect(a)
        a_signal.connect(a)
        result = a_signal.send(sender=self, val="test")
        self.assertEqual(len(result), 1)
        self.assertEqual(len(a_signal.receivers), 1)
        del a
        del result
        garbage_collect()
        self.assertTestIsClean(a_signal)

    def test_uid_registration(self):
        """
        Tests the registration of signal receivers using a unique dispatch UID.

        Verifies that when multiple receivers are connected to the same signal with the same dispatch UID,
        only one receiver is actually registered. Also checks that disconnecting using the dispatch UID
        correctly removes the registered receiver, leaving the signal in a clean state.
        """
        def uid_based_receiver_1(**kwargs):
            pass

        def uid_based_receiver_2(**kwargs):
            pass

        a_signal.connect(uid_based_receiver_1, dispatch_uid="uid")
        a_signal.connect(uid_based_receiver_2, dispatch_uid="uid")
        self.assertEqual(len(a_signal.receivers), 1)
        a_signal.disconnect(dispatch_uid="uid")
        self.assertTestIsClean(a_signal)

    def test_send_robust_success(self):
        a_signal.connect(receiver_1_arg)
        result = a_signal.send_robust(sender=self, val="test")
        self.assertEqual(result, [(receiver_1_arg, "test")])
        a_signal.disconnect(receiver_1_arg)
        self.assertTestIsClean(a_signal)

    def test_send_robust_no_receivers(self):
        result = a_signal.send_robust(sender=self, val="test")
        self.assertEqual(result, [])

    def test_send_robust_ignored_sender(self):
        a_signal.connect(receiver_1_arg)
        result = a_signal.send_robust(sender=self, val="test")
        self.assertEqual(result, [(receiver_1_arg, "test")])
        a_signal.disconnect(receiver_1_arg)
        self.assertTestIsClean(a_signal)

    def test_send_robust_fail(self):
        def fails(val, **kwargs):
            raise ValueError("this")

        a_signal.connect(fails)
        try:
            with self.assertLogs("django.dispatch", "ERROR") as cm:
                result = a_signal.send_robust(sender=self, val="test")
            err = result[0][1]
            self.assertIsInstance(err, ValueError)
            self.assertEqual(err.args, ("this",))
            self.assertIs(hasattr(err, "__traceback__"), True)
            self.assertIsInstance(err.__traceback__, TracebackType)

            log_record = cm.records[0]
            self.assertEqual(
                log_record.getMessage(),
                "Error calling "
                "DispatcherTests.test_send_robust_fail.<locals>.fails in "
                "Signal.send_robust() (this)",
            )
            self.assertIsNotNone(log_record.exc_info)
            _, exc_value, _ = log_record.exc_info
            self.assertIsInstance(exc_value, ValueError)
            self.assertEqual(str(exc_value), "this")
        finally:
            a_signal.disconnect(fails)
        self.assertTestIsClean(a_signal)

    def test_disconnection(self):
        """
        Tests the disconnection of receivers from a signal.

        This test case confirms that disconnecting a receiver from a signal 
        correctly removes the receiver, and that signals are properly cleaned 
        up even when receivers go out of scope and are garbage collected.

        The test covers three scenarios: explicit disconnection, garbage 
        collection of a disconnected receiver, and explicit disconnection 
        of a receiver after other receivers have been disconnected or 
        garbage collected. The test verifies that the signal is left in a 
        clean state after all disconnections and garbage collection are complete.
        """
        receiver_1 = Callable()
        receiver_2 = Callable()
        receiver_3 = Callable()
        a_signal.connect(receiver_1)
        a_signal.connect(receiver_2)
        a_signal.connect(receiver_3)
        a_signal.disconnect(receiver_1)
        del receiver_2
        garbage_collect()
        a_signal.disconnect(receiver_3)
        self.assertTestIsClean(a_signal)

    def test_values_returned_by_disconnection(self):
        """
        Tests the return values of the disconnect method on a signal.

        This test verifies that disconnecting a registered receiver from a signal returns True,
        while disconnecting a non-registered receiver returns False. It also ensures the signal
        remains in a clean state after disconnect operations.

        The test covers the case where a receiver is connected, then disconnected, as well as
        the case where a receiver that was never connected is attempted to be disconnected.
        """
        receiver_1 = Callable()
        receiver_2 = Callable()
        a_signal.connect(receiver_1)
        receiver_1_disconnected = a_signal.disconnect(receiver_1)
        receiver_2_disconnected = a_signal.disconnect(receiver_2)
        self.assertTrue(receiver_1_disconnected)
        self.assertFalse(receiver_2_disconnected)
        self.assertTestIsClean(a_signal)

    def test_has_listeners(self):
        """
        Tests if a signal has any registered listeners.

        This function checks for the presence of listeners connected to a signal,
        both with and without specifying a sender object. It verifies that the
        signal correctly reports the presence or absence of listeners after
        connecting and disconnecting a receiver, ensuring accurate tracking
        of signal listeners.

        Parameters
        ----------
        None

        Returns
        -------
        None

        Raises
        -------

        Notes
        -----
        This test case covers various scenarios to ensure the reliability of
        the signal's listener tracking mechanism, including empty listener
        lists, listener connection, and disconnection. The test uses a
        Callable object as a receiver to simulate a signal listener.

        """
        self.assertFalse(a_signal.has_listeners())
        self.assertFalse(a_signal.has_listeners(sender=object()))
        receiver_1 = Callable()
        a_signal.connect(receiver_1)
        self.assertTrue(a_signal.has_listeners())
        self.assertTrue(a_signal.has_listeners(sender=object()))
        a_signal.disconnect(receiver_1)
        self.assertFalse(a_signal.has_listeners())
        self.assertFalse(a_signal.has_listeners(sender=object()))


class ReceiverTestCase(SimpleTestCase):
    def test_receiver_single_signal(self):
        @receiver(a_signal)
        """
        Tests the reception of a single signal by a receiver function.

        This test case verifies that a signal is correctly received and processed by a registered receiver function, 
        updating the state accordingly. The test sender dispatches a signal with a value, and the receiver function 
        modifies the test object's state based on this received value. The test asserts that the state is updated 
        as expected after the signal is sent.

        Parameters
        ----------
        None

        Returns
        -------
        None

        Notes
        -----
        The test checks the correct registration and execution of the receiver function for a specific signal type.
        """
        def f(val, **kwargs):
            self.state = val

        self.state = False
        a_signal.send(sender=self, val=True)
        self.assertTrue(self.state)

    def test_receiver_signal_list(self):
        @receiver([a_signal, b_signal, c_signal])
        def f(val, **kwargs):
            self.state.append(val)

        self.state = []
        a_signal.send(sender=self, val="a")
        c_signal.send(sender=self, val="c")
        b_signal.send(sender=self, val="b")
        self.assertIn("a", self.state)
        self.assertIn("b", self.state)
        self.assertIn("c", self.state)
