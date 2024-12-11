import copy
import json
import os
import pickle
import unittest
import uuid

from django.core.exceptions import DisallowedRedirect
from django.core.serializers.json import DjangoJSONEncoder
from django.core.signals import request_finished
from django.db import close_old_connections
from django.http import (
    BadHeaderError,
    HttpResponse,
    HttpResponseNotAllowed,
    HttpResponseNotModified,
    HttpResponsePermanentRedirect,
    HttpResponseRedirect,
    JsonResponse,
    QueryDict,
    SimpleCookie,
    StreamingHttpResponse,
    parse_cookie,
)
from django.test import SimpleTestCase
from django.utils.functional import lazystr


class QueryDictTests(SimpleTestCase):
    def test_create_with_no_args(self):
        self.assertEqual(QueryDict(), QueryDict(""))

    def test_missing_key(self):
        """
        Test that attempting to retrieve a missing key from a QueryDict raises a KeyError. 

        This test case verifies that the QueryDict implementation correctly handles the absence of a key, ensuring that it does not silently fail or return an incorrect value, but instead raises an exception as expected.
        """
        q = QueryDict()
        with self.assertRaises(KeyError):
            q.__getitem__("foo")

    def test_immutability(self):
        q = QueryDict()
        with self.assertRaises(AttributeError):
            q.__setitem__("something", "bar")
        with self.assertRaises(AttributeError):
            q.setlist("foo", ["bar"])
        with self.assertRaises(AttributeError):
            q.appendlist("foo", ["bar"])
        with self.assertRaises(AttributeError):
            q.update({"foo": "bar"})
        with self.assertRaises(AttributeError):
            q.pop("foo")
        with self.assertRaises(AttributeError):
            q.popitem()
        with self.assertRaises(AttributeError):
            q.clear()

    def test_immutable_get_with_default(self):
        """
        Tests the retrieval of a value from an empty QueryDict with a default value.

        This test case ensures that when attempting to retrieve a key that does not exist in the QueryDict, 
        the function returns the specified default value instead of raising an exception.

        :returns: None, but verifies that the get method behaves correctly when the key is missing
        """
        q = QueryDict()
        self.assertEqual(q.get("foo", "default"), "default")

    def test_immutable_basic_operations(self):
        q = QueryDict()
        self.assertEqual(q.getlist("foo"), [])
        self.assertNotIn("foo", q)
        self.assertEqual(list(q), [])
        self.assertEqual(list(q.items()), [])
        self.assertEqual(list(q.lists()), [])
        self.assertEqual(list(q.keys()), [])
        self.assertEqual(list(q.values()), [])
        self.assertEqual(len(q), 0)
        self.assertEqual(q.urlencode(), "")

    def test_single_key_value(self):
        """Test QueryDict with one key/value pair"""

        q = QueryDict("foo=bar")
        self.assertEqual(q["foo"], "bar")
        with self.assertRaises(KeyError):
            q.__getitem__("bar")
        with self.assertRaises(AttributeError):
            q.__setitem__("something", "bar")

        self.assertEqual(q.get("foo", "default"), "bar")
        self.assertEqual(q.get("bar", "default"), "default")
        self.assertEqual(q.getlist("foo"), ["bar"])
        self.assertEqual(q.getlist("bar"), [])

        with self.assertRaises(AttributeError):
            q.setlist("foo", ["bar"])
        with self.assertRaises(AttributeError):
            q.appendlist("foo", ["bar"])

        self.assertIn("foo", q)
        self.assertNotIn("bar", q)

        self.assertEqual(list(q), ["foo"])
        self.assertEqual(list(q.items()), [("foo", "bar")])
        self.assertEqual(list(q.lists()), [("foo", ["bar"])])
        self.assertEqual(list(q.keys()), ["foo"])
        self.assertEqual(list(q.values()), ["bar"])
        self.assertEqual(len(q), 1)

        with self.assertRaises(AttributeError):
            q.update({"foo": "bar"})
        with self.assertRaises(AttributeError):
            q.pop("foo")
        with self.assertRaises(AttributeError):
            q.popitem()
        with self.assertRaises(AttributeError):
            q.clear()
        with self.assertRaises(AttributeError):
            q.setdefault("foo", "bar")

        self.assertEqual(q.urlencode(), "foo=bar")

    def test_urlencode(self):
        """

        Tests the urlencode method of a QueryDict object.

        This test case verifies that the urlencode method correctly encodes special characters in query parameters,
        such as ampersands (&) and non-ASCII characters. It also checks that the safe parameter can be used to
        prevent certain characters from being encoded, such as forward slashes (/).

        The test covers different scenarios, including query parameters with ampersands, non-ASCII characters,
        and forward slashes, ensuring that the urlencode method produces the expected output in each case.

        """
        q = QueryDict(mutable=True)
        q["next"] = "/a&b/"
        self.assertEqual(q.urlencode(), "next=%2Fa%26b%2F")
        self.assertEqual(q.urlencode(safe="/"), "next=/a%26b/")
        q = QueryDict(mutable=True)
        q["next"] = "/t\xebst&key/"
        self.assertEqual(q.urlencode(), "next=%2Ft%C3%ABst%26key%2F")
        self.assertEqual(q.urlencode(safe="/"), "next=/t%C3%ABst%26key/")

    def test_urlencode_int(self):
        # Normally QueryDict doesn't contain non-string values but lazily
        # written tests may make that mistake.
        """
        Tests that the urlencode method of a QueryDict instance correctly handles integer values.

        This test case verifies that when an integer value is assigned to a key in a mutable QueryDict and then urlencoded, the resulting string is correctly formatted as 'key=value'. 

        The expected behaviour is that the integer value is converted to a string and appended to the key with an equals sign, without any additional encoding or escaping. 

        This functionality is essential for ensuring that QueryDict instances can be used to construct and manipulate URL query strings that contain integer parameters.
        """
        q = QueryDict(mutable=True)
        q["a"] = 1
        self.assertEqual(q.urlencode(), "a=1")

    def test_mutable_copy(self):
        """A copy of a QueryDict is mutable."""
        q = QueryDict().copy()
        with self.assertRaises(KeyError):
            q.__getitem__("foo")
        q["name"] = "john"
        self.assertEqual(q["name"], "john")

    def test_mutable_delete(self):
        """

        Tests that deleting an item from a mutable QueryDict instance correctly removes the item.

        This test case verifies the behavior of the del statement on a mutable QueryDict, 
        ensuring that the specified key is successfully removed from the dictionary.

        """
        q = QueryDict(mutable=True)
        q["name"] = "john"
        del q["name"]
        self.assertNotIn("name", q)

    def test_basic_mutable_operations(self):
        q = QueryDict(mutable=True)
        q["name"] = "john"
        self.assertEqual(q.get("foo", "default"), "default")
        self.assertEqual(q.get("name", "default"), "john")
        self.assertEqual(q.getlist("name"), ["john"])
        self.assertEqual(q.getlist("foo"), [])

        q.setlist("foo", ["bar", "baz"])
        self.assertEqual(q.get("foo", "default"), "baz")
        self.assertEqual(q.getlist("foo"), ["bar", "baz"])

        q.appendlist("foo", "another")
        self.assertEqual(q.getlist("foo"), ["bar", "baz", "another"])
        self.assertEqual(q["foo"], "another")
        self.assertIn("foo", q)

        self.assertCountEqual(q, ["foo", "name"])
        self.assertCountEqual(q.items(), [("foo", "another"), ("name", "john")])
        self.assertCountEqual(
            q.lists(), [("foo", ["bar", "baz", "another"]), ("name", ["john"])]
        )
        self.assertCountEqual(q.keys(), ["foo", "name"])
        self.assertCountEqual(q.values(), ["another", "john"])

        q.update({"foo": "hello"})
        self.assertEqual(q["foo"], "hello")
        self.assertEqual(q.get("foo", "not available"), "hello")
        self.assertEqual(q.getlist("foo"), ["bar", "baz", "another", "hello"])
        self.assertEqual(q.pop("foo"), ["bar", "baz", "another", "hello"])
        self.assertEqual(q.pop("foo", "not there"), "not there")
        self.assertEqual(q.get("foo", "not there"), "not there")
        self.assertEqual(q.setdefault("foo", "bar"), "bar")
        self.assertEqual(q["foo"], "bar")
        self.assertEqual(q.getlist("foo"), ["bar"])
        self.assertIn(q.urlencode(), ["foo=bar&name=john", "name=john&foo=bar"])

        q.clear()
        self.assertEqual(len(q), 0)

    def test_multiple_keys(self):
        """Test QueryDict with two key/value pairs with same keys."""

        q = QueryDict("vote=yes&vote=no")

        self.assertEqual(q["vote"], "no")
        with self.assertRaises(AttributeError):
            q.__setitem__("something", "bar")

        self.assertEqual(q.get("vote", "default"), "no")
        self.assertEqual(q.get("foo", "default"), "default")
        self.assertEqual(q.getlist("vote"), ["yes", "no"])
        self.assertEqual(q.getlist("foo"), [])

        with self.assertRaises(AttributeError):
            q.setlist("foo", ["bar", "baz"])
        with self.assertRaises(AttributeError):
            q.setlist("foo", ["bar", "baz"])
        with self.assertRaises(AttributeError):
            q.appendlist("foo", ["bar"])

        self.assertIn("vote", q)
        self.assertNotIn("foo", q)
        self.assertEqual(list(q), ["vote"])
        self.assertEqual(list(q.items()), [("vote", "no")])
        self.assertEqual(list(q.lists()), [("vote", ["yes", "no"])])
        self.assertEqual(list(q.keys()), ["vote"])
        self.assertEqual(list(q.values()), ["no"])
        self.assertEqual(len(q), 1)

        with self.assertRaises(AttributeError):
            q.update({"foo": "bar"})
        with self.assertRaises(AttributeError):
            q.pop("foo")
        with self.assertRaises(AttributeError):
            q.popitem()
        with self.assertRaises(AttributeError):
            q.clear()
        with self.assertRaises(AttributeError):
            q.setdefault("foo", "bar")
        with self.assertRaises(AttributeError):
            q.__delitem__("vote")

    def test_pickle(self):
        q = QueryDict()
        q1 = pickle.loads(pickle.dumps(q, 2))
        self.assertEqual(q, q1)
        q = QueryDict("a=b&c=d")
        q1 = pickle.loads(pickle.dumps(q, 2))
        self.assertEqual(q, q1)
        q = QueryDict("a=b&c=d&a=1")
        q1 = pickle.loads(pickle.dumps(q, 2))
        self.assertEqual(q, q1)

    def test_update_from_querydict(self):
        """Regression test for #8278: QueryDict.update(QueryDict)"""
        x = QueryDict("a=1&a=2", mutable=True)
        y = QueryDict("a=3&a=4")
        x.update(y)
        self.assertEqual(x.getlist("a"), ["1", "2", "3", "4"])

    def test_non_default_encoding(self):
        """#13572 - QueryDict with a non-default encoding"""
        q = QueryDict("cur=%A4", encoding="iso-8859-15")
        self.assertEqual(q.encoding, "iso-8859-15")
        self.assertEqual(list(q.items()), [("cur", "€")])
        self.assertEqual(q.urlencode(), "cur=%A4")
        q = q.copy()
        self.assertEqual(q.encoding, "iso-8859-15")
        self.assertEqual(list(q.items()), [("cur", "€")])
        self.assertEqual(q.urlencode(), "cur=%A4")
        self.assertEqual(copy.copy(q).encoding, "iso-8859-15")
        self.assertEqual(copy.deepcopy(q).encoding, "iso-8859-15")

    def test_querydict_fromkeys(self):
        self.assertEqual(
            QueryDict.fromkeys(["key1", "key2", "key3"]), QueryDict("key1&key2&key3")
        )

    def test_fromkeys_with_nonempty_value(self):
        self.assertEqual(
            QueryDict.fromkeys(["key1", "key2", "key3"], value="val"),
            QueryDict("key1=val&key2=val&key3=val"),
        )

    def test_fromkeys_is_immutable_by_default(self):
        # Match behavior of __init__() which is also immutable by default.
        """
        Tests that a QueryDict instance created using the fromkeys method is immutable by default.

        Verifies that attempting to add a new key-value pair to the QueryDict instance raises an AttributeError with a message indicating that the instance is immutable.

        Ensures that the fromkeys method returns a QueryDict instance that cannot be modified, thereby maintaining data integrity and preventing unintended changes.
        """
        q = QueryDict.fromkeys(["key1", "key2", "key3"])
        with self.assertRaisesMessage(
            AttributeError, "This QueryDict instance is immutable"
        ):
            q["key4"] = "nope"

    def test_fromkeys_mutable_override(self):
        q = QueryDict.fromkeys(["key1", "key2", "key3"], mutable=True)
        q["key4"] = "yep"
        self.assertEqual(q, QueryDict("key1&key2&key3&key4=yep"))

    def test_duplicates_in_fromkeys_iterable(self):
        self.assertEqual(QueryDict.fromkeys("xyzzy"), QueryDict("x&y&z&z&y"))

    def test_fromkeys_with_nondefault_encoding(self):
        key_utf16 = b"\xff\xfe\x8e\x02\xdd\x01\x9e\x02"
        value_utf16 = b"\xff\xfe\xdd\x01n\x00l\x00P\x02\x8c\x02"
        q = QueryDict.fromkeys([key_utf16], value=value_utf16, encoding="utf-16")
        expected = QueryDict("", mutable=True)
        expected["ʎǝʞ"] = "ǝnlɐʌ"
        self.assertEqual(q, expected)

    def test_fromkeys_empty_iterable(self):
        self.assertEqual(QueryDict.fromkeys([]), QueryDict(""))

    def test_fromkeys_noniterable(self):
        with self.assertRaises(TypeError):
            QueryDict.fromkeys(0)


