import math
from decimal import Decimal

from django.db.models import DecimalField
from django.db.models.functions import ATan
from django.test import TestCase
from django.test.utils import register_lookup

from ..models import DecimalModel, FloatModel, IntegerModel


class ATanTests(TestCase):
    def test_null(self):
        """

        Tests the behavior of the ATan function when applied to a null value.

        Verifies that the result of the ATan function is None when the input is null,
        ensuring proper handling of missing or undefined values.

        The test case creates an instance of IntegerModel and annotates it with the
        ATan function, then asserts that the resulting value is None.

        """
        IntegerModel.objects.create()
        obj = IntegerModel.objects.annotate(null_atan=ATan("normal")).first()
        self.assertIsNone(obj.null_atan)

    def test_decimal(self):
        """

        Tests the calculation of arctangent for decimal fields.

        This function verifies that the arctangent (ATan) operation can be applied to decimal fields,
        and that the result is a decimal value. It checks the type of the result and compares it to the
        expected value calculated using the math.atan function.

        The test covers two decimal fields with different values, ensuring the functionality works
        correctly for various inputs.

        """
        DecimalModel.objects.create(n1=Decimal("-12.9"), n2=Decimal("0.6"))
        obj = DecimalModel.objects.annotate(
            n1_atan=ATan("n1"), n2_atan=ATan("n2")
        ).first()
        self.assertIsInstance(obj.n1_atan, Decimal)
        self.assertIsInstance(obj.n2_atan, Decimal)
        self.assertAlmostEqual(obj.n1_atan, Decimal(math.atan(obj.n1)))
        self.assertAlmostEqual(obj.n2_atan, Decimal(math.atan(obj.n2)))

    def test_float(self):
        FloatModel.objects.create(f1=-27.5, f2=0.33)
        obj = FloatModel.objects.annotate(
            f1_atan=ATan("f1"), f2_atan=ATan("f2")
        ).first()
        self.assertIsInstance(obj.f1_atan, float)
        self.assertIsInstance(obj.f2_atan, float)
        self.assertAlmostEqual(obj.f1_atan, math.atan(obj.f1))
        self.assertAlmostEqual(obj.f2_atan, math.atan(obj.f2))

    def test_integer(self):
        """
        Tests the functionality of the ATan database function with integer values.

        Verifies that applying the ATan function to integer fields in a model instance
        results in floating point numbers, and checks their accuracy against the
        -equivalent results from the math.atan function.

        Checks the ATan function's behavior with both negative and positive integer
        inputs, ensuring its correctness across different numerical ranges.
        """
        IntegerModel.objects.create(small=-20, normal=15, big=-1)
        obj = IntegerModel.objects.annotate(
            small_atan=ATan("small"),
            normal_atan=ATan("normal"),
            big_atan=ATan("big"),
        ).first()
        self.assertIsInstance(obj.small_atan, float)
        self.assertIsInstance(obj.normal_atan, float)
        self.assertIsInstance(obj.big_atan, float)
        self.assertAlmostEqual(obj.small_atan, math.atan(obj.small))
        self.assertAlmostEqual(obj.normal_atan, math.atan(obj.normal))
        self.assertAlmostEqual(obj.big_atan, math.atan(obj.big))

    def test_transform(self):
        """

        Tests the transformation of decimal fields using the ATan function.

        This function creates two DecimalModel objects with different values, 
        then applies a filter to retrieve the object where the arctangent of the n1 field is greater than 0.
        It verifies that the retrieved object is the one with n1 value equal to 3.12, 
        thus validating the correctness of the ATan transformation.

        The test relies on registering a lookup for DecimalField with the ATan function,
        which allows the use of the atan filter in the query.

        """
        with register_lookup(DecimalField, ATan):
            DecimalModel.objects.create(n1=Decimal("3.12"), n2=Decimal("0"))
            DecimalModel.objects.create(n1=Decimal("-5"), n2=Decimal("0"))
            obj = DecimalModel.objects.filter(n1__atan__gt=0).get()
            self.assertEqual(obj.n1, Decimal("3.12"))
