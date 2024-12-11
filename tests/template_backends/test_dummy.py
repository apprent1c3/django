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
        Test rendering a template from a string.

        This test case verifies that a template created from a string can be rendered correctly,
        producing the expected output. It ensures that the rendering process preserves the original content,
        including any newline characters, and that the resulting content matches the initial string exactly.
        """
        template = self.engine.from_string("Hello!\n")
        content = template.render()
        self.assertEqual(content, "Hello!\n")

    def test_get_template(self):
        template = self.engine.get_template("template_backends/hello.html")
        content = template.render({"name": "world"})
        self.assertEqual(content, "Hello world!\n")

    def test_get_template_nonexistent(self):
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
        self.assertEqual(len(token1), CSRF_TOKEN_LENGTH)
        self.assertEqual(len(token2), CSRF_TOKEN_LENGTH)
        token1, token2 = map(_unmask_cipher_token, (token1, token2))
        self.assertEqual(token1, token2)

    def test_csrf_token(self):
        """

        Tests the CSRF token is correctly rendered and matches the expected value.

        This test simulates a request through the CsrfViewMiddleware and checks that the
        rendered CSRF token template contains a hidden field with the expected token value.
        The test verifies that the token is correctly generated and inserted into the 
        HTML output, ensuring the CSRF protection mechanism is functioning as expected.

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

        This test case verifies that attempting to access a template outside of the
        designated template directories raises a TemplateDoesNotExist exception,
        preventing potential security vulnerabilities.

        :raises TemplateDoesNotExist: if directory traversal is attempted
        """
        with self.assertRaises(TemplateDoesNotExist):
            self.engine.get_template("../forbidden/template_backends/hello.html")

    def test_non_ascii_characters(self):
        """

        Tests the rendering of templates with non-ASCII characters.

        This test case checks if the template engine correctly handles strings 
        containing non-ASCII characters, such as accented letters, by rendering 
        a template with a name containing these characters and verifying the output.

        The test uses a predefined template and checks if the rendered content 
        matches the expected output, ensuring that the non-ASCII characters are 
        preserved and displayed correctly.

        """
        template = self.engine.get_template("template_backends/hello.html")
        content = template.render({"name": "Jérôme"})
        self.assertEqual(content, "Hello Jérôme!\n")