class HttpResponseTests(SimpleTestCase):
    def test_headers_type(self):
        """
        Tests the functionality of HttpResponse headers.

        Verifies that headers can be set and retrieved with both string and bytes values.
        Ensures that header values are properly encoded and decoded, and that the 
        serialize_headers method returns the expected output.

        Also tests that deleting the 'Content-Type' header does not affect other headers,
        and that keys and values are properly handled regardless of whether they are set
        with string or bytes.

        Checks for correct error handling when attempting to set headers with non-ASCII
        characters, ensuring that a UnicodeError is raised in such cases.
        """
        r = HttpResponse()

        # ASCII strings or bytes values are converted to strings.
        r.headers["key"] = "test"
        self.assertEqual(r.headers["key"], "test")
        r.headers["key"] = b"test"
        self.assertEqual(r.headers["key"], "test")
        self.assertIn(b"test", r.serialize_headers())

        # Non-ASCII values are serialized to Latin-1.
        r.headers["key"] = "café"
        self.assertIn("café".encode("latin-1"), r.serialize_headers())

        # Other Unicode values are MIME-encoded (there's no way to pass them as
        # bytes).
        r.headers["key"] = "†"
        self.assertEqual(r.headers["key"], "=?utf-8?b?4oCg?=")
        self.assertIn(b"=?utf-8?b?4oCg?=", r.serialize_headers())

        # The response also converts string or bytes keys to strings, but requires
        # them to contain ASCII
        r = HttpResponse()
        del r.headers["Content-Type"]
        r.headers["foo"] = "bar"
        headers = list(r.headers.items())
        self.assertEqual(len(headers), 1)
        self.assertEqual(headers[0], ("foo", "bar"))

        r = HttpResponse()
        del r.headers["Content-Type"]
        r.headers[b"foo"] = "bar"
        headers = list(r.headers.items())
        self.assertEqual(len(headers), 1)
        self.assertEqual(headers[0], ("foo", "bar"))
        self.assertIsInstance(headers[0][0], str)

        r = HttpResponse()
        with self.assertRaises(UnicodeError):
            r.headers.__setitem__("føø", "bar")
        with self.assertRaises(UnicodeError):
            r.headers.__setitem__("føø".encode(), "bar")

    def test_long_line(self):
        # Bug #20889: long lines trigger newlines to be added to headers
        # (which is not allowed due to bug #10188)
        h = HttpResponse()
        f = b"zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz a\xcc\x88"
        f = f.decode("utf-8")
        h.headers["Content-Disposition"] = 'attachment; filename="%s"' % f
        # This one is triggering https://bugs.python.org/issue20747, that is Python
        # will itself insert a newline in the header
        h.headers["Content-Disposition"] = (
            'attachment; filename="EdelRot_Blu\u0308te (3)-0.JPG"'
        )

    def test_newlines_in_headers(self):
        # Bug #10188: Do not allow newlines in headers (CR or LF)
        """

        Tests that headers in HTTP responses cannot contain newline characters.

        Checks that attempting to set a header key containing a carriage return ('\r') or
        newline ('\n') raises a BadHeaderError. This ensures that HTTP responses are
        properly formatted and do not contain potential security vulnerabilities.

        """
        r = HttpResponse()
        with self.assertRaises(BadHeaderError):
            r.headers.__setitem__("test\rstr", "test")
        with self.assertRaises(BadHeaderError):
            r.headers.__setitem__("test\nstr", "test")

    def test_encoded_with_newlines_in_headers(self):
        """
        Keys & values which throw a UnicodeError when encoding/decoding should
        still be checked for newlines and re-raised as a BadHeaderError.
        These specifically would still throw BadHeaderError after decoding
        successfully, because the newlines are sandwiched in the middle of the
        string and email.Header leaves those as they are.
        """
        r = HttpResponse()
        pairs = (
            ("†\nother", "test"),
            ("test", "†\nother"),
            (b"\xe2\x80\xa0\nother", "test"),
            ("test", b"\xe2\x80\xa0\nother"),
        )
        msg = "Header values can't contain newlines"
        for key, value in pairs:
            with self.subTest(key=key, value=value):
                with self.assertRaisesMessage(BadHeaderError, msg):
                    r[key] = value

    def test_dict_behavior(self):
        """
        Test for bug #14020: Make HttpResponse.get work like dict.get
        """
        r = HttpResponse()
        self.assertIsNone(r.get("test"))

    def test_non_string_content(self):
        # Bug 16494: HttpResponse should behave consistently with non-strings
        """
        Tests that non-string content in an HttpResponse is correctly converted to bytes.

        This test verifies that when a non-string value (e.g. an integer) is passed to 
        the HttpResponse constructor or assigned to its content attribute, it is 
        automatically converted to a bytes object. This ensures that the response 
        content can be properly handled and transmitted.

        The test covers two scenarios: passing non-string content to the HttpResponse 
        constructor and assigning it to the content attribute after the response object 
        has been created. In both cases, the test checks that the resulting content is 
        the bytes representation of the original non-string value.
        """
        r = HttpResponse(12345)
        self.assertEqual(r.content, b"12345")

        # test content via property
        r = HttpResponse()
        r.content = 12345
        self.assertEqual(r.content, b"12345")

    def test_memoryview_content(self):
        """
        Tests that the content of an HttpResponse object is correctly extracted from a memoryview object.

            Verifies that when a memoryview object is passed to the HttpResponse constructor,
            the content of the response is set correctly, without copying the underlying data.

            This test ensures that the HttpResponse class handles memoryview objects as expected,
            allowing for efficient and memory-friendly responses in certain scenarios.
        """
        r = HttpResponse(memoryview(b"memoryview"))
        self.assertEqual(r.content, b"memoryview")

    def test_iter_content(self):
        """
        Sets the `content` attribute of an `HttpResponse` object to a list or an iterable and tests its behavior, ensuring that the resulting HTTP response content is correctly concatenated and encoded. The test covers various scenarios, including setting the `content` attribute directly, using iterables, and writing to the response object after initialization. It also verifies that the response object's content is correctly returned as bytes and can be joined multiple times without changing its value.
        """
        r = HttpResponse(["abc", "def", "ghi"])
        self.assertEqual(r.content, b"abcdefghi")

        # test iter content via property
        r = HttpResponse()
        r.content = ["idan", "alex", "jacob"]
        self.assertEqual(r.content, b"idanalexjacob")

        r = HttpResponse()
        r.content = [1, 2, 3]
        self.assertEqual(r.content, b"123")

        # test odd inputs
        r = HttpResponse()
        r.content = ["1", "2", 3, "\u079e"]
        # '\xde\x9e' == unichr(1950).encode()
        self.assertEqual(r.content, b"123\xde\x9e")

        # .content can safely be accessed multiple times.
        r = HttpResponse(iter(["hello", "world"]))
        self.assertEqual(r.content, r.content)
        self.assertEqual(r.content, b"helloworld")
        # __iter__ can safely be called multiple times (#20187).
        self.assertEqual(b"".join(r), b"helloworld")
        self.assertEqual(b"".join(r), b"helloworld")
        # Accessing .content still works.
        self.assertEqual(r.content, b"helloworld")

        # Accessing .content also works if the response was iterated first.
        r = HttpResponse(iter(["hello", "world"]))
        self.assertEqual(b"".join(r), b"helloworld")
        self.assertEqual(r.content, b"helloworld")

        # Additional content can be written to the response.
        r = HttpResponse(iter(["hello", "world"]))
        self.assertEqual(r.content, b"helloworld")
        r.write("!")
        self.assertEqual(r.content, b"helloworld!")

    def test_iterator_isnt_rewound(self):
        # Regression test for #13222
        r = HttpResponse("abc")
        i = iter(r)
        self.assertEqual(list(i), [b"abc"])
        self.assertEqual(list(i), [])

    def test_lazy_content(self):
        """
        Checks that lazy content is properly evaluated and included in an HTTP response. 

        Verifies that the `HttpResponse` object correctly handles lazy strings, 
        converting them to bytes and including them in the response content.
        """
        r = HttpResponse(lazystr("helloworld"))
        self.assertEqual(r.content, b"helloworld")

    def test_file_interface(self):
        """

        Tests the interface of an HttpResponse object, ensuring it behaves correctly 
        when writing and reading data. This includes checks for the object's position 
        after writing different types of data, as well as its handling of headers and 
        content encoding. The tests cover various scenarios, including writing bytes 
        and strings, to verify that the HttpResponse object correctly tracks its 
        content and position. 

        The tests verify the following functionality:
        - Writing bytes and strings to the response object
        - Updating the position after writing data
        - Handling of headers and content encoding
        - Reading and verifying the content of the response object

        """
        r = HttpResponse()
        r.write(b"hello")
        self.assertEqual(r.tell(), 5)
        r.write("привет")
        self.assertEqual(r.tell(), 17)

        r = HttpResponse(["abc"])
        r.write("def")
        self.assertEqual(r.tell(), 6)
        self.assertEqual(r.content, b"abcdef")

        # with Content-Encoding header
        r = HttpResponse()
        r.headers["Content-Encoding"] = "winning"
        r.write(b"abc")
        r.write(b"def")
        self.assertEqual(r.content, b"abcdef")

    def test_stream_interface(self):
        """
        Tests the functionality of the stream interface for HttpResponse objects.

        Ensures that the HttpResponse object can be used as a file-like object, 
        allowing for writing and reading of content. Verifies that the 
        getvalue() method returns the correct bytes, the object is initially 
        writable, and the writelines() method correctly appends content to the 
        response. The content is then validated to ensure it matches the 
        expected output.
        """
        r = HttpResponse("asdf")
        self.assertEqual(r.getvalue(), b"asdf")

        r = HttpResponse()
        self.assertIs(r.writable(), True)
        r.writelines(["foo\n", "bar\n", "baz\n"])
        self.assertEqual(r.content, b"foo\nbar\nbaz\n")

    def test_unsafe_redirect(self):
        bad_urls = [
            'data:text/html,<script>window.alert("xss")</script>',
            "mailto:test@example.com",
            "file:///etc/passwd",
        ]
        for url in bad_urls:
            with self.assertRaises(DisallowedRedirect):
                HttpResponseRedirect(url)
            with self.assertRaises(DisallowedRedirect):
                HttpResponsePermanentRedirect(url)

    def test_header_deletion(self):
        r = HttpResponse("hello")
        r.headers["X-Foo"] = "foo"
        del r.headers["X-Foo"]
        self.assertNotIn("X-Foo", r.headers)
        # del doesn't raise a KeyError on nonexistent headers.
        del r.headers["X-Foo"]

    def test_instantiate_with_headers(self):
        """
        Tests instantiation of HttpResponse object with custom headers.

        Verifies that the HttpResponse object correctly stores and retrieves custom headers,
        regardless of case sensitivity, ensuring that header keys are treated in a case-insensitive manner.

        This test case checks that a custom 'X-Foo' header is properly set and retrieved,
        demonstrating that the HttpResponse object handles headers as expected.
        """
        r = HttpResponse("hello", headers={"X-Foo": "foo"})
        self.assertEqual(r.headers["X-Foo"], "foo")
        self.assertEqual(r.headers["x-foo"], "foo")

    def test_content_type(self):
        r = HttpResponse("hello", content_type="application/json")
        self.assertEqual(r.headers["Content-Type"], "application/json")

    def test_content_type_headers(self):
        r = HttpResponse("hello", headers={"Content-Type": "application/json"})
        self.assertEqual(r.headers["Content-Type"], "application/json")

    def test_content_type_mutually_exclusive(self):
        msg = (
            "'headers' must not contain 'Content-Type' when the "
            "'content_type' parameter is provided."
        )
        with self.assertRaisesMessage(ValueError, msg):
            HttpResponse(
                "hello",
                content_type="application/json",
                headers={"Content-Type": "text/csv"},
            )


