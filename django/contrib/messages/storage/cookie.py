import binascii
import json

from django.conf import settings
from django.contrib.messages.storage.base import BaseStorage, Message
from django.core import signing
from django.http import SimpleCookie
from django.utils.safestring import SafeData, mark_safe


class MessageEncoder(json.JSONEncoder):
    """
    Compactly serialize instances of the ``Message`` class as JSON.
    """

    message_key = "__json_message"

    def default(self, obj):
        """
        Handle serialization of Message objects into a list format, 
        adding relevant metadata such as message key, safety data flag, 
        and logging level, with optional extra tags if provided, 
        otherwise defer to the parent class for serialization.
        """
        if isinstance(obj, Message):
            # Using 0/1 here instead of False/True to produce more compact json
            is_safedata = 1 if isinstance(obj.message, SafeData) else 0
            message = [self.message_key, is_safedata, obj.level, obj.message]
            if obj.extra_tags is not None:
                message.append(obj.extra_tags)
            return message
        return super().default(obj)


class MessageDecoder(json.JSONDecoder):
    """
    Decode JSON that includes serialized ``Message`` instances.
    """

    def process_messages(self, obj):
        """
        Recursively processes a given object, decoding and marking as safe any messages found within lists or dictionaries, and returning the processed object.
        """
        if isinstance(obj, list) and obj:
            if obj[0] == MessageEncoder.message_key:
                if obj[1]:
                    obj[3] = mark_safe(obj[3])
                return Message(*obj[2:])
            return [self.process_messages(item) for item in obj]
        if isinstance(obj, dict):
            return {key: self.process_messages(value) for key, value in obj.items()}
        return obj

    def decode(self, s, **kwargs):
        decoded = super().decode(s, **kwargs)
        return self.process_messages(decoded)


class MessagePartSerializer:
    def dumps(self, obj):
        return [
            json.dumps(
                o,
                separators=(",", ":"),
                cls=MessageEncoder,
            )
            for o in obj
        ]


class MessagePartGatherSerializer:
    def dumps(self, obj):
        """
        The parameter is an already serialized list of Message objects. No need
        to serialize it again, only join the list together and encode it.
        """
        return ("[" + ",".join(obj) + "]").encode("latin-1")


class MessageSerializer:
    def loads(self, data):
        return json.loads(data.decode("latin-1"), cls=MessageDecoder)


