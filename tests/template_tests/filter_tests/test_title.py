from django.template.defaultfilters import title
from django.test import SimpleTestCase

from ..utils import setup


class TitleTests(SimpleTestCase):
    @setup({"title1": "{{ a|title }}"})
    def test_title1(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("title1", {"a": "JOE'S CRAB SHACK"})
        self.assertEqual(output, "Joe&#x27;s Crab Shack")

    @setup({"title2": "{{ a|title }}"})
    def test_title2(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("title2", {"a": "555 WEST 53RD STREET"})
        self.assertEqual(output, "555 West 53rd Street")


class FunctionTests(SimpleTestCase):
    def test_title(self):
        """
        This is a comment
        """
        self.assertEqual(title("a nice title, isn't it?"), "A Nice Title, Isn't It?")

    def test_unicode(self):
        """
        This is a comment
        """
        self.assertEqual(title("discoth\xe8que"), "Discoth\xe8que")

    def test_non_string_input(self):
        """
        This is a comment
        """
        self.assertEqual(title(123), "123")
