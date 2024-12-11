from django.conf import settings
from django.core.exceptions import MiddlewareNotUsed
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from . import middleware as mw


@override_settings(ROOT_URLCONF="middleware_exceptions.urls")
class MiddlewareTests(SimpleTestCase):
    def tearDown(self):
        mw.log = []

    @override_settings(
        MIDDLEWARE=["middleware_exceptions.middleware.ProcessViewNoneMiddleware"]
    )
    def test_process_view_return_none(self):
        response = self.client.get("/middleware_exceptions/view/")
        self.assertEqual(mw.log, ["processed view normal_view"])
        self.assertEqual(response.content, b"OK")

    @override_settings(
        MIDDLEWARE=["middleware_exceptions.middleware.ProcessViewMiddleware"]
    )
    def test_process_view_return_response(self):
        """
        Tests the ProcessViewMiddleware when a view returns a response.

        Verifies that the middleware correctly handles a view that returns a normal response.
        It checks that the expected response is returned by the middleware after processing the view.

        The test case inspects the response content to ensure it matches the expected output
        when a view is processed by the middleware, confirming the middleware's functionality
        in a standard request-response scenario.
        """
        response = self.client.get("/middleware_exceptions/view/")
        self.assertEqual(response.content, b"Processed view normal_view")

    @override_settings(
        MIDDLEWARE=[
            "middleware_exceptions.middleware.ProcessViewTemplateResponseMiddleware",
            "middleware_exceptions.middleware.LogMiddleware",
        ]
    )
    def test_templateresponse_from_process_view_rendered(self):
        """
        TemplateResponses returned from process_view() must be rendered before
        being passed to any middleware that tries to access response.content,
        such as middleware_exceptions.middleware.LogMiddleware.
        """
        response = self.client.get("/middleware_exceptions/view/")
        self.assertEqual(
            response.content,
            b"Processed view normal_view\nProcessViewTemplateResponseMiddleware",
        )

    @override_settings(
        MIDDLEWARE=[
            "middleware_exceptions.middleware.ProcessViewTemplateResponseMiddleware",
            "middleware_exceptions.middleware.TemplateResponseMiddleware",
        ]
    )
    def test_templateresponse_from_process_view_passed_to_process_template_response(
        self,
    ):
        """
        TemplateResponses returned from process_view() should be passed to any
        template response middleware.
        """
        response = self.client.get("/middleware_exceptions/view/")
        expected_lines = [
            b"Processed view normal_view",
            b"ProcessViewTemplateResponseMiddleware",
            b"TemplateResponseMiddleware",
        ]
        self.assertEqual(response.content, b"\n".join(expected_lines))

    @override_settings(
        MIDDLEWARE=["middleware_exceptions.middleware.TemplateResponseMiddleware"]
    )
    def test_process_template_response(self):
        """
        Tests the TemplateResponseMiddleware by making a GET request to the '/middleware_exceptions/template_response/' URL and verifies that the middleware correctly processes the template response, resulting in the expected content being returned.
        """
        response = self.client.get("/middleware_exceptions/template_response/")
        self.assertEqual(
            response.content, b"template_response OK\nTemplateResponseMiddleware"
        )

    @override_settings(
        MIDDLEWARE=["middleware_exceptions.middleware.NoTemplateResponseMiddleware"]
    )
    def test_process_template_response_returns_none(self):
        """
        Tests that NoTemplateResponseMiddleware correctly handles template responses.

        This test case checks that when the middleware encounters a template response,
        it raises a ValueError with a specific error message, indicating that it did not
        return an HttpResponse object as expected. The error message is verified to
        contain the expected text.

        The test utilizes a test client to simulate a GET request to a specific URL,
        triggering the middleware's processing of the template response. The test then
        asserts that the expected ValueError is raised with the correct error message,
        verifying the middleware's behavior in this scenario.
        """
        msg = (
            "NoTemplateResponseMiddleware.process_template_response didn't "
            "return an HttpResponse object. It returned None instead."
        )
        with self.assertRaisesMessage(ValueError, msg):
            self.client.get("/middleware_exceptions/template_response/")

    @override_settings(MIDDLEWARE=["middleware_exceptions.middleware.LogMiddleware"])
    def test_view_exception_converted_before_middleware(self):
        """
        Tests that a view exception is properly converted before being passed to middleware.

        This test case checks if a permission denied exception raised by a view is 
        correctly handled and logged by the middleware. It verifies that the 
        middleware correctly captures the response status code and content, and that 
        the response status code is set to 403 Forbidden as expected.

        The test is conducted with a custom middleware configuration to isolate the 
        behavior of the LogMiddleware class. The test outcome ensures that the 
        middleware accurately logs exceptions and that the view exception is 
        converted into a suitable HTTP response.
        """
        response = self.client.get("/middleware_exceptions/permission_denied/")
        self.assertEqual(mw.log, [(response.status_code, response.content)])
        self.assertEqual(response.status_code, 403)

    @override_settings(
        MIDDLEWARE=["middleware_exceptions.middleware.ProcessExceptionMiddleware"]
    )
    def test_view_exception_handled_by_process_exception(self):
        """
        Tests if the ProcessExceptionMiddleware correctly handles view exceptions by checking the response content when an exception is raised. The test simulates a request to a URL that triggers an exception and verifies that the middleware catches the exception and returns the expected response.
        """
        response = self.client.get("/middleware_exceptions/error/")
        self.assertEqual(response.content, b"Exception caught")

    @override_settings(
        MIDDLEWARE=[
            "middleware_exceptions.middleware.ProcessExceptionLogMiddleware",
            "middleware_exceptions.middleware.ProcessExceptionMiddleware",
        ]
    )
    def test_response_from_process_exception_short_circuits_remainder(self):
        response = self.client.get("/middleware_exceptions/error/")
        self.assertEqual(mw.log, [])
        self.assertEqual(response.content, b"Exception caught")

    @override_settings(
        MIDDLEWARE=[
            "middleware_exceptions.middleware.ProcessExceptionMiddleware",
            "middleware_exceptions.middleware.ProcessExceptionLogMiddleware",
        ]
    )
    def test_response_from_process_exception_when_return_response(self):
        response = self.client.get("/middleware_exceptions/error/")
        self.assertEqual(mw.log, ["process-exception"])
        self.assertEqual(response.content, b"Exception caught")

    @override_settings(
        MIDDLEWARE=[
            "middleware_exceptions.middleware.LogMiddleware",
            "middleware_exceptions.middleware.NotFoundMiddleware",
        ]
    )
    def test_exception_in_middleware_converted_before_prior_middleware(self):
        """
        Tests the scenario where an exception occurs in a middleware and is converted before a prior middleware is executed.

        The function sends a GET request to the '/middleware_exceptions/view/' URL and checks the following conditions:

        - The log from the middleware contains the correct status code (404) and response content.
        - The status code of the HTTP response is 404, indicating that the request was not found. 

        This test case verifies that exceptions in middleware are properly handled and converted before being processed by subsequent middleware in the stack.
        """
        response = self.client.get("/middleware_exceptions/view/")
        self.assertEqual(mw.log, [(404, response.content)])
        self.assertEqual(response.status_code, 404)

    @override_settings(
        MIDDLEWARE=["middleware_exceptions.middleware.ProcessExceptionMiddleware"]
    )
    def test_exception_in_render_passed_to_process_exception(self):
        """
        Tests that an exception raised during template rendering is caught and processed by the ProcessExceptionMiddleware.

        This test case simulates a scenario where an exception occurs while rendering a template and verifies that the exception is properly handled and passed to the ProcessExceptionMiddleware for further processing.

        The expected outcome of this test is that the exception is caught and a response with the content 'Exception caught' is returned, indicating successful processing of the exception by the middleware.
        """
        response = self.client.get("/middleware_exceptions/exception_in_render/")
        self.assertEqual(response.content, b"Exception caught")


