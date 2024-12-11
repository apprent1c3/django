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

        Tests the discovery of templatetags within the Django template engine.

        This function verifies that the template engine correctly loads and resolves templatetags
        from installed applications, including custom tags and overridden built-in tags.
        It checks that the engine can find tags in the specified libraries, including those 
        defined in subpackages and overridden by custom implementations.

        The test covers various scenarios, including:
        - Custom templatetags defined in an application
        - Templatetags defined in a subpackage of an application
        - Overridden built-in templatetags
        - Custom templatetags with an alternate name

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
        :param self: reference to the instance of the class
        :returns: None
        :raises: AssertionError if the rendered template does not match the expected output

        Tests whether the autoescape feature is enabled by default in Django templates.
        The test checks if HTML special characters in template variables are properly escaped.
        In this case, it verifies that an ampersand (&) in the 'name' variable is replaced with its corresponding HTML entity (&amp;).
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
        Test rendering of templates using the Django template engine and pathlib.

        This test verifies that the Django template engine can correctly render templates
        from a specified directory using pathlib. It checks that the engine can locate the
        template, render it with provided context, and return the expected output.

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
