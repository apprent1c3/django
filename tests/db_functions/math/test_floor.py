import math
from decimal import Decimal

from django.db.models import DecimalField
from django.db.models.functions import Floor
from django.test import TestCase
from django.test.utils import register_lookup

from ..models import DecimalModel, FloatModel, IntegerModel


class FloorTests(TestCase):
    def test_null(self):
        IntegerModel.objects.create()
        obj = IntegerModel.objects.annotate(null_floor=Floor("normal")).first()
        self.assertIsNone(obj.null_floor)

    def test_decimal(self):
        DecimalModel.objects.create(n1=Decimal("-12.9"), n2=Decimal("0.6"))
        obj = DecimalModel.objects.annotate(
            n1_floor=Floor("n1"), n2_floor=Floor("n2")
        ).first()
        self.assertIsInstance(obj.n1_floor, Decimal)
        self.assertIsInstance(obj.n2_floor, Decimal)
        self.assertEqual(obj.n1_floor, Decimal(math.floor(obj.n1)))
        self.assertEqual(obj.n2_floor, Decimal(math.floor(obj.n2)))

    def test_float(self):
        FloatModel.objects.create(f1=-27.5, f2=0.33)
        obj = FloatModel.objects.annotate(
            f1_floor=Floor("f1"), f2_floor=Floor("f2")
        ).first()
        self.assertIsInstance(obj.f1_floor, float)
        self.assertIsInstance(obj.f2_floor, float)
        self.assertEqual(obj.f1_floor, math.floor(obj.f1))
        self.assertEqual(obj.f2_floor, math.floor(obj.f2))

    def test_integer(self):
        IntegerModel.objects.create(small=-20, normal=15, big=-1)
        obj = IntegerModel.objects.annotate(
            small_floor=Floor("small"),
            normal_floor=Floor("normal"),
            big_floor=Floor("big"),
        ).first()
        self.assertIsInstance(obj.small_floor, int)
        self.assertIsInstance(obj.normal_floor, int)
        self.assertIsInstance(obj.big_floor, int)
        self.assertEqual(obj.small_floor, math.floor(obj.small))
        self.assertEqual(obj.normal_floor, math.floor(obj.normal))
        self.assertEqual(obj.big_floor, math.floor(obj.big))

    def test_transform(self):
        """

        Tests the floor transform lookup by checking if it correctly filters Decimal fields.

        The floor transform is applied to the DecimalField, effectively rounding down to the nearest integer.
        This test case creates two DecimalModel objects with different decimal values and then attempts to retrieve
        the object where the floor of the 'n1' field is greater than 4. The test passes if the object with 'n1' equal to 5.4 is returned.

        """
        with register_lookup(DecimalField, Floor):
            DecimalModel.objects.create(n1=Decimal("5.4"), n2=Decimal("0"))
            DecimalModel.objects.create(n1=Decimal("3.4"), n2=Decimal("0"))
            obj = DecimalModel.objects.filter(n1__floor__gt=4).get()
            self.assertEqual(obj.n1, Decimal("5.4"))
