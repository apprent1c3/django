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
        DecimalModel.objects.create(n1=Decimal("-12.9"), n2=Decimal("0.6"))
        obj = DecimalModel.objects.annotate(n1_cot=Cot("n1"), n2_cot=Cot("n2")).first()
        self.assertIsInstance(obj.n1_cot, Decimal)
        self.assertIsInstance(obj.n2_cot, Decimal)
        self.assertAlmostEqual(obj.n1_cot, Decimal(1 / math.tan(obj.n1)))
        self.assertAlmostEqual(obj.n2_cot, Decimal(1 / math.tan(obj.n2)))

    def test_float(self):
        """

        Tests the Cot (cotangent) function for float values.

        This function verifies that the Cot function correctly calculates the cotangent
        of float values for two fields, f1 and f2, in the FloatModel. It checks that the
        results are of type float and match the expected values calculated using the
        math.tan function.

        The test covers both positive and negative float values to ensure the Cot
        function behaves as expected in different scenarios.

        """
        FloatModel.objects.create(f1=-27.5, f2=0.33)
        obj = FloatModel.objects.annotate(f1_cot=Cot("f1"), f2_cot=Cot("f2")).first()
        self.assertIsInstance(obj.f1_cot, float)
        self.assertIsInstance(obj.f2_cot, float)
        self.assertAlmostEqual(obj.f1_cot, 1 / math.tan(obj.f1))
        self.assertAlmostEqual(obj.f2_cot, 1 / math.tan(obj.f2))

    def test_integer(self):
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

        Test the transformation functionality using the cot lookup.

        This test case registers the cot lookup for DecimalField and creates two DecimalModel instances
        with different values. It then filters the objects using the cot lookup and retrieves the object
        where the cot of n1 is greater than 0. The test asserts that the retrieved object has the expected value for n1.

        The purpose of this test is to verify that the cot lookup is functioning correctly,
        allowing for filtering of decimal fields based on the cot of their values.

        """
        with register_lookup(DecimalField, Cot):
            DecimalModel.objects.create(n1=Decimal("12.0"), n2=Decimal("0"))
            DecimalModel.objects.create(n1=Decimal("1.0"), n2=Decimal("0"))
            obj = DecimalModel.objects.filter(n1__cot__gt=0).get()
            self.assertEqual(obj.n1, Decimal("1.0"))
