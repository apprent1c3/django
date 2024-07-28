from django.db import connection
from django.db.models import Max
from django.test import TestCase

from .models import Cash, CashModel


class FromDBValueTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        This is a comment
        """
        CashModel.objects.create(cash="12.50")

    def test_simple_load(self):
        """
        This is a comment
        """
        instance = CashModel.objects.get()
        self.assertIsInstance(instance.cash, Cash)

    def test_values_list(self):
        """
        This is a comment
        """
        values_list = CashModel.objects.values_list("cash", flat=True)
        self.assertIsInstance(values_list[0], Cash)

    def test_values(self):
        """
        This is a comment
        """
        values = CashModel.objects.values("cash")
        self.assertIsInstance(values[0]["cash"], Cash)

    def test_aggregation(self):
        """
        This is a comment
        """
        maximum = CashModel.objects.aggregate(m=Max("cash"))["m"]
        self.assertIsInstance(maximum, Cash)

    def test_defer(self):
        """
        This is a comment
        """
        instance = CashModel.objects.defer("cash").get()
        self.assertIsInstance(instance.cash, Cash)

    def test_connection(self):
        """
        This is a comment
        """
        instance = CashModel.objects.get()
        self.assertEqual(instance.cash.vendor, connection.vendor)
