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
        async def async_view(request):
            return HttpResponse()

        wrapped_view = require_http_methods(["GET"])(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_require_http_methods_methods(self):
        @require_http_methods(["GET", "PUT"])
        """

         Tests the functionality of the require_http_methods decorator.

         The require_http_methods decorator restricts the HTTP methods that a view can handle.
         It checks the HTTP method of the incoming request and returns an HttpResponseNotAllowed
         if the method is not in the list of allowed methods.

         This test function verifies that the decorator correctly allows or rejects requests
         based on their HTTP method, by testing a view decorated with require_http_methods
         with different types of requests (GET, PUT, HEAD, POST, DELETE).

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
        """

        Tests the behavior of the require_safe decorator, verifying that it only accepts safe HTTP methods.

        The require_safe decorator is expected to allow GET and HEAD requests to pass through to the view, 
        while blocking other HTTP methods (such as POST, PUT, and DELETE) and returning an HttpResponseNotAllowed instead.

        This test confirms that the decorator behaves as expected, ensuring that only safe methods are allowed to interact with the view.

        """
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
        Tests whether a Sync view function remains a non-coroutine function after being wrapped by the condition decorator with etag and last modified functions. 

        This ensures that the decorator does not inadvertently convert a synchronous view function into an asynchronous coroutine function.
        """
        def sync_view(request):
            return HttpResponse()

        wrapped_view = condition(
            etag_func=self.etag_func, last_modified_func=self.latest_entry
        )(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
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
        """

        Tests the usage of the condition decorator with an asynchronous view.

        This test case verifies that the condition decorator correctly applies the ETag
        and Last-Modified headers to the HTTP response returned by the asynchronous view.
        The test validates the status code of the response and the values of the ETag
        and Last-Modified headers to ensure they match the expected results.

        The condition decorator is applied to an asynchronous view function, which returns
        an HTTP response. The test uses a mock HTTP request object to invoke the view
        function and then asserts that the resulting response contains the correct headers.

        """
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
        def sync_view(request):
            return HttpResponse()

        wrapped_view = conditional_page(sync_view)
        self.assertIs(iscoroutinefunction(wrapped_view), False)

    def test_wrapped_async_function_is_coroutine_function(self):
        async def async_view(request):
            return HttpResponse()

        wrapped_view = conditional_page(async_view)
        self.assertIs(iscoroutinefunction(wrapped_view), True)

    def test_conditional_page_decorator_successful(self):
        @conditional_page
        """
        Tests the conditional page decorator to ensure it successfully handles a view by verifying that it returns a response with a 200 status code and an Etag header.
        """
        def sync_view(request):
            """

            Handles the HTTP request for the sync view page.

            This view returns an HTTP response with a simple test message.
            The response is configured to be publicly cacheable, allowing intermediaries
            to cache the response and reduce the number of requests to the server.

            The response does not render any templates or perform complex computations,
            instead focusing on providing a lightweight and cache-friendly response.

            :return: An HttpResponse object containing the test message

            """
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
