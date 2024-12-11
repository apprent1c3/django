from django.db.models import Q
from django.test import TestCase

from .models import Number


class XorLookupsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.numbers = [Number.objects.create(num=i) for i in range(10)]

    def test_filter(self):
        self.assertCountEqual(
            Number.objects.filter(num__lte=7) ^ Number.objects.filter(num__gte=3),
            self.numbers[:3] + self.numbers[8:],
        )
        self.assertCountEqual(
            Number.objects.filter(Q(num__lte=7) ^ Q(num__gte=3)),
            self.numbers[:3] + self.numbers[8:],
        )

    def test_filter_multiple(self):
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

        Tests the filtering of Number objects using negated Q objects and XOR operations.

        This test case verifies the correctness of filtering Number objects based on various
        conditions, including negated Q objects and XOR operations between them.
        The tested conditions include filtering numbers less than or equal to 7 and not less
        than 3, numbers not greater than 7 and not less than 3, and combinations of these
        conditions with additional filtering criteria.

        The tests ensure that the filtering produces the expected results, including the
        correct exclusion and inclusion of Number objects based on the specified conditions.

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
