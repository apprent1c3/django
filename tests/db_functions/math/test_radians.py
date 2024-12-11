import math
from decimal import Decimal

from django.db.models import DecimalField
from django.db.models.functions import Radians
from django.test import TestCase
from django.test.utils import register_lookup

from ..models import DecimalModel, FloatModel, IntegerModel


class RadiansTests(TestCase):
    def test_null(self):
        IntegerModel.objects.create()
        obj = IntegerModel.objects.annotate(null_radians=Radians("normal")).first()
        self.assertIsNone(obj.null_radians)

    def test_decimal(self):
        """

        Tests the DecimalModel's annotation functionality for converting decimal degrees to radians.

        This test case verifies that the `Radians` annotation function correctly converts decimal degree values to radians, ensuring the result is also a decimal value. It checks the output data type and performs a comparison with the expected radian values calculated using the math library.

        The test involves creating a test instance of the DecimalModel with sample decimal degree values, applying the `Radians` annotation, and then asserting the correctness of the resulting radian values.

        """
        DecimalModel.objects.create(n1=Decimal("-12.9"), n2=Decimal("0.6"))
        obj = DecimalModel.objects.annotate(
            n1_radians=Radians("n1"), n2_radians=Radians("n2")
        ).first()
        self.assertIsInstance(obj.n1_radians, Decimal)
        self.assertIsInstance(obj.n2_radians, Decimal)
        self.assertAlmostEqual(obj.n1_radians, Decimal(math.radians(obj.n1)))
        self.assertAlmostEqual(obj.n2_radians, Decimal(math.radians(obj.n2)))

    def test_float(self):
        FloatModel.objects.create(f1=-27.5, f2=0.33)
        obj = FloatModel.objects.annotate(
            f1_radians=Radians("f1"), f2_radians=Radians("f2")
        ).first()
        self.assertIsInstance(obj.f1_radians, float)
        self.assertIsInstance(obj.f2_radians, float)
        self.assertAlmostEqual(obj.f1_radians, math.radians(obj.f1))
        self.assertAlmostEqual(obj.f2_radians, math.radians(obj.f2))

    def test_integer(self):
        """
        Tests the conversion of integer values to radians using the Radians database function.

        This function creates an instance of IntegerModel with small, normal, and big integer values, 
        then uses the Radians function to annotate these values with their corresponding radians. 
        It verifies that the resulting radians values are floats and match the expected results calculated 
        using the math.radians function, ensuring accurate conversion of integer values to radians.
        """
        IntegerModel.objects.create(small=-20, normal=15, big=-1)
        obj = IntegerModel.objects.annotate(
            small_radians=Radians("small"),
            normal_radians=Radians("normal"),
            big_radians=Radians("big"),
        ).first()
        self.assertIsInstance(obj.small_radians, float)
        self.assertIsInstance(obj.normal_radians, float)
        self.assertIsInstance(obj.big_radians, float)
        self.assertAlmostEqual(obj.small_radians, math.radians(obj.small))
        self.assertAlmostEqual(obj.normal_radians, math.radians(obj.normal))
        self.assertAlmostEqual(obj.big_radians, math.radians(obj.big))

    def test_transform(self):
        """

        Tests the transformation of decimal fields to radians.

        This test case verifies that decimal fields can be successfully transformed to radians
        and used in filters. It checks that objects can be created with decimal fields and
        then retrieved using a filter that compares the radians value of those fields.

        The test creates two objects with decimal fields and then uses a filter to retrieve
        the object where the radians value of the field is greater than 0. It then asserts
        that the retrieved object has the expected decimal field value.

        """
        with register_lookup(DecimalField, Radians):
            DecimalModel.objects.create(n1=Decimal("2.0"), n2=Decimal("0"))
            DecimalModel.objects.create(n1=Decimal("-1.0"), n2=Decimal("0"))
            obj = DecimalModel.objects.filter(n1__radians__gt=0).get()
            self.assertEqual(obj.n1, Decimal("2.0"))
