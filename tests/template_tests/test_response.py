import pickle
import time
from datetime import datetime

from django.template import engines
from django.template.response import (
    ContentNotRenderedError,
    SimpleTemplateResponse,
    TemplateResponse,
)
from django.test import (
    RequestFactory,
    SimpleTestCase,
    modify_settings,
    override_settings,
)
from django.test.utils import require_jinja2

from .utils import TEMPLATE_DIR


def test_processor(request):
    return {"processors": "yes"}


test_processor_name = "template_tests.test_response.test_processor"


# A test middleware that installs a temporary URLConf
def custom_urlconf_middleware(get_response):
    """

    Custom middleware to override the default URL configuration.

    This function returns a middleware that modifies the incoming request by setting
    the `urlconf` attribute to a custom URL configuration module named 'template_tests.alternate_urls'.
    The modified request is then passed to the next middleware or view in the chain.

    The primary use case for this middleware is to allow for dynamic URL routing based on specific conditions.
    It enables the use of alternative URL patterns for testing or other custom scenarios.

    """
    def middleware(request):
        request.urlconf = "template_tests.alternate_urls"
        return get_response(request)

    return middleware


class SimpleTemplateResponseTest(SimpleTestCase):
    def _response(self, template="foo", *args, **kwargs):
        template = engines["django"].from_string(template)
        return SimpleTemplateResponse(template, *args, **kwargs)

    def test_template_resolving(self):
        """

        Tests the resolving of templates using the SimpleTemplateResponse class.

        This test case checks that the SimpleTemplateResponse class correctly resolves
        templates in the following scenarios:

        - When a single template name is provided, the corresponding template is rendered.
        - When a list of template names is provided, the first existing template in the list is rendered.
        - When a response object is created and rendered, the expected content is generated.

        The test verifies that the resolved template content matches the expected output in each case.

        """
        response = SimpleTemplateResponse("first/test.html")
        response.render()
        self.assertEqual(response.content, b"First template\n")

        templates = ["foo.html", "second/test.html", "first/test.html"]
        response = SimpleTemplateResponse(templates)
        response.render()
        self.assertEqual(response.content, b"Second template\n")

        response = self._response()
        response.render()
        self.assertEqual(response.content, b"foo")

    def test_explicit_baking(self):
        # explicit baking
        response = self._response()
        self.assertFalse(response.is_rendered)
        response.render()
        self.assertTrue(response.is_rendered)

    def test_render(self):
        # response is not re-rendered without the render call
        """

        Tests the rendering functionality of a response object.

        This test case verifies that the content of the response remains unchanged 
        when rendering is applied with an updated template, but the template itself 
        does not actually modify the content. Additionally, it checks that direct 
        modification of the response content results in the expected output.

        It covers the following scenarios:
        - Initial rendering with default template
        - Rendering with a custom template
        - Direct modification of the response content

        """
        response = self._response().render()
        self.assertEqual(response.content, b"foo")

        # rebaking doesn't change the rendered content
        template = engines["django"].from_string("bar{{ baz }}")
        response.template_name = template
        response.render()
        self.assertEqual(response.content, b"foo")

        # but rendered content can be overridden by manually
        # setting content
        response.content = "bar"
        self.assertEqual(response.content, b"bar")

    def test_iteration_unrendered(self):
        # unrendered response raises an exception on iteration
        """

        Tests that attempting to iterate over an unrendered response raises a ContentNotRenderedError.

        The test verifies that the response remains unrendered after the error is raised, 
        ensuring that the iteration attempt does not implicitly render the response content.

        """
        response = self._response()
        self.assertFalse(response.is_rendered)

        def iteration():
            list(response)

        msg = "The response content must be rendered before it can be iterated over."
        with self.assertRaisesMessage(ContentNotRenderedError, msg):
            iteration()
        self.assertFalse(response.is_rendered)

    def test_iteration_rendered(self):
        # iteration works for rendered responses
        response = self._response().render()
        self.assertEqual(list(response), [b"foo"])

    def test_content_access_unrendered(self):
        # unrendered response raises an exception when content is accessed
        """
        Tests that attempting to access the content of an unrendered response raises an error.

            Verifies that the is_rendered flag remains unchanged after the error is raised, confirming
            that the response remains in an unrendered state. This ensures that the response does not
            inadvertently render or modify its content when accessed before rendering is complete.
        """
        response = self._response()
        self.assertFalse(response.is_rendered)
        with self.assertRaises(ContentNotRenderedError):
            response.content
        self.assertFalse(response.is_rendered)

    def test_content_access_rendered(self):
        # rendered response content can be accessed
        response = self._response().render()
        self.assertEqual(response.content, b"foo")

    def test_set_content(self):
        # content can be overridden
        """
        Tests the setting of content on a response object.

        Verifies that setting the content property renders the response and that
        subsequent modifications to the content update the response correctly.

        The test covers both initial setting of content and subsequent updates,
        ensuring that the response's rendered status and content are correctly
        updated in each case.
        """
        response = self._response()
        self.assertFalse(response.is_rendered)
        response.content = "spam"
        self.assertTrue(response.is_rendered)
        self.assertEqual(response.content, b"spam")
        response.content = "baz"
        self.assertEqual(response.content, b"baz")

    def test_dict_context(self):
        response = self._response("{{ foo }}{{ processors }}", {"foo": "bar"})
        self.assertEqual(response.context_data, {"foo": "bar"})
        response.render()
        self.assertEqual(response.content, b"bar")

    def test_kwargs(self):
        """
        Test keyword arguments for response object creation.

        Verifies that the content_type, status, and charset keyword arguments are 
        correctly applied when creating a response object. The test case checks 
        the resulting response object's headers, status code, and charset to 
        ensure they match the provided keyword arguments.

        Raises:
            AssertionError: If any of the expected values do not match the 
                            actual values in the response object.
        """
        response = self._response(
            content_type="application/json", status=504, charset="ascii"
        )
        self.assertEqual(response.headers["content-type"], "application/json")
        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.charset, "ascii")

    def test_args(self):
        """
        Tests that a SimpleTemplateResponse object correctly sets its response headers and status code.

        The function verifies that a SimpleTemplateResponse instance with a specified MIME type
        ('application/json') and a non-standard HTTP status code (504) correctly includes these values
        in its HTTP response headers and status code, respectively.

        This test case ensures that the SimpleTemplateResponse class behaves as expected when
        constructing responses for scenarios requiring non-standard HTTP status codes and specific
        content types.
        """
        response = SimpleTemplateResponse("", {}, "application/json", 504)
        self.assertEqual(response.headers["content-type"], "application/json")
        self.assertEqual(response.status_code, 504)

    @require_jinja2
    def test_using(self):
        """

        Tests the rendering of templates using different template engines.

        This function verifies that templates can be rendered correctly with both 
        Django Template Language (DTL) and Jinja2 template engines. It checks 
        the output of a test template when rendered with the default engine, 
        as well as when explicitly set to use Django or Jinja2.

        The test ensures that the correct output is produced in each case, 
        demonstrating that the template rendering system is functioning as expected.

        """
        response = SimpleTemplateResponse("template_tests/using.html").render()
        self.assertEqual(response.content, b"DTL\n")
        response = SimpleTemplateResponse(
            "template_tests/using.html", using="django"
        ).render()
        self.assertEqual(response.content, b"DTL\n")
        response = SimpleTemplateResponse(
            "template_tests/using.html", using="jinja2"
        ).render()
        self.assertEqual(response.content, b"Jinja2\n")

    def test_post_callbacks(self):
        "Rendering a template response triggers the post-render callbacks"
        post = []

        def post1(obj):
            post.append("post1")

        def post2(obj):
            post.append("post2")

        response = SimpleTemplateResponse("first/test.html", {})
        response.add_post_render_callback(post1)
        response.add_post_render_callback(post2)

        # When the content is rendered, all the callbacks are invoked, too.
        response.render()
        self.assertEqual(response.content, b"First template\n")
        self.assertEqual(post, ["post1", "post2"])

    def test_pickling(self):
        # Create a template response. The context is
        # known to be unpicklable (e.g., a function).
        """
        Tests the pickling of a SimpleTemplateResponse object.

        Checks that attempting to pickle the response before it has been rendered raises
        a ContentNotRenderedError. After rendering the response, the test pickles and
        unpickles the response, verifying that the important attributes (content, headers,
        and status code) are preserved. Additionally, it ensures that certain template
        attributes are not present in the unpickled response to prevent accidental
        access to the template's internal state.

        Verifies the correct behavior of the response object after being pickled and
        unpickled, ensuring its integrity and usability in various scenarios.
        """
        response = SimpleTemplateResponse(
            "first/test.html",
            {
                "value": 123,
                "fn": datetime.now,
            },
        )
        with self.assertRaises(ContentNotRenderedError):
            pickle.dumps(response)

        # But if we render the response, we can pickle it.
        response.render()
        pickled_response = pickle.dumps(response)
        unpickled_response = pickle.loads(pickled_response)

        self.assertEqual(unpickled_response.content, response.content)
        self.assertEqual(
            unpickled_response.headers["content-type"], response.headers["content-type"]
        )
        self.assertEqual(unpickled_response.status_code, response.status_code)

        # ...and the unpickled response doesn't have the
        # template-related attributes, so it can't be re-rendered
        template_attrs = ("template_name", "context_data", "_post_render_callbacks")
        for attr in template_attrs:
            self.assertFalse(hasattr(unpickled_response, attr))

        # ...and requesting any of those attributes raises an exception
        for attr in template_attrs:
            with self.assertRaises(AttributeError):
                getattr(unpickled_response, attr)

    def test_repickling(self):
        response = SimpleTemplateResponse(
            "first/test.html",
            {
                "value": 123,
                "fn": datetime.now,
            },
        )
        with self.assertRaises(ContentNotRenderedError):
            pickle.dumps(response)

        response.render()
        pickled_response = pickle.dumps(response)
        unpickled_response = pickle.loads(pickled_response)
        pickle.dumps(unpickled_response)

    def test_pickling_cookie(self):
        """

        Tests that a cookie set on a response can be successfully pickled and unpickled.

        This test case verifies that the cookie's value is retained after the response object
        has been serialized and deserialized, ensuring that cookie data is preserved
        across different execution contexts.

        """
        response = SimpleTemplateResponse(
            "first/test.html",
            {
                "value": 123,
                "fn": datetime.now,
            },
        )

        response.cookies["key"] = "value"

        response.render()
        pickled_response = pickle.dumps(response, pickle.HIGHEST_PROTOCOL)
        unpickled_response = pickle.loads(pickled_response)

        self.assertEqual(unpickled_response.cookies["key"].value, "value")

    def test_headers(self):
        """
        Tests that custom HTTP headers are correctly set in a response when using the SimpleTemplateResponse class.

        The function verifies that a specific header, 'X-Foo', is included in the response with the expected value 'foo'. This ensures that the SimpleTemplateResponse class properly handles the headers parameter and includes custom headers in the response as intended.
        """
        response = SimpleTemplateResponse(
            "first/test.html",
            {"value": 123, "fn": datetime.now},
            headers={"X-Foo": "foo"},
        )
        self.assertEqual(response.headers["X-Foo"], "foo")


