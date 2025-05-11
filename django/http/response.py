import datetime
import io
import json
import mimetypes
import os
import re
import sys
import time
import warnings
from email.header import Header
from http.client import responses
from urllib.parse import urlsplit

from asgiref.sync import async_to_sync, sync_to_async

from django.conf import settings
from django.core import signals, signing
from django.core.exceptions import DisallowedRedirect
from django.core.serializers.json import DjangoJSONEncoder
from django.http.cookie import SimpleCookie
from django.utils import timezone
from django.utils.datastructures import CaseInsensitiveMapping
from django.utils.encoding import iri_to_uri
from django.utils.http import content_disposition_header, http_date
from django.utils.regex_helper import _lazy_re_compile

_charset_from_content_type_re = _lazy_re_compile(
    r";\s*charset=(?P<charset>[^\s;]+)", re.I
)


class ResponseHeaders(CaseInsensitiveMapping):
    def __init__(self, data):
        """
        Initializes the object with the given data, properly encoding the values.
        """
        self._store = {}
        if data:
            for header, value in self._unpack_items(data):
                self[header] = value

    def _convert_to_charset(self, value, charset, mime_encode=False):
        """
        Converts a header value to the specified charset, either 'ascii' or 'latin-1', 
        applying MIME-encoding if the value cannot be represented in the given charset and 
        mime_encode is True, while validating that the value does not contain newlines.
        """
        try:
            if isinstance(value, str):
                # Ensure string is valid in given charset
                value.encode(charset)
            elif isinstance(value, bytes):
                # Convert bytestring using given charset
                value = value.decode(charset)
            else:
                value = str(value)
                # Ensure string is valid in given charset.
                value.encode(charset)
            if "\n" in value or "\r" in value:
                raise BadHeaderError(
                    f"Header values can't contain newlines (got {value!r})"
                )
        except UnicodeError as e:
            # Encoding to a string of the specified charset failed, but we
            # don't know what type that value was, or if it contains newlines,
            # which we may need to check for before sending it to be
            # encoded for multiple character sets.
            if (isinstance(value, bytes) and (b"\n" in value or b"\r" in value)) or (
                isinstance(value, str) and ("\n" in value or "\r" in value)
            ):
                raise BadHeaderError(
                    f"Header values can't contain newlines (got {value!r})"
                ) from e
            if mime_encode:
                value = Header(value, "utf-8", maxlinelen=sys.maxsize).encode()
            else:
                e.reason += ", HTTP response headers must be in %s format" % charset
                raise
        return value

    def __delitem__(self, key):
        self.pop(key)

    def __setitem__(self, key, value):
        key = self._convert_to_charset(key, "ascii")
        value = self._convert_to_charset(value, "latin-1", mime_encode=True)
        self._store[key.lower()] = (key, value)

    def pop(self, key, default=None):
        return self._store.pop(key.lower(), default)

    def setdefault(self, key, value):
        if key not in self:
            self[key] = value


class BadHeaderError(ValueError):
    pass


