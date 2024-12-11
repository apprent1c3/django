from django.template import TemplateDoesNotExist
from django.template.loader import get_template, render_to_string, select_template
from django.test import SimpleTestCase, override_settings
from django.test.client import RequestFactory


@override_settings(
    TEMPLATES=[
        {
            "BACKEND": "django.template.backends.dummy.TemplateStrings",
            "APP_DIRS": True,
        },
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "OPTIONS": {
                "context_processors": [
                    "django.template.context_processors.request",
                ],
                "loaders": [
                    "django.template.loaders.filesystem.Loader",
                    "django.template.loaders.app_directories.Loader",
                ],
            },
        },
    ]
)
class TemplateLoaderTests(SimpleTestCase):
    def test_get_template_first_engine(self):
        """

        Tests the retrieval of a template using the first template engine.

        This test case verifies that the :func:`get_template` function can successfully
        load a template from the 'template_loader/hello.html' file and render it
        correctly. The expected output of the rendered template is 'Hello! (template strings)\n'.

        The purpose of this test is to ensure that the template engine is properly
        configured and functional, allowing for the rendering of templates with the
        correct content.

        """
        template = get_template("template_loader/hello.html")
        self.assertEqual(template.render(), "Hello! (template strings)\n")

    def test_get_template_second_engine(self):
        template = get_template("template_loader/goodbye.html")
        self.assertEqual(template.render(), "Goodbye! (Django templates)\n")

    def test_get_template_using_engine(self):
        template = get_template("template_loader/hello.html", using="django")
        self.assertEqual(template.render(), "Hello! (Django templates)\n")

    def test_get_template_not_found(self):
        with self.assertRaises(TemplateDoesNotExist) as e:
            get_template("template_loader/unknown.html")
        self.assertEqual(
            e.exception.chain[-1].tried[0][0].template_name,
            "template_loader/unknown.html",
        )
        self.assertEqual(e.exception.chain[-1].backend.name, "django")

    def test_select_template_first_engine(self):
        """

        Tests the selection of the first available template from a list of templates.

        This test case validates that when multiple templates are provided, the function 
        selects the first template that is successfully loaded and renders the expected output.

        """
        template = select_template(
            ["template_loader/unknown.html", "template_loader/hello.html"]
        )
        self.assertEqual(template.render(), "Hello! (template strings)\n")

    def test_select_template_second_engine(self):
        """
        Tests the selection and rendering of a template using a secondary template engine.

        This test case verifies that the correct template is chosen from a list of options and that it can be successfully rendered, returning the expected output.

        The test checks the functionality of the template selection mechanism to ensure it correctly handles the availability of multiple templates and engines, ultimately providing the correct rendered template content.
        """
        template = select_template(
            ["template_loader/unknown.html", "template_loader/goodbye.html"]
        )
        self.assertEqual(template.render(), "Goodbye! (Django templates)\n")

    def test_select_template_using_engine(self):
        """

        Tests the selection of a template using the Django engine.

        This test case verifies that the correct template is selected and rendered
        when using the Django template engine. It checks that the `select_template`
        function returns a template object that can be rendered to produce the
        expected output.

        """
        template = select_template(
            ["template_loader/unknown.html", "template_loader/hello.html"],
            using="django",
        )
        self.assertEqual(template.render(), "Hello! (Django templates)\n")

    def test_select_template_empty(self):
        """
        Tests the behavior of the select_template function when given an empty list of templates.

        Checks that calling select_template with no templates raises a TemplateDoesNotExist exception, 
        indicating that the function correctly handles this edge case and provides a meaningful error 
        when no templates are available for selection.
        """
        with self.assertRaises(TemplateDoesNotExist):
            select_template([])

    def test_select_template_string(self):
        with self.assertRaisesMessage(
            TypeError,
            "select_template() takes an iterable of template names but got a "
            "string: 'template_loader/hello.html'. Use get_template() if you "
            "want to load a single template by name.",
        ):
            select_template("template_loader/hello.html")

    def test_select_template_not_found(self):
        """

        Tests the select_template function when a template is not found.

        Verifies that the function raises a TemplateDoesNotExist exception and checks the
        exception's chain to ensure that it contains the correct template names and backends.
        The function is expected to try the 'dummy' backend first and then the 'django' backend,
        and the exception's chain should reflect this order.

        The test case checks the template names and backend names for both the first and last
        entries in the exception's chain, providing a comprehensive verification of the
        function's behavior when a template is not found.

        """
        with self.assertRaises(TemplateDoesNotExist) as e:
            select_template(
                ["template_loader/unknown.html", "template_loader/missing.html"]
            )
        self.assertEqual(
            e.exception.chain[0].tried[0][0].template_name,
            "template_loader/unknown.html",
        )
        self.assertEqual(e.exception.chain[0].backend.name, "dummy")
        self.assertEqual(
            e.exception.chain[-1].tried[0][0].template_name,
            "template_loader/missing.html",
        )
        self.assertEqual(e.exception.chain[-1].backend.name, "django")

    def test_select_template_tries_all_engines_before_names(self):
        template = select_template(
            ["template_loader/goodbye.html", "template_loader/hello.html"]
        )
        self.assertEqual(template.render(), "Goodbye! (Django templates)\n")

    def test_render_to_string_first_engine(self):
        """

        Tests the rendering of a template string to a string using the first engine.

        This test ensures that the render_to_string function correctly loads and renders 
        the specified template, returning the expected content as a string.

        The test case uses a simple 'hello.html' template from the 'template_loader' 
        directory and verifies that the rendered content matches the expected output.

        """
        content = render_to_string("template_loader/hello.html")
        self.assertEqual(content, "Hello! (template strings)\n")

    def test_render_to_string_second_engine(self):
        content = render_to_string("template_loader/goodbye.html")
        self.assertEqual(content, "Goodbye! (Django templates)\n")

    def test_render_to_string_with_request(self):
        request = RequestFactory().get("/foobar/")
        content = render_to_string("template_loader/request.html", request=request)
        self.assertEqual(content, "/foobar/\n")

    def test_render_to_string_using_engine(self):
        content = render_to_string("template_loader/hello.html", using="django")
        self.assertEqual(content, "Hello! (Django templates)\n")

    def test_render_to_string_not_found(self):
        """
        Tests that rendering a template to a string raises a TemplateDoesNotExist exception when the template is not found.

        Verifies that the exception contains the correct information about the missing template, including its name and the template backend that attempted to load it.
        """
        with self.assertRaises(TemplateDoesNotExist) as e:
            render_to_string("template_loader/unknown.html")
        self.assertEqual(
            e.exception.chain[-1].tried[0][0].template_name,
            "template_loader/unknown.html",
        )
        self.assertEqual(e.exception.chain[-1].backend.name, "django")

    def test_render_to_string_with_list_first_engine(self):
        """
        Test that rendering to a string with a list of templates returns the expected output when the first template is not found and the second one is used as a fallback.

        The purpose of this function is to verify that the render_to_string method behaves as expected when given a list of templates, prioritizing the first template and using subsequent ones if the previous ones are not found. The test case ensures that the rendered content matches the expected string.
        """
        content = render_to_string(
            ["template_loader/unknown.html", "template_loader/hello.html"]
        )
        self.assertEqual(content, "Hello! (template strings)\n")

    def test_render_to_string_with_list_second_engine(self):
        """

        Tests rendering a string using the second templating engine in a list.

        This function verifies that when multiple templates are provided, the first template
        that exists and can be rendered by a compatible templating engine will be used.
        In cases where the primary template is unknown or fails to render, it checks if 
        the function falls back to the next available template.

        The test confirms that the correct template ('goodbye.html') is rendered when the 
        primary template ('unknown.html') is not found or is not compatible with the 
        templating engine, and that the rendered content matches the expected output.

        """
        content = render_to_string(
            ["template_loader/unknown.html", "template_loader/goodbye.html"]
        )
        self.assertEqual(content, "Goodbye! (Django templates)\n")

    def test_render_to_string_with_list_using_engine(self):
        content = render_to_string(
            ["template_loader/unknown.html", "template_loader/hello.html"],
            using="django",
        )
        self.assertEqual(content, "Hello! (Django templates)\n")

    def test_render_to_string_with_list_empty(self):
        with self.assertRaises(TemplateDoesNotExist):
            render_to_string([])

    def test_render_to_string_with_list_not_found(self):
        with self.assertRaises(TemplateDoesNotExist) as e:
            render_to_string(
                ["template_loader/unknown.html", "template_loader/missing.html"]
            )
        self.assertEqual(
            e.exception.chain[0].tried[0][0].template_name,
            "template_loader/unknown.html",
        )
        self.assertEqual(e.exception.chain[0].backend.name, "dummy")
        self.assertEqual(
            e.exception.chain[1].tried[0][0].template_name,
            "template_loader/unknown.html",
        )
        self.assertEqual(e.exception.chain[1].backend.name, "django")
        self.assertEqual(
            e.exception.chain[2].tried[0][0].template_name,
            "template_loader/missing.html",
        )
        self.assertEqual(e.exception.chain[2].backend.name, "dummy")
        self.assertEqual(
            e.exception.chain[3].tried[0][0].template_name,
            "template_loader/missing.html",
        )
        self.assertEqual(e.exception.chain[3].backend.name, "django")

    def test_render_to_string_with_list_tries_all_engines_before_names(self):
        """

        Tests that render_to_string attempts to render a list of templates with all available engines before falling back to template names.

        This test case verifies that when provided with a list of template names, the function tries to render each template using all supported template engines.
        The rendering stops when the first successful render is encountered, and the resulting content is returned.
        In this specific test, it checks that the correct content ('Goodbye! (Django templates)\n') is rendered from the provided template list.

        """
        content = render_to_string(
            ["template_loader/goodbye.html", "template_loader/hello.html"]
        )
        self.assertEqual(content, "Goodbye! (Django templates)\n")
