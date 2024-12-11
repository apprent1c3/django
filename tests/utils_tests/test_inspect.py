import unittest

from django.utils import inspect


class Person:
    def no_arguments(self):
        return None

    def one_argument(self, something):
        return something

    def just_args(self, *args):
        return args

    def all_kinds(self, name, address="home", age=25, *args, **kwargs):
        return kwargs

    @classmethod
    def cls_all_kinds(cls, name, address="home", age=25, *args, **kwargs):
        return kwargs


class TestInspectMethods(unittest.TestCase):
    def test_get_callable_parameters(self):
        self.assertIs(
            inspect._get_callable_parameters(Person.no_arguments),
            inspect._get_callable_parameters(Person.no_arguments),
        )
        self.assertIs(
            inspect._get_callable_parameters(Person().no_arguments),
            inspect._get_callable_parameters(Person().no_arguments),
        )

    def test_get_func_full_args_no_arguments(self):
        """
        Verifies that the get_func_full_args function correctly handles cases where a function has no arguments.

        This test checks that when given a function with no parameters, either as a class method or an instance method, 
        the get_func_full_args function returns an empty list as expected, indicating that there are no arguments to be retrieved.
        """
        self.assertEqual(inspect.get_func_full_args(Person.no_arguments), [])
        self.assertEqual(inspect.get_func_full_args(Person().no_arguments), [])

    def test_get_func_full_args_one_argument(self):
        """

        Tests the functionality of getting full argument names for functions with one argument.

        Verifies that the 'get_func_full_args' function correctly retrieves the argument names 
        from both static and instance methods, returning a list of tuples containing the argument name.

        This test checks the correctness of the function when applied to a method with a single argument.

        """
        self.assertEqual(
            inspect.get_func_full_args(Person.one_argument), [("something",)]
        )
        self.assertEqual(
            inspect.get_func_full_args(Person().one_argument),
            [("something",)],
        )

    def test_get_func_full_args_all_arguments_method(self):
        """

        Test that the get_func_full_args function correctly retrieves all arguments 
        from the all_kinds method, whether called on the class or an instance.

        This ensures that the function can accurately parse method signatures, 
        including regular arguments, variable arguments (*args), and keyword arguments (**kwargs).

        """
        arguments = [
            ("name",),
            ("address", "home"),
            ("age", 25),
            ("*args",),
            ("**kwargs",),
        ]
        self.assertEqual(inspect.get_func_full_args(Person.all_kinds), arguments)
        self.assertEqual(inspect.get_func_full_args(Person().all_kinds), arguments)

    def test_get_func_full_args_all_arguments_classmethod(self):
        arguments = [
            ("name",),
            ("address", "home"),
            ("age", 25),
            ("*args",),
            ("**kwargs",),
        ]
        self.assertEqual(inspect.get_func_full_args(Person.cls_all_kinds), arguments)
        self.assertEqual(inspect.get_func_full_args(Person().cls_all_kinds), arguments)

    def test_func_accepts_var_args_has_var_args(self):
        self.assertIs(inspect.func_accepts_var_args(Person.just_args), True)
        self.assertIs(inspect.func_accepts_var_args(Person().just_args), True)

    def test_func_accepts_var_args_no_var_args(self):
        self.assertIs(inspect.func_accepts_var_args(Person.one_argument), False)
        self.assertIs(inspect.func_accepts_var_args(Person().one_argument), False)

    def test_method_has_no_args(self):
        """
        Tests whether the `inspect.method_has_no_args` function correctly identifies methods with no arguments.

        This function verifies that `method_has_no_args` returns True for methods without any parameters and False for methods with parameters, in both static and instance contexts.
        """
        self.assertIs(inspect.method_has_no_args(Person.no_arguments), True)
        self.assertIs(inspect.method_has_no_args(Person().no_arguments), True)
        self.assertIs(inspect.method_has_no_args(Person.one_argument), False)
        self.assertIs(inspect.method_has_no_args(Person().one_argument), False)

    def test_func_supports_parameter(self):
        """
        Tests that the all_kinds function supports the 'address' parameter.

        This test case verifies that the function can handle the 'address' parameter both 
        when called as a class method and as an instance method. Additionally, it checks 
        that the function does not support the 'zone' parameter in either case. The test 
        ensures the correctness of the func_supports_parameter inspection function in 
        determining parameter support for the all_kinds function in different contexts.
        """
        self.assertIs(
            inspect.func_supports_parameter(Person.all_kinds, "address"), True
        )
        self.assertIs(
            inspect.func_supports_parameter(Person().all_kinds, "address"),
            True,
        )
        self.assertIs(inspect.func_supports_parameter(Person.all_kinds, "zone"), False)
        self.assertIs(
            inspect.func_supports_parameter(Person().all_kinds, "zone"),
            False,
        )

    def test_func_accepts_kwargs(self):
        self.assertIs(inspect.func_accepts_kwargs(Person.just_args), False)
        self.assertIs(inspect.func_accepts_kwargs(Person().just_args), False)
        self.assertIs(inspect.func_accepts_kwargs(Person.all_kinds), True)
        self.assertIs(inspect.func_accepts_kwargs(Person().just_args), False)