class HttpResponseSubclassesTests(SimpleTestCase):
    def test_redirect(self):
        """
        Tests the functionality of HTTP redirects.

        This test case verifies that an HttpResponseRedirect object correctly sets the 
        status code to 302, and that the Location header matches the provided URL. 
        Additionally, it checks that any provided content is included in the response, 
        even when the status code indicates a redirect. The test covers the usage of 
        HttpResponseRedirect with and without custom content, ensuring that it behaves 
        as expected in both scenarios.
        """
        response = HttpResponseRedirect("/redirected/")
        self.assertEqual(response.status_code, 302)
        # Standard HttpResponse init args can be used
        response = HttpResponseRedirect(
            "/redirected/",
            content="The resource has temporarily moved",
        )
        self.assertContains(
            response, "The resource has temporarily moved", status_code=302
        )
        self.assertEqual(response.url, response.headers["Location"])

    def test_redirect_lazy(self):
        """Make sure HttpResponseRedirect works with lazy strings."""
        r = HttpResponseRedirect(lazystr("/redirected/"))
        self.assertEqual(r.url, "/redirected/")

    def test_redirect_repr(self):
        response = HttpResponseRedirect("/redirected/")
        expected = (
            '<HttpResponseRedirect status_code=302, "text/html; charset=utf-8", '
            'url="/redirected/">'
        )
        self.assertEqual(repr(response), expected)

    def test_invalid_redirect_repr(self):
        """
        If HttpResponseRedirect raises DisallowedRedirect, its __repr__()
        should work (in the debug view, for example).
        """
        response = HttpResponseRedirect.__new__(HttpResponseRedirect)
        with self.assertRaisesMessage(
            DisallowedRedirect, "Unsafe redirect to URL with protocol 'ssh'"
        ):
            HttpResponseRedirect.__init__(response, "ssh://foo")
        expected = (
            '<HttpResponseRedirect status_code=302, "text/html; charset=utf-8", '
            'url="ssh://foo">'
        )
        self.assertEqual(repr(response), expected)

    def test_not_modified(self):
        response = HttpResponseNotModified()
        self.assertEqual(response.status_code, 304)
        # 304 responses should not have content/content-type
        with self.assertRaises(AttributeError):
            response.content = "Hello dear"
        self.assertNotIn("content-type", response)

    def test_not_modified_repr(self):
        """
        Tests that the representation of an HttpResponseNotModified object is correctly formatted.

        Checks that the string representation of an HttpResponseNotModified instance matches the expected format,
        including the status code (304) in the output.

        This ensures that the repr() method provides a useful and informative string representation of the object,
        which can be helpful for debugging purposes.
        """
        response = HttpResponseNotModified()
        self.assertEqual(repr(response), "<HttpResponseNotModified status_code=304>")

    def test_not_allowed(self):
        """
        Verifies the correct behavior of HttpResponseNotAllowed.

        This test checks that the HttpResponseNotAllowed response object returns the 
        correct status code (405 Method Not Allowed) and allows customization of the 
        response content. It also confirms that the response contains the specified 
        content when the 'content' parameter is provided.

        The test covers two scenarios: 
        1. Verifying the default response when only allowed methods are provided.
        2. Verifying the response when custom content is provided along with the 
        allowed methods.

        Parameters are not directly tested in this function, but rather the 
        HttpResponseNotAllowed object is exercised to ensure it behaves as expected 
        in different situations.
        """
        response = HttpResponseNotAllowed(["GET"])
        self.assertEqual(response.status_code, 405)
        # Standard HttpResponse init args can be used
        response = HttpResponseNotAllowed(
            ["GET"], content="Only the GET method is allowed"
        )
        self.assertContains(response, "Only the GET method is allowed", status_code=405)

    def test_not_allowed_repr(self):
        """
        Tests the string representation of an HttpResponseNotAllowed object, verifying it correctly displays the list of allowed HTTP methods and the status code.
        """
        response = HttpResponseNotAllowed(["GET", "OPTIONS"], content_type="text/plain")
        expected = (
            '<HttpResponseNotAllowed [GET, OPTIONS] status_code=405, "text/plain">'
        )
        self.assertEqual(repr(response), expected)

    def test_not_allowed_repr_no_content_type(self):
        """

        Tests that HttpResponseNotAllowed objects return the expected string representation 
        when the 'Content-Type' header is missing.

        The expected string representation includes the allowed HTTP methods and the 
        status code of the response, regardless of the absence of the 'Content-Type' header.

        """
        response = HttpResponseNotAllowed(("GET", "POST"))
        del response.headers["Content-Type"]
        self.assertEqual(
            repr(response), "<HttpResponseNotAllowed [GET, POST] status_code=405>"
        )


