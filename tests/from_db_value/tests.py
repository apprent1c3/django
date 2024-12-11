from django.db import connection
from django.db.models import Max
from django.test import TestCase

from .models import Cash, CashModel


class FromDBValueTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        CashModel.objects.create(cash="12.50")

    def test_simple_load(self):
        """

        Tests that loading a CashModel instance results in a Cash object being correctly associated with it.

        This tests the basic functionality of loading a CashModel instance from the database and
        verifies that the 'cash' attribute of the instance is an instance of the Cash class.

        """
        instance = CashModel.objects.get()
        self.assertIsInstance(instance.cash, Cash)

    def test_values_list(self):
        values_list = CashModel.objects.values_list("cash", flat=True)
        self.assertIsInstance(values_list[0], Cash)

    def test_values(self):
        """
        Tests that the values retrieved from the CashModel database query are instances of the Cash class.

        This function verifies that the 'cash' field in the retrieved objects is of the expected type, ensuring data consistency and validity. It is used for quality assurance and debugging purposes, helping to catch potential errors or inconsistencies in the data.
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
        Tests whether the vendor of the retrieved CashModel instance matches the expected vendor from the connection.

        Verifies that the data fetched from the database contains the correct vendor information, ensuring a successful connection to the data source.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the vendor of the CashModel instance does not match the connection vendor
        """
        instance = CashModel.objects.get()
        self.assertEqual(instance.cash.vendor, connection.vendor)
