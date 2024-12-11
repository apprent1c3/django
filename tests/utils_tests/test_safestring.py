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
        Tests the behavior of the mark_safe function in a templating context.

        This test case verifies that when a string marked as safe is rendered in a template,
        it is output exactly as is, without any escaping. Additionally, it checks that 
        if the string is explicitly escaped using the force_escape filter, it is properly 
        HTML-escaped, replacing special characters like '&' with their corresponding 
        HTML entities, such as '&amp;'.
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
        e = customescape("<a&b>")
        s = mark_safe(e)
        self.assertIs(s, e)

        self.assertRenderEqual("{{ s }}", "<<a&b>>", s=s)
        self.assertRenderEqual("{{ s|force_escape }}", "&lt;a&amp;b&gt;", s=s)

    def test_mark_safe_lazy(self):
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

        Tests the behavior of the mark_safe function when passed an object that implements the __str__ method.
        The function verifies that mark_safe properly handles and renders objects with custom string representations.
        It checks that the rendered output matches the expected string, ensuring the correct implementation of the mark_safe function.

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
        """
        Tests the addition of lazy safe text and safe text.

        This function checks if the correct output is rendered when combining lazy safe text
        with safe text. It verifies that the escaped characters are handled correctly
        in two different scenarios: HTML escaping and JavaScript escaping.

        The test case ensures that the resulting string is as expected, with the special
        characters '&b' being preserved as safe text, while the lazy safe text 'a' is
        properly escaped in both HTML and JavaScript contexts.

        The test covers two main cases:
            - When using html.escape() for HTML escaping
            - When using html.escapejs() for JavaScript escaping

        Both cases verify that the rendered output matches the expected result 'a&b', 
        indicating that the combination of lazy safe text and safe text is handled correctly.
        """
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
        """
        Tests the default behavior of SafeString objects when attempting to assign a value to an attribute that does not exist, specifically verifying that an AttributeError is raised with the expected message when trying to assign to 'dynamic_attr'.
        """
        s = SafeString("a&b")
        msg = "object has no attribute 'dynamic_attr'"
        with self.assertRaisesMessage(AttributeError, msg):
            s.dynamic_attr = True

    def test_default_safe_data_additional_attrs(self):
        """

        Tests that attempting to set a non-existent attribute on a SafeData object raises an AttributeError.

        Verifies that the SafeData class does not dynamically create attributes when assigned, ensuring data integrity and safety by enforcing attribute existence checks.

        """
        s = SafeData()
        msg = "object has no attribute 'dynamic_attr'"
        with self.assertRaisesMessage(AttributeError, msg):
            s.dynamic_attr = True