class JsonResponseTests(SimpleTestCase):
    def test_json_response_non_ascii(self):
        """

        Tests that a JsonResponse object can correctly handle non-ASCII characters.

        Verifies that when a dictionary containing non-ASCII characters is passed to JsonResponse,
        the resulting JSON response contains the correct data and can be decoded without errors.

        """
        data = {"key": "łóżko"}
        response = JsonResponse(data)
        self.assertEqual(json.loads(response.content.decode()), data)

    def test_json_response_raises_type_error_with_default_setting(self):
        with self.assertRaisesMessage(
            TypeError,
            "In order to allow non-dict objects to be serialized set the "
            "safe parameter to False",
        ):
            JsonResponse([1, 2, 3])

    def test_json_response_text(self):
        """

        Tests that a JsonResponse with a simple text payload is correctly encoded as JSON.
        Verifies that the response content can be successfully decoded and matches the original text.

        """
        response = JsonResponse("foobar", safe=False)
        self.assertEqual(json.loads(response.content.decode()), "foobar")

    def test_json_response_list(self):
        """

        Verifies that a JsonResponse object correctly returns a list of JSON data.

        This test checks that a JsonResponse object initialized with a list of values
        is properly serialized and can be parsed back into the original list.
        The test ensures that the 'safe' parameter is set to False to allow serialization
        of non-dict objects, and then verifies that the resulting JSON content matches
        the original input list.

        """
        response = JsonResponse(["foo", "bar"], safe=False)
        self.assertEqual(json.loads(response.content.decode()), ["foo", "bar"])

    def test_json_response_uuid(self):
        """
        Tests the JSON response for a UUID object.

        Verifies that a UUID object can be correctly serialized to a JSON response.
        The test checks that the JSON response content matches the original UUID string.
        This ensures that the JsonResponse can handle UUID objects without errors and 
        produces the expected output in the JSON format.
        """
        u = uuid.uuid4()
        response = JsonResponse(u, safe=False)
        self.assertEqual(json.loads(response.content.decode()), str(u))

    def test_json_response_custom_encoder(self):
        """
        Tests if a custom JSON encoder can be used with the JsonResponse class.

         The test verifies that the custom encoder's encode method is called when creating a JsonResponse object,
         allowing for custom JSON serialization. In this case, the encoder returns a hardcoded JSON payload 
         regardless of the input data, and the test checks that the response content matches the expected JSON data.
        """
        class CustomDjangoJSONEncoder(DjangoJSONEncoder):
            def encode(self, o):
                return json.dumps({"foo": "bar"})

        response = JsonResponse({}, encoder=CustomDjangoJSONEncoder)
        self.assertEqual(json.loads(response.content.decode()), {"foo": "bar"})

    def test_json_response_passing_arguments_to_json_dumps(self):
        """
        Tests that a JsonResponse successfully passes arguments to json.dumps.

        This test case verifies that the JsonResponse object is able to serialize its data
        into a JSON string, using custom parameters passed to the json.dumps function.
        The test checks that the resulting JSON string is formatted as expected, with the
        specified indentation.
        """
        response = JsonResponse({"foo": "bar"}, json_dumps_params={"indent": 2})
        self.assertEqual(response.content.decode(), '{\n  "foo": "bar"\n}')


