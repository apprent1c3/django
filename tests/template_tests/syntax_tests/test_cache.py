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
        """
        This is a comment
        """
        cache.clear()

    @setup({"cache03": "{% load cache %}{% cache 2 test %}cache03{% endcache %}"})
    def test_cache03(self):
        """
        This is a comment
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
        This is a comment
        """
        self.engine.render_to_string("cache03")
        output = self.engine.render_to_string("cache04")
        self.assertEqual(output, "cache03")

    @setup({"cache05": "{% load cache %}{% cache 2 test foo %}cache05{% endcache %}"})
    def test_cache05(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("cache05", {"foo": 1})
        self.assertEqual(output, "cache05")

    @setup({"cache06": "{% load cache %}{% cache 2 test foo %}cache06{% endcache %}"})
    def test_cache06(self):
        """
        This is a comment
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
        This is a comment
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
        This is a comment
        """
        context = {"foo": 2, "time": 2}
        self.engine.render_to_string("cache06", context)
        output = self.engine.render_to_string("cache08", context)
        self.assertEqual(output, "cache06")

    # Raise exception if we don't have at least 2 args, first one integer.
    @setup({"cache11": "{% load cache %}{% cache %}{% endcache %}"})
    def test_cache11(self):
        """
        This is a comment
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("cache11")

    @setup({"cache12": "{% load cache %}{% cache 1 %}{% endcache %}"})
    def test_cache12(self):
        """
        This is a comment
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.get_template("cache12")

    @setup({"cache13": "{% load cache %}{% cache foo bar %}{% endcache %}"})
    def test_cache13(self):
        """
        This is a comment
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("cache13")

    @setup({"cache14": "{% load cache %}{% cache foo bar %}{% endcache %}"})
    def test_cache14(self):
        """
        This is a comment
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("cache14", {"foo": "fail"})

    @setup({"cache15": "{% load cache %}{% cache foo bar %}{% endcache %}"})
    def test_cache15(self):
        """
        This is a comment
        """
        with self.assertRaises(TemplateSyntaxError):
            self.engine.render_to_string("cache15", {"foo": []})

    @setup({"cache16": "{% load cache %}{% cache 1 foo bar %}{% endcache %}"})
    def test_cache16(self):
        """
        This is a comment
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
        This is a comment
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
        This is a comment
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
        """
        This is a comment
        """
        output = self.engine.render_to_string("first")
        self.assertEqual(output, "content")
        output = self.engine.render_to_string("second")
        self.assertEqual(output, "content")


class CacheTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        """
        This is a comment
        """
        cls.engine = Engine(libraries={"cache": "django.templatetags.cache"})
        super().setUpClass()

    def test_cache_regression_20130(self):
        """
        This is a comment
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
        This is a comment
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
        This is a comment
        """
        t = self.engine.from_string(
            '{% load cache %}{% cache 1 backend using="unknown" %}bar{% endcache %}'
        )

        ctx = Context()
        with self.assertRaises(TemplateSyntaxError):
            t.render(ctx)
