from django.db.models import Q
from django.test import TestCase

from .models import Number


class XorLookupsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.numbers = [Number.objects.create(num=i) for i in range(10)]

    def test_filter(self):
        """
        Tests the filter functionality with XOR operator.

        This function checks that the filter operation using the XOR operator (^) returns the correct results.
        It compares the result of filtering numbers less than or equal to 7 and numbers greater than or equal to 3,
        excluding the overlap between the two sets, with the expected set of numbers.
        The test is performed using both the regular XOR operator and the Q object XOR operation, ensuring consistency between the two methods.
        The expected result is the union of numbers less than 3 and numbers greater than 7, which is compared to the actual result using assertCountEqual.
        """
        self.assertCountEqual(
            Number.objects.filter(num__lte=7) ^ Number.objects.filter(num__gte=3),
            self.numbers[:3] + self.numbers[8:],
        )
        self.assertCountEqual(
            Number.objects.filter(Q(num__lte=7) ^ Q(num__gte=3)),
            self.numbers[:3] + self.numbers[8:],
        )

    def test_filter_multiple(self):
        """

        Tests the ability to filter a queryset using multiple XOR conditions.

        Verifies that a queryset filtered by a combination of XOR conditions returns the expected results, 
        specifically objects where the number matches at least one, but not all of the conditions.

        The test case checks the count and values of the filtered objects against the expected output 
        to ensure the correct application of the XOR operation.

        """
        qs = Number.objects.filter(
            Q(num__gte=1)
            ^ Q(num__gte=3)
            ^ Q(num__gte=5)
            ^ Q(num__gte=7)
            ^ Q(num__gte=9)
        )
        self.assertCountEqual(
            qs,
            self.numbers[1:3] + self.numbers[5:7] + self.numbers[9:],
        )
        self.assertCountEqual(
            qs.values_list("num", flat=True),
            [
                i
                for i in range(10)
                if (i >= 1) ^ (i >= 3) ^ (i >= 5) ^ (i >= 7) ^ (i >= 9)
            ],
        )

    def test_filter_negated(self):
        """
        Tests the filter functionality with negated queries.

        Verifies that the filter method correctly handles the XOR (^) operator 
        and negation (~) of query objects, ensuring that the resulting 
        database query returns the expected set of objects.

        The function checks various filter scenarios, including the combination 
        of less-than-or-equal-to and less-than conditions, as well as the 
        negation of these conditions. The expected results are compared to 
        the actual query results using assertCountEqual, ensuring that the 
        filter method behaves as expected in different edge cases.

        The test cases cover the following scenarios:

        * Filtering with a single XOR condition
        * Filtering with multiple XOR conditions
        * Filtering with a negated XOR condition

        The goal of these tests is to ensure that the filter method correctly 
        handles complex query logic and returns the expected results.
        """
        self.assertCountEqual(
            Number.objects.filter(Q(num__lte=7) ^ ~Q(num__lt=3)),
            self.numbers[:3] + self.numbers[8:],
        )
        self.assertCountEqual(
            Number.objects.filter(~Q(num__gt=7) ^ ~Q(num__lt=3)),
            self.numbers[:3] + self.numbers[8:],
        )
        self.assertCountEqual(
            Number.objects.filter(Q(num__lte=7) ^ ~Q(num__lt=3) ^ Q(num__lte=1)),
            [self.numbers[2]] + self.numbers[8:],
        )
        self.assertCountEqual(
            Number.objects.filter(~(Q(num__lte=7) ^ ~Q(num__lt=3) ^ Q(num__lte=1))),
            self.numbers[:2] + self.numbers[3:8],
        )

    def test_exclude(self):
        self.assertCountEqual(
            Number.objects.exclude(Q(num__lte=7) ^ Q(num__gte=3)),
            self.numbers[3:8],
        )

    def test_stages(self):
        """
        Tests the filter functionality of Number objects across different stages.

        This function checks if the filtered results for numbers greater than or equal to 0 and less than or equal to 11 are identical, 
        and if the filtered results for numbers greater than 0 and less than 11 only returns the first Number object.

        In essence, it ensures that the filters are correctly applied to the Number objects based on the given conditions.

        Checks include:
        - A symmetric difference between numbers greater than or equal to 0 and less than or equal to 11 is empty.
        - A symmetric difference between numbers greater than 0 and less than 11 returns the first Number object.

        The function uses Django's built-in ORM filtering and assertion methods to validate the expected behavior of these filters.
        """
        numbers = Number.objects.all()
        self.assertSequenceEqual(
            numbers.filter(num__gte=0) ^ numbers.filter(num__lte=11),
            [],
        )
        self.assertSequenceEqual(
            numbers.filter(num__gt=0) ^ numbers.filter(num__lt=11),
            [self.numbers[0]],
        )

    def test_pk_q(self):
        self.assertCountEqual(
            Number.objects.filter(Q(pk=self.numbers[0].pk) ^ Q(pk=self.numbers[1].pk)),
            self.numbers[:2],
        )

    def test_empty_in(self):
        self.assertCountEqual(
            Number.objects.filter(Q(pk__in=[]) ^ Q(num__gte=5)),
            self.numbers[5:],
        )
