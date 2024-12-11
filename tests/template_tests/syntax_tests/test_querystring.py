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
        Tests that the querystring template tag returns an empty string when the request query string is empty. 

        This test case verifies the expected behavior of the querystring template tag when there are no query parameters in the request URL, ensuring that it correctly handles this edge case and returns the expected output.
        """
        request = self.request_factory.get("/")
        template = self.engine.get_template("querystring_empty")
        context = RequestContext(request)
        output = template.render(context)
        self.assertEqual(output, "")

    @setup({"querystring_non_empty": "{% querystring %}"})
    def test_querystring_non_empty(self):
        """

        Tests that a template correctly renders a query string when it is not empty.

        This test case verifies that the query string is properly formatted and
        includes all key-value pairs from the request. The expected output is a
        string in the format '?key=value', where 'key' and 'value' are the key-value
        pairs from the request query string.

        """
        request = self.request_factory.get("/", {"a": "b"})
        template = self.engine.get_template("querystring_non_empty")
        context = RequestContext(request)
        output = template.render(context)
        self.assertEqual(output, "?a=b")

    @setup({"querystring_multiple": "{% querystring %}"})
    def test_querystring_multiple(self):
        """

        Tests the rendering of a template that handles multiple query string parameters.

        The test case verifies that the template engine correctly parses and formats 
        multiple query string parameters into a URL query string, ensuring proper 
        escaping and concatenation of the parameters.

        The expected output is a query string in the format of '?key1=value1&amp;key2=value2'.

        """
        request = self.request_factory.get("/", {"x": "y", "a": "b"})
        template = self.engine.get_template("querystring_multiple")
        context = RequestContext(request)
        output = template.render(context)
        self.assertEqual(output, "?x=y&amp;a=b")

    @setup({"querystring_replace": "{% querystring a=1 %}"})
    def test_querystring_replace(self):
        request = self.request_factory.get("/", {"x": "y", "a": "b"})
        template = self.engine.get_template("querystring_replace")
        context = RequestContext(request)
        output = template.render(context)
        self.assertEqual(output, "?x=y&amp;a=1")

    @setup({"querystring_add": "{% querystring test_new='something' %}"})
    def test_querystring_add(self):
        """
        Test that the querystring template tag adds new parameters to the current query string.

        This test case checks if the querystring tag correctly appends a new query parameter to the existing query string in a URL. The expected output is a query string with the original parameters plus the new parameter added by the template tag.
        """
        request = self.request_factory.get("/", {"a": "b"})
        template = self.engine.get_template("querystring_add")
        context = RequestContext(request)
        output = template.render(context)
        self.assertEqual(output, "?a=b&amp;test_new=something")

    @setup({"querystring_remove": "{% querystring test=None a=1 %}"})
    def test_querystring_remove(self):
        """

        Tests the removal of query string parameters using the querystring template tag.

        This test case verifies that the querystring tag correctly removes specified
        parameters from the current URL's query string. The test checks that the
        'test' parameter is removed while the 'a' parameter is preserved, resulting
        in the expected output '?a=1'.

        """
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
        request = self.request_factory.get("/", {"a": 1})
        output = self.engine.render_to_string(
            "querystring_query_dict", {"request": request}
        )
        self.assertEqual(output, "?a=2")

    @setup({"querystring_query_dict_no_request": "{% querystring my_query_dict a=2 %}"})
    def test_querystring_with_explicit_query_dict_and_no_request(self):
        """
        Tests the querystring template tag with an explicit query dictionary and no request object.

        This test ensures that the querystring template tag correctly handles a query dictionary
        and a set of query parameters to be overridden, returning a URL query string.

        The test verifies that the resulting query string contains all the expected query parameters,
        both from the original query dictionary and the overridden parameters.

        The expected output is a URL query string that includes all query parameters, with any
        special characters properly escaped, such as ampersands (&) replaced with their HTML
        entity equivalents (&amp;).
        """
        context = {"my_query_dict": QueryDict("a=1&b=2")}
        output = self.engine.render_to_string(
            "querystring_query_dict_no_request", context
        )
        self.assertEqual(output, "?a=2&amp;b=2")

    @setup({"querystring_no_request_no_query_dict": "{% querystring %}"})
    def test_querystring_without_request_or_explicit_query_dict(self):
        """
        Test case to verify the behavior of rendering querystring without an explicit request or query dictionary.

        This test ensures that attempting to render a template using querystring without providing a request or query dictionary raises an AttributeError, as expected.

        The test validates the error message to confirm that it is related to the 'Context' object lacking a 'request' attribute, which is the root cause of the issue.

        The purpose of this test is to guarantee the correct error handling and messaging when using querystring in scenarios where the required context is not properly set up.
        """
        msg = "'Context' object has no attribute 'request'"
        with self.assertRaisesMessage(AttributeError, msg):
            self.engine.render_to_string("querystring_no_request_no_query_dict")
