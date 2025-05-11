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
        """
        Tests that HTML templates correctly escape user-provided input to prevent XSS attacks.
        """
        template = self.engine.get_template("template_backends/hello.html")
        context = {"name": '<script>alert("XSS!");</script>'}
        content = template.render(context)

        self.assertIn("&lt;script&gt;", content)
        self.assertNotIn("<script>", content)

    def test_django_html_escaping(self):
        """
        Tests the Django template engine's HTML escaping functionality, ensuring that form media and fields are properly rendered and escaped. Skips the test for the 'dummy' backend, as it does not apply.
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
        Test the presence and correctness of a CSRF token in a rendered template.

        Verifies that a valid CSRF token is included as a hidden input field in the
        output of a template that utilizes the CSRF middleware, and that the token
        matches the one stored in the request object.
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
        with self.assertRaises(TemplateDoesNotExist):
            self.engine.get_template("../forbidden/template_backends/hello.html")

    def test_non_ascii_characters(self):
        template = self.engine.get_template("template_backends/hello.html")
        content = template.render({"name": "Jérôme"})
        self.assertEqual(content, "Hello Jérôme!\n")
