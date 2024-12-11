import math
from decimal import Decimal

from django.db.models.functions import Mod
from django.test import TestCase

from ..models import DecimalModel, FloatModel, IntegerModel


class ModTests(TestCase):
    def test_null(self):
        """

        Tests the behavior of the Mod database function when dealing with null values.

        This test case verifies that the Mod function correctly handles null values by
        annotating a model instance with the Mod function and checking that the result
        is None when the dividend or divisor is null.

        """
        IntegerModel.objects.create(big=100)
        obj = IntegerModel.objects.annotate(
            null_mod_small=Mod("small", "normal"),
            null_mod_normal=Mod("normal", "big"),
        ).first()
        self.assertIsNone(obj.null_mod_small)
        self.assertIsNone(obj.null_mod_normal)

    def test_decimal(self):
        DecimalModel.objects.create(n1=Decimal("-9.9"), n2=Decimal("4.6"))
        obj = DecimalModel.objects.annotate(n_mod=Mod("n1", "n2")).first()
        self.assertIsInstance(obj.n_mod, Decimal)
        self.assertAlmostEqual(obj.n_mod, Decimal(math.fmod(obj.n1, obj.n2)))

    def test_float(self):
        """

        Tests the Mod database function with floating point numbers.

        This test ensures that the Mod function correctly calculates the remainder of
        a floating point division operation. It validates the result against the math
        library's fmod function for accuracy.

        The test creates a FloatModel instance with negative and fractional values,
        applies the Mod function, and verifies that the result is a float. It then
        compares the result with the equivalent operation using math.fmod to confirm
        accuracy.

        """
        FloatModel.objects.create(f1=-25, f2=0.33)
        obj = FloatModel.objects.annotate(f_mod=Mod("f1", "f2")).first()
        self.assertIsInstance(obj.f_mod, float)
        self.assertAlmostEqual(obj.f_mod, math.fmod(obj.f1, obj.f2))

    def test_integer(self):
        """

        Tests the usage of the Mod database function with integer fields.

        This function creates an instance of IntegerModel, annotates it with the modulus
        of each field (small, normal, big) with respect to another field, and then checks
        that the resulting annotations are of type float and equal to the expected values
        calculated using the math.fmod function.

        The test covers the correctness of the Mod function in a cyclical operation 
        where each field is taken modulo another, ensuring that the function behaves as
        expected in different scenarios.

        """
        IntegerModel.objects.create(small=20, normal=15, big=1)
        obj = IntegerModel.objects.annotate(
            small_mod=Mod("small", "normal"),
            normal_mod=Mod("normal", "big"),
            big_mod=Mod("big", "small"),
        ).first()
        self.assertIsInstance(obj.small_mod, float)
        self.assertIsInstance(obj.normal_mod, float)
        self.assertIsInstance(obj.big_mod, float)
        self.assertEqual(obj.small_mod, math.fmod(obj.small, obj.normal))
        self.assertEqual(obj.normal_mod, math.fmod(obj.normal, obj.big))
        self.assertEqual(obj.big_mod, math.fmod(obj.big, obj.small))