class StreamingHttpResponseTests(SimpleTestCase):
    def test_streaming_response(self):
        r = StreamingHttpResponse(iter(["hello", "world"]))

        # iterating over the response itself yields bytestring chunks.
        chunks = list(r)
        self.assertEqual(chunks, [b"hello", b"world"])
        for chunk in chunks:
            self.assertIsInstance(chunk, bytes)

        # and the response can only be iterated once.
        self.assertEqual(list(r), [])

        # even when a sequence that can be iterated many times, like a list,
        # is given as content.
        r = StreamingHttpResponse(["abc", "def"])
        self.assertEqual(list(r), [b"abc", b"def"])
        self.assertEqual(list(r), [])

        # iterating over strings still yields bytestring chunks.
        r.streaming_content = iter(["hello", "café"])
        chunks = list(r)
        # '\xc3\xa9' == unichr(233).encode()
        self.assertEqual(chunks, [b"hello", b"caf\xc3\xa9"])
        for chunk in chunks:
            self.assertIsInstance(chunk, bytes)

        # streaming responses don't have a `content` attribute.
        self.assertFalse(hasattr(r, "content"))

        # and you can't accidentally assign to a `content` attribute.
        with self.assertRaises(AttributeError):
            r.content = "xyz"

        # but they do have a `streaming_content` attribute.
        self.assertTrue(hasattr(r, "streaming_content"))

        # that exists so we can check if a response is streaming, and wrap or
        # replace the content iterator.
        r.streaming_content = iter(["abc", "def"])
        r.streaming_content = (chunk.upper() for chunk in r.streaming_content)
        self.assertEqual(list(r), [b"ABC", b"DEF"])

        # coercing a streaming response to bytes doesn't return a complete HTTP
        # message like a regular response does. it only gives us the headers.
        r = StreamingHttpResponse(iter(["hello", "world"]))
        self.assertEqual(bytes(r), b"Content-Type: text/html; charset=utf-8")

        # and this won't consume its content.
        self.assertEqual(list(r), [b"hello", b"world"])

        # additional content cannot be written to the response.
        r = StreamingHttpResponse(iter(["hello", "world"]))
        with self.assertRaises(Exception):
            r.write("!")

        # and we can't tell the current position.
        with self.assertRaises(Exception):
            r.tell()

        r = StreamingHttpResponse(iter(["hello", "world"]))
        self.assertEqual(r.getvalue(), b"helloworld")

    def test_repr(self):
        """
        Checks the string representation of a StreamingHttpResponse instance.

        Ensures that the repr() function returns a human-readable string with the
        status code and content type of the response, confirming that it matches the
        expected format.

        This test is crucial for verifying the correctness of the object's string
        representation, which is particularly useful for debugging purposes.
        """
        r = StreamingHttpResponse(iter(["hello", "café"]))
        self.assertEqual(
            repr(r),
            '<StreamingHttpResponse status_code=200, "text/html; charset=utf-8">',
        )

    async def test_async_streaming_response(self):
        """
        Tests asynchronous streaming response functionality.

        Verifies that an asynchronous iterable can be successfully used to generate a 
        streaming HTTP response, with chunks of data yielded by the iterable being 
        properly received and processed.

        The test setup involves creating a StreamingHttpResponse object with an 
        asynchronous iterator that yields a sequence of bytes, and then consuming 
        the response as an asynchronous iterator to verify the expected output.

        """
        async def async_iter():
            """
            Asynchronously generates an iterator that yields byte strings.

            This asynchronous iterator produces a sequence of byte strings, allowing for 
            efficient handling of data in an asynchronous context. The yielded values can 
            be iterated over using an async for loop, making it suitable for use cases where 
            data is generated or retrieved asynchronously.

            Yields:
                bytes: The next byte string in the sequence.
            """
            yield b"hello"
            yield b"world"

        r = StreamingHttpResponse(async_iter())

        chunks = []
        async for chunk in r:
            chunks.append(chunk)
        self.assertEqual(chunks, [b"hello", b"world"])

    def test_async_streaming_response_warning(self):
        async def async_iter():
            """

            Asynchronously yields a sequence of bytes.

            This asynchronous iterator produces a series of byte strings, allowing 
            for efficient handling of data streams or chunks of binary data.

            Yields:
                bytes: The next byte string in the sequence.

            Example use cases include data streaming, pagination, or handling large 
            binary files in an asynchronous context.

            """
            yield b"hello"
            yield b"world"

        r = StreamingHttpResponse(async_iter())

        msg = (
            "StreamingHttpResponse must consume asynchronous iterators in order to "
            "serve them synchronously. Use a synchronous iterator instead."
        )
        with self.assertWarnsMessage(Warning, msg):
            self.assertEqual(list(r), [b"hello", b"world"])

    async def test_sync_streaming_response_warning(self):
        r = StreamingHttpResponse(iter(["hello", "world"]))

        msg = (
            "StreamingHttpResponse must consume synchronous iterators in order to "
            "serve them asynchronously. Use an asynchronous iterator instead."
        )
        with self.assertWarnsMessage(Warning, msg):
            self.assertEqual(b"hello", await anext(aiter(r)))


