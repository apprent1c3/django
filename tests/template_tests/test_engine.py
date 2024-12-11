import os

from django.core.exceptions import ImproperlyConfigured
from django.template import Context
from django.template.engine import Engine
from django.test import SimpleTestCase, override_settings

from .utils import ROOT, TEMPLATE_DIR

OTHER_DIR = os.path.join(ROOT, "other_templates")


class EngineTest(SimpleTestCase):
    def test_repr_empty(self):
        """
        Tests the representation of an Engine instance with default settings. 

        Verifies that the string representation of the Engine object contains all the expected properties and their respective default values, including the application directory settings, debug mode, template loaders, invalid string handling, file character encoding, built-in tags and filters, and auto-escaping configuration.
        """
        engine = Engine()
        self.assertEqual(
            repr(engine),
            "<Engine: app_dirs=False debug=False loaders=[("
            "'django.template.loaders.cached.Loader', "
            "['django.template.loaders.filesystem.Loader'])] "
            "string_if_invalid='' file_charset='utf-8' builtins=["
            "'django.template.defaulttags', 'django.template.defaultfilters', "
            "'django.template.loader_tags'] autoescape=True>",
        )

    def test_repr(self):
        """

        Tests the representation of the Engine class.

        This test ensures that the __repr__ method of the Engine class returns a string
        that accurately represents the engine's configuration, including template directories,
        context processors, debug mode, template loaders, and other settings. The test verifies
        that the repr string correctly reflects the engine's attributes, such as the directories
        to search for templates, whether to autoescape template content, and custom libraries.

        """
        engine = Engine(
            dirs=[TEMPLATE_DIR],
            context_processors=["django.template.context_processors.debug"],
            debug=True,
            loaders=["django.template.loaders.filesystem.Loader"],
            string_if_invalid="x",
            file_charset="utf-16",
            libraries={"custom": "template_tests.templatetags.custom"},
            autoescape=False,
        )
        self.assertEqual(
            repr(engine),
            f"<Engine: dirs=[{TEMPLATE_DIR!r}] app_dirs=False "
            "context_processors=['django.template.context_processors.debug'] "
            "debug=True loaders=['django.template.loaders.filesystem.Loader'] "
            "string_if_invalid='x' file_charset='utf-16' "
            "libraries={'custom': 'template_tests.templatetags.custom'} "
            "builtins=['django.template.defaulttags', "
            "'django.template.defaultfilters', 'django.template.loader_tags'] "
            "autoescape=False>",
        )


class RenderToStringTest(SimpleTestCase):
    def setUp(self):
        self.engine = Engine(dirs=[TEMPLATE_DIR])

    def test_basic_context(self):
        self.assertEqual(
            self.engine.render_to_string("test_context.html", {"obj": "test"}),
            "obj:test\n",
        )

    def test_autoescape_off(self):
        """

        Tests the rendering of a template with autoescape turned off.

        Checks if the engine correctly renders a template without escaping special characters, 
        by passing a string containing HTML markup as a context variable and verifying that 
        the output is not escaped.

        """
        engine = Engine(dirs=[TEMPLATE_DIR], autoescape=False)
        self.assertEqual(
            engine.render_to_string("test_context.html", {"obj": "<script>"}),
            "obj:<script>\n",
        )


class GetDefaultTests(SimpleTestCase):
    @override_settings(TEMPLATES=[])
    def test_no_engines_configured(self):
        msg = "No DjangoTemplates backend is configured."
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            Engine.get_default()

    @override_settings(
        TEMPLATES=[
            {
                "NAME": "default",
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "OPTIONS": {"file_charset": "abc"},
            }
        ]
    )
    def test_single_engine_configured(self):
        self.assertEqual(Engine.get_default().file_charset, "abc")

    @override_settings(
        TEMPLATES=[
            {
                "NAME": "default",
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "OPTIONS": {"file_charset": "abc"},
            },
            {
                "NAME": "other",
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "OPTIONS": {"file_charset": "def"},
            },
        ]
    )
    def test_multiple_engines_configured(self):
        self.assertEqual(Engine.get_default().file_charset, "abc")


class LoaderTests(SimpleTestCase):
    def test_origin(self):
        """

        Tests that the template origin is correctly identified.

        Verifies that when a template is retrieved from the engine, its origin
        matches the expected template name. This ensures that the template
        engine is correctly tracking the source of templates.

        The test checks the template name of the retrieved template against the
        expected name 'index.html', confirming that the engine is functioning
        as expected.

        """
        engine = Engine(dirs=[TEMPLATE_DIR], debug=True)
        template = engine.get_template("index.html")
        self.assertEqual(template.origin.template_name, "index.html")

    def test_loader_priority(self):
        """
        #21460 -- The order of template loader works.
        """
        loaders = [
            "django.template.loaders.filesystem.Loader",
            "django.template.loaders.app_directories.Loader",
        ]
        engine = Engine(dirs=[OTHER_DIR, TEMPLATE_DIR], loaders=loaders)
        template = engine.get_template("priority/foo.html")
        self.assertEqual(template.render(Context()), "priority\n")

    def test_cached_loader_priority(self):
        """
        The order of template loader works. Refs #21460.
        """
        loaders = [
            (
                "django.template.loaders.cached.Loader",
                [
                    "django.template.loaders.filesystem.Loader",
                    "django.template.loaders.app_directories.Loader",
                ],
            ),
        ]
        engine = Engine(dirs=[OTHER_DIR, TEMPLATE_DIR], loaders=loaders)

        template = engine.get_template("priority/foo.html")
        self.assertEqual(template.render(Context()), "priority\n")

        template = engine.get_template("priority/foo.html")
        self.assertEqual(template.render(Context()), "priority\n")
