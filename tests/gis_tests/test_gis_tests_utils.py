from django.db import connection, models
from django.test import SimpleTestCase

from .utils import FuncTestMixin


def test_mutation(raises=True):
    """

    Decorator to test if a mutation function modifies a SQL function during compilation.

    The decorated test function will check if the mutation function raises an AssertionError
    when the SQL function is compiled. The test can be configured to check for either
    the presence or absence of the exception, depending on the 'raises' parameter.

    :param raises: Whether the mutation function is expected to raise an AssertionError.
    :rtype: function

    """
    def wrapper(mutation_func):
        """

        Function decorator to wrap a test function for database mutation.

        Checks whether a provided mutation function modifies the function's output during compilation.
        Can be used with test case instances to assert if an AssertionError is raised. 

        :param mutation_func: The function that potentially modifies the output
        :return: A test function that checks the mutation function's behavior

        """
        def test(test_case_instance, *args, **kwargs):
            """
            Tests whether the TestFunc class is mutated during compilation, 
            depending on the raises parameter, it checks if an AssertionError is raised 
            with a specific message or if the as_sql method runs without errors.
            """
            class TestFunc(models.Func):
                output_field = models.IntegerField()

                def __init__(self):
                    self.attribute = "initial"
                    super().__init__("initial", ["initial"])

                def as_sql(self, *args, **kwargs):
                    mutation_func(self)
                    return "", ()

            if raises:
                msg = "TestFunc Func was mutated during compilation."
                with test_case_instance.assertRaisesMessage(AssertionError, msg):
                    getattr(TestFunc(), "as_" + connection.vendor)(None, None)
            else:
                getattr(TestFunc(), "as_" + connection.vendor)(None, None)

        return test

    return wrapper


class FuncTestMixinTests(FuncTestMixin, SimpleTestCase):
    @test_mutation()
    def test_mutated_attribute(func):
        func.attribute = "mutated"

    @test_mutation()
    def test_mutated_expressions(func):
        func.source_expressions.clear()

    @test_mutation()
    def test_mutated_expression(func):
        func.source_expressions[0].name = "mutated"

    @test_mutation()
    def test_mutated_expression_deep(func):
        func.source_expressions[1].value[0] = "mutated"

    @test_mutation(raises=False)
    def test_not_mutated(func):
        pass
