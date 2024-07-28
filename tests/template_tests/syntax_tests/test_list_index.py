from django.test import SimpleTestCase

from ..utils import setup


class ListIndexTests(SimpleTestCase):
    @setup({"list-index01": "{{ var.1 }}"})
    def test_list_index01(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string(
            "list-index01", {"var": ["first item", "second item"]}
        )
        self.assertEqual(output, "second item")

    @setup({"list-index02": "{{ var.5 }}"})
    def test_list_index02(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string(
            "list-index02", {"var": ["first item", "second item"]}
        )
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "")

    @setup({"list-index03": "{{ var.1 }}"})
    def test_list_index03(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("list-index03", {"var": None})
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "")

    @setup({"list-index04": "{{ var.1 }}"})
    def test_list_index04(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("list-index04", {"var": {}})
        if self.engine.string_if_invalid:
            self.assertEqual(output, "INVALID")
        else:
            self.assertEqual(output, "")

    @setup({"list-index05": "{{ var.1 }}"})
    def test_list_index05(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("list-index05", {"var": {"1": "hello"}})
        self.assertEqual(output, "hello")

    @setup({"list-index06": "{{ var.1 }}"})
    def test_list_index06(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string("list-index06", {"var": {1: "hello"}})
        self.assertEqual(output, "hello")

    @setup({"list-index07": "{{ var.1 }}"})
    def test_list_index07(self):
        """
        This is a comment
        """
        output = self.engine.render_to_string(
            "list-index07", {"var": {"1": "hello", 1: "world"}}
        )
        self.assertEqual(output, "hello")
