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
    Compose multiple functions together, creating a pipeline where the output of each function is used as the input for the next.

    The functions are applied in reverse order, meaning the first function passed to compose is executed first and the last function passed is executed last.

    This allows for a concise way to chain together multiple operations without the need for intermediate variables or nested function calls. 

    The returned function takes in any number of positional and keyword arguments, which are passed directly to the first function in the pipeline. 

    Example use cases include data processing pipelines, function composition, and higher-order programming.
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

            Tests the functionality related to a given user.

            This function applies a test decorator to the provided user and returns a boolean result.
            The decorator is tracked in the user's decorators_applied list, allowing for further analysis or processing.

            :param user: The user object to be tested
            :return: A boolean indicating the success of the test operation

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

    Decorator function that modifies the behavior of the decorated function by prepending 'test:' to its input argument.

    This decorator is designed to wrap a function that takes a single argument, and returns the result of calling the original function with the modified argument. The original function's behavior is preserved, but its input is transformed before being processed.

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
    """
    Decorator function to set a custom attribute `myattr2` on a function.

    This decorator allows you to mark a function with the `myattr2` attribute, 
    indicating that it has been modified or extended in some way. The original 
    function's behavior is preserved, and the decorated function will return the 
    same results as the original. The `myattr2` attribute can be used for inspection 
    or filtering purposes. 

    :returns: The decorated function with the `myattr2` attribute set to `True`.

    """
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    wrapper.myattr2 = True
    return wrapper


myattr2_dec_m = method_decorator(myattr2_dec)


class ClsDec:
    def __init__(self, myattr):
        self.myattr = myattr

    def __call__(self, f):
        def wrapper():
            return f() and self.myattr

        return update_wrapper(wrapper, f)


class MethodDecoratorTests(SimpleTestCase):
    """
    Tests for method_decorator
    """

    def test_preserve_signature(self):
        """
        Tests that a function decorated with simple_dec_m preserves its original signature.

        This test case verifies that the decorated function can be called with the expected
        arguments and returns the correct result, ensuring that the decorator does not alter
        the function's behavior or interface. The test uses a simple example class `Test`
        with a method `say` that takes an argument, and checks that the decorated method
        returns the expected output when called with a specific input.
        """
        class Test:
            @simple_dec_m
            def say(self, arg):
                return arg

        self.assertEqual("test:hello", Test().say("hello"))

    def test_preserve_attributes(self):
        # Sanity check myattr_dec and myattr2_dec
        @myattr_dec
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
        """
        Test that a class decorator correctly overrides the return value of a method.

        This test verifies that a class-level decorator properly modifies the behavior of a
        decorated method. The decorator is expected to return False, regardless of the original
        method's return value.

        The test case creates a test class with a decorated method, invokes the method, and
        asserts that the return value is False, as expected from the decorator's behavior.
        """
        class Test:
            @method_decorator(ClsDec(False))
            def method(self):
                return True

        self.assertIs(Test().method(), False)

    def test_descriptors(self):
        """

        Tests the functionality of method decorators in conjunction with descriptor wrappers.

        This test case verifies that the application of a decorator to a method using a descriptor wrapper 
        results in the correct execution of the original method. The test involves creating a decorator, 
        a descriptor wrapper, and a class with a decorated method. It then asserts that the decorated method 
        behaves as expected when invoked on an instance of the class.

        """
        def original_dec(wrapped):
            """

            Create a decorator that preserves the original behavior of a function.

            This decorator returns a new function that wraps the original function, 
            passing the input argument to it and returning its result. The original 
            function's behavior and output are not modified in any way.

            The purpose of this decorator is likely to serve as a foundation for 
            more complex decorators that need to build upon the original function's 
            behavior.

            :param wrapped: The function to be wrapped
            :return: A new function that wraps the original function

            """
            def _wrapped(arg):
                return wrapped(arg)

            return _wrapped

        method_dec = method_decorator(original_dec)

        class bound_wrapper:
            def __init__(self, wrapped):
                self.wrapped = wrapped
                self.__name__ = wrapped.__name__

            def __call__(self, arg):
                return self.wrapped(arg)

            def __get__(self, instance, cls=None):
                return self

        class descriptor_wrapper:
            def __init__(self, wrapped):
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

            The wrapper function currently returns True, effectively overriding the original function's behavior.
            It captures all positional and keyword arguments passed to the original function, 
            but does not use them in the current implementation.

            This decorator can be used to alter or extend the behavior of existing functions,
            although its current implementation simply returns a constant value.

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
            A decorator function that appends a question mark to the output of a given function.

             It takes in a function as an argument, wraps it with a new function, and returns the wrapped function.
             The wrapped function calls the original function with its original arguments and keyword arguments, 
             then appends a question mark to the result before returning it.

             This decorator can be used to easily add a question mark to the output of any function, 
             which can be useful for functions that return strings or other text-based outputs.
            """
            def _wrapper(*args, **kwargs):
                return func(*args, **kwargs) + "?"

            return _wrapper

        def add_exclamation_mark(func):
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
            décorator 

                A function decorator that captures and assigns the name and module of the 
                decorated function to the func_name and func_module variables, 
                respectively, while preserving the original function's behavior and 
                metadata. It enables the decoration of functions without altering their 
                functionality, thereby providing a seamless way to track or log 
                function-specific information.
            """
            def inner(*args, **kwargs):
                """
                Inner function wrapper that preserves the original function's name and module.

                This wrapper captures the name and module of the original function, allowing for 
                accurate identification and logging of function calls. It then calls the original 
                function with the provided arguments, returning the result. The wrapper does not 
                alter the behavior of the original function, making it suitable for use in 
                decorator patterns.

                Parameters
                ----------
                *args : variable
                    Variable length non-keyword arguments to be passed to the original function.
                **kwargs : variable
                    Variable length keyword arguments to be passed to the original function.

                Returns
                -------
                result
                    The result of calling the original function with the provided arguments.

                Notes
                -----
                This wrapper is intended for use within a decorator, and should not be called 
                directly. The preserved function name and module are stored in the func_name and 
                func_module variables, respectively, and can be accessed as needed.

                """
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
