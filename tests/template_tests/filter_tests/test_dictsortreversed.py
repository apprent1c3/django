from django.template.defaultfilters import dictsortreversed
from django.test import SimpleTestCase


class FunctionTests(SimpleTestCase):
    def test_sort(self):
        """

        Tests the functionality of sorting a list of dictionaries in descending order based on a specified key.

        The test case verifies that the dictionaries are sorted correctly by the 'age' key and returns the expected list of sorted dictionaries.

        The sorting is done in descending order, meaning the dictionary with the highest value for the specified key comes first in the sorted list.

        The test includes dictionaries with varying key-value pairs to ensure the sorting function works correctly even when the dictionaries have different structures, as long as they contain the specified key.

        """
        sorted_dicts = dictsortreversed(
            [
                {"age": 23, "name": "Barbara-Ann"},
                {"age": 63, "name": "Ra Ra Rasputin"},
                {"name": "Jonny B Goode", "age": 18},
            ],
            "age",
        )

        self.assertEqual(
            [sorted(dict.items()) for dict in sorted_dicts],
            [
                [("age", 63), ("name", "Ra Ra Rasputin")],
                [("age", 23), ("name", "Barbara-Ann")],
                [("age", 18), ("name", "Jonny B Goode")],
            ],
        )

    def test_sort_list_of_tuples(self):
        data = [("a", "42"), ("c", "string"), ("b", "foo")]
        expected = [("c", "string"), ("b", "foo"), ("a", "42")]
        self.assertEqual(dictsortreversed(data, 0), expected)

    def test_sort_list_of_tuple_like_dicts(self):
        data = [
            {"0": "a", "1": "42"},
            {"0": "c", "1": "string"},
            {"0": "b", "1": "foo"},
        ]
        expected = [
            {"0": "c", "1": "string"},
            {"0": "b", "1": "foo"},
            {"0": "a", "1": "42"},
        ]
        self.assertEqual(dictsortreversed(data, "0"), expected)

    def test_invalid_values(self):
        """
        If dictsortreversed is passed something other than a list of
        dictionaries, fail silently.
        """
        self.assertEqual(dictsortreversed([1, 2, 3], "age"), "")
        self.assertEqual(dictsortreversed("Hello!", "age"), "")
        self.assertEqual(dictsortreversed({"a": 1}, "age"), "")
        self.assertEqual(dictsortreversed(1, "age"), "")

    def test_invalid_args(self):
        """Fail silently if invalid lookups are passed."""
        self.assertEqual(dictsortreversed([{}], "._private"), "")
        self.assertEqual(dictsortreversed([{"_private": "test"}], "_private"), "")
        self.assertEqual(
            dictsortreversed([{"nested": {"_private": "test"}}], "nested._private"), ""
        )
