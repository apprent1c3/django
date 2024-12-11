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
        Tests the include template tag functionality by rendering a template that includes another template.

        The test verifies that the rendered output contains the expected headline text, confirming that the include tag correctly inserts the content of the specified template.

        :param none:
        :raises AssertionError: if the rendered output does not match the expected result
        :return: none
        """
        output = self.engine.render_to_string(
            "include03",
            {"template_name": "basic-syntax02", "headline": "Included"},
        )
        self.assertEqual(output, "Included")

    @setup({"include04": 'a{% include "nonexistent" %}b'})
    def test_include04(self):
        """
        Tests that a TemplateDoesNotExist exception is raised when attempting to render a template containing an include statement referencing a non-existent template.
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
        -/
        \"\"\"
        Tests the rendering of a template that includes another template with a space in its name.

        The purpose of this test is to ensure that the templating engine correctly handles 
        includes with names containing spaces, and that the output matches the expected result.

        """
        output = self.engine.render_to_string("include06")
        self.assertEqual(output, "template with a space")

    @setup(
        {"include07": '{% include "basic-syntax02" with headline="Inline" %}'},
        basic_templates,
    )
    def test_include07(self):
        output = self.engine.render_to_string("include07", {"headline": "Included"})
        self.assertEqual(output, "Inline")

    @setup(
        {"include08": '{% include headline with headline="Dynamic" %}'}, basic_templates
    )
    def test_include08(self):
        """
        ..\"render_to_string\" method of the template engine to test the include directive.

            The function verifies that the include directive correctly renders a template 
            with a specified headline, and that the output matches the expected string.

            :param self: instance of the test class
            :return: None 
            :raises AssertionError: if the rendered output does not match the expected string
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
        Tests the rendering of included templates with context variables.

        This test case checks the inclusion of a template named 'basic-syntax03' within the 'include09' template.
        It verifies that the included template has access to the context variables 'first' and 'second', 
        and that these variables can be manipulated using filters such as lower and upper case conversions.
        The expected output is then compared to the actual rendered string to ensure correct rendering of the included template.
        """
        output = self.engine.render_to_string(
            "include09", {"first": "Ul", "second": "lU"}
        )
        self.assertEqual(output, "Ul--LU --- UL--lU")

    @setup({"include10": '{% include "basic-syntax03" only %}'}, basic_templates)
    def test_include10(self):
        """
        Tests the functionality of including templated content using the '{% include %}' syntax.
        The test case verifies that the included template is properly rendered within the context of the parent template.
        It checks the output of the rendered template against expected results, considering the engine's string_if_invalid configuration.
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
        Tests the rendering of a template that includes another template with specific variables.

        This test case verifies that the included template \"basic-syntax03\" is rendered correctly
        when passed the variable 'first' with value 1, and that the variable 'second' from the
        outer template is not propagated to the included template. The test checks the output
        of the rendering process, taking into account the engine's behavior when encountering
        invalid variables (i.e., whether it replaces them with a specific string or leaves them
        untouched).
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
        """
        Tests the rendering of an included template with autoescaping disabled, using the 'include14' template setup. 
        The test checks if the engine correctly renders the template when a variable is passed, and validates the output against expected results with and without string_if_invalid setting.
        """
        output = self.engine.render_to_string("include14", {"var1": "&"})
        if self.engine.string_if_invalid:
            self.assertEqual(output, "& --- INVALID")
        else:
            self.assertEqual(output, "& --- ")

    # Include syntax errors
    @setup({"include-error01": '{% include "basic-syntax01" with %}'})
    def test_include_error01(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("include-error01")

    @setup({"include-error02": '{% include "basic-syntax01" with "no key" %}'})
    def test_include_error02(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("include-error02")

    @setup(
        {"include-error03": '{% include "basic-syntax01" with dotted.arg="error" %}'}
    )
    def test_include_error03(self):
        """
        Tests the template engine's behavior when encountering an invalid include statement.

         The function verifies that a TemplateSyntaxError is raised when the engine attempts to render a template containing a malformed include directive.

         :raises: AssertionError if a TemplateSyntaxError is not raised by the template engine
         :return: None
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("include-error03")

    @setup({"include-error04": '{% include "basic-syntax01" something_random %}'})
    def test_include_error04(self):
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
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("include-error06")

    @setup(include_fail_templates)
    def test_include_fail1(self):
        """
        Test that the engine correctly raises an exception when attempting to render a template with an include directive that fails. 

        This test case verifies that the engine handles include failures by throwing a RuntimeError, ensuring that errors in included templates are properly propagated and handled.
        """
        with self.assertRaises(RuntimeError):
            self.engine.get_template("include-fail1")

    @setup(include_fail_templates)
    def test_include_fail2(self):
        """
        Test the template engine's error handling when an included template fails to render.

        This test case verifies that the template engine correctly raises a :exc:`TemplateSyntaxError` when
        an included template contains invalid syntax. The test uses a pre-configured template 'include-fail2'
        that intentionally contains errors, and checks that the expected exception is raised when attempting
        to render it.

        :raises: :exc:`TemplateSyntaxError` if the template engine does not correctly handle the invalid syntax

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
        """
        Tests that a TemplateSyntaxError is raised when an include statement 
        within a template references a failed include from the context.

        This test case ensures that the template engine correctly handles 
        situations where an included template_failed template tries to include 
        another failed template. The test confirms that a TemplateSyntaxError 
        is raised when this occurs, allowing the application to handle the 
        error as needed. The context is set up to include a 'failed_include' 
        variable that maps to another failed include template, 'include-fail2'. 
        The 'include-error10' template is then rendered with this context, 
        resulting in the expected TemplateSyntaxError being raised.
        """
        context = Context({"failed_include": "include-fail2"})
        template = self.engine.get_template("include-error10")
        with self.assertRaises(TemplateSyntaxError):
            template.render(context)

    @setup({"include_empty": "{% include %}"})
    def test_include_empty(self):
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

        Tests the inclusion of templates loaded by the template loader.

        This test case verifies that a template can successfully include another template
        loaded by the loader. It checks that the included template is rendered correctly
        and its output is as expected.

        The test renders an 'include_tpl.html' template, which includes an 'index.html'
        template loaded by the loader, and asserts that the rendered output matches the
        expected result.

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
        """

        Checks the string representation of an IncludeNode object.

        Verifies that the repr() function returns a string in the format 
        <IncludeNode: template='template_path'>, where template_path is the path 
        to the template file passed during the node's creation.

        """
        include_node = IncludeNode("app/template.html")
        self.assertEqual(
            repr(include_node),
            "<IncludeNode: template='app/template.html'>",
        )
