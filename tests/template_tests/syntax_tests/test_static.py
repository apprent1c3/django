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
        #: Tests the correct rendering of the 'static-prefixtag03' template tag.
        #: 
        #: Verifies that the rendered output of the template tag is equal to the MEDIA_URL setting.
        #: 
        #: This test case ensures that the static prefix tag loads the media prefix correctly from the settings.
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
        msg = "First argument in 'get_media_prefix' must be 'as'"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("t")

    @setup({"static-statictag01": '{% load static %}{% static "admin/base.css" %}'})
    def test_static_statictag01(self):
        """
        Tests the functionality of the static tag when used with a static URL, verifying that the rendered output matches the expected static URL for the 'admin/base.css' file.
        """
        output = self.engine.render_to_string("static-statictag01")
        self.assertEqual(output, urljoin(settings.STATIC_URL, "admin/base.css"))

    @setup({"static-statictag02": "{% load static %}{% static base_css %}"})
    def test_static_statictag02(self):
        """
        Test the rendering of the static template tag when the base CSS is specified.

        This test case checks if the static template tag correctly renders the URL 
        for the base CSS file when it is provided as a variable. It verifies that the 
        output matches the expected URL, which is the concatenation of the static URL 
        and the base CSS file path.
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
        .. function:: test_static_statictag03

           Tests the functionality of the static template tag with the \"as\" keyword.

           Verifies that the static template tag correctly loads and renders a static file,
           and that the resulting URL is properly joined with the STATIC_URL setting.

           The test checks the rendered output against the expected URL of the static file.
        """
        output = self.engine.render_to_string("static-statictag03")
        self.assertEqual(output, urljoin(settings.STATIC_URL, "admin/base.css"))

    @setup(
        {"static-statictag04": "{% load static %}{% static base_css as foo %}{{ foo }}"}
    )
    def test_static_statictag04(self):
        """

         Tests the rendering of the static template tag when used with the load static tag.

         The test checks that the static tag correctly generates a URL for a static file
         when used in conjunction with the load static tag. It verifies that the output
         matches the expected static URL, which is constructed by joining the static URL
         from the settings with the specified static file path.

        """
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
        Test that the static template tag correctly handles special characters in URLs.

        This test ensures that special characters, such as question marks and ampersands, are properly URL encoded when using the static template tag. The expected output is the STATIC_URL joined with the URL-encoded path of the static file.
        """
        output = self.engine.render_to_string("static-statictag05")
        self.assertEqual(
            output,
            urljoin(settings.STATIC_URL, "/static/special%3Fchars%26quoted.html"),
        )

    @setup({"t": "{% load static %}{% static %}"})
    def test_static_statictag_without_path(self):
        msg = "'static' takes at least one argument (path to file)"
        with self.assertRaisesMessage(TemplateSyntaxError, msg):
            self.engine.render_to_string("t")


class StaticNodeTests(SimpleTestCase):
    def test_repr(self):
        """
        Tests the string representation of a StaticNode object.

        Verifies that the repr function returns a string that accurately reflects the
        object's attributes, including varname and path. The test cases cover scenarios
        where varname is provided and where it is not, ensuring that the representation
        is correct in both situations.

        The expected output is a string in the format 'StaticNode(varname='varname', path='path')',
        where 'varname' and 'path' are the actual values of the object's attributes.
        If varname is not provided, it is represented as None in the string representation.

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