@override_settings(ROOT_URLCONF="middleware_exceptions.urls")
class RootUrlconfTests(SimpleTestCase):
    @override_settings(ROOT_URLCONF=None)
    def test_missing_root_urlconf(self):
        # Removing ROOT_URLCONF is safe, as override_settings will restore
        # the previously defined settings.
        """
        Tests that a missing ROOT_URLCONF setting results in an AttributeError when making a request.

        This test case simulates the absence of a root URL configuration by deleting the ROOT_URLCONF setting.
        It then attempts to make a GET request to a specific URL and verifies that an AttributeError is raised,
        indicating that the root URL configuration is required for request processing to proceed.

        The purpose of this test is to ensure that the application correctly handles the absence of a root URL configuration,
        and that it raises an exception instead of producing unexpected behavior or errors.

        """
        del settings.ROOT_URLCONF
        with self.assertRaises(AttributeError):
            self.client.get("/middleware_exceptions/view/")


class MyMiddleware:
    def __init__(self, get_response):
        raise MiddlewareNotUsed

    def process_request(self, request):
        pass


class MyMiddlewareWithExceptionMessage:
    def __init__(self, get_response):
        raise MiddlewareNotUsed("spam eggs")

    def process_request(self, request):
        pass


@override_settings(
    DEBUG=True,
    ROOT_URLCONF="middleware_exceptions.urls",
    MIDDLEWARE=["django.middleware.common.CommonMiddleware"],
)
class MiddlewareNotUsedTests(SimpleTestCase):
    rf = RequestFactory()

    def test_raise_exception(self):
        """
        Tests that a MiddlewareNotUsed exception is raised when MyMiddleware processes a request.

        This test case verifies that the expected exception is thrown when the middleware
        is not properly utilized, ensuring correct handling of exceptions in the application.

        The test utilizes a sample request and a basic response to simulate a request 
        processing scenario, checking that the MiddlewareNotUsed exception is correctly 
        raised when the middleware is invoked with an incompatible request handler.
        """
        request = self.rf.get("middleware_exceptions/view/")
        with self.assertRaises(MiddlewareNotUsed):
            MyMiddleware(lambda req: HttpResponse()).process_request(request)

    @override_settings(MIDDLEWARE=["middleware_exceptions.tests.MyMiddleware"])
    def test_log(self):
        """
        Tests that the error message \"MiddlewareNotUsed\" is correctly logged when a middleware is not used as expected, at the DEBUG log level. The test case simulates a GET request to a view and verifies that the expected log message is produced.
        """
        with self.assertLogs("django.request", "DEBUG") as cm:
            self.client.get("/middleware_exceptions/view/")
        self.assertEqual(
            cm.records[0].getMessage(),
            "MiddlewareNotUsed: 'middleware_exceptions.tests.MyMiddleware'",
        )

    @override_settings(
        MIDDLEWARE=["middleware_exceptions.tests.MyMiddlewareWithExceptionMessage"]
    )
    def test_log_custom_message(self):
        """

        Tests logging of custom message in Django middleware exception.

        This test case verifies that a custom exception message is properly logged when an exception occurs in a Django middleware.
        It checks that the log message at the DEBUG level contains the expected custom message.

        """
        with self.assertLogs("django.request", "DEBUG") as cm:
            self.client.get("/middleware_exceptions/view/")
        self.assertEqual(
            cm.records[0].getMessage(),
            "MiddlewareNotUsed('middleware_exceptions.tests."
            "MyMiddlewareWithExceptionMessage'): spam eggs",
        )

    @override_settings(
        DEBUG=False,
        MIDDLEWARE=["middleware_exceptions.tests.MyMiddleware"],
    )
    def test_do_not_log_when_debug_is_false(self):
        """

        Tests that no logs are generated at the DEBUG level when the DEBUG setting is False.

        This test case ensures that the logging behavior is correct when the application is running in a non-debug mode.
        It verifies that the expected log messages are not produced, which helps prevent unnecessary log noise in production environments.

        """
        with self.assertNoLogs("django.request", "DEBUG"):
            self.client.get("/middleware_exceptions/view/")

    @override_settings(
        MIDDLEWARE=[
            "middleware_exceptions.middleware.SyncAndAsyncMiddleware",
            "middleware_exceptions.tests.MyMiddleware",
        ]
    )
    async def test_async_and_sync_middleware_chain_async_call(self):
        with self.assertLogs("django.request", "DEBUG") as cm:
            response = await self.async_client.get("/middleware_exceptions/view/")
        self.assertEqual(response.content, b"OK")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            cm.records[0].getMessage(),
            "Asynchronous handler adapted for middleware "
            "middleware_exceptions.tests.MyMiddleware.",
        )
        self.assertEqual(
            cm.records[1].getMessage(),
            "MiddlewareNotUsed: 'middleware_exceptions.tests.MyMiddleware'",
        )


