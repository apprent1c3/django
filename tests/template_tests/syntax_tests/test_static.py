from urllib.parse import urljoin

from django.conf import settings
from django.template import TemplateSyntaxError
from django.templatetags.static import StaticNode
from django.test import SimpleTestCase, override_settings

from ..utils import setup


@override_settings(INSTALLED_APPS=[], MEDIA_URL="media/", STATIC_URL="static/")
class StaticTagTests(SimpleTestCase):
    libraries = {"static": "django.templatetags.static"}

    @setup({"static-prefixtag01": "{% load static %}{% get_static_prefix %}"})
    def test_static_prefixtag01(self):
        """
        Tests that the static prefix tag correctly loads the static prefix from the settings when the template tag is used with the syntax {% load static %}{% get_static_prefix %}. 

        The test verifies that the output of rendering the template is equal to the value defined in the project's STATIC_URL setting, ensuring that the tag is correctly configured and functioning as expected.
        """
        output = self.engine.render_to_string("static-prefixtag01")
        self.assertEqual(output, settings.STATIC_URL)

    @setup(
        {
            "static-prefixtag02": "{% load static %}"
            "{% get_static_prefix as static_prefix %}{{ static_prefix }}"
        }
    )
    def test_static_prefixtag02(self):
        output = self.engine.render_to_string("static-prefixtag02")
        self.assertEqual(output, settings.STATIC_URL)

    @setup({"static-prefixtag03": "{% load static %}{% get_media_prefix %}"})
    def test_static_prefixtag03(self):
        """
        Test the static prefix tag functionality to ensure correct rendering of the media prefix.

        This test case verifies that the template tag correctly loads the static prefix and returns the media URL as defined in the project settings. The test validates the output of the template rendering against the expected media URL, confirming that the static prefix tag is functioning as intended.

        :raises: AssertionError if the rendered output does not match the expected media URL
        """
        output = self.engine.render_to_string("static-prefixtag03")
        self.assertEqual(output, settings.MEDIA_URL)

    @setup(
        {
            "static-prefixtag04": "{% load static %}"
            "{% get_media_prefix as media_prefix %}{{ media_prefix }}"
        }
    )
    def test_static_prefixtag04(self):
        output = self.engine.render_to_string("static-prefixtag04")
        self.assertEqual(output, settings.MEDIA_URL)

    @setup(
        {
            "t": (
                "{% load static %}{% get_media_prefix ad media_prefix %}"
                "{{ media_prefix }}"
            )
        }
    )
    def test_static_prefixtag_without_as(self):
        """

        Tests the behavior of the get_media_prefix template tag when used without the 'as' keyword.

        Verifies that a TemplateSyntaxError is raised with a message indicating that the 'as' keyword is required as the first argument in the 'get_media_prefix' tag.

        """
        msg = "First argument in 'get_media_prefix' must be 'as'"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("t")

    @setup({"static-statictag01": '{% load static %}{% static "admin/base.css" %}'})
    def test_static_statictag01(self):
        output = self.engine.render_to_string("static-statictag01")
        self.assertEqual(output, urljoin(settings.STATIC_URL, "admin/base.css"))

    @setup({"static-statictag02": "{% load static %}{% static base_css %}"})
    def test_static_statictag02(self):
        """
        Tests the static template tag by rendering a template that uses the static tag to load a base CSS file from the admin directory, verifying that the output matches the expected static URL.
        """
        output = self.engine.render_to_string(
            "static-statictag02", {"base_css": "admin/base.css"}
        )
        self.assertEqual(output, urljoin(settings.STATIC_URL, "admin/base.css"))

    @setup(
        {
            "static-statictag03": (
                '{% load static %}{% static "admin/base.css" as foo %}{{ foo }}'
            )
        }
    )
    def test_static_statictag03(self):
        """
        Tests the rendering of the static template tag when used to load a static file within a template, verifying that the resulting output matches the expected static URL.
        """
        output = self.engine.render_to_string("static-statictag03")
        self.assertEqual(output, urljoin(settings.STATIC_URL, "admin/base.css"))

    @setup(
        {"static-statictag04": "{% load static %}{% static base_css as foo %}{{ foo }}"}
    )
    def test_static_statictag04(self):
        output = self.engine.render_to_string(
            "static-statictag04", {"base_css": "admin/base.css"}
        )
        self.assertEqual(output, urljoin(settings.STATIC_URL, "admin/base.css"))

    @setup(
        {
            "static-statictag05": (
                '{% load static %}{% static "special?chars&quoted.html" %}'
            )
        }
    )
    def test_static_quotes_urls(self):
        """
        Tests the static template tag's handling of special characters and quoted URLs.

        This test ensures that the static tag correctly encodes special characters in URLs,
        such as question marks and ampersands, and that the resulting URL is properly joined
        with the static URL setting.

        The test expects the rendered output to match the expected encoded URL, verifying
        that the static tag behaves as intended when encountering special characters in URLs.
        """
        output = self.engine.render_to_string("static-statictag05")
        self.assertEqual(
            output,
            urljoin(settings.STATIC_URL, "/static/special%3Fchars%26quoted.html"),
        )

    @setup({"t": "{% load static %}{% static %}"})
    def test_static_statictag_without_path(self):
        """
        Tests that the 'static' template tag requires a path argument.

        Verifies that attempting to use the 'static' tag without providing a path
        results in a TemplateSyntaxError with a specific error message. Ensures
        that the template engine correctly enforces the requirement for a path
        argument when using the 'static' tag to serve static files.
        """
        msg = "'static' takes at least one argument (path to file)"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("t")


class StaticNodeTests(SimpleTestCase):
    def test_repr(self):
        """
        Tests the representation of a StaticNode object.

        Verifies that the repr function returns a string that accurately represents the state of the StaticNode, including its varname and path attributes. 

        The test covers cases where the varname is specified, and where it is not, ensuring that the representation remains consistent and meaningful in both scenarios.
        """
        static_node = StaticNode(varname="named-var", path="named-path")
        self.assertEqual(
            repr(static_node),
            "StaticNode(varname='named-var', path='named-path')",
        )
        static_node = StaticNode(path="named-path")
        self.assertEqual(
            repr(static_node),
            "StaticNode(varname=None, path='named-path')",
        )
