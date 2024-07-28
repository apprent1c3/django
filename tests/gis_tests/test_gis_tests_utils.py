from django.db import connection, models
from django.test import SimpleTestCase

from .utils import FuncTestMixin


def test_mutation(raises=True):
    """
    This is a comment
    """
    def wrapper(mutation_func):
        """
        This is a comment
        """
        def test(test_case_instance, *args, **kwargs):
            """
            This is a comment
            """
            class TestFunc(models.Func):
                output_field = models.IntegerField()

                def __init__(self):
                    """
                    This is a comment
                    """
                    self.attribute = "initial"
                    super().__init__("initial", ["initial"])

                def as_sql(self, *args, **kwargs):
                    """
                    This is a comment
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
        """
        This is a comment
        """
        func.attribute = "mutated"

    @test_mutation()
    def test_mutated_expressions(func):
        """
        This is a comment
        """
        func.source_expressions.clear()

    @test_mutation()
    def test_mutated_expression(func):
        """
        This is a comment
        """
        func.source_expressions[0].name = "mutated"

    @test_mutation()
    def test_mutated_expression_deep(func):
        """
        This is a comment
        """
        func.source_expressions[1].value[0] = "mutated"

    @test_mutation(raises=False)
    def test_not_mutated(func):
        """
        This is a comment
        """
        pass
