import re

from django.forms import CharField, Form, Media
from django.http import HttpRequest, HttpResponse
from django.middleware.csrf import (
    CSRF_TOKEN_LENGTH,
    CsrfViewMiddleware,
    _unmask_cipher_token,
    get_token,
)
from django.template import TemplateDoesNotExist, TemplateSyntaxError
from django.template.backends.dummy import TemplateStrings
from django.test import SimpleTestCase


class TemplateStringsTests(SimpleTestCase):
    engine_class = TemplateStrings
    backend_name = "dummy"
    options = {}

    @classmethod
    def setUpClass(cls):
        """


        Sets up the class with a configured engine instance.

        This method is a class-level setup hook that initializes the necessary configurations
        and creates an engine instance using the specified backend and options. It ensures
        that the engine is properly set up and ready for use by the class.

        The engine's configuration includes settings such as directories, app directories,
        and options, which are used to customize its behavior.

        The result of this setup is stored in the `engine` class attribute, making it
        accessible to other methods within the class.

        """
        super().setUpClass()
        params = {
            "DIRS": [],
            "APP_DIRS": True,
            "NAME": cls.backend_name,
            "OPTIONS": cls.options,
        }
        cls.engine = cls.engine_class(params)

    def test_from_string(self):
        """

        Tests rendering a template from a string.

        This test case verifies that a template engine can correctly render a simple string template.
        It checks that the rendered content matches the original string, ensuring that the engine
        does not modify or alter the template in any way.

        The test case covers a basic rendering scenario, providing a foundation for more complex
        template rendering tests. It is an essential check to ensure the template engine's correctness
        and reliability.

        """
        template = self.engine.from_string("Hello!\n")
        content = template.render()
        self.assertEqual(content, "Hello!\n")

    def test_get_template(self):
        template = self.engine.get_template("template_backends/hello.html")
        content = template.render({"name": "world"})
        self.assertEqual(content, "Hello world!\n")

    def test_get_template_nonexistent(self):
        """
        Tests that attempting to retrieve a non-existent template raises a TemplateDoesNotExist exception.

        The test verifies that the exception is correctly attributed to the template engine that attempted to load the template, ensuring proper error handling and debugging capabilities.

        Args: None

        Returns: None

        Raises: TemplateDoesNotExist exception when a non-existent template is requested
        """
        with self.assertRaises(TemplateDoesNotExist) as e:
            self.engine.get_template("template_backends/nonexistent.html")
        self.assertEqual(e.exception.backend, self.engine)

    def test_get_template_syntax_error(self):
        # There's no way to trigger a syntax error with the dummy backend.
        # The test still lives here to factor it between other backends.
        """

        Test the handling of a template syntax error when retrieving a template.

        This test checks that the correct exception, :exc:`TemplateSyntaxError`, is raised
        when an attempt is made to get a template containing a syntax error.

        The test is skipped if the backend being used is 'dummy', as this test does not
        apply to that specific backend.

        """
        if self.backend_name == "dummy":
            self.skipTest("test doesn't apply to dummy backend")
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("template_backends/syntax_error.html")

    def test_html_escaping(self):
        """
        Tests that HTML special characters are properly escaped within template rendering.

        Verifies that a potentially malicious input, such as a script tag, is correctly
        escaped to prevent cross-site scripting (XSS) attacks when rendered as part of
        the template content. Ensures the output contains the escaped version of the
        input and does not contain the raw, potentially executable code.
        """
        template = self.engine.get_template("template_backends/hello.html")
        context = {"name": '<script>alert("XSS!");</script>'}
        content = template.render(context)

        self.assertIn("&lt;script&gt;", content)
        self.assertNotIn("<script>", content)

    def test_django_html_escaping(self):
        """

         Tests the Django HTML escaping functionality in the template engine.

         This test checks if the template engine correctly escapes HTML content when rendering
         a Django form with a media object. It verifies that the rendered content matches the
         expected output, ensuring that HTML escaping is applied correctly to prevent potential
         security vulnerabilities.

         The test covers the following scenarios:

         * Rendering of a Django form with a single field
         * Inclusion of a media object with a JavaScript file
         * Correct escaping of HTML content in the rendered template

         Note: This test is skipped when using the 'dummy' backend, as it does not apply to this configuration.

        """
        if self.backend_name == "dummy":
            self.skipTest("test doesn't apply to dummy backend")

        class TestForm(Form):
            test_field = CharField()

        media = Media(js=["my-script.js"])
        form = TestForm()
        template = self.engine.get_template("template_backends/django_escaping.html")
        content = template.render({"media": media, "test_form": form})

        expected = "{}\n\n{}\n\n{}".format(media, form, form["test_field"])

        self.assertHTMLEqual(content, expected)

    def check_tokens_equivalent(self, token1, token2):
        self.assertEqual(len(token1), CSRF_TOKEN_LENGTH)
        self.assertEqual(len(token2), CSRF_TOKEN_LENGTH)
        token1, token2 = map(_unmask_cipher_token, (token1, token2))
        self.assertEqual(token1, token2)

    def test_csrf_token(self):
        """
        Tests the functionality of the CSRF token in the given template, verifying that it is correctly generated and rendered.

        The test creates a request object, processes it through the CSRF view middleware, and then renders the CSRF template using the provided engine. It checks that the rendered content includes a hidden input field containing the CSRF token and ensures that the token matches the one generated by the middleware. 

        :raises AssertionError: If the hidden CSRF token field is not found in the rendered template content or if the token does not match the one generated by the middleware.
        """
        request = HttpRequest()
        CsrfViewMiddleware(lambda req: HttpResponse()).process_view(
            request, lambda r: None, (), {}
        )

        template = self.engine.get_template("template_backends/csrf.html")
        content = template.render(request=request)

        expected = '<input type="hidden" name="csrfmiddlewaretoken" value="([^"]+)">'
        match = re.match(expected, content) or re.match(
            expected.replace('"', "'"), content
        )
        self.assertTrue(match, "hidden csrftoken field not found in output")
        self.check_tokens_equivalent(match[1], get_token(request))

    def test_no_directory_traversal(self):
        """
        Tests that the template engine prevents directory traversal attacks by raising a TemplateDoesNotExist exception when attempting to access a template outside of the allowed directory structure.

        This test ensures that the engine correctly handles attempts to access templates using relative paths that would otherwise allow an attacker to traverse the file system and access sensitive information.

        :raises: TemplateDoesNotExist
        """
        with self.assertRaises(TemplateDoesNotExist):
            self.engine.get_template("../forbidden/template_backends/hello.html")

    def test_non_ascii_characters(self):
        template = self.engine.get_template("template_backends/hello.html")
        content = template.render({"name": "Jérôme"})
        self.assertEqual(content, "Hello Jérôme!\n")
