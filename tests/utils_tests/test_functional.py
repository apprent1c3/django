from django.test import SimpleTestCase
from django.utils.functional import cached_property, classproperty, lazy
from django.utils.version import PY312


class FunctionalTests(SimpleTestCase):
    def test_lazy(self):
        t = lazy(lambda: tuple(range(3)), list, tuple)
        for a, b in zip(t(), range(3)):
            self.assertEqual(a, b)

    def test_lazy_base_class(self):
        """
        Verifies that the lazy function can discover and include methods from base classes in the proxy object, ensuring correct inheritance and method accessibility.
        """

        class Base:
            def base_method(self):
                pass

        class Klazz(Base):
            pass

        t = lazy(lambda: Klazz(), Klazz)()
        self.assertIn("base_method", dir(t))

    def test_lazy_base_class_override(self):
        """
        Tests that the lazy function finds the correct overridden method implementation in a subclass, ensuring it calls the subclass method instead of the base class method.
        """

        class Base:
            def method(self):
                return "Base"

        class Klazz(Base):
            def method(self):
                return "Klazz"

        t = lazy(lambda: Klazz(), Base)()
        self.assertEqual(t.method(), "Klazz")

    def test_lazy_object_to_string(self):
        """
        Verifies that a lazy object correctly delegates string and bytes conversion to its underlying object.
        """
        class Klazz:
            def __str__(self):
                return "Î am ā Ǩlâzz."

            def __bytes__(self):
                return b"\xc3\x8e am \xc4\x81 binary \xc7\xa8l\xc3\xa2zz."

        t = lazy(lambda: Klazz(), Klazz)()
        self.assertEqual(str(t), "Î am ā Ǩlâzz.")
        self.assertEqual(bytes(t), b"\xc3\x8e am \xc4\x81 binary \xc7\xa8l\xc3\xa2zz.")

    def assertCachedPropertyWorks(self, attr, Class):
        """

        Verifies the functionality of a cached property on a given class.

        Checks that the cached property is correctly implemented, 
        inherits correctly to a subclass, and behaves as expected 
        across different instances of the class and its subclass.

        """
        with self.subTest(attr=attr):

            def get(source):
                return getattr(source, attr)

            obj = Class()

            class SubClass(Class):
                pass

            subobj = SubClass()
            # Docstring is preserved.
            self.assertEqual(get(Class).__doc__, "Here is the docstring...")
            self.assertEqual(get(SubClass).__doc__, "Here is the docstring...")
            # It's cached.
            self.assertEqual(get(obj), get(obj))
            self.assertEqual(get(subobj), get(subobj))
            # The correct value is returned.
            self.assertEqual(get(obj)[0], 1)
            self.assertEqual(get(subobj)[0], 1)
            # State isn't shared between instances.
            obj2 = Class()
            subobj2 = SubClass()
            self.assertNotEqual(get(obj), get(obj2))
            self.assertNotEqual(get(subobj), get(subobj2))
            # It behaves like a property when there's no instance.
            self.assertIsInstance(get(Class), cached_property)
            self.assertIsInstance(get(SubClass), cached_property)
            # 'other_value' doesn't become a property.
            self.assertTrue(callable(obj.other_value))
            self.assertTrue(callable(subobj.other_value))

    def test_cached_property(self):
        """
        Test the functionality of the cached_property decorator, ensuring it correctly caches its value and behaves like a property for different attribute names, including those that start with double underscores.
        """

        class Class:
            @cached_property
            def value(self):
                """Here is the docstring..."""
                return 1, object()

            @cached_property
            def __foo__(self):
                """Here is the docstring..."""
                return 1, object()

            def other_value(self):
                """Here is the docstring..."""
                return 1, object()

            other = cached_property(other_value)

        attrs = ["value", "other", "__foo__"]
        for attr in attrs:
            self.assertCachedPropertyWorks(attr, Class)

    def test_cached_property_auto_name(self):
        """
        Verifies that cached_property correctly caches its value and behaves like a property, regardless of whether the name is mangled or explicitly set.
        """

        class Class:
            @cached_property
            def __value(self):
                """Here is the docstring..."""
                return 1, object()

            def other_value(self):
                """Here is the docstring..."""
                return 1, object()

            other = cached_property(other_value)

        attrs = ["_Class__value", "other"]
        for attr in attrs:
            self.assertCachedPropertyWorks(attr, Class)

    def test_cached_property_reuse_different_names(self):
        """
        Tests that attempting to reuse a cached_property under different names raises an error, as this would prevent caching from working correctly.
        """
        type_msg = (
            "Cannot assign the same cached_property to two different names ('a' and "
            "'b')."
        )
        if PY312:
            error_type = TypeError
            msg = type_msg
        else:
            error_type = RuntimeError
            msg = "Error calling __set_name__"

        with self.assertRaisesMessage(error_type, msg) as ctx:

            class ReusedCachedProperty:
                @cached_property
                def a(self):
                    pass

                b = a

        if not PY312:
            self.assertEqual(str(ctx.exception.__context__), str(TypeError(type_msg)))

    def test_cached_property_reuse_same_name(self):
        """
        Tests that a cached property can be reused under the same name across different classes without conflicts, ensuring the correct increment of the property's value.
        """
        counter = 0

        @cached_property
        def _cp(_self):
            nonlocal counter
            counter += 1
            return counter

        class A:
            cp = _cp

        class B:
            cp = _cp

        a = A()
        b = B()
        self.assertEqual(a.cp, 1)
        self.assertEqual(b.cp, 2)
        self.assertEqual(a.cp, 1)

    def test_cached_property_set_name_not_called(self):
        """
        Checks if an attempt to access a cached property instance on a class without calling its __set_name__() method raises a TypeError.
        """
        cp = cached_property(lambda s: None)

        class Foo:
            pass

        Foo.cp = cp
        msg = (
            "Cannot use cached_property instance without calling __set_name__() on it."
        )
        with self.assertRaisesMessage(TypeError, msg):
            Foo().cp

    def test_lazy_add_int(self):
        """
        Tests the addition of integers with lazy values, ensuring that lazy values can be correctly added to integers and to other lazy values, both when the lazy value is on the left and right side of the addition operation, and when both operands are lazy.
        """
        lazy_4 = lazy(lambda: 4, int)
        lazy_5 = lazy(lambda: 5, int)
        self.assertEqual(4 + lazy_5(), 9)
        self.assertEqual(lazy_4() + 5, 9)
        self.assertEqual(lazy_4() + lazy_5(), 9)

    def test_lazy_add_list(self):
        """
        Tests the addition of lazy lists, verifying that they can be concatenated with both eager and lazy lists, and that the results are as expected.
        """
        lazy_4 = lazy(lambda: [4], list)
        lazy_5 = lazy(lambda: [5], list)
        self.assertEqual([4] + lazy_5(), [4, 5])
        self.assertEqual(lazy_4() + [5], [4, 5])
        self.assertEqual(lazy_4() + lazy_5(), [4, 5])

    def test_lazy_add_str(self):
        """
        Checks if the lazy string wrapper correctly implements string concatenation when involved in addition operations with other strings or lazy strings.
        """
        lazy_a = lazy(lambda: "a", str)
        lazy_b = lazy(lambda: "b", str)
        self.assertEqual("a" + lazy_b(), "ab")
        self.assertEqual(lazy_a() + "b", "ab")
        self.assertEqual(lazy_a() + lazy_b(), "ab")

    def test_lazy_mod_int(self):
        """
        Tests the functionality of lazy objects in modulo operations with integers, verifying expected behavior when the lazy object is on either side of the operator.
        """
        lazy_4 = lazy(lambda: 4, int)
        lazy_5 = lazy(lambda: 5, int)
        self.assertEqual(4 % lazy_5(), 4)
        self.assertEqual(lazy_4() % 5, 4)
        self.assertEqual(lazy_4() % lazy_5(), 4)

    def test_lazy_mod_str(self):
        """
        Tests string formatting operations with lazy objects as operands, verifying correct behavior and substitution of lazy values when used as both format strings and format specifiers
        """
        lazy_a = lazy(lambda: "a%s", str)
        lazy_b = lazy(lambda: "b", str)
        self.assertEqual("a%s" % lazy_b(), "ab")
        self.assertEqual(lazy_a() % "b", "ab")
        self.assertEqual(lazy_a() % lazy_b(), "ab")

    def test_lazy_mul_int(self):
        """
        Tests the multiplication operation with lazy integers to ensure correct functionality when combined with regular integers.
        """
        lazy_4 = lazy(lambda: 4, int)
        lazy_5 = lazy(lambda: 5, int)
        self.assertEqual(4 * lazy_5(), 20)
        self.assertEqual(lazy_4() * 5, 20)
        self.assertEqual(lazy_4() * lazy_5(), 20)

    def test_lazy_mul_list(self):
        """
        Tests the implementation of multiplication with lists in the lazy evaluation system, ensuring both list multiplication and scalar multiplication behave as expected.
        """
        lazy_4 = lazy(lambda: [4], list)
        lazy_5 = lazy(lambda: 5, int)
        self.assertEqual([4] * lazy_5(), [4, 4, 4, 4, 4])
        self.assertEqual(lazy_4() * 5, [4, 4, 4, 4, 4])
        self.assertEqual(lazy_4() * lazy_5(), [4, 4, 4, 4, 4])

    def test_lazy_mul_str(self):
        """
        Tests the multiplication of lazy strings with integers and other lazy values, ensuring correct results when Lazy instances are used as operands.
        """
        lazy_a = lazy(lambda: "a", str)
        lazy_5 = lazy(lambda: 5, int)
        self.assertEqual("a" * lazy_5(), "aaaaa")
        self.assertEqual(lazy_a() * 5, "aaaaa")
        self.assertEqual(lazy_a() * lazy_5(), "aaaaa")

    def test_lazy_format(self):
        """
        Tests the lazy format functionality by creating a custom string class 
        that adds quotes around the formatted value, and demonstrates that the 
        lazy formatting is correctly applied when the value is retrieved and 
        formatted at different stages.
        """
        class QuotedString(str):
            def __format__(self, format_spec):
                value = super().__format__(format_spec)
                return f"“{value}”"

        lazy_f = lazy(lambda: QuotedString("Hello!"), QuotedString)
        self.assertEqual(format(lazy_f(), ""), "“Hello!”")
        f = lazy_f()
        self.assertEqual(f"I said, {f}", "I said, “Hello!”")

    def test_lazy_equality(self):
        """

        Tests the correctness of equality operators for Promises.

        Verifies that the == and!= operators work as expected when comparing the values 
        of Promises, even when they are lazily evaluated.

        """
        lazy_a = lazy(lambda: 4, int)
        lazy_b = lazy(lambda: 4, int)
        lazy_c = lazy(lambda: 5, int)

        self.assertEqual(lazy_a(), lazy_b())
        self.assertNotEqual(lazy_b(), lazy_c())

    def test_lazy_repr_text(self):
        original_object = "Lazy translation text"
        lazy_obj = lazy(lambda: original_object, str)
        self.assertEqual(repr(original_object), repr(lazy_obj()))

    def test_lazy_repr_int(self):
        original_object = 15
        lazy_obj = lazy(lambda: original_object, int)
        self.assertEqual(repr(original_object), repr(lazy_obj()))

    def test_lazy_repr_bytes(self):
        original_object = b"J\xc3\xbcst a str\xc3\xadng"
        lazy_obj = lazy(lambda: original_object, bytes)
        self.assertEqual(repr(original_object), repr(lazy_obj()))

    def test_lazy_regular_method(self):
        original_object = 15
        lazy_obj = lazy(lambda: original_object, int)
        self.assertEqual(original_object.bit_length(), lazy_obj().bit_length())

    def test_lazy_bytes_and_str_result_classes(self):
        lazy_obj = lazy(lambda: "test", str, bytes)
        self.assertEqual(str(lazy_obj()), "test")

    def test_lazy_str_cast_mixed_result_types(self):
        lazy_value = lazy(lambda: [1], str, list)()
        self.assertEqual(str(lazy_value), "[1]")

    def test_lazy_str_cast_mixed_bytes_result_types(self):
        lazy_value = lazy(lambda: [1], bytes, list)()
        self.assertEqual(str(lazy_value), "[1]")

    def test_classproperty_getter(self):
        """
        Tests the behavior of class properties, specifically their getters, when accessed through the class and instances of the class.
        """
        class Foo:
            foo_attr = 123

            def __init__(self):
                self.foo_attr = 456

            @classproperty
            def foo(cls):
                return cls.foo_attr

        class Bar:
            bar = classproperty()

            @bar.getter
            def bar(cls):
                return 123

        self.assertEqual(Foo.foo, 123)
        self.assertEqual(Foo().foo, 123)
        self.assertEqual(Bar.bar, 123)
        self.assertEqual(Bar().bar, 123)

    def test_classproperty_override_getter(self):
        """
        Tests the override behavior of a class property's getter method. Verifies that the overridden getter is used when accessing the class property through both the class and an instance of the class.
        """
        class Foo:
            @classproperty
            def foo(cls):
                return 123

            @foo.getter
            def foo(cls):
                return 456

        self.assertEqual(Foo.foo, 456)
        self.assertEqual(Foo().foo, 456)
