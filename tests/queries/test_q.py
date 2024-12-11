from django.core.exceptions import FieldError
from django.db.models import (
    BooleanField,
    Exists,
    ExpressionWrapper,
    F,
    OuterRef,
    Q,
    Value,
)
from django.db.models.expressions import NegatedExpression, RawSQL
from django.db.models.functions import Lower
from django.db.models.lookups import Exact, IsNull
from django.db.models.sql.where import NothingNode
from django.test import SimpleTestCase, TestCase

from .models import Tag


class QTests(SimpleTestCase):
    def test_combine_and_empty(self):
        """

         Tests the combination of query objects with an empty query, ensuring that 
         the result is the original query object, verifying the idempotent property 
         of combining with an empty query.

        """
        q = Q(x=1)
        self.assertEqual(q & Q(), q)
        self.assertEqual(Q() & q, q)

        q = Q(x__in={}.keys())
        self.assertEqual(q & Q(), q)
        self.assertEqual(Q() & q, q)

    def test_combine_and_both_empty(self):
        self.assertEqual(Q() & Q(), Q())

    def test_combine_or_empty(self):
        """

        Tests the combine operation of query objects with an empty query.

        Verifies that combining a query with an empty query using the bitwise OR operator 
        results in the original query, ensuring that the empty query has no impact on the 
        resulting query. This behavior holds true regardless of the order in which the 
        queries are combined and applies to queries with various filter conditions.

        """
        q = Q(x=1)
        self.assertEqual(q | Q(), q)
        self.assertEqual(Q() | q, q)

        q = Q(x__in={}.keys())
        self.assertEqual(q | Q(), q)
        self.assertEqual(Q() | q, q)

    def test_combine_xor_empty(self):
        q = Q(x=1)
        self.assertEqual(q ^ Q(), q)
        self.assertEqual(Q() ^ q, q)

        q = Q(x__in={}.keys())
        self.assertEqual(q ^ Q(), q)
        self.assertEqual(Q() ^ q, q)

    def test_combine_empty_copy(self):
        base_q = Q(x=1)
        tests = [
            base_q | Q(),
            Q() | base_q,
            base_q & Q(),
            Q() & base_q,
            base_q ^ Q(),
            Q() ^ base_q,
        ]
        for i, q in enumerate(tests):
            with self.subTest(i=i):
                self.assertEqual(q, base_q)
                self.assertIsNot(q, base_q)

    def test_combine_or_both_empty(self):
        self.assertEqual(Q() | Q(), Q())

    def test_combine_xor_both_empty(self):
        self.assertEqual(Q() ^ Q(), Q())

    def test_combine_not_q_object(self):
        obj = object()
        q = Q(x=1)
        with self.assertRaisesMessage(TypeError, str(obj)):
            q | obj
        with self.assertRaisesMessage(TypeError, str(obj)):
            q & obj
        with self.assertRaisesMessage(TypeError, str(obj)):
            q ^ obj

    def test_combine_negated_boolean_expression(self):
        tagged = Tag.objects.filter(category=OuterRef("pk"))
        tests = [
            Q() & ~Exists(tagged),
            Q() | ~Exists(tagged),
            Q() ^ ~Exists(tagged),
        ]
        for q in tests:
            with self.subTest(q=q):
                self.assertIsInstance(q, NegatedExpression)

    def test_deconstruct(self):
        q = Q(price__gt=F("discounted_price"))
        path, args, kwargs = q.deconstruct()
        self.assertEqual(path, "django.db.models.Q")
        self.assertEqual(args, (("price__gt", F("discounted_price")),))
        self.assertEqual(kwargs, {})

    def test_deconstruct_negated(self):
        """
        Tests the deconstruction of a negated query.

        This test case verifies that a negated query is correctly broken down into its constituent parts.
        The query in question negates the condition where the price is greater than the discounted price.
        It checks that the deconstructed query correctly captures the original query's arguments and keyword arguments, including the '_negated' flag indicating negation.
        By ensuring the correctness of this deconstruction process, this test helps validate the query's behavior and ensures it works as expected in various scenarios.
        """
        q = ~Q(price__gt=F("discounted_price"))
        path, args, kwargs = q.deconstruct()
        self.assertEqual(args, (("price__gt", F("discounted_price")),))
        self.assertEqual(kwargs, {"_negated": True})

    def test_deconstruct_or(self):
        q1 = Q(price__gt=F("discounted_price"))
        q2 = Q(price=F("discounted_price"))
        q = q1 | q2
        path, args, kwargs = q.deconstruct()
        self.assertEqual(
            args,
            (
                ("price__gt", F("discounted_price")),
                ("price", F("discounted_price")),
            ),
        )
        self.assertEqual(kwargs, {"_connector": Q.OR})

    def test_deconstruct_xor(self):
        q1 = Q(price__gt=F("discounted_price"))
        q2 = Q(price=F("discounted_price"))
        q = q1 ^ q2
        path, args, kwargs = q.deconstruct()
        self.assertEqual(
            args,
            (
                ("price__gt", F("discounted_price")),
                ("price", F("discounted_price")),
            ),
        )
        self.assertEqual(kwargs, {"_connector": Q.XOR})

    def test_deconstruct_and(self):
        q1 = Q(price__gt=F("discounted_price"))
        q2 = Q(price=F("discounted_price"))
        q = q1 & q2
        path, args, kwargs = q.deconstruct()
        self.assertEqual(
            args,
            (
                ("price__gt", F("discounted_price")),
                ("price", F("discounted_price")),
            ),
        )
        self.assertEqual(kwargs, {})

    def test_deconstruct_multiple_kwargs(self):
        q = Q(price__gt=F("discounted_price"), price=F("discounted_price"))
        path, args, kwargs = q.deconstruct()
        self.assertEqual(
            args,
            (
                ("price", F("discounted_price")),
                ("price__gt", F("discounted_price")),
            ),
        )
        self.assertEqual(kwargs, {})

    def test_deconstruct_nested(self):
        q = Q(Q(price__gt=F("discounted_price")))
        path, args, kwargs = q.deconstruct()
        self.assertEqual(args, (Q(price__gt=F("discounted_price")),))
        self.assertEqual(kwargs, {})

    def test_deconstruct_boolean_expression(self):
        """
        Tests the deconstruction of a boolean expression by verifying that the deconstruct method returns the correct arguments and keyword arguments. 

        This test case ensures that a boolean expression, created from a raw SQL query, can be successfully deconstructed into its constituent parts. The test verifies that the deconstructed arguments match the original expression and that no keyword arguments are returned.
        """
        expr = RawSQL("1 = 1", BooleanField())
        q = Q(expr)
        _, args, kwargs = q.deconstruct()
        self.assertEqual(args, (expr,))
        self.assertEqual(kwargs, {})

    def test_reconstruct(self):
        """

        Tests the deconstruction and reconstruction of a complex Q object.

        The function verifies that a Q object with a filter condition comparing two fields
        can be successfully deconstructed into its constituent parts and then rebuilt
        into an equivalent Q object.

        This test ensures the correctness of the deconstruction and reconstruction
        process, which is essential for reliably serializing and deserializing complex
        query objects.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the reconstructed Q object does not match the original object

        """
        q = Q(price__gt=F("discounted_price"))
        path, args, kwargs = q.deconstruct()
        self.assertEqual(Q(*args, **kwargs), q)

    def test_reconstruct_negated(self):
        """
        Tests the deconstruction and reconstruction of a negated django ORM query.

         Verifies that a query negating the condition 'price greater than discounted price'
         can be broken down into its components and then reassembled into an equivalent query,
         ensuring that the negation is preserved and the query remains valid:

         * Creates a query :math:`~(price > discounted\_price)`
         * Deconstructs the query into its constituent parts
         * Reassembles the query from the deconstructed parts
         * Asserts that the reassembled query is equivalent to the original query
        """
        q = ~Q(price__gt=F("discounted_price"))
        path, args, kwargs = q.deconstruct()
        self.assertEqual(Q(*args, **kwargs), q)

    def test_reconstruct_or(self):
        """

        Tests the deconstruction and reconstruction of a QuerySet object 
        that uses the bitwise OR operator.

        Verifies that a complex QuerySet created by combining two queries 
        with the | operator can be successfully deconstructed and then 
        reconstructed into an equivalent QuerySet, ensuring the preservation 
        of its original logic and functionality.

        This test case involves queries related to product pricing, 
        checking for products where the price is either greater than the 
        discounted price or equal to it, and ensures that the 
        deconstruction and reconstruction process maintains the correctness 
        of these queries.

        """
        q1 = Q(price__gt=F("discounted_price"))
        q2 = Q(price=F("discounted_price"))
        q = q1 | q2
        path, args, kwargs = q.deconstruct()
        self.assertEqual(Q(*args, **kwargs), q)

    def test_reconstruct_xor(self):
        """

        Tests the deconstruction and reconstruction of a QuerySet XOR operation.

        The function verifies that an XOR operation between two query filters can be
        successfully deconstructed into its constituent parts, and then reconstructed
        back into the original QuerySet, ensuring that the resulting queries are equal.

        This test case covers the scenario where a query filter checks for records with
        a price greater than the discounted price, or where the price is equal to the
        discounted price, checking for correctness of the XOR operation.

        """
        q1 = Q(price__gt=F("discounted_price"))
        q2 = Q(price=F("discounted_price"))
        q = q1 ^ q2
        path, args, kwargs = q.deconstruct()
        self.assertEqual(Q(*args, **kwargs), q)

    def test_reconstruct_and(self):
        """

        Test the reconstruction of a QuerySet using the bitwise AND operator.

        This test case verifies that a complex query constructed using the bitwise AND
        operator (&) can be successfully deconstructed and then reconstructed back into
        its original form, ensuring that the queried data remains consistent and accurate.

        The test involves creating two query objects (q1 and q2) with different conditions,
        merging them using the bitwise AND operator, deconstructing the resulting query,
        and then reconstructing it to verify that the original query is restored correctly.

        """
        q1 = Q(price__gt=F("discounted_price"))
        q2 = Q(price=F("discounted_price"))
        q = q1 & q2
        path, args, kwargs = q.deconstruct()
        self.assertEqual(Q(*args, **kwargs), q)

    def test_equal(self):
        self.assertEqual(Q(), Q())
        self.assertEqual(
            Q(("pk__in", (1, 2))),
            Q(("pk__in", [1, 2])),
        )
        self.assertEqual(
            Q(("pk__in", (1, 2))),
            Q(pk__in=[1, 2]),
        )
        self.assertEqual(
            Q(("pk__in", (1, 2))),
            Q(("pk__in", {1: "first", 2: "second"}.keys())),
        )
        self.assertNotEqual(
            Q(name__iexact=F("other_name")),
            Q(name=Lower(F("other_name"))),
        )

    def test_hash(self):
        self.assertEqual(hash(Q()), hash(Q()))
        self.assertEqual(
            hash(Q(("pk__in", (1, 2)))),
            hash(Q(("pk__in", [1, 2]))),
        )
        self.assertEqual(
            hash(Q(("pk__in", (1, 2)))),
            hash(Q(pk__in=[1, 2])),
        )
        self.assertEqual(
            hash(Q(("pk__in", (1, 2)))),
            hash(Q(("pk__in", {1: "first", 2: "second"}.keys()))),
        )
        self.assertNotEqual(
            hash(Q(name__iexact=F("other_name"))),
            hash(Q(name=Lower(F("other_name")))),
        )

    def test_flatten(self):
        q = Q()
        self.assertEqual(list(q.flatten()), [q])
        q = Q(NothingNode())
        self.assertEqual(list(q.flatten()), [q, q.children[0]])
        q = Q(
            ExpressionWrapper(
                Q(RawSQL("id = 0", params=(), output_field=BooleanField()))
                | Q(price=Value("4.55"))
                | Q(name=Lower("category")),
                output_field=BooleanField(),
            )
        )
        flatten = list(q.flatten())
        self.assertEqual(len(flatten), 7)

    def test_create_helper(self):
        items = [("a", 1), ("b", 2), ("c", 3)]
        for connector in [Q.AND, Q.OR, Q.XOR]:
            with self.subTest(connector=connector):
                self.assertEqual(
                    Q.create(items, connector=connector),
                    Q(*items, _connector=connector),
                )

    def test_referenced_base_fields(self):
        # Make sure Q.referenced_base_fields retrieves all base fields from
        # both filters and F expressions.
        """
        Tests that the :meth:`referenced_base_fields` method of a :class:`Q` object correctly identifies the base model fields referenced by a query.

        The method is tested against a variety of query types, including simple field lookups,
        logical AND operations, exact matches, and lookups using F-expressions and Q objects.
        Each test case verifies that the :meth:`referenced_base_fields` method returns the expected set of base model fields.

        The test cases cover various scenarios, such as:

        * Basic field lookups (e.g., `field_1=1`)
        * Logical AND operations combining multiple lookups
        * Exact matches using F-expressions and Q objects
        * Lookups using field aliases and nested joins

        The :meth:`referenced_base_fields` method is expected to return a set of base model field names
        that are referenced by the query, excluding any intermediate fields or joins.
        """
        tests = [
            (Q(field_1=1) & Q(field_2=1), {"field_1", "field_2"}),
            (
                Q(Exact(F("field_3"), IsNull(F("field_4"), True))),
                {"field_3", "field_4"},
            ),
            (Q(Exact(Q(field_5=F("field_6")), True)), {"field_5", "field_6"}),
            (Q(field_2=1), {"field_2"}),
            (Q(field_7__lookup=True), {"field_7"}),
            (Q(field_7__joined_field__lookup=True), {"field_7"}),
        ]
        combined_q = Q(1)
        combined_q_base_fields = set()
        for q, expected_base_fields in tests:
            combined_q &= q
            combined_q_base_fields |= expected_base_fields
        tests.append((combined_q, combined_q_base_fields))
        for q, expected_base_fields in tests:
            with self.subTest(q=q):
                self.assertEqual(
                    q.referenced_base_fields,
                    expected_base_fields,
                )


