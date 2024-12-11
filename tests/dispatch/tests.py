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
        """
        Tests the functionality of sending a signal when there are no receivers.

         Verifies that the signal is sent successfully and the expected result is an empty list, 
         indicating that no receivers were notified.
        """
        result = a_signal.send(sender=self, val="test")
        self.assertEqual(result, [])

    def test_send_connected_no_sender(self):
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
        Tests if a signal's connection to a callable object is properly garbage collected when the object is deleted.

        Verifies that after deleting a callable object connected to a signal and triggering garbage collection, 
        the signal no longer calls the deleted object, ensuring memory safety and preventing unexpected behavior.

        The test scenario involves connecting a callable object to a signal, deleting the object, and then sending the signal. 
        The expected outcome is that the signal does not attempt to call the deleted object, resulting in an empty list of return values.

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

        Tests the registration of multiple receivers to the same signal.

        This test ensures that when a receiver is connected to a signal multiple times,
        it is only triggered once when the signal is sent. Additionally, it verifies
        that the receiver is properly disassociated from the signal after being deleted.

        The test case covers the following scenarios:
        - Connecting a receiver to a signal multiple times
        - Sending the signal and verifying that the receiver is only triggered once
        - Deleting the receiver and verifying that it is properly disassociated from the signal
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
        """
        Tests the send_robust method of a signal when there are no receivers.

        This test case verifies that the send_robust method returns an empty list when 
        there are no receivers attached to the signal, as expected. The test sender 
        sends a test signal with a 'test' value and checks that the result is an empty 
        list, confirming the signal was not received by any handlers.
        """
        result = a_signal.send_robust(sender=self, val="test")
        self.assertEqual(result, [])

    def test_send_robust_ignored_sender(self):
        """

        Tests the send_robust method of a signal by connecting a receiver, sending a signal from a specific sender, and verifying the result.
        The test then disconnects the receiver and ensures the signal is left in a clean state.

        The test covers the scenario where the sender of the signal is intentionally ignored by the receiver, 
        and checks that the receiver still receives the signal's value ('val') as expected.

        """
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

        Checks if a signal currently has any connected listeners.

        This method verifies if there are any receivers attached to the signal, 
        optionally filtering by a specific sender object. It returns True if 
        at least one listener is found, and False otherwise.

        The presence of listeners can change over time as they are connected 
        or disconnected from the signal, and this method reflects the current 
        state of the signal's listener connections.

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

        Tests that a single signal is properly received and handled by a receiver function.

        The receiver function updates the state of the test instance based on the signal value.
        The test sender sends a signal with a value of True and then asserts that the state
        has been updated correctly.

        """
        def f(val, **kwargs):
            self.state = val

        self.state = False
        a_signal.send(sender=self, val=True)
        self.assertTrue(self.state)

    def test_receiver_signal_list(self):
        @receiver([a_signal, b_signal, c_signal])
        """

        Tests the reception of multiple signals by a single receiver function.

        This test case verifies that a receiver function can correctly handle and record 
        values from multiple signals. It checks that the receiver function is triggered 
        for each signal sent, and that the values from these signals are properly stored.

        The test covers the following signals: a_signal, b_signal, and c_signal. 
        It asserts that the values sent by these signals are correctly received and 
        recorded by the receiver function.

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
