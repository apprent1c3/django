import sys

from django.template import Context, Engine, TemplateDoesNotExist, TemplateSyntaxError
from django.template.base import UNKNOWN_SOURCE
from django.test import SimpleTestCase, override_settings
from django.urls import NoReverseMatch
from django.utils import translation
from django.utils.html import escape


class TemplateTestMixin:
    def _engine(self, **kwargs):
        return Engine(debug=self.debug_engine, **kwargs)

    def test_string_origin(self):
        """

        Tests the origin of a string template.

        Verifies that a template loaded from a string has the expected origin attributes,
        including the name of the origin, loader name, and the source of the template itself.

        """
        template = self._engine().from_string("string template")
        self.assertEqual(template.origin.name, UNKNOWN_SOURCE)
        self.assertIsNone(template.origin.loader_name)
        self.assertEqual(template.source, "string template")

    @override_settings(SETTINGS_MODULE=None)
    def test_url_reverse_no_settings_module(self):
        """
        #9005 -- url tag shouldn't require settings.SETTINGS_MODULE to
        be set.
        """
        t = self._engine().from_string("{% url will_not_match %}")
        c = Context()
        with self.assertRaises(NoReverseMatch):
            t.render(c)

    def test_url_reverse_view_name(self):
        """
        #19827 -- url tag should keep original stack trace when reraising
        exception.
        """
        t = self._engine().from_string("{% url will_not_match %}")
        c = Context()
        try:
            t.render(c)
        except NoReverseMatch:
            tb = sys.exc_info()[2]
            depth = 0
            while tb.tb_next is not None:
                tb = tb.tb_next
                depth += 1
            self.assertGreater(
                depth, 5, "The traceback context was lost when reraising the traceback."
            )

    def test_no_wrapped_exception(self):
        """
        # 16770 -- The template system doesn't wrap exceptions, but annotates
        them.
        """
        engine = self._engine()
        c = Context({"coconuts": lambda: 42 / 0})
        t = engine.from_string("{{ coconuts }}")

        with self.assertRaises(ZeroDivisionError) as e:
            t.render(c)

        if self.debug_engine:
            debug = e.exception.template_debug
            self.assertEqual(debug["start"], 0)
            self.assertEqual(debug["end"], 14)

    def test_invalid_block_suggestion(self):
        """
        Error messages should include the unexpected block name and be in all
        English.
        """
        engine = self._engine()
        msg = (
            "Invalid block tag on line 1: 'endblock', expected 'elif', 'else' "
            "or 'endif'. Did you forget to register or load this tag?"
        )
        with self.settings(USE_I18N=True), translation.override("de"):
            with self.assertRaisesMessage(TemplateSyntaxError, msg):
                engine.from_string("{% if 1 %}lala{% endblock %}{% endif %}")

    def test_unknown_block_tag(self):
        """
        Tests that the templating engine correctly raises an exception when encountering an unknown block tag in a template.

        The test case verifies that a TemplateSyntaxError is raised with a descriptive error message when the engine encounters a tag that has not been registered or loaded.

        This test ensures that the templating engine behaves as expected when encountering invalid or unknown syntax, providing a clear error message to aid in debugging and template development.
        """
        engine = self._engine()
        msg = (
            "Invalid block tag on line 1: 'foobar'. Did you forget to "
            "register or load this tag?"
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            engine.from_string("lala{% foobar %}")

    def test_compile_filter_expression_error(self):
        """
        19819 -- Make sure the correct token is highlighted for
        FilterExpression errors.
        """
        engine = self._engine()
        msg = "Could not parse the remainder: '@bar' from 'foo@bar'"

        with self.assertRaisesMessage(TemplateSyntaxError, msg) as e:
            engine.from_string("{% if 1 %}{{ foo@bar }}{% endif %}")

        if self.debug_engine:
            debug = e.exception.template_debug
            self.assertEqual((debug["start"], debug["end"]), (10, 23))
            self.assertEqual((debug["during"]), "{{ foo@bar }}")

    def test_compile_tag_error(self):
        """
        Errors raised while compiling nodes should include the token
        information.
        """
        engine = self._engine(
            libraries={"bad_tag": "template_tests.templatetags.bad_tag"},
        )
        with self.assertRaises(RuntimeError) as e:
            engine.from_string("{% load bad_tag %}{% badtag %}")
        if self.debug_engine:
            self.assertEqual(e.exception.template_debug["during"], "{% badtag %}")

    def test_compile_tag_error_27584(self):
        """
        Test that a TemplateSyntaxError is raised when a template contains a tag with a compile error.

        The test specifically checks for the presence of the correct error message 
        when rendering a template with a deliberately faulty tag, 
        verifying that the template engine correctly handles the compilation error. 

        If debug mode is enabled, it also verifies the specific point in the template 
        where the error occurred, ensuring that the error message accurately reflects the location of the issue.
        """
        engine = self._engine(
            app_dirs=True,
            libraries={"tag_27584": "template_tests.templatetags.tag_27584"},
        )
        t = engine.get_template("27584_parent.html")
        with self.assertRaises(TemplateSyntaxError) as e:
            t.render(Context())
        if self.debug_engine:
            self.assertEqual(e.exception.template_debug["during"], "{% badtag %}")

    def test_compile_tag_error_27956(self):
        """Errors in a child of {% extends %} are displayed correctly."""
        engine = self._engine(
            app_dirs=True,
            libraries={"tag_27584": "template_tests.templatetags.tag_27584"},
        )
        t = engine.get_template("27956_child.html")
        with self.assertRaises(TemplateSyntaxError) as e:
            t.render(Context())
        if self.debug_engine:
            self.assertEqual(e.exception.template_debug["during"], "{% badtag %}")

    def test_compile_tag_extra_data(self):
        """Custom tags can pass extra data back to template."""
        engine = self._engine(
            app_dirs=True,
            libraries={"custom": "template_tests.templatetags.custom"},
        )
        t = engine.from_string("{% load custom %}{% extra_data %}")
        self.assertEqual(t.extra_data["extra_data"], "CUSTOM_DATA")

    def test_render_tag_error_in_extended_block(self):
        """Errors in extended block are displayed correctly."""
        e = self._engine(app_dirs=True)
        template = e.get_template("test_extends_block_error.html")
        context = Context()
        with self.assertRaises(TemplateDoesNotExist) as cm:
            template.render(context)
        if self.debug_engine:
            self.assertEqual(
                cm.exception.template_debug["during"],
                escape('{% include "missing.html" %}'),
            )

    def test_super_errors(self):
        """
        #18169 -- NoReverseMatch should not be silence in block.super.
        """
        engine = self._engine(app_dirs=True)
        t = engine.get_template("included_content.html")
        with self.assertRaises(NoReverseMatch):
            t.render(Context())

    def test_extends_generic_template(self):
        """
        #24338 -- Allow extending django.template.backends.django.Template
        objects.
        """
        engine = self._engine()
        parent = engine.from_string("{% block content %}parent{% endblock %}")
        child = engine.from_string(
            "{% extends parent %}{% block content %}child{% endblock %}"
        )
        self.assertEqual(child.render(Context({"parent": parent})), "child")

    def test_node_origin(self):
        """
        #25848 -- Set origin on Node so debugging tools can determine which
        template the node came from even if extending or including templates.
        """
        template = self._engine().from_string("content")
        for node in template.nodelist:
            self.assertEqual(node.origin, template.origin)

    def test_render_built_in_type_method(self):
        """
        Templates should not crash when rendering methods for built-in types
        without required arguments.
        """
        template = self._engine().from_string("{{ description.count }}")
        self.assertEqual(template.render(Context({"description": "test"})), "")


class TemplateTests(TemplateTestMixin, SimpleTestCase):
    debug_engine = False


class DebugTemplateTests(TemplateTestMixin, SimpleTestCase):
    debug_engine = True
