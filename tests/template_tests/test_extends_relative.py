import os

from django.template import Context, Engine, TemplateSyntaxError
from django.test import SimpleTestCase

from .utils import ROOT

RELATIVE = os.path.join(ROOT, "relative_templates")


class ExtendsRelativeBehaviorTests(SimpleTestCase):
    def test_normal_extend(self):
        engine = Engine(dirs=[RELATIVE])
        template = engine.get_template("one.html")
        output = template.render(Context({}))
        self.assertEqual(output.strip(), "three two one")

    def test_normal_extend_variable(self):
        """

        Tests the normal extension of a variable in a template.

        This function verifies that the templating engine can correctly extend and render a template with a variable.
        The template 'one_var.html' is used, which includes another template 'two.html' specified by the 'tmpl' variable.
        The function checks that the final rendered output is as expected, demonstrating a successful extension of the variable. 

        """
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

        Test to verify the extension of a directory in the templating engine.

        This test checks that the templating engine can correctly extend a template from a subdirectory,
        rendering the extended content in the correct order.

        The test expects the rendered output to be a concatenated string of the extended content,
        in a specific order, confirming that the engine is able to properly handle directory extension.

        """
        engine = Engine(dirs=[RELATIVE])
        template = engine.get_template("dir1/one2.html")
        output = template.render(Context({}))
        self.assertEqual(output.strip(), "three two one dir1 one")

    def test_dir1_extend3(self):
        """
        Tests the extending of a template in directory 'dir1' with template 'one3.html' which should render 'three two one dir1 one' after rendering.

         Checks the functionality of template inheritance and rendering with the provided engine and context.

         :return: None
        """
        engine = Engine(dirs=[RELATIVE])
        template = engine.get_template("dir1/one3.html")
        output = template.render(Context({}))
        self.assertEqual(output.strip(), "three two one dir1 one")

    def test_dir2_extend(self):
        """

        Tests the rendering of a template located in a subdirectory.

        This test case verifies that the template engine can correctly extend
        a template from a subdirectory ('dir2') and render its content.
        The test checks if the rendered output contains the expected text.

        """
        engine = Engine(dirs=[RELATIVE])
        template = engine.get_template("dir1/dir2/one.html")
        output = template.render(Context({}))
        self.assertEqual(output.strip(), "three two one dir2 one")

    def test_extend_error(self):
        """
        Test the error handling for template extensions that point outside the file hierarchy.

        This test case checks that a :exc:`TemplateSyntaxError` is raised when a template attempts to extend another template using a relative path that points outside the directory where the template resides. The test verifies that the error message includes the expected path information.
        """
        engine = Engine(dirs=[RELATIVE])
        msg = (
            "The relative path '\"./../two.html\"' points outside the file "
            "hierarchy that template 'error_extends.html' is in."
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            engine.render_to_string("error_extends.html")


class IncludeRelativeBehaviorTests(SimpleTestCase):
    def test_normal_include(self):
        """

        Tests the inclusion of a template in a subdirectory using a relative path.

        The test case verifies that the Engine can correctly locate and render a template
        from a subdirectory, and that the rendered output matches the expected result.
        This ensures that the templating engine's include functionality works as expected
        when using relative paths.

        """
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

        Tests that the templating engine correctly raises an error when an included template references a path outside of the current file hierarchy.

        This test case verifies that the engine is properly handling relative paths and detecting potential security vulnerabilities. It checks that a TemplateSyntaxError is raised with a descriptive message when trying to render a template that includes a path that points outside the allowed directory structure.

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
        """

        Tests the mixing of templates by rendering a specific template and verifying its output content.

        The function checks if the rendering process correctly combines the expected templates, 
        and if the resulting output matches the anticipated string.

        """
        engine = Engine(dirs=[RELATIVE])
        template = engine.get_template("dir1/two.html")
        output = template.render(Context({}))
        self.assertEqual(output.strip(), "three two one dir2 one dir1 two")

    def test_mixing2(self):
        """

        Tests the mixing of directory configurations using the Engine class.

        This function verifies that templates can be correctly rendered from a specific directory,
        and that their output matches the expected content.

        The test case checks the rendering of a template from a relative directory,
        and asserts that the rendered output matches the predefined string.

        """
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
