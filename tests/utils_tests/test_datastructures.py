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
        Tests that initializing an OrderedSet with an iterable preserves the original order of elements.

        The test verifies that when an OrderedSet is created from a list, the resulting set maintains the same order as the input list.

        """
        s = OrderedSet([1, 2, 3])
        self.assertEqual(list(s.dict.keys()), [1, 2, 3])

    def test_remove(self):
        """
        Tests the removal of an element from an OrderedSet.

        Verifies that the length of the set decreases by one and the removed element is no longer present in the set after removal.

        Ensures correct functionality of the remove method by checking the set's length and membership before and after removal of an element.
        """
        s = OrderedSet()
        self.assertEqual(len(s), 0)
        s.add(1)
        s.add(2)
        s.remove(2)
        self.assertEqual(len(s), 1)
        self.assertNotIn(2, s)

    def test_discard(self):
        """
        Tests the discard method of the OrderedSet class.

        Verifies that discarding an element not present in the set does not modify the set.
        The test starts with an empty OrderedSet, adds an element, and then attempts to discard
        a different element. The set's length is checked at the beginning and end to ensure
        it remains unchanged, confirming the discard operation has no effect when the element
        is not present in the set.
        """
        s = OrderedSet()
        self.assertEqual(len(s), 0)
        s.add(1)
        s.discard(2)
        self.assertEqual(len(s), 1)

    def test_reversed(self):
        """
        Tests if reversing an OrderedSet returns the elements in the correct order.

        Verifies that the reversed set is an iterator and that the elements are yielded in reverse order of their original insertion, i.e. from last to first added element.
        """
        s = reversed(OrderedSet([1, 2, 3]))
        self.assertIsInstance(s, collections.abc.Iterator)
        self.assertEqual(list(s), [3, 2, 1])

    def test_contains(self):
        """
        Tests if an element is correctly added and contained within an OrderedSet.

         Verifies the initial state of the OrderedSet is empty, then adds an element and 
         checks that it is present in the set, confirming the add operation and the 
         containment check functionality.

         :return: None

        """
        s = OrderedSet()
        self.assertEqual(len(s), 0)
        s.add(1)
        self.assertIn(1, s)

    def test_bool(self):
        # Refs #23664
        """
        Checks if an OrderedSet instance evaluates to True or False based on the presence of elements, where an empty set is considered False and a non-empty set is considered True.
        """
        s = OrderedSet()
        self.assertFalse(s)
        s.add(1)
        self.assertTrue(s)

    def test_len(self):
        """

        Tests the length of an OrderedSet.

        Verifies that the length of the OrderedSet behaves as expected when adding elements, 
        including handling duplicates. The test checks that the length is 0 for an empty set, 
        and that it correctly increments when unique elements are added, ignoring duplicate values.

        """
        s = OrderedSet()
        self.assertEqual(len(s), 0)
        s.add(1)
        s.add(2)
        s.add(2)
        self.assertEqual(len(s), 2)

    def test_repr(self):
        """
        Tests the representation of an OrderedSet object.

        Verifies that the repr function returns a string that accurately represents the OrderedSet,
        including the order of elements and handling of duplicates. The test checks both an empty
        OrderedSet and one populated with a list of elements, ensuring that the output string matches
        the expected format.
        """
        self.assertEqual(repr(OrderedSet()), "OrderedSet()")
        self.assertEqual(repr(OrderedSet([2, 3, 2, 1])), "OrderedSet([2, 3, 1])")


class MultiValueDictTests(SimpleTestCase):
    def test_repr(self):
        """
        Tests the repr method of the MultiValueDict class to ensure it returns a string representation with the correct format.

        The test checks if the string representation of a MultiValueDict instance matches the expected format, including the class name and the dictionary contents.

        :raises AssertionError: If the repr method does not return the expected string representation
        """
        d = MultiValueDict({"key": "value"})
        self.assertEqual(repr(d), "<MultiValueDict: {'key': 'value'}>")

    def test_multivaluedict(self):
        """

        Tests the functionality of the MultiValueDict class.

        The MultiValueDict class is a dictionary-like object that can store multiple values for each key.
        It provides methods to retrieve the first value, all values, or a default value for a given key.

        This test case covers the following scenarios:
        - Retrieval of single and multiple values for existing keys
        - Handling of non-existent keys, including raising exceptions and returning default values
        - Updating the dictionary with new values for existing and non-existing keys
        - Retrieval of dictionary items, including key-value pairs and lists of values

        """
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
        """
        Tests the copying functionality of MultiValueDict instances.

        This test case verifies that copying a MultiValueDict instance using either the
        copy.copy function or the dictionary's own copy method creates a new, independent
        instance. It checks that updating the copied instance does not affect the original
        instance, except in cases where the original instance contains mutable values, such
        as lists. In the case of mutable values, the test verifies that changes to the
        copied instance's values are reflected in the original instance, due to the shared
        reference to the mutable value.

        Two copying functions are tested: copy.copy and the dictionary's own copy method.
        The test covers scenarios with both immutable and mutable values in the MultiValueDict
        instances, ensuring that the copying behavior is correct in all cases.
        """
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
        """
        Tests the behavior of shallow and deep copying on a MultiValueDict instance, 
         focusing on the preservation of nested object references. 
         Verifies that a shallow copy preserves the original nested object references, 
         while a deep copy creates new, independent copies of the nested objects.
        """
        d1 = MultiValueDict({"a": [[123]]})
        d2 = copy.copy(d1)
        d3 = copy.deepcopy(d1)
        self.assertIs(d1["a"], d2["a"])
        self.assertIsNot(d1["a"], d3["a"])

    def test_pickle(self):
        """
        Test the serialization of a MultiValueDict instance using the pickle module.

        Verify that a MultiValueDict instance can be properly pickled and unpickled, 
        ensuring that its contents are preserved during the serialization process.

        This test covers the basic functionality of serializing and deserializing 
        a MultiValueDict, providing confidence in its compatibility with the pickle 
        module.
        """
        x = MultiValueDict({"a": ["1", "2"], "b": ["3"]})
        self.assertEqual(x, pickle.loads(pickle.dumps(x)))

    def test_dict_translation(self):
        """

        Tests the translation of a MultiValueDict to a standard dictionary.

        Verifies that the dictionary representation of a MultiValueDict contains the same keys and values as the original MultiValueDict.
        Also checks that an empty MultiValueDict correctly translates to an empty dictionary.

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
        """
        Tests that the getlist method does not mutate the internal state of the dictionary.

        Verifies that calling getlist on a key and appending its result to another list does not modify the original list associated with that key in the dictionary.

        Ensures that subsequent calls to getlist return the original list, unchanged by previous getlist operations or external modifications to the returned list.
        """
        x = MultiValueDict({"a": ["1", "2"], "b": ["3"]})
        values = x.getlist("a")
        values += x.getlist("b")
        self.assertEqual(x.getlist("a"), ["1", "2"])

    def test_internal_getlist_does_mutate(self):
        """
        Tests that the internal MultiValueDict _getlist method does not return a copy of the list but instead returns a mutable reference, allowing external modifications to affect the original MultiValueDict. The test verifies this behavior by modifying the returned list and checking that the changes are reflected in the original object.
        """
        x = MultiValueDict({"a": ["1", "2"], "b": ["3"]})
        values = x._getlist("a")
        values += x._getlist("b")
        self.assertEqual(x._getlist("a"), ["1", "2", "3"])

    def test_getlist_default(self):
        """

        Retrieves a list of values for a given key from a MultiValueDict, 
        returning a default value if the key is not present.

        When the key is missing and a default value is specified, 
        this method returns the default value, allowing the caller 
        to handle the missing key scenario in a predictable manner.

        The primary use case for this function is to safely retrieve 
        values from a MultiValueDict without raising exceptions 
        for missing keys, providing a more robust and fault-tolerant 
        way to access dictionary data.

        """
        x = MultiValueDict({"a": [1]})
        MISSING = object()
        values = x.getlist("b", default=MISSING)
        self.assertIs(values, MISSING)

    def test_getlist_none_empty_values(self):
        """
        Tests the getlist method of MultiValueDict for handling 'None' and empty list values.

        This test case verifies that when the getlist method is called on a key with a 'None' value, 
        it returns 'None', and when called on a key with an empty list value, it returns an empty list.
        """
        x = MultiValueDict({"a": None, "b": []})
        self.assertIsNone(x.getlist("a"))
        self.assertEqual(x.getlist("b"), [])

    def test_setitem(self):
        x = MultiValueDict({"a": [1, 2]})
        x["a"] = 3
        self.assertEqual(list(x.lists()), [("a", [3])])

    def test_setdefault(self):
        """
        Tests the functionality of the setdefault method in a MultiValueDict.

        This method returns the value of a given key if it exists in the dictionary.
        If the key does not exist, it inserts the key with a given default value and returns the default value.

        The test case checks the behavior of setdefault when the key is already present in the dictionary and when it is not.
        It verifies that the method correctly returns the existing or default value and updates the dictionary accordingly.
        """
        x = MultiValueDict({"a": [1, 2]})
        a = x.setdefault("a", 3)
        b = x.setdefault("b", 3)
        self.assertEqual(a, 2)
        self.assertEqual(b, 3)
        self.assertEqual(list(x.lists()), [("a", [1, 2]), ("b", [3])])

    def test_update_too_many_args(self):
        """

        Tests that updating a MultiValueDict with too many arguments raises a TypeError.

        Verifies that an update operation with more than one argument fails with a specific error message,
        ensuring that the dictionary enforces its expected argument count.

        """
        x = MultiValueDict({"a": []})
        msg = "update expected at most 1 argument, got 2"
        with self.assertRaisesMessage(TypeError, msg):
            x.update(1, 2)

    def test_update_no_args(self):
        """
        Tests that the update method of MultiValueDict works correctly when no arguments are provided.

            Verifies that the dictionary remains unchanged after an update with no new data.

            This test case ensures the integrity of the dictionary's existing data when the update method is called without any additional arguments.
        """
        x = MultiValueDict({"a": []})
        x.update()
        self.assertEqual(list(x.lists()), [("a", [])])

    def test_update_dict_arg(self):
        """
        Update a MultiValueDict instance with new key-value pairs, handling existing keys by appending the new values to the existing list of values.

        Args:
            None (method operates on the instance itself)

        Returns:
            None (modifies the instance in-place)

        Examples:
            An existing dictionary key will have its value list updated with the new value, while keys without existing values will be added with their corresponding value.
            If a key has an existing single value, it will be converted to a list containing both the original and new values.
        """
        x = MultiValueDict({"a": [1], "b": [2], "c": [3]})
        x.update({"a": 4, "b": 5})
        self.assertEqual(list(x.lists()), [("a", [1, 4]), ("b", [2, 5]), ("c", [3])])

    def test_update_multivaluedict_arg(self):
        """
        Tests whether the update method of a MultiValueDict correctly appends new values to existing keys and leaves unchanged keys that do not receive new values.
        """
        x = MultiValueDict({"a": [1], "b": [2], "c": [3]})
        x.update(MultiValueDict({"a": [4], "b": [5]}))
        self.assertEqual(list(x.lists()), [("a", [1, 4]), ("b", [2, 5]), ("c", [3])])

    def test_update_kwargs(self):
        """

        Tests that the update method correctly merges new values into the existing MultiValueDict.

        The update method appends new values to the existing list of values for each key.
        If a key does not exist in the MultiValueDict, it will be added with the provided value.

        Args will be merged into the dictionary with their corresponding values.

        """
        x = MultiValueDict({"a": [1], "b": [2], "c": [3]})
        x.update(a=4, b=5)
        self.assertEqual(list(x.lists()), [("a", [1, 4]), ("b", [2, 5]), ("c", [3])])

    def test_update_with_empty_iterable(self):
        """
        Tests the update method of MultiValueDict when given an empty iterable.

        Ensures that updating a MultiValueDict with various types of empty iterables, 
        such as strings, bytes, tuples, lists, sets, and dictionaries, does not modify 
        the dictionary and results in an empty MultiValueDict.

        Verifies that the update method correctly handles these edge cases and maintains 
        the expected behavior of the MultiValueDict class.
        """
        for value in ["", b"", (), [], set(), {}]:
            d = MultiValueDict()
            d.update(value)
            self.assertEqual(d, MultiValueDict())

    def test_update_with_iterable_of_pairs(self):
        """
        Tests the update method of MultiValueDict with various iterable collections of key-value pairs.

        This test case ensures that the update method correctly handles different types of iterables, including tuples, lists, and sets, containing key-value pairs. It verifies that the resulting MultiValueDict instance has the expected key-value structure after updating with the given iterable of pairs.

        The test expects the MultiValueDict to be updated with a single key-value pair ('a', 1) and asserts that the resulting dictionary contains the key 'a' with a value of [1].
        """
        for value in [(("a", 1),), [("a", 1)], {("a", 1)}]:
            d = MultiValueDict()
            d.update(value)
            self.assertEqual(d, MultiValueDict({"a": [1]}))

    def test_update_raises_correct_exceptions(self):
        # MultiValueDict.update() raises equivalent exceptions to
        # dict.update().
        # Non-iterable values raise TypeError.
        """
        Tests the update method of the MultiValueDict class to ensure it raises correct exceptions when invalid input types are provided.

        The test validates that a TypeError is raised when the update method is passed a value of an invalid type, including None, boolean, integer, float, bytes, tuple, list, or set. Additionally, it checks that a ValueError is raised when the update method is passed a string, tuple, list, or set that cannot be properly processed. 

        This test case verifies the robustness and error handling of the MultiValueDict class, ensuring it correctly handles a wide range of input types and raises informative exceptions when necessary.
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
        Tests the creation of a CaseInsensitiveMapping instance with invalid input values.

        The function verifies that attempting to initialize the mapping with a sequence containing an element of incorrect length raises a ValueError with a specific error message.
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
        """
        Tests the repr function for CaseInsensitiveMapping instances.

        Verifies that the string representation of a CaseInsensitiveMapping object 
        is equivalent to the string representation of a standard dictionary with the same key-value pairs. 

        This test ensures that the repr function provides a human-readable and 
        unambiguous representation of the object, which is useful for debugging purposes.
        """
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
        """
        Tests the equality of dictionary values while handling case sensitivity.

        This method checks if two dictionaries are equal, considering key case sensitivity.
        It also verifies that the dictionary is not equal to a string value, ensuring type safety.
        The test cases cover scenarios where dictionary keys have differing cases to validate 
        the comparison logic. 
        """
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
        Tests the copy functionality of a dictionary to ensure it behaves as expected.

         Verifies that the copied dictionary is the same object as the original, 
         and that the contents of the copied dictionary are equal to those of the original.
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
        """

        Verifies the presence of specific keys in a dictionary, regardless of their case.

        This function checks for the existence of 'Accept' and 'Content-Type' keys in varying
        case formats, ensuring that both lowercase and uppercase versions are accounted for.
        It is designed to test the robustness and case-insensitivity of dictionary key access.

        Raises:
            AssertionError: If any of the expected keys are not found in the dictionary.

        """
        self.assertIn("Accept", self.dict1)
        self.assertIn("accept", self.dict1)
        self.assertIn("aCCept", self.dict1)
        self.assertIn("content-type", self.dict1)
        self.assertIn("Content-Type", self.dict1)

    def test_del(self):
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
