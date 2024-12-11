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
        q = Q(x=1)
        self.assertEqual(q & Q(), q)
        self.assertEqual(Q() & q, q)

        q = Q(x__in={}.keys())
        self.assertEqual(q & Q(), q)
        self.assertEqual(Q() & q, q)

    def test_combine_and_both_empty(self):
        self.assertEqual(Q() & Q(), Q())

    def test_combine_or_empty(self):
        q = Q(x=1)
        self.assertEqual(q | Q(), q)
        self.assertEqual(Q() | q, q)

        q = Q(x__in={}.keys())
        self.assertEqual(q | Q(), q)
        self.assertEqual(Q() | q, q)

    def test_combine_xor_empty(self):
        """

        Test the combination of XOR operation with empty queries.

        This test case verifies that when an empty query is combined with a non-empty query using the XOR operator,
        the resulting query is the non-empty query itself. The test covers both scenarios where the empty query
        is the left or the right operand in the XOR operation.

        The test also checks that this behavior holds for queries with empty lookup fields, such as an \"in\" lookup
        with an empty dictionary. 

        The goal is to ensure that the XOR operation with an empty query does not alter the original query.

        """
        q = Q(x=1)
        self.assertEqual(q ^ Q(), q)
        self.assertEqual(Q() ^ q, q)

        q = Q(x__in={}.keys())
        self.assertEqual(q ^ Q(), q)
        self.assertEqual(Q() ^ q, q)

    def test_combine_empty_copy(self):
        """

        Checks the behavior of combining a query with an empty query using different logical operators.

        This test ensures that the resulting query is equivalent to the original query when combined with an empty query using union, intersection, and symmetric difference operators.
        The test also verifies that a new query object is created, rather than modifying the original query, to maintain immutability.

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
        Tests the deconstruction of a negated query, specifically a query that negates the condition of a price being greater than a discounted price. 

        Checks if the deconstructed query returns the correct path, arguments and keyword arguments. 

        The test verifies that the arguments returned include the original condition (price greater than discounted price) and that the keyword arguments indicate the query has been negated.
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
        """
        Tests the deconstruction of a nested Q object.

        This test ensures that a Q object containing another Q object is successfully
        deconstructed into its path, arguments, and keyword arguments components.

        The deconstruction process is tested with a Q object that represents a filter 
        condition where the price is greater than the discounted price. The test verifies 
        that the deconstructed arguments and keyword arguments match the expected output, 
        demonstrating the correct handling of nested Q objects.

        :raises: AssertionError if the deconstruction of the nested Q object fails
        """
        q = Q(Q(price__gt=F("discounted_price")))
        path, args, kwargs = q.deconstruct()
        self.assertEqual(args, (Q(price__gt=F("discounted_price")),))
        self.assertEqual(kwargs, {})

    def test_deconstruct_boolean_expression(self):
        """
        Tests the deconstruction of a boolean expression.

        This function verifies that the deconstruct method of a Q object correctly
        decomposes a boolean expression into its constituent parts. It checks that
        the arguments and keyword arguments returned by the deconstruct method
        match the expected values.

        This ensures that complex boolean expressions can be properly rebuilt and
        reused, which is essential for constructing and manipulating database queries.

        """
        expr = RawSQL("1 = 1", BooleanField())
        q = Q(expr)
        _, args, kwargs = q.deconstruct()
        self.assertEqual(args, (expr,))
        self.assertEqual(kwargs, {})

    def test_reconstruct(self):
        """
        Tests the reconstruction of a Q object.

         The function verifies that a Q object can be deconstructed into its path, 
         arguments, and keyword arguments, and then reconstructed back into the 
         original Q object, ensuring correctness and equivalence between the original 
         and reconstructed objects.

         This test case uses a Q object with a filter condition where the price 
         is greater than the discounted price, demonstrating the reconstruction 
         process for a comparison operation involving field references.

        """
        q = Q(price__gt=F("discounted_price"))
        path, args, kwargs = q.deconstruct()
        self.assertEqual(Q(*args, **kwargs), q)

    def test_reconstruct_negated(self):
        """

         Tests the reconstruction of a negated query.

         Verifies that deconstructing and reconstructing a negated query using the
         bitwise NOT operator (~) results in an equivalent query object. The test
         checks if the reconstructed query is equal to the original query, ensuring
         that the deconstruction and reconstruction process preserves the query's
         logic and effectiveness.

        """
        q = ~Q(price__gt=F("discounted_price"))
        path, args, kwargs = q.deconstruct()
        self.assertEqual(Q(*args, **kwargs), q)

    def test_reconstruct_or(self):
        q1 = Q(price__gt=F("discounted_price"))
        q2 = Q(price=F("discounted_price"))
        q = q1 | q2
        path, args, kwargs = q.deconstruct()
        self.assertEqual(Q(*args, **kwargs), q)

    def test_reconstruct_xor(self):
        q1 = Q(price__gt=F("discounted_price"))
        q2 = Q(price=F("discounted_price"))
        q = q1 ^ q2
        path, args, kwargs = q.deconstruct()
        self.assertEqual(Q(*args, **kwargs), q)

    def test_reconstruct_and(self):
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
        """
        Tests the Q.create function for generating complex queries with different logical connectors.

        The test verifies that the Q.create function correctly constructs queries using 
        the provided items and logical connectors (AND, OR, XOR), ensuring the resulting 
        query matches the expected output.

        Parameters are not explicitly defined in this function as it is a test case, 
        but the Q.create function's behavior is validated for various connector types.
        """
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
        """
        Tests the evaluation of a boolean expression.

        This function checks if a given boolean expression is satisfied by a set of input data.
        The expression being tested is whether the 'price' value is greater than 20.
        It verifies that the expression correctly returns True when the price is above 20 and False otherwise.
        The test includes scenarios where the input data is a numeric value and a Django database Value object. 
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
