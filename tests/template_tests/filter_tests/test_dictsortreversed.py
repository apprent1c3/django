from django.template.defaultfilters import dictsortreversed
from django.test import SimpleTestCase


class FunctionTests(SimpleTestCase):
    def test_sort(self):
        """

        Tests the sorting of dictionaries in descending order based on a specified key.

        This function verifies that a list of dictionaries can be sorted in reverse order
        by a given key, in this case 'age'. It checks that the resulting sorted list
        contains the same dictionaries as the original list, but in the correct order.

        The function ensures that the dictionaries are sorted correctly regardless of the
        order of their keys, by comparing the sorted items of each dictionary.

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
        """

        Tests the sorting of a list of tuples in descending order based on the first element of each tuple.

        This function verifies that the dictsortreversed function correctly sorts a list of tuples
        where the first element of each tuple is used as the sorting key.

        """
        data = [("a", "42"), ("c", "string"), ("b", "foo")]
        expected = [("c", "string"), ("b", "foo"), ("a", "42")]
        self.assertEqual(dictsortreversed(data, 0), expected)

    def test_sort_list_of_tuple_like_dicts(self):
        """

        Tests the sorting of a list of dictionary-like objects in descending order based on a specified key.

        The function verifies that the dictsortreversed function correctly sorts a list of dictionaries, 
        where each dictionary represents a tuple-like object, by the values associated with a given key.
        In this case, the list is sorted in descending order based on the '0' key.

        """
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
