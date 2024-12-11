"""
Tests for stuff in django.utils.datastructures.
"""

import collections.abc
import copy
import pickle

from django.test import SimpleTestCase
from django.utils.datastructures import (
    CaseInsensitiveMapping,
    DictWrapper,
    ImmutableList,
    MultiValueDict,
    MultiValueDictKeyError,
    OrderedSet,
)


class OrderedSetTests(SimpleTestCase):
    def test_init_with_iterable(self):
        """
        Tests the initialization of an OrderedSet instance with an iterable.

            Verifies that the OrderedSet correctly stores the elements from the iterable in the expected order.

            The test checks if the dictionary keys of the OrderedSet match the elements provided during initialization, ensuring that the set preserves the order and uniqueness of the elements.


        """
        s = OrderedSet([1, 2, 3])
        self.assertEqual(list(s.dict.keys()), [1, 2, 3])

    def test_remove(self):
        """
        Tests the removal of an element from an OrderedSet.

        This test case verifies that removing an element from an OrderedSet reduces its size by one and that the removed element is no longer present in the set.

        The test covers the following scenarios:
        - An element is successfully removed from the OrderedSet.
        - The size of the OrderedSet is updated correctly after removal.
        - The removed element is no longer contained in the OrderedSet.

        This test ensures the correct functionality of the remove method in the OrderedSet class, providing confidence in its ability to manage elements accurately.
        """
        s = OrderedSet()
        self.assertEqual(len(s), 0)
        s.add(1)
        s.add(2)
        s.remove(2)
        self.assertEqual(len(s), 1)
        self.assertNotIn(2, s)

    def test_discard(self):
        s = OrderedSet()
        self.assertEqual(len(s), 0)
        s.add(1)
        s.discard(2)
        self.assertEqual(len(s), 1)

    def test_reversed(self):
        s = reversed(OrderedSet([1, 2, 3]))
        self.assertIsInstance(s, collections.abc.Iterator)
        self.assertEqual(list(s), [3, 2, 1])

    def test_contains(self):
        s = OrderedSet()
        self.assertEqual(len(s), 0)
        s.add(1)
        self.assertIn(1, s)

    def test_bool(self):
        # Refs #23664
        """
        Tests the boolean representation of an OrderedSet instance.

        Verifies that an empty OrderedSet is considered False in a boolean context, 
        and that adding at least one element causes it to be considered True.
        """
        s = OrderedSet()
        self.assertFalse(s)
        s.add(1)
        self.assertTrue(s)

    def test_len(self):
        s = OrderedSet()
        self.assertEqual(len(s), 0)
        s.add(1)
        s.add(2)
        s.add(2)
        self.assertEqual(len(s), 2)

    def test_repr(self):
        """
        Tests the string representation of an OrderedSet instance. 

        Verifies that an empty OrderedSet is represented as 'OrderedSet()' and 
        a non-empty OrderedSet is represented with its elements in the order they were 
        first added, without duplicates, enclosed in 'OrderedSet([])'.
        """
        self.assertEqual(repr(OrderedSet()), "OrderedSet()")
        self.assertEqual(repr(OrderedSet([2, 3, 2, 1])), "OrderedSet([2, 3, 1])")


