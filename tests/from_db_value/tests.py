from django.db import connection
from django.db.models import Max
from django.test import TestCase

from .models import Cash, CashModel


class FromDBValueTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        CashModel.objects.create(cash="12.50")

    def test_simple_load(self):
        instance = CashModel.objects.get()
        self.assertIsInstance(instance.cash, Cash)

    def test_values_list(self):
        values_list = CashModel.objects.values_list("cash", flat=True)
        self.assertIsInstance(values_list[0], Cash)

    def test_values(self):
        """

        Tests that the 'cash' values retrieved from the CashModel are indeed instances of Cash.

        This test case ensures data consistency by verifying that the cash values stored in the database are of the expected type, i.e., Cash objects. If the test passes, it confirms that the data is being properly serialized and deserialized, allowing for reliable operations on cash values.

        Note: This test assumes that the CashModel has at least one entry in the database.

        """
        values = CashModel.objects.values("cash")
        self.assertIsInstance(values[0]["cash"], Cash)

    def test_aggregation(self):
        maximum = CashModel.objects.aggregate(m=Max("cash"))["m"]
        self.assertIsInstance(maximum, Cash)

    def test_defer(self):
        instance = CashModel.objects.defer("cash").get()
        self.assertIsInstance(instance.cash, Cash)

    def test_connection(self):
        """

        Tests the connection by verifying that the vendor of the cash object
        matches the vendor specified in the connection settings.

        This function retrieves a CashModel instance from the database and
        compares its vendor attribute with the vendor attribute of the
        connection object, asserting that they are equal.

        """
        instance = CashModel.objects.get()
        self.assertEqual(instance.cash.vendor, connection.vendor)
