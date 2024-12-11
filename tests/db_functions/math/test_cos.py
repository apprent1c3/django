import math
from decimal import Decimal

from django.db.models import DecimalField
from django.db.models.functions import Cos
from django.test import TestCase
from django.test.utils import register_lookup

from ..models import DecimalModel, FloatModel, IntegerModel


class CosTests(TestCase):
    def test_null(self):
        """
        ..:param: None
        :raises: AssertionError
        :return: None
        :rtype: None

        Tests the calculation of the cosine of a value where it results in null (None). This function verifies that the cosine of 'normal' is correctly annotated as None in the database query. It ensures the integrity of the mathematical operation under specific conditions, confirming that the result is null when expected.
        """
        IntegerModel.objects.create()
        obj = IntegerModel.objects.annotate(null_cos=Cos("normal")).first()
        self.assertIsNone(obj.null_cos)

    def test_decimal(self):
        """

        Test the annotation of Decimal fields with cosine calculation.

        This test case verifies that the cosine of Decimal field values can be correctly 
        calculated and annotated on a model instance. It creates an instance of DecimalModel 
        with predefined decimal values, annotates the instance with cosine calculations, 
        and then checks the types and accuracy of the annotated values.

        The test ensures that the annotated cosine values are of Decimal type and their 
        numerical values closely match the expected cosine results, validating the 
        correctness of the annotation logic.

        """
        DecimalModel.objects.create(n1=Decimal("-12.9"), n2=Decimal("0.6"))
        obj = DecimalModel.objects.annotate(n1_cos=Cos("n1"), n2_cos=Cos("n2")).first()
        self.assertIsInstance(obj.n1_cos, Decimal)
        self.assertIsInstance(obj.n2_cos, Decimal)
        self.assertAlmostEqual(obj.n1_cos, Decimal(math.cos(obj.n1)))
        self.assertAlmostEqual(obj.n2_cos, Decimal(math.cos(obj.n2)))

    def test_float(self):
        FloatModel.objects.create(f1=-27.5, f2=0.33)
        obj = FloatModel.objects.annotate(f1_cos=Cos("f1"), f2_cos=Cos("f2")).first()
        self.assertIsInstance(obj.f1_cos, float)
        self.assertIsInstance(obj.f2_cos, float)
        self.assertAlmostEqual(obj.f1_cos, math.cos(obj.f1))
        self.assertAlmostEqual(obj.f2_cos, math.cos(obj.f2))

    def test_integer(self):
        IntegerModel.objects.create(small=-20, normal=15, big=-1)
        obj = IntegerModel.objects.annotate(
            small_cos=Cos("small"),
            normal_cos=Cos("normal"),
            big_cos=Cos("big"),
        ).first()
        self.assertIsInstance(obj.small_cos, float)
        self.assertIsInstance(obj.normal_cos, float)
        self.assertIsInstance(obj.big_cos, float)
        self.assertAlmostEqual(obj.small_cos, math.cos(obj.small))
        self.assertAlmostEqual(obj.normal_cos, math.cos(obj.normal))
        self.assertAlmostEqual(obj.big_cos, math.cos(obj.big))

    def test_transform(self):
        """

        Tests the transformation of decimal fields using the cosine function.

        Ensures that the cosine lookup is correctly applied to decimal fields,
        allowing filtering of objects based on the cosine of a decimal value.

        Verifies that the transformation is correctly applied by checking if an object
        with a decimal value of -8.0 has a cosine greater than -0.2, which should be true.

        """
        with register_lookup(DecimalField, Cos):
            DecimalModel.objects.create(n1=Decimal("-8.0"), n2=Decimal("0"))
            DecimalModel.objects.create(n1=Decimal("3.14"), n2=Decimal("0"))
            obj = DecimalModel.objects.filter(n1__cos__gt=-0.2).get()
            self.assertEqual(obj.n1, Decimal("-8.0"))
