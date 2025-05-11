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
        Tests the construction of a simple database query with a greater-than condition, verifying the correct creation of a GreaterThan lookup object.
        """
        query = Query(Author)
        where = query.build_where(Q(num__gt=2))
        lookup = where.children[0]
        self.assertIsInstance(lookup, GreaterThan)
        self.assertEqual(lookup.rhs, 2)
        self.assertEqual(lookup.lhs.target, Author._meta.get_field("num"))

    def test_non_alias_cols_query(self):
        """
        Tests the construction of a query with non-aliased columns, verifying that the generated lookups (GreaterThan, IsNull, LessThan) reference columns without aliases.
        """
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
        ``` 
        \"\"\"Tests the construction of a complex query with OR condition.

        Verifies that the query correctly generates a WHERE clause with OR connector
        and contains the expected lookup types (GreaterThan, LessThan) and their values.
        \"\"\" 
        ```
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
        """
        Verifies that a where clause with a comparison between two model fields is correctly constructed and aliased.
        """
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
        Tests that the `build_where` method correctly transforms a query using a custom lookup, specifically verifying that the lookup is an `Exact` lookup with the `Lower` transformation applied to the field.
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
        """
        Tests the negation of a nullable query, ensuring that the resulting WHERE clause is correctly marked as negated and contains the expected lookup operations.
        """
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
        Tests the construction of a WHERE clause for a Query that checks if either of two related objects is null, verifying the correct usage of foreign key relationships in the query builder.
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
        """
        Tests that cloning a query preserves the original query's select_related configuration and allows the clone to be modified independently.
        """
        query = Query(Item)
        query.add_select_related(["creator"])
        clone = query.clone()
        clone.add_select_related(["note", "creator__extra"])
        self.assertEqual(query.select_related, {"creator": {}})

    def test_iterable_lookup_value(self):
        """
        Tests the lookup of iterable values in a query, ensuring that the 'name' field is matched exactly against the provided list of values. Verifies that the generated 'where' clause contains an Exact query with the correct values.
        """
        query = Query(Item)
        where = query.build_where(Q(name=["a", "b"]))
        name_exact = where.children[0]
        self.assertIsInstance(name_exact, Exact)
        self.assertEqual(name_exact.rhs, "['a', 'b']")

    def test_filter_conditional(self):
        """
        Tests that the build_where method of a Query object generates a conditional filter with the correct structure, specifically an Exact node with a Func on the left-hand side and True on the right-hand side.
        """
        query = Query(Item)
        where = query.build_where(Func(output_field=BooleanField()))
        exact = where.children[0]
        self.assertIsInstance(exact, Exact)
        self.assertIsInstance(exact.lhs, Func)
        self.assertIs(exact.rhs, True)

    def test_filter_conditional_join(self):
        """
        Tests that attempting to use a joined field reference in a Query build operation correctly raises a FieldError.\"\"\"

        or more accurately 

        \"\"\"Verifies that a FieldError is raised when a joined field reference is used in a conditional join query.
        """
        query = Query(Item)
        filter_expr = Func("note__note", output_field=BooleanField())
        msg = "Joined field references are not permitted in this query"
        with self.assertRaisesMessage(FieldError, msg):
            query.build_where(filter_expr)

    def test_filter_non_conditional(self):
        query = Query(Item)
        msg = "Cannot filter against a non-conditional expression."
        with self.assertRaisesMessage(TypeError, msg):
            query.build_where(Func(output_field=CharField()))


class TestQueryNoModel(TestCase):
    def test_rawsql_annotation(self):
        """
        Tests the annotation of a query with a raw SQL expression.\"\"\"

         \"\"\"Verifies that the raw SQL annotation is correctly executed and returns the expected boolean value.
        """
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
        query = Query(None)
        query.add_annotation(Exists(Item.objects.all()), "_check")
        result = query.get_compiler(using=DEFAULT_DB_ALIAS).execute_sql(SINGLE)
        self.assertEqual(result[0], 0)

    @skipUnlessDBFeature("supports_boolean_expr_in_select_clause")
    def test_q_annotation(self):
        """

         Tests annotating a query with a boolean expression.

        """
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
        Translates field names to their corresponding path and field objects.

        Maps a list of field names to their respective path, final field type, 
        and target field objects, facilitating field access and resolution.

        :returns: A tuple containing the path, final field, target fields, and any remaining field names.
        :rtype: tuple[list, Field, list[Field], list[str]]
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
