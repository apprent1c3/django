from unittest import mock

from asgiref.sync import markcoroutinefunction

from django import dispatch
from django.apps.registry import Apps
from django.db import models
from django.db.models import signals
from django.dispatch import receiver
from django.test import SimpleTestCase, TestCase
from django.test.utils import isolate_apps

from .models import Author, Book, Car, Page, Person


class BaseSignalSetup:
    def setUp(self):
        # Save up the number of connected signals so that we can check at the
        # end that all the signals we register get properly unregistered (#9989)
        self.pre_signals = (
            len(signals.pre_save.receivers),
            len(signals.post_save.receivers),
            len(signals.pre_delete.receivers),
            len(signals.post_delete.receivers),
        )

    def tearDown(self):
        # All our signals got disconnected properly.
        post_signals = (
            len(signals.pre_save.receivers),
            len(signals.post_save.receivers),
            len(signals.pre_delete.receivers),
            len(signals.post_delete.receivers),
        )
        self.assertEqual(self.pre_signals, post_signals)


class SignalTests(BaseSignalSetup, TestCase):
    def test_model_pre_init_and_post_init(self):
        data = []

        def pre_init_callback(sender, args, **kwargs):
            data.append(kwargs["kwargs"])

        signals.pre_init.connect(pre_init_callback)

        def post_init_callback(sender, instance, **kwargs):
            data.append(instance)

        signals.post_init.connect(post_init_callback)

        p1 = Person(first_name="John", last_name="Doe")
        self.assertEqual(data, [{}, p1])

    def test_save_signals(self):
        data = []

        def pre_save_handler(signal, sender, instance, **kwargs):
            data.append((instance, sender, kwargs.get("raw", False)))

        def post_save_handler(signal, sender, instance, **kwargs):
            data.append(
                (instance, sender, kwargs.get("created"), kwargs.get("raw", False))
            )

        signals.pre_save.connect(pre_save_handler, weak=False)
        signals.post_save.connect(post_save_handler, weak=False)
        try:
            p1 = Person.objects.create(first_name="John", last_name="Smith")

            self.assertEqual(
                data,
                [
                    (p1, Person, False),
                    (p1, Person, True, False),
                ],
            )
            data[:] = []

            p1.first_name = "Tom"
            p1.save()
            self.assertEqual(
                data,
                [
                    (p1, Person, False),
                    (p1, Person, False, False),
                ],
            )
            data[:] = []

            # Calling an internal method purely so that we can trigger a "raw" save.
            p1.save_base(raw=True)
            self.assertEqual(
                data,
                [
                    (p1, Person, True),
                    (p1, Person, False, True),
                ],
            )
            data[:] = []

            p2 = Person(first_name="James", last_name="Jones")
            p2.id = 99999
            p2.save()
            self.assertEqual(
                data,
                [
                    (p2, Person, False),
                    (p2, Person, True, False),
                ],
            )
            data[:] = []
            p2.id = 99998
            p2.save()
            self.assertEqual(
                data,
                [
                    (p2, Person, False),
                    (p2, Person, True, False),
                ],
            )

            # The sender should stay the same when using defer().
            data[:] = []
            p3 = Person.objects.defer("first_name").get(pk=p1.pk)
            p3.last_name = "Reese"
            p3.save()
            self.assertEqual(
                data,
                [
                    (p3, Person, False),
                    (p3, Person, False, False),
                ],
            )
        finally:
            signals.pre_save.disconnect(pre_save_handler)
            signals.post_save.disconnect(post_save_handler)

    def test_delete_signals(self):
        """

        Test the functionality of deleting signals.

        This test case verifies that the pre_delete and post_delete signals are triggered 
        correctly when an object is deleted. It checks the signal handlers for both 
        database-backed objects (i.e., those with a valid id) and non-database-backed 
        objects (i.e., those without a valid id).

        The test covers the following scenarios:

        - Deleting a database-backed object
        - Deleting a non-database-backed object
        - Verifying the signal handlers are called with the correct parameters
        - Ensuring the object is removed from the database after deletion

        The test validates that the signal handlers are called with the correct 
        parameters, including the instance being deleted, the sender of the signal, 
        and the origin of the deletion.

        """
        data = []

        def pre_delete_handler(signal, sender, instance, origin, **kwargs):
            data.append((instance, sender, instance.id is None, origin))

        # #8285: signals can be any callable
        class PostDeleteHandler:
            def __init__(self, data):
                self.data = data

            def __call__(self, signal, sender, instance, origin, **kwargs):
                self.data.append((instance, sender, instance.id is None, origin))

        post_delete_handler = PostDeleteHandler(data)

        signals.pre_delete.connect(pre_delete_handler, weak=False)
        signals.post_delete.connect(post_delete_handler, weak=False)
        try:
            p1 = Person.objects.create(first_name="John", last_name="Smith")
            p1.delete()
            self.assertEqual(
                data,
                [
                    (p1, Person, False, p1),
                    (p1, Person, False, p1),
                ],
            )
            data[:] = []

            p2 = Person(first_name="James", last_name="Jones")
            p2.id = 99999
            p2.save()
            p2.id = 99998
            p2.save()
            p2.delete()
            self.assertEqual(
                data,
                [
                    (p2, Person, False, p2),
                    (p2, Person, False, p2),
                ],
            )
            data[:] = []

            self.assertQuerySetEqual(
                Person.objects.all(),
                [
                    "James Jones",
                ],
                str,
            )
        finally:
            signals.pre_delete.disconnect(pre_delete_handler)
            signals.post_delete.disconnect(post_delete_handler)

    def test_delete_signals_origin_model(self):
        """

        Tests that the origin model is correctly passed to the pre and post delete signal handlers.

        The test creates instances of Person and Book models, and connects to the pre and post delete signals.
        It then deletes the person and book instances, and verifies that the signal handlers are called with the correct sender and origin objects.

        The test checks that the origin model is correctly propagated to the signal handlers when deleting instances of the model, 
        ensuring that the handlers are able to identify the origin of the deletion signal.

        """
        data = []

        def pre_delete_handler(signal, sender, instance, origin, **kwargs):
            data.append((sender, origin))

        def post_delete_handler(signal, sender, instance, origin, **kwargs):
            data.append((sender, origin))

        person = Person.objects.create(first_name="John", last_name="Smith")
        book = Book.objects.create(name="Rayuela")
        Page.objects.create(text="Page 1", book=book)
        Page.objects.create(text="Page 2", book=book)

        signals.pre_delete.connect(pre_delete_handler, weak=False)
        signals.post_delete.connect(post_delete_handler, weak=False)
        try:
            # Instance deletion.
            person.delete()
            self.assertEqual(data, [(Person, person), (Person, person)])
            data[:] = []
            # Cascade deletion.
            book.delete()
            self.assertEqual(
                data,
                [
                    (Page, book),
                    (Page, book),
                    (Book, book),
                    (Page, book),
                    (Page, book),
                    (Book, book),
                ],
            )
        finally:
            signals.pre_delete.disconnect(pre_delete_handler)
            signals.post_delete.disconnect(post_delete_handler)

    def test_delete_signals_origin_queryset(self):
        data = []

        def pre_delete_handler(signal, sender, instance, origin, **kwargs):
            data.append((sender, origin))

        def post_delete_handler(signal, sender, instance, origin, **kwargs):
            data.append((sender, origin))

        Person.objects.create(first_name="John", last_name="Smith")
        book = Book.objects.create(name="Rayuela")
        Page.objects.create(text="Page 1", book=book)
        Page.objects.create(text="Page 2", book=book)

        signals.pre_delete.connect(pre_delete_handler, weak=False)
        signals.post_delete.connect(post_delete_handler, weak=False)
        try:
            # Queryset deletion.
            qs = Person.objects.all()
            qs.delete()
            self.assertEqual(data, [(Person, qs), (Person, qs)])
            data[:] = []
            # Cascade deletion.
            qs = Book.objects.all()
            qs.delete()
            self.assertEqual(
                data,
                [
                    (Page, qs),
                    (Page, qs),
                    (Book, qs),
                    (Page, qs),
                    (Page, qs),
                    (Book, qs),
                ],
            )
        finally:
            signals.pre_delete.disconnect(pre_delete_handler)
            signals.post_delete.disconnect(post_delete_handler)

    def test_decorators(self):
        """
        Tests the behavior of decorators in the context of signal registration.

        This function verifies that signal handlers are properly registered and
        executed when decorated with the receiver decorator. It specifically checks
        that handlers with and without the sender argument are correctly triggered
        and that instances are appended to the data list as expected.

        The test case covers the pre-save signal and ensures that the handlers are
        connected and disconnected correctly to prevent interference with other tests.

        """
        data = []

        @receiver(signals.pre_save, weak=False)
        def decorated_handler(signal, sender, instance, **kwargs):
            data.append(instance)

        @receiver(signals.pre_save, sender=Car, weak=False)
        def decorated_handler_with_sender_arg(signal, sender, instance, **kwargs):
            data.append(instance)

        try:
            c1 = Car.objects.create(make="Volkswagen", model="Passat")
            self.assertEqual(data, [c1, c1])
        finally:
            signals.pre_save.disconnect(decorated_handler)
            signals.pre_save.disconnect(decorated_handler_with_sender_arg, sender=Car)

    def test_save_and_delete_signals_with_m2m(self):
        data = []

        def pre_save_handler(signal, sender, instance, **kwargs):
            """

            Handles the pre-save signal by appending relevant information to the data list.

            This function is triggered before an instance is saved, allowing for additional
            processing or logging to occur. It captures the instance being saved and
            appends a corresponding message to the data list. If the save operation is
            marked as 'raw', an additional message is appended to indicate this.

            """
            data.append("pre_save signal, %s" % instance)
            if kwargs.get("raw"):
                data.append("Is raw")

        def post_save_handler(signal, sender, instance, **kwargs):
            """

            Handles post save events, tracking the instance and event details.

            This function is triggered after an instance has been saved, and it logs the event
            including whether the instance was created or updated. It also checks if the save
            was performed in raw mode.

            The handler appends information to the data list for further analysis or logging,
            providing insight into the save operations that have occurred.

            :param signal: The signal that triggered this handler
            :param sender: The model class that sent the signal
            :param instance: The instance that was saved
            :param **kwargs: Additional keyword arguments including 'created' and 'raw'

            """
            data.append("post_save signal, %s" % instance)
            if "created" in kwargs:
                if kwargs["created"]:
                    data.append("Is created")
                else:
                    data.append("Is updated")
            if kwargs.get("raw"):
                data.append("Is raw")

        def pre_delete_handler(signal, sender, instance, **kwargs):
            data.append("pre_delete signal, %s" % instance)
            data.append("instance.id is not None: %s" % (instance.id is not None))

        def post_delete_handler(signal, sender, instance, **kwargs):
            """
            Handles the post delete signal, appending a notification and the instance's id existence status to the data list.

            This handler captures the post delete event, records the instance that triggered the signal, and logs whether the instance's id is still present after deletion. The recorded data can be used for auditing, logging, or further processing as needed.

            Args:
                signal: The signal that triggered this handler.
                sender: The model class that sent the signal.
                instance: The instance of the model that was deleted.
                **kwargs: Additional keyword arguments passed to the handler.

            Notes:
                The data list is assumed to be accessible and modifiable within the context of this handler. The handler does not perform any error checking or handling for the data list or the instance's id.

            """
            data.append("post_delete signal, %s" % instance)
            data.append("instance.id is not None: %s" % (instance.id is not None))

        signals.pre_save.connect(pre_save_handler, weak=False)
        signals.post_save.connect(post_save_handler, weak=False)
        signals.pre_delete.connect(pre_delete_handler, weak=False)
        signals.post_delete.connect(post_delete_handler, weak=False)
        try:
            a1 = Author.objects.create(name="Neal Stephenson")
            self.assertEqual(
                data,
                [
                    "pre_save signal, Neal Stephenson",
                    "post_save signal, Neal Stephenson",
                    "Is created",
                ],
            )
            data[:] = []

            b1 = Book.objects.create(name="Snow Crash")
            self.assertEqual(
                data,
                [
                    "pre_save signal, Snow Crash",
                    "post_save signal, Snow Crash",
                    "Is created",
                ],
            )
            data[:] = []

            # Assigning and removing to/from m2m shouldn't generate an m2m signal.
            b1.authors.set([a1])
            self.assertEqual(data, [])
            b1.authors.set([])
            self.assertEqual(data, [])
        finally:
            signals.pre_save.disconnect(pre_save_handler)
            signals.post_save.disconnect(post_save_handler)
            signals.pre_delete.disconnect(pre_delete_handler)
            signals.post_delete.disconnect(post_delete_handler)

    def test_disconnect_in_dispatch(self):
        """
        Signals that disconnect when being called don't mess future
        dispatching.
        """

        class Handler:
            def __init__(self, param):
                self.param = param
                self._run = False

            def __call__(self, signal, sender, **kwargs):
                self._run = True
                signal.disconnect(receiver=self, sender=sender)

        a, b = Handler(1), Handler(2)
        signals.post_save.connect(a, sender=Person, weak=False)
        signals.post_save.connect(b, sender=Person, weak=False)
        Person.objects.create(first_name="John", last_name="Smith")

        self.assertTrue(a._run)
        self.assertTrue(b._run)
        self.assertEqual(signals.post_save.receivers, [])

    @mock.patch("weakref.ref")
    def test_lazy_model_signal(self, ref):
        """

        Tests the behavior of connecting and disconnecting signals in lazy models.

        This test case verifies that when a callback is connected to a signal with the
        default weak reference behavior, the weak reference is called when the callback
        is disconnected. Additionally, it checks that when the callback is connected with
        weak=False, the weak reference is not called upon disconnection.

        The test covers two scenarios:
        - Connecting and disconnecting a signal with the default weak reference behavior.
        - Connecting and disconnecting a signal with weak reference behavior disabled.

        """
        def callback(sender, args, **kwargs):
            pass

        signals.pre_init.connect(callback)
        signals.pre_init.disconnect(callback)
        self.assertTrue(ref.called)
        ref.reset_mock()

        signals.pre_init.connect(callback, weak=False)
        signals.pre_init.disconnect(callback)
        ref.assert_not_called()

    @isolate_apps("signals", kwarg_name="apps")
    def test_disconnect_model(self, apps):
        """

        Tests the disconnect functionality of a model signal receiver.

        This test case verifies that a receiver is properly disconnected from a model signal,
        and that no signal is sent to the receiver after disconnection. It also checks that
        attempting to disconnect a receiver that has already been disconnected returns False.

        The test creates a model, connects a receiver to its post_init signal, then disconnects
        the receiver and checks that the signal is no longer received.

        """
        received = []

        def receiver(**kwargs):
            received.append(kwargs)

        class Created(models.Model):
            pass

        signals.post_init.connect(receiver, sender=Created, apps=apps)
        try:
            self.assertIs(
                signals.post_init.disconnect(receiver, sender=Created, apps=apps),
                True,
            )
            self.assertIs(
                signals.post_init.disconnect(receiver, sender=Created, apps=apps),
                False,
            )
            Created()
            self.assertEqual(received, [])
        finally:
            signals.post_init.disconnect(receiver, sender=Created)


