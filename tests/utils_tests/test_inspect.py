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
        self.assertEqual(inspect.get_func_full_args(Person.no_arguments), [])
        self.assertEqual(inspect.get_func_full_args(Person().no_arguments), [])

    def test_get_func_full_args_one_argument(self):
        self.assertEqual(
            inspect.get_func_full_args(Person.one_argument), [("something",)]
        )
        self.assertEqual(
            inspect.get_func_full_args(Person().one_argument),
            [("something",)],
        )

    def test_get_func_full_args_all_arguments_method(self):
        """
        Tests that the inspect.get_func_full_args function correctly retrieves all 
        arguments of the all_kinds method in the Person class, including positional, default, 
        variable, and keyword arguments.

        It verifies the function's behavior when provided with both the class method 
        and an instance method, ensuring consistency in argument retrieval regardless 
        of the method's invocation context.
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
        """
        Tests that the one_argument method does not accept variable arguments.

        This test checks the function signature of the one_argument method 
        in the Person class and an instance of the Person class to verify 
        it does not accept any variable arguments, ensuring its usage 
        conforms to the expected function signature.

        It utilizes the inspect module to check the function's parameters 
        and asserts that the result matches the expected behavior, 
        providing confidence in the function's implementation and usage.

        """
        self.assertIs(inspect.func_accepts_var_args(Person.one_argument), False)
        self.assertIs(inspect.func_accepts_var_args(Person().one_argument), False)

    def test_method_has_no_args(self):
        self.assertIs(inspect.method_has_no_args(Person.no_arguments), True)
        self.assertIs(inspect.method_has_no_args(Person().no_arguments), True)
        self.assertIs(inspect.method_has_no_args(Person.one_argument), False)
        self.assertIs(inspect.method_has_no_args(Person().one_argument), False)

    def test_func_supports_parameter(self):
        """
        Tests whether the all_kinds function of the Person class supports a given parameter.

        This function checks if the all_kinds function can accept a specific parameter, 
        such as 'address' or 'zone', when called as a class method or an instance method.
        It verifies that the function correctly identifies supported and unsupported parameters.
        The test cases cover both class-level and instance-level function calls to ensure consistent behavior.
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