class HttpResponseBase:
    """
    An HTTP response base class with dictionary-accessed headers.

    This class doesn't handle content. It should not be used directly.
    Use the HttpResponse and StreamingHttpResponse subclasses instead.
    """

    status_code = 200

    def __init__(
        self, content_type=None, status=None, reason=None, charset=None, headers=None
    ):
        """

        Initialize a response object with optional content type, HTTP status, reason phrase, character set, and headers.

        The response object is responsible for managing HTTP response data, including headers, status codes, and cookies.
        It provides a flexible way to construct and configure HTTP responses for various use cases.

        :param content_type: The content type of the response (e.g., text/html, application/json)
        :param status: The HTTP status code of the response (e.g., 200, 404, 500)
        :param reason: The reason phrase of the response (e.g., OK, Not Found, Internal Server Error)
        :param charset: The character set of the response (e.g., utf-8, iso-8859-1)
        :param headers: A dictionary of HTTP headers to include in the response

        """
        self.headers = ResponseHeaders(headers)
        self._charset = charset
        if "Content-Type" not in self.headers:
            if content_type is None:
                content_type = f"text/html; charset={self.charset}"
            self.headers["Content-Type"] = content_type
        elif content_type:
            raise ValueError(
                "'headers' must not contain 'Content-Type' when the "
                "'content_type' parameter is provided."
            )
        self._resource_closers = []
        # This parameter is set by the handler. It's necessary to preserve the
        # historical behavior of request_finished.
        self._handler_class = None
        self.cookies = SimpleCookie()
        self.closed = False
        if status is not None:
            try:
                self.status_code = int(status)
            except (ValueError, TypeError):
                raise TypeError("HTTP status code must be an integer.")

            if not 100 <= self.status_code <= 599:
                raise ValueError("HTTP status code must be an integer from 100 to 599.")
        self._reason_phrase = reason

    @property
    def reason_phrase(self):
        if self._reason_phrase is not None:
            return self._reason_phrase
        # Leave self._reason_phrase unset in order to use the default
        # reason phrase for status code.
        return responses.get(self.status_code, "Unknown Status Code")

    @reason_phrase.setter
    def reason_phrase(self, value):
        self._reason_phrase = value

    @property
    def charset(self):
        """
        Returns the character set of the object, attempting to determine it from the 'Content-Type' header if not explicitly set. If still unknown, defaults to the DEFAULT_CHARSET setting.
        """
        if self._charset is not None:
            return self._charset
        # The Content-Type header may not yet be set, because the charset is
        # being inserted *into* it.
        if content_type := self.headers.get("Content-Type"):
            if matched := _charset_from_content_type_re.search(content_type):
                # Extract the charset and strip its double quotes.
                # Note that having parsed it from the Content-Type, we don't
                # store it back into the _charset for later intentionally, to
                # allow for the Content-Type to be switched again later.
                return matched["charset"].replace('"', "")
        return settings.DEFAULT_CHARSET

    @charset.setter
    def charset(self, value):
        self._charset = value

    def serialize_headers(self):
        """HTTP headers as a bytestring."""
        return b"\r\n".join(
            [
                key.encode("ascii") + b": " + value.encode("latin-1")
                for key, value in self.headers.items()
            ]
        )

    __bytes__ = serialize_headers

    @property
    def _content_type_for_repr(self):
        return (
            ', "%s"' % self.headers["Content-Type"]
            if "Content-Type" in self.headers
            else ""
        )

    def __setitem__(self, header, value):
        self.headers[header] = value

    def __delitem__(self, header):
        del self.headers[header]

    def __getitem__(self, header):
        return self.headers[header]

    def has_header(self, header):
        """Case-insensitive check for a header."""
        return header in self.headers

    __contains__ = has_header

    def items(self):
        return self.headers.items()

    def get(self, header, alternate=None):
        return self.headers.get(header, alternate)

    def set_cookie(
        self,
        key,
        value="",
        max_age=None,
        expires=None,
        path="/",
        domain=None,
        secure=False,
        httponly=False,
        samesite=None,
    ):
        """
        Set a cookie with the given key and value, and optional attributes such as expiration date, maximum age, path, domain, security and same-site flags. The ``expires`` attribute can be specified as a string, a naive or aware datetime object, and the ``max_age`` attribute can be specified as an integer, float or timedelta object.
        """
        self.cookies[key] = value
        if expires is not None:
            if isinstance(expires, datetime.datetime):
                if timezone.is_naive(expires):
                    expires = timezone.make_aware(expires, datetime.timezone.utc)
                delta = expires - datetime.datetime.now(tz=datetime.timezone.utc)
                # Add one second so the date matches exactly (a fraction of
                # time gets lost between converting to a timedelta and
                # then the date string).
                delta += datetime.timedelta(seconds=1)
                # Just set max_age - the max_age logic will set expires.
                expires = None
                if max_age is not None:
                    raise ValueError("'expires' and 'max_age' can't be used together.")
                max_age = max(0, delta.days * 86400 + delta.seconds)
            else:
                self.cookies[key]["expires"] = expires
        else:
            self.cookies[key]["expires"] = ""
        if max_age is not None:
            if isinstance(max_age, datetime.timedelta):
                max_age = max_age.total_seconds()
            self.cookies[key]["max-age"] = int(max_age)
            # IE requires expires, so set it if hasn't been already.
            if not expires:
                self.cookies[key]["expires"] = http_date(time.time() + max_age)
        if path is not None:
            self.cookies[key]["path"] = path
        if domain is not None:
            self.cookies[key]["domain"] = domain
        if secure:
            self.cookies[key]["secure"] = True
        if httponly:
            self.cookies[key]["httponly"] = True
        if samesite:
            if samesite.lower() not in ("lax", "none", "strict"):
                raise ValueError('samesite must be "lax", "none", or "strict".')
            self.cookies[key]["samesite"] = samesite

    def setdefault(self, key, value):
        """Set a header unless it has already been set."""
        self.headers.setdefault(key, value)

    def set_signed_cookie(self, key, value, salt="", **kwargs):
        value = signing.get_cookie_signer(salt=key + salt).sign(value)
        return self.set_cookie(key, value, **kwargs)

    def delete_cookie(self, key, path="/", domain=None, samesite=None):
        # Browsers can ignore the Set-Cookie header if the cookie doesn't use
        # the secure flag and:
        # - the cookie name starts with "__Host-" or "__Secure-", or
        # - the samesite is "none".
        secure = key.startswith(("__Secure-", "__Host-")) or (
            samesite and samesite.lower() == "none"
        )
        self.set_cookie(
            key,
            max_age=0,
            path=path,
            domain=domain,
            secure=secure,
            expires="Thu, 01 Jan 1970 00:00:00 GMT",
            samesite=samesite,
        )

    # Common methods used by subclasses

    def make_bytes(self, value):
        """
        Encode a given value into a bytestring using the output charset.
        """
        # Per PEP 3333, this response body must be bytes. To avoid returning
        # an instance of a subclass, this function returns `bytes(value)`.
        # This doesn't make a copy when `value` already contains bytes.

        # Handle string types -- we can't rely on force_bytes here because:
        # - Python attempts str conversion first
        # - when self._charset != 'utf-8' it re-encodes the content
        if isinstance(value, (bytes, memoryview)):
            return bytes(value)
        if isinstance(value, str):
            return bytes(value.encode(self.charset))
        # Handle non-string types.
        return str(value).encode(self.charset)

    # These methods partially implement the file-like object interface.
    # See https://docs.python.org/library/io.html#io.IOBase

    # The WSGI server must call this method upon completion of the request.
    # See http://blog.dscpl.com.au/2012/10/obligations-for-calling-close-on.html
    def close(self):
        """

        Closes all managed resources and signals the end of a request.

        Releases all registered resource closers and prevents further access.

        """
        for closer in self._resource_closers:
            try:
                closer()
            except Exception:
                pass
        # Free resources that were still referenced.
        self._resource_closers.clear()
        self.closed = True
        signals.request_finished.send(sender=self._handler_class)

    def write(self, content):
        raise OSError("This %s instance is not writable" % self.__class__.__name__)

    def flush(self):
        pass

    def tell(self):
        raise OSError(
            "This %s instance cannot tell its position" % self.__class__.__name__
        )

    # These methods partially implement a stream-like object interface.
    # See https://docs.python.org/library/io.html#io.IOBase

    def readable(self):
        return False

    def seekable(self):
        return False

    def writable(self):
        return False

    def writelines(self, lines):
        raise OSError("This %s instance is not writable" % self.__class__.__name__)


