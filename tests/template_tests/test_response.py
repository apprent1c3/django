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
    def middleware(request):
        """
        Middleware function to modify the URL configuration for a given request.

        This function overrides the default URL configuration by setting the urlconf attribute
        of the request object to 'template_tests.alternate_urls'. It then passes the modified
        request to the next middleware or view in the chain by calling get_response.

        Using this middleware allows for alternate URL routing to be applied to specific
        requests, enabling more flexible and dynamic URL handling in the application.

        :param request: The current HTTP request object
        :return: The response from the next middleware or view in the chain
        """
        request.urlconf = "template_tests.alternate_urls"
        return get_response(request)

    return middleware


class SimpleTemplateResponseTest(SimpleTestCase):
    def _response(self, template="foo", *args, **kwargs):
        """
        Returns a SimpleTemplateResponse object based on a provided template and arguments.

        The template can be a string representation of a Django template. The function uses the Django template engine to render the template.

        Parameters
        ----------
        template : str, optional
            A string representation of a Django template (default is 'foo').
        *args
            Variable length argument list to be passed to the SimpleTemplateResponse object.
        **kwargs
            Arbitrary keyword arguments to be passed to the SimpleTemplateResponse object.

        Returns
        -------
        SimpleTemplateResponse
            A response object with the rendered template.
        Note
        ----
        This function is intended for internal use, as indicated by the leading underscore in its name.
        """
        template = engines["django"].from_string(template)
        return SimpleTemplateResponse(template, *args, **kwargs)

    def test_template_resolving(self):
        """

        Tests the resolving of templates in the :class:`SimpleTemplateResponse` class.

        This test case covers the scenario where a single template is provided, as well as
        when multiple templates are given. The test verifies that the correct template is
        resolved and rendered, even when multiple templates with the same name are found
        in different directories. The test also checks the rendering of templates with
        different contents.

        The test consists of three main parts:

        1.  Resolving a single template
        2.  Resolving multiple templates with the same name in different directories
        3.  Rendering a template with a custom response object

        The expected output of each rendering is verified to ensure that the correct
        template is being used.

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
        Tests the rendering of a response object by verifying its content under different conditions.

         The function checks if the initial rendering of the response produces the expected content.
         It then modifies the response's template and re-renders, checking if the new template is ignored when rendering.
         Finally, it tests if manually setting the response content overrides any rendering results.
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
        response = self._response(
            content_type="application/json", status=504, charset="ascii"
        )
        self.assertEqual(response.headers["content-type"], "application/json")
        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.charset, "ascii")

    def test_args(self):
        response = SimpleTemplateResponse("", {}, "application/json", 504)
        self.assertEqual(response.headers["content-type"], "application/json")
        self.assertEqual(response.status_code, 504)

    @require_jinja2
    def test_using(self):
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
        Tests the ability to pickle and unpickle a response object that contains a cookie.

        Verifies that a response with a cookie can be successfully serialized using the pickle module,
        and that the cookie's value is preserved after deserialization.

        Checks that the cookie's value is correctly restored after the pickling and unpickling process,
        ensuring that the cookie remains intact and functional throughout the serialization process.
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
        """

        Return a TemplateResponse instance using the provided template string.

        The template string is rendered using the Django template engine. 
        You can pass additional positional and keyword arguments to customize the response.

        :param template: A string representing the template to be rendered (defaults to 'foo')
        :param args: Additional positional arguments to be passed to the TemplateResponse constructor
        :param kwargs: Additional keyword arguments to be passed to the TemplateResponse constructor
        :return: A TemplateResponse instance

        """
        self._request = self.factory.get("/")
        template = engines["django"].from_string(template)
        return TemplateResponse(self._request, template, *args, **kwargs)

    def test_render(self):
        """
        Tests the rendering of a template with variables.

        This test case verifies that the template engine correctly replaces placeholders with
        their corresponding values, resulting in the expected output content. The test checks
        for the presence of specific variables ('foo' and 'processors') in the rendered response
        and asserts that the rendered content is as expected.
        """
        response = self._response("{{ foo }}{{ processors }}").render()
        self.assertEqual(response.content, b"yes")

    def test_render_with_requestcontext(self):
        response = self._response("{{ foo }}{{ processors }}", {"foo": "bar"}).render()
        self.assertEqual(response.content, b"baryes")

    def test_context_processor_priority(self):
        # context processors should be overridden by passed-in context
        response = self._response(
            "{{ foo }}{{ processors }}", {"processors": "no"}
        ).render()
        self.assertEqual(response.content, b"no")

    def test_kwargs(self):
        """
        Tests response object initialization with keyword arguments.

        Verifies that the response object is correctly created with the specified content type and status code.
        The function checks if the 'content-type' header and the status code of the response match the expected values.

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
        Tests the repickling of a SimpleTemplateResponse object after it has been rendered.

        This test ensures that the object can be successfully pickled and unpickled after rendering, 
        while also verifying that it cannot be pickled before rendering.

        The test case covers the following scenarios:
            - Attempting to pickle the response before rendering, which should raise a ContentNotRenderedError.
            - Rendering the response and then pickling it, which should be successful.
            - Unpickling the pickled response and then pickling it again, which should also be successful.

        The goal of this test is to ensure that the SimpleTemplateResponse object behaves correctly 
        when it comes to pickling and rendering, which is essential for certain use cases such as caching 
        or storing the response for later use.
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
