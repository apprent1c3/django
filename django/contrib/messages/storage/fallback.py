from django.contrib.messages.storage.base import BaseStorage
from django.contrib.messages.storage.cookie import CookieStorage
from django.contrib.messages.storage.session import SessionStorage


class FallbackStorage(BaseStorage):
    """
    Try to store all messages in the first backend. Store any unstored
    messages in each subsequent backend.
    """

    storage_classes = (CookieStorage, SessionStorage)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.storages = [
            storage_class(*args, **kwargs) for storage_class in self.storage_classes
        ]
        self._used_storages = set()

    def _get(self, *args, **kwargs):
        """
        Retrieves a list of messages from all available storage backends, aggregating messages until all backends have been queried or a single backend indicates all messages have been retrieved.
        """
        all_messages = []
        for storage in self.storages:
            messages, all_retrieved = storage._get()
            # If the backend hasn't been used, no more retrieval is necessary.
            if messages is None:
                break
            if messages:
                self._used_storages.add(storage)
            all_messages.extend(messages)
            # If this storage class contained all the messages, no further
            # retrieval is necessary
            if all_retrieved:
                break
        return all_messages, all_retrieved

    def _store(self, messages, response, *args, **kwargs):
        """
        Stores given messages using a series of storage backends, with each backend attempting to store any messages not stored by the previous one, and returns a list of any messages that could not be stored by any backend.
        """
        for storage in self.storages:
            if messages:
                messages = storage._store(messages, response, remove_oldest=False)
            # Even if there are no more messages, continue iterating to ensure
            # storages which contained messages are flushed.
            elif storage in self._used_storages:
                storage._store([], response)
                self._used_storages.remove(storage)
        return messages