class MultiValueDictTests(SimpleTestCase):
    def test_repr(self):
        d = MultiValueDict({"key": "value"})
        self.assertEqual(repr(d), "<MultiValueDict: {'key': 'value'}>")

    def test_multivaluedict(self):
        d = MultiValueDict(
            {"name": ["Adrian", "Simon"], "position": ["Developer"], "empty": []}
        )
        self.assertEqual(d["name"], "Simon")
        self.assertEqual(d.get("name"), "Simon")
        self.assertEqual(d.getlist("name"), ["Adrian", "Simon"])
        self.assertEqual(
            list(d.items()),
            [("name", "Simon"), ("position", "Developer"), ("empty", [])],
        )
        self.assertEqual(
            list(d.lists()),
            [("name", ["Adrian", "Simon"]), ("position", ["Developer"]), ("empty", [])],
        )
        with self.assertRaisesMessage(MultiValueDictKeyError, "'lastname'"):
            d.__getitem__("lastname")
        self.assertIsNone(d.get("empty"))
        self.assertEqual(d.get("empty", "nonexistent"), "nonexistent")
        self.assertIsNone(d.get("lastname"))
        self.assertEqual(d.get("lastname", "nonexistent"), "nonexistent")
        self.assertEqual(d.getlist("lastname"), [])
        self.assertEqual(
            d.getlist("doesnotexist", ["Adrian", "Simon"]), ["Adrian", "Simon"]
        )
        d.setlist("lastname", ["Holovaty", "Willison"])
        self.assertEqual(d.getlist("lastname"), ["Holovaty", "Willison"])
        self.assertEqual(list(d.values()), ["Simon", "Developer", [], "Willison"])

        d.setlistdefault("lastname", ["Doe"])
        self.assertEqual(d.getlist("lastname"), ["Holovaty", "Willison"])
        d.setlistdefault("newkey", ["Doe"])
        self.assertEqual(d.getlist("newkey"), ["Doe"])

    def test_appendlist(self):
        """

        Tests the appendlist method of a MultiValueDict object.

        This method appends a new value to the list of values associated with a given key.
        If the key does not exist, a new key-value pair is created with the value as a list.
        The test verifies that multiple values can be appended to the same key and retrieved correctly.

        """
        d = MultiValueDict()
        d.appendlist("name", "Adrian")
        d.appendlist("name", "Simon")
        self.assertEqual(d.getlist("name"), ["Adrian", "Simon"])

    def test_copy(self):
        for copy_func in [copy.copy, lambda d: d.copy()]:
            with self.subTest(copy_func):
                d1 = MultiValueDict({"developers": ["Carl", "Fred"]})
                self.assertEqual(d1["developers"], "Fred")
                d2 = copy_func(d1)
                d2.update({"developers": "Groucho"})
                self.assertEqual(d2["developers"], "Groucho")
                self.assertEqual(d1["developers"], "Fred")

                d1 = MultiValueDict({"key": [[]]})
                self.assertEqual(d1["key"], [])
                d2 = copy_func(d1)
                d2["key"].append("Penguin")
                self.assertEqual(d1["key"], ["Penguin"])
                self.assertEqual(d2["key"], ["Penguin"])

    def test_deepcopy(self):
        d1 = MultiValueDict({"a": [[123]]})
        d2 = copy.copy(d1)
        d3 = copy.deepcopy(d1)
        self.assertIs(d1["a"], d2["a"])
        self.assertIsNot(d1["a"], d3["a"])

    def test_pickle(self):
        x = MultiValueDict({"a": ["1", "2"], "b": ["3"]})
        self.assertEqual(x, pickle.loads(pickle.dumps(x)))

    def test_dict_translation(self):
        """

        Test the translation of a MultiValueDict to a standard dictionary.

        Verifies that the resulting dictionary contains the same keys and values as the original MultiValueDict,
        and that empty MultiValueDicts are correctly translated to empty dictionaries.

        """
        mvd = MultiValueDict(
            {
                "devs": ["Bob", "Joe"],
                "pm": ["Rory"],
            }
        )
        d = mvd.dict()
        self.assertEqual(list(d), list(mvd))
        for key in mvd:
            self.assertEqual(d[key], mvd[key])

        self.assertEqual({}, MultiValueDict().dict())

    def test_getlist_doesnt_mutate(self):
        x = MultiValueDict({"a": ["1", "2"], "b": ["3"]})
        values = x.getlist("a")
        values += x.getlist("b")
        self.assertEqual(x.getlist("a"), ["1", "2"])

    def test_internal_getlist_does_mutate(self):
        x = MultiValueDict({"a": ["1", "2"], "b": ["3"]})
        values = x._getlist("a")
        values += x._getlist("b")
        self.assertEqual(x._getlist("a"), ["1", "2", "3"])

    def test_getlist_default(self):
        x = MultiValueDict({"a": [1]})
        MISSING = object()
        values = x.getlist("b", default=MISSING)
        self.assertIs(values, MISSING)

    def test_getlist_none_empty_values(self):
        x = MultiValueDict({"a": None, "b": []})
        self.assertIsNone(x.getlist("a"))
        self.assertEqual(x.getlist("b"), [])

    def test_setitem(self):
        x = MultiValueDict({"a": [1, 2]})
        x["a"] = 3
        self.assertEqual(list(x.lists()), [("a", [3])])

    def test_setdefault(self):
        x = MultiValueDict({"a": [1, 2]})
        a = x.setdefault("a", 3)
        b = x.setdefault("b", 3)
        self.assertEqual(a, 2)
        self.assertEqual(b, 3)
        self.assertEqual(list(x.lists()), [("a", [1, 2]), ("b", [3])])

    def test_update_too_many_args(self):
        x = MultiValueDict({"a": []})
        msg = "update expected at most 1 argument, got 2"
        with self.assertRaisesMessage(TypeError, msg):
            x.update(1, 2)

    def test_update_no_args(self):
        """

        Tests that the update method of a MultiValueDict instance does not modify its contents when called without any arguments.

        It verifies that the dict remains unchanged after the update operation, ensuring that the data is not inadvertently altered when no new data is provided.

        """
        x = MultiValueDict({"a": []})
        x.update()
        self.assertEqual(list(x.lists()), [("a", [])])

    def test_update_dict_arg(self):
        x = MultiValueDict({"a": [1], "b": [2], "c": [3]})
        x.update({"a": 4, "b": 5})
        self.assertEqual(list(x.lists()), [("a", [1, 4]), ("b", [2, 5]), ("c", [3])])

    def test_update_multivaluedict_arg(self):
        x = MultiValueDict({"a": [1], "b": [2], "c": [3]})
        x.update(MultiValueDict({"a": [4], "b": [5]}))
        self.assertEqual(list(x.lists()), [("a", [1, 4]), ("b", [2, 5]), ("c", [3])])

    def test_update_kwargs(self):
        """

        Tests the update functionality of a MultiValueDict with keyword arguments.

        This function verifies that when a MultiValueDict is updated with new values,
        the existing values are appended to instead of replaced. It checks this behavior
        for keys that already exist in the dictionary, while leaving unchanged any keys
        that do not receive new values. The test ensures that the resulting dictionary
        contains all the original and updated values, correctly combined.

        """
        x = MultiValueDict({"a": [1], "b": [2], "c": [3]})
        x.update(a=4, b=5)
        self.assertEqual(list(x.lists()), [("a", [1, 4]), ("b", [2, 5]), ("c", [3])])

    def test_update_with_empty_iterable(self):
        for value in ["", b"", (), [], set(), {}]:
            d = MultiValueDict()
            d.update(value)
            self.assertEqual(d, MultiValueDict())

    def test_update_with_iterable_of_pairs(self):
        for value in [(("a", 1),), [("a", 1)], {("a", 1)}]:
            d = MultiValueDict()
            d.update(value)
            self.assertEqual(d, MultiValueDict({"a": [1]}))

    def test_update_raises_correct_exceptions(self):
        # MultiValueDict.update() raises equivalent exceptions to
        # dict.update().
        # Non-iterable values raise TypeError.
        """

        Tests that the update method of MultiValueDict raises the correct exceptions when given invalid input.

        The function checks that a TypeError is raised when the update method is given a value that is not a mapping, such as None, a boolean, an integer, a float, a bytes object, or a tuple, list, or set.

        It also checks that a ValueError is raised when the update method is given a value that is a mapping but contains invalid key-value pairs, such as a string, a tuple, a list, or a set as keys.

        The test covers a variety of input types to ensure that the update method behaves correctly in different scenarios.

        """
        for value in [None, True, False, 123, 123.45]:
            with self.subTest(value), self.assertRaises(TypeError):
                MultiValueDict().update(value)
        # Iterables of objects that cannot be unpacked raise TypeError.
        for value in [b"123", b"abc", (1, 2, 3), [1, 2, 3], {1, 2, 3}]:
            with self.subTest(value), self.assertRaises(TypeError):
                MultiValueDict().update(value)
        # Iterables of unpackable objects with incorrect number of items raise
        # ValueError.
        for value in ["123", "abc", ("a", "b", "c"), ["a", "b", "c"], {"a", "b", "c"}]:
            with self.subTest(value), self.assertRaises(ValueError):
                MultiValueDict().update(value)