@override_settings(
    TEMPLATES=[
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "DIRS": [TEMPLATE_DIR],
            "OPTIONS": {
                "context_processors": [test_processor_name],
            },
        }
    ]
)
class TemplateResponseTest(SimpleTestCase):
    factory = RequestFactory()

    def _response(self, template="foo", *args, **kwargs):
        self._request = self.factory.get("/")
        template = engines["django"].from_string(template)
        return TemplateResponse(self._request, template, *args, **kwargs)

    def test_render(self):
        """
        Tests the render functionality of a template containing variables and processors.

        This test case verifies that the template is correctly rendered and the expected output is produced, 
        validating the function's ability to handle template variables and processors. 

        The test checks if the rendered content matches the expected result of 'yes'. 

        :raises AssertionError: If the rendered content does not match the expected output.
        """
        response = self._response("{{ foo }}{{ processors }}").render()
        self.assertEqual(response.content, b"yes")

    def test_render_with_requestcontext(self):
        response = self._response("{{ foo }}{{ processors }}", {"foo": "bar"}).render()
        self.assertEqual(response.content, b"baryes")

    def test_context_processor_priority(self):
        # context processors should be overridden by passed-in context
        """

        Tests the priority of context processors.

        This function evaluates the rendering of a template that includes two context variables: 'foo' and 'processors'.
        It checks that the rendering prioritizes the 'processors' context variable when both are present, resulting in 'no' as the output.

        """
        response = self._response(
            "{{ foo }}{{ processors }}", {"processors": "no"}
        ).render()
        self.assertEqual(response.content, b"no")

    def test_kwargs(self):
        """
        Tests the creation of a response object with keyword arguments.

        This test case verifies that the response object is correctly initialized with 
        the provided keyword arguments, specifically the content type and status code. 

        It checks that the 'Content-Type' header of the response is set to 'application/json' 
        and the status code is set to 504, indicating a Gateway Timeout error.

        The test ensures that the response object accurately reflects the provided 
        parameters, allowing for reliable testing of HTTP responses in different scenarios.
        """
        response = self._response(content_type="application/json", status=504)
        self.assertEqual(response.headers["content-type"], "application/json")
        self.assertEqual(response.status_code, 504)

    def test_args(self):
        response = TemplateResponse(
            self.factory.get("/"), "", {}, "application/json", 504
        )
        self.assertEqual(response.headers["content-type"], "application/json")
        self.assertEqual(response.status_code, 504)

    @require_jinja2
    def test_using(self):
        """
        Tests the rendering of templates using different template engines.

        This function verifies that a template can be rendered correctly with both the Django template engine and Jinja2.
        It checks that the rendered template content matches the expected output for each engine.

        The test covers the following scenarios:
        - Rendering a template without specifying a template engine (default engine)
        - Rendering a template using the Django template engine
        - Rendering a template using the Jinja2 template engine

        It ensures that the correct template engine is used and that the rendered content is as expected in each case.
        """
        request = self.factory.get("/")
        response = TemplateResponse(request, "template_tests/using.html").render()
        self.assertEqual(response.content, b"DTL\n")
        response = TemplateResponse(
            request, "template_tests/using.html", using="django"
        ).render()
        self.assertEqual(response.content, b"DTL\n")
        response = TemplateResponse(
            request, "template_tests/using.html", using="jinja2"
        ).render()
        self.assertEqual(response.content, b"Jinja2\n")

    def test_pickling(self):
        # Create a template response. The context is
        # known to be unpicklable (e.g., a function).
        """

        Tests the pickling of a TemplateResponse object.

        Verifies that attempting to pickle a TemplateResponse before rendering raises a ContentNotRenderedError.
        After rendering the response, it checks that the pickled and unpickled responses have the same content,
        headers, and status code. Additionally, it ensures that certain template-related attributes are not
        present in the unpickled response, as these are not intended to be preserved during the pickling process.

        """
        response = TemplateResponse(
            self.factory.get("/"),
            "first/test.html",
            {
                "value": 123,
                "fn": datetime.now,
            },
        )
        with self.assertRaises(ContentNotRenderedError):
            pickle.dumps(response)

        # But if we render the response, we can pickle it.
        response.render()
        pickled_response = pickle.dumps(response)
        unpickled_response = pickle.loads(pickled_response)

        self.assertEqual(unpickled_response.content, response.content)
        self.assertEqual(
            unpickled_response.headers["content-type"], response.headers["content-type"]
        )
        self.assertEqual(unpickled_response.status_code, response.status_code)

        # ...and the unpickled response doesn't have the
        # template-related attributes, so it can't be re-rendered
        template_attrs = (
            "template_name",
            "context_data",
            "_post_render_callbacks",
            "_request",
        )
        for attr in template_attrs:
            self.assertFalse(hasattr(unpickled_response, attr))

        # ...and requesting any of those attributes raises an exception
        for attr in template_attrs:
            with self.assertRaises(AttributeError):
                getattr(unpickled_response, attr)

    def test_repickling(self):
        """
        Tests that a response object can be successfully pickled after rendering its content.

        This test ensures that attempting to pickle a response before its content has been rendered raises a ContentNotRenderedError.
        It then verifies that the response can be pickled and unpickled correctly after rendering, and that the unpickled response can also be pickled without issues.

        The test covers the following scenarios:
        - Attempting to pickle an unrendered response
        - Pickling a rendered response
        - Unpickling the pickled response
        - Pickling the unpickled response
        """
        response = SimpleTemplateResponse(
            "first/test.html",
            {
                "value": 123,
                "fn": datetime.now,
            },
        )
        with self.assertRaises(ContentNotRenderedError):
            pickle.dumps(response)

        response.render()
        pickled_response = pickle.dumps(response)
        unpickled_response = pickle.loads(pickled_response)
        pickle.dumps(unpickled_response)

    def test_headers(self):
        """

        Tests the inclusion of custom HTTP headers in a view's response.

        Checks that a template response correctly sets a specified header, 
        in this case 'X-Foo', to the provided value 'foo'. This test verifies 
        that custom headers are properly included in the HTTP response.

        """
        response = TemplateResponse(
            self.factory.get("/"),
            "first/test.html",
            {"value": 123, "fn": datetime.now},
            headers={"X-Foo": "foo"},
        )
        self.assertEqual(response.headers["X-Foo"], "foo")


