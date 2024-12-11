from django.template import Context, Template
from django.test import SimpleTestCase
from django.utils import html, translation
from django.utils.functional import Promise, lazy, lazystr
from django.utils.safestring import SafeData, SafeString, mark_safe
from django.utils.translation import gettext_lazy


class customescape(str):
    def __html__(self):
        # Implement specific and wrong escaping in order to be able to detect
        # when it runs.
        return self.replace("<", "<<").replace(">", ">>")


class SafeStringTest(SimpleTestCase):
    def assertRenderEqual(self, tpl, expected, **context):
        context = Context(context)
        tpl = Template(tpl)
        self.assertEqual(tpl.render(context), expected)

    def test_mark_safe(self):
        """

        Tests the functionality of the mark_safe feature, ensuring that marked strings are rendered without HTML escaping.

        The test verifies two scenarios: 

        1. Rendering a marked string directly, confirming that it is not escaped.
        2. Rendering a marked string with forced escaping, confirming that special characters are properly escaped.

        """
        s = mark_safe("a&b")

        self.assertRenderEqual("{{ s }}", "a&b", s=s)
        self.assertRenderEqual("{{ s|force_escape }}", "a&amp;b", s=s)

    def test_mark_safe_str(self):
        """
        Calling str() on a SafeString instance doesn't lose the safe status.
        """
        s = mark_safe("a&b")
        self.assertIsInstance(str(s), type(s))

    def test_mark_safe_object_implementing_dunder_html(self):
        """
        Test that an object implementing the __html__ dunder method is properly marked as safe.
        This test verifies that when an object with a custom HTML representation is wrapped in a mark_safe call, 
        it can be safely rendered in a template without being auto-escaped, but will be escaped if the 
        force_escape filter is applied.
        """
        e = customescape("<a&b>")
        s = mark_safe(e)
        self.assertIs(s, e)

        self.assertRenderEqual("{{ s }}", "<<a&b>>", s=s)
        self.assertRenderEqual("{{ s|force_escape }}", "&lt;a&amp;b&gt;", s=s)

    def test_mark_safe_lazy(self):
        """

        Tests the rendering of a lazy string marked as safe.

        Verifies that the marked string is correctly identified as a Promise object and
        renders the expected output when used in a template. Additionally, checks that
        converting the marked string to a regular string results in a SafeData object,
        indicating that the string's safety is preserved.

        """
        safe_s = mark_safe(lazystr("a&b"))

        self.assertIsInstance(safe_s, Promise)
        self.assertRenderEqual("{{ s }}", "a&b", s=safe_s)
        self.assertIsInstance(str(safe_s), SafeData)

    def test_mark_safe_lazy_i18n(self):
        s = mark_safe(gettext_lazy("name"))
        tpl = Template("{{ s }}")
        with translation.override("fr"):
            self.assertEqual(tpl.render(Context({"s": s})), "nom")

    def test_mark_safe_object_implementing_dunder_str(self):
        """
        Tests that the mark_safe function correctly handles objects that implement the __str__ method, ensuring their string representation is rendered without HTML escaping.
        """
        class Obj:
            def __str__(self):
                return "<obj>"

        s = mark_safe(Obj())

        self.assertRenderEqual("{{ s }}", "<obj>", s=s)

    def test_mark_safe_result_implements_dunder_html(self):
        self.assertEqual(mark_safe("a&b").__html__(), "a&b")

    def test_mark_safe_lazy_result_implements_dunder_html(self):
        self.assertEqual(mark_safe(lazystr("a&b")).__html__(), "a&b")

    def test_add_lazy_safe_text_and_safe_text(self):
        s = html.escape(lazystr("a"))
        s += mark_safe("&b")
        self.assertRenderEqual("{{ s }}", "a&b", s=s)

        s = html.escapejs(lazystr("a"))
        s += mark_safe("&b")
        self.assertRenderEqual("{{ s }}", "a&b", s=s)

    def test_mark_safe_as_decorator(self):
        """
        mark_safe used as a decorator leaves the result of a function
        unchanged.
        """

        def clean_string_provider():
            return "<html><body>dummy</body></html>"

        self.assertEqual(mark_safe(clean_string_provider)(), clean_string_provider())

    def test_mark_safe_decorator_does_not_affect_dunder_html(self):
        """
        mark_safe doesn't affect a callable that has an __html__() method.
        """

        class SafeStringContainer:
            def __html__(self):
                return "<html></html>"

        self.assertIs(mark_safe(SafeStringContainer), SafeStringContainer)

    def test_mark_safe_decorator_does_not_affect_promises(self):
        """
        mark_safe doesn't affect lazy strings (Promise objects).
        """

        def html_str():
            return "<html></html>"

        lazy_str = lazy(html_str, str)()
        self.assertEqual(mark_safe(lazy_str), html_str())

    def test_default_additional_attrs(self):
        s = SafeString("a&b")
        msg = "object has no attribute 'dynamic_attr'"
        with self.assertRaisesMessage(AttributeError, msg):
            s.dynamic_attr = True

    def test_default_safe_data_additional_attrs(self):
        s = SafeData()
        msg = "object has no attribute 'dynamic_attr'"
        with self.assertRaisesMessage(AttributeError, msg):
            s.dynamic_attr = True
