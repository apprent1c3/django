from django.template.defaultfilters import slugify
from django.test import SimpleTestCase
from django.utils.functional import lazy
from django.utils.safestring import mark_safe

from ..utils import setup


class SlugifyTests(SimpleTestCase):
    """
    Running slugify on a pre-escaped string leads to odd behavior,
    but the result is still safe.
    """

    @setup(
        {
            "slugify01": (
                "{% autoescape off %}{{ a|slugify }} {{ b|slugify }}{% endautoescape %}"
            )
        }
    )
    def test_slugify01(self):
        """
        Tests the slugify filter in a template by rendering a string with two variables, 
        one containing special characters and the other containing HTML entities, 
        and checks if the output matches the expected slugified result.
        """
        output = self.engine.render_to_string(
            "slugify01", {"a": "a & b", "b": mark_safe("a &amp; b")}
        )
        self.assertEqual(output, "a-b a-amp-b")

    @setup({"slugify02": "{{ a|slugify }} {{ b|slugify }}"})
    def test_slugify02(self):
        """

        Test the slugify filter functionality.

        This test case checks if the slugify filter correctly converts strings into a slug format, 
        handling special characters and HTML entities. It verifies that the filter replaces 
        special characters with hyphens and leaves HTML-safe strings unchanged, resulting 
        in a slugified output string.

        """
        output = self.engine.render_to_string(
            "slugify02", {"a": "a & b", "b": mark_safe("a &amp; b")}
        )
        self.assertEqual(output, "a-b a-amp-b")


class FunctionTests(SimpleTestCase):
    def test_slugify(self):
        self.assertEqual(
            slugify(
                " Jack & Jill like numbers 1,2,3 and 4 and silly characters ?%.$!/"
            ),
            "jack-jill-like-numbers-123-and-4-and-silly-characters",
        )

    def test_unicode(self):
        self.assertEqual(
            slugify("Un \xe9l\xe9phant \xe0 l'or\xe9e du bois"),
            "un-elephant-a-loree-du-bois",
        )

    def test_non_string_input(self):
        self.assertEqual(slugify(123), "123")

    def test_slugify_lazy_string(self):
        """
        Tests the slugify function with a lazy string.

        Verifies that the function correctly converts a string containing special characters 
        and numbers into a slug, which is a URL-friendly string of lowercase letters, 
        numbers, and hyphens. The test covers the handling of non-alphanumeric characters 
        and ensures their proper removal or replacement in the resulting slug.
        """
        lazy_str = lazy(lambda string: string, str)
        self.assertEqual(
            slugify(
                lazy_str(
                    " Jack & Jill like numbers 1,2,3 and 4 and silly characters ?%.$!/"
                )
            ),
            "jack-jill-like-numbers-123-and-4-and-silly-characters",
        )
