from django.db.models.functions import Random
from django.test import TestCase

from ..models import FloatModel


class RandomTests(TestCase):
    def test(self):
        """
        Tests that a random float value between 0 and 1 is correctly generated and annotated to a model instance.
        """
        FloatModel.objects.create()
        obj = FloatModel.objects.annotate(random=Random()).first()
        self.assertIsInstance(obj.random, float)
        self.assertGreaterEqual(obj.random, 0)
        self.assertLess(obj.random, 1)