class FileCloseTests(SimpleTestCase):
    def setUp(self):
        # Disable the request_finished signal during this test
        # to avoid interfering with the database connection.
        request_finished.disconnect(close_old_connections)
        self.addCleanup(request_finished.connect, close_old_connections)

    def test_response(self):
        """
        Tests the correct handling of file objects in HttpResponse instances. 

        Verifies that when a file object is passed to an HttpResponse and then closed, the file is indeed properly closed. 

        Also checks that when the content of an HttpResponse is replaced with another file object, both the original and new file objects are properly closed. 

        This test case ensures that HttpResponse instances correctly manage the lifetime of file objects, preventing file descriptor leaks.
        """
        filename = os.path.join(os.path.dirname(__file__), "abc.txt")

        # file isn't closed until we close the response.
        file1 = open(filename)
        r = HttpResponse(file1)
        self.assertTrue(file1.closed)
        r.close()

        # when multiple file are assigned as content, make sure they are all
        # closed with the response.
        file1 = open(filename)
        file2 = open(filename)
        r = HttpResponse(file1)
        r.content = file2
        self.assertTrue(file1.closed)
        self.assertTrue(file2.closed)

    def test_streaming_response(self):
        filename = os.path.join(os.path.dirname(__file__), "abc.txt")

        # file isn't closed until we close the response.
        file1 = open(filename)
        r = StreamingHttpResponse(file1)
        self.assertFalse(file1.closed)
        r.close()
        self.assertTrue(file1.closed)

        # when multiple file are assigned as content, make sure they are all
        # closed with the response.
        file1 = open(filename)
        file2 = open(filename)
        r = StreamingHttpResponse(file1)
        r.streaming_content = file2
        self.assertFalse(file1.closed)
        self.assertFalse(file2.closed)
        r.close()
        self.assertTrue(file1.closed)
        self.assertTrue(file2.closed)


