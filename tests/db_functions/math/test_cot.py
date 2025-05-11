import math
from decimal import Decimal

from django.db.models import DecimalField
from django.db.models.functions import Cot
from django.test import TestCase
from django.test.utils import register_lookup

from ..models import DecimalModel, FloatModel, IntegerModel


class CotTests(TestCase):
    def test_null(self):
        IntegerModel.objects.create()
        obj = IntegerModel.objects.annotate(null_cot=Cot("normal")).first()
        self.assertIsNone(obj.null_cot)

    def test_decimal(self):
        """
        Tests the calculation of the cotangent function on Decimal values in the database.

        Verifies that the Cot function correctly handles Decimal inputs and returns Decimal outputs,
        and that the calculated result matches the expected value of 1/tan(n).
        """
        DecimalModel.objects.create(n1=Decimal("-12.9"), n2=Decimal("0.6"))
        obj = DecimalModel.objects.annotate(n1_cot=Cot("n1"), n2_cot=Cot("n2")).first()
        self.assertIsInstance(obj.n1_cot, Decimal)
        self.assertIsInstance(obj.n2_cot, Decimal)
        self.assertAlmostEqual(obj.n1_cot, Decimal(1 / math.tan(obj.n1)))
        self.assertAlmostEqual(obj.n2_cot, Decimal(1 / math.tan(obj.n2)))

    def test_float(self):
        """
        Tests the cotangent calculation for float fields in the FloatModel using the Cot database function. Verifies that the result is a float and matches the mathematical definition of cotangent (1/tan).
        """
        FloatModel.objects.create(f1=-27.5, f2=0.33)
        obj = FloatModel.objects.annotate(f1_cot=Cot("f1"), f2_cot=Cot("f2")).first()
        self.assertIsInstance(obj.f1_cot, float)
        self.assertIsInstance(obj.f2_cot, float)
        self.assertAlmostEqual(obj.f1_cot, 1 / math.tan(obj.f1))
        self.assertAlmostEqual(obj.f2_cot, 1 / math.tan(obj.f2))

    def test_integer(self):
        """
        Tests the Cot (cotangent) database function for integer values.

        Verifies that annotating a model with Cot expressions results in floating-point
        values and that these values accurately represent the cotangent of the original
        integer values.
        """
        IntegerModel.objects.create(small=-5, normal=15, big=-1)
        obj = IntegerModel.objects.annotate(
            small_cot=Cot("small"),
            normal_cot=Cot("normal"),
            big_cot=Cot("big"),
        ).first()
        self.assertIsInstance(obj.small_cot, float)
        self.assertIsInstance(obj.normal_cot, float)
        self.assertIsInstance(obj.big_cot, float)
        self.assertAlmostEqual(obj.small_cot, 1 / math.tan(obj.small))
        self.assertAlmostEqual(obj.normal_cot, 1 / math.tan(obj.normal))
        self.assertAlmostEqual(obj.big_cot, 1 / math.tan(obj.big))

    def test_transform(self):
        """
        Tests the transformation of decimal fields using the cot lookup.
        """
        with register_lookup(DecimalField, Cot):
            DecimalModel.objects.create(n1=Decimal("12.0"), n2=Decimal("0"))
            DecimalModel.objects.create(n1=Decimal("1.0"), n2=Decimal("0"))
            obj = DecimalModel.objects.filter(n1__cot__gt=0).get()
            self.assertEqual(obj.n1, Decimal("1.0"))
