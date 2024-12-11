import math
from decimal import Decimal

from django.db.models.functions import Log
from django.test import TestCase

from ..models import DecimalModel, FloatModel, IntegerModel


class LogTests(TestCase):
    def test_null(self):
        """
        Tests the behavior of the Log database function when encountering null values.
        Verifies that log calculations with null inputs produce null results, as expected by mathematical definition.
        Specifically, this test checks the values of logarithms with zero or undefined base and normal or undefined inputs, ensuring they are correctly evaluated as null.
        """
        IntegerModel.objects.create(big=100)
        obj = IntegerModel.objects.annotate(
            null_log_small=Log("small", "normal"),
            null_log_normal=Log("normal", "big"),
            null_log_big=Log("big", "normal"),
        ).first()
        self.assertIsNone(obj.null_log_small)
        self.assertIsNone(obj.null_log_normal)
        self.assertIsNone(obj.null_log_big)

    def test_decimal(self):
        """
        Test the calculation of the logarithm with decimal numbers.

        This test case verifies that the logarithm of one decimal number with respect to another 
        can be correctly computed and returned as a Decimal instance. It checks that the 
        result is indeed a Decimal object and that its value is approximately equal to the 
        expected result calculated using the math library's log function.
        """
        DecimalModel.objects.create(n1=Decimal("12.9"), n2=Decimal("3.6"))
        obj = DecimalModel.objects.annotate(n_log=Log("n1", "n2")).first()
        self.assertIsInstance(obj.n_log, Decimal)
        self.assertAlmostEqual(obj.n_log, Decimal(math.log(obj.n2, obj.n1)))

    def test_float(self):
        """

        Checks the calculation of the logarithm of one floating point field with respect to another.

        This test case verifies that the logarithmic function can be correctly applied to two float fields in a model.
        It creates an instance of the model with two floating point values, annotates the model with a calculated logarithm field,
        and then checks that the result is a float and matches the expected logarithmic value.

        """
        FloatModel.objects.create(f1=2.0, f2=4.0)
        obj = FloatModel.objects.annotate(f_log=Log("f1", "f2")).first()
        self.assertIsInstance(obj.f_log, float)
        self.assertAlmostEqual(obj.f_log, math.log(obj.f2, obj.f1))

    def test_integer(self):
        IntegerModel.objects.create(small=4, normal=8, big=2)
        obj = IntegerModel.objects.annotate(
            small_log=Log("small", "big"),
            normal_log=Log("normal", "big"),
            big_log=Log("big", "big"),
        ).first()
        self.assertIsInstance(obj.small_log, float)
        self.assertIsInstance(obj.normal_log, float)
        self.assertIsInstance(obj.big_log, float)
        self.assertAlmostEqual(obj.small_log, math.log(obj.big, obj.small))
        self.assertAlmostEqual(obj.normal_log, math.log(obj.big, obj.normal))
        self.assertAlmostEqual(obj.big_log, math.log(obj.big, obj.big))
