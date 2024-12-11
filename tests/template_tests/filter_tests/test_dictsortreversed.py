from django.template.defaultfilters import dictsortreversed
from django.test import SimpleTestCase


class FunctionTests(SimpleTestCase):
    def test_sort(self):
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
        """
        Tests the sorting of a list of tuples in reverse order based on the first element of each tuple.

        The function verifies that the dictsortreversed function correctly rearranges the tuples in descending order, 
        with the tuple containing the highest value in the specified position coming first.

        Args:
            None (test data is predefined within the function)

        Returns:
            None (the function asserts that the sorted result matches the expected output)

        Note:
            This test case covers a specific scenario, checking the sorting of tuples with mixed data types and 
            ensuring the correct order is maintained when sorting in reverse.

        """
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