class CookieStorage(BaseStorage):
    """
    Store messages in a cookie.
    """

    cookie_name = "messages"
    # uwsgi's default configuration enforces a maximum size of 4kb for all the
    # HTTP headers. In order to leave some room for other cookies and headers,
    # restrict the session cookie to 1/2 of 4kb. See #18781.
    max_cookie_size = 2048
    not_finished = "__messagesnotfinished__"
    not_finished_json = json.dumps("__messagesnotfinished__")
    key_salt = "django.contrib.messages"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.signer = signing.get_cookie_signer(salt=self.key_salt)

    def _get(self, *args, **kwargs):
        """
        Retrieves a list of messages stored in the messages cookie and indicates whether all messages have been retrieved.
        """
        data = self.request.COOKIES.get(self.cookie_name)
        messages = self._decode(data)
        all_retrieved = not (messages and messages[-1] == self.not_finished)
        if messages and not all_retrieved:
            # remove the sentinel value
            messages.pop()
        return messages, all_retrieved

    def _update_cookie(self, encoded_data, response):
        """
        Updates the cookie with the encoded data if present, or deletes it if empty.
        """
        if encoded_data:
            response.set_cookie(
                self.cookie_name,
                encoded_data,
                domain=settings.SESSION_COOKIE_DOMAIN,
                secure=settings.SESSION_COOKIE_SECURE or None,
                httponly=settings.SESSION_COOKIE_HTTPONLY or None,
                samesite=settings.SESSION_COOKIE_SAMESITE,
            )
        else:
            response.delete_cookie(
                self.cookie_name,
                domain=settings.SESSION_COOKIE_DOMAIN,
                samesite=settings.SESSION_COOKIE_SAMESITE,
            )

    def _store(self, messages, response, remove_oldest=True, *args, **kwargs):
        """
        Stores messages in a cookie, returning a list of messages that could not be stored due to cookie size limitations. If the encoded message data exceeds the maximum cookie size, messages are removed to fit within the size constraint, with the removed messages being returned.
        """
        unstored_messages = []
        serialized_messages = MessagePartSerializer().dumps(messages)
        encoded_data = self._encode_parts(serialized_messages)
        if self.max_cookie_size:
            # data is going to be stored eventually by SimpleCookie, which
            # adds its own overhead, which we must account for.
            cookie = SimpleCookie()  # create outside the loop

            def is_too_large_for_cookie(data):
                return data and len(cookie.value_encode(data)[1]) > self.max_cookie_size

            def compute_msg(some_serialized_msg):
                return self._encode_parts(
                    some_serialized_msg + [self.not_finished_json],
                    encode_empty=True,
                )

            if is_too_large_for_cookie(encoded_data):
                if remove_oldest:
                    idx = bisect_keep_right(
                        serialized_messages,
                        fn=lambda m: is_too_large_for_cookie(compute_msg(m)),
                    )
                    unstored_messages = messages[:idx]
                    encoded_data = compute_msg(serialized_messages[idx:])
                else:
                    idx = bisect_keep_left(
                        serialized_messages,
                        fn=lambda m: is_too_large_for_cookie(compute_msg(m)),
                    )
                    unstored_messages = messages[idx:]
                    encoded_data = compute_msg(serialized_messages[:idx])

        self._update_cookie(encoded_data, response)
        return unstored_messages

    def _encode_parts(self, messages, encode_empty=False):
        """
        Return an encoded version of the serialized messages list which can be
        stored as plain text.

        Since the data will be retrieved from the client-side, the encoded data
        also contains a hash to ensure that the data was not tampered with.
        """
        if messages or encode_empty:
            return self.signer.sign_object(
                messages, serializer=MessagePartGatherSerializer, compress=True
            )

    def _encode(self, messages, encode_empty=False):
        """
        Return an encoded version of the messages list which can be stored as
        plain text.

        Proxies MessagePartSerializer.dumps and _encoded_parts.
        """
        serialized_messages = MessagePartSerializer().dumps(messages)
        return self._encode_parts(serialized_messages, encode_empty=encode_empty)

    def _decode(self, data):
        """
        Decodes an encoded text stream back into a list of messages.

        Reverses the encoding process, returning the original messages if the data is valid.

        Returns None if the encoded text stream contains an invalid hash, is in an invalid format, or if the decoding process fails.
        """
        if not data:
            return None
        try:
            return self.signer.unsign_object(data, serializer=MessageSerializer)
        except (signing.BadSignature, binascii.Error, json.JSONDecodeError):
            pass
        # Mark the data as used (so it gets removed) since something was wrong
        # with the data.
        self.used = True
        return None


def bisect_keep_left(a, fn):
    """
    Find the index of the first element from the start of the array that verifies the given condition, using a binary search approach. The condition is checked for the subarray from the start to the pivot, allowing for efficient search.
    """
    lo = 0
    hi = len(a)
    while lo < hi:
        mid = (lo + hi) // 2
        if fn(a[: mid + 1]):
            hi = mid
        else:
            lo = mid + 1
    return lo


def bisect_keep_right(a, fn):
    """

    Find the index of the first element from the end of the array that verifies
    the given condition. The function is applied from the pivot to the end of array.

    :param a: The input array
    :param fn: The function to apply to subarrays of a
    :return: The index of the first element from the end of the array that verifies the condition

    """
    lo = 0
    hi = len(a)
    while lo < hi:
        mid = (lo + hi) // 2
        if fn(a[mid:]):
            lo = mid + 1
        else:
            hi = mid
    return lo
