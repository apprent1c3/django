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
        s = OrderedSet([1, 2, 3])
        self.assertEqual(list(s.dict.keys()), [1, 2, 3])

    def test_remove(self):
        s = OrderedSet()
        self.assertEqual(len(s), 0)
        s.add(1)
        s.add(2)
        s.remove(2)
        self.assertEqual(len(s), 1)
        self.assertNotIn(2, s)

    def test_discard(self):
        """
        Tests the discard method of an OrderedSet.

        Verifies that attempting to discard an element that is not present in the set does not modify the set's contents or size.

        This test case ensures the discard method behaves correctly when the element to be discarded is not a member of the set, maintaining the set's original state and size.
        """
        s = OrderedSet()
        self.assertEqual(len(s), 0)
        s.add(1)
        s.discard(2)
        self.assertEqual(len(s), 1)

    def test_reversed(self):
        """

        Tests that the OrderedSet object is properly reversed.

        The OrderedSet object is a collection that preserves the order in which elements were added,
        and this function verifies that when reversed, the elements are returned in reverse order.
        It checks that the reversed object is an iterator and that the elements are returned in the correct order.

        """
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
        s = OrderedSet()
        self.assertFalse(s)
        s.add(1)
        self.assertTrue(s)

    def test_len(self):
        """
        Test the length calculation of an OrderedSet instance.

        This method verifies that the length of an OrderedSet is correctly updated when elements are added, specifically in cases where duplicate elements are added. It ensures that the length reflects the number of unique elements in the set.
        """
        s = OrderedSet()
        self.assertEqual(len(s), 0)
        s.add(1)
        s.add(2)
        s.add(2)
        self.assertEqual(len(s), 2)

    def test_repr(self):
        self.assertEqual(repr(OrderedSet()), "OrderedSet()")
        self.assertEqual(repr(OrderedSet([2, 3, 2, 1])), "OrderedSet([2, 3, 1])")


class MultiValueDictTests(SimpleTestCase):
    def test_repr(self):
        """

        Tests the representation of a MultiValueDict instance.

        Verifies that the string representation of the MultiValueDict object is as expected,
        in the format <MultiValueDict: dictionary_contents>, where dictionary_contents is a 
        string representation of the dictionary contents.

        """
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
        """
        Tests that MultiValueDict instances can be successfully pickled and unpickled.

        This test case ensures that the internal state of a MultiValueDict is preserved
        when it is serialized and deserialized using the pickle module. It creates a
        sample MultiValueDict, pickles and then unpickles it, and checks that the
        original and unpickled dictionaries are equal.

        The test verifies that the MultiValueDict's structure and data are correctly
        restored after the pickling and unpickling process, which is essential for
        reliable data storage and retrieval in various applications.
        """
        x = MultiValueDict({"a": ["1", "2"], "b": ["3"]})
        self.assertEqual(x, pickle.loads(pickle.dumps(x)))

    def test_dict_translation(self):
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
        """
        Tests that the getlist method of MultiValueDict does not modify the original dictionary.

        Verifies that retrieving a list of values for a given key and then concatenating with another list of values does not alter the original data stored in the dictionary. Ensures data integrity and prevents unintended side effects when working with MultiValueDict instances.
        """
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
        """
        Tests the getlist method of a MultiValueDict object when the key is not present and a default value is provided.

        The test checks that if the key is missing from the dictionary and a default value is specified,
        the getlist method returns the default value instead of raising an error or returning an empty list.

        :raises AssertionError: if the returned value does not match the expected default value
        """
        x = MultiValueDict({"a": [1]})
        MISSING = object()
        values = x.getlist("b", default=MISSING)
        self.assertIs(values, MISSING)

    def test_getlist_none_empty_values(self):
        x = MultiValueDict({"a": None, "b": []})
        self.assertIsNone(x.getlist("a"))
        self.assertEqual(x.getlist("b"), [])

    def test_setitem(self):
        """

        Tests the behavior of setting an item in a MultiValueDict using the setitem method.

        When a key already exists in the dictionary, this method updates the key with a new single value, replacing any existing values.

        The resulting dictionary will contain the updated key with the new value, discarding any previous values associated with that key.

        """
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
        """

        Tests the update method of MultiValueDict when provided with too many arguments.

        This test case verifies that an error is raised when attempting to update a MultiValueDict with more than one argument, 
        ensuring that the method behaves as expected and enforces the correct number of arguments.

        The expected error message is also checked to ensure it accurately reflects the cause of the error.

        """
        x = MultiValueDict({"a": []})
        msg = "update expected at most 1 argument, got 2"
        with self.assertRaisesMessage(TypeError, msg):
            x.update(1, 2)

    def test_update_no_args(self):
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
        """

        Tests the implementation of a custom warning in ImmutableList.

        Verifies that attempting to modify an ImmutableList instance raises an AttributeError
        with a user-defined warning message, while allowing read-only access to its elements.

        """
        d = ImmutableList(range(10), warning="Object is immutable!")

        self.assertEqual(d[1], 1)

        # AttributeError: Object is immutable!
        with self.assertRaisesMessage(AttributeError, "Object is immutable!"):
            d.__setitem__(1, "test")


class DictWrapperTests(SimpleTestCase):
    def test_dictwrapper(self):
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
        """
        Tests that creating a CaseInsensitiveMapping instance with an invalid sequence of key-value pairs raises a ValueError. The error is triggered when the sequence contains an element that does not have exactly two values, such as a string instead of a tuple or list of length 2.
        """
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
        ..: Test that the CaseInsensitiveMapping object does not support item deletion using the del statement.

            This test checks that attempting to delete an item from a CaseInsensitiveMapping object
            raises a TypeError with the expected error message. It also verifies that the object
            remains unchanged after the failed deletion attempt, ensuring that the original key-value
            pair is still present.
        """
        self.assertIn("Accept", self.dict1)
        msg = "'CaseInsensitiveMapping' object does not support item deletion"
        with self.assertRaisesMessage(TypeError, msg):
            del self.dict1["Accept"]
        self.assertIn("Accept", self.dict1)

    def test_set(self):
        """
        Tests that the CaseInsensitiveMapping object does not support item assignment.

        Verifies that attempting to add a new key-value pair to the mapping raises a TypeError
        with a specific message, and that the mapping's length remains unchanged after the operation.
        """
        self.assertEqual(len(self.dict1), 2)
        msg = "'CaseInsensitiveMapping' object does not support item assignment"
        with self.assertRaisesMessage(TypeError, msg):
            self.dict1["New Key"] = 1
        self.assertEqual(len(self.dict1), 2)
