import os

from django.template import Context, Engine, TemplateSyntaxError
from django.test import SimpleTestCase

from .utils import ROOT

RELATIVE = os.path.join(ROOT, "relative_templates")


class ExtendsRelativeBehaviorTests(SimpleTestCase):
    def test_normal_extend(self):
        """
        Tests the normal extension behavior of a template engine by rendering a template and asserting the expected output.

        The test creates an engine with a specific directory, retrieves a template named 'one.html', and renders it with an empty context.
        It verifies that the rendered output matches the expected string 'three two one', ensuring that the extension mechanism is working correctly.
        """
        engine = Engine(dirs=[RELATIVE])
        template = engine.get_template("one.html")
        output = template.render(Context({}))
        self.assertEqual(output.strip(), "three two one")

    def test_normal_extend_variable(self):
        engine = Engine(dirs=[RELATIVE])
        template = engine.get_template("one_var.html")
        output = template.render(Context({"tmpl": "./two.html"}))
        self.assertEqual(output.strip(), "three two one")

    def test_dir1_extend(self):
        engine = Engine(dirs=[RELATIVE])
        template = engine.get_template("dir1/one.html")
        output = template.render(Context({}))
        self.assertEqual(output.strip(), "three two one dir1 one")

    def test_dir1_extend1(self):
        engine = Engine(dirs=[RELATIVE])
        template = engine.get_template("dir1/one1.html")
        output = template.render(Context({}))
        self.assertEqual(output.strip(), "three two one dir1 one")

    def test_dir1_extend2(self):
        """
        Tests the rendering of a template from the 'dir1' directory with extended templates.

        Verifies that the template 'one2.html' in 'dir1' directory is correctly rendered 
        with the extended template, checking that the final output contains the expected 
        sequence of strings 'three two one dir1 one' after removing leading/trailing whitespaces.
        """
        engine = Engine(dirs=[RELATIVE])
        template = engine.get_template("dir1/one2.html")
        output = template.render(Context({}))
        self.assertEqual(output.strip(), "three two one dir1 one")

    def test_dir1_extend3(self):
        engine = Engine(dirs=[RELATIVE])
        template = engine.get_template("dir1/one3.html")
        output = template.render(Context({}))
        self.assertEqual(output.strip(), "three two one dir1 one")

    def test_dir2_extend(self):
        """

        Tests the extension of the directory structure in the templating engine.

        This test case verifies that the templating engine can correctly extend the 
        directory structure and render the corresponding template. It checks that the 
        rendered output matches the expected string, ensuring that the extension 
        mechanism is working as expected.

        :raises AssertionError: If the rendered output does not match the expected string.

        """
        engine = Engine(dirs=[RELATIVE])
        template = engine.get_template("dir1/dir2/one.html")
        output = template.render(Context({}))
        self.assertEqual(output.strip(), "three two one dir2 one")

    def test_extend_error(self):
        engine = Engine(dirs=[RELATIVE])
        msg = (
            "The relative path '\"./../two.html\"' points outside the file "
            "hierarchy that template 'error_extends.html' is in."
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            engine.render_to_string("error_extends.html")


class IncludeRelativeBehaviorTests(SimpleTestCase):
    def test_normal_include(self):
        engine = Engine(dirs=[RELATIVE])
        template = engine.get_template("dir1/dir2/inc2.html")
        output = template.render(Context({}))
        self.assertEqual(output.strip(), "dir2 include")

    def test_normal_include_variable(self):
        engine = Engine(dirs=[RELATIVE])
        template = engine.get_template("dir1/dir2/inc3.html")
        output = template.render(Context({"tmpl": "./include_content.html"}))
        self.assertEqual(output.strip(), "dir2 include")

    def test_dir2_include(self):
        engine = Engine(dirs=[RELATIVE])
        template = engine.get_template("dir1/dir2/inc1.html")
        output = template.render(Context({}))
        self.assertEqual(output.strip(), "three")

    def test_include_error(self):
        """

        Tests the engine's behavior when an include statement references a file outside the allowed directory hierarchy.

        This test case verifies that a TemplateSyntaxError is raised when attempting to render a template that includes a file using a relative path that points outside the template's directory.

        The expected error message indicates that the relative path is not allowed, ensuring the engine enforces the directory hierarchy constraints.

        """
        engine = Engine(dirs=[RELATIVE])
        msg = (
            "The relative path '\"./../three.html\"' points outside the file "
            "hierarchy that template 'error_include.html' is in."
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            engine.render_to_string("error_include.html")


class ExtendsMixedBehaviorTests(SimpleTestCase):
    def test_mixing1(self):
        engine = Engine(dirs=[RELATIVE])
        template = engine.get_template("dir1/two.html")
        output = template.render(Context({}))
        self.assertEqual(output.strip(), "three two one dir2 one dir1 two")

    def test_mixing2(self):
        engine = Engine(dirs=[RELATIVE])
        template = engine.get_template("dir1/three.html")
        output = template.render(Context({}))
        self.assertEqual(output.strip(), "three dir1 three")

    def test_mixing_loop(self):
        engine = Engine(dirs=[RELATIVE])
        msg = (
            "The relative path '\"./dir2/../looped.html\"' was translated to "
            "template name 'dir1/looped.html', the same template in which "
            "the tag appears."
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            engine.render_to_string("dir1/looped.html")
