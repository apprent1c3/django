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
        request.urlconf = "template_tests.alternate_urls"
        return get_response(request)

    return middleware


class SimpleTemplateResponseTest(SimpleTestCase):
    def _response(self, template="foo", *args, **kwargs):
        template = engines["django"].from_string(template)
        return SimpleTemplateResponse(template, *args, **kwargs)

    def test_template_resolving(self):
        """
        Checks the template resolving functionality of the SimpleTemplateResponse class, verifying that it correctly selects and renders the first available template from a given list.
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
        Tests the rendering of a response, verifying that the content is rendered correctly from a Django template and that the content attribute can be set manually.
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
        Tests that attempting to iterate over an unrendered response raises a ContentNotRenderedError, ensuring the response content is rendered before it can be iterated over.
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
        Tests that accessing the content of an unrendered response raises an error and does not render the response.
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

        Verifies correct behavior of response content manipulation.

        Tests setting and updating of content in a response, ensuring that the
        is_rendered flag is correctly updated and the content is properly stored.

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
        """

        Verifies the functionality of template rendering with different template engines.

        Tests the rendering of a template using the default template engine and the 'django' and 'jinja2' engines, 
        ensuring the expected output is produced in each case.

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
        """
        Tests that rendering a template response triggers all registered post-render callbacks in the correct order
        """
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
        Tests that a SimpleTemplateResponse can be pickled after rendering, but not before.

        The test ensures that pickling a response before rendering raises a ContentNotRenderedError,
        and that after rendering, the response can be pickled and unpickled without losing data,
        while also verifying that certain template attributes are not retained after unpickling.
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
        """
        Tests the repickling of a SimpleTemplateResponse object, ensuring that it can be successfully pickled after rendering, but raises an error if attempted before rendering.
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

    def test_pickling_cookie(self):
        """
        Tests the ability to pickle and unpickle a response object containing a cookie, ensuring the cookie's value is preserved through the serialization process.
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
        self._request = self.factory.get("/")
        template = engines["django"].from_string(template)
        return TemplateResponse(self._request, template, *args, **kwargs)

    def test_render(self):
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
        Tests template rendering using different engine backends. 

        Verifies that a template can be rendered correctly with both Django template language (DTL) and Jinja2 templating engines, ensuring proper output for each case.
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

        Ensures that a TemplateResponse cannot be pickled before it is rendered,
        and that after rendering, it can be successfully pickled and unpickled
        with all relevant attributes preserved, while sensitive template attributes
        are discarded.

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
        Tests that a SimpleTemplateResponse can be pickled after rendering, but raises an exception if attempted before rendering, and that the pickled and unpickled response can also be pickled again.
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
        """
        Tests the caching behavior of middleware by making multiple requests to a view and verifying the response contents are the same when cached and different when the cache is expired.
        """
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