class QCheckTests(TestCase):
    def test_basic(self):
        """
        Tests basic functionality of the query filter.

        Verifies that the filter correctly identifies objects that match a simple condition, 
        in this case, objects with a 'price' greater than 20. 

        The test covers two scenarios: one where the object's 'price' is above the threshold, 
        and one where it is below, ensuring the filter behaves as expected in both cases.
        """
        q = Q(price__gt=20)
        self.assertIs(q.check({"price": 30}), True)
        self.assertIs(q.check({"price": 10}), False)

    def test_expression(self):
        q = Q(name="test")
        self.assertIs(q.check({"name": Lower(Value("TeSt"))}), True)
        self.assertIs(q.check({"name": Value("other")}), False)

    def test_missing_field(self):
        """
        Tests that a FieldError is raised when a query contains a field that does not exist in the data.

        Verifies that the check method correctly handles missing fields by attempting to query a data set
        with a field that is not present, resulting in a FieldError with a descriptive error message.

        The test case covers a specific scenario where the description field is referenced in the query,
        but is not available in the provided data, ensuring robust error handling in such situations.
        """
        q = Q(description__startswith="prefix")
        msg = "Cannot resolve keyword 'description' into field."
        with self.assertRaisesMessage(FieldError, msg):
            q.check({"name": "test"})

    def test_boolean_expression(self):
        """
        Tests the evaluation of a boolean expression.

        This function checks if a given expression, specifically a price greater than 20, 
        is correctly evaluated against a data set. It uses a query (Q) object with 
        an ExpressionWrapper to generate a boolean output. The test case validates 
        the expression's result for both true and false conditions, ensuring the 
        correct functionality of the expression evaluation mechanism.
        """
        q = Q(ExpressionWrapper(Q(price__gt=20), output_field=BooleanField()))
        self.assertIs(q.check({"price": 25}), True)
        self.assertIs(q.check({"price": Value(10)}), False)

    def test_rawsql(self):
        """
        RawSQL expressions cause a database error because "price" cannot be
        replaced by its value. In this case, Q.check() logs a warning and
        return True.
        """
        q = Q(RawSQL("price > %s", params=(20,), output_field=BooleanField()))
        with self.assertLogs("django.db.models", "WARNING") as cm:
            self.assertIs(q.check({"price": 10}), True)
        self.assertIn(
            f"Got a database error calling check() on {q!r}: ",
            cm.records[0].getMessage(),
        )
