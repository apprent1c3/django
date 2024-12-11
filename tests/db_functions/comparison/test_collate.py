from django.db import connection
from django.db.models import F, Value
from django.db.models.functions import Collate
from django.test import TestCase

from ..models import Author


class CollateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """

        Sets up initial test data for the class.

        This method is called once to create a set of static test data that can be used across all tests in the class.
        It creates two test authors with distinct aliases and names, which can be used as a basis for subsequent tests.

        """
        cls.author1 = Author.objects.create(alias="a", name="Jones 1")
        cls.author2 = Author.objects.create(alias="A", name="Jones 2")

    def test_collate_filter_ci(self):
        collation = connection.features.test_collations.get("ci")
        if not collation:
            self.skipTest("This backend does not support case-insensitive collations.")
        qs = Author.objects.filter(alias=Collate(Value("a"), collation))
        self.assertEqual(qs.count(), 2)

    def test_collate_order_by_cs(self):
        """
        Tests the database's collation support by ordering query results using a case-sensitive collation.

        If the database backend does not support case-sensitive collations, the test is skipped.

        The test verifies that the records are ordered as expected, with the case-sensitive collation applied to the 'alias' field.
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
        *)).. function:: test_invalid_collation

            Tests that invalid collation names raise a :class:`ValueError`.

            Verifies that passing a variety of invalid collation names to the :class:`Collate` function
            results in a :class:`ValueError` with a message indicating the invalid collation name.

            The test cases include passing :data:`None`, an empty string, and strings that are syntactically
            invalid or contain SQL injection attempts.
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