@modify_settings(
    MIDDLEWARE={"append": ["template_tests.test_response.custom_urlconf_middleware"]}
)
@override_settings(ROOT_URLCONF="template_tests.urls")
class CustomURLConfTest(SimpleTestCase):
    def test_custom_urlconf(self):
        """

        Tests the custom URL configuration by sending a GET request to the '/template_response_view/' URL 
        and verifying that the response contains the expected text 'This is where you can find the snark: /snark/'.

        This test ensures that the custom URL configuration correctly maps to the desired view 
        and that the view returns the expected response.

        """
        response = self.client.get("/template_response_view/")
        self.assertContains(response, "This is where you can find the snark: /snark/")


@modify_settings(
    MIDDLEWARE={
        "append": [
            "django.middleware.cache.FetchFromCacheMiddleware",
            "django.middleware.cache.UpdateCacheMiddleware",
        ],
    },
)
@override_settings(
    CACHE_MIDDLEWARE_SECONDS=2, ROOT_URLCONF="template_tests.alternate_urls"
)
class CacheMiddlewareTest(SimpleTestCase):
    def test_middleware_caching(self):
        response = self.client.get("/template_response_view/")
        self.assertEqual(response.status_code, 200)

        time.sleep(1.0)

        response2 = self.client.get("/template_response_view/")
        self.assertEqual(response2.status_code, 200)

        self.assertEqual(response.content, response2.content)

        time.sleep(2.0)

        # Let the cache expire and test again
        response2 = self.client.get("/template_response_view/")
        self.assertEqual(response2.status_code, 200)

        self.assertNotEqual(response.content, response2.content)
