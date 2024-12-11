from datetime import datetime

from django.core.exceptions import FieldError
from django.db import DEFAULT_DB_ALIAS, connection
from django.db.models import BooleanField, CharField, F, Q
from django.db.models.expressions import (
    Col,
    Exists,
    ExpressionWrapper,
    Func,
    RawSQL,
    Value,
)
from django.db.models.fields.related_lookups import RelatedIsNull
from django.db.models.functions import Lower
from django.db.models.lookups import Exact, GreaterThan, IsNull, LessThan
from django.db.models.sql.constants import SINGLE
from django.db.models.sql.query import JoinPromoter, Query, get_field_names_from_opts
from django.db.models.sql.where import AND, OR
from django.test import SimpleTestCase, TestCase, skipUnlessDBFeature
from django.test.utils import register_lookup

from .models import Author, Item, ObjectC, Ranking


class TestQuery(SimpleTestCase):
    def test_simple_query(self):
        """

        Tests a simple query by building a Where clause with a Greater Than condition.

        Checks that the query can correctly translate the condition into a
        `GreaterThan` lookup and that the lookup's left-hand side (LHS) and
        right-hand side (RHS) values are correctly set. The LHS is verified to
        reference the 'num' field of the Author model, while the RHS is verified
        to be equal to 2.

        """
        query = Query(Author)
        where = query.build_where(Q(num__gt=2))
        lookup = where.children[0]
        self.assertIsInstance(lookup, GreaterThan)
        self.assertEqual(lookup.rhs, 2)
        self.assertEqual(lookup.lhs.target, Author._meta.get_field("num"))

    def test_non_alias_cols_query(self):
        query = Query(Author, alias_cols=False)
        where = query.build_where(Q(num__gt=2, name__isnull=False) | Q(num__lt=F("id")))

        name_isnull_lookup, num_gt_lookup = where.children[0].children
        self.assertIsInstance(num_gt_lookup, GreaterThan)
        self.assertIsInstance(num_gt_lookup.lhs, Col)
        self.assertIsNone(num_gt_lookup.lhs.alias)
        self.assertIsInstance(name_isnull_lookup, IsNull)
        self.assertIsInstance(name_isnull_lookup.lhs, Col)
        self.assertIsNone(name_isnull_lookup.lhs.alias)

        num_lt_lookup = where.children[1]
        self.assertIsInstance(num_lt_lookup, LessThan)
        self.assertIsInstance(num_lt_lookup.rhs, Col)
        self.assertIsNone(num_lt_lookup.rhs.alias)
        self.assertIsInstance(num_lt_lookup.lhs, Col)
        self.assertIsNone(num_lt_lookup.lhs.alias)

    def test_complex_query(self):
        """

        Tests the construction of complex queries using the Query class.

        Specifically, this function verifies that a query with multiple conditions
        combined using the logical OR operator is correctly built. It checks that
        the connector used is the OR operator and that the conditions are properly
        evaluated as greater than and less than comparisons on the 'num' field of the
        Author model.

        The test case covers the following scenarios:
        - The query is constructed with two conditions: 'num' greater than 2 and 'num' less than 0.
        - The conditions are combined using the logical OR operator.
        - The resulting query has the correct connector (OR) and conditions (GreaterThan and LessThan).

        """
        query = Query(Author)
        where = query.build_where(Q(num__gt=2) | Q(num__lt=0))
        self.assertEqual(where.connector, OR)

        lookup = where.children[0]
        self.assertIsInstance(lookup, GreaterThan)
        self.assertEqual(lookup.rhs, 2)
        self.assertEqual(lookup.lhs.target, Author._meta.get_field("num"))

        lookup = where.children[1]
        self.assertIsInstance(lookup, LessThan)
        self.assertEqual(lookup.rhs, 0)
        self.assertEqual(lookup.lhs.target, Author._meta.get_field("num"))

    def test_multiple_fields(self):
        query = Query(Item, alias_cols=False)
        where = query.build_where(Q(modified__gt=F("created")))
        lookup = where.children[0]
        self.assertIsInstance(lookup, GreaterThan)
        self.assertIsInstance(lookup.rhs, Col)
        self.assertIsNone(lookup.rhs.alias)
        self.assertIsInstance(lookup.lhs, Col)
        self.assertIsNone(lookup.lhs.alias)
        self.assertEqual(lookup.rhs.target, Item._meta.get_field("created"))
        self.assertEqual(lookup.lhs.target, Item._meta.get_field("modified"))

    def test_transform(self):
        """

        Tests the application of a transformation to a database query.

        Verifies that a :class:`Lower` transformation is correctly applied to a 
        :field:`CharField` in a query, and that the resulting lookup is of the 
        correct type (:class:`Exact`) and structure.

        The transformation is applied as a :class:`Lower` lookup registration 
        for a :class:`CharField`, and the test ensures that this is correctly 
        translated into a lookup with the expected characteristics, including 
        the absence of an alias and the correct reference to the underlying 
        database field.

        """
        query = Query(Author, alias_cols=False)
        with register_lookup(CharField, Lower):
            where = query.build_where(~Q(name__lower="foo"))
        lookup = where.children[0]
        self.assertIsInstance(lookup, Exact)
        self.assertIsInstance(lookup.lhs, Lower)
        self.assertIsInstance(lookup.lhs.lhs, Col)
        self.assertIsNone(lookup.lhs.lhs.alias)
        self.assertEqual(lookup.lhs.lhs.target, Author._meta.get_field("name"))

    def test_negated_nullable(self):
        query = Query(Item)
        where = query.build_where(~Q(modified__lt=datetime(2017, 1, 1)))
        self.assertTrue(where.negated)
        lookup = where.children[0]
        self.assertIsInstance(lookup, LessThan)
        self.assertEqual(lookup.lhs.target, Item._meta.get_field("modified"))
        lookup = where.children[1]
        self.assertIsInstance(lookup, IsNull)
        self.assertEqual(lookup.lhs.target, Item._meta.get_field("modified"))

    def test_foreign_key(self):
        query = Query(Item)
        msg = "Joined field references are not permitted in this query"
        with self.assertRaisesMessage(FieldError, msg):
            query.build_where(Q(creator__num__gt=2))

    def test_foreign_key_f(self):
        query = Query(Ranking)
        with self.assertRaises(FieldError):
            query.build_where(Q(rank__gt=F("author__num")))

    def test_foreign_key_exclusive(self):
        """

        Tests the generation of WHERE clauses for foreign key exclusivity.

        This function verifies that a query with an OR condition on two related
        objects' foreign keys correctly generates the expected RelatedIsNull and
        Column representations in the WHERE clause.

        The test checks that:
        - The generated WHERE clause has RelatedIsNull instances for both related
          objects.
        - Each RelatedIsNull instance has a Column representation on its left-hand
          side with no alias.
        - The Column representation targets the correct field in the model metadata.

        """
        query = Query(ObjectC, alias_cols=False)
        where = query.build_where(Q(objecta=None) | Q(objectb=None))
        a_isnull = where.children[0]
        self.assertIsInstance(a_isnull, RelatedIsNull)
        self.assertIsInstance(a_isnull.lhs, Col)
        self.assertIsNone(a_isnull.lhs.alias)
        self.assertEqual(a_isnull.lhs.target, ObjectC._meta.get_field("objecta"))
        b_isnull = where.children[1]
        self.assertIsInstance(b_isnull, RelatedIsNull)
        self.assertIsInstance(b_isnull.lhs, Col)
        self.assertIsNone(b_isnull.lhs.alias)
        self.assertEqual(b_isnull.lhs.target, ObjectC._meta.get_field("objectb"))

    def test_clone_select_related(self):
        query = Query(Item)
        query.add_select_related(["creator"])
        clone = query.clone()
        clone.add_select_related(["note", "creator__extra"])
        self.assertEqual(query.select_related, {"creator": {}})

    def test_iterable_lookup_value(self):
        query = Query(Item)
        where = query.build_where(Q(name=["a", "b"]))
        name_exact = where.children[0]
        self.assertIsInstance(name_exact, Exact)
        self.assertEqual(name_exact.rhs, "['a', 'b']")

    def test_filter_conditional(self):
        """

        Tests the conditional filtering functionality of the query builder.

        Verifies that the query's where clause is correctly constructed using the 
        Func and Exact classes, resulting in a conditional filter that checks 
        for a specific boolean value.

        """
        query = Query(Item)
        where = query.build_where(Func(output_field=BooleanField()))
        exact = where.children[0]
        self.assertIsInstance(exact, Exact)
        self.assertIsInstance(exact.lhs, Func)
        self.assertIs(exact.rhs, True)

    def test_filter_conditional_join(self):
        """
        Tests that attempting to filter a query based on a conditional join raises a FieldError. 
        The test verifies that a specific error message is produced when trying to filter on a joined field reference, which is not supported in the query.
        """
        query = Query(Item)
        filter_expr = Func("note__note", output_field=BooleanField())
        msg = "Joined field references are not permitted in this query"
        with self.assertRaisesMessage(FieldError, msg):
            query.build_where(filter_expr)

    def test_filter_non_conditional(self):
        """
        Tests that building a WHERE clause with a non-conditional expression raises a TypeError.
        The error is raised when using a Func object without a conditional expression, 
        indicating that non-conditional expressions are not supported for filtering.
        The expected error message is 'Cannot filter against a non-conditional expression.' 
        which is checked to ensure the correct exception is raised.
        """
        query = Query(Item)
        msg = "Cannot filter against a non-conditional expression."
        with self.assertRaisesMessage(TypeError, msg):
            query.build_where(Func(output_field=CharField()))