class ImmutableListTests(SimpleTestCase):
    def test_sort(self):
        d = ImmutableList(range(10))

        # AttributeError: ImmutableList object is immutable.
        with self.assertRaisesMessage(
            AttributeError, "ImmutableList object is immutable."
        ):
            d.sort()

        self.assertEqual(repr(d), "(0, 1, 2, 3, 4, 5, 6, 7, 8, 9)")

    def test_custom_warning(self):
        d = ImmutableList(range(10), warning="Object is immutable!")

        self.assertEqual(d[1], 1)

        # AttributeError: Object is immutable!
        with self.assertRaisesMessage(AttributeError, "Object is immutable!"):
            d.__setitem__(1, "test")


class DictWrapperTests(SimpleTestCase):
    def test_dictwrapper(self):
        """

        Tests the functionality of DictWrapper by verifying it correctly applies a transformation function to dictionary values.

        The test checks that the DictWrapper instance returns the original and modified dictionary values as expected, 
        using the transformation function to prefix the modified values with an asterisk. 

        It ensures that the DictWrapper can be used to access and manipulate dictionary values in a flexible and efficient manner.

        """
        def f(x):
            return "*%s" % x

        d = DictWrapper({"a": "a"}, f, "xx_")
        self.assertEqual(
            "Normal: %(a)s. Modified: %(xx_a)s" % d, "Normal: a. Modified: *a"
        )


