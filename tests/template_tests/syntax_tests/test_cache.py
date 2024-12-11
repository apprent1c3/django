from django.core.cache import cache
from django.template import Context, Engine, TemplateSyntaxError
from django.test import SimpleTestCase, override_settings

from ..utils import setup


class CacheTagTests(SimpleTestCase):
    libraries = {
        "cache": "django.templatetags.cache",
        "custom": "template_tests.templatetags.custom",
    }

    def tearDown(self):
        cache.clear()

    @setup({"cache03": "{% load cache %}{% cache 2 test %}cache03{% endcache %}"})
    def test_cache03(self):
        """

        Test the caching mechanism with a template that uses the cache tag.

        This test renders a template containing a cached section and verifies that the
        cached content is correctly returned. The test checks that the rendered output
        matches the expected result, ensuring that the caching functionality works as
        expected.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the rendered output does not match the expected result.

        """
        output = self.engine.render_to_string("cache03")
        self.assertEqual(output, "cache03")

    @setup(
        {
            "cache03": "{% load cache %}{% cache 2 test %}cache03{% endcache %}",
            "cache04": "{% load cache %}{% cache 2 test %}cache04{% endcache %}",
        }
    )
    def test_cache04(self):
        """

        Tests the behavior of the cache template tag when rendering multiple cached sections.

        This test case checks if the cached content is correctly reused when multiple templates
        contain the same cache tag with the same parameters, but with different template content.
        It verifies that the rendered output of the second template matches the content of the first template,
        demonstrating that the cache tag is working correctly and reusing the cached content.

        The test setup includes two cached sections, 'cache03' and 'cache04', which are used to evaluate
        the cache tag's behavior in this scenario.

        """
        self.engine.render_to_string("cache03")
        output = self.engine.render_to_string("cache04")
        self.assertEqual(output, "cache03")

    @setup({"cache05": "{% load cache %}{% cache 2 test foo %}cache05{% endcache %}"})
    def test_cache05(self):
        output = self.engine.render_to_string("cache05", {"foo": 1})
        self.assertEqual(output, "cache05")

    @setup({"cache06": "{% load cache %}{% cache 2 test foo %}cache06{% endcache %}"})
    def test_cache06(self):
        """

        Test the cache template tag with a render timeout of 2 seconds.

        This test case checks that the cache tag correctly caches a block of content
        and returns the cached output when the template is rendered. The test template
        'cache06' is used, which contains a cache block with a timeout of 2 seconds.

        The test verifies that the rendered output matches the expected cached output.

        """
        output = self.engine.render_to_string("cache06", {"foo": 2})
        self.assertEqual(output, "cache06")

    @setup(
        {
            "cache05": "{% load cache %}{% cache 2 test foo %}cache05{% endcache %}",
            "cache07": "{% load cache %}{% cache 2 test foo %}cache07{% endcache %}",
        }
    )
    def test_cache07(self):
        """

        Tests the cache functionality to ensure that the cache key is correctly generated 
        and shared across different templates with the same cache parameters.

        The test verifies that when two templates have the same cache parameters but 
        different contents, the cache output is correctly rendered and matches the 
        expected output. This ensures that the caching mechanism is working as 
        expected and that templates with identical cache parameters will share the 
        same cache entry.

        """
        context = {"foo": 1}
        self.engine.render_to_string("cache05", context)
        output = self.engine.render_to_string("cache07", context)
        self.assertEqual(output, "cache05")

    @setup(
        {
            "cache06": "{% load cache %}{% cache 2 test foo %}cache06{% endcache %}",
            "cache08": "{% load cache %}{% cache time test foo %}cache08{% endcache %}",
        }
    )
    def test_cache08(self):
        """
        Allow first argument to be a variable.
        """
        context = {"foo": 2, "time": 2}
        self.engine.render_to_string("cache06", context)
        output = self.engine.render_to_string("cache08", context)
        self.assertEqual(output, "cache06")

    # Raise exception if we don't have at least 2 args, first one integer.
    @setup({"cache11": "{% load cache %}{% cache %}{% endcache %}"})
    def test_cache11(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("cache11")

    @setup({"cache12": "{% load cache %}{% cache 1 %}{% endcache %}"})
    def test_cache12(self):
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("cache12")

    @setup({"cache13": "{% load cache %}{% cache foo bar %}{% endcache %}"})
    def test_cache13(self):
        """
        Tests that a TemplateSyntaxError is raised when the cache template tag is used with invalid arguments. 

        The function verifies that the template engine correctly handles and rejects a cache template tag with an incorrect number or type of arguments, ensuring that the syntax is enforced and preventing potential rendering issues.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("cache13")

    @setup({"cache14": "{% load cache %}{% cache foo bar %}{% endcache %}"})
    def test_cache14(self):
        """

        Tests that a TemplateSyntaxError is raised when the cache tag is used 
        with an incorrectly formatted argument.

        The test case verifies that the template engine properly enforces 
        the correct syntax for the cache tag, ensuring that any invalid 
        usage is detected and reported.

        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("cache14", {"foo": "fail"})

    @setup({"cache15": "{% load cache %}{% cache foo bar %}{% endcache %}"})
    def test_cache15(self):
        """

        Test that a TemplateSyntaxError is raised when attempting to cache a template with a variable that is incompatible with caching.

        This test case covers the scenario where the cache tag is used with a variable that cannot be serialized, such as an empty list. 
        It verifies that the template engine correctly handles this situation and raises a TemplateSyntaxError.

        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("cache15", {"foo": []})

    @setup({"cache16": "{% load cache %}{% cache 1 foo bar %}{% endcache %}"})
    def test_cache16(self):
        """
        Regression test for #7460.
        """
        output = self.engine.render_to_string(
            "cache16", {"foo": "foo", "bar": "with spaces"}
        )
        self.assertEqual(output, "")

    @setup(
        {
            "cache17": (
                "{% load cache %}{% cache 10 long_cache_key poem %}Some Content"
                "{% endcache %}"
            )
        }
    )
    def test_cache17(self):
        """
        Regression test for #11270.
        """
        output = self.engine.render_to_string(
            "cache17",
            {
                "poem": (
                    "Oh freddled gruntbuggly/Thy micturations are to me/"
                    "As plurdled gabbleblotchits/On a lurgid bee/"
                    "That mordiously hath bitled out/Its earted jurtles/"
                    "Into a rancid festering/Or else I shall rend thee in the "
                    "gobberwarts with my blurglecruncheon/See if I don't."
                ),
            },
        )
        self.assertEqual(output, "Some Content")

    @setup(
        {
            "cache18": (
                '{% load cache custom %}{% cache 2|noop:"x y" cache18 %}cache18'
                "{% endcache %}"
            )
        }
    )
    def test_cache18(self):
        """
        Test whitespace in filter arguments
        """
        output = self.engine.render_to_string("cache18")
        self.assertEqual(output, "cache18")

    @setup(
        {
            "first": "{% load cache %}{% cache None fragment19 %}content{% endcache %}",
            "second": (
                "{% load cache %}{% cache None fragment19 %}not rendered{% endcache %}"
            ),
        }
    )
    def test_none_timeout(self):
        """A timeout of None means "cache forever"."""
        output = self.engine.render_to_string("first")
        self.assertEqual(output, "content")
        output = self.engine.render_to_string("second")
        self.assertEqual(output, "content")


class CacheTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = Engine(libraries={"cache": "django.templatetags.cache"})
        super().setUpClass()

    def test_cache_regression_20130(self):
        """
        Tests the cache functionality to ensure it handles fragment names correctly, specifically addressing a regression issue (#20130).

        Verifies that the cache node's fragment name matches the expected value, confirming that the caching mechanism is working as intended and not regressing to previous behavior.

        This test case is essential to prevent regressions in the caching system and ensure that it continues to function correctly in various scenarios.
        """
        t = self.engine.from_string(
            "{% load cache %}{% cache 1 regression_20130 %}foo{% endcache %}"
        )
        cachenode = t.nodelist[1]
        self.assertEqual(cachenode.fragment_name, "regression_20130")

    @override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "default",
            },
            "template_fragments": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "fragments",
            },
        }
    )
    def test_cache_fragment_cache(self):
        """
        When a cache called "template_fragments" is present, the cache tag
        will use it in preference to 'default'
        """
        t1 = self.engine.from_string(
            "{% load cache %}{% cache 1 fragment %}foo{% endcache %}"
        )
        t2 = self.engine.from_string(
            '{% load cache %}{% cache 1 fragment using="default" %}bar{% endcache %}'
        )

        ctx = Context()
        o1 = t1.render(ctx)
        o2 = t2.render(ctx)

        self.assertEqual(o1, "foo")
        self.assertEqual(o2, "bar")

    def test_cache_missing_backend(self):
        """
        When a cache that doesn't exist is specified, the cache tag will
        raise a TemplateSyntaxError
        '"""
        t = self.engine.from_string(
            '{% load cache %}{% cache 1 backend using="unknown" %}bar{% endcache %}'
        )

        ctx = Context()
        with self.assertRaises(TemplateSyntaxError):
            t.render(ctx)
