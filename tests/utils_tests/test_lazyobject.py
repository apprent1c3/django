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
        """
        Tests the setattr functionality of the lazy wrap object.

        This test case verifies that attributes can be successfully set on the wrapped object
        and their values retrieved correctly.

        It checks the assignment and retrieval of attributes 'foo' and 'bar' on the wrapped object,
        ensuring that their values are as expected after setting them to 'BAR' and 'baz' respectively.

        The test validates the behavior of the lazy wrap mechanism in handling attribute assignment,
        providing confidence that the wrapped object can be used as expected in various scenarios.
        """
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
        """
        Tests the comparison of lazy-wrapped objects, verifying that they can be correctly compared to their unwrapped values and other lazy-wrapped objects. The function checks for equality between objects with the same and different values, as well as equality between a lazy-wrapped object and its corresponding unwrapped value.
        """
        obj1 = self.lazy_wrap("foo")
        obj2 = self.lazy_wrap("bar")
        obj3 = self.lazy_wrap("foo")
        self.assertEqual(obj1, "foo")
        self.assertEqual(obj1, obj3)
        self.assertNotEqual(obj1, obj2)
        self.assertNotEqual(obj1, "bar")

    def test_lt(self):
        """
        Tests that the lazy wrapped object correctly implements the less-than operator.

        This test ensures that when comparing two lazy wrapped objects, the result reflects
        the expected ordering of their underlying values. Specifically, it verifies that
        an object with a smaller value is considered less than an object with a larger value.
        """
        obj1 = self.lazy_wrap(1)
        obj2 = self.lazy_wrap(2)
        self.assertLess(obj1, obj2)

    def test_gt(self):
        obj1 = self.lazy_wrap(1)
        obj2 = self.lazy_wrap(2)
        self.assertGreater(obj2, obj1)

    def test_bytes(self):
        """
        Tests the conversion of a lazy wrapped bytes object to bytes.

        Verifies that the bytes representation of the wrapped object matches the original bytes value. This ensures that the lazy wrapping mechanism does not alter the underlying data when converted to bytes.
        """
        obj = self.lazy_wrap(b"foo")
        self.assertEqual(bytes(obj), b"foo")

    def test_text(self):
        """

        Tests that the lazy wrapping of a text object returns a string representation as expected.

        The function verifies that when a text object is lazily wrapped, its string representation 
        matches the original text, ensuring correct functionality of the lazy wrapping mechanism.

        """
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
        """

        Tests the length of lazily wrapped sequences.

        Verifies that the length of various sequences (strings, lists, dictionaries)
        remains consistent after being wrapped by the lazy wrap functionality.

        Checks if the length of the wrapped objects matches the expected length of 3.

        """
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

        Tests the pickling and unpickling of a lazily wrapped object.

        This test creates a wrapped instance of Foo, sets an attribute on it, and then serializes
        it to a byte stream using pickle.dumps. The byte stream is then deserialized back into a
        Python object using pickle.loads. The test verifies that the resulting object is an
        instance of Foo, and that its attributes match those of the original object.

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
        Tests the creation of a copy of a lazily wrapped list object.

        Verifies that a copy of the wrapped list is a separate object from the original,
        is an instance of the list type, and contains the same elements as the original list.
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

        Tests that copying a lazily wrapped list does not trigger evaluation.

        Verifies that a copy of the wrapped object is a distinct entity, 
        and that neither the original nor the copied object evaluates the wrapped list until needed.

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

        Tests the copying behavior of the lazy wrapper class.

        Verifies that a copy of the lazy wrapped object is created successfully, 
        is a separate instance from the original, and preserves the class type and attributes.

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
        """
        Tests that a deep copy of a wrapped object results in a new instance of the original class.

        This test verifies that the deepcopy operation correctly creates a new, independent copy of the object,
        while maintaining its type and equality properties. It checks that the copied object is not the same
        instance as the original, but is equivalent in terms of its class and attributes, and is equal to a newly
        created instance of the same class.
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

        Tests the lazy wrapping of a class instance and its deepcopy behavior.

        Verifies that creating a deep copy of a lazily wrapped object results in a new, 
        separate instance, and that neither the original nor the copied object has its 
        wrapped attribute evaluated. The test ensures the correct behavior of lazy 
        wrapping in conjunction with the deepcopy operation.

        This test case checks the following conditions:

        * The original and copied objects are distinct instances.
        * Both objects have their wrapped attributes in an unevaluated state.

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

        This test case verifies that addition operations involving lazy wrapped objects
        produce the expected results. It checks both the addition of a lazy wrapped object
        with an integer and the addition of two lazy wrapped objects. The test ensures that
        the results are as expected and that the order of operands does not affect the outcome.

        The test cases cover the following scenarios:
        - Addition of a lazy wrapped object with an integer
        - Addition of two lazy wrapped objects, testing commutativity

        """
        obj1 = self.lazy_wrap(1)
        self.assertEqual(obj1 + 1, 2)
        obj2 = self.lazy_wrap(2)
        self.assertEqual(obj2 + obj1, 3)
        self.assertEqual(obj1 + obj2, 3)

    def test_radd(self):
        """
        Tests the functionality of the right-hand side addition operator (__radd__) for objects returned by lazy_wrap.

        This method verifies that when an integer is added to an object returned by lazy_wrap, the result is correctly calculated as if the integer was added to the underlying value wrapped by the object.

        The test case checks for the correct outcome of an addition operation, ensuring the lazy_wrap functionality does not interfere with standard arithmetic operations.

        Checks the condition: int + lazy_wrap(int) == expected_result, where expected_result is the sum of the integer and the wrapped integer value.
        """
        obj1 = self.lazy_wrap(1)
        self.assertEqual(1 + obj1, 2)

    def test_trace(self):
        # See ticket #19456
        """
        Tests the trace functionality by setting a temporary trace function.

        This function installs a custom trace function that forces the evaluation of a 
        lazy wrapper when a specific event occurs. The original trace function is saved 
        and restored after the test, ensuring that the tracing functionality is 
        temporarily modified only for the duration of this test. The purpose of this 
        test is to verify that the lazy wrapper is correctly evaluated when the trace 
        function is activated.
        """
        old_trace_func = sys.gettrace()
        try:

            def trace_func(frame, event, arg):
                """

                Tracing function that extends the functionality of the original tracing function.

                It captures the current frame, event, and argument, then retrieves the class of the
                current object ('self') from the local variables of the frame.

                If an old tracing function is defined, it calls this function with the same parameters,
                thus preserving the original tracing behavior and allowing for additional functionality. 

                :param frame: The current frame being traced.
                :param event: The event that triggered the tracing function (e.g., 'call', 'line', 'return', etc.).
                :param arg: An argument associated with the event (e.g., the return value for a 'return' event).

                """
                frame.f_locals["self"].__class__
                if old_trace_func is not None:
                    old_trace_func(frame, event, arg)

            sys.settrace(trace_func)
            self.lazy_wrap(None)
        finally:
            sys.settrace(old_trace_func)

    def test_none(self):
        """
        Tests the behavior of a lazy object when its function returns None.

        Verifies that the lazy object's string representation is 'None' after the
        underlying function has been evaluated, and that the function is only
        evaluated once, even if the string representation is accessed multiple times.
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
        Test the behavior of SimpleLazyObject when used with lists and sets.

        This function checks that the in operator, len function, and membership tests work as expected with SimpleLazyObject instances wrapping lists and sets. The test covers both positive and negative membership tests, ensuring that the lazy objects behave similarly to their non-lazy counterparts.
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
        """

        Supports pickling of the class instance by implementing the __reduce__ protocol.

        This method prepares the instance for serialization by setting the 'baz' attribute to a specific value, 
        and then delegates the actual reduction to the superclass implementation.

        """
        self.baz = "right"
        return super().__reduce__()

    def __eq__(self, other):
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
        """
        Initializes a new instance of the class by copying the attributes from the provided baz object.

         Parameters
         ----------
         baz : object
             The object from which to copy attributes.

         The baz object is stored internally for future reference, and the inherited class is initialized using the superclass constructor.
        """
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
