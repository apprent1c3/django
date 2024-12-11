import copy
import pickle
import sys
import unittest
import warnings

from django.test import TestCase
from django.utils.functional import LazyObject, SimpleLazyObject, empty

from .models import Category, CategoryInfo


class Foo:
    """
    A simple class with just one attribute.
    """

    foo = "bar"

    def __eq__(self, other):
        return self.foo == other.foo


class LazyObjectTestCase(unittest.TestCase):
    def lazy_wrap(self, wrapped_object):
        """
        Wrap the given object into a LazyObject
        """

        class AdHocLazyObject(LazyObject):
            def _setup(self):
                self._wrapped = wrapped_object

        return AdHocLazyObject()

    def test_getattribute(self):
        """
        Proxy methods don't exist on wrapped objects unless they're set.
        """
        attrs = [
            "__getitem__",
            "__setitem__",
            "__delitem__",
            "__iter__",
            "__len__",
            "__contains__",
        ]
        foo = Foo()
        obj = self.lazy_wrap(foo)
        for attr in attrs:
            with self.subTest(attr):
                self.assertFalse(hasattr(obj, attr))
                setattr(foo, attr, attr)
                obj_with_attr = self.lazy_wrap(foo)
                self.assertTrue(hasattr(obj_with_attr, attr))
                self.assertEqual(getattr(obj_with_attr, attr), attr)

    def test_getattr(self):
        obj = self.lazy_wrap(Foo())
        self.assertEqual(obj.foo, "bar")

    def test_getattr_falsey(self):
        class Thing:
            def __getattr__(self, key):
                return []

        obj = self.lazy_wrap(Thing())
        self.assertEqual(obj.main, [])

    def test_setattr(self):
        obj = self.lazy_wrap(Foo())
        obj.foo = "BAR"
        obj.bar = "baz"
        self.assertEqual(obj.foo, "BAR")
        self.assertEqual(obj.bar, "baz")

    def test_setattr2(self):
        # Same as test_setattr but in reversed order
        obj = self.lazy_wrap(Foo())
        obj.bar = "baz"
        obj.foo = "BAR"
        self.assertEqual(obj.foo, "BAR")
        self.assertEqual(obj.bar, "baz")

    def test_delattr(self):
        obj = self.lazy_wrap(Foo())
        obj.bar = "baz"
        self.assertEqual(obj.bar, "baz")
        del obj.bar
        with self.assertRaises(AttributeError):
            obj.bar

    def test_cmp(self):
        obj1 = self.lazy_wrap("foo")
        obj2 = self.lazy_wrap("bar")
        obj3 = self.lazy_wrap("foo")
        self.assertEqual(obj1, "foo")
        self.assertEqual(obj1, obj3)
        self.assertNotEqual(obj1, obj2)
        self.assertNotEqual(obj1, "bar")

    def test_lt(self):
        """
        Tests the less-than operator functionality.

        This method verifies that the wrapped object comparison works correctly by
        checking if an object with a value of 1 is considered less than an object
        with a value of 2.

        The comparison is performed using the assertLess method, ensuring that the
        expected order is maintained.

        :raises AssertionError: If the comparison does not yield the expected result.
        """
        obj1 = self.lazy_wrap(1)
        obj2 = self.lazy_wrap(2)
        self.assertLess(obj1, obj2)

    def test_gt(self):
        obj1 = self.lazy_wrap(1)
        obj2 = self.lazy_wrap(2)
        self.assertGreater(obj2, obj1)

    def test_bytes(self):
        obj = self.lazy_wrap(b"foo")
        self.assertEqual(bytes(obj), b"foo")

    def test_text(self):
        obj = self.lazy_wrap("foo")
        self.assertEqual(str(obj), "foo")

    def test_bool(self):
        # Refs #21840
        for f in [False, 0, (), {}, [], None, set()]:
            self.assertFalse(self.lazy_wrap(f))
        for t in [True, 1, (1,), {1: 2}, [1], object(), {1}]:
            self.assertTrue(t)

    def test_dir(self):
        """

        Checks if the lazy wrapper correctly exposes the same attributes as the wrapped object.

        Verifies that the directory of the lazy wrapped object is identical to the directory of the original object.

        """
        obj = self.lazy_wrap("foo")
        self.assertEqual(dir(obj), dir("foo"))

    def test_len(self):
        for seq in ["asd", [1, 2, 3], {"a": 1, "b": 2, "c": 3}]:
            obj = self.lazy_wrap(seq)
            self.assertEqual(len(obj), 3)

    def test_class(self):
        self.assertIsInstance(self.lazy_wrap(42), int)

        class Bar(Foo):
            pass

        self.assertIsInstance(self.lazy_wrap(Bar()), Foo)

    def test_hash(self):
        obj = self.lazy_wrap("foo")
        d = {obj: "bar"}
        self.assertIn("foo", d)
        self.assertEqual(d["foo"], "bar")

    def test_contains(self):
        test_data = [
            ("c", "abcde"),
            (2, [1, 2, 3]),
            ("a", {"a": 1, "b": 2, "c": 3}),
            (2, {1, 2, 3}),
        ]
        for needle, haystack in test_data:
            self.assertIn(needle, self.lazy_wrap(haystack))

        # __contains__ doesn't work when the haystack is a string and the
        # needle a LazyObject.
        for needle_haystack in test_data[1:]:
            self.assertIn(self.lazy_wrap(needle), haystack)
            self.assertIn(self.lazy_wrap(needle), self.lazy_wrap(haystack))

    def test_getitem(self):
        """
        Tests the functionality of getting items from lazily wrapped objects.

        This test case checks that items can be retrieved from lists and dictionaries 
        using indexing and key-based access. It also verifies that appropriate errors 
        are raised when attempting to access items that are out of range or do not exist.

        Validations include:

        - Index-based access for lists
        - Key-based access for dictionaries
        - Slice notation for lists
        - Error handling for index out of range and missing keys
        """
        obj_list = self.lazy_wrap([1, 2, 3])
        obj_dict = self.lazy_wrap({"a": 1, "b": 2, "c": 3})

        self.assertEqual(obj_list[0], 1)
        self.assertEqual(obj_list[-1], 3)
        self.assertEqual(obj_list[1:2], [2])

        self.assertEqual(obj_dict["b"], 2)

        with self.assertRaises(IndexError):
            obj_list[3]

        with self.assertRaises(KeyError):
            obj_dict["f"]

    def test_setitem(self):
        obj_list = self.lazy_wrap([1, 2, 3])
        obj_dict = self.lazy_wrap({"a": 1, "b": 2, "c": 3})

        obj_list[0] = 100
        self.assertEqual(obj_list, [100, 2, 3])
        obj_list[1:2] = [200, 300, 400]
        self.assertEqual(obj_list, [100, 200, 300, 400, 3])

        obj_dict["a"] = 100
        obj_dict["d"] = 400
        self.assertEqual(obj_dict, {"a": 100, "b": 2, "c": 3, "d": 400})

    def test_delitem(self):
        obj_list = self.lazy_wrap([1, 2, 3])
        obj_dict = self.lazy_wrap({"a": 1, "b": 2, "c": 3})

        del obj_list[-1]
        del obj_dict["c"]
        self.assertEqual(obj_list, [1, 2])
        self.assertEqual(obj_dict, {"a": 1, "b": 2})

        with self.assertRaises(IndexError):
            del obj_list[3]

        with self.assertRaises(KeyError):
            del obj_dict["f"]

    def test_iter(self):
        # Tests whether an object's custom `__iter__` method is being
        # used when iterating over it.

        """
        Tests the lazy_wrap functionality with an iterable object.

        This test case verifies that the lazy_wrap method correctly handles an object that implements the iterator protocol.
        It checks if the wrapped object can be iterated over and its contents match the original data.

        The test utilizes a custom IterObject class, which allows for straightforward verification of the lazy_wrap behavior with an iterable object.
        It ensures that the resulting list from the lazy_wrap function is equal to the original list of values, confirming the correct functionality of the method.
        """
        class IterObject:
            def __init__(self, values):
                self.values = values

            def __iter__(self):
                return iter(self.values)

        original_list = ["test", "123"]
        self.assertEqual(list(self.lazy_wrap(IterObject(original_list))), original_list)

    def test_pickle(self):
        # See ticket #16563
        obj = self.lazy_wrap(Foo())
        obj.bar = "baz"
        pickled = pickle.dumps(obj)
        unpickled = pickle.loads(pickled)
        self.assertIsInstance(unpickled, Foo)
        self.assertEqual(unpickled, obj)
        self.assertEqual(unpickled.foo, obj.foo)
        self.assertEqual(unpickled.bar, obj.bar)

    # Test copying lazy objects wrapping both builtin types and user-defined
    # classes since a lot of the relevant code does __dict__ manipulation and
    # builtin types don't have __dict__.

    def test_copy_list(self):
        # Copying a list works and returns the correct objects.
        lst = [1, 2, 3]

        obj = self.lazy_wrap(lst)
        len(lst)  # forces evaluation
        obj2 = copy.copy(obj)

        self.assertIsNot(obj, obj2)
        self.assertIsInstance(obj2, list)
        self.assertEqual(obj2, [1, 2, 3])

    def test_copy_list_no_evaluation(self):
        # Copying a list doesn't force evaluation.
        """
        Tests that copying a lazily wrapped list does not evaluate the wrapped object.

        Verifies that the original and copied objects are distinct instances, 
        and that both objects' internal wrapped values remain unevaluated after copying.
        """
        lst = [1, 2, 3]

        obj = self.lazy_wrap(lst)
        obj2 = copy.copy(obj)

        self.assertIsNot(obj, obj2)
        self.assertIs(obj._wrapped, empty)
        self.assertIs(obj2._wrapped, empty)

    def test_copy_class(self):
        # Copying a class works and returns the correct objects.
        foo = Foo()

        obj = self.lazy_wrap(foo)
        str(foo)  # forces evaluation
        obj2 = copy.copy(obj)

        self.assertIsNot(obj, obj2)
        self.assertIsInstance(obj2, Foo)
        self.assertEqual(obj2, Foo())

    def test_copy_class_no_evaluation(self):
        # Copying a class doesn't force evaluation.
        foo = Foo()

        obj = self.lazy_wrap(foo)
        obj2 = copy.copy(obj)

        self.assertIsNot(obj, obj2)
        self.assertIs(obj._wrapped, empty)
        self.assertIs(obj2._wrapped, empty)

    def test_deepcopy_list(self):
        # Deep copying a list works and returns the correct objects.
        lst = [1, 2, 3]

        obj = self.lazy_wrap(lst)
        len(lst)  # forces evaluation
        obj2 = copy.deepcopy(obj)

        self.assertIsNot(obj, obj2)
        self.assertIsInstance(obj2, list)
        self.assertEqual(obj2, [1, 2, 3])

    def test_deepcopy_list_no_evaluation(self):
        # Deep copying doesn't force evaluation.
        lst = [1, 2, 3]

        obj = self.lazy_wrap(lst)
        obj2 = copy.deepcopy(obj)

        self.assertIsNot(obj, obj2)
        self.assertIs(obj._wrapped, empty)
        self.assertIs(obj2._wrapped, empty)

    def test_deepcopy_class(self):
        # Deep copying a class works and returns the correct objects.
        foo = Foo()

        obj = self.lazy_wrap(foo)
        str(foo)  # forces evaluation
        obj2 = copy.deepcopy(obj)

        self.assertIsNot(obj, obj2)
        self.assertIsInstance(obj2, Foo)
        self.assertEqual(obj2, Foo())

    def test_deepcopy_class_no_evaluation(self):
        # Deep copying doesn't force evaluation.
        foo = Foo()

        obj = self.lazy_wrap(foo)
        obj2 = copy.deepcopy(obj)

        self.assertIsNot(obj, obj2)
        self.assertIs(obj._wrapped, empty)
        self.assertIs(obj2._wrapped, empty)


