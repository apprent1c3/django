from decimal import Decimal

from django.db.models.functions import Power
from django.test import TestCase

from ..models import DecimalModel, FloatModel, IntegerModel


class PowerTests(TestCase):
    def test_null(self):
        """

        Tests the database model's handling of null values in mathematical operations.

        Specifically, it checks that when a null value is encountered in a power operation,
        the result is correctly determined as null, regardless of the relative position of
        the null value (base or exponent). This ensures that the model behaves as expected
        when dealing with incomplete or missing data.

        """
        IntegerModel.objects.create(big=100)
        obj = IntegerModel.objects.annotate(
            null_power_small=Power("small", "normal"),
            null_power_normal=Power("normal", "big"),
            null_power_big=Power("big", "normal"),
        ).first()
        self.assertIsNone(obj.null_power_small)
        self.assertIsNone(obj.null_power_normal)
        self.assertIsNone(obj.null_power_big)

    def test_decimal(self):
        """

        Tests the calculation of a decimal power operation using the database's Power function.

        This test ensures that the result of raising a decimal number to a decimal power
        is correctly calculated and returned as a Decimal instance. It verifies both
        the type and the value of the result, comparing it to the equivalent operation
        performed directly on Python Decimal instances.

        """
        DecimalModel.objects.create(n1=Decimal("1.0"), n2=Decimal("-0.6"))
        obj = DecimalModel.objects.annotate(n_power=Power("n1", "n2")).first()
        self.assertIsInstance(obj.n_power, Decimal)
        self.assertAlmostEqual(obj.n_power, Decimal(obj.n1**obj.n2))

    def test_float(self):
        FloatModel.objects.create(f1=2.3, f2=1.1)
        obj = FloatModel.objects.annotate(f_power=Power("f1", "f2")).first()
        self.assertIsInstance(obj.f_power, float)
        self.assertAlmostEqual(obj.f_power, obj.f1**obj.f2)

    def test_integer(self):
        IntegerModel.objects.create(small=-1, normal=20, big=3)
        obj = IntegerModel.objects.annotate(
            small_power=Power("small", "normal"),
            normal_power=Power("normal", "big"),
            big_power=Power("big", "small"),
        ).first()
        self.assertIsInstance(obj.small_power, float)
        self.assertIsInstance(obj.normal_power, float)
        self.assertIsInstance(obj.big_power, float)
        self.assertAlmostEqual(obj.small_power, obj.small**obj.normal)
        self.assertAlmostEqual(obj.normal_power, obj.normal**obj.big)
        self.assertAlmostEqual(obj.big_power, obj.big**obj.small)
