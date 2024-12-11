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
        Set up the class-level environment prior to running tests.

        This method is called once before any tests in the class are executed.
        It establishes the necessary configuration for the test environment,
        including setting up the engine with the specified backend and options.
        The engine is then stored as a class attribute for use in subsequent tests.

        :param None
        :rtype: None
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
        template = self.engine.from_string("Hello!\n")
        content = template.render()
        self.assertEqual(content, "Hello!\n")

    def test_get_template(self):
        """

        Tests the retrieval and rendering of a template.

        This test case verifies that a template can be successfully fetched from the template engine and rendered with the provided context.
        The test checks if the rendered template content matches the expected output.

        :raises AssertionError: If the rendered template content does not match the expected output.

        """
        template = self.engine.get_template("template_backends/hello.html")
        content = template.render({"name": "world"})
        self.assertEqual(content, "Hello world!\n")

    def test_get_template_nonexistent(self):
        """

        Tests that attempting to retrieve a non-existent template raises a TemplateDoesNotExist exception.

        This test case verifies that the get_template method of the template engine correctly handles cases where the requested template does not exist, ensuring that the expected exception is raised and that its backend attribute is properly set to the template engine instance.

        """
        with self.assertRaises(TemplateDoesNotExist) as e:
            self.engine.get_template("template_backends/nonexistent.html")
        self.assertEqual(e.exception.backend, self.engine)

    def test_get_template_syntax_error(self):
        # There's no way to trigger a syntax error with the dummy backend.
        # The test still lives here to factor it between other backends.
        if self.backend_name == "dummy":
            self.skipTest("test doesn't apply to dummy backend")
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("template_backends/syntax_error.html")

    def test_html_escaping(self):
        """
        Tests that user input in HTML templates is properly escaped to prevent cross-site scripting (XSS) attacks.

        Verifies that the template engine correctly escapes special characters in user-provided data, ensuring that malicious scripts are not executed.

        Checks for the presence of escaped HTML tags in the rendered template content, while also verifying that the original script tags are not present, thus confirming that the template engine is properly securing user input.
        """
        template = self.engine.get_template("template_backends/hello.html")
        context = {"name": '<script>alert("XSS!");</script>'}
        content = template.render(context)

        self.assertIn("&lt;script&gt;", content)
        self.assertNotIn("<script>", content)

    def test_django_html_escaping(self):
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
        """
        Checks if two given tokens are equivalent by comparing their lengths and then their unmasked and decrypted values.

        :param token1: The first token for comparison
        :param token2: The second token for comparison
        :raises AssertionError: If the tokens do not have the expected length or if their unmasked and decrypted values do not match
        """
        self.assertEqual(len(token1), CSRF_TOKEN_LENGTH)
        self.assertEqual(len(token2), CSRF_TOKEN_LENGTH)
        token1, token2 = map(_unmask_cipher_token, (token1, token2))
        self.assertEqual(token1, token2)

    def test_csrf_token(self):
        """

        Tests the generation of a CSRF token within a template.

        This test evaluates the CsrfViewMiddleware's ability to generate a valid CSRF token
        and ensure it is correctly embedded within a rendered template. It verifies the
        presence of a hidden input field containing the CSRF token in the template output.

        The test checks for the token in both double-quoted and single-quoted input fields,
        providing flexibility in the template's HTML structure. It asserts that the token
        is correctly generated and equivalent to the one obtained directly from the request.

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

        Tests that the template engine prevents directory traversal attacks.

        Verifies that attempting to load a template from a parent directory raises a 
        :exc:`TemplateDoesNotExist` exception, ensuring that the engine does not allow 
        access to files outside of its designated template directories.

        """
        with self.assertRaises(TemplateDoesNotExist):
            self.engine.get_template("../forbidden/template_backends/hello.html")

    def test_non_ascii_characters(self):
        """
        Tests rendering of a template containing non-ASCII characters.

        This test case verifies that the template engine correctly handles Unicode characters in the rendered content, ensuring that special characters are displayed as expected. It checks the output of a template that includes a name with a non-ASCII character, confirming that the result matches the expected string.
        """
        template = self.engine.get_template("template_backends/hello.html")
        content = template.render({"name": "Jérôme"})
        self.assertEqual(content, "Hello Jérôme!\n")