class SimpleLazyObjectTestCase(LazyObjectTestCase):
    # By inheriting from LazyObjectTestCase and redefining the lazy_wrap()
    # method which all testcases use, we get to make sure all behaviors
    # tested in the parent testcase also apply to SimpleLazyObject.
    def lazy_wrap(self, wrapped_object):
        return SimpleLazyObject(lambda: wrapped_object)

    def test_repr(self):
        # First, for an unevaluated SimpleLazyObject
        obj = self.lazy_wrap(42)
        # __repr__ contains __repr__ of setup function and does not evaluate
        # the SimpleLazyObject
        self.assertRegex(repr(obj), "^<SimpleLazyObject:")
        self.assertIs(obj._wrapped, empty)  # make sure evaluation hasn't been triggered

        self.assertEqual(obj, 42)  # evaluate the lazy object
        self.assertIsInstance(obj._wrapped, int)
        self.assertEqual(repr(obj), "<SimpleLazyObject: 42>")

    def test_add(self):
        """

        Tests the addition operation on lazy wrapped objects.

        This test ensures that lazy wrapped objects can be added to integers and other lazy wrapped objects,
        resulting in the correct sum. It verifies the commutative property of addition by checking that the order
        of the operands does not affect the result.

        The test covers the following scenarios:
        - Adding an integer to a lazy wrapped object
        - Adding two lazy wrapped objects

        """
        obj1 = self.lazy_wrap(1)
        self.assertEqual(obj1 + 1, 2)
        obj2 = self.lazy_wrap(2)
        self.assertEqual(obj2 + obj1, 3)
        self.assertEqual(obj1 + obj2, 3)

    def test_radd(self):
        obj1 = self.lazy_wrap(1)
        self.assertEqual(1 + obj1, 2)

    def test_trace(self):
        # See ticket #19456
        old_trace_func = sys.gettrace()
        try:

            def trace_func(frame, event, arg):
                frame.f_locals["self"].__class__
                if old_trace_func is not None:
                    old_trace_func(frame, event, arg)

            sys.settrace(trace_func)
            self.lazy_wrap(None)
        finally:
            sys.settrace(old_trace_func)

    def test_none(self):
        i = [0]

        def f():
            """
            Increments the first element of a predefined list `i` by 1 and returns None. Note that this function relies on an externally defined list `i` and modifies it in-place. This modification is a side-effect of the function, as the return value is always None.
            """
            i[0] += 1
            return None

        x = SimpleLazyObject(f)
        self.assertEqual(str(x), "None")
        self.assertEqual(i, [1])
        self.assertEqual(str(x), "None")
        self.assertEqual(i, [1])

    def test_dict(self):
        # See ticket #18447
        """
        Tests the functionality of a SimpleLazyObject instance that wraps a dictionary.

        This test case verifies that the lazy object behaves like a regular dictionary, 
        including retrieving values by key, assigning new values, checking key presence, 
        getting the number of items, and deleting items. It also checks that attempting 
        to access a non-existent key after deletion raises a KeyError, as expected from 
        standard dictionary behavior.
        """
        lazydict = SimpleLazyObject(lambda: {"one": 1})
        self.assertEqual(lazydict["one"], 1)
        lazydict["one"] = -1
        self.assertEqual(lazydict["one"], -1)
        self.assertIn("one", lazydict)
        self.assertNotIn("two", lazydict)
        self.assertEqual(len(lazydict), 1)
        del lazydict["one"]
        with self.assertRaises(KeyError):
            lazydict["one"]

    def test_list_set(self):
        lazy_list = SimpleLazyObject(lambda: [1, 2, 3, 4, 5])
        lazy_set = SimpleLazyObject(lambda: {1, 2, 3, 4})
        self.assertIn(1, lazy_list)
        self.assertIn(1, lazy_set)
        self.assertNotIn(6, lazy_list)
        self.assertNotIn(6, lazy_set)
        self.assertEqual(len(lazy_list), 5)
        self.assertEqual(len(lazy_set), 4)


