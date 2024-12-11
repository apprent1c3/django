from functools import update_wrapper, wraps
from unittest import TestCase

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import (
    login_required,
    permission_required,
    user_passes_test,
)
from django.http import HttpResponse
from django.test import SimpleTestCase
from django.utils.decorators import method_decorator
from django.utils.functional import keep_lazy, keep_lazy_text, lazy
from django.utils.safestring import mark_safe
from django.views.decorators.cache import cache_control, cache_page, never_cache
from django.views.decorators.http import (
    condition,
    require_GET,
    require_http_methods,
    require_POST,
    require_safe,
)
from django.views.decorators.vary import vary_on_cookie, vary_on_headers


def fully_decorated(request):
    """Expected __doc__"""
    return HttpResponse("<html><body>dummy</body></html>")


fully_decorated.anything = "Expected __dict__"


def compose(*functions):
    # compose(f, g)(*args, **kwargs) == f(g(*args, **kwargs))
    """
    .Compose multiple functions into a single function.

    This function takes in an arbitrary number of functions as arguments, 
    reverses their order, and returns a new function that applies each input 
    function in sequence, passing the output of one function as the input to 
    the next. The resulting composed function can then be called with any 
    number of positional and keyword arguments, which are passed to the 
    first function in the composition.

    :rtype: callable
    :return: A new function that represents the composition of the input functions.
    """
    functions = list(reversed(functions))

    def _inner(*args, **kwargs):
        result = functions[0](*args, **kwargs)
        for f in functions[1:]:
            result = f(result)
        return result

    return _inner


full_decorator = compose(
    # django.views.decorators.http
    require_http_methods(["GET"]),
    require_GET,
    require_POST,
    require_safe,
    condition(lambda r: None, lambda r: None),
    # django.views.decorators.vary
    vary_on_headers("Accept-language"),
    vary_on_cookie,
    # django.views.decorators.cache
    cache_page(60 * 15),
    cache_control(private=True),
    never_cache,
    # django.contrib.auth.decorators
    # Apply user_passes_test twice to check #9474
    user_passes_test(lambda u: True),
    login_required,
    permission_required("change_world"),
    # django.contrib.admin.views.decorators
    staff_member_required,
    # django.utils.functional
    keep_lazy(HttpResponse),
    keep_lazy_text,
    lazy,
    # django.utils.safestring
    mark_safe,
)

fully_decorated = full_decorator(fully_decorated)


class DecoratorsTest(TestCase):
    def test_attributes(self):
        """
        Built-in decorators set certain attributes of the wrapped function.
        """
        self.assertEqual(fully_decorated.__name__, "fully_decorated")
        self.assertEqual(fully_decorated.__doc__, "Expected __doc__")
        self.assertEqual(fully_decorated.__dict__["anything"], "Expected __dict__")

    def test_user_passes_test_composition(self):
        """
        The user_passes_test decorator can be applied multiple times (#9474).
        """

        def test1(user):
            """

            Applies a test decorator to a given user object.

            This function appends 'test1' to the user's list of decorators applied and returns a boolean True value, indicating successful application.

            Args:
                user: The user object to apply the decorator to.

            Returns:
                bool: True if the decorator was applied successfully.

            Note:
                This function modifies the user object in-place by appending to its decorators_applied list.

            """
            user.decorators_applied.append("test1")
            return True

        def test2(user):
            user.decorators_applied.append("test2")
            return True

        def callback(request):
            return request.user.decorators_applied

        callback = user_passes_test(test1)(callback)
        callback = user_passes_test(test2)(callback)

        class DummyUser:
            pass

        class DummyRequest:
            pass

        request = DummyRequest()
        request.user = DummyUser()
        request.user.decorators_applied = []
        response = callback(request)

        self.assertEqual(response, ["test2", "test1"])