class CaseInsensitiveMappingTests(SimpleTestCase):
    def setUp(self):
        self.dict1 = CaseInsensitiveMapping(
            {
                "Accept": "application/json",
                "content-type": "text/html",
            }
        )

    def test_create_with_invalid_values(self):
        msg = "dictionary update sequence element #1 has length 4; 2 is required"
        with self.assertRaisesMessage(ValueError, msg):
            CaseInsensitiveMapping([("Key1", "Val1"), "Key2"])

    def test_create_with_invalid_key(self):
        msg = "Element key 1 invalid, only strings are allowed"
        with self.assertRaisesMessage(ValueError, msg):
            CaseInsensitiveMapping([(1, "2")])

    def test_list(self):
        self.assertEqual(list(self.dict1), ["Accept", "content-type"])

    def test_dict(self):
        self.assertEqual(
            dict(self.dict1),
            {"Accept": "application/json", "content-type": "text/html"},
        )

    def test_repr(self):
        dict1 = CaseInsensitiveMapping({"Accept": "application/json"})
        dict2 = CaseInsensitiveMapping({"content-type": "text/html"})
        self.assertEqual(repr(dict1), repr({"Accept": "application/json"}))
        self.assertEqual(repr(dict2), repr({"content-type": "text/html"}))

    def test_str(self):
        dict1 = CaseInsensitiveMapping({"Accept": "application/json"})
        dict2 = CaseInsensitiveMapping({"content-type": "text/html"})
        self.assertEqual(str(dict1), str({"Accept": "application/json"}))
        self.assertEqual(str(dict2), str({"content-type": "text/html"}))

    def test_equal(self):
        self.assertEqual(
            self.dict1, {"Accept": "application/json", "content-type": "text/html"}
        )
        self.assertNotEqual(
            self.dict1, {"accept": "application/jso", "Content-Type": "text/html"}
        )
        self.assertNotEqual(self.dict1, "string")

    def test_items(self):
        other = {"Accept": "application/json", "content-type": "text/html"}
        self.assertEqual(sorted(self.dict1.items()), sorted(other.items()))

    def test_copy(self):
        """

        Tests that the copy of a dictionary is correctly created.

        Verifies that the copied dictionary is the same object as the original and
        contains the same key-value pairs, ensuring a correct shallow copy is made.

        """
        copy = self.dict1.copy()
        self.assertIs(copy, self.dict1)
        self.assertEqual(copy, self.dict1)

    def test_getitem(self):
        self.assertEqual(self.dict1["Accept"], "application/json")
        self.assertEqual(self.dict1["accept"], "application/json")
        self.assertEqual(self.dict1["aCCept"], "application/json")
        self.assertEqual(self.dict1["content-type"], "text/html")
        self.assertEqual(self.dict1["Content-Type"], "text/html")
        self.assertEqual(self.dict1["Content-type"], "text/html")

    def test_in(self):
        self.assertIn("Accept", self.dict1)
        self.assertIn("accept", self.dict1)
        self.assertIn("aCCept", self.dict1)
        self.assertIn("content-type", self.dict1)
        self.assertIn("Content-Type", self.dict1)

    def test_del(self):
        """
        Tests that attempting to delete an item from a CaseInsensitiveMapping object raises a TypeError.

        Verifies that the object does not support item deletion and that the item remains in the object after attempting deletion.

        Raises:
            TypeError: If an attempt is made to delete an item from the CaseInsensitiveMapping object.

        """
        self.assertIn("Accept", self.dict1)
        msg = "'CaseInsensitiveMapping' object does not support item deletion"
        with self.assertRaisesMessage(TypeError, msg):
            del self.dict1["Accept"]
        self.assertIn("Accept", self.dict1)

    def test_set(self):
        self.assertEqual(len(self.dict1), 2)
        msg = "'CaseInsensitiveMapping' object does not support item assignment"
        with self.assertRaisesMessage(TypeError, msg):
            self.dict1["New Key"] = 1
        self.assertEqual(len(self.dict1), 2)
