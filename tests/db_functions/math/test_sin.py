import math
from decimal import Decimal

from django.db.models import DecimalField
from django.db.models.functions import Sin
from django.test import TestCase
from django.test.utils import register_lookup

from ..models import DecimalModel, FloatModel, IntegerModel


class SinTests(TestCase):
    def test_null(self):
        IntegerModel.objects.create()
        obj = IntegerModel.objects.annotate(null_sin=Sin("normal")).first()
        self.assertIsNone(obj.null_sin)

    def test_decimal(self):
        """
        Tests the Sin database function with Decimal field values, verifying that it returns Decimal instances and produces correct results, consistent with the math library's sin function.
        """
        DecimalModel.objects.create(n1=Decimal("-12.9"), n2=Decimal("0.6"))
        obj = DecimalModel.objects.annotate(n1_sin=Sin("n1"), n2_sin=Sin("n2")).first()
        self.assertIsInstance(obj.n1_sin, Decimal)
        self.assertIsInstance(obj.n2_sin, Decimal)
        self.assertAlmostEqual(obj.n1_sin, Decimal(math.sin(obj.n1)))
        self.assertAlmostEqual(obj.n2_sin, Decimal(math.sin(obj.n2)))

    def test_float(self):
        """
        Tests the correct application of trigonometric functions to FloatModel fields.

        Verifies that the Sin function can be used as an annotation in a database query,
        and that the results are correctly converted to floats and match the expected values.
        """
        FloatModel.objects.create(f1=-27.5, f2=0.33)
        obj = FloatModel.objects.annotate(f1_sin=Sin("f1"), f2_sin=Sin("f2")).first()
        self.assertIsInstance(obj.f1_sin, float)
        self.assertIsInstance(obj.f2_sin, float)
        self.assertAlmostEqual(obj.f1_sin, math.sin(obj.f1))
        self.assertAlmostEqual(obj.f2_sin, math.sin(obj.f2))

    def test_integer(self):
        """
        Tests the correctness of the Sin database function when applied to integer fields, 
        verifying the result is a float and matches the expected mathematical value.
        """
        IntegerModel.objects.create(small=-20, normal=15, big=-1)
        obj = IntegerModel.objects.annotate(
            small_sin=Sin("small"),
            normal_sin=Sin("normal"),
            big_sin=Sin("big"),
        ).first()
        self.assertIsInstance(obj.small_sin, float)
        self.assertIsInstance(obj.normal_sin, float)
        self.assertIsInstance(obj.big_sin, float)
        self.assertAlmostEqual(obj.small_sin, math.sin(obj.small))
        self.assertAlmostEqual(obj.normal_sin, math.sin(obj.normal))
        self.assertAlmostEqual(obj.big_sin, math.sin(obj.big))

    def test_transform(self):
        """

        Tests the transformation of DecimalField values using the Sin function.

        Verifies that objects are correctly filtered based on the sine of their DecimalField values.

        """
        with register_lookup(DecimalField, Sin):
            DecimalModel.objects.create(n1=Decimal("5.4"), n2=Decimal("0"))
            DecimalModel.objects.create(n1=Decimal("0.1"), n2=Decimal("0"))
            obj = DecimalModel.objects.filter(n1__sin__lt=0).get()
            self.assertEqual(obj.n1, Decimal("5.4"))
