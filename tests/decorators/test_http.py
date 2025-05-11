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

        Tests that the require_http_methods decorator correctly restricts the allowed HTTP methods for a view.

        The decorator ensures that only the specified HTTP methods are permitted to access the view,
        returning an HttpResponse for allowed methods and an HttpResponseNotAllowed for disallowed methods.

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
        Tests that the @require_http_methods decorator correctly allows or disallows HTTP requests to an asynchronous view based on the specified methods.
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
        """
        Tests that the require_safe decorator restricts view access to only safe HTTP methods (GET and HEAD), returning a 405 response for other methods.
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
        """
        Tests that the require_safe decorator restricts an async view to only allow safe HTTP methods (GET and HEAD).
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
        """

        Tests the condition decorator with ETag and Last-Modified headers.

        Verifies that the decorator correctly sets the ETag and Last-Modified headers 
        in the response based on the provided etag_func and last_modified_func.

        """
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
        ..: Tests the functionality of the condition decorator with an asynchronous view, 
            verifying it correctly sets ETag and Last-Modified headers in the HTTP response.
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
        Tests the successful application of the conditional page decorator to a view function, verifying that it properly sets the response status code and Etag header.
        """
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
        Tests the conditional page decorator with a successful asynchronous view, verifying that the view returns a 200 status code and includes an Etag header in the response.
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
