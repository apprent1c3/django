from django.forms import SlugField
from django.test import SimpleTestCase


class SlugFieldTest(SimpleTestCase):
    def test_slugfield_normalization(self):
        f = SlugField()
        self.assertEqual(f.clean("    aa-bb-cc    "), "aa-bb-cc")

    def test_slugfield_unicode_normalization(self):
        """
        Tests the SlugField's unicode normalization when allow_unicode is True, ensuring it correctly preserves and cleans unicode characters in input strings.
        """
        f = SlugField(allow_unicode=True)
        self.assertEqual(f.clean("a"), "a")
        self.assertEqual(f.clean("1"), "1")
        self.assertEqual(f.clean("a1"), "a1")
        self.assertEqual(f.clean("你好"), "你好")
        self.assertEqual(f.clean("  你-好  "), "你-好")
        self.assertEqual(f.clean("ıçğüş"), "ıçğüş")
        self.assertEqual(f.clean("foo-ıç-bar"), "foo-ıç-bar")

    def test_empty_value(self):
        """
        #: Tests the cleaning behavior of a SlugField when it contains an empty value.
        #: Verifies that the field returns an empty string by default, but can be configured
        #: to return a custom empty value, such as None, when the input is empty or None.
        """
        f = SlugField(required=False)
        self.assertEqual(f.clean(""), "")
        self.assertEqual(f.clean(None), "")
        f = SlugField(required=False, empty_value=None)
        self.assertIsNone(f.clean(""))
        self.assertIsNone(f.clean(None))
