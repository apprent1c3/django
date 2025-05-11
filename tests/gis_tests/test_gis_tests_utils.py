from django.db import connection, models
from django.test import SimpleTestCase

from .utils import FuncTestMixin


def test_mutation(raises=True):
    """
    Decorator for testing mutation of database function during compilation.

    Tests whether the provided mutation function alters the function's state
    in an expected way, checking for either the presence or absence of a
    mutation, depending on the 'raises' parameter.

    :param raises: Whether to expect an AssertionError due to mutation (default: True)
    :returns: A wrapper function for testing the mutation function
    """
    def wrapper(mutation_func):
        """

        A decorator-like function that creates a test function for verifying the mutation of a database function during compilation.

        The function takes a mutation function as an argument, which is expected to modify the internal state of a database function.
        The test function returned by the wrapper checks whether the mutation function raises an AssertionError when the database function is compiled.
        If the mutation function is expected to raise an error, the test function verifies that the correct error message is raised; otherwise, it checks that no error is raised.

        """
        def test(test_case_instance, *args, **kwargs):
            """

            Tests the mutation of the TestFunc class during SQL compilation.

            This function verifies that the TestFunc class remains unchanged during the compilation process,
            raising an AssertionError if the class is mutated. The test is performed in the context of the provided test case instance.

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