class TestQueryNoModel(TestCase):
    def test_rawsql_annotation(self):
        query = Query(None)
        sql = "%s = 1"
        # Wrap with a CASE WHEN expression if a database backend (e.g. Oracle)
        # doesn't support boolean expression in SELECT list.
        if not connection.features.supports_boolean_expr_in_select_clause:
            sql = f"CASE WHEN {sql} THEN 1 ELSE 0 END"
        query.add_annotation(RawSQL(sql, (1,), BooleanField()), "_check")
        result = query.get_compiler(using=DEFAULT_DB_ALIAS).execute_sql(SINGLE)
        self.assertEqual(result[0], 1)

    def test_subquery_annotation(self):
        """
        Tests the functionality of subquery annotations in queries.

        This test case checks if a query with an 'Exists' subquery annotation returns the expected result.
        The annotation verifies the existence of items in the database, and the test asserts that the query correctly 
        returns a count of 0 when no items match the subquery condition.

        The test utilizes a Query object with a custom annotation and executes it using the database compiler, 
        simulating a real-world query execution scenario. The result is then verified to ensure the annotation 
        functions as expected.


        """
        query = Query(None)
        query.add_annotation(Exists(Item.objects.all()), "_check")
        result = query.get_compiler(using=DEFAULT_DB_ALIAS).execute_sql(SINGLE)
        self.assertEqual(result[0], 0)

    @skipUnlessDBFeature("supports_boolean_expr_in_select_clause")
    def test_q_annotation(self):
        query = Query(None)
        check = ExpressionWrapper(
            Q(RawSQL("%s = 1", (1,), BooleanField())) | Q(Exists(Item.objects.all())),
            BooleanField(),
        )
        query.add_annotation(check, "_check")
        result = query.get_compiler(using=DEFAULT_DB_ALIAS).execute_sql(SINGLE)
        self.assertEqual(result[0], 1)

    def test_names_to_path_field(self):
        """

        Translates a list of names to a path field, resolving the corresponding fields and targets.

        This method takes a list of names as input and returns a tuple containing the path, 
        the final field, a list of targets, and a list of remaining names. The path represents 
        the sequence of fields that were traversed to reach the final field. The final field 
        is the field that corresponds to the last name in the input list. The targets list 
        contains the fields that are targeted by the input names. The remaining names list 
        contains any names that were not resolved to a field.

        The method is useful for resolving names to fields and targets in a query, allowing 
        for navigating and querying complex data structures. 

        Parameters
        ----------
        names : list
            A list of names to be translated to a path field.

        Returns
        -------
        tuple
            A tuple containing the path, the final field, a list of targets, and a list of 
            remaining names.

        """
        query = Query(None)
        query.add_annotation(Value(True), "value")
        path, final_field, targets, names = query.names_to_path(["value"], opts=None)
        self.assertEqual(path, [])
        self.assertIsInstance(final_field, BooleanField)
        self.assertEqual(len(targets), 1)
        self.assertIsInstance(targets[0], BooleanField)
        self.assertEqual(names, [])

    def test_names_to_path_field_error(self):
        """
        Tests that the names_to_path method raises a FieldError when given a nonexistent field name.

        This test case verifies that the names_to_path method correctly handles invalid field names by raising a FieldError with a meaningful error message. It checks that the error message includes the name of the nonexistent field, providing useful feedback for debugging purposes.
        """
        query = Query(None)
        msg = "Cannot resolve keyword 'nonexistent' into field."
        with self.assertRaisesMessage(FieldError, msg):
            query.names_to_path(["nonexistent"], opts=None)

    def test_get_field_names_from_opts(self):
        self.assertEqual(get_field_names_from_opts(None), set())


class JoinPromoterTest(SimpleTestCase):
    def test_repr(self):
        self.assertEqual(
            repr(JoinPromoter(AND, 3, True)),
            "JoinPromoter(connector='AND', num_children=3, negated=True)",
        )
