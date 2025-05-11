from django.db import connection
from django.db.models import F, Value
from django.db.models.functions import Collate
from django.test import TestCase

from ..models import Author


class CollateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author1 = Author.objects.create(alias="a", name="Jones 1")
        cls.author2 = Author.objects.create(alias="A", name="Jones 2")

    def test_collate_filter_ci(self):
        """
        Tests the case-insensitive filter in a database query using a collation, verifying that it correctly returns results regardless of the case of the filtered value.
        """
        collation = connection.features.test_collations.get("ci")
        if not collation:
            self.skipTest("This backend does not support case-insensitive collations.")
        qs = Author.objects.filter(alias=Collate(Value("a"), collation))
        self.assertEqual(qs.count(), 2)

    def test_collate_order_by_cs(self):
        """
        Tests the collation order of a query set using a case-sensitive collation.
        """
        collation = connection.features.test_collations.get("cs")
        if not collation:
            self.skipTest("This backend does not support case-sensitive collations.")
        qs = Author.objects.order_by(Collate("alias", collation))
        self.assertSequenceEqual(qs, [self.author2, self.author1])

    def test_language_collation_order_by(self):
        """
        Test ordering of Author objects using language-specific collation rules.

        This test verifies that authors are ordered correctly based on their alias, 
        taking into account language-specific character ordering, such as umlauts and accents.
        """
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
        Tests that invalid collation names raise a ValueError with a descriptive error message.
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
