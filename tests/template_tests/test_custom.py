import os

from django.template import Context, Engine, TemplateSyntaxError
from django.template.base import Node
from django.template.library import InvalidTemplateLibrary
from django.test import SimpleTestCase
from django.test.utils import extend_sys_path

from .templatetags import custom, inclusion
from .utils import ROOT

LIBRARIES = {
    "custom": "template_tests.templatetags.custom",
    "inclusion": "template_tests.templatetags.inclusion",
}


class CustomFilterTests(SimpleTestCase):
    def test_filter(self):
        engine = Engine(libraries=LIBRARIES)
        t = engine.from_string("{% load custom %}{{ string|trim:5 }}")
        self.assertEqual(
            t.render(Context({"string": "abcdefghijklmnopqrstuvwxyz"})), "abcde"
        )

    def test_decorated_filter(self):
        """

        Tests the custom 'make_data_div' filter when applied to a string variable.

        This test case verifies that the filter correctly transforms the input string into 
        an HTML div element, where the 'data-name' attribute is set to the input string value.

        The test renders a template that utilizes the 'custom' library and applies the 
        'make_data_div' filter to the 'name' variable, then asserts that the resulting 
        rendered HTML matches the expected output.

        """
        engine = Engine(libraries=LIBRARIES)
        t = engine.from_string("{% load custom %}{{ name|make_data_div }}")
        self.assertEqual(
            t.render(Context({"name": "foo"})), '<div data-name="foo"></div>'
        )


