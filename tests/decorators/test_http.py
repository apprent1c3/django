import datetime

from asgiref.sync import iscoroutinefunction

from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.test import SimpleTestCase
from django.views.decorators.http import (
    condition,
    conditional_page,
    require_http_methods,
    require_safe,
)


class RequireHttpMethodsTest(SimpleTestCase):
    def test_wrapped_sync_function_is_not_coroutine_function(self):
        def sync_view(request):
            return HttpResponse()

        wrapped_view = require_http_methods(["GET"])(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
        """
        Tests that an asynchronous view function wrapped with the require_http_methods decorator remains a coroutine function.

        The require_http_methods decorator is expected to preserve the asynchronous nature of the original view function, 
        allowing it to be properly handled by the asynchronous view system. This test ensures that the decorator does not alter 
        the coroutine status of the wrapped view function, which is essential for maintaining the correct execution flow in an 
        asynchronous environment.
        """
        async def async_view(request):
            return HttpResponse()

        wrapped_view = require_http_methods(["GET"])(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_require_http_methods_methods(self):
        @require_http_methods(["GET", "PUT"])
        """
        Tests the require_http_methods decorator to ensure it correctly restricts allowed HTTP methods.

        This test verifies that only the specified HTTP methods are allowed and that 
        all others are responded to with an HttpResponseNotAllowed response.

        The decorator is tested with GET and PUT methods as allowed methods, and 
        HEAD, POST, DELETE as disallowed methods.

        :param none:
        :returns: none
        :raises: AssertionError if the decorated view does not behave as expected
        """
        def my_view(request):
            return HttpResponse("OK")

        request = HttpRequest()
        request.method = "GET"
        self.assertIsInstance(my_view(request), HttpResponse)
        request.method = "PUT"
        self.assertIsInstance(my_view(request), HttpResponse)
        request.method = "HEAD"
        self.assertIsInstance(my_view(request), HttpResponseNotAllowed)
        request.method = "POST"
        self.assertIsInstance(my_view(request), HttpResponseNotAllowed)
        request.method = "DELETE"
        self.assertIsInstance(my_view(request), HttpResponseNotAllowed)

    async def test_require_http_methods_methods_async_view(self):
        @require_http_methods(["GET", "PUT"])
        """
        Tests the ``require_http_methods`` decorator for an asynchronous view.

        This test case verifies that the decorator correctly restricts the allowed HTTP methods 
        for an async view. It checks that the view returns a successful response for the allowed 
        methods ('GET' and 'PUT') and returns a '405 Method Not Allowed' response for disallowed 
        methods ('HEAD', 'POST', 'DELETE').
        """
        async def my_view(request):
            return HttpResponse("OK")

        request = HttpRequest()
        request.method = "GET"
        self.assertIsInstance(await my_view(request), HttpResponse)
        request.method = "PUT"
        self.assertIsInstance(await my_view(request), HttpResponse)
        request.method = "HEAD"
        self.assertIsInstance(await my_view(request), HttpResponseNotAllowed)
        request.method = "POST"
        self.assertIsInstance(await my_view(request), HttpResponseNotAllowed)
        request.method = "DELETE"
        self.assertIsInstance(await my_view(request), HttpResponseNotAllowed)


class RequireSafeDecoratorTest(SimpleTestCase):
    def test_require_safe_accepts_only_safe_methods(self):
        def my_view(request):
            return HttpResponse("OK")

        my_safe_view = require_safe(my_view)
        request = HttpRequest()
        request.method = "GET"
        self.assertIsInstance(my_safe_view(request), HttpResponse)
        request.method = "HEAD"
        self.assertIsInstance(my_safe_view(request), HttpResponse)
        request.method = "POST"
        self.assertIsInstance(my_safe_view(request), HttpResponseNotAllowed)
        request.method = "PUT"
        self.assertIsInstance(my_safe_view(request), HttpResponseNotAllowed)
        request.method = "DELETE"
        self.assertIsInstance(my_safe_view(request), HttpResponseNotAllowed)

    async def test_require_safe_accepts_only_safe_methods_async_view(self):
        @require_safe
        """

        Test that the require_safe decorator correctly restricts an async view to only 
        allow safe HTTP methods (GET and HEAD).

        The decorator should permit requests with GET and HEAD methods, while rejecting 
        requests with POST, PUT, DELETE, and other non-safe methods, returning a 
        405 Method Not Allowed response instead.

        This test covers the expected behavior of the require_safe decorator when used 
        with an asynchronous view function, verifying its correctness in a variety of 
        scenarios.

        """
        async def async_view(request):
            return HttpResponse("OK")

        request = HttpRequest()
        request.method = "GET"
        self.assertIsInstance(await async_view(request), HttpResponse)
        request.method = "HEAD"
        self.assertIsInstance(await async_view(request), HttpResponse)
        request.method = "POST"
        self.assertIsInstance(await async_view(request), HttpResponseNotAllowed)
        request.method = "PUT"
        self.assertIsInstance(await async_view(request), HttpResponseNotAllowed)
        request.method = "DELETE"
        self.assertIsInstance(await async_view(request), HttpResponseNotAllowed)


class ConditionDecoratorTest(SimpleTestCase):
    def etag_func(request, *args, **kwargs):
        return '"b4246ffc4f62314ca13147c9d4f76974"'

    def latest_entry(request, *args, **kwargs):
        return datetime.datetime(2023, 1, 2, 23, 21, 47)

    def test_wrapped_sync_function_is_not_coroutine_function(self):
        """

        Tests that a synchronous function wrapped with conditional decorators remains a non-coroutine function.

        Verifies that after applying the condition decorator with etag and last modified functions to a synchronous view function, the resulting wrapped view function is still not a coroutine function.

        """
        def sync_view(request):
            return HttpResponse()

        wrapped_view = condition(
            etag_func=self.etag_func, last_modified_func=self.latest_entry
        )(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
        """
        Tests that a wrapped asynchronous view function remains a coroutine function.

        The function verifies that applying the condition decorator with etag and last modified
        functionalities to an asynchronous view does not alter its coroutine nature.

        This test ensures that the decorated asynchronous view can still be used as a coroutine,
        allowing for proper asynchronous execution and handling of HTTP requests.
        """
        async def async_view(request):
            return HttpResponse()

        wrapped_view = condition(
            etag_func=self.etag_func, last_modified_func=self.latest_entry
        )(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_condition_decorator(self):
        @condition(
            etag_func=self.etag_func,
            last_modified_func=self.latest_entry,
        )
        def my_view(request):
            return HttpResponse()

        request = HttpRequest()
        request.method = "GET"
        response = my_view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["ETag"], '"b4246ffc4f62314ca13147c9d4f76974"')
        self.assertEqual(
            response.headers["Last-Modified"],
            "Mon, 02 Jan 2023 23:21:47 GMT",
        )

    async def test_condition_decorator_async_view(self):
        @condition(
            etag_func=self.etag_func,
            last_modified_func=self.latest_entry,
        )
        async def async_view(request):
            return HttpResponse()

        request = HttpRequest()
        request.method = "GET"
        response = await async_view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["ETag"], '"b4246ffc4f62314ca13147c9d4f76974"')
        self.assertEqual(
            response.headers["Last-Modified"],
            "Mon, 02 Jan 2023 23:21:47 GMT",
        )


class ConditionalPageTests(SimpleTestCase):
    def test_wrapped_sync_function_is_not_coroutine_function(self):
        """
        Tests that a wrapped synchronous function remains a non-coroutine function.

        The function checks that when a synchronous view is wrapped with the conditional_page decorator, 
        the resulting wrapped view is still not a coroutine function, 
        preserving its synchronous behavior and avoiding any potential asynchronous side effects.
        """
        def sync_view(request):
            return HttpResponse()

        wrapped_view = conditional_page(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
        """
        Tests that the conditional_page decorator correctly wraps an asynchronous view function, 
        resulting in a coroutine function. 

        Verifies that the wrapped view function retains its asynchronous nature, 
        allowing it to be properly handled and awaited as a coroutine. 

        This ensures that the decorated function can be used in asynchronous contexts 
        and can leverage the benefits of asynchronous programming, such as improved concurrency and responsiveness.
        """
        async def async_view(request):
            return HttpResponse()

        wrapped_view = conditional_page(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_conditional_page_decorator_successful(self):
        @conditional_page
        def sync_view(request):
            response = HttpResponse()
            response.content = b"test"
            response["Cache-Control"] = "public"
            return response

        request = HttpRequest()
        request.method = "GET"
        response = sync_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.get("Etag"))

    async def test_conditional_page_decorator_successful_async_view(self):
        @conditional_page
        """
        Tests the conditional page decorator with a successful asynchronous view.

        This test case verifies that the conditional page decorator correctly handles
        an asynchronous view that returns a successful response. It checks that the
        response status code is 200 and that an Etag header is present in the response.

        The test scenario involves an asynchronous view that returns a simple HTTP response
        with a public cache control policy. The test then asserts that the decorated view
        behaves as expected, returning a successful response with the correct headers.\"\"\"
        ```
        """
        async def async_view(request):
            response = HttpResponse()
            response.content = b"test"
            response["Cache-Control"] = "public"
            return response

        request = HttpRequest()
        request.method = "GET"
        response = await async_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.get("Etag"))
