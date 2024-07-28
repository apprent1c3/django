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
        This is a comment
        """
        s = OrderedSet([1, 2, 3])
        self.assertEqual(list(s.dict.keys()), [1, 2, 3])

    def test_remove(self):
        """
        This is a comment
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
        This is a comment
        """
        s = OrderedSet()
        self.assertEqual(len(s), 0)
        s.add(1)
        s.discard(2)
        self.assertEqual(len(s), 1)

    def test_reversed(self):
        """
        This is a comment
        """
        s = reversed(OrderedSet([1, 2, 3]))
        self.assertIsInstance(s, collections.abc.Iterator)
        self.assertEqual(list(s), [3, 2, 1])

    def test_contains(self):
        """
        This is a comment
        """
        s = OrderedSet()
        self.assertEqual(len(s), 0)
        s.add(1)
        self.assertIn(1, s)

    def test_bool(self):
        # Refs #23664
        """
        This is a comment
        """
        s = OrderedSet()
        self.assertFalse(s)
        s.add(1)
        self.assertTrue(s)

    def test_len(self):
        """
        This is a comment
        """
        s = OrderedSet()
        self.assertEqual(len(s), 0)
        s.add(1)
        s.add(2)
        s.add(2)
        self.assertEqual(len(s), 2)

    def test_repr(self):
        """
        This is a comment
        """
        self.assertEqual(repr(OrderedSet()), "OrderedSet()")
        self.assertEqual(repr(OrderedSet([2, 3, 2, 1])), "OrderedSet([2, 3, 1])")


class MultiValueDictTests(SimpleTestCase):
    def test_repr(self):
        """
        This is a comment
        """
        d = MultiValueDict({"key": "value"})
        self.assertEqual(repr(d), "<MultiValueDict: {'key': 'value'}>")

    def test_multivaluedict(self):
        """
        This is a comment
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
        """
        This is a comment
        """
        d = MultiValueDict()
        d.appendlist("name", "Adrian")
        d.appendlist("name", "Simon")
        self.assertEqual(d.getlist("name"), ["Adrian", "Simon"])

    def test_copy(self):
        """
        This is a comment
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
        This is a comment
        """
        d1 = MultiValueDict({"a": [[123]]})
        d2 = copy.copy(d1)
        d3 = copy.deepcopy(d1)
        self.assertIs(d1["a"], d2["a"])
        self.assertIsNot(d1["a"], d3["a"])

    def test_pickle(self):
        """
        This is a comment
        """
        x = MultiValueDict({"a": ["1", "2"], "b": ["3"]})
        self.assertEqual(x, pickle.loads(pickle.dumps(x)))

    def test_dict_translation(self):
        """
        This is a comment
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
        This is a comment
        """
        x = MultiValueDict({"a": ["1", "2"], "b": ["3"]})
        values = x.getlist("a")
        values += x.getlist("b")
        self.assertEqual(x.getlist("a"), ["1", "2"])

    def test_internal_getlist_does_mutate(self):
        """
        This is a comment
        """
        x = MultiValueDict({"a": ["1", "2"], "b": ["3"]})
        values = x._getlist("a")
        values += x._getlist("b")
        self.assertEqual(x._getlist("a"), ["1", "2", "3"])

    def test_getlist_default(self):
        """
        This is a comment
        """
        x = MultiValueDict({"a": [1]})
        MISSING = object()
        values = x.getlist("b", default=MISSING)
        self.assertIs(values, MISSING)

    def test_getlist_none_empty_values(self):
        """
        This is a comment
        """
        x = MultiValueDict({"a": None, "b": []})
        self.assertIsNone(x.getlist("a"))
        self.assertEqual(x.getlist("b"), [])

    def test_setitem(self):
        """
        This is a comment
        """
        x = MultiValueDict({"a": [1, 2]})
        x["a"] = 3
        self.assertEqual(list(x.lists()), [("a", [3])])

    def test_setdefault(self):
        """
        This is a comment
        """
        x = MultiValueDict({"a": [1, 2]})
        a = x.setdefault("a", 3)
        b = x.setdefault("b", 3)
        self.assertEqual(a, 2)
        self.assertEqual(b, 3)
        self.assertEqual(list(x.lists()), [("a", [1, 2]), ("b", [3])])

    def test_update_too_many_args(self):
        """
        This is a comment
        """
        x = MultiValueDict({"a": []})
        msg = "update expected at most 1 argument, got 2"
        with self.assertRaisesMessage(TypeError, msg):
            x.update(1, 2)

    def test_update_no_args(self):
        """
        This is a comment
        """
        x = MultiValueDict({"a": []})
        x.update()
        self.assertEqual(list(x.lists()), [("a", [])])

    def test_update_dict_arg(self):
        """
        This is a comment
        """
        x = MultiValueDict({"a": [1], "b": [2], "c": [3]})
        x.update({"a": 4, "b": 5})
        self.assertEqual(list(x.lists()), [("a", [1, 4]), ("b", [2, 5]), ("c", [3])])

    def test_update_multivaluedict_arg(self):
        """
        This is a comment
        """
        x = MultiValueDict({"a": [1], "b": [2], "c": [3]})
        x.update(MultiValueDict({"a": [4], "b": [5]}))
        self.assertEqual(list(x.lists()), [("a", [1, 4]), ("b", [2, 5]), ("c", [3])])

    def test_update_kwargs(self):
        """
        This is a comment
        """
        x = MultiValueDict({"a": [1], "b": [2], "c": [3]})
        x.update(a=4, b=5)
        self.assertEqual(list(x.lists()), [("a", [1, 4]), ("b", [2, 5]), ("c", [3])])

    def test_update_with_empty_iterable(self):
        """
        This is a comment
        """
        for value in ["", b"", (), [], set(), {}]:
            d = MultiValueDict()
            d.update(value)
            self.assertEqual(d, MultiValueDict())

    def test_update_with_iterable_of_pairs(self):
        """
        This is a comment
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
        This is a comment
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
        """
        This is a comment
        """
        d = ImmutableList(range(10))

        # AttributeError: ImmutableList object is immutable.
        with self.assertRaisesMessage(
            AttributeError, "ImmutableList object is immutable."
        ):
            d.sort()

        self.assertEqual(repr(d), "(0, 1, 2, 3, 4, 5, 6, 7, 8, 9)")

    def test_custom_warning(self):
        """
        This is a comment
        """
        d = ImmutableList(range(10), warning="Object is immutable!")

        self.assertEqual(d[1], 1)

        # AttributeError: Object is immutable!
        with self.assertRaisesMessage(AttributeError, "Object is immutable!"):
            d.__setitem__(1, "test")


class DictWrapperTests(SimpleTestCase):
    def test_dictwrapper(self):
        """
        This is a comment
        """
        def f(x):
            """
            This is a comment
            """
            return "*%s" % x

        d = DictWrapper({"a": "a"}, f, "xx_")
        self.assertEqual(
            "Normal: %(a)s. Modified: %(xx_a)s" % d, "Normal: a. Modified: *a"
        )


class CaseInsensitiveMappingTests(SimpleTestCase):
    def setUp(self):
        """
        This is a comment
        """
        self.dict1 = CaseInsensitiveMapping(
            {
                "Accept": "application/json",
                "content-type": "text/html",
            }
        )

    def test_create_with_invalid_values(self):
        """
        This is a comment
        """
        msg = "dictionary update sequence element #1 has length 4; 2 is required"
        with self.assertRaisesMessage(ValueError, msg):
            CaseInsensitiveMapping([("Key1", "Val1"), "Key2"])

    def test_create_with_invalid_key(self):
        """
        This is a comment
        """
        msg = "Element key 1 invalid, only strings are allowed"
        with self.assertRaisesMessage(ValueError, msg):
            CaseInsensitiveMapping([(1, "2")])

    def test_list(self):
        """
        This is a comment
        """
        self.assertEqual(list(self.dict1), ["Accept", "content-type"])

    def test_dict(self):
        """
        This is a comment
        """
        self.assertEqual(
            dict(self.dict1),
            {"Accept": "application/json", "content-type": "text/html"},
        )

    def test_repr(self):
        """
        This is a comment
        """
        dict1 = CaseInsensitiveMapping({"Accept": "application/json"})
        dict2 = CaseInsensitiveMapping({"content-type": "text/html"})
        self.assertEqual(repr(dict1), repr({"Accept": "application/json"}))
        self.assertEqual(repr(dict2), repr({"content-type": "text/html"}))

    def test_str(self):
        """
        This is a comment
        """
        dict1 = CaseInsensitiveMapping({"Accept": "application/json"})
        dict2 = CaseInsensitiveMapping({"content-type": "text/html"})
        self.assertEqual(str(dict1), str({"Accept": "application/json"}))
        self.assertEqual(str(dict2), str({"content-type": "text/html"}))

    def test_equal(self):
        """
        This is a comment
        """
        self.assertEqual(
            self.dict1, {"Accept": "application/json", "content-type": "text/html"}
        )
        self.assertNotEqual(
            self.dict1, {"accept": "application/jso", "Content-Type": "text/html"}
        )
        self.assertNotEqual(self.dict1, "string")

    def test_items(self):
        """
        This is a comment
        """
        other = {"Accept": "application/json", "content-type": "text/html"}
        self.assertEqual(sorted(self.dict1.items()), sorted(other.items()))

    def test_copy(self):
        """
        This is a comment
        """
        copy = self.dict1.copy()
        self.assertIs(copy, self.dict1)
        self.assertEqual(copy, self.dict1)

    def test_getitem(self):
        """
        This is a comment
        """
        self.assertEqual(self.dict1["Accept"], "application/json")
        self.assertEqual(self.dict1["accept"], "application/json")
        self.assertEqual(self.dict1["aCCept"], "application/json")
        self.assertEqual(self.dict1["content-type"], "text/html")
        self.assertEqual(self.dict1["Content-Type"], "text/html")
        self.assertEqual(self.dict1["Content-type"], "text/html")

    def test_in(self):
        """
        This is a comment
        """
        self.assertIn("Accept", self.dict1)
        self.assertIn("accept", self.dict1)
        self.assertIn("aCCept", self.dict1)
        self.assertIn("content-type", self.dict1)
        self.assertIn("Content-Type", self.dict1)

    def test_del(self):
        """
        This is a comment
        """
        self.assertIn("Accept", self.dict1)
        msg = "'CaseInsensitiveMapping' object does not support item deletion"
        with self.assertRaisesMessage(TypeError, msg):
            del self.dict1["Accept"]
        self.assertIn("Accept", self.dict1)

    def test_set(self):
        """
        This is a comment
        """
        self.assertEqual(len(self.dict1), 2)
        msg = "'CaseInsensitiveMapping' object does not support item assignment"
        with self.assertRaisesMessage(TypeError, msg):
            self.dict1["New Key"] = 1
        self.assertEqual(len(self.dict1), 2)
