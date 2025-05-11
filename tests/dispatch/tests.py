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
        """
        Tests that connecting a signal receiver without keyword arguments (**kwargs) raises a ValueError.
        """
        def receiver_no_kwargs(sender):
            pass

        msg = "Signal receivers must accept keyword arguments (**kwargs)."
        with self.assertRaisesMessage(ValueError, msg):
            a_signal.connect(receiver_no_kwargs)
        self.assertTestIsClean(a_signal)

    @override_settings(DEBUG=True)
    def test_cannot_connect_non_callable(self):
        msg = "Signal receivers must be callable."
        with self.assertRaisesMessage(TypeError, msg):
            a_signal.connect(object())
        self.assertTestIsClean(a_signal)

    def test_send(self):
        """
        Tests the sending of a signal, ensuring it is properly connected, sent, and then disconnected, with the expected result being returned and the signal state returning to clean after disconnection.
        """
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
        Tests the signal sending mechanism when the sender is connected but not specified in the receiver function.

         Verifies that the signal is sent correctly and that the receiver function is called with the expected argument.

         Also checks that the signal is properly disconnected after testing and the test environment is left in a clean state.
        """
        a_signal.connect(receiver_1_arg)
        result = a_signal.send(sender=self, val="test")
        self.assertEqual(result, [(receiver_1_arg, "test")])
        a_signal.disconnect(receiver_1_arg)
        self.assertTestIsClean(a_signal)

    def test_send_different_no_sender(self):
        """

        Tests the handling of a signal sender that differs from the one specified during connection.

        Verifies that a signal sent with a different sender than the one expected by the receiver
        results in no invocation of the receiver and a clean signal state after disconnection.

        """
        a_signal.connect(receiver_1_arg, sender=object)
        result = a_signal.send(sender=self, val="test")
        self.assertEqual(result, [])
        a_signal.disconnect(receiver_1_arg, sender=object)
        self.assertTestIsClean(a_signal)

    def test_garbage_collected(self):
        """
        Tests if a signal's receiver is properly garbage collected when the receiver object is deleted.
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
        Tests that a signal only maintains a single reference to a receiver, even if it is registered multiple times, and that the reference is properly removed when the receiver is deleted.
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

        Tests the registration of receivers with unique dispatch_uids.
        Verifies that multiple receivers with the same dispatch_uid are treated as a single receiver,
        and that disconnecting by dispatch_uid correctly removes the associated receiver.

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
        """
        Tests the successful sending of a signal with a single receiver using the send_robust method.
        """
        a_signal.connect(receiver_1_arg)
        result = a_signal.send_robust(sender=self, val="test")
        self.assertEqual(result, [(receiver_1_arg, "test")])
        a_signal.disconnect(receiver_1_arg)
        self.assertTestIsClean(a_signal)

    def test_send_robust_no_receivers(self):
        result = a_signal.send_robust(sender=self, val="test")
        self.assertEqual(result, [])

    def test_send_robust_ignored_sender(self):
        """

        Tests that the send_robust method handles signal sending correctly, 
        including handling the specified sender and returning expected results.

        """
        a_signal.connect(receiver_1_arg)
        result = a_signal.send_robust(sender=self, val="test")
        self.assertEqual(result, [(receiver_1_arg, "test")])
        a_signal.disconnect(receiver_1_arg)
        self.assertTestIsClean(a_signal)

    def test_send_robust_fail(self):
        """
        Tests the robust signal sending functionality to ensure it handles and logs exceptions correctly when a connected receiver raises an error.
        """
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
        Tests the disconnection of signal receivers, verifying that receivers are properly removed and garbage collected, ensuring the signal is left in a clean state.
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
        Tests the return values of the disconnect method, verifying that it correctly indicates whether a receiver was disconnected or not.
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
        Tests the functionality of the has_listeners method on a signal.

        Verifies that the method correctly reports the presence or absence of connected listeners,
        both with and without a specified sender object.
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
        Tests that a single signal is received and processed correctly, updating the receiver's state accordingly.
        """
        def f(val, **kwargs):
            self.state = val

        self.state = False
        a_signal.send(sender=self, val=True)
        self.assertTrue(self.state)

    def test_receiver_signal_list(self):
        @receiver([a_signal, b_signal, c_signal])
        """
        Tests that the receiver function correctly handles a list of signals.

        This test case verifies that the function is triggered by each signal in the list 
        and that it appends the received signal values to the state list in the order they 
        are received.
        """
        def f(val, **kwargs):
            self.state.append(val)

        self.state = []
        a_signal.send(sender=self, val="a")
        c_signal.send(sender=self, val="c")
        b_signal.send(sender=self, val="b")
        self.assertIn("a", self.state)
        self.assertIn("b", self.state)
        self.assertIn("c", self.state)