@override_settings(
    DEBUG=True,
    ROOT_URLCONF="middleware_exceptions.urls",
)
class MiddlewareSyncAsyncTests(SimpleTestCase):
    @override_settings(
        MIDDLEWARE=[
            "middleware_exceptions.middleware.PaymentMiddleware",
        ]
    )
    def test_sync_middleware(self):
        response = self.client.get("/middleware_exceptions/view/")
        self.assertEqual(response.status_code, 402)

    @override_settings(
        MIDDLEWARE=[
            "middleware_exceptions.middleware.DecoratedPaymentMiddleware",
        ]
    )
    def test_sync_decorated_middleware(self):
        response = self.client.get("/middleware_exceptions/view/")
        self.assertEqual(response.status_code, 402)

    @override_settings(
        MIDDLEWARE=[
            "middleware_exceptions.middleware.async_payment_middleware",
        ]
    )
    def test_async_middleware(self):
        with self.assertLogs("django.request", "DEBUG") as cm:
            response = self.client.get("/middleware_exceptions/view/")
        self.assertEqual(response.status_code, 402)
        self.assertEqual(
            cm.records[0].getMessage(),
            "Synchronous handler adapted for middleware "
            "middleware_exceptions.middleware.async_payment_middleware.",
        )

    @override_settings(
        MIDDLEWARE=[
            "middleware_exceptions.middleware.NotSyncOrAsyncMiddleware",
        ]
    )
    def test_not_sync_or_async_middleware(self):
        msg = (
            "Middleware "
            "middleware_exceptions.middleware.NotSyncOrAsyncMiddleware must "
            "have at least one of sync_capable/async_capable set to True."
        )
        with self.assertRaisesMessage(RuntimeError, msg):
            self.client.get("/middleware_exceptions/view/")

    @override_settings(
        MIDDLEWARE=[
            "middleware_exceptions.middleware.PaymentMiddleware",
        ]
    )
    async def test_sync_middleware_async(self):
        """
        Tests the synchronous middleware functionality in an asynchronous context.

        This test case verifies that a synchronous middleware can be successfully adapted to work with asynchronous handlers.
        It checks for the correct HTTP status code response and confirms the corresponding log message is generated.

        The test scenario involves sending a GET request to a specific view and asserting the expected response status code and log output.
        The middleware under test is PaymentMiddleware, which is expected to return a 402 status code.

        The test provides assurance that synchronous middleware can be used seamlessly in asynchronous environments, ensuring backwards compatibility and flexibility in handling different types of requests.
        """
        with self.assertLogs("django.request", "DEBUG") as cm:
            response = await self.async_client.get("/middleware_exceptions/view/")
        self.assertEqual(response.status_code, 402)
        self.assertEqual(
            cm.records[0].getMessage(),
            "Asynchronous handler adapted for middleware "
            "middleware_exceptions.middleware.PaymentMiddleware.",
        )

    @override_settings(
        MIDDLEWARE=[
            "middleware_exceptions.middleware.async_payment_middleware",
        ]
    )
    async def test_async_middleware_async(self):
        with self.assertLogs("django.request", "WARNING") as cm:
            response = await self.async_client.get("/middleware_exceptions/view/")
        self.assertEqual(response.status_code, 402)
        self.assertEqual(
            cm.records[0].getMessage(),
            "Payment Required: /middleware_exceptions/view/",
        )

    @override_settings(
        DEBUG=False,
        MIDDLEWARE=[
            "middleware_exceptions.middleware.AsyncNoTemplateResponseMiddleware",
        ],
    )
    def test_async_process_template_response_returns_none_with_sync_client(self):
        msg = (
            "AsyncNoTemplateResponseMiddleware.process_template_response "
            "didn't return an HttpResponse object."
        )
        with self.assertRaisesMessage(ValueError, msg):
            self.client.get("/middleware_exceptions/template_response/")

    @override_settings(
        MIDDLEWARE=[
            "middleware_exceptions.middleware.SyncAndAsyncMiddleware",
        ]
    )
    async def test_async_and_sync_middleware_async_call(self):
        """
        Tests that an asynchronous request to the view handled by SyncAndAsyncMiddleware returns a successful response.

        This test case verifies that the middleware correctly handles asynchronous calls and returns the expected response content and status code.

        The test utilizes a test client to send an asynchronous GET request to the specified view, and then asserts that the response content is 'OK' and the status code is 200, indicating a successful request.

        The middleware being tested is configured with override settings to isolate its behavior and ensure accurate test results. 
        """
        response = await self.async_client.get("/middleware_exceptions/view/")
        self.assertEqual(response.content, b"OK")
        self.assertEqual(response.status_code, 200)

    @override_settings(
        MIDDLEWARE=[
            "middleware_exceptions.middleware.SyncAndAsyncMiddleware",
        ]
    )
    def test_async_and_sync_middleware_sync_call(self):
        """

        Tests the SyncAndAsyncMiddleware when handling a synchronous HTTP request.

        This test case verifies that the middleware correctly handles a GET request to the 
        '/middleware_exceptions/view/' endpoint, checking that the response content and 
        status code match the expected values, indicating successful processing of the 
        request.

        """
        response = self.client.get("/middleware_exceptions/view/")
        self.assertEqual(response.content, b"OK")
        self.assertEqual(response.status_code, 200)


