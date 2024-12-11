import math

from django.db.models.functions import Pi
from django.test import TestCase

from ..models import FloatModel


class PiTests(TestCase):
    def test(self):
        """

        Tests the calculation of Pi in the FloatModel.

        Verifies that the Pi value calculated using the Pi database function is a float and 
        approximates the actual value of Pi to 5 decimal places.

        Checks that the annotation of the Pi value to a FloatModel object instance is correct,
        ensuring the successful integration of the Pi database function with the model.

        """
        FloatModel.objects.create(f1=2.5, f2=15.9)
        obj = FloatModel.objects.annotate(pi=Pi()).first()
        self.assertIsInstance(obj.pi, float)
        self.assertAlmostEqual(obj.pi, math.pi, places=5)
