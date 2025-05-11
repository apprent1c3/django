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
        Tests the behavior of combining query objects with empty queries using the bitwise AND operator.
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

        Tests the combination of query objects with an empty query using the bitwise OR operator.

        Verifies that combining an empty query with a non-empty query, or vice versa, returns the non-empty query.

        """
        q = Q(x=1)
        self.assertEqual(q | Q(), q)
        self.assertEqual(Q() | q, q)

        q = Q(x__in={}.keys())
        self.assertEqual(q | Q(), q)
        self.assertEqual(Q() | q, q)

    def test_combine_xor_empty(self):
        """

        Tests the behaviour of combining XOR operation with empty queries.
        Verifies that an empty query does not affect the result of the XOR operation.

        """
        q = Q(x=1)
        self.assertEqual(q ^ Q(), q)
        self.assertEqual(Q() ^ q, q)

        q = Q(x__in={}.keys())
        self.assertEqual(q ^ Q(), q)
        self.assertEqual(Q() ^ q, q)

    def test_combine_empty_copy(self):
        """
        Tests the combination of a base query with an empty query for various operations,
        verifying that the resulting query is equivalent to the base query but a distinct object.
        """
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
        """
        Tests that combining a Q object with a non-Q object raises a TypeError
        """
        obj = object()
        q = Q(x=1)
        with self.assertRaisesMessage(TypeError, str(obj)):
            q | obj
        with self.assertRaisesMessage(TypeError, str(obj)):
            q & obj
        with self.assertRaisesMessage(TypeError, str(obj)):
            q ^ obj

    def test_combine_negated_boolean_expression(self):
        """
        Tests the combination of negated boolean expressions with various logical operators to ensure they are correctly classified as NegatedExpressions.
        """
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
        """

        Tests the deconstruction of a Django Q object containing a comparison between a field and an F expression.

        """
        q = Q(price__gt=F("discounted_price"))
        path, args, kwargs = q.deconstruct()
        self.assertEqual(path, "django.db.models.Q")
        self.assertEqual(args, (("price__gt", F("discounted_price")),))
        self.assertEqual(kwargs, {})

    def test_deconstruct_negated(self):
        q = ~Q(price__gt=F("discounted_price"))
        path, args, kwargs = q.deconstruct()
        self.assertEqual(args, (("price__gt", F("discounted_price")),))
        self.assertEqual(kwargs, {"_negated": True})

    def test_deconstruct_or(self):
        """
        Tests the deconstruction of a Q object containing an 'or' condition, 
        verifying that the resulting arguments and keyword arguments accurately represent the original query.
        """
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
        """
        Verifies the deconstruction of an XOR query, ensuring it correctly represents the original query conditions and connector.
        """
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
        """
        Tests that a compound QuerySet filter is correctly deconstructed.

        Verifies that the deconstruction process preserves the logical AND operation
        and maintains the correct filter arguments.
        """
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
        Tests the deconstruction of a boolean expression into its constituent parts. Verifies that the deconstructed expression is correctly broken down into its raw SQL and keyword arguments.
        """
        expr = RawSQL("1 = 1", BooleanField())
        q = Q(expr)
        _, args, kwargs = q.deconstruct()
        self.assertEqual(args, (expr,))
        self.assertEqual(kwargs, {})

    def test_reconstruct(self):
        q = Q(price__gt=F("discounted_price"))
        path, args, kwargs = q.deconstruct()
        self.assertEqual(Q(*args, **kwargs), q)

    def test_reconstruct_negated(self):
        q = ~Q(price__gt=F("discounted_price"))
        path, args, kwargs = q.deconstruct()
        self.assertEqual(Q(*args, **kwargs), q)

    def test_reconstruct_or(self):
        """
        Tests the reconstruction of a complex query using the bitwise OR operator.
        """
        q1 = Q(price__gt=F("discounted_price"))
        q2 = Q(price=F("discounted_price"))
        q = q1 | q2
        path, args, kwargs = q.deconstruct()
        self.assertEqual(Q(*args, **kwargs), q)

    def test_reconstruct_xor(self):
        """
        Tests the reconstruction of a query using the XOR operator.
        """
        q1 = Q(price__gt=F("discounted_price"))
        q2 = Q(price=F("discounted_price"))
        q = q1 ^ q2
        path, args, kwargs = q.deconstruct()
        self.assertEqual(Q(*args, **kwargs), q)

    def test_reconstruct_and(self):
        """
        Tests that Q objects can be successfully reconstructed from their deconstructed parts, ensuring equivalence after reconstruction.
        """
        q1 = Q(price__gt=F("discounted_price"))
        q2 = Q(price=F("discounted_price"))
        q = q1 & q2
        path, args, kwargs = q.deconstruct()
        self.assertEqual(Q(*args, **kwargs), q)

    def test_equal(self):
        """
        Tests the equality of various query object instances to ensure that they are compared correctly, regardless of the input data types or formats. Covers various cases, including different collection types and query syntaxes.
        """
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
        """
        Tests the consistency of hash values generated by the Q object, ensuring that equivalent queries produce the same hash value regardless of the query's internal representation.
        """
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
        """
        Tests the flattening of query objects into a list of nodes, ensuring that all children are properly traversed and included in the resulting list.
        """
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

        Tests that the referenced_base_fields method of a QuerySet correctly returns the set of base fields referenced by the query.

        This ensures that the method accurately identifies the fields that are used in the query, including nested fields and fields referenced in lookups and Exact filters.

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
        q = Q(price__gt=20)
        self.assertIs(q.check({"price": 30}), True)
        self.assertIs(q.check({"price": 10}), False)

    def test_expression(self):
        q = Q(name="test")
        self.assertIs(q.check({"name": Lower(Value("TeSt"))}), True)
        self.assertIs(q.check({"name": Value("other")}), False)

    def test_missing_field(self):
        q = Q(description__startswith="prefix")
        msg = "Cannot resolve keyword 'description' into field."
        with self.assertRaisesMessage(FieldError, msg):
            q.check({"name": "test"})

    def test_boolean_expression(self):
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
