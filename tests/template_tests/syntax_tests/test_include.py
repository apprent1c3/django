from django.template import (
    Context,
    Engine,
    TemplateDoesNotExist,
    TemplateSyntaxError,
    loader,
)
from django.template.loader_tags import IncludeNode
from django.test import SimpleTestCase

from ..utils import setup
from .test_basic import basic_templates

include_fail_templates = {
    "include-fail1": "{% load bad_tag %}{% badtag %}",
    "include-fail2": "{% load broken_tag %}",
}


class IncludeTagTests(SimpleTestCase):
    libraries = {"bad_tag": "template_tests.templatetags.bad_tag"}

    @setup({"include01": '{% include "basic-syntax01" %}'}, basic_templates)
    def test_include01(self):
        output = self.engine.render_to_string("include01")
        self.assertEqual(output, "something cool")

    @setup({"include02": '{% include "basic-syntax02" %}'}, basic_templates)
    def test_include02(self):
        output = self.engine.render_to_string("include02", {"headline": "Included"})
        self.assertEqual(output, "Included")

    @setup({"include03": "{% include template_name %}"}, basic_templates)
    def test_include03(self):
        """
        Render a template string with an include statement and verify its output.

        This function tests the rendering of a template that includes another template using the `{% include %}` tag. It checks if the rendered output matches the expected result, confirming that the include statement is correctly processed and the included template's contents are properly embedded in the final output.
        """
        output = self.engine.render_to_string(
            "include03",
            {"template_name": "basic-syntax02", "headline": "Included"},
        )
        self.assertEqual(output, "Included")

    @setup({"include04": 'a{% include "nonexistent" %}b'})
    def test_include04(self):
        """
        Test that rendering a template with an include tag referencing a non-existent template raises a TemplateDoesNotExist exception.
        """
        template = self.engine.get_template("include04")
        with self.assertRaises(TemplateDoesNotExist):
            template.render(Context({}))

    @setup(
        {
            "include 05": "template with a space",
            "include06": '{% include "include 05"%}',
        }
    )
    def test_include06(self):
        """
        Tests the rendering of a template that includes another template with a space in its name.

        The test case checks if the inclusion of a template with a name containing a space is handled correctly by the template engine, 
        and verifies that the output of the rendering process matches the expected string.
        """
        output = self.engine.render_to_string("include06")
        self.assertEqual(output, "template with a space")

    @setup(
        {"include07": '{% include "basic-syntax02" with headline="Inline" %}'},
        basic_templates,
    )
    def test_include07(self):
        """
        Test the rendering of included templates to ensure the correct content is displayed.

        The function checks that a template inclusion directive correctly inserts the content of another template, even when that content includes a variable. 
        It verifies that the engine renders the included template with the expected output, in this case, the string 'Inline'.
        """
        output = self.engine.render_to_string("include07", {"headline": "Included"})
        self.assertEqual(output, "Inline")

    @setup(
        {"include08": '{% include headline with headline="Dynamic" %}'}, basic_templates
    )
    def test_include08(self):
        """
        ylie 
            Render an include template tag with a variable headline value.

            This function tests the rendering of an include template tag using the Jinja2 engine.
            It passes a dictionary with a 'headline' key to the 'include08' template and checks if the output matches the expected headline value.


            :return: None
            :rtype: None
        """
        output = self.engine.render_to_string(
            "include08", {"headline": "basic-syntax02"}
        )
        self.assertEqual(output, "Dynamic")

    @setup(
        {
            "include09": (
                "{{ first }}--"
                '{% include "basic-syntax03" with '
                "first=second|lower|upper second=first|upper %}"
                "--{{ second }}"
            )
        },
        basic_templates,
    )
    def test_include09(self):
        """

        Test the rendering of includes with template variables and filters.

        This test case verifies that the include tag can handle variables passed from the
        parent template and apply filters to them. Specifically, it checks the correct
        passing of variables 'first' and 'second' to the included template 'basic-syntax03',
        and the application of the lower and upper case filters to these variables.

        The test expects the output to follow a specific pattern, demonstrating the correct
        substitution of variables and application of filters within the included template.

        """
        output = self.engine.render_to_string(
            "include09", {"first": "Ul", "second": "lU"}
        )
        self.assertEqual(output, "Ul--LU --- UL--lU")

    @setup({"include10": '{% include "basic-syntax03" only %}'}, basic_templates)
    def test_include10(self):
        """
        Test the inclusion of a template using the include tag in a rendering engine.

        This test case verifies that a template can be successfully included within another template.
        It checks the rendered output of the template with an included file and asserts that it matches the expected output.
        The test handles cases where the rendering engine is configured to display an error message if an included template is invalid, as well as cases where it is not.

        :raises AssertionError: If the rendered output does not match the expected output.

        """
        output = self.engine.render_to_string("include10", {"first": "1"})
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID --- INVALID")
        else:
            self.assertEqual(output, " --- ")

    @setup(
        {"include11": '{% include "basic-syntax03" only with second=2 %}'},
        basic_templates,
    )
    def test_include11(self):
        """

        Tests the functionality of including templates with specific variables.

        Verifies that when a template is included with specified variables, 
        it correctly renders the included template with the provided variable values.
        In this case, the test checks the inclusion of the 'basic-syntax03' template 
        with the 'second' variable set to 2 and the 'first' variable set to '1'. 
        The test covers both cases when the engine is configured to display an 
        'INVALID' string for failed template variables and when it does not.

        """
        output = self.engine.render_to_string("include11", {"first": "1"})
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID --- 2")
        else:
            self.assertEqual(output, " --- 2")

    @setup(
        {"include12": '{% include "basic-syntax03" with first=1 only %}'},
        basic_templates,
    )
    def test_include12(self):
        """
        Tests the rendering of an include statement with a 'with' keyword in a template.

        The test verifies that the template engine correctly includes the specified template
        (basic-syntax03) with the provided context variables (first=1) and renders the output
        according to the engine's settings for handling invalid templates. The expected output
        may vary depending on whether the engine is configured to display an 'INVALID' marker
        for unresolvable variables or to simply omit them.
        """
        output = self.engine.render_to_string("include12", {"second": "2"})
        if self.engine.string_if_invalid:
            self.assertEqual(output, "1 --- INVALID")
        else:
            self.assertEqual(output, "1 --- ")

    @setup(
        {
            "include13": (
                '{% autoescape off %}{% include "basic-syntax03" %}{% endautoescape %}'
            )
        },
        basic_templates,
    )
    def test_include13(self):
        """

        Tests the rendering of templates with autoescaping disabled and an included template.

        This test case verifies that the rendering engine handles the inclusion of a template
        with autoescaping turned off, and that the output is correctly generated based on
        the engine's configuration regarding the handling of invalid templates.

        """
        output = self.engine.render_to_string("include13", {"first": "&"})
        if self.engine.string_if_invalid:
            self.assertEqual(output, "& --- INVALID")
        else:
            self.assertEqual(output, "& --- ")

    @setup(
        {
            "include14": "{% autoescape off %}"
            '{% include "basic-syntax03" with first=var1 only %}'
            "{% endautoescape %}"
        },
        basic_templates,
    )
    def test_include14(self):
        output = self.engine.render_to_string("include14", {"var1": "&"})
        if self.engine.string_if_invalid:
            self.assertEqual(output, "& --- INVALID")
        else:
            self.assertEqual(output, "& --- ")

    # Include syntax errors
    @setup({"include-error01": '{% include "basic-syntax01" with %}'})
    def test_include_error01(self):
        """
        Tests that including a template with invalid syntax raises a TemplateSyntaxError.

        This test case verifies that the template engine correctly handles mistakes in template inclusion
        by checking for the presence of an expected exception when rendering a template that contains
        an invalid include statement. The test asserts that a TemplateSyntaxError is raised, ensuring
        that the engine behaves as expected when encountering syntax errors in included templates.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("include-error01")

    @setup({"include-error02": '{% include "basic-syntax01" with "no key" %}'})
    def test_include_error02(self):
        """
        Tests that a TemplateSyntaxError is raised when attempting to include a template with an invalid syntax.

        This test case verifies that the template engine correctly handles errors when including templates with missing or incorrect parameters.

        :raises: TemplateSyntaxError if the template engine encounters an invalid include syntax.
        :raises: AssertionError if the expected TemplateSyntaxError is not raised.

        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("include-error02")

    @setup(
        {"include-error03": '{% include "basic-syntax01" with dotted.arg="error" %}'}
    )
    def test_include_error03(self):
        """
        Tests that the template engine raises a TemplateSyntaxError when an include statement contains invalid syntax.

        This test case verifies that the engine correctly handles errors in include statements, specifically when the included template contains syntax errors. The test expects a TemplateSyntaxError to be raised when attempting to get a template with an invalid include statement.

        :raises: TemplateSyntaxError
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("include-error03")

    @setup({"include-error04": '{% include "basic-syntax01" something_random %}'})
    def test_include_error04(self):
        """
        Tests the template engine's behavior when encountering an invalid include statement.

        Verifies that a TemplateSyntaxError is raised when the template includes a non-existent
        or incorrectly formatted template file, ensuring proper error handling and reporting.

        :raises: TemplateSyntaxError if the include statement is malformed
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("include-error04")

    @setup(
        {"include-error05": '{% include "basic-syntax01" foo="duplicate" foo="key" %}'}
    )
    def test_include_error05(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("include-error05")

    @setup({"include-error06": '{% include "basic-syntax01" only only %}'})
    def test_include_error06(self):
        """
        Tests the template engine's behavior when encountering an invalid include statement with the 'only' keyword specified twice. 

        This test case verifies that the engine raises a TemplateSyntaxError when it encounters such an invalid include statement, ensuring proper error handling and syntax validation.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("include-error06")

    @setup(include_fail_templates)
    def test_include_fail1(self):
        """

        Tests that including a template with a failed include statement raises a RuntimeError.

        This test case exercises the template engine's behavior when an include statement
        fails, ensuring that the expected exception is raised and reported correctly.

        """
        with self.assertRaises(RuntimeError):
            self.engine.get_template("include-fail1")

    @setup(include_fail_templates)
    def test_include_fail2(self):
        """
        Tests that the template engine correctly raises a TemplateSyntaxError when attempting to include a template with a failing include statement.

        This test case verifies that the engine properly handles include failures, ensuring that errors are propagated and handled as expected. The test is designed to validate the engine's behavior when faced with invalid or unsupported include directives, providing confidence in its ability to handle edge cases and errors.

        :raises: TemplateSyntaxError
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("include-fail2")

    @setup({"include-error07": '{% include "include-fail1" %}'}, include_fail_templates)
    def test_include_error07(self):
        template = self.engine.get_template("include-error07")
        with self.assertRaises(RuntimeError):
            template.render(Context())

    @setup({"include-error08": '{% include "include-fail2" %}'}, include_fail_templates)
    def test_include_error08(self):
        """
        Tests that the template engine correctly raises a TemplateSyntaxError when an include statement fails.

         This test case checks the handling of a specific error scenario where an included template cannot be found or rendered, 
         ensuring the expected exception is thrown and reported.

         :raises TemplateSyntaxError: when the template include statement fails
        """
        template = self.engine.get_template("include-error08")
        with self.assertRaises(TemplateSyntaxError):
            template.render(Context())

    @setup({"include-error09": "{% include failed_include %}"}, include_fail_templates)
    def test_include_error09(self):
        context = Context({"failed_include": "include-fail1"})
        template = self.engine.get_template("include-error09")
        with self.assertRaises(RuntimeError):
            template.render(context)

    @setup({"include-error10": "{% include failed_include %}"}, include_fail_templates)
    def test_include_error10(self):
        context = Context({"failed_include": "include-fail2"})
        template = self.engine.get_template("include-error10")
        with self.assertRaises(TemplateSyntaxError):
            template.render(context)

    @setup({"include_empty": "{% include %}"})
    def test_include_empty(self):
        """
        Tests that the 'include' tag in a template raises a TemplateSyntaxError when no arguments are provided, ensuring that the template engine requires a template name to be specified for inclusion.
        """
        msg = (
            "'include' tag takes at least one argument: the name of the "
            "template to be included."
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.get_template("include_empty")


class IncludeTests(SimpleTestCase):
    def test_include_missing_template(self):
        """
        The correct template is identified as not existing
        when {% include %} specifies a template that does not exist.
        """
        engine = Engine(app_dirs=True, debug=True)
        template = engine.get_template("test_include_error.html")
        with self.assertRaisesMessage(TemplateDoesNotExist, "missing.html"):
            template.render(Context())

    def test_extends_include_missing_baseloader(self):
        """
        #12787 -- The correct template is identified as not existing
        when {% extends %} specifies a template that does exist, but that
        template has an {% include %} of something that does not exist.
        """
        engine = Engine(app_dirs=True, debug=True)
        template = engine.get_template("test_extends_error.html")
        with self.assertRaisesMessage(TemplateDoesNotExist, "missing.html"):
            template.render(Context())

    def test_extends_include_missing_cachedloader(self):
        """

        Test that the extends tag works correctly with a missing template 
        when using a cached loader.

        The test creates an engine with a cached loader and uses it to render 
        a template that extends a missing template. It verifies that the 
        expected TemplateDoesNotExist exception is raised, both initially 
        and after the template is retrieved from the cache.

        """
        engine = Engine(
            debug=True,
            loaders=[
                (
                    "django.template.loaders.cached.Loader",
                    [
                        "django.template.loaders.app_directories.Loader",
                    ],
                ),
            ],
        )

        template = engine.get_template("test_extends_error.html")
        with self.assertRaisesMessage(TemplateDoesNotExist, "missing.html"):
            template.render(Context())

        # Repeat to ensure it still works when loading from the cache
        template = engine.get_template("test_extends_error.html")
        with self.assertRaisesMessage(TemplateDoesNotExist, "missing.html"):
            template.render(Context())

    def test_include_template_argument(self):
        """
        Support any render() supporting object
        """
        engine = Engine()
        ctx = Context(
            {
                "tmpl": engine.from_string("This worked!"),
            }
        )
        outer_tmpl = engine.from_string("{% include tmpl %}")
        output = outer_tmpl.render(ctx)
        self.assertEqual(output, "This worked!")

    def test_include_template_iterable(self):
        """

        Tests the include template functionality when the variable provided is an iterable.

        This function checks that the include tag correctly handles both string and list iterables
        as template names, and that it correctly renders the last template in the iterable.

        The test cases cover scenarios where the iterable contains both a non-existent template
        and an existing template. The expected output is the content of the existing template.

        """
        engine = Engine.get_default()
        outer_temp = engine.from_string("{% include var %}")
        tests = [
            ("admin/fail.html", "index.html"),
            ["admin/fail.html", "index.html"],
        ]
        for template_names in tests:
            with self.subTest(template_names):
                output = outer_temp.render(Context({"var": template_names}))
                self.assertEqual(output, "index\n")

    def test_include_template_none(self):
        engine = Engine.get_default()
        outer_temp = engine.from_string("{% include var %}")
        ctx = Context({"var": None})
        msg = "No template names provided"
        with self.assertRaisesMessage(TemplateDoesNotExist, msg):
            outer_temp.render(ctx)

    def test_include_from_loader_get_template(self):
        """
        Tests the inclusion of templates from a loader.

        This test case verifies that a template can include another template using the
        loader. It checks that the included template ('index.html') is correctly rendered
        and its output is as expected when included in the 'include_tpl.html' template.

        The test includes a simple scenario where the included template is rendered with
        no additional context, and the resulting output is validated against the
        expected result. It ensures that the inclusion mechanism works correctly and
        produces the desired output. 
        """
        tmpl = loader.get_template("include_tpl.html")  # {% include tmpl %}
        output = tmpl.render({"tmpl": loader.get_template("index.html")})
        self.assertEqual(output, "index\n\n")

    def test_include_immediate_missing(self):
        """
        #16417 -- Include tags pointing to missing templates should not raise
        an error at parsing time.
        """
        Engine(debug=True).from_string('{% include "this_does_not_exist.html" %}')

    def test_include_recursive(self):
        comments = [
            {
                "comment": "A1",
                "children": [
                    {"comment": "B1", "children": []},
                    {"comment": "B2", "children": []},
                    {"comment": "B3", "children": [{"comment": "C1", "children": []}]},
                ],
            }
        ]
        engine = Engine(app_dirs=True)
        t = engine.get_template("recursive_include.html")
        self.assertEqual(
            "Recursion!  A1  Recursion!  B1   B2   B3  Recursion!  C1",
            t.render(Context({"comments": comments}))
            .replace(" ", "")
            .replace("\n", " ")
            .strip(),
        )

    def test_include_cache(self):
        """
        {% include %} keeps resolved templates constant (#27974). The
        CounterNode object in the {% counter %} template tag is created once
        if caching works properly. Each iteration increases the counter instead
        of restarting it.

        This works as a regression test only if the cached loader
        isn't used, so the @setup decorator isn't used.
        """
        engine = Engine(
            loaders=[
                (
                    "django.template.loaders.locmem.Loader",
                    {
                        "template": (
                            '{% for x in vars %}{% include "include" %}{% endfor %}'
                        ),
                        "include": '{% include "next" %}',
                        "next": "{% load custom %}{% counter %}",
                    },
                ),
            ],
            libraries={"custom": "template_tests.templatetags.custom"},
        )
        output = engine.render_to_string("template", {"vars": range(9)})
        self.assertEqual(output, "012345678")


class IncludeNodeTests(SimpleTestCase):
    def test_repr(self):
        include_node = IncludeNode("app/template.html")
        self.assertEqual(
            repr(include_node),
            "<IncludeNode: template='app/template.html'>",
        )
