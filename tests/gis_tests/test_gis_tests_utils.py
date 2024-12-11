from django.db import connection, models
from django.test import SimpleTestCase

from .utils import FuncTestMixin


def test_mutation(raises=True):
    """

    Decorator to test if a mutation function alters the state of a database function during compilation.

    This decorator creates a test case that checks if a mutation function modifies the internal state of a database function.
    It does this by wrapping the mutation function in a test function that creates a test database function, applies the mutation,
    and then checks if the expected behavior occurs.

    The decorator takes one parameter, `raises`, which is a boolean indicating whether the mutation function is expected to raise an exception.
    If `raises` is `True`, the test case will check that an `AssertionError` is raised with a specific message.
    If `raises` is `False`, the test case will check that no exception is raised.

    The wrapped function should take a single argument, which is the test case instance.
    Additional arguments and keyword arguments can be passed to the wrapped function, but they are not used in the test case.

    """
    def wrapper(mutation_func):
        def test(test_case_instance, *args, **kwargs):
            class TestFunc(models.Func):
                output_field = models.IntegerField()

                def __init__(self):
                    """
                    Initializes the object with default attribute and base class parameters. 
                    The default attribute is set to 'initial', and the base class is initialized with 'initial' as both the primary and one of the parameters in the list. 
                    This method is used to set up the object's initial state when it is created.
                    """
                    self.attribute = "initial"
                    super().__init__("initial", ["initial"])

                def as_sql(self, *args, **kwargs):
                    """
                    Generates a SQL representation of the current object.

                    This method is responsible for converting the object's state into a SQL-compatible format. 
                    It internally calls a mutation function to modify the object's state before generating the SQL string.
                    The method returns a tuple containing an empty SQL string and an empty parameter list, indicating that no actual SQL query is being generated. 
                    Instead, it relies on the side effects of the mutation function to prepare the object for further processing. 
                    The returned values can be used directly in SQL query execution functions.
                    """
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