class LazyModelRefTests(BaseSignalSetup, SimpleTestCase):
    def setUp(self):
        """

        Set up the test environment.

        This method initializes the test setup by calling the parent class's setUp method and 
        then initializes an empty list 'received' to store data received during the test.

        """
        super().setUp()
        self.received = []

    def receiver(self, **kwargs):
        self.received.append(kwargs)

    def test_invalid_sender_model_name(self):
        """
        Tests that an invalid sender model name raises a ValueError when attempting to connect a signal receiver.

        The function checks that connecting a receiver to a signal with an incorrectly formatted sender model name (i.e., not in the form 'app_label.ModelName') results in a ValueError with a descriptive error message.

        :raises: ValueError if the sender model name is not in the correct format
        """
        msg = (
            "Invalid model reference 'invalid'. String model references must be of the "
            "form 'app_label.ModelName'."
        )
        with self.assertRaisesMessage(ValueError, msg):
            signals.post_init.connect(self.receiver, sender="invalid")

    def test_already_loaded_model(self):
        signals.post_init.connect(self.receiver, sender="signals.Book", weak=False)
        try:
            instance = Book()
            self.assertEqual(
                self.received,
                [{"signal": signals.post_init, "sender": Book, "instance": instance}],
            )
        finally:
            signals.post_init.disconnect(self.receiver, sender=Book)

    @isolate_apps("signals", kwarg_name="apps")
    def test_not_loaded_model(self, apps):
        """
        Tests the post_init signal for the case when the model is not loaded, ensuring that the signal is properly connected and received.

        Parameters
        ----------
        apps : application registry
            The list of applications to be used in the test.

        Notes
        -----
        The test creates a model instance, connects the post_init signal, and verifies that the signal is received as expected.

        Raises
        ------
        AssertionError
            If the post_init signal is not received correctly.
        """
        signals.post_init.connect(
            self.receiver, sender="signals.Created", weak=False, apps=apps
        )

        try:

            class Created(models.Model):
                pass

            instance = Created()
            self.assertEqual(
                self.received,
                [
                    {
                        "signal": signals.post_init,
                        "sender": Created,
                        "instance": instance,
                    }
                ],
            )
        finally:
            signals.post_init.disconnect(self.receiver, sender=Created)

    @isolate_apps("signals", kwarg_name="apps")
    def test_disconnect_registered_model(self, apps):
        received = []

        def receiver(**kwargs):
            received.append(kwargs)

        class Created(models.Model):
            pass

        signals.post_init.connect(receiver, sender="signals.Created", apps=apps)
        try:
            self.assertIsNone(
                signals.post_init.disconnect(
                    receiver, sender="signals.Created", apps=apps
                )
            )
            self.assertIsNone(
                signals.post_init.disconnect(
                    receiver, sender="signals.Created", apps=apps
                )
            )
            Created()
            self.assertEqual(received, [])
        finally:
            signals.post_init.disconnect(receiver, sender="signals.Created")

    @isolate_apps("signals", kwarg_name="apps")
    def test_disconnect_unregistered_model(self, apps):
        received = []

        def receiver(**kwargs):
            received.append(kwargs)

        signals.post_init.connect(receiver, sender="signals.Created", apps=apps)
        try:
            self.assertIsNone(
                signals.post_init.disconnect(
                    receiver, sender="signals.Created", apps=apps
                )
            )
            self.assertIsNone(
                signals.post_init.disconnect(
                    receiver, sender="signals.Created", apps=apps
                )
            )

            class Created(models.Model):
                pass

            Created()
            self.assertEqual(received, [])
        finally:
            signals.post_init.disconnect(receiver, sender="signals.Created")

    def test_register_model_class_senders_immediately(self):
        """
        Model signals registered with model classes as senders don't use the
        Apps.lazy_model_operation() mechanism.
        """
        # Book isn't registered with apps2, so it will linger in
        # apps2._pending_operations if ModelSignal does the wrong thing.
        apps2 = Apps()
        signals.post_init.connect(self.receiver, sender=Book, apps=apps2)
        self.assertEqual(list(apps2._pending_operations), [])