class CookieTests(unittest.TestCase):
    def test_encode(self):
        """Semicolons and commas are encoded."""
        c = SimpleCookie()
        c["test"] = "An,awkward;value"
        self.assertNotIn(";", c.output().rstrip(";"))  # IE compat
        self.assertNotIn(",", c.output().rstrip(";"))  # Safari compat

    def test_decode(self):
        """Semicolons and commas are decoded."""
        c = SimpleCookie()
        c["test"] = "An,awkward;value"
        c2 = SimpleCookie()
        c2.load(c.output()[12:])
        self.assertEqual(c["test"].value, c2["test"].value)
        c3 = parse_cookie(c.output()[12:])
        self.assertEqual(c["test"].value, c3["test"])

    def test_nonstandard_keys(self):
        """
        A single non-standard cookie name doesn't affect all cookies (#13007).
        """
        self.assertIn("good_cookie", parse_cookie("good_cookie=yes;bad:cookie=yes"))

    def test_repeated_nonstandard_keys(self):
        """
        A repeated non-standard name doesn't affect all cookies (#15852).
        """
        self.assertIn("good_cookie", parse_cookie("a:=b; a:=c; good_cookie=yes"))

    def test_python_cookies(self):
        """
        Test cases copied from Python's Lib/test/test_http_cookies.py
        """
        self.assertEqual(
            parse_cookie("chips=ahoy; vienna=finger"),
            {"chips": "ahoy", "vienna": "finger"},
        )
        # Here parse_cookie() differs from Python's cookie parsing in that it
        # treats all semicolons as delimiters, even within quotes.
        self.assertEqual(
            parse_cookie('keebler="E=mc2; L=\\"Loves\\"; fudge=\\012;"'),
            {"keebler": '"E=mc2', "L": '\\"Loves\\"', "fudge": "\\012", "": '"'},
        )
        # Illegal cookies that have an '=' char in an unquoted value.
        self.assertEqual(parse_cookie("keebler=E=mc2"), {"keebler": "E=mc2"})
        # Cookies with ':' character in their name.
        self.assertEqual(
            parse_cookie("key:term=value:term"), {"key:term": "value:term"}
        )
        # Cookies with '[' and ']'.
        self.assertEqual(
            parse_cookie("a=b; c=[; d=r; f=h"), {"a": "b", "c": "[", "d": "r", "f": "h"}
        )

    def test_cookie_edgecases(self):
        # Cookies that RFC 6265 allows.
        self.assertEqual(
            parse_cookie("a=b; Domain=example.com"), {"a": "b", "Domain": "example.com"}
        )
        # parse_cookie() has historically kept only the last cookie with the
        # same name.
        self.assertEqual(parse_cookie("a=b; h=i; a=c"), {"a": "c", "h": "i"})

    def test_invalid_cookies(self):
        """
        Cookie strings that go against RFC 6265 but browsers will send if set
        via document.cookie.
        """
        # Chunks without an equals sign appear as unnamed values per
        # https://bugzilla.mozilla.org/show_bug.cgi?id=169091
        self.assertIn(
            "django_language", parse_cookie("abc=def; unnamed; django_language=en")
        )
        # Even a double quote may be an unnamed value.
        self.assertEqual(parse_cookie('a=b; "; c=d'), {"a": "b", "": '"', "c": "d"})
        # Spaces in names and values, and an equals sign in values.
        self.assertEqual(
            parse_cookie("a b c=d e = f; gh=i"), {"a b c": "d e = f", "gh": "i"}
        )
        # More characters the spec forbids.
        self.assertEqual(
            parse_cookie('a   b,c<>@:/[]?{}=d  "  =e,f g'),
            {"a   b,c<>@:/[]?{}": 'd  "  =e,f g'},
        )
        # Unicode characters. The spec only allows ASCII.
        self.assertEqual(
            parse_cookie("saint=André Bessette"), {"saint": "André Bessette"}
        )
        # Browsers don't send extra whitespace or semicolons in Cookie headers,
        # but parse_cookie() should parse whitespace the same way
        # document.cookie parses whitespace.
        self.assertEqual(
            parse_cookie("  =  b  ;  ;  =  ;   c  =  ;  "), {"": "b", "c": ""}
        )

    def test_samesite(self):
        """
        Checks the handling of the SameSite attribute in HTTP cookies, specifically when the attribute is set to 'lax'. Verifies that the attribute is correctly parsed and included in the cookie output.
        """
        c = SimpleCookie("name=value; samesite=lax; httponly")
        self.assertEqual(c["name"]["samesite"], "lax")
        self.assertIn("SameSite=lax", c.output())

    def test_httponly_after_load(self):
        """
        Tests whether the HttpOnly flag is correctly set for a cookie after loading.

        This test case checks if setting the HttpOnly attribute of a cookie after it has been loaded from a string works as expected. It verifies that the HttpOnly flag is successfully enabled for the cookie, ensuring that the cookie's value is not accessible through JavaScript, enhancing the cookie's security.

        The test covers a typical scenario where a cookie is loaded from a string, modified to include the HttpOnly attribute, and then verified to ensure the attribute was successfully applied. This is crucial for web applications that need to protect sensitive information stored in cookies from potential XSS attacks.

        The test method checks the 'httponly' attribute of a loaded cookie to confirm its value after being explicitly set, providing assurance in the handling of such security-critical attributes by the cookie management system.
        """
        c = SimpleCookie()
        c.load("name=val")
        c["name"]["httponly"] = True
        self.assertTrue(c["name"]["httponly"])

    def test_load_dict(self):
        """

        Tests the ability to load a dictionary into a SimpleCookie object.

        This test case verifies that the load method correctly populates the SimpleCookie
        object with key-value pairs from the input dictionary, and that the values can be
        successfully retrieved.

        Checks that the value associated with a given key is correctly stored and 
        retrieved from the SimpleCookie object.

        """
        c = SimpleCookie()
        c.load({"name": "val"})
        self.assertEqual(c["name"].value, "val")

    def test_pickle(self):
        """

        Tests the serialization of a SimpleCookie object using the pickle module.

        Verifies that a SimpleCookie object can be successfully pickled and unpickled 
        at various protocol levels, and that its contents remain intact after the 
        serialization process. This ensures that the object's state is correctly 
        preserved when it is converted to a byte stream and back.

        The test case creates a SimpleCookie object, populates it with sample data, 
        and checks that its output matches the expected result. It then pickles and 
        unpickles the object at each supported protocol level, verifying that the 
        unpickled object's output remains consistent with the original object.

        """
        rawdata = 'Customer="WILE_E_COYOTE"; Path=/acme; Version=1'
        expected_output = "Set-Cookie: %s" % rawdata

        C = SimpleCookie()
        C.load(rawdata)
        self.assertEqual(C.output(), expected_output)

        for proto in range(pickle.HIGHEST_PROTOCOL + 1):
            C1 = pickle.loads(pickle.dumps(C, protocol=proto))
            self.assertEqual(C1.output(), expected_output)


