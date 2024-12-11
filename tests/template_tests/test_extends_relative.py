import os

from django.template import Context, Engine, TemplateSyntaxError
from django.test import SimpleTestCase

from .utils import ROOT

RELATIVE = os.path.join(ROOT, "relative_templates")


class ExtendsRelativeBehaviorTests(SimpleTestCase):
    def test_normal_extend(self):
        """
        Tests the normal extension behavior of a template.

        This test case verifies that a template can be properly extended, 
        with the extended blocks being correctly overridden and rendered.
        The test expects the rendered output to be in a specific order, 
        indicating that the extension and block overriding are working as expected.

        The test checks the rendering of a template named 'one.html' 
        using a context without any variables, and asserts that the output 
        matches the expected result, which is 'three two one'.
        """
        engine = Engine(dirs=[RELATIVE])
        template = engine.get_template("one.html")
        output = template.render(Context({}))
        self.assertEqual(output.strip(), "three two one")

    def test_normal_extend_variable(self):
        """

        Test the normal extension of a template variable.

        This test case checks the ability of the templating engine to properly extend
        and render a template variable by including another template and maintaining
        the correct order of contents. The expected output is a concatenated string
        from the included templates, verifying the correct functionality of the 
        templating engine's variable extension mechanism.

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
        Tests the extension of a directory with a nested directory structure.

        Verifies that a template rendered from a subdirectory correctly extends 
        a template from its parent directory, thus allowing inheritance of content.

        The test checks if the rendered output contains the expected content 
        in the correct order, indicating successful extension of the directory 
        and proper template inheritance.
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
        """

        Tests the normal inclusion of a template.

        Verifies that a template can be successfully included from a subdirectory
        using a relative path, and that the resulting output matches the expected content.

        The test checks the rendering of the 'inc2.html' template located in 'dir1/dir2',
        ensuring that it produces the expected string 'dir2 include'.

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
        Tests if the template engine correctly handles an include statement with a relative path that points outside the file hierarchy.

        This test case checks for a TemplateSyntaxError when an include statement with a relative path attempts to access a file outside the allowed directory structure.

        Args:
            None

        Returns:
            None

        Raises:
            TemplateSyntaxError: If the relative path points outside the file hierarchy.

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
        """
        Tests the mixing of templates in the Engine class.

        This test case verifies that the Engine can correctly render a template 
        from a directory with mixed template inheritance, ensuring that the 
        inherited templates are properly loaded and rendered in the correct order.

        The test uses a specific template 'three.html' located in the 'dir1' 
        directory to validate the mixing functionality, checking that the 
        output matches the expected result.
        """
        engine = Engine(dirs=[RELATIVE])
        template = engine.get_template("dir1/three.html")
        output = template.render(Context({}))
        self.assertEqual(output.strip(), "three dir1 three")

    def test_mixing_loop(self):
        """
        Tests that a template cannot contain a directive that leads to its own rendering, 
        causing an infinite loop. Verifies that the Engine raises a TemplateSyntaxError 
        when a relative path resolves to the same template that contains the tag, 
        preventing a potential loop in template rendering logic.
        """
        engine = Engine(dirs=[RELATIVE])
        msg = (
            "The relative path '\"./dir2/../looped.html\"' was translated to "
            "template name 'dir1/looped.html', the same template in which "
            "the tag appears."
        )
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            engine.render_to_string("dir1/looped.html")
