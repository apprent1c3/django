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
        """

        Tests the rendering of a URL in a template using the 'url' template tag.

        This test case checks that the 'url' template tag correctly generates a URL
        for a client object, and that the rendered URL matches the expected format.

        The test renders a template string containing the 'url' template tag with a
        .client object, and then asserts that the output matches the expected URL path.

        """
        output = self.engine.render_to_string("url01", {"client": {"id": 1}})
        self.assertEqual(output, "/client/1/")

    @setup({"url02": '{% url "client_action" id=client.id action="update" %}'})
    def test_url02(self):
        """

        Tests the rendering of a URL template string with a client ID and action.

        This test case verifies that the template engine correctly renders the 'client_action' URL
        with the provided client ID and action. It checks that the output matches the expected URL pattern.

        """
        output = self.engine.render_to_string("url02", {"client": {"id": 1}})
        self.assertEqual(output, "/client/1/update/")

    @setup({"url02a": '{% url "client_action" client.id "update" %}'})
    def test_url02a(self):
        """
        Tests that the 'client_action' URL is correctly rendered when the 'update' action is specified, 
        using a client instance with the provided ID. The expected output is a string representing 
        the URL path in the format '/client/<id>/update/'.
        """
        output = self.engine.render_to_string("url02a", {"client": {"id": 1}})
        self.assertEqual(output, "/client/1/update/")

    @setup({"url02b": "{% url 'client_action' id=client.id action='update' %}"})
    def test_url02b(self):
        """

        Tests the rendering of a URL template with an update action for a client.

        This test case verifies that the URL template is correctly rendered with the client ID and
        the specified action. It checks that the resulting URL string matches the expected format.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the rendered URL does not match the expected output.

        """
        output = self.engine.render_to_string("url02b", {"client": {"id": 1}})
        self.assertEqual(output, "/client/1/update/")

    @setup({"url02c": "{% url 'client_action' client.id 'update' %}"})
    def test_url02c(self):
        """
        Tests the rendering of a URL template tag with a client ID, verifying that the generated URL matches the expected format.

        :param None:
        :returns: None
        :raises AssertionError: if the rendered URL does not match the expected string '/client/1/update/' 

        Note: This test case is designed to ensure that the 'url02c' template tag correctly generates a URL for a client update action, given a client ID.
        """
        output = self.engine.render_to_string("url02c", {"client": {"id": 1}})
        self.assertEqual(output, "/client/1/update/")

    @setup({"url03": '{% url "index" %}'})
    def test_url03(self):
        output = self.engine.render_to_string("url03")
        self.assertEqual(output, "/")

    @setup({"url04": '{% url "named.client" client.id %}'})
    def test_url04(self):
        output = self.engine.render_to_string("url04", {"client": {"id": 1}})
        self.assertEqual(output, "/named-client/1/")

    @setup({"url05": '{% url "метка_оператора" v %}'})
    def test_url05(self):
        """
        Tests the rendering of a URL with a non-ASCII parameter.

        This test case verifies that the templating engine correctly handles Unicode characters in URL parameters.
        It checks if the rendered URL matches the expected output, ensuring proper encoding of special characters.

        :raises AssertionError: If the rendered URL does not match the expected output.

        """
        output = self.engine.render_to_string("url05", {"v": "Ω"})
        self.assertEqual(output, "/%D0%AE%D0%BD%D0%B8%D0%BA%D0%BE%D0%B4/%CE%A9/")

    @setup({"url06": '{% url "метка_оператора_2" tag=v %}'})
    def test_url06(self):
        """
        Tests the rendering of a URL template tag with a non-ASCII character.

        This test case verifies that the template engine correctly renders a URL
        template tag containing a non-ASCII character, specifically the Greek
        letter Omega (Ω), and that the resulting URL is properly encoded.

        The expected output is a URL with the Omega character correctly
        percent-encoded as '%CE%A9' and the URL path containing the
        correctly encoded Unicode characters for 'Юникод'. The test passes if
        the rendered output matches the expected URL string.
        """
        output = self.engine.render_to_string("url06", {"v": "Ω"})
        self.assertEqual(output, "/%D0%AE%D0%BD%D0%B8%D0%BA%D0%BE%D0%B4/%CE%A9/")

    @setup({"url08": '{% url "метка_оператора" v %}'})
    def test_url08(self):
        """

        Test that the url template tag correctly generates a URL for a given view name and parameter.

        The test renders a template with a url tag that includes a non-ASCII character in the view name and a non-ASCII character as a parameter.
        It then checks that the rendered URL is correctly encoded.

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
        """

        Tests rendering of a specific URL pattern using the Jinja2 templating engine.

        The function verifies if the rendered URL matches the expected output. 
        It checks if the `client_action` URL is correctly formatted with the client ID and action parameters.

        The test case uses a test client with a predefined ID and action ('==') to verify the correctness of the rendered URL.

        """
        output = self.engine.render_to_string("url11", {"client": {"id": 1}})
        self.assertEqual(output, "/client/1/==/")

    @setup(
        {"url12": '{% url "client_action" id=client.id action="!$&\'()*+,;=~:@," %}'}
    )
    def test_url12(self):
        """

        Tests the rendering of a URL template with special characters.

        This test ensures that the template engine correctly handles and escapes special characters in a URL.
        The test case provides a client object with an ID and a URL template that includes special characters.
        The expected output is a rendered URL string with the special characters properly escaped.

        """
        output = self.engine.render_to_string("url12", {"client": {"id": 1}})
        self.assertEqual(output, "/client/1/!$&amp;&#x27;()*+,;=~:@,/")

    @setup({"url13": '{% url "client_action" id=client.id action=arg|join:"-" %}'})
    def test_url13(self):
        """
        Tests the url13 setup configuration by rendering a template string that uses the client_action URL with an id and action parameters.

        The test case validates the correct construction of the URL by comparing the rendered output with an expected URL pattern. 
        It verifies that the id and action parameters are correctly formatted and appended to the URL. 
        In this specific test, the action parameter is built by joining the elements of the arg list with a hyphen, and the test checks that the resulting URL matches the expected format.
        """
        output = self.engine.render_to_string(
            "url13", {"client": {"id": 1}, "arg": ["a", "b"]}
        )
        self.assertEqual(output, "/client/1/a-b/")

    @setup({"url14": '{% url "client_action" client.id arg|join:"-" %}'})
    def test_url14(self):
        """

        Tests the URL rendering for the 'client_action' route with a client ID and arguments.

        The test case verifies that the rendered URL matches the expected format, 
        which includes the client ID and arguments joined by hyphens.

        :raises AssertionError: If the rendered URL does not match the expected output.

        """
        output = self.engine.render_to_string(
            "url14", {"client": {"id": 1}, "arg": ["a", "b"]}
        )
        self.assertEqual(output, "/client/1/a-b/")

    @setup({"url15": '{% url "client_action" 12 "test" %}'})
    def test_url15(self):
        """

        Tests the rendering of a URL with parameters in a template.

        This test case verifies that the 'client_action' URL pattern is correctly
        rendered with the provided arguments, resulting in the expected output URL.

        """
        output = self.engine.render_to_string("url15")
        self.assertEqual(output, "/client/12/test/")

    @setup({"url18": '{% url "client" "1,2" %}'})
    def test_url18(self):
        """

        Tests the rendering of a URL template tag with multiple arguments.

        This test case verifies that the URL template tag correctly handles multiple
        arguments and renders the expected URL path. It checks that the output of the
        template rendering matches the expected URL format.

        """
        output = self.engine.render_to_string("url18")
        self.assertEqual(output, "/client/1,2/")

    @setup({"url19": "{% url named_url client.id %}"})
    def test_url19(self):
        """
        Tests the rendering of a URL named 'client' with a client ID.

        Specifically, verifies that the named URL is correctly generated with the 
        provided client ID, resulting in the expected output URL path.

        The test case expects the output to be in the format '/client/<client_id>/',
        where <client_id> is the ID of the client passed to the template context.

        This test ensures proper integration of the URL template tag with the 
        engine's rendering functionality, confirming that the named URL is resolved 
        correctly and the resulting URL path is as expected.
        """
        output = self.engine.render_to_string(
            "url19", {"client": {"id": 1}, "named_url": "client"}
        )
        self.assertEqual(output, "/client/1/")

    @setup({"url20": "{% url url_name_in_var client.id %}"})
    def test_url20(self):
        """
        Tests the rendering of a URL using the url20 template, 
        verifying that the resulting output matches the expected URL pattern.

        The test case checks that the URL is correctly generated with the client ID 
        and the URL name passed as variables, ensuring that the template is properly 
        rendered and the output is as expected.
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
        Tests the rendering of a URL with special characters in a template.

        The function checks if a URL with special characters can be correctly generated 
        from a template when the autoescape is turned off. The test case verifies that 
        the output of the rendered URL matches the expected string.
        """
        output = self.engine.render_to_string("url21", {"client": {"id": 1}})
        self.assertEqual(output, "/client/1/!$&'()*+,;=~:@,/")

    # Failures
    @setup({"url-fail01": "{% url %}"})
    def test_url_fail01(self):
        """

        Tests that a TemplateSyntaxError is raised when a malformed URL tag is used in a template.

        Checks that the templating engine correctly handles invalid URL syntax by attempting to
        parse a template containing a URL tag with missing arguments, and verifies that the
        expected error is raised as a result.

        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("url-fail01")

    @setup({"url-fail02": '{% url "no_such_view" %}'})
    def test_url_fail02(self):
        """

        Tests that the template engine correctly raises a NoReverseMatch exception when attempting to render a URL pattern that does not exist.

        This test case exercises the engine's error handling behavior when encountering a malformed or non-existent URL pattern, ensuring that it produces the expected error response.

        """
        with self.assertRaises(NoReverseMatch):
            self.engine.render_to_string("url-fail02")

    @setup({"url-fail03": '{% url "client" %}'})
    def test_url_fail03(self):
        """

        Tests rendering a template with an incorrect URL tag.

        This test case checks that a NoReverseMatch exception is raised when the URL
        engine attempts to render a template with a malformed url tag.

        """
        with self.assertRaises(NoReverseMatch):
            self.engine.render_to_string("url-fail03")

    @setup({"url-fail04": '{% url "view" id, %}'})
    def test_url_fail04(self):
        """
        Tests that a TemplateSyntaxError is raised when a URL template tag is missing a closing quotes. 

        This check ensures the 'url' template tag is properly formatted to avoid errors during template rendering.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("url-fail04")

    @setup({"url-fail05": '{% url "view" id= %}'})
    def test_url_fail05(self):
        """
        Test that the template engine raises a TemplateSyntaxError when the url template tag is missing a required argument.
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
        """
        Tests that a TemplateSyntaxError is raised when the url tag is used with an unterminated string in the template engine. 

        Verifies that the engine correctly handles syntax errors by attempting to retrieve a template that contains a malformed url template tag, then checks for the expected exception to be raised, ensuring the engine's error handling behavior is as expected.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("url-fail08")

    @setup({"url-fail09": '{% url "view" id=", %}'})
    def test_url_fail09(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("url-fail09")

    @setup({"url-fail11": "{% url named_url %}"})
    def test_url_fail11(self):
        """
        Tests that a NoReverseMatch exception is raised when rendering a template with an invalid named URL.

        The test case verifies that the template engine correctly handles a URL reference with a name that does not exist, and that it raises the expected exception when rendering the template.

        :raises NoReverseMatch: When the template engine cannot find a reverse match for the given URL name
        """
        with self.assertRaises(NoReverseMatch):
            self.engine.render_to_string("url-fail11")

    @setup({"url-fail12": "{% url named_url %}"})
    def test_url_fail12(self):
        with self.assertRaises(NoReverseMatch):
            self.engine.render_to_string("url-fail12", {"named_url": "no_such_view"})

    @setup({"url-fail13": "{% url named_url %}"})
    def test_url_fail13(self):
        """
        Test that rendering a URL with an invalid view name raises a NoReverseMatch exception.

        This test case verifies that when a template attempts to generate a URL using a named URL pattern,
        but the associated view name is not a valid callable, the expected exception is thrown.
        The test provides a named URL pattern and an invalid view name, then checks that rendering the
        template results in the anticipated error condition.

        :raises: NoReverseMatch
        :seealso: django.template.engine.Template Engine, django.urls.reverse
        """
        with self.assertRaises(NoReverseMatch):
            self.engine.render_to_string(
                "url-fail13", {"named_url": "template_tests.views.client"}
            )

    @setup({"url-fail14": "{% url named_url id, %}"})
    def test_url_fail14(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("url-fail14", {"named_url": "view"})

    @setup({"url-fail15": "{% url named_url id= %}"})
    def test_url_fail15(self):
        """
        Test that a TemplateSyntaxError is raised when the url template tag is used with a named URL but without providing the required arguments (like id). 

        This test case checks the behavior of the template engine when encountering an invalid url template tag usage.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("url-fail15", {"named_url": "view"})

    @setup({"url-fail16": "{% url named_url a.id=id %}"})
    def test_url_fail16(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("url-fail16", {"named_url": "view"})

    @setup({"url-fail17": "{% url named_url a.id!id %}"})
    def test_url_fail17(self):
        """
        Test that the URL template tag throws a TemplateSyntaxError when an incorrect syntax is used.

        This test case verifies that the URL template tag correctly handles invalid input and raises an exception when it encounters an invalid syntax. It specifically tests the case where an invalid separator is used in the URL template tag.

        Args:
            None

        Raises:
            TemplateSyntaxError: When the URL template tag encounters an incorrect syntax.

        Returns:
            None

        Note:
            This test is expected to fail with a TemplateSyntaxError when the URL template tag is rendered with an invalid syntax. The test passes if the exception is correctly raised.

        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("url-fail17", {"named_url": "view"})

    @setup({"url-fail18": '{% url named_url id="unterminatedstring %}'})
    def test_url_fail18(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("url-fail18", {"named_url": "view"})

    @setup({"url-fail19": '{% url named_url id=", %}'})
    def test_url_fail19(self):
        """
        Tests that a TemplateSyntaxError is raised when attempting to render a template with a malformed 'url' template tag, specifically when using a named URL with an incorrect argument format.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("url-fail19", {"named_url": "view"})

    # {% url ... as var %}
    @setup({"url-asvar01": '{% url "index" as url %}'})
    def test_url_asvar01(self):
        """

        Tests that a URL is correctly rendered as a variable when using the 'as' keyword.

        The test case verifies that the 'url' template tag correctly assigns the URL to a variable 
        instead of directly outputting it, resulting in an empty string as the expected output.

        This ensures that the 'as' keyword is properly utilized to store the URL in a variable for 
        further use in the template, rather than directly rendering it. 

        """
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

        Tests the URL namespace functionality.

        Verifies that the correct URL is generated when using a namespaced URL
        pattern in a template. Specifically, this test checks that the URL
        resolver correctly handles the namespace and app name when rendering
        the template with a given context.

        The test case sets up a request and template context, then renders the
        template and asserts that the output matches the expected URL.

        """
        request = self.request_factory.get("/")
        request.resolver_match = resolve("/ns1/")
        template = self.engine.get_template("url-namespace01")
        context = RequestContext(request)
        output = template.render(context)
        self.assertEqual(output, "/ns1/named-client/42/")

    @setup({"url-namespace02": '{% url "app:named.client" 42 %}'})
    def test_url_namespace02(self):
        """

        Tests rendering of a URL in a template using the URL namespace.

        This test case verifies that a URL generated using the 'url' template tag
        with a specified namespace is rendered correctly in a template. It checks
        if the URL 'named.client' with the argument '42' is correctly resolved to
        '/ns2/named-client/42/' when the URL namespace is 'url-namespace02' and
        the resolver match is set to '/ns2/'.

        The test uses a pre-configured setup with a URL namespace defined as
        '{% url \"app:named.client\" 42 %}' and checks the output of the template
        rendering against the expected result.

        """
        request = self.request_factory.get("/")
        request.resolver_match = resolve("/ns2/")
        template = self.engine.get_template("url-namespace02")
        context = RequestContext(request)
        output = template.render(context)
        self.assertEqual(output, "/ns2/named-client/42/")

    @setup({"url-namespace03": '{% url "app:named.client" 42 %}'})
    def test_url_namespace03(self):
        """
        Tests the rendering of a namespaced URL in a template.

        This test case verifies that a URL with a namespace is correctly resolved and
        rendered in a template. The URL is constructed using the 'url' template tag
        with a namespace and an argument, and the test checks that the resulting URL
        matches the expected output.

        The test setup includes creating a request, rendering a template with the URL
        tag, and comparing the output to the expected URL.

        The expected output URL should be in the format '/ns2/named-client/<id>/', where
        '<id>' is the argument passed to the URL tag.

        """
        request = self.request_factory.get("/")
        template = self.engine.get_template("url-namespace03")
        context = RequestContext(request)
        output = template.render(context)
        self.assertEqual(output, "/ns2/named-client/42/")

    @setup({"url-namespace-no-current-app": '{% url "app:named.client" 42 %}'})
    def test_url_namespace_no_current_app(self):
        """
        Tests URL resolution with a namespaced URL pattern when the current application is not set.

        This test case verifies that the url template tag correctly resolves a URL with a namespace
        when the current application is None, ensuring the resulting URL is correctly constructed.

        The expected output is a URL path with the namespace and view name, demonstrating that the
        template tag can handle namespaced URLs without relying on the current application context.
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
        request = self.request_factory.get("/")
        request.resolver_match = resolve("/ns1/")
        request.current_app = "app"
        template = self.engine.get_template("url-namespace-explicit-current-app")
        context = RequestContext(request)
        output = template.render(context)
        self.assertEqual(output, "/ns2/named-client/42/")


class URLNodeTest(SimpleTestCase):
    def test_repr(self):
        """

        Tests the string representation of a URLNode object.

        This test ensures that the repr() function returns a string that accurately represents the state of a URLNode, including its view name, arguments, keyword arguments, and variable assignment.

        """
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
