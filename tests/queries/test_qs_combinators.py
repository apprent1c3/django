import operator

from django.db import DatabaseError, NotSupportedError, connection
from django.db.models import (
    Exists,
    F,
    IntegerField,
    OuterRef,
    Subquery,
    Transform,
    Value,
)
from django.db.models.functions import Mod
from django.test import TestCase, skipIfDBFeature, skipUnlessDBFeature
from django.test.utils import CaptureQueriesContext

from .models import Author, Celebrity, ExtraInfo, Number, ReservedName


@skipUnlessDBFeature("supports_select_union")
class QuerySetSetOperationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Number.objects.bulk_create(Number(num=i, other_num=10 - i) for i in range(10))

    def assertNumbersEqual(self, queryset, expected_numbers, ordered=True):
        self.assertQuerySetEqual(
            queryset, expected_numbers, operator.attrgetter("num"), ordered
        )

    def test_simple_union(self):
        qs1 = Number.objects.filter(num__lte=1)
        qs2 = Number.objects.filter(num__gte=8)
        qs3 = Number.objects.filter(num=5)
        self.assertNumbersEqual(qs1.union(qs2, qs3), [0, 1, 5, 8, 9], ordered=False)

    @skipUnlessDBFeature("supports_select_intersection")
    def test_simple_intersection(self):
        qs1 = Number.objects.filter(num__lte=5)
        qs2 = Number.objects.filter(num__gte=5)
        qs3 = Number.objects.filter(num__gte=4, num__lte=6)
        self.assertNumbersEqual(qs1.intersection(qs2, qs3), [5], ordered=False)

    @skipUnlessDBFeature("supports_select_intersection")
    def test_intersection_with_values(self):
        """

        Tests the intersection method of a queryset with values.

        This test verifies that the intersection method correctly returns the common elements
        between two querysets, and that the resulting data can be retrieved using both the 
        values and values_list methods.

        The test case creates a single instance of a ReservedName object with the name 'a' and 
        order 2, then uses the intersection method to retrieve this instance from the 
        queryset of all ReservedName objects. It checks that the name and order of the 
        retrieved instance match the expected values, both when using the values method 
        (which returns a dictionary-like object) and the values_list method (which returns 
        a tuple-like object).

        """
        ReservedName.objects.create(name="a", order=2)
        qs1 = ReservedName.objects.all()
        reserved_name = qs1.intersection(qs1).values("name", "order", "id").get()
        self.assertEqual(reserved_name["name"], "a")
        self.assertEqual(reserved_name["order"], 2)
        reserved_name = qs1.intersection(qs1).values_list("name", "order", "id").get()
        self.assertEqual(reserved_name[:2], ("a", 2))

    @skipUnlessDBFeature("supports_select_difference")
    def test_simple_difference(self):
        """
        Tests the simple difference operation between two querysets.

        This test case verifies that the difference method correctly returns the elements 
        present in the first queryset but not in the second. In this specific test, it 
        checks that the number 5 is returned when finding the difference between querysets 
        containing numbers less than or equal to 5 and numbers less than or equal to 4, 
        respectively.

        The test requires a database feature that supports the select difference operation.

        """
        qs1 = Number.objects.filter(num__lte=5)
        qs2 = Number.objects.filter(num__lte=4)
        self.assertNumbersEqual(qs1.difference(qs2), [5], ordered=False)

    def test_union_distinct(self):
        """
        Tests the union of two querysets on the Number model, verifying that the resulting queryset contains distinct elements when the 'all' parameter is set to True and duplicates are removed when 'all' is False.
        """
        qs1 = Number.objects.all()
        qs2 = Number.objects.all()
        self.assertEqual(len(list(qs1.union(qs2, all=True))), 20)
        self.assertEqual(len(list(qs1.union(qs2))), 10)

    def test_union_none(self):
        qs1 = Number.objects.filter(num__lte=1)
        qs2 = Number.objects.filter(num__gte=8)
        qs3 = qs1.union(qs2)
        self.assertSequenceEqual(qs3.none(), [])
        self.assertNumbersEqual(qs3, [0, 1, 8, 9], ordered=False)

    def test_union_none_slice(self):
        qs1 = Number.objects.filter(num__lte=0)
        qs2 = Number.objects.none()
        qs3 = qs1.union(qs2)
        self.assertNumbersEqual(qs3[:1], [0])

    def test_union_all_none_slice(self):
        """
        Tests the functionality of the union operation on an empty QuerySet.

            This test case verifies that the union of two empty QuerySets returns an empty list.
            Additionally, it checks that taking a slice of the union result also returns an empty list.
            The test ensures that no database queries are executed during this operation, thus validating
            the expected behavior of the union operation on empty QuerySets in terms of database interaction.
        """
        qs = Number.objects.filter(id__in=[])
        with self.assertNumQueries(0):
            self.assertSequenceEqual(qs.union(qs), [])
            self.assertSequenceEqual(qs.union(qs)[0:0], [])

    def test_union_empty_filter_slice(self):
        qs1 = Number.objects.filter(num__lte=0)
        qs2 = Number.objects.filter(pk__in=[])
        qs3 = qs1.union(qs2)
        self.assertNumbersEqual(qs3[:1], [0])

    @skipUnlessDBFeature("supports_slicing_ordering_in_compound")
    def test_union_slice_compound_empty(self):
        """

        Tests the union of query sets with a slice applied to the compound result, 
        particularly when one query set is empty. Verifies that the resulting 
        query set behaves correctly when a slicing operation is applied, 
        returning the expected results.

        """
        qs1 = Number.objects.filter(num__lte=0)[:1]
        qs2 = Number.objects.none()
        qs3 = qs1.union(qs2)
        self.assertNumbersEqual(qs3[:1], [0])

    @skipUnlessDBFeature("supports_slicing_ordering_in_compound")
    def test_union_combined_slice_compound_empty(self):
        """
        Tests the union operation on two querysets, one of which is sliced, combined with an empty queryset, and verifies that the resulting queryset supports ordering and slicing. 

        Specifically, it checks that the union of a sliced queryset and an empty queryset, ordered by a specific field, returns the expected results when sliced again. This ensures that the database backend correctly handles slicing and ordering in compound queries, even when one of the querysets is empty.
        """
        qs1 = Number.objects.filter(num__lte=2)[:3]
        qs2 = Number.objects.none()
        qs3 = qs1.union(qs2)
        self.assertNumbersEqual(qs3.order_by("num")[2:3], [2])

    def test_union_slice_index(self):
        """
        Tests the union and slice index functionality of a QuerySet.

        Verifies that combining two QuerySets using the union method and then
        applying a slice index returns the expected result. The test case checks
        if a Celebrity object is correctly retrieved from the combined QuerySet
        when using an offset index.

        The test scenario includes creating Celebrity objects, filtering to ensure
        one of the QuerySets is empty, and then combining the QuerySets using union.
        The resulting combined QuerySet is then ordered by name and verified to
        contain the expected object at the specified index.
        """
        Celebrity.objects.create(name="Famous")
        c1 = Celebrity.objects.create(name="Very famous")

        qs1 = Celebrity.objects.filter(name="nonexistent")
        qs2 = Celebrity.objects.all()
        combined_qs = qs1.union(qs2).order_by("name")
        self.assertEqual(combined_qs[1], c1)

    def test_union_order_with_null_first_last(self):
        """
        Tests the ordering of a union query with null values as the first or last item.

        This test case verifies that null values are correctly ordered when using the union
        method to combine two queries. It checks the ordering when null values are placed
        at the beginning or end of the result set, ensuring that the results match the
        expected sequence of values.

        In particular, it checks that:
        - When nulls are ordered first, the null value appears at the beginning of the result set.
        - When nulls are ordered last, the null value appears at the end of the result set.

        The test uses two queries that filter on different ranges of a number field, and
        then combines the results using the union method. The ordering of the combined
        query is then checked with null values placed at the start or end of the result set.

        """
        Number.objects.filter(other_num=5).update(other_num=None)
        qs1 = Number.objects.filter(num__lte=1)
        qs2 = Number.objects.filter(num__gte=2)
        qs3 = qs1.union(qs2)
        self.assertSequenceEqual(
            qs3.order_by(
                F("other_num").asc(nulls_first=True),
            ).values_list("other_num", flat=True),
            [None, 1, 2, 3, 4, 6, 7, 8, 9, 10],
        )
        self.assertSequenceEqual(
            qs3.order_by(
                F("other_num").asc(nulls_last=True),
            ).values_list("other_num", flat=True),
            [1, 2, 3, 4, 6, 7, 8, 9, 10, None],
        )

    def test_union_nested(self):
        qs1 = Number.objects.all()
        qs2 = qs1.union(qs1)
        self.assertNumbersEqual(
            qs1.union(qs2),
            [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
            ordered=False,
        )

    @skipUnlessDBFeature("supports_select_intersection")
    def test_intersection_with_empty_qs(self):
        """

        Tests the intersection operation between various QuerySets, including empty sets.

        This test case ensures that the intersection of QuerySets behaves correctly when
        one or both of the sets are empty. It verifies that the resulting intersection
        is also empty, and that the operation works in both directions (i.e., `qs1.intersection(qs2)` and `qs2.intersection(qs1)`).

        The test covers the following scenarios:

        * Intersection of a non-empty QuerySet with an empty QuerySet
        * Intersection of an empty QuerySet with a non-empty QuerySet
        * Intersection of two empty QuerySets
        * Intersection of an empty QuerySet with itself
        * Intersection of a QuerySet with an empty QuerySet created using different methods (e.g., `objects.none()` and `filter(pk__in=[])`)

        The expected result in all cases is an empty QuerySet.

        """
        qs1 = Number.objects.all()
        qs2 = Number.objects.none()
        qs3 = Number.objects.filter(pk__in=[])
        self.assertEqual(len(qs1.intersection(qs2)), 0)
        self.assertEqual(len(qs1.intersection(qs3)), 0)
        self.assertEqual(len(qs2.intersection(qs1)), 0)
        self.assertEqual(len(qs3.intersection(qs1)), 0)
        self.assertEqual(len(qs2.intersection(qs2)), 0)
        self.assertEqual(len(qs3.intersection(qs3)), 0)

    @skipUnlessDBFeature("supports_select_difference")
    def test_difference_with_empty_qs(self):
        """

        Tests the difference operation between two querysets, focusing on its behavior with empty querysets.

        This test case verifies that subtracting an empty queryset from a non-empty one yields the original queryset,
        while subtracting a non-empty queryset from an empty one results in an empty queryset.
        Additionally, it checks that subtracting an empty queryset from itself and a non-empty queryset from itself both produce an empty queryset.

        The test covers various combinations of queryset differences to ensure correctness and expected output lengths.

        """
        qs1 = Number.objects.all()
        qs2 = Number.objects.none()
        qs3 = Number.objects.filter(pk__in=[])
        self.assertEqual(len(qs1.difference(qs2)), 10)
        self.assertEqual(len(qs1.difference(qs3)), 10)
        self.assertEqual(len(qs2.difference(qs1)), 0)
        self.assertEqual(len(qs3.difference(qs1)), 0)
        self.assertEqual(len(qs2.difference(qs2)), 0)
        self.assertEqual(len(qs3.difference(qs3)), 0)

    @skipUnlessDBFeature("supports_select_difference")
    def test_difference_with_values(self):
        """

        Test the difference operation between two querysets of ReservedName objects.

        This test case creates a ReservedName object, then uses the difference method to 
        find the objects that are in the first queryset but not in the second. It 
        verifies that the resulting object has the correct attributes and that the 
        difference method works correctly with both the values and values_list methods.

        Args: None

        Returns: None

        Raises: AssertionError if the difference operation does not produce the expected result.

        """
        ReservedName.objects.create(name="a", order=2)
        qs1 = ReservedName.objects.all()
        qs2 = ReservedName.objects.none()
        reserved_name = qs1.difference(qs2).values("name", "order", "id").get()
        self.assertEqual(reserved_name["name"], "a")
        self.assertEqual(reserved_name["order"], 2)
        reserved_name = qs1.difference(qs2).values_list("name", "order", "id").get()
        self.assertEqual(reserved_name[:2], ("a", 2))

    def test_union_with_empty_qs(self):
        """

        Tests the union operation on QuerySets, specifically when combined with empty QuerySets.

        Verifies that the union of a non-empty QuerySet and an empty QuerySet results in the original non-empty QuerySet.
        Additionally, checks the behavior when using the union method with multiple QuerySets, including the case when the all=True parameter is provided, which allows duplicates.
        Also confirms that the union of two empty QuerySets is an empty QuerySet.

        """
        qs1 = Number.objects.all()
        qs2 = Number.objects.none()
        qs3 = Number.objects.filter(pk__in=[])
        self.assertEqual(len(qs1.union(qs2)), 10)
        self.assertEqual(len(qs2.union(qs1)), 10)
        self.assertEqual(len(qs1.union(qs3)), 10)
        self.assertEqual(len(qs3.union(qs1)), 10)
        self.assertEqual(len(qs2.union(qs1, qs1, qs1)), 10)
        self.assertEqual(len(qs2.union(qs1, qs1, all=True)), 20)
        self.assertEqual(len(qs2.union(qs2)), 0)
        self.assertEqual(len(qs3.union(qs3)), 0)

    def test_empty_qs_union_with_ordered_qs(self):
        """
        Tests the behavior of combining an empty queryset with an ordered queryset using the union method.
        The purpose of this test is to verify that the resulting queryset from the union operation is correctly ordered and contains the same elements as the original ordered queryset, even when one of the querysets being combined is empty.
        """
        qs1 = Number.objects.order_by("num")
        qs2 = Number.objects.none().union(qs1).order_by("num")
        self.assertEqual(list(qs1), list(qs2))

    def test_limits(self):
        qs1 = Number.objects.all()
        qs2 = Number.objects.all()
        self.assertEqual(len(list(qs1.union(qs2)[:2])), 2)

    def test_ordering(self):
        """
        Tests the ordering of a union of two querysets containing Number objects.

        The test verifies that the union of two querysets, filtered by different number ranges,
        is correctly ordered in descending order by the 'num' field. The expected ordering
        is from highest to lowest number, regardless of the original order in the individual querysets.

        Arguments:
            None

        Returns:
            None

        Raises:
            AssertionError: If the ordered union of the querysets does not match the expected result.
        """
        qs1 = Number.objects.filter(num__lte=1)
        qs2 = Number.objects.filter(num__gte=2, num__lte=3)
        self.assertNumbersEqual(qs1.union(qs2).order_by("-num"), [3, 2, 1, 0])

    def test_ordering_by_alias(self):
        """

        Tests the ordering of a queryset by alias.

        Verifies that a query with multiple filters can be combined using union and ordered
        in descending order by an alias.

        The test case checks if numbers between 0 and 3 can be ordered in descending order,
        with the resulting queryset being [3, 2, 1, 0].

        """
        qs1 = Number.objects.filter(num__lte=1).values(alias=F("num"))
        qs2 = Number.objects.filter(num__gte=2, num__lte=3).values(alias=F("num"))
        self.assertQuerySetEqual(
            qs1.union(qs2).order_by("-alias"),
            [3, 2, 1, 0],
            operator.itemgetter("alias"),
        )

    def test_ordering_by_f_expression(self):
        qs1 = Number.objects.filter(num__lte=1)
        qs2 = Number.objects.filter(num__gte=2, num__lte=3)
        self.assertNumbersEqual(qs1.union(qs2).order_by(F("num").desc()), [3, 2, 1, 0])

    def test_ordering_by_f_expression_and_alias(self):
        """

        Tests that Django ORM's union and ordering functionality works as expected when using 
        F-expressions and aliasing.

        Verifies that the resulting query set is ordered correctly in descending order 
        by the aliased field, and that NULL values can be placed at the end of the result 
        set using the `nulls_last` parameter.

        """
        qs1 = Number.objects.filter(num__lte=1).values(alias=F("other_num"))
        qs2 = Number.objects.filter(num__gte=2, num__lte=3).values(alias=F("other_num"))
        self.assertQuerySetEqual(
            qs1.union(qs2).order_by(F("alias").desc()),
            [10, 9, 8, 7],
            operator.itemgetter("alias"),
        )
        Number.objects.create(num=-1)
        self.assertQuerySetEqual(
            qs1.union(qs2).order_by(F("alias").desc(nulls_last=True)),
            [10, 9, 8, 7, None],
            operator.itemgetter("alias"),
        )

    def test_union_with_values(self):
        ReservedName.objects.create(name="a", order=2)
        qs1 = ReservedName.objects.all()
        reserved_name = qs1.union(qs1).values("name", "order", "id").get()
        self.assertEqual(reserved_name["name"], "a")
        self.assertEqual(reserved_name["order"], 2)
        reserved_name = qs1.union(qs1).values_list("name", "order", "id").get()
        self.assertEqual(reserved_name[:2], ("a", 2))
        # List of columns can be changed.
        reserved_name = qs1.union(qs1).values_list("order").get()
        self.assertEqual(reserved_name, (2,))

    def test_union_with_two_annotated_values_list(self):
        qs1 = (
            Number.objects.filter(num=1)
            .annotate(
                count=Value(0, IntegerField()),
            )
            .values_list("num", "count")
        )
        qs2 = (
            Number.objects.filter(num=2)
            .values("pk")
            .annotate(
                count=F("num"),
            )
            .annotate(
                num=Value(1, IntegerField()),
            )
            .values_list("num", "count")
        )
        self.assertCountEqual(qs1.union(qs2), [(1, 0), (1, 2)])

    def test_union_with_field_and_annotation_values(self):
        """
        Tests the union of two querysets with annotated fields.

        Verifies that the union of two querysets, each containing a field and an annotated value, 
        produces the expected combined result, regardless of the order of fields in the querysets.

        The test querysets are generated by filtering objects with specific values, annotating them with a 
        constant value, and then retrieving specific fields. The resulting union is then validated against 
        the expected output, ensuring that the querysets are correctly combined and the resulting tuples 
        contain the correct field values in the expected order.
        """
        qs1 = (
            Number.objects.filter(num=1)
            .annotate(
                zero=Value(0, IntegerField()),
            )
            .values_list("num", "zero")
        )
        qs2 = (
            Number.objects.filter(num=2)
            .annotate(
                zero=Value(0, IntegerField()),
            )
            .values_list("zero", "num")
        )
        self.assertCountEqual(qs1.union(qs2), [(1, 0), (0, 2)])

    def test_union_with_extra_and_values_list(self):
        """
        Tests the union operation between two QuerySets, one with an extra select value and a values_list, and another with only an extra select value, verifying that the resulting QuerySet contains all expected tuples in any order.
        """
        qs1 = (
            Number.objects.filter(num=1)
            .extra(
                select={"count": 0},
            )
            .values_list("num", "count")
        )
        qs2 = Number.objects.filter(num=2).extra(select={"count": 1})
        self.assertCountEqual(qs1.union(qs2), [(1, 0), (2, 1)])

    def test_union_with_values_list_on_annotated_and_unannotated(self):
        ReservedName.objects.create(name="rn1", order=1)
        qs1 = Number.objects.annotate(
            has_reserved_name=Exists(ReservedName.objects.filter(order=OuterRef("num")))
        ).filter(has_reserved_name=True)
        qs2 = Number.objects.filter(num=9)
        self.assertCountEqual(qs1.union(qs2).values_list("num", flat=True), [1, 9])

    def test_union_with_values_list_and_order(self):
        ReservedName.objects.bulk_create(
            [
                ReservedName(name="rn1", order=7),
                ReservedName(name="rn2", order=5),
                ReservedName(name="rn0", order=6),
                ReservedName(name="rn9", order=-1),
            ]
        )
        qs1 = ReservedName.objects.filter(order__gte=6)
        qs2 = ReservedName.objects.filter(order__lte=5)
        union_qs = qs1.union(qs2)
        for qs, expected_result in (
            # Order by a single column.
            (union_qs.order_by("-pk").values_list("order", flat=True), [-1, 6, 5, 7]),
            (union_qs.order_by("pk").values_list("order", flat=True), [7, 5, 6, -1]),
            (union_qs.values_list("order", flat=True).order_by("-pk"), [-1, 6, 5, 7]),
            (union_qs.values_list("order", flat=True).order_by("pk"), [7, 5, 6, -1]),
            # Order by multiple columns.
            (
                union_qs.order_by("-name", "pk").values_list("order", flat=True),
                [-1, 5, 7, 6],
            ),
            (
                union_qs.values_list("order", flat=True).order_by("-name", "pk"),
                [-1, 5, 7, 6],
            ),
        ):
            with self.subTest(qs=qs):
                self.assertEqual(list(qs), expected_result)

    def test_union_with_values_list_and_order_on_annotation(self):
        """

        Tests the union operation on two annotated querysets with ordering.

        This test case verifies that the union operation on two querysets, each annotated with a value and a multiplier,
        produces the expected results when ordered by the annotated value and the 'num' field.
        It also checks that the ordering works correctly when using an expression that involves the annotation and multiplier.

        The test case covers scenarios where the querysets are filtered by different conditions, and the union operation is
        performed with and without reordering the results based on an expression involving the annotated fields.

        """
        qs1 = Number.objects.annotate(
            annotation=Value(-1),
            multiplier=F("annotation"),
        ).filter(num__gte=6)
        qs2 = Number.objects.annotate(
            annotation=Value(2),
            multiplier=F("annotation"),
        ).filter(num__lte=5)
        self.assertSequenceEqual(
            qs1.union(qs2).order_by("annotation", "num").values_list("num", flat=True),
            [6, 7, 8, 9, 0, 1, 2, 3, 4, 5],
        )
        self.assertQuerySetEqual(
            qs1.union(qs2)
            .order_by(
                F("annotation") * F("multiplier"),
                "num",
            )
            .values("num"),
            [6, 7, 8, 9, 0, 1, 2, 3, 4, 5],
            operator.itemgetter("num"),
        )

    def test_order_by_annotation_transform(self):
        """
        Tests if an ordering combined query by a transform raises a NotImplementedError.

        The test verifies that attempting to order a union of queries using an annotated
        transform results in an error, specifically a NotImplementedError, due to the
        current unimplemented functionality of ordering combined queries by transforms.

        It utilizes a custom transform, Mod2, derived from the Transform class, to create
        an annotation with a custom output field. The test then attempts to order the
        union of two queries annotated with this transform, expecting the raise of a
        NotImplementedError with a specific error message indicating the feature is not
        yet supported. This check ensures the correct handling of trying to order queries
        in such a manner, adhering to the expected behavior of the system in this scenario.
        """
        class Mod2(Mod, Transform):
            def __init__(self, expr):
                super().__init__(expr, 2)

        output_field = IntegerField()
        output_field.register_lookup(Mod2, "mod2")
        qs1 = Number.objects.annotate(
            annotation=Value(1, output_field=output_field),
        )
        qs2 = Number.objects.annotate(
            annotation=Value(2, output_field=output_field),
        )
        msg = "Ordering combined queries by transforms is not implemented."
        with self.assertRaisesMessage(NotImplementedError, msg):
            list(qs1.union(qs2).order_by("annotation__mod2"))

    def test_union_with_select_related_and_order(self):
        """
        Tests the union of two querysets that have been filtered from a base queryset.
        The base queryset has been optimized with select_related to fetch related 'extra' objects and ordered to ensure a predictable result set.
        This function verifies that the union operation properly combines and orders the results of the two querysets by primary key, and that the resulting queryset only contains the expected objects.
        """
        e1 = ExtraInfo.objects.create(value=7, info="e1")
        a1 = Author.objects.create(name="a1", num=1, extra=e1)
        a2 = Author.objects.create(name="a2", num=3, extra=e1)
        Author.objects.create(name="a3", num=2, extra=e1)
        base_qs = Author.objects.select_related("extra").order_by()
        qs1 = base_qs.filter(name="a1")
        qs2 = base_qs.filter(name="a2")
        self.assertSequenceEqual(qs1.union(qs2).order_by("pk"), [a1, a2])

    @skipUnlessDBFeature("supports_slicing_ordering_in_compound")
    def test_union_with_select_related_and_first(self):
        """

        Tests that a union of two querysets with select_related and ordering
        returns the expected result when retrieving the first element.

        This test case covers the scenario where two querysets are combined using
        the union method, and then ordered by a specific field. It verifies that
        the first element of the resulting queryset is the expected one.

        The test involves creating Author objects with related ExtraInfo objects,
        and then constructing querysets to retrieve these objects. The union of
        these querysets is then ordered and the first element is retrieved,
        which is compared to the expected result.

        """
        e1 = ExtraInfo.objects.create(value=7, info="e1")
        a1 = Author.objects.create(name="a1", num=1, extra=e1)
        Author.objects.create(name="a2", num=3, extra=e1)
        base_qs = Author.objects.select_related("extra").order_by()
        qs1 = base_qs.filter(name="a1")
        qs2 = base_qs.filter(name="a2")
        self.assertEqual(qs1.union(qs2).order_by("name").first(), a1)

    def test_union_with_first(self):
        """
        Tests that the :meth:`union` method of a QuerySet returns the first object from the combined querysets, 
        in this case an :class:`Author` instance, when its conditions match. 
        The test verifies that the union operation preserves the queryset order and returns the correct object. 
        It specifically checks the scenario where the union involves an author object that has an associated 
        :class:`ExtraInfo` object.
        """
        e1 = ExtraInfo.objects.create(value=7, info="e1")
        a1 = Author.objects.create(name="a1", num=1, extra=e1)
        base_qs = Author.objects.order_by()
        qs1 = base_qs.filter(name="a1")
        qs2 = base_qs.filter(name="a2")
        self.assertEqual(qs1.union(qs2).first(), a1)

    def test_union_multiple_models_with_values_list_and_order(self):
        reserved_name = ReservedName.objects.create(name="rn1", order=0)
        qs1 = Celebrity.objects.all()
        qs2 = ReservedName.objects.all()
        self.assertSequenceEqual(
            qs1.union(qs2).order_by("name").values_list("pk", flat=True),
            [reserved_name.pk],
        )

    def test_union_multiple_models_with_values_list_and_order_by_extra_select(self):
        """
        Tests the union operation on multiple QuerySets with extra select and ordering applied.

        Verifies that the union of two QuerySets, one from the Celebrity model and the other from the ReservedName model, 
        with an extra select column 'extra_name' and ordered by this column, returns the expected results. The test case 
        also checks that the values_list method correctly returns a list of primary keys when 'flat=True' is specified.

        The scenario specifically tests the case where one ReservedName instance is created with a specific name and order, 
        and the union operation is applied to retrieve the primary key of this instance, demonstrating the functionality 
        of combining and ordering complex queries with extra selects and values list retrieval.
        """
        reserved_name = ReservedName.objects.create(name="rn1", order=0)
        qs1 = Celebrity.objects.extra(select={"extra_name": "name"})
        qs2 = ReservedName.objects.extra(select={"extra_name": "name"})
        self.assertSequenceEqual(
            qs1.union(qs2).order_by("extra_name").values_list("pk", flat=True),
            [reserved_name.pk],
        )

    def test_union_multiple_models_with_values_list_and_annotations(self):
        """
        This function tests the union operation between two querysets, where each queryset is obtained from a different model and contains annotated values. It verifies that the combined result is correctly ordered by the 'order' field, with the annotated 'row_type' supporting the distinction between the models.
        """
        ReservedName.objects.create(name="rn1", order=10)
        Celebrity.objects.create(name="c1")
        qs1 = ReservedName.objects.annotate(row_type=Value("rn")).values_list(
            "name", "order", "row_type"
        )
        qs2 = Celebrity.objects.annotate(
            row_type=Value("cb"), order=Value(-10)
        ).values_list("name", "order", "row_type")
        self.assertSequenceEqual(
            qs1.union(qs2).order_by("order"),
            [("c1", -10, "cb"), ("rn1", 10, "rn")],
        )

    def test_union_in_subquery(self):
        """

        Tests the union of subqueries in the database query.

        Verifies that using the union operator in a subquery within an annotation
        returns the correct results. In this case, it checks that the correct
        ReservedName objects are returned when their order is either greater than 7 or less than 2.
        The test creates sample ReservedName objects, then uses two different queries
        to filter Number objects based on these conditions. It then checks that the
        correct orders are returned from the annotation.

        """
        ReservedName.objects.bulk_create(
            [
                ReservedName(name="rn1", order=8),
                ReservedName(name="rn2", order=1),
                ReservedName(name="rn3", order=5),
            ]
        )
        qs1 = Number.objects.filter(num__gt=7, num=OuterRef("order"))
        qs2 = Number.objects.filter(num__lt=2, num=OuterRef("order"))
        self.assertCountEqual(
            ReservedName.objects.annotate(
                number=Subquery(qs1.union(qs2).values("num")),
            )
            .filter(number__isnull=False)
            .values_list("order", flat=True),
            [8, 1],
        )

    def test_union_in_subquery_related_outerref(self):
        e1 = ExtraInfo.objects.create(value=7, info="e3")
        e2 = ExtraInfo.objects.create(value=5, info="e2")
        e3 = ExtraInfo.objects.create(value=1, info="e1")
        Author.objects.bulk_create(
            [
                Author(name="a1", num=1, extra=e1),
                Author(name="a2", num=3, extra=e2),
                Author(name="a3", num=2, extra=e3),
            ]
        )
        qs1 = ExtraInfo.objects.order_by().filter(value=OuterRef("num"))
        qs2 = ExtraInfo.objects.order_by().filter(value__lt=OuterRef("extra__value"))
        qs = (
            Author.objects.annotate(
                info=Subquery(qs1.union(qs2).values("info")[:1]),
            )
            .filter(info__isnull=False)
            .values_list("name", flat=True)
        )
        self.assertCountEqual(qs, ["a1", "a2"])
        # Combined queries don't mutate.
        self.assertCountEqual(qs, ["a1", "a2"])

    @skipUnlessDBFeature("supports_slicing_ordering_in_compound")
    def test_union_in_with_ordering(self):
        """
        Tests the union of two querysets with ordering, ensuring the resulting queryset is correctly ordered and contains the expected values.

        Specifically, this test verifies that when combining two querysets, one with values greater than 7 and the other with values less than 2, the resulting union is correctly ordered, and the exclude operation correctly filters out the expected values.

        The test asserts that the numbers 2 through 7 are not included in the resulting queryset, demonstrating the proper application of the union and exclude operations with ordering.
        """
        qs1 = Number.objects.filter(num__gt=7).order_by("num")
        qs2 = Number.objects.filter(num__lt=2).order_by("num")
        self.assertNumbersEqual(
            Number.objects.exclude(id__in=qs1.union(qs2).values("id")),
            [2, 3, 4, 5, 6, 7],
            ordered=False,
        )

    @skipUnlessDBFeature(
        "supports_slicing_ordering_in_compound", "allow_sliced_subqueries_with_in"
    )
    def test_union_in_with_ordering_and_slice(self):
        qs1 = Number.objects.filter(num__gt=7).order_by("num")[:1]
        qs2 = Number.objects.filter(num__lt=2).order_by("-num")[:1]
        self.assertNumbersEqual(
            Number.objects.exclude(id__in=qs1.union(qs2).values("id")),
            [0, 2, 3, 4, 5, 6, 7, 9],
            ordered=False,
        )

    def test_count_union(self):
        qs1 = Number.objects.filter(num__lte=1).values("num")
        qs2 = Number.objects.filter(num__gte=2, num__lte=3).values("num")
        self.assertEqual(qs1.union(qs2).count(), 4)

    def test_count_union_empty_result(self):
        qs = Number.objects.filter(pk__in=[])
        self.assertEqual(qs.union(qs).count(), 0)

    def test_count_union_with_select_related(self):
        e1 = ExtraInfo.objects.create(value=1, info="e1")
        Author.objects.create(name="a1", num=1, extra=e1)
        qs = Author.objects.select_related("extra").order_by()
        self.assertEqual(qs.union(qs).count(), 1)

    @skipUnlessDBFeature("supports_select_difference")
    def test_count_difference(self):
        qs1 = Number.objects.filter(num__lt=10)
        qs2 = Number.objects.filter(num__lt=9)
        self.assertEqual(qs1.difference(qs2).count(), 1)

    @skipUnlessDBFeature("supports_select_intersection")
    def test_count_intersection(self):
        qs1 = Number.objects.filter(num__gte=5)
        qs2 = Number.objects.filter(num__lte=5)
        self.assertEqual(qs1.intersection(qs2).count(), 1)

    def test_exists_union(self):
        """
        Test that the union of two queries is executed as a single query with a LIMIT, 
        without quoting the primary key column, when checking for existence.

        This test case verifies that the `exists()` method on a union of two querysets 
        returns the correct result and that the underlying SQL query is optimized for 
        existence checking by limiting the result to a single row. It also ensures that 
        the primary key column is not unnecessarily quoted in the generated SQL.

        The test uses two querysets filtering numbers greater than or equal to 5 and 
        less than or equal to 5, and then checks that their union exists and that only 
        one database query is executed to determine existence.
        """
        qs1 = Number.objects.filter(num__gte=5)
        qs2 = Number.objects.filter(num__lte=5)
        with CaptureQueriesContext(connection) as context:
            self.assertIs(qs1.union(qs2).exists(), True)
        captured_queries = context.captured_queries
        self.assertEqual(len(captured_queries), 1)
        captured_sql = captured_queries[0]["sql"]
        self.assertNotIn(
            connection.ops.quote_name(Number._meta.pk.column),
            captured_sql,
        )
        self.assertEqual(
            captured_sql.count(connection.ops.limit_offset_sql(None, 1)), 1
        )

    def test_exists_union_empty_result(self):
        """

        Tests that the union of two empty querysets results in an empty queryset.

        Verifies that when two querysets, both resulting from filtering on an empty list of primary keys, 
        are combined using the union method, the resulting queryset does not contain any objects.

        """
        qs = Number.objects.filter(pk__in=[])
        self.assertIs(qs.union(qs).exists(), False)

    @skipUnlessDBFeature("supports_select_intersection")
    def test_exists_intersection(self):
        qs1 = Number.objects.filter(num__gt=5)
        qs2 = Number.objects.filter(num__lt=5)
        self.assertIs(qs1.intersection(qs1).exists(), True)
        self.assertIs(qs1.intersection(qs2).exists(), False)

    @skipUnlessDBFeature("supports_select_difference")
    def test_exists_difference(self):
        qs1 = Number.objects.filter(num__gte=5)
        qs2 = Number.objects.filter(num__gte=3)
        self.assertIs(qs1.difference(qs2).exists(), False)
        self.assertIs(qs2.difference(qs1).exists(), True)

    def test_get_union(self):
        """
        Tests the union method on a QuerySet, ensuring that the result contains the expected elements.

            Specifically, this test checks that the union of a QuerySet with itself returns the original QuerySet,
            and that the resulting query can be used to retrieve the expected object.

            The test uses a QuerySet of Number objects, filtered by a specific number, and verifies that the
            resulting union contains the expected number.

        """
        qs = Number.objects.filter(num=2)
        self.assertEqual(qs.union(qs).get().num, 2)

    @skipUnlessDBFeature("supports_select_difference")
    def test_get_difference(self):
        """
        Tests the difference method of a QuerySet, which returns a new QuerySet containing elements that are in the first QuerySet but not in the second.

        This test case checks if the difference between two QuerySets can be correctly computed, specifically in cases where one QuerySet excludes certain elements. It verifies that the resulting QuerySet contains the expected element.

        Note: This test is skipped unless the database feature 'supports_select_difference' is supported.
        """
        qs1 = Number.objects.all()
        qs2 = Number.objects.exclude(num=2)
        self.assertEqual(qs1.difference(qs2).get().num, 2)

    @skipUnlessDBFeature("supports_select_intersection")
    def test_get_intersection(self):
        """
        ..: Test that the QuerySet intersection method returns the correct result.

            This test checks if the intersection of two QuerySets returns the expected
            result, specifically the object that is common to both QuerySets. It
            creates two QuerySets, one with all objects and one with objects filtered
            by a specific condition, and then tests if the intersection of these two
            QuerySets contains the expected object. 

            :return: None 
            :raises: AssertionError if the intersection result is not as expected.
        """
        qs1 = Number.objects.all()
        qs2 = Number.objects.filter(num=2)
        self.assertEqual(qs1.intersection(qs2).get().num, 2)

    @skipUnlessDBFeature("supports_slicing_ordering_in_compound")
    def test_ordering_subqueries(self):
        qs1 = Number.objects.order_by("num")[:2]
        qs2 = Number.objects.order_by("-num")[:2]
        self.assertNumbersEqual(qs1.union(qs2).order_by("-num")[:4], [9, 8, 1, 0])

    @skipIfDBFeature("supports_slicing_ordering_in_compound")
    def test_unsupported_ordering_slicing_raises_db_error(self):
        qs1 = Number.objects.all()
        qs2 = Number.objects.all()
        qs3 = Number.objects.all()
        msg = "LIMIT/OFFSET not allowed in subqueries of compound statements"
        with self.assertRaisesMessage(DatabaseError, msg):
            list(qs1.union(qs2[:10]))
        msg = "ORDER BY not allowed in subqueries of compound statements"
        with self.assertRaisesMessage(DatabaseError, msg):
            list(qs1.order_by("id").union(qs2))
        with self.assertRaisesMessage(DatabaseError, msg):
            list(qs1.union(qs2).order_by("id").union(qs3))

    @skipIfDBFeature("supports_select_intersection")
    def test_unsupported_intersection_raises_db_error(self):
        """
        Tests that attempting to use the intersection method on a queryset raises a NotSupportedError
        when the underlying database does not support the intersection operation.

        This test case covers the scenario where the database backend does not have built-in support
        for set intersection operations, ensuring that the correct error is raised with a descriptive
        error message.
        """
        qs1 = Number.objects.all()
        qs2 = Number.objects.all()
        msg = "intersection is not supported on this database backend"
        with self.assertRaisesMessage(NotSupportedError, msg):
            list(qs1.intersection(qs2))

    def test_combining_multiple_models(self):
        """
        Tests the ability to combine multiple models into a single query.

        This function checks if a union of two querysets, one from the Number model and
        one from the ReservedName model, returns the correct ordered result. It verifies
        that the resulting list contains the expected values, demonstrating that the
        querysets are properly combined and sorted.

        The test case creates a ReservedName object and uses it to test the union
        operation, ensuring that the order_by clause correctly sorts the combined
        results by the 'num' field, which is present in the Number model's queryset.
        """
        ReservedName.objects.create(name="99 little bugs", order=99)
        qs1 = Number.objects.filter(num=1).values_list("num", flat=True)
        qs2 = ReservedName.objects.values_list("order")
        self.assertEqual(list(qs1.union(qs2).order_by("num")), [1, 99])

    def test_order_raises_on_non_selected_column(self):
        qs1 = (
            Number.objects.filter()
            .annotate(
                annotation=Value(1, IntegerField()),
            )
            .values("annotation", num2=F("num"))
        )
        qs2 = Number.objects.filter().values("id", "num")
        # Should not raise
        list(qs1.union(qs2).order_by("annotation"))
        list(qs1.union(qs2).order_by("num2"))
        msg = "ORDER BY term does not match any column in the result set"
        # 'id' is not part of the select
        with self.assertRaisesMessage(DatabaseError, msg):
            list(qs1.union(qs2).order_by("id"))
        # 'num' got realiased to num2
        with self.assertRaisesMessage(DatabaseError, msg):
            list(qs1.union(qs2).order_by("num"))
        with self.assertRaisesMessage(DatabaseError, msg):
            list(qs1.union(qs2).order_by(F("num")))
        with self.assertRaisesMessage(DatabaseError, msg):
            list(qs1.union(qs2).order_by(F("num").desc()))
        # switched order, now 'exists' again:
        list(qs2.union(qs1).order_by("num"))

    @skipUnlessDBFeature("supports_select_difference", "supports_select_intersection")
    def test_qs_with_subcompound_qs(self):
        qs1 = Number.objects.all()
        qs2 = Number.objects.intersection(Number.objects.filter(num__gt=1))
        self.assertEqual(qs1.difference(qs2).count(), 2)

    def test_order_by_same_type(self):
        qs = Number.objects.all()
        union = qs.union(qs)
        numbers = list(range(10))
        self.assertNumbersEqual(union.order_by("num"), numbers)
        self.assertNumbersEqual(union.order_by("other_num"), reversed(numbers))

    def test_unsupported_operations_on_combined_qs(self):
        """
        :param msg: Testing unsupported operations on combined QuerySets.
        :raises NotSupportedError: When attempting to perform certain operations after using a QuerySet combinator function.
        :description: This test checks that calling various QuerySet methods (e.g. alias, annotate, defer) after using a combinator function (union, difference, intersection) raises a NotSupportedError as expected.
        :note: The test covers all supported combinator functions (union, difference, intersection) depending on the database features, and checks that attempting to call these operations results in the correct error message.
        :preconditions: A QuerySet of Number objects.
        :tested operations: alias, annotate, defer, delete, distinct, exclude, extra, filter, only, prefetch_related, select_related, update, contains.
        """
        qs = Number.objects.all()
        msg = "Calling QuerySet.%s() after %s() is not supported."
        combinators = ["union"]
        if connection.features.supports_select_difference:
            combinators.append("difference")
        if connection.features.supports_select_intersection:
            combinators.append("intersection")
        for combinator in combinators:
            for operation in (
                "alias",
                "annotate",
                "defer",
                "delete",
                "distinct",
                "exclude",
                "extra",
                "filter",
                "only",
                "prefetch_related",
                "select_related",
                "update",
            ):
                with self.subTest(combinator=combinator, operation=operation):
                    with self.assertRaisesMessage(
                        NotSupportedError,
                        msg % (operation, combinator),
                    ):
                        getattr(getattr(qs, combinator)(qs), operation)()
            with self.assertRaisesMessage(
                NotSupportedError,
                msg % ("contains", combinator),
            ):
                obj = Number.objects.first()
                getattr(qs, combinator)(qs).contains(obj)

    def test_get_with_filters_unsupported_on_combined_qs(self):
        qs = Number.objects.all()
        msg = "Calling QuerySet.get(...) with filters after %s() is not supported."
        combinators = ["union"]
        if connection.features.supports_select_difference:
            combinators.append("difference")
        if connection.features.supports_select_intersection:
            combinators.append("intersection")
        for combinator in combinators:
            with self.subTest(combinator=combinator):
                with self.assertRaisesMessage(NotSupportedError, msg % combinator):
                    getattr(qs, combinator)(qs).get(num=2)

    def test_operator_on_combined_qs_error(self):
        """
        Tests the behavior of binary logical operators when used with a combined queryset.

        The test checks that using the bitwise OR, AND, or XOR operators with a queryset 
        that has been combined using union, difference, or intersection raises a TypeError. 
        This ensures that the operators are not supported with combined querysets, as 
        expected, and provides a clear error message instead. 
        The test covers both cases where the combined queryset is the first or second 
        argument to the binary operator.
        """
        qs = Number.objects.all()
        msg = "Cannot use %s operator with combined queryset."
        combinators = ["union"]
        if connection.features.supports_select_difference:
            combinators.append("difference")
        if connection.features.supports_select_intersection:
            combinators.append("intersection")
        operators = [
            ("|", operator.or_),
            ("&", operator.and_),
            ("^", operator.xor),
        ]
        for combinator in combinators:
            combined_qs = getattr(qs, combinator)(qs)
            for operator_, operator_func in operators:
                with self.subTest(combinator=combinator):
                    with self.assertRaisesMessage(TypeError, msg % operator_):
                        operator_func(qs, combined_qs)
                    with self.assertRaisesMessage(TypeError, msg % operator_):
                        operator_func(combined_qs, qs)