class HttpResponseHeadersTestCase(SimpleTestCase):
    """Headers by treating HttpResponse like a dictionary."""

    def test_headers(self):
        response = HttpResponse()
        response["X-Foo"] = "bar"
        self.assertEqual(response["X-Foo"], "bar")
        self.assertEqual(response.headers["X-Foo"], "bar")
        self.assertIn("X-Foo", response)
        self.assertIs(response.has_header("X-Foo"), True)
        del response["X-Foo"]
        self.assertNotIn("X-Foo", response)
        self.assertNotIn("X-Foo", response.headers)
        # del doesn't raise a KeyError on nonexistent headers.
        del response["X-Foo"]

    def test_headers_as_iterable_of_tuple_pairs(self):
        """

        Tests that HTTP response headers can be provided as an iterable of tuple pairs.

        This test case verifies that an HttpResponse object can be instantiated with
        headers represented as a collection of key-value pairs, where each pair is a
        tuple containing the header name and its corresponding value. The test checks
        that the header values are correctly accessible by their respective names.

        """
        response = HttpResponse(headers=(("X-Foo", "bar"),))
        self.assertEqual(response["X-Foo"], "bar")

    def test_headers_bytestring(self):
        """
        Tests that HTTP response headers containing byte strings are properly decoded.

        Verifies that a header value set as a byte string is correctly stored and 
        retrieved as a Unicode string, ensuring consistency in header value access 
        through dictionary and headers attributes. 

        The test covers the case where a response header is initially set with a byte 
        string value and then checks that this value is correctly decoded and 
        accessible through both the response object's dictionary-like interface and 
        its headers dictionary.

        """
        response = HttpResponse()
        response["X-Foo"] = b"bar"
        self.assertEqual(response["X-Foo"], "bar")
        self.assertEqual(response.headers["X-Foo"], "bar")

    def test_newlines_in_headers(self):
        response = HttpResponse()
        with self.assertRaises(BadHeaderError):
            response["test\rstr"] = "test"
        with self.assertRaises(BadHeaderError):
            response["test\nstr"] = "test"