class SyncHandler:
    param = 0

    def __call__(self, **kwargs):
        self.param += 1
        return self.param


class AsyncHandler:
    param = 0

    def __init__(self):
        markcoroutinefunction(self)

    async def __call__(self, **kwargs):
        self.param += 1
        return self.param


class AsyncReceiversTests(SimpleTestCase):
    async def test_asend(self):
        sync_handler = SyncHandler()
        async_handler = AsyncHandler()
        signal = dispatch.Signal()
        signal.connect(sync_handler)
        signal.connect(async_handler)
        result = await signal.asend(self.__class__)
        self.assertEqual(result, [(sync_handler, 1), (async_handler, 1)])

    def test_send(self):
        """
        Tests the functionality of sending a signal through the dispatch system.

        This function verifies that both synchronous and asynchronous handlers are properly
        notified when a signal is sent. It checks that the signal's send method returns
        the expected results, which include the handlers that were called and their respective
        return values.

        The test case covers the connection of both sync and async handlers to a signal, 
        and then triggers the signal to ensure the connected handlers are executed as expected.
        It asserts that the results returned by the signal's send method match the expected output.
        """
        sync_handler = SyncHandler()
        async_handler = AsyncHandler()
        signal = dispatch.Signal()
        signal.connect(sync_handler)
        signal.connect(async_handler)
        result = signal.send(self.__class__)
        self.assertEqual(result, [(sync_handler, 1), (async_handler, 1)])

    def test_send_robust(self):
        """

        Test the behavior of the send_robust method of a dispatch signal.

        The send_robust method is used to send a signal to all connected handlers, 
        continuing execution even if one of the handlers raises an exception. 
        This test verifies that the method correctly handles both synchronous and 
        asynchronous handlers, as well as exceptions raised by handlers.

        The test checks that the result of sending the signal is a list of tuples, 
        where each tuple contains a handler and the result of its execution. 
        If a handler raises an exception, the exception is included in the result tuple instead of the result of the handler.

        """
        class ReceiverException(Exception):
            pass

        receiver_exception = ReceiverException()

        async def failing_async_handler(**kwargs):
            raise receiver_exception

        sync_handler = SyncHandler()
        async_handler = AsyncHandler()
        signal = dispatch.Signal()
        signal.connect(failing_async_handler)
        signal.connect(async_handler)
        signal.connect(sync_handler)
        result = signal.send_robust(self.__class__)
        # The ordering here is different than the order that signals were
        # connected in.
        self.assertEqual(
            result,
            [
                (sync_handler, 1),
                (failing_async_handler, receiver_exception),
                (async_handler, 1),
            ],
        )

    async def test_asend_robust(self):
        """

        Tests the robust asynchronous sending of a signal to connected handlers.

        This function checks that the :meth:`asend_robust` method can handle a mix of synchronous and asynchronous handlers,
        including ones that may raise exceptions, and returns the expected results.

        The function verifies that the signal is sent to all connected handlers and that the results are collected correctly,
        including any exceptions that may have been raised during the sending process.

        """
        class ReceiverException(Exception):
            pass

        receiver_exception = ReceiverException()

        async def failing_async_handler(**kwargs):
            raise receiver_exception

        sync_handler = SyncHandler()
        async_handler = AsyncHandler()
        signal = dispatch.Signal()
        signal.connect(failing_async_handler)
        signal.connect(async_handler)
        signal.connect(sync_handler)
        result = await signal.asend_robust(self.__class__)
        # The ordering here is different than the order that signals were
        # connected in.
        self.assertEqual(
            result,
            [
                (sync_handler, 1),
                (failing_async_handler, receiver_exception),
                (async_handler, 1),
            ],
        )

    async def test_asend_only_async_receivers(self):
        """
        Test sending a signal to asynchronous receivers using async/await syntax.

        This test case verifies that the asend method correctly dispatches a signal to
        asynchronous handler functions, ensuring that the signal is sent and received
        properly. The test also checks that the result returned by asend contains the
        expected handler and argument count.

        :raises: AssertionError if the asend method does not return the expected result
        """
        async_handler = AsyncHandler()
        signal = dispatch.Signal()
        signal.connect(async_handler)

        result = await signal.asend(self.__class__)
        self.assertEqual(result, [(async_handler, 1)])

    async def test_asend_robust_only_async_receivers(self):
        async_handler = AsyncHandler()
        signal = dispatch.Signal()
        signal.connect(async_handler)

        result = await signal.asend_robust(self.__class__)
        self.assertEqual(result, [(async_handler, 1)])
