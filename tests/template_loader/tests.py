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

        Tests the retrieval of a template from the first engine using the get_template function.

        This test case verifies that the correct template is loaded and rendered successfully.
        It checks if the rendered template matches the expected output, ensuring the template
        is correctly parsed and interpreted.

        The test uses a sample template 'hello.html' located in the 'template_loader' directory
        to validate the functionality of the get_template function.

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

        Selects the first available template from a list of template paths.

        This function attempts to load and render the first template that is found in the given list of paths.
        The selection process stops at the first successfully loaded template.

        :returns: The first successfully loaded template object, or None if no templates are found.

        """
        template = select_template(
            ["template_loader/unknown.html", "template_loader/hello.html"]
        )
        self.assertEqual(template.render(), "Hello! (template strings)\n")

    def test_select_template_second_engine(self):
        template = select_template(
            ["template_loader/unknown.html", "template_loader/goodbye.html"]
        )
        self.assertEqual(template.render(), "Goodbye! (Django templates)\n")

    def test_select_template_using_engine(self):
        template = select_template(
            ["template_loader/unknown.html", "template_loader/hello.html"],
            using="django",
        )
        self.assertEqual(template.render(), "Hello! (Django templates)\n")

    def test_select_template_empty(self):
        """

        Tests that the select_template function raises a TemplateDoesNotExist exception when given an empty list of template names.

        This test ensures that the function behaves correctly in the case where no template names are provided, 
        indicating that a template cannot be found.

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
        content = render_to_string("template_loader/hello.html")
        self.assertEqual(content, "Hello! (template strings)\n")

    def test_render_to_string_second_engine(self):
        """
        Tests rendering a template to a string using the secondary template engine.

        Verifies that the rendered content matches the expected output, ensuring that the
        template engine correctly loads and renders the specified template.

        The test case asserts the equality of the rendered content with the string
        'Goodbye! (Django templates)\\n', which is the expected result of rendering the
        'goodbye.html' template using the secondary engine.
        """
        content = render_to_string("template_loader/goodbye.html")
        self.assertEqual(content, "Goodbye! (Django templates)\n")

    def test_render_to_string_with_request(self):
        request = RequestFactory().get("/foobar/")
        content = render_to_string("template_loader/request.html", request=request)
        self.assertEqual(content, "/foobar/\n")

    def test_render_to_string_using_engine(self):
        """

        Tests rendering of a template to a string using the Django template engine.

        Verifies that the render_to_string function correctly loads a template and returns
        its rendered content as a string. The test expects the rendered content to match
        the expected output, ensuring that the template is being rendered correctly.

        The test case uses a specific template ('hello.html') and checks that the rendered
        content matches the expected string ('Hello! (Django templates)\n').

        """
        content = render_to_string("template_loader/hello.html", using="django")
        self.assertEqual(content, "Hello! (Django templates)\n")

    def test_render_to_string_not_found(self):
        with self.assertRaises(TemplateDoesNotExist) as e:
            render_to_string("template_loader/unknown.html")
        self.assertEqual(
            e.exception.chain[-1].tried[0][0].template_name,
            "template_loader/unknown.html",
        )
        self.assertEqual(e.exception.chain[-1].backend.name, "django")

    def test_render_to_string_with_list_first_engine(self):
        content = render_to_string(
            ["template_loader/unknown.html", "template_loader/hello.html"]
        )
        self.assertEqual(content, "Hello! (template strings)\n")

    def test_render_to_string_with_list_second_engine(self):
        """
        Render a Django template to a string using a list of template paths and assert the correctness of the output.

        This function tests the rendering of templates using multiple paths, ensuring that the first available template is used. It verifies that the rendered content matches the expected output, in this case, a string containing 'Goodbye!' rendered by a Django template engine.
        """
        content = render_to_string(
            ["template_loader/unknown.html", "template_loader/goodbye.html"]
        )
        self.assertEqual(content, "Goodbye! (Django templates)\n")

    def test_render_to_string_with_list_using_engine(self):
        """
        Tests rendering a string using a list of templates with the Django template engine.

        This test case verifies that the render_to_string function correctly handles a list of templates and uses the specified engine to render the content. It checks that the function returns the expected output when the first template in the list is not found and the second template is successfully rendered.

        The test ensures that the render_to_string function behaves as expected when used with a list of templates and the Django template engine, providing a basic level of confidence in the functionality of the render_to_string function in this specific scenario.
        """
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
        content = render_to_string(
            ["template_loader/goodbye.html", "template_loader/hello.html"]
        )
        self.assertEqual(content, "Goodbye! (Django templates)\n")
