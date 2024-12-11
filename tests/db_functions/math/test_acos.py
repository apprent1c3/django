import math
from decimal import Decimal

from django.db.models import DecimalField
from django.db.models.functions import ACos
from django.test import TestCase
from django.test.utils import register_lookup

from ..models import DecimalModel, FloatModel, IntegerModel


class ACosTests(TestCase):
    def test_null(self):
        """
        Tests the behavior of the ACos function when applied to a null value.

        This test case verifies that the ACos function correctly handles null input by
        checking if the result is None. It creates an instance of IntegerModel, annotates
        it with the ACos of the 'normal' field, and asserts that the result is None when
        the input is null.

        Returns:
            None

        Raises:
            AssertionError: If the result of the ACos function is not None for null input
        """
        IntegerModel.objects.create()
        obj = IntegerModel.objects.annotate(null_acos=ACos("normal")).first()
        self.assertIsNone(obj.null_acos)

    def test_decimal(self):
        """

        Tests the usage of the ACos function with Decimal values.

        This function verifies that the ACos database function correctly handles Decimal 
        inputs and returns accurate results as Decimal instances. It checks the type and 
        value of the results to ensure they match the expected output from the math.acos 
        function.

        """
        DecimalModel.objects.create(n1=Decimal("-0.9"), n2=Decimal("0.6"))
        obj = DecimalModel.objects.annotate(
            n1_acos=ACos("n1"), n2_acos=ACos("n2")
        ).first()
        self.assertIsInstance(obj.n1_acos, Decimal)
        self.assertIsInstance(obj.n2_acos, Decimal)
        self.assertAlmostEqual(obj.n1_acos, Decimal(math.acos(obj.n1)))
        self.assertAlmostEqual(obj.n2_acos, Decimal(math.acos(obj.n2)))

    def test_float(self):
        """

        Tests the calculation of the inverse cosine (arccos) of float fields in the database.

        Verifies that the arccos values are correctly calculated and returned as float instances.
        The test covers both positive and negative input values to ensure the function's accuracy.

        It checks the calculated arccos values against the expected results from the math library to ensure precision.

        """
        FloatModel.objects.create(f1=-0.5, f2=0.33)
        obj = FloatModel.objects.annotate(
            f1_acos=ACos("f1"), f2_acos=ACos("f2")
        ).first()
        self.assertIsInstance(obj.f1_acos, float)
        self.assertIsInstance(obj.f2_acos, float)
        self.assertAlmostEqual(obj.f1_acos, math.acos(obj.f1))
        self.assertAlmostEqual(obj.f2_acos, math.acos(obj.f2))

    def test_integer(self):
        """
        Tests the calculation of the inverse cosine (arccos) of integer fields in a database model.

        Verifies that the arccos function is applied correctly to fields containing different integer values,
        including zero, positive, and negative numbers. It checks that the result of the arccos calculation
        is a float and matches the expected value calculated using the math library.

        Ensures the correctness of the annotation functionality when used with the ACos database function
        in conjunction with integer model fields.
        """
        IntegerModel.objects.create(small=0, normal=1, big=-1)
        obj = IntegerModel.objects.annotate(
            small_acos=ACos("small"),
            normal_acos=ACos("normal"),
            big_acos=ACos("big"),
        ).first()
        self.assertIsInstance(obj.small_acos, float)
        self.assertIsInstance(obj.normal_acos, float)
        self.assertIsInstance(obj.big_acos, float)
        self.assertAlmostEqual(obj.small_acos, math.acos(obj.small))
        self.assertAlmostEqual(obj.normal_acos, math.acos(obj.normal))
        self.assertAlmostEqual(obj.big_acos, math.acos(obj.big))

    def test_transform(self):
        """

        Tests the transformation of decimal fields using the ACos lookup function.

        This test case creates sample DecimalModel objects with different decimal values,
        registers the ACos lookup function for DecimalField, and then filters the objects
        using the ACos transformation. It verifies that the correct object is returned
        based on the specified condition.

        The test covers the creation of decimal objects, registration of lookup functions,
        and filtering using transformed decimal values.

        """
        with register_lookup(DecimalField, ACos):
            DecimalModel.objects.create(n1=Decimal("0.5"), n2=Decimal("0"))
            DecimalModel.objects.create(n1=Decimal("-0.9"), n2=Decimal("0"))
            obj = DecimalModel.objects.filter(n1__acos__lt=2).get()
            self.assertEqual(obj.n1, Decimal("0.5"))
