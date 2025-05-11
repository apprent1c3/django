import math
from decimal import Decimal

from django.db.models.functions import ATan2
from django.test import TestCase

from ..models import DecimalModel, FloatModel, IntegerModel


class ATan2Tests(TestCase):
    def test_null(self):
        """
        Tests the handling of null values in the ATan2 database function, ensuring it correctly returns None when a null input is provided in various position combinations.
        """
        IntegerModel.objects.create(big=100)
        obj = IntegerModel.objects.annotate(
            null_atan2_sn=ATan2("small", "normal"),
            null_atan2_nb=ATan2("normal", "big"),
            null_atan2_bn=ATan2("big", "normal"),
        ).first()
        self.assertIsNone(obj.null_atan2_sn)
        self.assertIsNone(obj.null_atan2_nb)
        self.assertIsNone(obj.null_atan2_bn)

    def test_decimal(self):
        DecimalModel.objects.create(n1=Decimal("-9.9"), n2=Decimal("4.6"))
        obj = DecimalModel.objects.annotate(n_atan2=ATan2("n1", "n2")).first()
        self.assertIsInstance(obj.n_atan2, Decimal)
        self.assertAlmostEqual(obj.n_atan2, Decimal(math.atan2(obj.n1, obj.n2)))

    def test_float(self):
        FloatModel.objects.create(f1=-25, f2=0.33)
        obj = FloatModel.objects.annotate(f_atan2=ATan2("f1", "f2")).first()
        self.assertIsInstance(obj.f_atan2, float)
        self.assertAlmostEqual(obj.f_atan2, math.atan2(obj.f1, obj.f2))

    def test_integer(self):
        """
        Tests the functionality of the ATan2 database function with integer values.

        Verifies that the function returns the correct results and that the output is of the expected float type, by comparing it to the equivalent math.atan2 calculation.
        """
        IntegerModel.objects.create(small=0, normal=1, big=10)
        obj = IntegerModel.objects.annotate(
            atan2_sn=ATan2("small", "normal"),
            atan2_nb=ATan2("normal", "big"),
        ).first()
        self.assertIsInstance(obj.atan2_sn, float)
        self.assertIsInstance(obj.atan2_nb, float)
        self.assertAlmostEqual(obj.atan2_sn, math.atan2(obj.small, obj.normal))
        self.assertAlmostEqual(obj.atan2_nb, math.atan2(obj.normal, obj.big))
