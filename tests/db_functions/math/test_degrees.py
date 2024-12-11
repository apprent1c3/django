import math
from decimal import Decimal

from django.db.models import DecimalField
from django.db.models.functions import Degrees
from django.test import TestCase
from django.test.utils import register_lookup

from ..models import DecimalModel, FloatModel, IntegerModel


class DegreesTests(TestCase):
    def test_null(self):
        """
        Tests the null value handling of the Degrees annotation.

        Verifies that when the Degrees annotation is applied to an object with no associated degrees, the result is None.
        """
        IntegerModel.objects.create()
        obj = IntegerModel.objects.annotate(null_degrees=Degrees("normal")).first()
        self.assertIsNone(obj.null_degrees)

    def test_decimal(self):
        """

        Tests the conversion of decimal values to degrees using the Degrees database function.

        This test case creates a DecimalModel instance with sample decimal values, 
        annotates the model with the Degrees function to convert the decimal values to degrees, 
        and then verifies that the converted values are instances of Decimal and match the expected results.

        The test ensures that the Degrees function correctly converts decimal values to degrees 
        and that the results are accurately stored as Decimal instances.

        """
        DecimalModel.objects.create(n1=Decimal("-12.9"), n2=Decimal("0.6"))
        obj = DecimalModel.objects.annotate(
            n1_degrees=Degrees("n1"), n2_degrees=Degrees("n2")
        ).first()
        self.assertIsInstance(obj.n1_degrees, Decimal)
        self.assertIsInstance(obj.n2_degrees, Decimal)
        self.assertAlmostEqual(obj.n1_degrees, Decimal(math.degrees(obj.n1)))
        self.assertAlmostEqual(obj.n2_degrees, Decimal(math.degrees(obj.n2)))

    def test_float(self):
        """

        Tests the functionality of converting floating point numbers to degrees.

        This test case creates a FloatModel instance with sample float values, 
        then annotates the model to convert these values to degrees. It verifies
        that the converted values are of float type and match the expected results
        calculated using the math.degrees function. The test ensures accurate 
        conversion of float values to degrees.

        """
        FloatModel.objects.create(f1=-27.5, f2=0.33)
        obj = FloatModel.objects.annotate(
            f1_degrees=Degrees("f1"), f2_degrees=Degrees("f2")
        ).first()
        self.assertIsInstance(obj.f1_degrees, float)
        self.assertIsInstance(obj.f2_degrees, float)
        self.assertAlmostEqual(obj.f1_degrees, math.degrees(obj.f1))
        self.assertAlmostEqual(obj.f2_degrees, math.degrees(obj.f2))

    def test_integer(self):
        """
        Tests the conversion of integer fields to degrees using the Degrees database function.

        This test creates an instance of IntegerModel with different integer values and annotates
        the instance with their corresponding degrees. It then verifies that the degrees are calculated
        correctly and are of the expected data type (float). The test checks for both positive and negative
        integer values to ensure the conversion works as expected in all cases.
        """
        IntegerModel.objects.create(small=-20, normal=15, big=-1)
        obj = IntegerModel.objects.annotate(
            small_degrees=Degrees("small"),
            normal_degrees=Degrees("normal"),
            big_degrees=Degrees("big"),
        ).first()
        self.assertIsInstance(obj.small_degrees, float)
        self.assertIsInstance(obj.normal_degrees, float)
        self.assertIsInstance(obj.big_degrees, float)
        self.assertAlmostEqual(obj.small_degrees, math.degrees(obj.small))
        self.assertAlmostEqual(obj.normal_degrees, math.degrees(obj.normal))
        self.assertAlmostEqual(obj.big_degrees, math.degrees(obj.big))

    def test_transform(self):
        """

        Tests the transformation of decimal values to degrees.

        This test ensures that decimal values can be correctly filtered based on their degree values.
        It creates test data with decimal values, transforms them to degrees, and then tests that the
        correct object is retrieved when filtering by degree values.

        The test scenario includes both positive and negative decimal values to cover different cases.

        """
        with register_lookup(DecimalField, Degrees):
            DecimalModel.objects.create(n1=Decimal("5.4"), n2=Decimal("0"))
            DecimalModel.objects.create(n1=Decimal("-30"), n2=Decimal("0"))
            obj = DecimalModel.objects.filter(n1__degrees__gt=0).get()
            self.assertEqual(obj.n1, Decimal("5.4"))
