import asyncio
import logging
import threading
import weakref

from asgiref.sync import async_to_sync, iscoroutinefunction, sync_to_async

from django.utils.inspect import func_accepts_kwargs

logger = logging.getLogger("django.dispatch")


def _make_id(target):
    if hasattr(target, "__func__"):
        return (id(target.__self__), id(target.__func__))
    return id(target)


NONE_ID = _make_id(None)

# A marker for caching
NO_RECEIVERS = object()


class Signal:
    """
    Base class for all signals

    Internal attributes:

        receivers
            { receiverkey (id) : weakref(receiver) }
    """

    def __init__(self, use_caching=False):
        """
        Initializes a new signal, preparing it to manage a set of receivers. 
        The `use_caching` parameter determines whether caching is used to optimize receiver lookup.
        """
        self.receivers = []
        self.lock = threading.Lock()
        self.use_caching = use_caching
        # For convenience we create empty caches even if they are not used.
        # A note about caching: if use_caching is defined, then for each
        # distinct sender we cache the receivers that sender has in
        # 'sender_receivers_cache'. The cache is cleaned when .connect() or
        # .disconnect() is called and populated on send().
        self.sender_receivers_cache = weakref.WeakKeyDictionary() if use_caching else {}
        self._dead_receivers = False

    def connect(self, receiver, sender=None, weak=True, dispatch_uid=None):
        """

            Connect a receiver function or method to a sender object for signal notification.

            This method establishes a connection between a receiver, which can be a function or instance method,
            and a sender, allowing the receiver to respond to signals emitted by the sender.

            Parameters
            ----------
            receiver : callable
                The function or instance method to receive signals.
            sender : object, optional
                The sender object to which the receiver should respond. Defaults to None.
            weak : bool, optional
                Whether to use a weak reference to the receiver. Defaults to True.
            dispatch_uid : hashable, optional
                A unique identifier for the receiver. Defaults to None.

        """
        from django.conf import settings

        # If DEBUG is on, check that we got a good receiver
        if settings.configured and settings.DEBUG:
            if not callable(receiver):
                raise TypeError("Signal receivers must be callable.")
            # Check for **kwargs
            if not func_accepts_kwargs(receiver):
                raise ValueError(
                    "Signal receivers must accept keyword arguments (**kwargs)."
                )

        if dispatch_uid:
            lookup_key = (dispatch_uid, _make_id(sender))
        else:
            lookup_key = (_make_id(receiver), _make_id(sender))

        is_async = iscoroutinefunction(receiver)

        if weak:
            ref = weakref.ref
            receiver_object = receiver
            # Check for bound methods
            if hasattr(receiver, "__self__") and hasattr(receiver, "__func__"):
                ref = weakref.WeakMethod
                receiver_object = receiver.__self__
            receiver = ref(receiver)
            weakref.finalize(receiver_object, self._remove_receiver)

        with self.lock:
            self._clear_dead_receivers()
            if not any(r_key == lookup_key for r_key, _, _ in self.receivers):
                self.receivers.append((lookup_key, receiver, is_async))
            self.sender_receivers_cache.clear()

    def disconnect(self, receiver=None, sender=None, dispatch_uid=None):
        """
        Disconnect a receiver from a sender for a signal, allowing for flexible disconnection via receiver, sender, or unique dispatch UID.
        """
        if dispatch_uid:
            lookup_key = (dispatch_uid, _make_id(sender))
        else:
            lookup_key = (_make_id(receiver), _make_id(sender))

        disconnected = False
        with self.lock:
            self._clear_dead_receivers()
            for index in range(len(self.receivers)):
                r_key, *_ = self.receivers[index]
                if r_key == lookup_key:
                    disconnected = True
                    del self.receivers[index]
                    break
            self.sender_receivers_cache.clear()
        return disconnected

    def has_listeners(self, sender=None):
        sync_receivers, async_receivers = self._live_receivers(sender)
        return bool(sync_receivers) or bool(async_receivers)

    def send(self, sender, **named):
        """
        Send a signal from a specified sender to all connected receivers, handling both synchronous and asynchronous receivers, and return a list of receiver responses.
        """
        if (
            not self.receivers
            or self.sender_receivers_cache.get(sender) is NO_RECEIVERS
        ):
            return []
        responses = []
        sync_receivers, async_receivers = self._live_receivers(sender)
        for receiver in sync_receivers:
            response = receiver(signal=self, sender=sender, **named)
            responses.append((receiver, response))
        if async_receivers:

            async def asend():
                async_responses = await asyncio.gather(
                    *(
                        receiver(signal=self, sender=sender, **named)
                        for receiver in async_receivers
                    )
                )
                return zip(async_receivers, async_responses)

            responses.extend(async_to_sync(asend)())
        return responses

    async def asend(self, sender, **named):
        """
        Send signal from sender to all connected receivers in async mode.

        Asynchronously dispatches a signal to all attached receivers, 
        handling both sync and async receivers. Any sync receivers are 
        adapted and executed before async ones, which are run concurrently.

        若_declare arguments_: 

            sender
                The object sending the signal, or None.

            named
                Keyword arguments passed to receivers.

        Returns a list of tuples containing each receiver and its response.
        """
        if (
            not self.receivers
            or self.sender_receivers_cache.get(sender) is NO_RECEIVERS
        ):
            return []
        sync_receivers, async_receivers = self._live_receivers(sender)
        if sync_receivers:

            @sync_to_async
            def sync_send():
                """

                Asynchronously sends a signal to all registered receivers and returns their responses.

                :param: None
                :returns: A list of tuples containing the receiver and its corresponding response.

                """
                responses = []
                for receiver in sync_receivers:
                    response = receiver(signal=self, sender=sender, **named)
                    responses.append((receiver, response))
                return responses

        else:

            async def sync_send():
                return []

        responses, async_responses = await asyncio.gather(
            sync_send(),
            asyncio.gather(
                *(
                    receiver(signal=self, sender=sender, **named)
                    for receiver in async_receivers
                )
            ),
        )
        responses.extend(zip(async_receivers, async_responses))
        return responses

    def _log_robust_failure(self, receiver, err):
        logger.error(
            "Error calling %s in Signal.send_robust() (%s)",
            receiver.__qualname__,
            err,
            exc_info=err,
        )

    def send_robust(self, sender, **named):
        """
        Send a signal from a sender to connected receivers, catching and handling any errors that occur during signal transmission.

        The function differentiates between synchronous and asynchronous receivers, executing the latter concurrently using asyncio.gather(). 

        It returns a list of tuples, where each tuple contains a receiver and its corresponding response. If a receiver raises an error, the error instance is returned as the response for that receiver. 

        The function takes two parameters: the sender of the signal and any named arguments to be passed to the receivers.
        """
        if (
            not self.receivers
            or self.sender_receivers_cache.get(sender) is NO_RECEIVERS
        ):
            return []

        # Call each receiver with whatever arguments it can accept.
        # Return a list of tuple pairs [(receiver, response), ... ].
        responses = []
        sync_receivers, async_receivers = self._live_receivers(sender)
        for receiver in sync_receivers:
            try:
                response = receiver(signal=self, sender=sender, **named)
            except Exception as err:
                self._log_robust_failure(receiver, err)
                responses.append((receiver, err))
            else:
                responses.append((receiver, response))
        if async_receivers:

            async def asend_and_wrap_exception(receiver):
                """
                Send a signal to a receiver and handle any exceptions that occur.

                The receiver is called with the signal and sender as arguments, and any additional
                keyword arguments are passed through. If an exception occurs during the call, it
                is logged and then returned. Otherwise, the response from the receiver is returned.
                """
                try:
                    response = await receiver(signal=self, sender=sender, **named)
                except Exception as err:
                    self._log_robust_failure(receiver, err)
                    return err
                return response

            async def asend():
                async_responses = await asyncio.gather(
                    *(
                        asend_and_wrap_exception(receiver)
                        for receiver in async_receivers
                    )
                )
                return zip(async_receivers, async_responses)

            responses.extend(async_to_sync(asend)())
        return responses

    async def asend_robust(self, sender, **named):
        """
        Send a signal from a given sender to all connected receivers, handling exceptions and supporting both synchronous and asynchronous receivers. 

        Arguments:
            sender: The sender of the signal.
            **named: Named arguments passed to receivers.

        Returns:
            A list of tuples, where each tuple contains a receiver and its response or error if an exception occurred.
        """
        if (
            not self.receivers
            or self.sender_receivers_cache.get(sender) is NO_RECEIVERS
        ):
            return []

        # Call each receiver with whatever arguments it can accept.
        # Return a list of tuple pairs [(receiver, response), ... ].
        sync_receivers, async_receivers = self._live_receivers(sender)

        if sync_receivers:

            @sync_to_async
            def sync_send():
                """
                Asynchronously sends a signal to a list of registered receivers, capturing and logging any failures that occur during the sending process, and returning a list of tuples containing each receiver and its corresponding response or error.
                """
                responses = []
                for receiver in sync_receivers:
                    try:
                        response = receiver(signal=self, sender=sender, **named)
                    except Exception as err:
                        self._log_robust_failure(receiver, err)
                        responses.append((receiver, err))
                    else:
                        responses.append((receiver, response))
                return responses

        else:

            async def sync_send():
                return []

        async def asend_and_wrap_exception(receiver):
            """
            Send a signal to a receiver and handle any exceptions that occur.

            Asynchronously invokes the receiver with the given signal and arguments.
            If an exception is raised, it is logged as a robust failure and then returned,
            otherwise the receiver's response is returned.
            """
            try:
                response = await receiver(signal=self, sender=sender, **named)
            except Exception as err:
                self._log_robust_failure(receiver, err)
                return err
            return response

        responses, async_responses = await asyncio.gather(
            sync_send(),
            asyncio.gather(
                *(asend_and_wrap_exception(receiver) for receiver in async_receivers),
            ),
        )
        responses.extend(zip(async_receivers, async_responses))
        return responses

    def _clear_dead_receivers(self):
        # Note: caller is assumed to hold self.lock.
        if self._dead_receivers:
            self._dead_receivers = False
            self.receivers = [
                r
                for r in self.receivers
                if not (isinstance(r[1], weakref.ReferenceType) and r[1]() is None)
            ]

    def _live_receivers(self, sender):
        """
        Filters and resolves a sequence of receivers for a given sender, 
        returning two lists: synchronous live receivers and asynchronous live receivers. 
        It removes dead receivers, handles weak references, and supports caching for performance.
        """
        receivers = None
        if self.use_caching and not self._dead_receivers:
            receivers = self.sender_receivers_cache.get(sender)
            # We could end up here with NO_RECEIVERS even if we do check this case in
            # .send() prior to calling _live_receivers() due to concurrent .send() call.
            if receivers is NO_RECEIVERS:
                return [], []
        if receivers is None:
            with self.lock:
                self._clear_dead_receivers()
                senderkey = _make_id(sender)
                receivers = []
                for (_receiverkey, r_senderkey), receiver, is_async in self.receivers:
                    if r_senderkey == NONE_ID or r_senderkey == senderkey:
                        receivers.append((receiver, is_async))
                if self.use_caching:
                    if not receivers:
                        self.sender_receivers_cache[sender] = NO_RECEIVERS
                    else:
                        # Note, we must cache the weakref versions.
                        self.sender_receivers_cache[sender] = receivers
        non_weak_sync_receivers = []
        non_weak_async_receivers = []
        for receiver, is_async in receivers:
            if isinstance(receiver, weakref.ReferenceType):
                # Dereference the weak reference.
                receiver = receiver()
                if receiver is not None:
                    if is_async:
                        non_weak_async_receivers.append(receiver)
                    else:
                        non_weak_sync_receivers.append(receiver)
            else:
                if is_async:
                    non_weak_async_receivers.append(receiver)
                else:
                    non_weak_sync_receivers.append(receiver)
        return non_weak_sync_receivers, non_weak_async_receivers

    def _remove_receiver(self, receiver=None):
        # Mark that the self.receivers list has dead weakrefs. If so, we will
        # clean those up in connect, disconnect and _live_receivers while
        # holding self.lock. Note that doing the cleanup here isn't a good
        # idea, _remove_receiver() will be called as side effect of garbage
        # collection, and so the call can happen while we are already holding
        # self.lock.
        self._dead_receivers = True


def receiver(signal, **kwargs):
    """
    Connects a function to one or more signals, allowing it to receive notifications when the signals are sent.
    """

    def _decorator(func):
        """
        Registers a function to receive notifications from one or more signals.

        Connects the provided function to the given signal(s), allowing it to react to events.
        Returns the original function, unchanged, to enable decorator syntax usage.
        """
        if isinstance(signal, (list, tuple)):
            for s in signal:
                s.connect(func, **kwargs)
        else:
            signal.connect(func, **kwargs)
        return func

    return _decorator
