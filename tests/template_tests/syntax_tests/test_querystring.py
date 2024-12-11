from django.http import QueryDict
from django.template import RequestContext
from django.test import RequestFactory, SimpleTestCase

from ..utils import setup


class QueryStringTagTests(SimpleTestCase):
    def setUp(self):
        self.request_factory = RequestFactory()

    @setup({"querystring_empty": "{% querystring %}"})
    def test_querystring_empty(self):
        """
        Tests if rendering a template with a querystring tag results in an empty string when the query string is empty. 

        The test case covers the scenario where the query string is not present in the request, 
        verifying that the template engine correctly handles this edge case and produces the expected output.
        """
        request = self.request_factory.get("/")
        template = self.engine.get_template("querystring_empty")
        context = RequestContext(request)
        output = template.render(context)
        self.assertEqual(output, "")

    @setup({"querystring_non_empty": "{% querystring %}"})
    def test_querystring_non_empty(self):
        request = self.request_factory.get("/", {"a": "b"})
        template = self.engine.get_template("querystring_non_empty")
        context = RequestContext(request)
        output = template.render(context)
        self.assertEqual(output, "?a=b")

    @setup({"querystring_multiple": "{% querystring %}"})
    def test_querystring_multiple(self):
        """

        Tests the rendering of a template that contains a query string with multiple parameters.

        This test case verifies that the query string is correctly formatted and escaped
        when multiple parameters are present. It checks that the output matches the expected
        format of '?key1=value1&amp;key2=value2'.

        The test uses a sample request with a query string containing two parameters, 'x' and 'a',
        and checks that the rendered template output matches the expected result.

        """
        request = self.request_factory.get("/", {"x": "y", "a": "b"})
        template = self.engine.get_template("querystring_multiple")
        context = RequestContext(request)
        output = template.render(context)
        self.assertEqual(output, "?x=y&amp;a=b")

    @setup({"querystring_replace": "{% querystring a=1 %}"})
    def test_querystring_replace(self):
        """

        Tests the query string replacement functionality in template rendering.

        This test case verifies that the query string replacement mechanism correctly
        replaces values in the query string with new values specified in the template.
        The test uses a sample template that replaces the value of the 'a' parameter
        in the query string with '1' and checks if the rendered output matches the
        expected query string.

        The test covers the scenario where the original query string contains the
        parameter to be replaced, as well as other parameters that should remain
        unchanged in the output.

        """
        request = self.request_factory.get("/", {"x": "y", "a": "b"})
        template = self.engine.get_template("querystring_replace")
        context = RequestContext(request)
        output = template.render(context)
        self.assertEqual(output, "?x=y&amp;a=1")

    @setup({"querystring_add": "{% querystring test_new='something' %}"})
    def test_querystring_add(self):
        """

        Tests the addition of a query string parameter to an existing URL.

        This test case verifies that the querystring add functionality correctly appends
        a new key-value pair to the query string of a request, ensuring proper URL encoding.

        The test checks the output against an expected result, confirming that the query
        string parameters are correctly added and escaped.

        """
        request = self.request_factory.get("/", {"a": "b"})
        template = self.engine.get_template("querystring_add")
        context = RequestContext(request)
        output = template.render(context)
        self.assertEqual(output, "?a=b&amp;test_new=something")

    @setup({"querystring_remove": "{% querystring test=None a=1 %}"})
    def test_querystring_remove(self):
        request = self.request_factory.get("/", {"test": "value", "a": "1"})
        template = self.engine.get_template("querystring_remove")
        context = RequestContext(request)
        output = template.render(context)
        self.assertEqual(output, "?a=1")

    @setup({"querystring_remove_nonexistent": "{% querystring nonexistent=None a=1 %}"})
    def test_querystring_remove_nonexistent(self):
        request = self.request_factory.get("/", {"x": "y", "a": "1"})
        template = self.engine.get_template("querystring_remove_nonexistent")
        context = RequestContext(request)
        output = template.render(context)
        self.assertEqual(output, "?x=y&amp;a=1")

    @setup({"querystring_list": "{% querystring a=my_list %}"})
    def test_querystring_add_list(self):
        request = self.request_factory.get("/")
        template = self.engine.get_template("querystring_list")
        context = RequestContext(request, {"my_list": [2, 3]})
        output = template.render(context)
        self.assertEqual(output, "?a=2&amp;a=3")

    @setup({"querystring_query_dict": "{% querystring request.GET a=2 %}"})
    def test_querystring_with_explicit_query_dict(self):
        """
        Tests rendering of a querystring using an explicit query dictionary.

        This test case verifies that the querystring template tag can render a querystring
        from a predefined dictionary, overriding any existing query parameters from the
        request object. It checks if the resulting querystring matches the expected output.

        :returns: None
        :raises: AssertionError if the rendered querystring does not match the expected output
        """
        request = self.request_factory.get("/", {"a": 1})
        output = self.engine.render_to_string(
            "querystring_query_dict", {"request": request}
        )
        self.assertEqual(output, "?a=2")

    @setup({"querystring_query_dict_no_request": "{% querystring my_query_dict a=2 %}"})
    def test_querystring_with_explicit_query_dict_and_no_request(self):
        """
        Tests the querystring template tag with an explicit query dictionary and without a request object.

        Verifies that the template tag correctly merges the query parameters from the provided dictionary and the ones specified in the tag, and that the output is properly URL-encoded.

        The expected output is a URL query string that includes both the original and overridden query parameters.

        """
        context = {"my_query_dict": QueryDict("a=1&b=2")}
        output = self.engine.render_to_string(
            "querystring_query_dict_no_request", context
        )
        self.assertEqual(output, "?a=2&amp;b=2")

    @setup({"querystring_no_request_no_query_dict": "{% querystring %}"})
    def test_querystring_without_request_or_explicit_query_dict(self):
        msg = "'Context' object has no attribute 'request'"
        with self.assertRaisesMessage(AttributeError, msg):
            self.engine.render_to_string("querystring_no_request_no_query_dict")
