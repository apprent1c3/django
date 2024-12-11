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
        """

        Tests the ProcessViewNoneMiddleware when a view returns None.

        This test case checks that when a view returns None, the middleware correctly handles the response and logs the expected message.
        It verifies that the log contains the 'processed view normal_view' message and the HTTP response content is 'OK'.

        """
        response = self.client.get("/middleware_exceptions/view/")
        self.assertEqual(mw.log, ["processed view normal_view"])
        self.assertEqual(response.content, b"OK")

    @override_settings(
        MIDDLEWARE=["middleware_exceptions.middleware.ProcessViewMiddleware"]
    )
    def test_process_view_return_response(self):
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

        Tests the processing of a template response by the TemplateResponseMiddleware.

        This test case simulates a GET request to a specific URL and verifies that the 
        response content matches the expected output, indicating successful processing 
        by the middleware.

        The test overrides the default middleware settings to isolate the behavior of 
        the TemplateResponseMiddleware, ensuring that it correctly handles template 
        responses as expected.

        """
        response = self.client.get("/middleware_exceptions/template_response/")
        self.assertEqual(
            response.content, b"template_response OK\nTemplateResponseMiddleware"
        )

    @override_settings(
        MIDDLEWARE=["middleware_exceptions.middleware.NoTemplateResponseMiddleware"]
    )
    def test_process_template_response_returns_none(self):
        msg = (
            "NoTemplateResponseMiddleware.process_template_response didn't "
            "return an HttpResponse object. It returned None instead."
        )
        with self.assertRaisesMessage(ValueError, msg):
            self.client.get("/middleware_exceptions/template_response/")

    @override_settings(MIDDLEWARE=["middleware_exceptions.middleware.LogMiddleware"])
    def test_view_exception_converted_before_middleware(self):
        response = self.client.get("/middleware_exceptions/permission_denied/")
        self.assertEqual(mw.log, [(response.status_code, response.content)])
        self.assertEqual(response.status_code, 403)

    @override_settings(
        MIDDLEWARE=["middleware_exceptions.middleware.ProcessExceptionMiddleware"]
    )
    def test_view_exception_handled_by_process_exception(self):
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

        Tests that an exception in a middleware is converted and logged before being handled by prior middleware.

        This test case verifies that middleware exceptions are properly intercepted, converted, and recorded
        before being passed to subsequent middleware for handling. It checks that the logging middleware
        correctly captures the exception and logs it with the expected status code and response content.

        """
        response = self.client.get("/middleware_exceptions/view/")
        self.assertEqual(mw.log, [(404, response.content)])
        self.assertEqual(response.status_code, 404)

    @override_settings(
        MIDDLEWARE=["middleware_exceptions.middleware.ProcessExceptionMiddleware"]
    )
    def test_exception_in_render_passed_to_process_exception(self):
        """

        Tests that an exception raised during the render phase of a view is properly caught and handled by the ProcessExceptionMiddleware.

        The test case simulates a request to a view that intentionally raises an exception during rendering. It then verifies that the middleware successfully intercepts the exception and returns a response indicating that the exception was caught.

        This tests the integration of the ProcessExceptionMiddleware with the view rendering process, ensuring that exceptions are properly propagated and handled.\"
        """
        response = self.client.get("/middleware_exceptions/exception_in_render/")
        self.assertEqual(response.content, b"Exception caught")


@override_settings(ROOT_URLCONF="middleware_exceptions.urls")
class RootUrlconfTests(SimpleTestCase):
    @override_settings(ROOT_URLCONF=None)
    def test_missing_root_urlconf(self):
        # Removing ROOT_URLCONF is safe, as override_settings will restore
        # the previously defined settings.
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
        request = self.rf.get("middleware_exceptions/view/")
        with self.assertRaises(MiddlewareNotUsed):
            MyMiddleware(lambda req: HttpResponse()).process_request(request)

    @override_settings(MIDDLEWARE=["middleware_exceptions.tests.MyMiddleware"])
    def test_log(self):
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
        Test case to verify that custom exception messages are logged correctly.

        This test checks that when a custom middleware raises an exception with a custom message,
        the message is properly logged by the logging system. It simulates a GET request to a view
        and asserts that the log message matches the expected custom message, confirming that
        the logging system is working as expected with custom middleware exceptions.

        The test uses a custom middleware that raises an exception with a message containing 'spam eggs',
        allowing the test to verify that this message is correctly logged and propagated through the system.
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

        This test case ensures that the logging mechanism behaves as expected when the application is running in a production-like environment (DEBUG=False).
        It verifies that no DEBUG-level log messages are emitted by the 'django.request' logger when a request is processed.
        The test is relevant for guaranteeing that sensitive information is not inadvertently logged in production environments, helping to maintain the security and integrity of the application.
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
        """
        Tests the asynchronous middleware functionality.

        This test case verifies that the middleware correctly handles asynchronous requests.
        It checks the HTTP response status code and logs the adaptation of a synchronous handler
        for the asynchronous payment middleware. The test ensures the correct logging and status
        code are produced when accessing a specific view through the test client.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the expected status code or log message does not match the actual output.

        """
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
        Tests the synchronous call to a view through the SyncAndAsyncMiddleware, 
         ensuring it returns a successful response with status code 200 and content 'OK'.
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
        """
        Tests that AsyncNoTemplateResponseMiddleware correctly raises an error when process_template_response returns None instead of an HttpResponse object.

        This test case verifies the expected behavior of the middleware when it encounters a missing or invalid response from a view. It checks that a ValueError is raised with a descriptive message, ensuring that the application handles this scenario properly and provides useful error information.

        The test scenario involves making an asynchronous GET request to a URL that triggers the middleware's process_template_response method, and then asserting that the expected exception is raised with the correct error message.
        """
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
        response = await self.async_client.get("/middleware_exceptions/view/")
        self.assertEqual(response.content, b"Processed view normal_view")
