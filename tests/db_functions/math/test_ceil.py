import math
from decimal import Decimal

from django.db.models import DecimalField
from django.db.models.functions import Ceil
from django.test import TestCase
from django.test.utils import register_lookup

from ..models import DecimalModel, FloatModel, IntegerModel


class CeilTests(TestCase):
    def test_null(self):
        """

        Tests the behavior of the Ceil function when applied to a null value.

        Verifies that when the Ceil function is used to annotate a model instance with a null value,
        the resulting annotated field is also null.

        """
        IntegerModel.objects.create()
        obj = IntegerModel.objects.annotate(null_ceil=Ceil("normal")).first()
        self.assertIsNone(obj.null_ceil)

    def test_decimal(self):
        """
        Tests the usage of the Ceil annotation with decimal fields.

        Verifies that the Ceil annotation correctly calculates the ceiling of decimal values 
        and returns the result as a Decimal instance. The function checks the data type 
        and the accuracy of the calculated values for two decimal fields.

        This test case ensures that the Ceil annotation works as expected with decimal 
        fields in the DecimalModel, which is essential for maintaining data consistency 
        and accuracy in mathematical operations.

        The test creates a DecimalModel instance with decimal values, applies the Ceil 
        annotation, and then validates the output. It confirms that the annotation 
        produces the expected results, which is crucial for applications relying on 
        precise decimal calculations.
        """
        DecimalModel.objects.create(n1=Decimal("12.9"), n2=Decimal("0.6"))
        obj = DecimalModel.objects.annotate(
            n1_ceil=Ceil("n1"), n2_ceil=Ceil("n2")
        ).first()
        self.assertIsInstance(obj.n1_ceil, Decimal)
        self.assertIsInstance(obj.n2_ceil, Decimal)
        self.assertEqual(obj.n1_ceil, Decimal(math.ceil(obj.n1)))
        self.assertEqual(obj.n2_ceil, Decimal(math.ceil(obj.n2)))

    def test_float(self):
        """

        Tests the ceiling function on float fields.

        Verifies that the Celil function correctly calculates the ceiling of float values
        in the database and returns the result as a float.

        The test creates a FloatModel instance with float values, annotates the model with
        the Celil function, and then checks the type and value of the annotated fields.

        """
        FloatModel.objects.create(f1=-12.5, f2=21.33)
        obj = FloatModel.objects.annotate(
            f1_ceil=Ceil("f1"), f2_ceil=Ceil("f2")
        ).first()
        self.assertIsInstance(obj.f1_ceil, float)
        self.assertIsInstance(obj.f2_ceil, float)
        self.assertEqual(obj.f1_ceil, math.ceil(obj.f1))
        self.assertEqual(obj.f2_ceil, math.ceil(obj.f2))

    def test_integer(self):
        IntegerModel.objects.create(small=-11, normal=0, big=-100)
        obj = IntegerModel.objects.annotate(
            small_ceil=Ceil("small"),
            normal_ceil=Ceil("normal"),
            big_ceil=Ceil("big"),
        ).first()
        self.assertIsInstance(obj.small_ceil, int)
        self.assertIsInstance(obj.normal_ceil, int)
        self.assertIsInstance(obj.big_ceil, int)
        self.assertEqual(obj.small_ceil, math.ceil(obj.small))
        self.assertEqual(obj.normal_ceil, math.ceil(obj.normal))
        self.assertEqual(obj.big_ceil, math.ceil(obj.big))

    def test_transform(self):
        """

        Tests the transformation of DecimalField using the Ceil lookup.

        This test verifies that the Ceil lookup function correctly rounds up Decimal values.
        It creates test data with Decimal fields, applies the Ceil lookup to filter the data,
        and asserts that the expected result is returned.

        The test case covers the scenario where the Ceil lookup is used to filter Decimal values
        greater than a specified threshold, ensuring that the correct object is retrieved.

        """
        with register_lookup(DecimalField, Ceil):
            DecimalModel.objects.create(n1=Decimal("3.12"), n2=Decimal("0"))
            DecimalModel.objects.create(n1=Decimal("1.25"), n2=Decimal("0"))
            obj = DecimalModel.objects.filter(n1__ceil__gt=3).get()
            self.assertEqual(obj.n1, Decimal("3.12"))