@override_settings(ROOT_URLCONF="middleware_exceptions.urls")
class AsyncMiddlewareTests(SimpleTestCase):
    @override_settings(
        MIDDLEWARE=[
            "middleware_exceptions.middleware.AsyncTemplateResponseMiddleware",
        ]
    )
    async def test_process_template_response(self):
        """
        Tests the asynchronous processing of template responses.

        This test case verifies that the AsyncTemplateResponseMiddleware correctly handles
        template responses. It simulates a GET request to a specific URL and checks that
        the response content matches the expected output, confirming that the middleware
        is functioning as expected.

        :raises AssertionError: If the response content does not match the expected output.

        """
        response = await self.async_client.get(
            "/middleware_exceptions/template_response/"
        )
        self.assertEqual(
            response.content,
            b"template_response OK\nAsyncTemplateResponseMiddleware",
        )

    @override_settings(
        MIDDLEWARE=[
            "middleware_exceptions.middleware.AsyncNoTemplateResponseMiddleware",
        ]
    )
    async def test_process_template_response_returns_none(self):
        msg = (
            "AsyncNoTemplateResponseMiddleware.process_template_response "
            "didn't return an HttpResponse object. It returned None instead."
        )
        with self.assertRaisesMessage(ValueError, msg):
            await self.async_client.get("/middleware_exceptions/template_response/")

    @override_settings(
        MIDDLEWARE=[
            "middleware_exceptions.middleware.AsyncProcessExceptionMiddleware",
        ]
    )
    async def test_exception_in_render_passed_to_process_exception(self):
        """
        Tests if an exception occurring during the render process is properly caught and handled by the AsyncProcessExceptionMiddleware.

        This test case sends an asynchronous GET request to the '/middleware_exceptions/exception_in_render/' endpoint, 
        which is expected to raise an exception during rendering. It then verifies that the middleware correctly 
        catches the exception and returns a response with the content 'Exception caught'. 

        The test is executed with the AsyncProcessExceptionMiddleware enabled, allowing it to intercept and process 
        the exception that occurs during the rendering process. 

        The successful test indicates that the middleware is functioning as expected, providing a basic error handling 
        mechanism for asynchronous requests. 
        """
        response = await self.async_client.get(
            "/middleware_exceptions/exception_in_render/"
        )
        self.assertEqual(response.content, b"Exception caught")

    @override_settings(
        MIDDLEWARE=[
            "middleware_exceptions.middleware.AsyncProcessExceptionMiddleware",
        ]
    )
    async def test_exception_in_async_render_passed_to_process_exception(self):
        """
        Tests an asynchronous HTTP request to a URL that triggers an exception in the render process, verifying that the exception is properly caught and handled by the AsyncProcessExceptionMiddleware. The test ensures that the middleware correctly intercepts and processes exceptions raised during asynchronous rendering, returning a response with a specific content.
        """
        response = await self.async_client.get(
            "/middleware_exceptions/async_exception_in_render/"
        )
        self.assertEqual(response.content, b"Exception caught")

    @override_settings(
        MIDDLEWARE=[
            "middleware_exceptions.middleware.AsyncProcessExceptionMiddleware",
        ]
    )
    async def test_view_exception_handled_by_process_exception(self):
        response = await self.async_client.get("/middleware_exceptions/error/")
        self.assertEqual(response.content, b"Exception caught")

    @override_settings(
        MIDDLEWARE=[
            "middleware_exceptions.middleware.AsyncProcessViewMiddleware",
        ]
    )
    async def test_process_view_return_response(self):
        """
        Tests that the AsyncProcessViewMiddleware correctly processes a view and returns the expected response.

        This test case verifies that the middleware executes the view and returns the predicted output, 
        demonstrating the proper functioning of the middleware in handling view processing and response generation.

        The test covers the successful execution of the view, ensuring that the middleware does not interfere 
        with the normal operation of the view, and that the expected response is returned to the client.

        This serves as a validation of the AsyncProcessViewMiddleware's ability to work with asynchronous views 
        and its impact on the overall request-response cycle.

        """
        response = await self.async_client.get("/middleware_exceptions/view/")
        self.assertEqual(response.content, b"Processed view normal_view")
