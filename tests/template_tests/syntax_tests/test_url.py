from django.template import RequestContext, TemplateSyntaxError
from django.template.defaulttags import URLNode
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import NoReverseMatch, resolve

from ..utils import setup


@override_settings(ROOT_URLCONF="template_tests.urls")
class UrlTagTests(SimpleTestCase):
    request_factory = RequestFactory()

    # Successes
    @setup({"url01": '{% url "client" client.id %}'})
    def test_url01(self):
        output = self.engine.render_to_string("url01", {"client": {"id": 1}})
        self.assertEqual(output, "/client/1/")

    @setup({"url02": '{% url "client_action" id=client.id action="update" %}'})
    def test_url02(self):
        output = self.engine.render_to_string("url02", {"client": {"id": 1}})
        self.assertEqual(output, "/client/1/update/")

    @setup({"url02a": '{% url "client_action" client.id "update" %}'})
    def test_url02a(self):
        """
        Tests the correct rendering of a specific URL pattern.

        This test case verifies that the URL for updating a client is generated correctly.
        It checks if the rendered URL matches the expected output when a client's ID is provided.
        The expected URL pattern is in the format '/client/{id}/update/', where '{id}' is the client's ID.
        The test ensures that the URL template is correctly replaced with the actual client ID, resulting in a valid URL for updating the client's information.
        """
        output = self.engine.render_to_string("url02a", {"client": {"id": 1}})
        self.assertEqual(output, "/client/1/update/")

    @setup({"url02b": "{% url 'client_action' id=client.id action='update' %}"})
    def test_url02b(self):
        output = self.engine.render_to_string("url02b", {"client": {"id": 1}})
        self.assertEqual(output, "/client/1/update/")

    @setup({"url02c": "{% url 'client_action' client.id 'update' %}"})
    def test_url02c(self):
        output = self.engine.render_to_string("url02c", {"client": {"id": 1}})
        self.assertEqual(output, "/client/1/update/")

    @setup({"url03": '{% url "index" %}'})
    def test_url03(self):
        """
        Tests the rendering of a template containing a URL tag with a named URL pattern 'index' using the 'engine.render_to_string' method, verifying that the output matches the expected URL '/'.
        """
        output = self.engine.render_to_string("url03")
        self.assertEqual(output, "/")

    @setup({"url04": '{% url "named.client" client.id %}'})
    def test_url04(self):
        """
        Tests the rendering of a URL template string with a named client URL, 
         verifying that it correctly substitutes the client ID into the URL.
        """
        output = self.engine.render_to_string("url04", {"client": {"id": 1}})
        self.assertEqual(output, "/named-client/1/")

    @setup({"url05": '{% url "метка_оператора" v %}'})
    def test_url05(self):
        """
        Test a URL rendering template tag with a non-ASCII parameter value.

        This test case checks if the template engine correctly renders a URL pattern
        when the URL parameter contains a non-ASCII character, such as the Greek letter Omega (Ω).
        It verifies that the rendered URL is properly URL-encoded to ensure correct
        processing by web servers and browsers.
        """
        output = self.engine.render_to_string("url05", {"v": "Ω"})
        self.assertEqual(output, "/%D0%AE%D0%BD%D0%B8%D0%BA%D0%BE%D0%B4/%CE%A9/")

    @setup({"url06": '{% url "метка_оператора_2" tag=v %}'})
    def test_url06(self):
        output = self.engine.render_to_string("url06", {"v": "Ω"})
        self.assertEqual(output, "/%D0%AE%D0%BD%D0%B8%D0%BA%D0%BE%D0%B4/%CE%A9/")

    @setup({"url08": '{% url "метка_оператора" v %}'})
    def test_url08(self):
        """
        Tests the rendering of a URL template tag with a non-ASCII parameter value.
        Checks that the output of the template rendering is a correctly URL-encoded string.
        The test uses a template with a URL tag referencing a named URL pattern, passing a non-ASCII value as a parameter.
        Verifies that the resulting URL is properly encoded to handle special characters.
        """
        output = self.engine.render_to_string("url08", {"v": "Ω"})
        self.assertEqual(output, "/%D0%AE%D0%BD%D0%B8%D0%BA%D0%BE%D0%B4/%CE%A9/")

    @setup({"url09": '{% url "метка_оператора_2" tag=v %}'})
    def test_url09(self):
        output = self.engine.render_to_string("url09", {"v": "Ω"})
        self.assertEqual(output, "/%D0%AE%D0%BD%D0%B8%D0%BA%D0%BE%D0%B4/%CE%A9/")

    @setup({"url10": '{% url "client_action" id=client.id action="two words" %}'})
    def test_url10(self):
        output = self.engine.render_to_string("url10", {"client": {"id": 1}})
        self.assertEqual(output, "/client/1/two%20words/")

    @setup({"url11": '{% url "client_action" id=client.id action="==" %}'})
    def test_url11(self):
        output = self.engine.render_to_string("url11", {"client": {"id": 1}})
        self.assertEqual(output, "/client/1/==/")

    @setup(
        {"url12": '{% url "client_action" id=client.id action="!$&\'()*+,;=~:@," %}'}
    )
    def test_url12(self):
        output = self.engine.render_to_string("url12", {"client": {"id": 1}})
        self.assertEqual(output, "/client/1/!$&amp;&#x27;()*+,;=~:@,/")

    @setup({"url13": '{% url "client_action" id=client.id action=arg|join:"-" %}'})
    def test_url13(self):
        output = self.engine.render_to_string(
            "url13", {"client": {"id": 1}, "arg": ["a", "b"]}
        )
        self.assertEqual(output, "/client/1/a-b/")

    @setup({"url14": '{% url "client_action" client.id arg|join:"-" %}'})
    def test_url14(self):
        output = self.engine.render_to_string(
            "url14", {"client": {"id": 1}, "arg": ["a", "b"]}
        )
        self.assertEqual(output, "/client/1/a-b/")

    @setup({"url15": '{% url "client_action" 12 "test" %}'})
    def test_url15(self):
        output = self.engine.render_to_string("url15")
        self.assertEqual(output, "/client/12/test/")

    @setup({"url18": '{% url "client" "1,2" %}'})
    def test_url18(self):
        """
        Tests that the URL template tag renders the correct URL path for a client view.

        The test verifies that the rendered URL matches the expected path of '/client/<id1>,<id2>/' when provided with the parameters '1,2'. 

        It ensures that the 'url' template tag is functioning correctly and returns the expected URL.
        """
        output = self.engine.render_to_string("url18")
        self.assertEqual(output, "/client/1,2/")

    @setup({"url19": "{% url named_url client.id %}"})
    def test_url19(self):
        """

        Tests the rendering of a URL template string with a named URL and a client ID.

        This test case verifies that the 'url19' template can correctly render a URL
        by replacing the 'named_url' and 'client.id' placeholders with the actual values.
        The test expects the rendered output to match the expected URL format.

        The test provides a dictionary with 'client' and 'named_url' as input data, and
        asserts that the rendered string is equal to the expected URL '/client/1/'.

        """
        output = self.engine.render_to_string(
            "url19", {"client": {"id": 1}, "named_url": "client"}
        )
        self.assertEqual(output, "/client/1/")

    @setup({"url20": "{% url url_name_in_var client.id %}"})
    def test_url20(self):
        """
        Tests rendering of URLs with URL names stored in variables.

        This test case verifies that the templating engine can correctly render URLs 
        when the URL name is passed as a variable, and then uses this rendered URL 
        to assert that it matches an expected output, ensuring the correct 
        functionality of the URL rendering mechanism.
        """
        output = self.engine.render_to_string(
            "url20", {"client": {"id": 1}, "url_name_in_var": "named.client"}
        )
        self.assertEqual(output, "/named-client/1/")

    @setup(
        {
            "url21": "{% autoescape off %}"
            '{% url "client_action" id=client.id action="!$&\'()*+,;=~:@," %}'
            "{% endautoescape %}"
        }
    )
    def test_url21(self):
        """

        Tests the rendering of a URL in a template with special characters.

        The URL is generated using the 'client_action' template tag, with a client ID and an action string that contains special characters.
        The expected output is compared to the actual rendered URL to ensure correct rendering.

        The test covers URL encoding and special character handling, verifying that the rendered URL is as expected.

        """
        output = self.engine.render_to_string("url21", {"client": {"id": 1}})
        self.assertEqual(output, "/client/1/!$&'()*+,;=~:@,/")

    # Failures
    @setup({"url-fail01": "{% url %}"})
    def test_url_fail01(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("url-fail01")

    @setup({"url-fail02": '{% url "no_such_view" %}'})
    def test_url_fail02(self):
        """

        Tests that the template engine correctly handles a template that contains a URL tag referencing a non-existent view.

        Raises:
            NoReverseMatch: The expected exception when the template engine encounters a URL tag that cannot be reversed.

        """
        with self.assertRaises(NoReverseMatch):
            self.engine.render_to_string("url-fail02")

    @setup({"url-fail03": '{% url "client" %}'})
    def test_url_fail03(self):
        with self.assertRaises(NoReverseMatch):
            self.engine.render_to_string("url-fail03")

    @setup({"url-fail04": '{% url "view" id, %}'})
    def test_url_fail04(self):
        """
        Tests that the template engine raises a TemplateSyntaxError when the url tag is used with a syntax error, specifically a missing closing quote after the view name and an incomplete argument list.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("url-fail04")

    @setup({"url-fail05": '{% url "view" id= %}'})
    def test_url_fail05(self):
        """
        Tests that a TemplateSyntaxError is raised when the url template tag 
        is used with a missing required argument 'id' in the 'view' URL pattern.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("url-fail05")

    @setup({"url-fail06": '{% url "view" a.id=id %}'})
    def test_url_fail06(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("url-fail06")

    @setup({"url-fail07": '{% url "view" a.id!id %}'})
    def test_url_fail07(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("url-fail07")

    @setup({"url-fail08": '{% url "view" id="unterminatedstring %}'})
    def test_url_fail08(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("url-fail08")

    @setup({"url-fail09": '{% url "view" id=", %}'})
    def test_url_fail09(self):
        """
        Raises a TemplateSyntaxError when a malformed url template tag is used.

        The test case verifies that the templating engine correctly handles and raises an exception for a url template tag with a missing argument, specifically when the \"id\" parameter is not properly defined.

        This check ensures that the templating engine behaves as expected and reports a syntax error when the url template tag is not correctly formatted.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("url-fail09")

    @setup({"url-fail11": "{% url named_url %}"})
    def test_url_fail11(self):
        with self.assertRaises(NoReverseMatch):
            self.engine.render_to_string("url-fail11")

    @setup({"url-fail12": "{% url named_url %}"})
    def test_url_fail12(self):
        with self.assertRaises(NoReverseMatch):
            self.engine.render_to_string("url-fail12", {"named_url": "no_such_view"})

    @setup({"url-fail13": "{% url named_url %}"})
    def test_url_fail13(self):
        with self.assertRaises(NoReverseMatch):
            self.engine.render_to_string(
                "url-fail13", {"named_url": "template_tests.views.client"}
            )

    @setup({"url-fail14": "{% url named_url id, %}"})
    def test_url_fail14(self):
        """

        Test that rendering a template with a malformed url tag raises a TemplateSyntaxError.

        In particular, this test checks that a url tag with a syntax error (missing closing bracket) 
        in its arguments causes the expected exception to be raised.

        The test simulates a template with a url tag referencing a named URL, 
        then verifies that attempting to render this template results in a TemplateSyntaxError.

        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("url-fail14", {"named_url": "view"})

    @setup({"url-fail15": "{% url named_url id= %}"})
    def test_url_fail15(self):
        """
        Test that template rendering fails with a TemplateSyntaxError when the url template tag is used with incorrect syntax, specifically missing a required 'id' argument.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("url-fail15", {"named_url": "view"})

    @setup({"url-fail16": "{% url named_url a.id=id %}"})
    def test_url_fail16(self):
        """
        Raises a TemplateSyntaxError when attempting to render a template string containing a malformed url tag with a named URL and an argument id that is assigned incorrectly using '=' instead of 'as'.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("url-fail16", {"named_url": "view"})

    @setup({"url-fail17": "{% url named_url a.id!id %}"})
    def test_url_fail17(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("url-fail17", {"named_url": "view"})

    @setup({"url-fail18": '{% url named_url id="unterminatedstring %}'})
    def test_url_fail18(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("url-fail18", {"named_url": "view"})

    @setup({"url-fail19": '{% url named_url id=", %}'})
    def test_url_fail19(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("url-fail19", {"named_url": "view"})

    # {% url ... as var %}
    @setup({"url-asvar01": '{% url "index" as url %}'})
    def test_url_asvar01(self):
        output = self.engine.render_to_string("url-asvar01")
        self.assertEqual(output, "")

    @setup({"url-asvar02": '{% url "index" as url %}{{ url }}'})
    def test_url_asvar02(self):
        output = self.engine.render_to_string("url-asvar02")
        self.assertEqual(output, "/")

    @setup({"url-asvar03": '{% url "no_such_view" as url %}{{ url }}'})
    def test_url_asvar03(self):
        output = self.engine.render_to_string("url-asvar03")
        self.assertEqual(output, "")

    @setup({"url-namespace01": '{% url "app:named.client" 42 %}'})
    def test_url_namespace01(self):
        """

        Tests URL resolution with a custom namespace.

        This test case verifies that the 'url' template tag correctly resolves URLs
        when a namespace is provided. It checks that the URL for a named client
        within the namespace 'ns1' is rendered as expected.

        The test uses a predefined URL pattern and a template with the 'url' tag
        to generate the URL. It then compares the rendered output with the expected
        result.

        """
        request = self.request_factory.get("/")
        request.resolver_match = resolve("/ns1/")
        template = self.engine.get_template("url-namespace01")
        context = RequestContext(request)
        output = template.render(context)
        self.assertEqual(output, "/ns1/named-client/42/")

    @setup({"url-namespace02": '{% url "app:named.client" 42 %}'})
    def test_url_namespace02(self):
        request = self.request_factory.get("/")
        request.resolver_match = resolve("/ns2/")
        template = self.engine.get_template("url-namespace02")
        context = RequestContext(request)
        output = template.render(context)
        self.assertEqual(output, "/ns2/named-client/42/")

    @setup({"url-namespace03": '{% url "app:named.client" 42 %}'})
    def test_url_namespace03(self):
        request = self.request_factory.get("/")
        template = self.engine.get_template("url-namespace03")
        context = RequestContext(request)
        output = template.render(context)
        self.assertEqual(output, "/ns2/named-client/42/")

    @setup({"url-namespace-no-current-app": '{% url "app:named.client" 42 %}'})
    def test_url_namespace_no_current_app(self):
        """

        Tests the URL namespace resolution when there is no current application set.

        Verifies that the URL template tag correctly handles URL namespaces
        when the current application is None. In this scenario, the tag should
        still be able to reverse URLs using the provided namespace and view name.
        The test checks if the rendered template matches the expected output URL.

        """
        request = self.request_factory.get("/")
        request.resolver_match = resolve("/ns1/")
        request.current_app = None
        template = self.engine.get_template("url-namespace-no-current-app")
        context = RequestContext(request)
        output = template.render(context)
        self.assertEqual(output, "/ns2/named-client/42/")

    @setup({"url-namespace-explicit-current-app": '{% url "app:named.client" 42 %}'})
    def test_url_namespace_explicit_current_app(self):
        """

        Tests the resolution of a namespaced URL with an explicit current app.

        The test case verifies that the 'url' template tag can correctly generate a URL 
        for a view named 'named.client' within a namespace, when the current app is 
        explicitly specified.

        It checks that the URL resolution takes into account the current app and 
        namespace, and that the resulting URL is correctly rendered in the template. 
        The test asserts that the rendered URL matches the expected output.

        """
        request = self.request_factory.get("/")
        request.resolver_match = resolve("/ns1/")
        request.current_app = "app"
        template = self.engine.get_template("url-namespace-explicit-current-app")
        context = RequestContext(request)
        output = template.render(context)
        self.assertEqual(output, "/ns2/named-client/42/")


class URLNodeTest(SimpleTestCase):
    def test_repr(self):
        url_node = URLNode(view_name="named-view", args=[], kwargs={}, asvar=None)
        self.assertEqual(
            repr(url_node),
            "<URLNode view_name='named-view' args=[] kwargs={} as=None>",
        )
        url_node = URLNode(
            view_name="named-view",
            args=[1, 2],
            kwargs={"action": "update"},
            asvar="my_url",
        )
        self.assertEqual(
            repr(url_node),
            "<URLNode view_name='named-view' args=[1, 2] "
            "kwargs={'action': 'update'} as='my_url'>",
        )