class TagTestCase(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        """
        ..:param cls: The class instance being set up
        :rtype: None

        Set up the class by initializing the engine with the necessary configuration and 
        calling the superclass's setUpClass method. This method is called once before all 
        tests in the class are run. It prepares the environment for testing by setting up 
        the engine with application directories and libraries.
        """
        cls.engine = Engine(app_dirs=True, libraries=LIBRARIES)
        super().setUpClass()

    def verify_tag(self, tag, name):
        self.assertEqual(tag.__name__, name)
        self.assertEqual(tag.__doc__, "Expected %s __doc__" % name)
        self.assertEqual(tag.__dict__["anything"], "Expected %s __dict__" % name)


class SimpleTagTests(TagTestCase):
    def test_simple_tags(self):
        c = Context({"value": 42})

        templates = [
            ("{% load custom %}{% no_params %}", "no_params - Expected result"),
            ("{% load custom %}{% one_param 37 %}", "one_param - Expected result: 37"),
            (
                "{% load custom %}{% explicit_no_context 37 %}",
                "explicit_no_context - Expected result: 37",
            ),
            (
                "{% load custom %}{% no_params_with_context %}",
                "no_params_with_context - Expected result (context value: 42)",
            ),
            (
                "{% load custom %}{% params_and_context 37 %}",
                "params_and_context - Expected result (context value: 42): 37",
            ),
            (
                "{% load custom %}{% simple_two_params 37 42 %}",
                "simple_two_params - Expected result: 37, 42",
            ),
            (
                "{% load custom %}{% simple_keyword_only_param kwarg=37 %}",
                "simple_keyword_only_param - Expected result: 37",
            ),
            (
                "{% load custom %}{% simple_keyword_only_default %}",
                "simple_keyword_only_default - Expected result: 42",
            ),
            (
                "{% load custom %}{% simple_keyword_only_default kwarg=37 %}",
                "simple_keyword_only_default - Expected result: 37",
            ),
            (
                "{% load custom %}{% simple_one_default 37 %}",
                "simple_one_default - Expected result: 37, hi",
            ),
            (
                '{% load custom %}{% simple_one_default 37 two="hello" %}',
                "simple_one_default - Expected result: 37, hello",
            ),
            (
                '{% load custom %}{% simple_one_default one=99 two="hello" %}',
                "simple_one_default - Expected result: 99, hello",
            ),
            (
                "{% load custom %}{% simple_one_default 37 42 %}",
                "simple_one_default - Expected result: 37, 42",
            ),
            (
                "{% load custom %}{% simple_unlimited_args 37 %}",
                "simple_unlimited_args - Expected result: 37, hi",
            ),
            (
                "{% load custom %}{% simple_unlimited_args 37 42 56 89 %}",
                "simple_unlimited_args - Expected result: 37, 42, 56, 89",
            ),
            (
                "{% load custom %}{% simple_only_unlimited_args %}",
                "simple_only_unlimited_args - Expected result: ",
            ),
            (
                "{% load custom %}{% simple_only_unlimited_args 37 42 56 89 %}",
                "simple_only_unlimited_args - Expected result: 37, 42, 56, 89",
            ),
            (
                "{% load custom %}"
                '{% simple_unlimited_args_kwargs 37 40|add:2 56 eggs="scrambled" '
                "four=1|add:3 %}",
                "simple_unlimited_args_kwargs - Expected result: 37, 42, 56 / "
                "eggs=scrambled, four=4",
            ),
        ]

        for entry in templates:
            t = self.engine.from_string(entry[0])
            self.assertEqual(t.render(c), entry[1])

        for entry in templates:
            t = self.engine.from_string(
                "%s as var %%}Result: {{ var }}" % entry[0][0:-2]
            )
            self.assertEqual(t.render(c), "Result: %s" % entry[1])

    def test_simple_tag_errors(self):
        """
        Tests a series of basic tag error scenarios to ensure proper error handling.

        This function checks that various incorrect uses of template tags raise the expected TemplateSyntaxError with the correct error message.
        The test cases cover a range of scenarios, including:
          * Passing unexpected keyword arguments to a tag
          * Passing too many positional arguments to a tag
          * Failing to provide required keyword arguments
          * Providing multiple values for a keyword argument
          * Passing positional arguments after keyword arguments
        Each test case verifies that the expected error message is raised when the template string is parsed.

        Additionally, the function checks that the same error conditions are enforced when using the 'as var' syntax to assign the result of the tag to a variable. 
        """
        errors = [
            (
                "'simple_one_default' received unexpected keyword argument 'three'",
                '{% load custom %}{% simple_one_default 99 two="hello" three="foo" %}',
            ),
            (
                "'simple_two_params' received too many positional arguments",
                "{% load custom %}{% simple_two_params 37 42 56 %}",
            ),
            (
                "'simple_one_default' received too many positional arguments",
                "{% load custom %}{% simple_one_default 37 42 56 %}",
            ),
            (
                "'simple_keyword_only_param' did not receive value(s) for the "
                "argument(s): 'kwarg'",
                "{% load custom %}{% simple_keyword_only_param %}",
            ),
            (
                "'simple_keyword_only_param' received multiple values for "
                "keyword argument 'kwarg'",
                "{% load custom %}{% simple_keyword_only_param kwarg=42 kwarg=37 %}",
            ),
            (
                "'simple_keyword_only_default' received multiple values for "
                "keyword argument 'kwarg'",
                "{% load custom %}{% simple_keyword_only_default kwarg=42 "
                "kwarg=37 %}",
            ),
            (
                "'simple_unlimited_args_kwargs' received some positional argument(s) "
                "after some keyword argument(s)",
                "{% load custom %}"
                "{% simple_unlimited_args_kwargs 37 40|add:2 "
                'eggs="scrambled" 56 four=1|add:3 %}',
            ),
            (
                "'simple_unlimited_args_kwargs' received multiple values for keyword "
                "argument 'eggs'",
                "{% load custom %}"
                "{% simple_unlimited_args_kwargs 37 "
                'eggs="scrambled" eggs="scrambled" %}',
            ),
        ]

        for entry in errors:
            with self.assertRaisesMessage(TemplateSyntaxError, entry[0]):
                self.engine.from_string(entry[1])

        for entry in errors:
            with self.assertRaisesMessage(TemplateSyntaxError, entry[0]):
                self.engine.from_string("%s as var %%}" % entry[1][0:-2])

    def test_simple_tag_escaping_autoescape_off(self):
        """

        Tests the behavior of the custom 'escape_naive' template tag when autoescaping is disabled.

        Verifies that the template renders correctly with special characters intact, 
        in this case, an ampersand (&) in the provided context variable 'name'. 

        The expected output is a string that includes the unescaped special character.

        """
        c = Context({"name": "Jack & Jill"}, autoescape=False)
        t = self.engine.from_string("{% load custom %}{% escape_naive %}")
        self.assertEqual(t.render(c), "Hello Jack & Jill!")

    def test_simple_tag_naive_escaping(self):
        """
        '''Test the rendering of a template that loads a custom tag and applies naive escaping.

        The test case verifies that the rendering of the template results in the correct output
        with special characters properly escaped. The input context includes a name with an
        ampersand, which should be converted to its corresponding HTML entity in the output.'''
        """
        c = Context({"name": "Jack & Jill"})
        t = self.engine.from_string("{% load custom %}{% escape_naive %}")
        self.assertEqual(t.render(c), "Hello Jack &amp; Jill!")

    def test_simple_tag_explicit_escaping(self):
        # Check we don't double escape
        """
        Tests the explicit escaping functionality of a custom template tag.

        This test checks that variables are properly escaped when the escape_explicit
        block is used in a template, ensuring that special characters are correctly
        represented as their corresponding HTML entities. The test verifies that the
        output of the rendered template contains the expected escaped characters.

        """
        c = Context({"name": "Jack & Jill"})
        t = self.engine.from_string("{% load custom %}{% escape_explicit %}")
        self.assertEqual(t.render(c), "Hello Jack &amp; Jill!")

    def test_simple_tag_format_html_escaping(self):
        # Check we don't double escape
        """

        Tests the correct formatting and HTML escaping of a simple template tag.

        This test ensures that the template engine properly loads the custom template
        tag and applies HTML escaping to the context variables, resulting in a rendered
        output with special characters correctly escaped.

        Args:
            None

        Returns:
            None

        Asserts that the rendered template output matches the expected string, which
        contains the context variable 'name' with HTML escaping applied.

        """
        c = Context({"name": "Jack & Jill"})
        t = self.engine.from_string("{% load custom %}{% escape_format_html %}")
        self.assertEqual(t.render(c), "Hello Jack &amp; Jill!")

    def test_simple_tag_registration(self):
        # The decorators preserve the decorated function's docstring, name,
        # and attributes.
        """

        Tests the registration of simple custom tags.

        This test case verifies that various types of custom tags can be successfully registered,
        including tags with no parameters, tags with one parameter, tags with explicit no context,
        tags with parameters and context, tags with unlimited arguments and keyword arguments, 
        and tags without context parameters. It checks that each tag can be registered correctly
        and that the registration process does not encounter any issues.

        """
        self.verify_tag(custom.no_params, "no_params")
        self.verify_tag(custom.one_param, "one_param")
        self.verify_tag(custom.explicit_no_context, "explicit_no_context")
        self.verify_tag(custom.no_params_with_context, "no_params_with_context")
        self.verify_tag(custom.params_and_context, "params_and_context")
        self.verify_tag(
            custom.simple_unlimited_args_kwargs, "simple_unlimited_args_kwargs"
        )
        self.verify_tag(
            custom.simple_tag_without_context_parameter,
            "simple_tag_without_context_parameter",
        )

    def test_simple_tag_missing_context(self):
        # The 'context' parameter must be present when takes_context is True
        msg = (
            "'simple_tag_without_context_parameter' is decorated with "
            "takes_context=True so it must have a first argument of 'context'"
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.from_string(
                "{% load custom %}{% simple_tag_without_context_parameter 123 %}"
            )

    def test_simple_tag_missing_context_no_params(self):
        """

        Tests that a custom template tag that is decorated with takes_context=True raises a TemplateSyntaxError
        if it does not include a 'context' argument, even if the tag does not take any additional parameters.

        This test case verifies that the template engine correctly enforces the expectation that context-aware
        template tags have 'context' as their first argument, ensuring proper handling of template variables.

        """
        msg = (
            "'simple_tag_takes_context_without_params' is decorated with "
            "takes_context=True so it must have a first argument of 'context'"
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.from_string(
                "{% load custom %}{% simple_tag_takes_context_without_params %}"
            )


class InclusionTagTests(TagTestCase):
    def test_inclusion_tags(self):
        """
        Test various templating scenarios using custom inclusion tags.

        This function covers a range of use cases, including calling tags with and without parameters, using explicit and implicit context values, and handling tags with default and keyword-only arguments. It also tests tags that accept unlimited arguments and keyword arguments. The function uses a templating engine to render the templates and checks that the output matches the expected results.

        It verifies the correctness of the following inclusion tags:
        - inclusion_no_params
        - inclusion_one_param
        - inclusion_explicit_no_context
        - inclusion_no_params_with_context
        - inclusion_params_and_context
        - inclusion_two_params
        - inclusion_one_default
        - inclusion_keyword_only_default
        - inclusion_unlimited_args
        - inclusion_only_unlimited_args
        - inclusion_unlimited_args_kwargs

        The function uses a context object with a 'value' attribute set to 42 for rendering the templates. The expected results are predefined strings that contain the expected output of each template. The function ensures that the rendered templates match these expected results.
        """
        c = Context({"value": 42})

        templates = [
            (
                "{% load inclusion %}{% inclusion_no_params %}",
                "inclusion_no_params - Expected result\n",
            ),
            (
                "{% load inclusion %}{% inclusion_one_param 37 %}",
                "inclusion_one_param - Expected result: 37\n",
            ),
            (
                "{% load inclusion %}{% inclusion_explicit_no_context 37 %}",
                "inclusion_explicit_no_context - Expected result: 37\n",
            ),
            (
                "{% load inclusion %}{% inclusion_no_params_with_context %}",
                "inclusion_no_params_with_context - Expected result (context value: "
                "42)\n",
            ),
            (
                "{% load inclusion %}{% inclusion_params_and_context 37 %}",
                "inclusion_params_and_context - Expected result (context value: 42): "
                "37\n",
            ),
            (
                "{% load inclusion %}{% inclusion_two_params 37 42 %}",
                "inclusion_two_params - Expected result: 37, 42\n",
            ),
            (
                "{% load inclusion %}{% inclusion_one_default 37 %}",
                "inclusion_one_default - Expected result: 37, hi\n",
            ),
            (
                '{% load inclusion %}{% inclusion_one_default 37 two="hello" %}',
                "inclusion_one_default - Expected result: 37, hello\n",
            ),
            (
                '{% load inclusion %}{% inclusion_one_default one=99 two="hello" %}',
                "inclusion_one_default - Expected result: 99, hello\n",
            ),
            (
                "{% load inclusion %}{% inclusion_one_default 37 42 %}",
                "inclusion_one_default - Expected result: 37, 42\n",
            ),
            (
                "{% load inclusion %}{% inclusion_keyword_only_default kwarg=37 %}",
                "inclusion_keyword_only_default - Expected result: 37\n",
            ),
            (
                "{% load inclusion %}{% inclusion_unlimited_args 37 %}",
                "inclusion_unlimited_args - Expected result: 37, hi\n",
            ),
            (
                "{% load inclusion %}{% inclusion_unlimited_args 37 42 56 89 %}",
                "inclusion_unlimited_args - Expected result: 37, 42, 56, 89\n",
            ),
            (
                "{% load inclusion %}{% inclusion_only_unlimited_args %}",
                "inclusion_only_unlimited_args - Expected result: \n",
            ),
            (
                "{% load inclusion %}{% inclusion_only_unlimited_args 37 42 56 89 %}",
                "inclusion_only_unlimited_args - Expected result: 37, 42, 56, 89\n",
            ),
            (
                "{% load inclusion %}"
                '{% inclusion_unlimited_args_kwargs 37 40|add:2 56 eggs="scrambled" '
                "four=1|add:3 %}",
                "inclusion_unlimited_args_kwargs - Expected result: 37, 42, 56 / "
                "eggs=scrambled, four=4\n",
            ),
        ]

        for entry in templates:
            t = self.engine.from_string(entry[0])
            self.assertEqual(t.render(c), entry[1])

    def test_inclusion_tag_errors(self):
        errors = [
            (
                "'inclusion_one_default' received unexpected keyword argument 'three'",
                "{% load inclusion %}"
                '{% inclusion_one_default 99 two="hello" three="foo" %}',
            ),
            (
                "'inclusion_two_params' received too many positional arguments",
                "{% load inclusion %}{% inclusion_two_params 37 42 56 %}",
            ),
            (
                "'inclusion_one_default' received too many positional arguments",
                "{% load inclusion %}{% inclusion_one_default 37 42 56 %}",
            ),
            (
                "'inclusion_one_default' did not receive value(s) for the argument(s): "
                "'one'",
                "{% load inclusion %}{% inclusion_one_default %}",
            ),
            (
                "'inclusion_keyword_only_default' received multiple values "
                "for keyword argument 'kwarg'",
                "{% load inclusion %}{% inclusion_keyword_only_default "
                "kwarg=37 kwarg=42 %}",
            ),
            (
                "'inclusion_unlimited_args' did not receive value(s) for the "
                "argument(s): 'one'",
                "{% load inclusion %}{% inclusion_unlimited_args %}",
            ),
            (
                "'inclusion_unlimited_args_kwargs' received some positional "
                "argument(s) after some keyword argument(s)",
                "{% load inclusion %}"
                "{% inclusion_unlimited_args_kwargs 37 40|add:2 "
                'eggs="boiled" 56 four=1|add:3 %}',
            ),
            (
                "'inclusion_unlimited_args_kwargs' received multiple values for "
                "keyword argument 'eggs'",
                "{% load inclusion %}"
                "{% inclusion_unlimited_args_kwargs 37 "
                'eggs="scrambled" eggs="scrambled" %}',
            ),
        ]

        for entry in errors:
            with self.assertRaisesMessage(TemplateSyntaxError, entry[0]):
                self.engine.from_string(entry[1])

    def test_include_tag_missing_context(self):
        # The 'context' parameter must be present when takes_context is True
        """
        Tests that the inclusion tag without a context parameter raises a TemplateSyntaxError when used with takes_context=True. 

        This test ensures that the template engine correctly handles the case where an inclusion tag is decorated with takes_context=True but does not have a 'context' parameter as its first argument, which is a required configuration for this decorator.
        """
        msg = (
            "'inclusion_tag_without_context_parameter' is decorated with "
            "takes_context=True so it must have a first argument of 'context'"
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.from_string(
                "{% load inclusion %}{% inclusion_tag_without_context_parameter 123 %}"
            )

    def test_include_tag_missing_context_no_params(self):
        """
        Tests that the template engine correctly raises a TemplateSyntaxError when an inclusion tag decorated with takes_context=True is used without passing a context parameter, despite not requiring any additional parameters.
        """
        msg = (
            "'inclusion_tag_takes_context_without_params' is decorated with "
            "takes_context=True so it must have a first argument of 'context'"
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.from_string(
                "{% load inclusion %}{% inclusion_tag_takes_context_without_params %}"
            )

    def test_inclusion_tags_from_template(self):
        """
        Test the inclusion tags loaded from a template.

        This test case covers various scenarios of using inclusion tags in Django templates.
        It checks if the inclusion tags can handle different types of parameters, 
        such as no parameters, fixed parameters, context variables, default values, 
        and unlimited arguments. It also verifies that the inclusion tags return 
        the expected results when rendered with a given context.

        The test cases include:
        - Inclusion tags with no parameters
        - Inclusion tags with one or more fixed parameters
        - Inclusion tags with explicit no context
        - Inclusion tags with context variables
        - Inclusion tags with a mix of fixed parameters and context variables
        - Inclusion tags with default values
        - Inclusion tags with unlimited arguments
        - Inclusion tags with only unlimited arguments

        Each test case checks if the rendered template matches the expected output.

        """
        c = Context({"value": 42})

        templates = [
            (
                "{% load inclusion %}{% inclusion_no_params_from_template %}",
                "inclusion_no_params_from_template - Expected result\n",
            ),
            (
                "{% load inclusion %}{% inclusion_one_param_from_template 37 %}",
                "inclusion_one_param_from_template - Expected result: 37\n",
            ),
            (
                "{% load inclusion %}"
                "{% inclusion_explicit_no_context_from_template 37 %}",
                "inclusion_explicit_no_context_from_template - Expected result: 37\n",
            ),
            (
                "{% load inclusion %}"
                "{% inclusion_no_params_with_context_from_template %}",
                "inclusion_no_params_with_context_from_template - Expected result "
                "(context value: 42)\n",
            ),
            (
                "{% load inclusion %}"
                "{% inclusion_params_and_context_from_template 37 %}",
                "inclusion_params_and_context_from_template - Expected result (context "
                "value: 42): 37\n",
            ),
            (
                "{% load inclusion %}{% inclusion_two_params_from_template 37 42 %}",
                "inclusion_two_params_from_template - Expected result: 37, 42\n",
            ),
            (
                "{% load inclusion %}{% inclusion_one_default_from_template 37 %}",
                "inclusion_one_default_from_template - Expected result: 37, hi\n",
            ),
            (
                "{% load inclusion %}{% inclusion_one_default_from_template 37 42 %}",
                "inclusion_one_default_from_template - Expected result: 37, 42\n",
            ),
            (
                "{% load inclusion %}{% inclusion_unlimited_args_from_template 37 %}",
                "inclusion_unlimited_args_from_template - Expected result: 37, hi\n",
            ),
            (
                "{% load inclusion %}"
                "{% inclusion_unlimited_args_from_template 37 42 56 89 %}",
                "inclusion_unlimited_args_from_template - Expected result: 37, 42, 56, "
                "89\n",
            ),
            (
                "{% load inclusion %}{% inclusion_only_unlimited_args_from_template %}",
                "inclusion_only_unlimited_args_from_template - Expected result: \n",
            ),
            (
                "{% load inclusion %}"
                "{% inclusion_only_unlimited_args_from_template 37 42 56 89 %}",
                "inclusion_only_unlimited_args_from_template - Expected result: 37, "
                "42, 56, 89\n",
            ),
        ]

        for entry in templates:
            t = self.engine.from_string(entry[0])
            self.assertEqual(t.render(c), entry[1])

    def test_inclusion_tag_registration(self):
        # The decorators preserve the decorated function's docstring, name,
        # and attributes.
        """
        Tests the registration of various inclusion tags, verifying their successful creation with different parameter configurations and context handling scenarios, including tags with and without parameters, context, default values, and unlimited arguments, as well as localization support.
        """
        self.verify_tag(inclusion.inclusion_no_params, "inclusion_no_params")
        self.verify_tag(inclusion.inclusion_one_param, "inclusion_one_param")
        self.verify_tag(
            inclusion.inclusion_explicit_no_context, "inclusion_explicit_no_context"
        )
        self.verify_tag(
            inclusion.inclusion_no_params_with_context,
            "inclusion_no_params_with_context",
        )
        self.verify_tag(
            inclusion.inclusion_params_and_context, "inclusion_params_and_context"
        )
        self.verify_tag(inclusion.inclusion_two_params, "inclusion_two_params")
        self.verify_tag(inclusion.inclusion_one_default, "inclusion_one_default")
        self.verify_tag(inclusion.inclusion_unlimited_args, "inclusion_unlimited_args")
        self.verify_tag(
            inclusion.inclusion_only_unlimited_args, "inclusion_only_unlimited_args"
        )
        self.verify_tag(
            inclusion.inclusion_tag_without_context_parameter,
            "inclusion_tag_without_context_parameter",
        )
        self.verify_tag(inclusion.inclusion_tag_use_l10n, "inclusion_tag_use_l10n")
        self.verify_tag(
            inclusion.inclusion_unlimited_args_kwargs, "inclusion_unlimited_args_kwargs"
        )

    def test_15070_use_l10n(self):
        """
        Inclusion tag passes down `use_l10n` of context to the
        Context of the included/rendered template as well.
        """
        c = Context({})
        t = self.engine.from_string("{% load inclusion %}{% inclusion_tag_use_l10n %}")
        self.assertEqual(t.render(c).strip(), "None")

        c.use_l10n = True
        self.assertEqual(t.render(c).strip(), "True")

    def test_no_render_side_effect(self):
        """
        #23441 -- InclusionNode shouldn't modify its nodelist at render time.
        """
        engine = Engine(app_dirs=True, libraries=LIBRARIES)
        template = engine.from_string("{% load inclusion %}{% inclusion_no_params %}")
        count = template.nodelist.get_nodes_by_type(Node)
        template.render(Context({}))
        self.assertEqual(template.nodelist.get_nodes_by_type(Node), count)

    def test_render_context_is_cleared(self):
        """
        #24555 -- InclusionNode should push and pop the render_context stack
        when rendering. Otherwise, leftover values such as blocks from
        extending can interfere with subsequent rendering.
        """
        engine = Engine(app_dirs=True, libraries=LIBRARIES)
        template = engine.from_string(
            "{% load inclusion %}{% inclusion_extends1 %}{% inclusion_extends2 %}"
        )
        self.assertEqual(template.render(Context({})).strip(), "one\ntwo")


class TemplateTagLoadingTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        """

        Sets up the class by defining the egg directory and calls the superclass setup method.

        This class method is called before any tests in the class are executed. It initializes the egg directory path
        by joining the ROOT directory with 'eggs', allowing for future test setup and operations to reference this path.

        The superclass setup method is then invoked to ensure any inherited setup functionality is also executed.

        """
        cls.egg_dir = os.path.join(ROOT, "eggs")
        super().setUpClass()

    def test_load_error(self):
        msg = (
            "Invalid template library specified. ImportError raised when "
            "trying to load 'template_tests.broken_tag': cannot import name "
            "'Xtemplate'"
        )
        with self.assertRaisesMessage(InvalidTemplateLibrary, msg):
            Engine(libraries={"broken_tag": "template_tests.broken_tag"})

    def test_load_error_egg(self):
        """
        Tests loading an invalid Django template library from an egg.

        This test ensures that an :class:`InvalidTemplateLibrary` exception is raised
        when attempting to load a template library that contains an import error.
        The test uses a deliberately broken egg file to simulate the error condition.

        The expected exception includes a message indicating that an :class:`ImportError`
        was raised when trying to import the library, with a specific error message
        describing the problem.

        Parameters are not applicable for this test case, as it is a test method.
        The test outcome verifies that the correct exception is raised with the expected message.
        """
        egg_name = "%s/tagsegg.egg" % self.egg_dir
        msg = (
            "Invalid template library specified. ImportError raised when "
            "trying to load 'tagsegg.templatetags.broken_egg': cannot "
            "import name 'Xtemplate'"
        )
        with extend_sys_path(egg_name):
            with self.assertRaisesMessage(InvalidTemplateLibrary, msg):
                Engine(libraries={"broken_egg": "tagsegg.templatetags.broken_egg"})

    def test_load_working_egg(self):
        """
        Tests the loading of a working Django template tag egg.

        This test checks if a Django template engine can correctly load and use a template tag from a working egg file.
        It verifies that the egg is properly installed and its contents are accessible by the template engine.
        The test creates a template engine instance with the working egg as a library and attempts to load the egg in a template string.
        """
        ttext = "{% load working_egg %}"
        egg_name = "%s/tagsegg.egg" % self.egg_dir
        with extend_sys_path(egg_name):
            engine = Engine(
                libraries={
                    "working_egg": "tagsegg.templatetags.working_egg",
                }
            )
            engine.from_string(ttext)

    def test_load_annotated_function(self):
        Engine(
            libraries={
                "annotated_tag_function": "template_tests.annotated_tag_function",
            }
        )