# For testing method_decorator, a decorator that assumes a single argument.
# We will get type arguments if there is a mismatch in the number of arguments.
def simple_dec(func):
    @wraps(func)
    """
    A decorator that modifies the input to a function by prefixing it with 'test:'.

    This decorator is intended to wrap around existing functions that accept a single string argument.
    The original function's behavior remains unchanged, but its input is modified to include the 'test:' prefix.
    This can be useful in scenarios where a function needs to be tested with a specific input prefix, 
    without altering the original function's implementation. 
    """
    def wrapper(arg):
        return func("test:" + arg)

    return wrapper


simple_dec_m = method_decorator(simple_dec)


# For testing method_decorator, two decorators that add an attribute to the function
def myattr_dec(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    wrapper.myattr = True
    return wrapper


myattr_dec_m = method_decorator(myattr_dec)


def myattr2_dec(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    wrapper.myattr2 = True
    return wrapper


myattr2_dec_m = method_decorator(myattr2_dec)


class ClsDec:
    def __init__(self, myattr):
        self.myattr = myattr

    def __call__(self, f):
        """

        Decorator function that wraps the input function f and modifies its return value.

        The wrapped function returns True only if the original function f returns True and 
        the object's attribute myattr is also True. If either of these conditions is False, 
        the wrapped function returns False.

        The original function's metadata, such as its name and docstring, are preserved in 
        the wrapped function.

        """
        def wrapper():
            return f() and self.myattr

        return update_wrapper(wrapper, f)


class MethodDecoratorTests(SimpleTestCase):
    """
    Tests for method_decorator
    """

    def test_preserve_signature(self):
        class Test:
            @simple_dec_m
            def say(self, arg):
                return arg

        self.assertEqual("test:hello", Test().say("hello"))

    def test_preserve_attributes(self):
        # Sanity check myattr_dec and myattr2_dec
        @myattr_dec
        """
        Tests the preservation of attributes when using various method decorators.

        This test case ensures that attributes set by decorators are correctly applied to 
        functions and methods, and that they do not interfere with each other. It also 
        verifies that the original method's documentation string and name are preserved.

        The test covers different scenarios, including:

        * Single decorators applied to functions and methods
        * Multiple decorators applied to functions and methods in various orders
        * Decorators applied to methods within classes
        * Decorators applied using the `method_decorator` function
        * Decorators applied as iterables

        The expected outcome is that all attributes set by the decorators are correctly 
        preserved, and that the original method's documentation string and name remain 
        unchanged.
        """
        def func():
            pass

        self.assertIs(getattr(func, "myattr", False), True)

        @myattr2_dec
        def func():
            pass

        self.assertIs(getattr(func, "myattr2", False), True)

        @myattr_dec
        @myattr2_dec
        def func():
            pass

        self.assertIs(getattr(func, "myattr", False), True)
        self.assertIs(getattr(func, "myattr2", False), False)

        # Decorate using method_decorator() on the method.
        class TestPlain:
            @myattr_dec_m
            @myattr2_dec_m
            def method(self):
                "A method"
                pass

        # Decorate using method_decorator() on both the class and the method.
        # The decorators applied to the methods are applied before the ones
        # applied to the class.
        @method_decorator(myattr_dec_m, "method")
        class TestMethodAndClass:
            @method_decorator(myattr2_dec_m)
            def method(self):
                "A method"
                pass

        # Decorate using an iterable of function decorators.
        @method_decorator((myattr_dec, myattr2_dec), "method")
        class TestFunctionIterable:
            def method(self):
                "A method"
                pass

        # Decorate using an iterable of method decorators.
        decorators = (myattr_dec_m, myattr2_dec_m)

        @method_decorator(decorators, "method")
        class TestMethodIterable:
            def method(self):
                "A method"
                pass

        tests = (
            TestPlain,
            TestMethodAndClass,
            TestFunctionIterable,
            TestMethodIterable,
        )
        for Test in tests:
            with self.subTest(Test=Test):
                self.assertIs(getattr(Test().method, "myattr", False), True)
                self.assertIs(getattr(Test().method, "myattr2", False), True)
                self.assertIs(getattr(Test.method, "myattr", False), True)
                self.assertIs(getattr(Test.method, "myattr2", False), True)
                self.assertEqual(Test.method.__doc__, "A method")
                self.assertEqual(Test.method.__name__, "method")

    def test_new_attribute(self):
        """A decorator that sets a new attribute on the method."""

        def decorate(func):
            func.x = 1
            return func

        class MyClass:
            @method_decorator(decorate)
            def method(self):
                return True

        obj = MyClass()
        self.assertEqual(obj.method.x, 1)
        self.assertIs(obj.method(), True)

    def test_bad_iterable(self):
        decorators = {myattr_dec_m, myattr2_dec_m}
        msg = "'set' object is not subscriptable"
        with self.assertRaisesMessage(TypeError, msg):

            @method_decorator(decorators, "method")
            class TestIterable:
                def method(self):
                    "A method"
                    pass

    # Test for argumented decorator
    def test_argumented(self):
        class Test:
            @method_decorator(ClsDec(False))
            def method(self):
                return True

        self.assertIs(Test().method(), False)

    def test_descriptors(self):
        """

        Tests the usage of method decorators with descriptor wrappers.

        This test case verifies that a method decorated with a descriptor wrapper
        functions correctly when called on an instance of a class. It checks
        whether the original method's behavior is preserved after applying the
        decoration.

        The test uses a simple method that takes an argument and returns it,
        and a decorator that wraps the original method. The decorator is then
        combined with a descriptor wrapper to ensure proper binding of the
        method to the instance.

        The expected outcome is that the decorated method returns the same
        value as the original method when called with the same argument.

        """
        def original_dec(wrapped):
            """
            Creates a decorator that preserves the original function's behavior.

            This decorator takes in a function as an argument and returns a new function that wraps the original function. The wrapped function takes in one argument and returns the result of calling the original function with that argument. 

            It effectively acts as an identity decorator, meaning it does not modify the original function's behavior in any way. 

            :arg wrapped: The function to be wrapped.
            :return: A new function that wraps the original function.

            """
            def _wrapped(arg):
                return wrapped(arg)

            return _wrapped

        method_dec = method_decorator(original_dec)

        class bound_wrapper:
            def __init__(self, wrapped):
                """
                Initializes a wrapper object with the given wrapped object, preserving the original object's name.

                :param wrapped: The object to be wrapped, typically a function or another callable. 
                :return: None 
                :note: This initializer is expected to be used in the context of a class that provides a wrapping functionality, where the wrapped object's attributes and methods are delegated or extended.
                """
                self.wrapped = wrapped
                self.__name__ = wrapped.__name__

            def __call__(self, arg):
                return self.wrapped(arg)

            def __get__(self, instance, cls=None):
                return self

        class descriptor_wrapper:
            def __init__(self, wrapped):
                """
                Initializes a wrapper object, encapsulating the provided wrapped object.

                 The wrapped object's properties are preserved, including its name.

                 :param wrapped: The object to be wrapped by the current instance.

                """
                self.wrapped = wrapped
                self.__name__ = wrapped.__name__

            def __get__(self, instance, cls=None):
                return bound_wrapper(self.wrapped.__get__(instance, cls))

        class Test:
            @method_dec
            @descriptor_wrapper
            def method(self, arg):
                return arg

        self.assertEqual(Test().method(1), 1)

    def test_class_decoration(self):
        """
        @method_decorator can be used to decorate a class and its methods.
        """

        def deco(func):
            """

            A decorator function that replaces the original function with a wrapper.

            This decorator always returns True, effectively overriding the original function's behavior.

            It takes in a function as an argument and returns a new function, allowing for modification or extension of the original function's behavior.

            The wrapper function accepts any number of positional and keyword arguments, but does not use them in this implementation.

            Use this decorator when you want to ensure a function always returns True, such as for testing or placeholder purposes.

            :arg func: The original function to be decorated
            :return: A new function that always returns True

            """
            def _wrapper(*args, **kwargs):
                return True

            return _wrapper

        @method_decorator(deco, name="method")
        class Test:
            def method(self):
                return False

        self.assertTrue(Test().method())

    def test_tuple_of_decorators(self):
        """
        @method_decorator can accept a tuple of decorators.
        """

        def add_question_mark(func):
            """
            Appends a question mark to the result of the wrapped function.

            This decorator is used to modify the output of a function by adding a question mark at the end of its result. It takes another function as an argument, executes it with the provided arguments, and appends a question mark to its return value. The result is then returned by the wrapper function.

            The purpose of this decorator is to provide a simple way to transform the output of a function without permanently modifying it, allowing for greater flexibility and reusability in different contexts.
            """
            def _wrapper(*args, **kwargs):
                return func(*args, **kwargs) + "?"

            return _wrapper

        def add_exclamation_mark(func):
            """
            Decorator that appends an exclamation mark to the result of a function.

            This decorator can be used to modify the output of a function by adding an exclamation mark at the end.
            It preserves the original function's arguments and keyword arguments, and only alters the returned value.

            Example use cases include modifying function outputs for display purposes or changing the format of strings.
            The original function remains unchanged, and the decorated function returns the modified result.

            :returns: The result of the decorated function with an exclamation mark appended to the end

            """
            def _wrapper(*args, **kwargs):
                return func(*args, **kwargs) + "!"

            return _wrapper

        # The order should be consistent with the usual order in which
        # decorators are applied, e.g.
        #    @add_exclamation_mark
        #    @add_question_mark
        #    def func():
        #        ...
        decorators = (add_exclamation_mark, add_question_mark)

        @method_decorator(decorators, name="method")
        class TestFirst:
            def method(self):
                return "hello world"

        class TestSecond:
            @method_decorator(decorators)
            def method(self):
                return "hello world"

        self.assertEqual(TestFirst().method(), "hello world?!")
        self.assertEqual(TestSecond().method(), "hello world?!")

    def test_invalid_non_callable_attribute_decoration(self):
        """
        @method_decorator on a non-callable attribute raises an error.
        """
        msg = (
            "Cannot decorate 'prop' as it isn't a callable attribute of "
            "<class 'Test'> (1)"
        )
        with self.assertRaisesMessage(TypeError, msg):

            @method_decorator(lambda: None, name="prop")
            class Test:
                prop = 1

                @classmethod
                def __module__(cls):
                    return "tests"

    def test_invalid_method_name_to_decorate(self):
        """
        @method_decorator on a nonexistent method raises an error.
        """
        msg = (
            "The keyword argument `name` must be the name of a method of the "
            "decorated class: <class 'Test'>. Got 'nonexistent_method' instead"
        )
        with self.assertRaisesMessage(ValueError, msg):

            @method_decorator(lambda: None, name="nonexistent_method")
            class Test:
                @classmethod
                def __module__(cls):
                    return "tests"

    def test_wrapper_assignments(self):
        """@method_decorator preserves wrapper assignments."""
        func_name = None
        func_module = None

        def decorator(func):
            @wraps(func)
            """
            .\"\"\"
            A decorator that preserves the original function's metadata while also capturing its name and module.

            This decorator is useful for logging or monitoring purposes, as it provides a way to identify the original function being called.
            It captures the function's name and module, making it easier to track and debug function calls.

            The decorator does not modify the original function's behavior, it only adds the functionality of capturing the function's metadata.

            """
            def inner(*args, **kwargs):
                nonlocal func_name, func_module
                func_name = getattr(func, "__name__", None)
                func_module = getattr(func, "__module__", None)
                return func(*args, **kwargs)

            return inner

        class Test:
            @method_decorator(decorator)
            def method(self):
                return "tests"

        Test().method()
        self.assertEqual(func_name, "method")
        self.assertIsNotNone(func_module)
