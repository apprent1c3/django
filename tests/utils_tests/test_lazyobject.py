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

        Wrap an object to defer its initialization until it is accessed.

        """

        class AdHocLazyObject(LazyObject):
            def _setup(self):
                self._wrapped = wrapped_object

        return AdHocLazyObject()

    def test_getattribute(self):
        """
        Verifies that proxy methods are only available on wrapped objects after being explicitly set, ensuring lazy wrapping behavior works as expected.
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
        """
        Tests that lazy_wrap returns a falsey value when getattr is called on a wrapped object and the attribute does not exist, but is instead handled by __getattr__ that returns an empty list.
        """
        class Thing:
            def __getattr__(self, key):
                return []

        obj = self.lazy_wrap(Thing())
        self.assertEqual(obj.main, [])

    def test_setattr(self):
        """
        Tests the setattr functionality of the lazy wrap object, verifying that attributes can be set and retrieved correctly.
        """
        obj = self.lazy_wrap(Foo())
        obj.foo = "BAR"
        obj.bar = "baz"
        self.assertEqual(obj.foo, "BAR")
        self.assertEqual(obj.bar, "baz")

    def test_setattr2(self):
        # Same as test_setattr but in reversed order
        """
        Tests the setattr functionality of the lazy wrapper, ensuring it correctly sets attributes on the underlying object.
        """
        obj = self.lazy_wrap(Foo())
        obj.bar = "baz"
        obj.foo = "BAR"
        self.assertEqual(obj.foo, "BAR")
        self.assertEqual(obj.bar, "baz")

    def test_delattr(self):
        """
        Tests the deletion of an attribute via the delattr method on a lazily wrapped object, verifying that the attribute is properly removed and attempting to access it afterwards raises an AttributeError.
        """
        obj = self.lazy_wrap(Foo())
        obj.bar = "baz"
        self.assertEqual(obj.bar, "baz")
        del obj.bar
        with self.assertRaises(AttributeError):
            obj.bar

    def test_cmp(self):
        """

        Verifies the comparison behavior of lazily wrapped objects.
        Ensures equal objects have the same value and unequal objects are properly distinguished.

        """
        obj1 = self.lazy_wrap("foo")
        obj2 = self.lazy_wrap("bar")
        obj3 = self.lazy_wrap("foo")
        self.assertEqual(obj1, "foo")
        self.assertEqual(obj1, obj3)
        self.assertNotEqual(obj1, obj2)
        self.assertNotEqual(obj1, "bar")

    def test_lt(self):
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
        obj = self.lazy_wrap("foo")
        self.assertEqual(dir(obj), dir("foo"))

    def test_len(self):
        for seq in ["asd", [1, 2, 3], {"a": 1, "b": 2, "c": 3}]:
            obj = self.lazy_wrap(seq)
            self.assertEqual(len(obj), 3)

    def test_class(self):
        """
        Tests the lazy_wrap function to ensure it correctly returns an instance of the expected type, verifying both primitive types and class instances.
        """
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
        """
        Tests the 'in' operator functionality for a lazily wrapped object, 
        verifying it contains an element within various data structures, 
        including strings, lists, dictionaries, and sets, in both wrapped and unwrapped forms.
        """
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
        Tests the functionality of the __getitem__ method for lazy-wrapped lists and dictionaries.

        Verifies that the method correctly retrieves elements by index or key, handles slice notation, and raises appropriate exceptions for out-of-range indices and missing keys.
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
        """
        Tests the item assignment functionality for lazy-wrapped lists and dictionaries, ensuring that individual items and slices can be properly set and updated.
        """
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
        """
        Tests the deletion of items from lazily wrapped lists and dictionaries using the del statement. Verifies that items are correctly removed and that appropriate exceptions are raised when attempting to delete non-existent items.
        """
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
        Tests the lazy_wrap function's ability to correctly iterate over an object and return its values.
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
        """
        Tests the pickle serialization and deserialization of an object wrapped by `lazy_wrap`, ensuring its type and attributes are preserved after the round trip.
        """
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
        """
        Verifies that copying a lazily wrapped list results in a standalone list instance with the same elements, while maintaining object independence.
        """
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
        """
        lst = [1, 2, 3]

        obj = self.lazy_wrap(lst)
        obj2 = copy.copy(obj)

        self.assertIsNot(obj, obj2)
        self.assertIs(obj._wrapped, empty)
        self.assertIs(obj2._wrapped, empty)

    def test_copy_class(self):
        # Copying a class works and returns the correct objects.
        """
        Tests that copying a lazily wrapped object results in a new instance of the original class, with the same attributes and behavior.
        """
        foo = Foo()

        obj = self.lazy_wrap(foo)
        str(foo)  # forces evaluation
        obj2 = copy.copy(obj)

        self.assertIsNot(obj, obj2)
        self.assertIsInstance(obj2, Foo)
        self.assertEqual(obj2, Foo())

    def test_copy_class_no_evaluation(self):
        # Copying a class doesn't force evaluation.
        """

        Verify that copying a lazily wrapped object does not trigger evaluation.

        Checks that the copied object remains unevaluated, with both original and copied
        objects having their wrapped attribute set to an empty value.

        """
        foo = Foo()

        obj = self.lazy_wrap(foo)
        obj2 = copy.copy(obj)

        self.assertIsNot(obj, obj2)
        self.assertIs(obj._wrapped, empty)
        self.assertIs(obj2._wrapped, empty)

    def test_deepcopy_list(self):
        # Deep copying a list works and returns the correct objects.
        """
        Tests that deepcopying a lazily wrapped list creates a new list instance with the same contents.
        """
        lst = [1, 2, 3]

        obj = self.lazy_wrap(lst)
        len(lst)  # forces evaluation
        obj2 = copy.deepcopy(obj)

        self.assertIsNot(obj, obj2)
        self.assertIsInstance(obj2, list)
        self.assertEqual(obj2, [1, 2, 3])

    def test_deepcopy_list_no_evaluation(self):
        # Deep copying doesn't force evaluation.
        """
        Tests that deepcopying a lazily wrapped list results in a new, independent object that does not evaluate the original list.
        """
        lst = [1, 2, 3]

        obj = self.lazy_wrap(lst)
        obj2 = copy.deepcopy(obj)

        self.assertIsNot(obj, obj2)
        self.assertIs(obj._wrapped, empty)
        self.assertIs(obj2._wrapped, empty)

    def test_deepcopy_class(self):
        # Deep copying a class works and returns the correct objects.
        """
        Verifies that the lazy wrapper supports deep copying, ensuring the copied object is a new instance of the wrapped class with the same attributes.
        """
        foo = Foo()

        obj = self.lazy_wrap(foo)
        str(foo)  # forces evaluation
        obj2 = copy.deepcopy(obj)

        self.assertIsNot(obj, obj2)
        self.assertIsInstance(obj2, Foo)
        self.assertEqual(obj2, Foo())

    def test_deepcopy_class_no_evaluation(self):
        # Deep copying doesn't force evaluation.
        """
        Tests that the deepcopy operation on a lazily wrapped object does not evaluate the wrapped instance, and that both the original and copied objects reference an empty wrapped value.
        """
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
        """

        Tests the representation of a SimpleLazyObject instance.

        Verifies that the object's string representation is correctly formatted and that 
        its value is lazy-loaded as expected. Ensures the object behaves as expected 
        both before and after its value is accessed.

        """
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
        Tests the addition functionality of lazy-wrapped objects, verifying that they behave as expected when added to integers or other lazy-wrapped objects.
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
        """
        Tests the lazy wrapping functionality, temporarily overriding the system's trace function to ensure proper initialization of wrapped objects.
        """
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
        """
        Verifies that a SimpleLazyObject returns 'None' when its wrapped function returns None, 
        and that the wrapped function is only executed once, on the first access to the object.
        """
        i = [0]

        def f():
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

        Tests the functionality of a SimpleLazyObject when used as a dictionary.
        Checks dictionary access, modification, membership, length, and deletion.
        Verifies that a KeyError is raised when accessing a deleted key.

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
        """

        Tests the behavior of SimpleLazyObject instances wrapping lists and sets.

        Verifies that the 'in' operator and len() function work as expected with lazy lists and sets.

        """
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
        Checks if this object is equal to another object of the same class.

        Two objects are considered equal if they have the same attributes 'bar', 'baz', and 'quux' with the same values.
        Returns True if the objects are equal, False otherwise.
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
        Tests the pickling and unpickling of lazy objects using different pickle protocols to ensure their integrity is preserved.
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
        Tests the pickling of a model instance to ensure that it is properly serialized and deserialized, focusing on the behavior of lazy objects with different pickle protocols.
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
