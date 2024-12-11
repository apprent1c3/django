from django.db import connection
from django.db.models import F, Value
from django.db.models.functions import Collate
from django.test import TestCase

from ..models import Author


class CollateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for the class, creating two authors with unique aliases and names for use in subsequent tests.
        """
        cls.author1 = Author.objects.create(alias="a", name="Jones 1")
        cls.author2 = Author.objects.create(alias="A", name="Jones 2")

    def test_collate_filter_ci(self):
        """

        Tests the filtering of database query results using case-insensitive collation.

        This test case verifies that the database backend supports case-insensitive collations and 
        that the filtering of query results using the :func:`Collate` function works as expected.

        The test checks that the number of results returned by the query matches the expected count, 
        demonstrating the correct application of the case-insensitive collation.

        """
        collation = connection.features.test_collations.get("ci")
        if not collation:
            self.skipTest("This backend does not support case-insensitive collations.")
        qs = Author.objects.filter(alias=Collate(Value("a"), collation))
        self.assertEqual(qs.count(), 2)

    def test_collate_order_by_cs(self):
        """
        Tests the ordering of querysets using case-sensitive collation.

        Checks if the database backend supports case-sensitive collations. If supported,
        it verifies that the Author objects are ordered correctly based on their 'alias'
        field, using the case-sensitive collation 'cs'. The expected order is with the
        lowercase alias first, followed by the uppercase one.
        """
        collation = connection.features.test_collations.get("cs")
        if not collation:
            self.skipTest("This backend does not support case-sensitive collations.")
        qs = Author.objects.order_by(Collate("alias", collation))
        self.assertSequenceEqual(qs, [self.author2, self.author1])

    def test_language_collation_order_by(self):
        collation = connection.features.test_collations.get("swedish_ci")
        if not collation:
            self.skipTest("This backend does not support language collations.")
        author3 = Author.objects.create(alias="O", name="Jones")
        author4 = Author.objects.create(alias="Ö", name="Jones")
        author5 = Author.objects.create(alias="P", name="Jones")
        qs = Author.objects.order_by(Collate(F("alias"), collation), "name")
        self.assertSequenceEqual(
            qs,
            [self.author1, self.author2, author3, author5, author4],
        )

    def test_invalid_collation(self):
        """
        Tests that creating a `Collate` object with an invalid collation name raises a `ValueError` with the expected error message. The function covers various invalid collation name scenarios, including empty or malformed strings.
        """
        tests = [
            None,
            "",
            'et-x-icu" OR ',
            '"schema"."collation"',
        ]
        msg = "Invalid collation name: %r."
        for value in tests:
            with self.subTest(value), self.assertRaisesMessage(ValueError, msg % value):
                Collate(F("alias"), value)
