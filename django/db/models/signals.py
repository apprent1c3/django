from functools import partial

from django.db.models.utils import make_model_tuple
from django.dispatch import Signal

class_prepared = Signal()


class ModelSignal(Signal):
    """
    Signal subclass that allows the sender to be lazily specified as a string
    of the `app_label.ModelName` form.
    """

    def _lazy_method(self, method, apps, receiver, sender, **kwargs):
        """
        Defers the execution of a given method until the model is fully loaded, allowing for lazy model operations.

        :param method: The method to be executed.
        :param apps: Django application registry.
        :param receiver: The receiver object for the method call.
        :param sender: The model instance or name that triggers the operation.
        :param kwargs: Additional keyword arguments to be passed to the method.

        :note: If the sender is a string, the operation is deferred until the model is loaded.
                If the sender is an instance, the method is executed immediately.
        :returns: The result of the method execution if the sender is an instance, otherwise None.
        """
        from django.db.models.options import Options

        # This partial takes a single optional argument named "sender".
        partial_method = partial(method, receiver, **kwargs)
        if isinstance(sender, str):
            apps = apps or Options.default_apps
            apps.lazy_model_operation(partial_method, make_model_tuple(sender))
        else:
            return partial_method(sender)

    def connect(self, receiver, sender=None, weak=True, dispatch_uid=None, apps=None):
        self._lazy_method(
            super().connect,
            apps,
            receiver,
            sender,
            weak=weak,
            dispatch_uid=dispatch_uid,
        )

    def disconnect(self, receiver=None, sender=None, dispatch_uid=None, apps=None):
        return self._lazy_method(
            super().disconnect, apps, receiver, sender, dispatch_uid=dispatch_uid
        )


pre_init = ModelSignal(use_caching=True)
post_init = ModelSignal(use_caching=True)

pre_save = ModelSignal(use_caching=True)
post_save = ModelSignal(use_caching=True)

pre_delete = ModelSignal(use_caching=True)
post_delete = ModelSignal(use_caching=True)

m2m_changed = ModelSignal(use_caching=True)

pre_migrate = Signal()
post_migrate = Signal()
