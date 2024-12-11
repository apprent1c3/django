import math
from decimal import Decimal

from django.db.models import DecimalField
from django.db.models.functions import ASin
from django.test import TestCase
from django.test.utils import register_lookup

from ..models import DecimalModel, FloatModel, IntegerModel


class ASinTests(TestCase):
    def test_null(self):
        """
        Tests that the ASin function correctly handles null or zero input values.

        This test case creates an instance of the IntegerModel, annotates it with the ASin of the 'normal' field, 
        and then asserts that the result is None, as expected when the input to the ASin function is zero or null.
        """
        IntegerModel.objects.create()
        obj = IntegerModel.objects.annotate(null_asin=ASin("normal")).first()
        self.assertIsNone(obj.null_asin)

    def test_decimal(self):
        """

        Checks the functionality of the ASin database function on Decimal fields.

        Tests whether the ASin function correctly calculates the arc sine of Decimal values
        and returns the result as a Decimal. Verifies the type of the returned values and
        checks for accuracy by comparing the results with the math.asin function.

        """
        DecimalModel.objects.create(n1=Decimal("0.9"), n2=Decimal("0.6"))
        obj = DecimalModel.objects.annotate(
            n1_asin=ASin("n1"), n2_asin=ASin("n2")
        ).first()
        self.assertIsInstance(obj.n1_asin, Decimal)
        self.assertIsInstance(obj.n2_asin, Decimal)
        self.assertAlmostEqual(obj.n1_asin, Decimal(math.asin(obj.n1)))
        self.assertAlmostEqual(obj.n2_asin, Decimal(math.asin(obj.n2)))

    def test_float(self):
        """

        Tests the calculation of the arcsine (ASin) of float fields in the FloatModel.

        This test creates a FloatModel instance with two float fields, calculates the arcsine
        of these fields using the ASin database function, and verifies that the results are
        correct and have the expected data type.

        The test checks that the arcsine calculations for both fields match the results of
        the math.asin function, ensuring that the database function behaves as expected.

        """
        FloatModel.objects.create(f1=-0.5, f2=0.87)
        obj = FloatModel.objects.annotate(
            f1_asin=ASin("f1"), f2_asin=ASin("f2")
        ).first()
        self.assertIsInstance(obj.f1_asin, float)
        self.assertIsInstance(obj.f2_asin, float)
        self.assertAlmostEqual(obj.f1_asin, math.asin(obj.f1))
        self.assertAlmostEqual(obj.f2_asin, math.asin(obj.f2))

    def test_integer(self):
        IntegerModel.objects.create(small=0, normal=1, big=-1)
        obj = IntegerModel.objects.annotate(
            small_asin=ASin("small"),
            normal_asin=ASin("normal"),
            big_asin=ASin("big"),
        ).first()
        self.assertIsInstance(obj.small_asin, float)
        self.assertIsInstance(obj.normal_asin, float)
        self.assertIsInstance(obj.big_asin, float)
        self.assertAlmostEqual(obj.small_asin, math.asin(obj.small))
        self.assertAlmostEqual(obj.normal_asin, math.asin(obj.normal))
        self.assertAlmostEqual(obj.big_asin, math.asin(obj.big))

    def test_transform(self):
        """
        Tests the transformation of decimal fields using the ASin lookup function.

        This test creates instances of DecimalModel with different decimal values, 
        then filters the objects based on the inverse sine of the 'n1' field and 
        verifies that the result matches the expected value. 

        The test ensures that the ASin lookup function is correctly applied to 
        decimal fields and returns the expected results when used in queries.
        """
        with register_lookup(DecimalField, ASin):
            DecimalModel.objects.create(n1=Decimal("0.1"), n2=Decimal("0"))
            DecimalModel.objects.create(n1=Decimal("1.0"), n2=Decimal("0"))
            obj = DecimalModel.objects.filter(n1__asin__gt=1).get()
            self.assertEqual(obj.n1, Decimal("1.0"))