class BaseBaz:
    """
    A base class with a funky __reduce__ method, meant to simulate the
    __reduce__ method of Model, which sets self._django_version.
    """

    def __init__(self):
        self.baz = "wrong"

    def __reduce__(self):
        self.baz = "right"
        return super().__reduce__()

    def __eq__(self, other):
        """
        Checks if the current object is equal to another object.

        This method compares the current object with the provided object to determine if they are equal.
        It first checks if both objects belong to the same class. If they do not, it immediately returns False.
        Then, it checks if both objects have the same set of attributes ('bar', 'baz', 'quux') and if the values of these attributes are equal.
        If all conditions are met, it returns True, indicating that the objects are equal. Otherwise, it returns False.
        """
        if self.__class__ != other.__class__:
            return False
        for attr in ["bar", "baz", "quux"]:
            if hasattr(self, attr) != hasattr(other, attr):
                return False
            elif getattr(self, attr, None) != getattr(other, attr, None):
                return False
        return True


class Baz(BaseBaz):
    """
    A class that inherits from BaseBaz and has its own __reduce_ex__ method.
    """

    def __init__(self, bar):
        self.bar = bar
        super().__init__()

    def __reduce_ex__(self, proto):
        self.quux = "quux"
        return super().__reduce_ex__(proto)


