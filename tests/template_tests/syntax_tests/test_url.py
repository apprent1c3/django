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
        Tests the rendering of a URL template string.

        This test case checks if the URL template 'url01' is correctly rendered
        with the provided client ID. It verifies that the rendered output matches
        the expected URL pattern.

        :raises AssertionError: If the rendered output does not match the expected URL.

        """
        output = self.engine.render_to_string("url01", {"client": {"id": 1}})
        self.assertEqual(output, "/client/1/")

    @setup({"url02": '{% url "client_action" id=client.id action="update" %}'})
    def test_url02(self):
        """

        Tests the rendering of a URL template for client update action.

        This test verifies that the 'url02' template renders the expected URL
        for a client update action, given a client ID.

        :raises AssertionError: If the rendered URL does not match the expected output.

        """
        output = self.engine.render_to_string("url02", {"client": {"id": 1}})
        self.assertEqual(output, "/client/1/update/")

    @setup({"url02a": '{% url "client_action" client.id "update" %}'})
    def test_url02a(self):
        """
        Tests that the URL pattern 'url02a' correctly generates a URL for the client update action.

        The function uses a test client to render the 'url02a' template with a sample client ID and then checks if the generated URL matches the expected format.

        Args:
            None

        Returns:
            None

        Note:
            This test relies on the 'client_action' URL pattern being correctly defined in the URL configuration. The test verifies that the generated URL is in the format '/client/<client_id>/update/', where <client_id> is the ID of the client.
        """
        output = self.engine.render_to_string("url02a", {"client": {"id": 1}})
        self.assertEqual(output, "/client/1/update/")

    @setup({"url02b": "{% url 'client_action' id=client.id action='update' %}"})
    def test_url02b(self):
        output = self.engine.render_to_string("url02b", {"client": {"id": 1}})
        self.assertEqual(output, "/client/1/update/")

    @setup({"url02c": "{% url 'client_action' client.id 'update' %}"})
    def test_url02c(self):
        """

        Tests the rendering of the 'url02c' template variable to ensure it generates the correct URL path for a client update action.

        The test case verifies that the 'url02c' variable, defined as a URL pattern for the 'client_action' view with 'update' action, is correctly rendered as '/client/{client_id}/update/' when passed a client ID.

        The expected output is compared to the actual rendered string to confirm that the template variable is properly resolved and formatted.

        """
        output = self.engine.render_to_string("url02c", {"client": {"id": 1}})
        self.assertEqual(output, "/client/1/update/")

    @setup({"url03": '{% url "index" %}'})
    def test_url03(self):
        """
        Tests that the 'url' template tag correctly renders the URL for the 'index' view.

        Verifies that the rendered URL matches the expected output, ensuring that the
        templating engine is correctly resolving URL patterns.

        The test checks that the URL resolution is done accurately, with the expected 
        result being the root URL ('/').
        """
        output = self.engine.render_to_string("url03")
        self.assertEqual(output, "/")

    @setup({"url04": '{% url "named.client" client.id %}'})
    def test_url04(self):
        """
        Test the url04 template tag by rendering it with a client id and verifying the output matches the expected URL pattern. 

        The test case checks that the rendered URL correctly expands to '/named-client/{id}/' where {id} is the client's id.
        """
        output = self.engine.render_to_string("url04", {"client": {"id": 1}})
        self.assertEqual(output, "/named-client/1/")

    @setup({"url05": '{% url "метка_оператора" v %}'})
    def test_url05(self):
        """

        Tests the rendering of a URL template using the 'метка_оператора' tag with a non-ASCII character.

        The function verifies that the rendered URL is correctly encoded and matches the expected output.

        :param self: The test instance.
        :returns: None
        :raises AssertionError: If the rendered URL does not match the expected output.

        """
        output = self.engine.render_to_string("url05", {"v": "Ω"})
        self.assertEqual(output, "/%D0%AE%D0%BD%D0%B8%D0%BA%D0%BE%D0%B4/%CE%A9/")

    @setup({"url06": '{% url "метка_оператора_2" tag=v %}'})
    def test_url06(self):
        """

        Tests the rendering of a URL using the 'метка_оператора_2' tag with a special character.

        The test verifies that the URL is correctly encoded and rendered as expected.
        The input value 'Ω' is used to test the handling of non-ASCII characters in the URL.

        """
        output = self.engine.render_to_string("url06", {"v": "Ω"})
        self.assertEqual(output, "/%D0%AE%D0%BD%D0%B8%D0%BA%D0%BE%D0%B4/%CE%A9/")

    @setup({"url08": '{% url "метка_оператора" v %}'})
    def test_url08(self):
        output = self.engine.render_to_string("url08", {"v": "Ω"})
        self.assertEqual(output, "/%D0%AE%D0%BD%D0%B8%D0%BA%D0%BE%D0%B4/%CE%A9/")

    @setup({"url09": '{% url "метка_оператора_2" tag=v %}'})
    def test_url09(self):
        output = self.engine.render_to_string("url09", {"v": "Ω"})
        self.assertEqual(output, "/%D0%AE%D0%BD%D0%B8%D0%BA%D0%BE%D0%B4/%CE%A9/")

    @setup({"url10": '{% url "client_action" id=client.id action="two words" %}'})
    def test_url10(self):
        """

        Tests the rendering of a URL template containing non-alphanumeric characters.

        Verifies that the templating engine correctly escapes special characters in the URL path.
        In this case, it checks that the string \"two words\" is properly URL encoded to \"two%20words\".
        The test validates the output against the expected URL pattern \"/client/<id>/<action>/\".

        """
        output = self.engine.render_to_string("url10", {"client": {"id": 1}})
        self.assertEqual(output, "/client/1/two%20words/")

    @setup({"url11": '{% url "client_action" id=client.id action="==" %}'})
    def test_url11(self):
        """
        Tests rendering of a URL template string using the client_action URL pattern.
        Verifies that the template correctly substitutes the client id and action into the URL.
        The test case passes a client object with id 1 and action \"==\" and checks that the rendered output matches the expected URL.
        It ensures that the URL template is correctly formatted and that the client id and action are correctly replaced in the URL.
        """
        output = self.engine.render_to_string("url11", {"client": {"id": 1}})
        self.assertEqual(output, "/client/1/==/")

    @setup(
        {"url12": '{% url "client_action" id=client.id action="!$&\'()*+,;=~:@," %}'}
    )
    def test_url12(self):
        """

        Tests the rendering of a URL with special characters in the 'action' parameter.

        This test case verifies that the 'url' template tag can correctly handle special characters
        in the 'action' parameter and properly encode them in the resulting URL.
        The test checks that the rendered URL matches the expected output, ensuring that the
        special characters are correctly escaped.

        """
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
        """

        Tests the rendering of a URL in a template using the 'url' template tag.

        Verifies that the 'url' tag correctly generates a URL for the 'client_action' view
        with the provided parameters, and that the resulting URL matches the expected format.

        """
        output = self.engine.render_to_string("url15")
        self.assertEqual(output, "/client/12/test/")

    @setup({"url18": '{% url "client" "1,2" %}'})
    def test_url18(self):
        output = self.engine.render_to_string("url18")
        self.assertEqual(output, "/client/1,2/")

    @setup({"url19": "{% url named_url client.id %}"})
    def test_url19(self):
        output = self.engine.render_to_string(
            "url19", {"client": {"id": 1}, "named_url": "client"}
        )
        self.assertEqual(output, "/client/1/")

    @setup({"url20": "{% url url_name_in_var client.id %}"})
    def test_url20(self):
        """
        Tests the rendering of a URL with a dynamic client ID.

        This test case verifies that the URL is correctly generated using the provided
        client ID and URL name. It checks that the rendered output matches the expected
        URL pattern.

        The test uses a template string with a URL template tag, which is replaced with
        the actual URL based on the provided client ID and URL name.

        Expected Behavior:
            The function should render the URL as '/named-client/1/' when the client ID
            is 1 and the URL name is 'named.client'. The test will pass if the rendered
            output matches this expected URL pattern, and fail otherwise.
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

        Tests the rendering of a URL with special characters in the query string.

        The function verifies that the :func:`~engine.render_to_string` method correctly
        handles special characters in the URL pattern, ensuring they are not encoded
        or escaped. The test case checks for a specific set of special characters,
        including ``!$, &'()*+,;=~:@,`` to ensure they are preserved in the output URL.

        The expected output is a URL with the special characters intact.

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

        Tests that rendering a template with a non-existent URL raises a NoReverseMatch exception.

        This test case verifies that the templating engine correctly handles invalid URL references
        by checking if it raises the expected exception when attempting to render a template
        containing a URL that does not correspond to any view function.

        """
        with self.assertRaises(NoReverseMatch):
            self.engine.render_to_string("url-fail02")

    @setup({"url-fail03": '{% url "client" %}'})
    def test_url_fail03(self):
        """
        Test the scenario where a reverse URL resolution fails.

        This test case verifies that a NoReverseMatch exception is raised when attempting to render a template string that contains a URL tag with an invalid or missing URL pattern. The test is designed to ensure that the URL resolution mechanism correctly handles and reports such errors, providing a meaningful exception that can be caught and handled by the application.
        """
        with self.assertRaises(NoReverseMatch):
            self.engine.render_to_string("url-fail03")

    @setup({"url-fail04": '{% url "view" id, %}'})
    def test_url_fail04(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("url-fail04")

    @setup({"url-fail05": '{% url "view" id= %}'})
    def test_url_fail05(self):
        """
        Tests that a TemplateSyntaxError is raised when the url template tag is used without providing a required argument, specifically the 'id' parameter in the url pattern.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("url-fail05")

    @setup({"url-fail06": '{% url "view" a.id=id %}'})
    def test_url_fail06(self):
        """
        Tests that using a named argument 'id' in a url tag raises a TemplateSyntaxError when it conflicts with the 'id' attribute of the object 'a'.

        This test case ensures that the templating engine correctly handles and rejects ambiguous syntax in url tags, preventing potential errors in template rendering.

        Raises:
            TemplateSyntaxError: If the template engine encounters the conflicting 'id' argument in the url tag.

        """
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
        Test that a TemplateSyntaxError is raised when a url template tag is missing a required argument, specifically the id value. This test case verifies that the template engine correctly handles invalid url template tags and raises an exception when a required parameter is not provided.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("url-fail09")

    @setup({"url-fail11": "{% url named_url %}"})
    def test_url_fail11(self):
        with self.assertRaises(NoReverseMatch):
            self.engine.render_to_string("url-fail11")

    @setup({"url-fail12": "{% url named_url %}"})
    def test_url_fail12(self):
        """

        Tests that rendering a template with a non-existent view name in a URL tag raises a NoReverseMatch exception.

        The function checks that when the URL template tag is used with an invalid view name, 
        the expected exception is thrown, ensuring the template engine handles this scenario correctly.

        :param none:
        :return: None
        :raises: NoReverseMatch

        """
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
        Tests that a TemplateSyntaxError is raised when using the url template tag with an invalid syntax, specifically when missing a required argument and instead including a trailing comma.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("url-fail14", {"named_url": "view"})

    @setup({"url-fail15": "{% url named_url id= %}"})
    def test_url_fail15(self):
        """
        Tests that rendering a template with an incomplete url tag raises a TemplateSyntaxError.

        The test verifies that the template engine correctly handles a url tag with a missing required argument, in this case, the 'id' parameter.

        :raises: TemplateSyntaxError
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("url-fail15", {"named_url": "view"})

    @setup({"url-fail16": "{% url named_url a.id=id %}"})
    def test_url_fail16(self):
        """
        Tests that a TemplateSyntaxError is raised when a URL template tag is used with an invalid syntax.

        This test case specifically checks that passing a keyword argument (e.g., 'a.id=id') to the url template tag results in a syntax error, as this is not a valid way to specify URL parameters.

        The test verifies that the rendering of the template with the invalid url tag raises the expected exception, ensuring that the template engine correctly handles and reports syntax errors in URL tags.
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
        """
        Tests the rendering of a template with a URL assigned to a variable.

        The function verifies that the rendered output is empty when the 'url' template tag
        is used with the 'as' keyword to assign the result to a variable, without directly
        outputting the URL in the template. This ensures that the URL is correctly
        captured and stored in the assigned variable, rather than being rendered as a
        string in the output.
        """
        output = self.engine.render_to_string("url-asvar01")
        self.assertEqual(output, "")

    @setup({"url-asvar02": '{% url "index" as url %}{{ url }}'})
    def test_url_asvar02(self):
        """
        Tests that the URL template tag correctly renders a URL to a string when assigned to a variable with the 'as' keyword. 

        Verifies that the rendered URL matches the expected output.
        """
        output = self.engine.render_to_string("url-asvar02")
        self.assertEqual(output, "/")

    @setup({"url-asvar03": '{% url "no_such_view" as url %}{{ url }}'})
    def test_url_asvar03(self):
        output = self.engine.render_to_string("url-asvar03")
        self.assertEqual(output, "")

    @setup({"url-namespace01": '{% url "app:named.client" 42 %}'})
    def test_url_namespace01(self):
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

        Tests the behavior of the url template tag when the current app is not provided.

        This test case checks that the url template tag correctly resolves URLs across
        different namespaces when the current app is set to None. The test sets up a
        request with a resolver match for a specific namespace and no current app,
        then renders a template containing a url tag with a namespace and view name.
        The test asserts that the rendered URL is correctly resolved to the expected
        path.

        The test covers the scenario where the current app is not available, and the
        url tag needs to fall back to the default app or namespace. It verifies that
        the url tag can handle this case correctly and produce the expected output.

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

        Tests the repr method of the URLNode class to ensure it correctly represents the object as a string.

        The test covers two main scenarios: 
        - When the URLNode has no arguments and no 'asvar' attribute, 
        - When the URLNode has arguments and an 'asvar' attribute.

        The expected output is a string that reflects the attributes of the URLNode, including view_name, args, kwargs, and asvar. 
        This test ensures that the repr method provides a useful and accurate representation of the URLNode object for debugging purposes.

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
