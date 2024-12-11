from django.db.models import F, Sum
from django.test import TestCase

from .models import Product, Stock


class DecimalFieldLookupTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """

        Sets up test data for the class, creating products with associated stock quantities.

            Creates three products, each with two stock entries, allowing for testing of various scenarios.
            Saves the created products as class attributes (p1, p2, p3) for use in tests.
            Additionally, creates a queryset of products with annotated fields for the total available quantity and the quantity needed to meet the target.

        """
        cls.p1 = Product.objects.create(name="Product1", qty_target=10)
        Stock.objects.create(product=cls.p1, qty_available=5)
        Stock.objects.create(product=cls.p1, qty_available=6)
        cls.p2 = Product.objects.create(name="Product2", qty_target=10)
        Stock.objects.create(product=cls.p2, qty_available=5)
        Stock.objects.create(product=cls.p2, qty_available=5)
        cls.p3 = Product.objects.create(name="Product3", qty_target=10)
        Stock.objects.create(product=cls.p3, qty_available=5)
        Stock.objects.create(product=cls.p3, qty_available=4)
        cls.queryset = Product.objects.annotate(
            qty_available_sum=Sum("stock__qty_available"),
        ).annotate(qty_needed=F("qty_target") - F("qty_available_sum"))

    def test_gt(self):
        qs = self.queryset.filter(qty_needed__gt=0)
        self.assertCountEqual(qs, [self.p3])

    def test_gte(self):
        """
        Tests that the queryset correctly filters products where the quantity needed is greater than or equal to 0.

        This test case verifies that the filtered queryset contains the expected products, ensuring the filtering logic is accurate and reliable.

        :note: This test assumes the presence of a queryset and specific products (p2, p3) in the test setup, which are used to validate the filtering result.
        """
        qs = self.queryset.filter(qty_needed__gte=0)
        self.assertCountEqual(qs, [self.p2, self.p3])

    def test_lt(self):
        """

        Tests that the queryset returns the expected results when filtering by quantities less than 0.

        The test verifies that only the instances with a quantity needed less than 0 are included in the filtered queryset.

        """
        qs = self.queryset.filter(qty_needed__lt=0)
        self.assertCountEqual(qs, [self.p1])

    def test_lte(self):
        """
        Tests that the queryset returns projects where the quantity needed is less than or equal to zero.

            Verifies that the correct projects are retrieved from the database when filtering
            by quantity needed. The test case checks if the retrieved projects match the
            expected projects, ensuring the queryset filter is working as expected.
        """
        qs = self.queryset.filter(qty_needed__lte=0)
        self.assertCountEqual(qs, [self.p1, self.p2])
