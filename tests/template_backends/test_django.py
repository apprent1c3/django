from pathlib import Path

from template_tests.test_response import test_processor_name

from django.template import Context, EngineHandler, RequestContext
from django.template.backends.django import DjangoTemplates
from django.template.library import InvalidTemplateLibrary
from django.test import RequestFactory, override_settings

from .test_dummy import TemplateStringsTests


class DjangoTemplatesTests(TemplateStringsTests):
    engine_class = DjangoTemplates
    backend_name = "django"
    request_factory = RequestFactory()

    def test_context_has_priority_over_template_context_processors(self):
        # See ticket #23789.
        engine = DjangoTemplates(
            {
                "DIRS": [],
                "APP_DIRS": False,
                "NAME": "django",
                "OPTIONS": {
                    "context_processors": [test_processor_name],
                },
            }
        )

        template = engine.from_string("{{ processors }}")
        request = self.request_factory.get("/")

        # Context processors run
        content = template.render({}, request)
        self.assertEqual(content, "yes")

        # Context overrides context processors
        content = template.render({"processors": "no"}, request)
        self.assertEqual(content, "no")

    def test_render_requires_dict(self):
        """django.Template.render() requires a dict."""
        engine = DjangoTemplates(
            {
                "DIRS": [],
                "APP_DIRS": False,
                "NAME": "django",
                "OPTIONS": {},
            }
        )
        template = engine.from_string("")
        context = Context()
        request_context = RequestContext(self.request_factory.get("/"), {})
        msg = "context must be a dict rather than Context."
        with self.assertRaisesMessage(TypeError, msg):
            template.render(context)
        msg = "context must be a dict rather than RequestContext."
        with self.assertRaisesMessage(TypeError, msg):
            template.render(request_context)

    @override_settings(INSTALLED_APPS=["template_backends.apps.good"])
    def test_templatetag_discovery(self):
        """
        Tests the discovery of template tags within a Django template engine.

        This test case verifies that the template engine correctly loads and identifies 
        template tags from various sources, including custom and built-in libraries, 
        when specific options are provided. It checks the engine's ability to find tags 
        in custom libraries defined in the OPTIONS dictionary, and compares the 
        expected library paths with the actual paths found by the engine. The test 
        ensures that both custom and built-in tags are properly loaded, including 
        those defined in an alternate library and those overriding existing ones.
        """
        engine = DjangoTemplates(
            {
                "DIRS": [],
                "APP_DIRS": False,
                "NAME": "django",
                "OPTIONS": {
                    "libraries": {
                        "alternate": (
                            "template_backends.apps.good.templatetags.good_tags"
                        ),
                        "override": (
                            "template_backends.apps.good.templatetags.good_tags"
                        ),
                    },
                },
            }
        )

        # libraries are discovered from installed applications
        self.assertEqual(
            engine.engine.libraries["good_tags"],
            "template_backends.apps.good.templatetags.good_tags",
        )
        self.assertEqual(
            engine.engine.libraries["subpackage.tags"],
            "template_backends.apps.good.templatetags.subpackage.tags",
        )
        # libraries are discovered from django.templatetags
        self.assertEqual(
            engine.engine.libraries["static"],
            "django.templatetags.static",
        )
        # libraries passed in OPTIONS are registered
        self.assertEqual(
            engine.engine.libraries["alternate"],
            "template_backends.apps.good.templatetags.good_tags",
        )
        # libraries passed in OPTIONS take precedence over discovered ones
        self.assertEqual(
            engine.engine.libraries["override"],
            "template_backends.apps.good.templatetags.good_tags",
        )

    @override_settings(INSTALLED_APPS=["template_backends.apps.importerror"])
    def test_templatetag_discovery_import_error(self):
        """
        Import errors in tag modules should be reraised with a helpful message.
        """
        with self.assertRaisesMessage(
            InvalidTemplateLibrary,
            "ImportError raised when trying to load "
            "'template_backends.apps.importerror.templatetags.broken_tags'",
        ) as cm:
            DjangoTemplates(
                {
                    "DIRS": [],
                    "APP_DIRS": False,
                    "NAME": "django",
                    "OPTIONS": {},
                }
            )
        self.assertIsInstance(cm.exception.__cause__, ImportError)

    def test_builtins_discovery(self):
        """

        Tests the discovery of built-in template tags in Django's templating engine.

        This test case verifies that the engine correctly incorporates both the default
        built-in template tags and any custom tags specified in the template engine's
        configuration. It checks that the built-in tags from Django's core, as well as
        the custom 'good_tags' from the 'template_backends.apps.good.templatetags' module,
        are properly registered and available for use in templates.

        The test configuration intentionally disables app directories to isolate the
        test to the explicitly configured built-in tags, ensuring that only the specified
        tags are loaded and recognized by the engine.

        """
        engine = DjangoTemplates(
            {
                "DIRS": [],
                "APP_DIRS": False,
                "NAME": "django",
                "OPTIONS": {
                    "builtins": ["template_backends.apps.good.templatetags.good_tags"],
                },
            }
        )

        self.assertEqual(
            engine.engine.builtins,
            [
                "django.template.defaulttags",
                "django.template.defaultfilters",
                "django.template.loader_tags",
                "template_backends.apps.good.templatetags.good_tags",
            ],
        )

    def test_autoescape_off(self):
        templates = [
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "OPTIONS": {"autoescape": False},
            }
        ]
        engines = EngineHandler(templates=templates)
        self.assertEqual(
            engines["django"]
            .from_string("Hello, {{ name }}")
            .render({"name": "Bob & Jim"}),
            "Hello, Bob & Jim",
        )

    def test_autoescape_default(self):
        """
        -tests the auto-escaping behavior of the template engine when rendering a template string with HTML special characters.

         The function verifies that the default auto-escape functionality correctly escapes special characters, 
         replacing '&' with '&amp;' to prevent potential HTML injection attacks and ensure safe output.
        """
        templates = [
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
            }
        ]
        engines = EngineHandler(templates=templates)
        self.assertEqual(
            engines["django"]
            .from_string("Hello, {{ name }}")
            .render({"name": "Bob & Jim"}),
            "Hello, Bob &amp; Jim",
        )

    def test_default_template_loaders(self):
        """The cached template loader is always enabled by default."""
        for debug in (True, False):
            with self.subTest(DEBUG=debug), self.settings(DEBUG=debug):
                engine = DjangoTemplates(
                    {"DIRS": [], "APP_DIRS": True, "NAME": "django", "OPTIONS": {}}
                )
                self.assertEqual(
                    engine.engine.loaders,
                    [
                        (
                            "django.template.loaders.cached.Loader",
                            [
                                "django.template.loaders.filesystem.Loader",
                                "django.template.loaders.app_directories.Loader",
                            ],
                        )
                    ],
                )

    def test_dirs_pathlib(self):
        """
        Tests the rendering of a Django template using the DIRS setting to specify a template location, verifying that the rendered output matches the expected result.

        The test case uses the DjangoTemplates engine to load a template named 'hello.html' from a specific directory, and then checks if the rendered template with the given context produces the expected string.

        This test ensures that the template engine is correctly configured to use the DIRS setting to find templates, and that the rendering process works as expected with the provided context.

        """
        engine = DjangoTemplates(
            {
                "DIRS": [Path(__file__).parent / "templates" / "template_backends"],
                "APP_DIRS": False,
                "NAME": "django",
                "OPTIONS": {},
            }
        )
        template = engine.get_template("hello.html")
        self.assertEqual(template.render({"name": "Joe"}), "Hello Joe!\n")