class HttpResponse(HttpResponseBase):
    """
    An HTTP response class with a string as content.

    This content can be read, appended to, or replaced.
    """

    streaming = False

    def __init__(self, content=b"", *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Content is a bytestring. See the `content` property methods.
        self.content = content

    def __repr__(self):
        return "<%(cls)s status_code=%(status_code)d%(content_type)s>" % {
            "cls": self.__class__.__name__,
            "status_code": self.status_code,
            "content_type": self._content_type_for_repr,
        }

    def serialize(self):
        """Full HTTP message, including headers, as a bytestring."""
        return self.serialize_headers() + b"\r\n\r\n" + self.content

    __bytes__ = serialize

    @property
    def content(self):
        return b"".join(self._container)

    @content.setter
    def content(self, value):
        # Consume iterators upon assignment to allow repeated iteration.
        """
        Sets the content of the object, converting the provided value into bytes if necessary.
        Accepts both single values and iterables, ensuring that all elements are properly converted.
        Closes the input value if it is an iterable that supports closing.
        """
        if hasattr(value, "__iter__") and not isinstance(
            value, (bytes, memoryview, str)
        ):
            content = b"".join(self.make_bytes(chunk) for chunk in value)
            if hasattr(value, "close"):
                try:
                    value.close()
                except Exception:
                    pass
        else:
            content = self.make_bytes(value)
        # Create a list of properly encoded bytestrings to support write().
        self._container = [content]

    def __iter__(self):
        return iter(self._container)

    def write(self, content):
        self._container.append(self.make_bytes(content))

    def tell(self):
        return len(self.content)

    def getvalue(self):
        return self.content

    def writable(self):
        return True

    def writelines(self, lines):
        for line in lines:
            self.write(line)


class StreamingHttpResponse(HttpResponseBase):
    """
    A streaming HTTP response class with an iterator as content.

    This should only be iterated once, when the response is streamed to the
    client. However, it can be appended to or replaced with a new iterator
    that wraps the original content (or yields entirely new content).
    """

    streaming = True

    def __init__(self, streaming_content=(), *args, **kwargs):
        super().__init__(*args, **kwargs)
        # `streaming_content` should be an iterable of bytestrings.
        # See the `streaming_content` property methods.
        self.streaming_content = streaming_content

    def __repr__(self):
        return "<%(cls)s status_code=%(status_code)d%(content_type)s>" % {
            "cls": self.__class__.__qualname__,
            "status_code": self.status_code,
            "content_type": self._content_type_for_repr,
        }

    @property
    def content(self):
        raise AttributeError(
            "This %s instance has no `content` attribute. Use "
            "`streaming_content` instead." % self.__class__.__name__
        )

    @property
    def streaming_content(self):
        """
        A property that returns an iterator or async iterator over the content data,
        either synchronously or asynchronously, depending on the streaming mode.
        """
        if self.is_async:
            # pull to lexical scope to capture fixed reference in case
            # streaming_content is set again later.
            _iterator = self._iterator

            async def awrapper():
                async for part in _iterator:
                    yield self.make_bytes(part)

            return awrapper()
        else:
            return map(self.make_bytes, self._iterator)

    @streaming_content.setter
    def streaming_content(self, value):
        self._set_streaming_content(value)

    def _set_streaming_content(self, value):
        # Ensure we can never iterate on "value" more than once.
        """

        Sets the streaming content to be iterated over, handling both synchronous and asynchronous sources.

        The function determines whether the provided value is an asynchronous or synchronous iterable and sets the iterator accordingly.
        It also registers the source for closure, if applicable.

        """
        try:
            self._iterator = iter(value)
            self.is_async = False
        except TypeError:
            self._iterator = aiter(value)
            self.is_async = True
        if hasattr(value, "close"):
            self._resource_closers.append(value.close)

    def __iter__(self):
        """

        Return an iterator over the response content, handling both synchronous and asynchronous iterators.

        If the content is an asynchronous iterator, it is converted to a synchronous iterator to ensure compatibility.

        Yields:
            bytes: The response content, split into chunks.

        """
        try:
            return iter(self.streaming_content)
        except TypeError:
            warnings.warn(
                "StreamingHttpResponse must consume asynchronous iterators in order to "
                "serve them synchronously. Use a synchronous iterator instead.",
                Warning,
            )

            # async iterator. Consume in async_to_sync and map back.
            async def to_list(_iterator):
                as_list = []
                async for chunk in _iterator:
                    as_list.append(chunk)
                return as_list

            return map(self.make_bytes, iter(async_to_sync(to_list)(self._iterator)))

    async def __aiter__(self):
        """
        Asynchronous iterator for the response content.

        Yields parts of the content in an asynchronous manner, allowing for 
        streaming responses. If the underlying content is not asynchronous, 
        it will be converted to an asynchronous iterator, generating a warning 
        in the process to recommend using an asynchronous iterator instead.
        """
        try:
            async for part in self.streaming_content:
                yield part
        except TypeError:
            warnings.warn(
                "StreamingHttpResponse must consume synchronous iterators in order to "
                "serve them asynchronously. Use an asynchronous iterator instead.",
                Warning,
            )
            # sync iterator. Consume via sync_to_async and yield via async
            # generator.
            for part in await sync_to_async(list)(self.streaming_content):
                yield part

    def getvalue(self):
        return b"".join(self.streaming_content)


class FileResponse(StreamingHttpResponse):
    """
    A streaming HTTP response class optimized for files.
    """

    block_size = 4096

    def __init__(self, *args, as_attachment=False, filename="", **kwargs):
        self.as_attachment = as_attachment
        self.filename = filename
        self._no_explicit_content_type = (
            "content_type" not in kwargs or kwargs["content_type"] is None
        )
        super().__init__(*args, **kwargs)

    def _set_streaming_content(self, value):
        """
        Sets the streaming content of the object, handling file-like objects and setting appropriate headers, while also ensuring proper resource closure.
        """
        if not hasattr(value, "read"):
            self.file_to_stream = None
            return super()._set_streaming_content(value)

        self.file_to_stream = filelike = value
        if hasattr(filelike, "close"):
            self._resource_closers.append(filelike.close)
        value = iter(lambda: filelike.read(self.block_size), b"")
        self.set_headers(filelike)
        super()._set_streaming_content(value)

    def set_headers(self, filelike):
        """
        Set common response headers based on the provided file-like response content, including Content-Length, Content-Type, and Content-Disposition, to facilitate proper content handling and delivery.
        """
        filename = getattr(filelike, "name", "")
        filename = filename if isinstance(filename, str) else ""
        seekable = hasattr(filelike, "seek") and (
            not hasattr(filelike, "seekable") or filelike.seekable()
        )
        if hasattr(filelike, "tell"):
            if seekable:
                initial_position = filelike.tell()
                filelike.seek(0, io.SEEK_END)
                self.headers["Content-Length"] = filelike.tell() - initial_position
                filelike.seek(initial_position)
            elif hasattr(filelike, "getbuffer"):
                self.headers["Content-Length"] = (
                    filelike.getbuffer().nbytes - filelike.tell()
                )
            elif os.path.exists(filename):
                self.headers["Content-Length"] = (
                    os.path.getsize(filename) - filelike.tell()
                )
        elif seekable:
            self.headers["Content-Length"] = sum(
                iter(lambda: len(filelike.read(self.block_size)), 0)
            )
            filelike.seek(-int(self.headers["Content-Length"]), io.SEEK_END)

        filename = os.path.basename(self.filename or filename)
        if self._no_explicit_content_type:
            if filename:
                content_type, encoding = mimetypes.guess_type(filename)
                # Encoding isn't set to prevent browsers from automatically
                # uncompressing files.
                content_type = {
                    "br": "application/x-brotli",
                    "bzip2": "application/x-bzip",
                    "compress": "application/x-compress",
                    "gzip": "application/gzip",
                    "xz": "application/x-xz",
                }.get(encoding, content_type)
                self.headers["Content-Type"] = (
                    content_type or "application/octet-stream"
                )
            else:
                self.headers["Content-Type"] = "application/octet-stream"

        if content_disposition := content_disposition_header(
            self.as_attachment, filename
        ):
            self.headers["Content-Disposition"] = content_disposition


class HttpResponseRedirectBase(HttpResponse):
    allowed_schemes = ["http", "https", "ftp"]

    def __init__(self, redirect_to, *args, **kwargs):
        """
        Initializes a redirect response object, setting the Location header to the provided URL and validating its protocol against a set of allowed schemes.
        """
        super().__init__(*args, **kwargs)
        self["Location"] = iri_to_uri(redirect_to)
        parsed = urlsplit(str(redirect_to))
        if parsed.scheme and parsed.scheme not in self.allowed_schemes:
            raise DisallowedRedirect(
                "Unsafe redirect to URL with protocol '%s'" % parsed.scheme
            )

    url = property(lambda self: self["Location"])

    def __repr__(self):
        return (
            '<%(cls)s status_code=%(status_code)d%(content_type)s, url="%(url)s">'
            % {
                "cls": self.__class__.__name__,
                "status_code": self.status_code,
                "content_type": self._content_type_for_repr,
                "url": self.url,
            }
        )


class HttpResponseRedirect(HttpResponseRedirectBase):
    status_code = 302


class HttpResponsePermanentRedirect(HttpResponseRedirectBase):
    status_code = 301


class HttpResponseNotModified(HttpResponse):
    status_code = 304

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        del self["content-type"]

    @HttpResponse.content.setter
    def content(self, value):
        if value:
            raise AttributeError(
                "You cannot set content to a 304 (Not Modified) response"
            )
        self._container = []


class HttpResponseBadRequest(HttpResponse):
    status_code = 400


class HttpResponseNotFound(HttpResponse):
    status_code = 404


class HttpResponseForbidden(HttpResponse):
    status_code = 403


class HttpResponseNotAllowed(HttpResponse):
    status_code = 405

    def __init__(self, permitted_methods, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self["Allow"] = ", ".join(permitted_methods)

    def __repr__(self):
        return "<%(cls)s [%(methods)s] status_code=%(status_code)d%(content_type)s>" % {
            "cls": self.__class__.__name__,
            "status_code": self.status_code,
            "content_type": self._content_type_for_repr,
            "methods": self["Allow"],
        }


class HttpResponseGone(HttpResponse):
    status_code = 410


class HttpResponseServerError(HttpResponse):
    status_code = 500


class Http404(Exception):
    pass


class JsonResponse(HttpResponse):
    """
    An HTTP response class that consumes data to be serialized to JSON.

    :param data: Data to be dumped into json. By default only ``dict`` objects
      are allowed to be passed due to a security flaw before ECMAScript 5. See
      the ``safe`` parameter for more information.
    :param encoder: Should be a json encoder class. Defaults to
      ``django.core.serializers.json.DjangoJSONEncoder``.
    :param safe: Controls if only ``dict`` objects may be serialized. Defaults
      to ``True``.
    :param json_dumps_params: A dictionary of kwargs passed to json.dumps().
    """

    def __init__(
        self,
        data,
        encoder=DjangoJSONEncoder,
        safe=True,
        json_dumps_params=None,
        **kwargs,
    ):
        """
        Initialize a JSON response object, handling data serialization and encoding.

        :param data: Data to be serialized into a JSON response
        :param encoder: Custom JSON encoder class, defaults to DjangoJSONEncoder
        :param safe: Flag to ensure data is a dictionary for safe serialization, defaults to True
        :param json_dumps_params: Additional parameters for json.dumps, defaults to {}
        :param **kwargs: Additional keyword arguments for the response object
        :raises TypeError: If safe is True and data is not a dictionary
        """
        if safe and not isinstance(data, dict):
            raise TypeError(
                "In order to allow non-dict objects to be serialized set the "
                "safe parameter to False."
            )
        if json_dumps_params is None:
            json_dumps_params = {}
        kwargs.setdefault("content_type", "application/json")
        data = json.dumps(data, cls=encoder, **json_dumps_params)
        super().__init__(content=data, **kwargs)
