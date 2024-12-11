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
        output = self.engine.render_to_string("cache03")
        self.assertEqual(output, "cache03")

    @setup(
        {
            "cache03": "{% load cache %}{% cache 2 test %}cache03{% endcache %}",
            "cache04": "{% load cache %}{% cache 2 test %}cache04{% endcache %}",
        }
    )
    def test_cache04(self):
        self.engine.render_to_string("cache03")
        output = self.engine.render_to_string("cache04")
        self.assertEqual(output, "cache03")

    @setup({"cache05": "{% load cache %}{% cache 2 test foo %}cache05{% endcache %}"})
    def test_cache05(self):
        output = self.engine.render_to_string("cache05", {"foo": 1})
        self.assertEqual(output, "cache05")

    @setup({"cache06": "{% load cache %}{% cache 2 test foo %}cache06{% endcache %}"})
    def test_cache06(self):
        output = self.engine.render_to_string("cache06", {"foo": 2})
        self.assertEqual(output, "cache06")

    @setup(
        {
            "cache05": "{% load cache %}{% cache 2 test foo %}cache05{% endcache %}",
            "cache07": "{% load cache %}{% cache 2 test foo %}cache07{% endcache %}",
        }
    )
    def test_cache07(self):
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
        """
        Test that using the cache tag without parameters raises a TemplateSyntaxError.

        Raised exception is tested to ensure proper error handling when attempting to use the cache template tag without the required parameters.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("cache11")

    @setup({"cache12": "{% load cache %}{% cache 1 %}{% endcache %}"})
    def test_cache12(self):
        """
        Tests that a TemplateSyntaxError is raised when the cache duration in a template tag is not a valid integer.

        This test case ensures that the template engine correctly handles invalid cache duration values and raises an exception as expected.

        The test template contains a cache tag with an invalid duration value, and this function verifies that attempting to load the template results in a TemplateSyntaxError being raised.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("cache12")

    @setup({"cache13": "{% load cache %}{% cache foo bar %}{% endcache %}"})
    def test_cache13(self):
        """
        Tests if the template engine correctly raises a TemplateSyntaxError when encountering an invalid cache template tag. Specifically, verifies that the engine fails to render a template with a malformed cache declaration that is missing required arguments.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("cache13")

    @setup({"cache14": "{% load cache %}{% cache foo bar %}{% endcache %}"})
    def test_cache14(self):
        """
        Tests rendering of a template that uses the cache tag with invalid syntax, verifying that a TemplateSyntaxError is raised when the template engine attempts to render the template. The test case specifically checks the handling of cache tag with missing or incorrect end tag.
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("cache14", {"foo": "fail"})

    @setup({"cache15": "{% load cache %}{% cache foo bar %}{% endcache %}"})
    def test_cache15(self):
        """
        Tests that a TemplateSyntaxError is raised when rendering a template with a cache tag that has a variable as a cache key, where the variable is an empty list.

        This test ensures that the template engine correctly handles invalid cache key values and raises an exception when necessary, preventing potential caching issues.

        Args:
            None

        Returns:
            None

        Raises:
            TemplateSyntaxError: When rendering a template with an invalid cache key value.

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
        """
        Sets up the class-level test environment.

        This method is called once before running all tests in the class. It initializes 
        the engine with support for Django's cache templating tag and calls the parent 
        class's setup method to perform any additional setup.

        The engine is configured to include the 'cache' library from 'django.templatetags.cache', 
        enabling the use of caching functionality in the tests.

        Returns:
            None
        """
        cls.engine = Engine(libraries={"cache": "django.templatetags.cache"})
        super().setUpClass()

    def test_cache_regression_20130(self):
        """
        Tests the cache regression for issue 20130.

        This test case verifies that the cache fragment name is correctly set when
        using the cache template tag. It ensures that the fragment name is properly
        assigned and matches the expected output, helping to prevent cache-related
        regressions.

         Args:
            None

         Returns:
            None

         Raises:
            AssertionError: If the cache fragment name does not match the expected
                             value 'regression_20130'.

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