class BazProxy(Baz):
    """
    A class that acts as a proxy for Baz. It does some scary mucking about with
    dicts, which simulates some crazy things that people might do with
    e.g. proxy models.
    """

    def __init__(self, baz):
        self.__dict__ = baz.__dict__
        self._baz = baz
        # Grandparent super
        super(BaseBaz, self).__init__()


class SimpleLazyObjectPickleTestCase(TestCase):
    """
    Regression test for pickling a SimpleLazyObject wrapping a model (#25389).
    Also covers other classes with a custom __reduce__ method.
    """

    def test_pickle_with_reduce(self):
        """
        Test in a fairly synthetic setting.
        """
        # Test every pickle protocol available
        for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
            lazy_objs = [
                SimpleLazyObject(lambda: BaseBaz()),
                SimpleLazyObject(lambda: Baz(1)),
                SimpleLazyObject(lambda: BazProxy(Baz(2))),
            ]
            for obj in lazy_objs:
                pickled = pickle.dumps(obj, protocol)
                unpickled = pickle.loads(pickled)
                self.assertEqual(unpickled, obj)
                self.assertEqual(unpickled.baz, "right")

    def test_pickle_model(self):
        """
        Test on an actual model, based on the report in #25426.
        """
        category = Category.objects.create(name="thing1")
        CategoryInfo.objects.create(category=category)
        # Test every pickle protocol available
        for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
            lazy_category = SimpleLazyObject(lambda: category)
            # Test both if we accessed a field on the model and if we didn't.
            lazy_category.categoryinfo
            lazy_category_2 = SimpleLazyObject(lambda: category)
            with warnings.catch_warnings(record=True) as recorded:
                self.assertEqual(
                    pickle.loads(pickle.dumps(lazy_category, protocol)), category
                )
                self.assertEqual(
                    pickle.loads(pickle.dumps(lazy_category_2, protocol)), category
                )
                # Assert that there were no warnings.
                self.assertEqual(len(recorded), 0)
