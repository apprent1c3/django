from django.db import connection
from django.db.models import CharField, F, Max
from django.db.models.functions import Lower
from django.test import TestCase, skipUnlessDBFeature
from django.test.utils import register_lookup

from .models import Celebrity, Fan, Staff, StaffTag, Tag


@skipUnlessDBFeature("can_distinct_on_fields")
@skipUnlessDBFeature("supports_nullable_unique_constraints")
class DistinctOnTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for testing purposes. This class method creates a hierarchy of tags, 
        staff members in different organisations, and assigns coworkers and tags to staff members. 
        Additionally, it creates celebrity and fan instances for further testing. The setup data 
        includes multiple levels of tag nesting and coworker relationships, allowing for comprehensive 
        testing of the application's functionality. All created instances are stored as class attributes 
        for easy access and reference throughout the testing process.
        """
        cls.t1 = Tag.objects.create(name="t1")
        cls.t2 = Tag.objects.create(name="t2", parent=cls.t1)
        cls.t3 = Tag.objects.create(name="t3", parent=cls.t1)
        cls.t4 = Tag.objects.create(name="t4", parent=cls.t3)
        cls.t5 = Tag.objects.create(name="t5", parent=cls.t3)

        cls.p1_o1 = Staff.objects.create(id=1, name="p1", organisation="o1")
        cls.p2_o1 = Staff.objects.create(id=2, name="p2", organisation="o1")
        cls.p3_o1 = Staff.objects.create(id=3, name="p3", organisation="o1")
        cls.p1_o2 = Staff.objects.create(id=4, name="p1", organisation="o2")
        cls.p1_o1.coworkers.add(cls.p2_o1, cls.p3_o1)
        cls.st1 = StaffTag.objects.create(staff=cls.p1_o1, tag=cls.t1)
        StaffTag.objects.create(staff=cls.p1_o1, tag=cls.t1)

        cls.celeb1 = Celebrity.objects.create(name="c1")
        cls.celeb2 = Celebrity.objects.create(name="c2")

        cls.fan1 = Fan.objects.create(fan_of=cls.celeb1)
        cls.fan2 = Fan.objects.create(fan_of=cls.celeb1)
        cls.fan3 = Fan.objects.create(fan_of=cls.celeb2)

    def test_basic_distinct_on(self):
        """QuerySet.distinct('field', ...) works"""
        # (qset, expected) tuples
        qsets = (
            (
                Staff.objects.distinct().order_by("name"),
                [self.p1_o1, self.p1_o2, self.p2_o1, self.p3_o1],
            ),
            (
                Staff.objects.distinct("name").order_by("name"),
                [self.p1_o1, self.p2_o1, self.p3_o1],
            ),
            (
                Staff.objects.distinct("organisation").order_by("organisation", "name"),
                [self.p1_o1, self.p1_o2],
            ),
            (
                Staff.objects.distinct("name", "organisation").order_by(
                    "name", "organisation"
                ),
                [self.p1_o1, self.p1_o2, self.p2_o1, self.p3_o1],
            ),
            (
                Celebrity.objects.filter(fan__in=[self.fan1, self.fan2, self.fan3])
                .distinct("name")
                .order_by("name"),
                [self.celeb1, self.celeb2],
            ),
            # Does combining querysets work?
            (
                (
                    Celebrity.objects.filter(fan__in=[self.fan1, self.fan2])
                    .distinct("name")
                    .order_by("name")
                    | Celebrity.objects.filter(fan__in=[self.fan3])
                    .distinct("name")
                    .order_by("name")
                ),
                [self.celeb1, self.celeb2],
            ),
            (StaffTag.objects.distinct("staff", "tag"), [self.st1]),
            (
                Tag.objects.order_by("parent__pk", "pk").distinct("parent"),
                (
                    [self.t2, self.t4, self.t1]
                    if connection.features.nulls_order_largest
                    else [self.t1, self.t2, self.t4]
                ),
            ),
            (
                StaffTag.objects.select_related("staff")
                .distinct("staff__name")
                .order_by("staff__name"),
                [self.st1],
            ),
            # Fetch the alphabetically first coworker for each worker
            (
                (
                    Staff.objects.distinct("id")
                    .order_by("id", "coworkers__name")
                    .values_list("id", "coworkers__name")
                ),
                [(1, "p2"), (2, "p1"), (3, "p1"), (4, None)],
            ),
        )
        for qset, expected in qsets:
            self.assertSequenceEqual(qset, expected)
            self.assertEqual(qset.count(), len(expected))

        # Combining queries with non-unique query is not allowed.
        base_qs = Celebrity.objects.all()
        msg = "Cannot combine a unique query with a non-unique query."
        with self.assertRaisesMessage(TypeError, msg):
            base_qs.distinct("id") & base_qs
        # Combining queries with different distinct_fields is not allowed.
        msg = "Cannot combine queries with different distinct fields."
        with self.assertRaisesMessage(TypeError, msg):
            base_qs.distinct("id") & base_qs.distinct("name")

        # Test join unreffing
        c1 = Celebrity.objects.distinct("greatest_fan__id", "greatest_fan__fan_of")
        self.assertIn("OUTER JOIN", str(c1.query))
        c2 = c1.distinct("pk")
        self.assertNotIn("OUTER JOIN", str(c2.query))

    def test_sliced_queryset(self):
        """

        Tests that a TypeError is raised when attempting to create distinct fields on a sliced queryset.

        The function verifies that once a slice has been taken from a queryset, it is no longer possible to create distinct fields.
        This is because slicing a queryset can lead to ambiguous or incorrect results when combined with distinct fields.

        The expected error message is checked to ensure it matches the expected output, providing a clear indication of the issue.

        """
        msg = "Cannot create distinct fields once a slice has been taken."
        with self.assertRaisesMessage(TypeError, msg):
            Staff.objects.all()[0:5].distinct("name")

    def test_transform(self):
        """
        Tests the transformation of Tag objects by creating a new Tag with a name in uppercase and verifying that it can be retrieved when ordering by lowercase name, ensuring case-insensitivity when using the Lower lookup function.
        """
        new_name = self.t1.name.upper()
        self.assertNotEqual(self.t1.name, new_name)
        Tag.objects.create(name=new_name)
        with register_lookup(CharField, Lower):
            self.assertCountEqual(
                Tag.objects.order_by().distinct("name__lower"),
                [self.t1, self.t2, self.t3, self.t4, self.t5],
            )

    def test_distinct_not_implemented_checks(self):
        # distinct + annotate not allowed
        msg = "annotate() + distinct(fields) is not implemented."
        with self.assertRaisesMessage(NotImplementedError, msg):
            Celebrity.objects.annotate(Max("id")).distinct("id")[0]
        with self.assertRaisesMessage(NotImplementedError, msg):
            Celebrity.objects.distinct("id").annotate(Max("id"))[0]

        # However this check is done only when the query executes, so you
        # can use distinct() to remove the fields before execution.
        Celebrity.objects.distinct("id").annotate(Max("id")).distinct()[0]
        # distinct + aggregate not allowed
        msg = "aggregate() + distinct(fields) not implemented."
        with self.assertRaisesMessage(NotImplementedError, msg):
            Celebrity.objects.distinct("id").aggregate(Max("id"))

    def test_distinct_on_in_ordered_subquery(self):
        """

        Tests the behavior of the distinct() and order_by() methods when used in conjunction 
        with the filter() method and an ordered subquery.

        Specifically, this test case evaluates the ordering of results when the subquery 
        is ordered in ascending and descending order by 'id', after applying distinct() 
        on 'name'. It verifies that the resulting query sets are correctly ordered by 'name' 
        and contain the expected distinct staff objects.

        """
        qs = Staff.objects.distinct("name").order_by("name", "id")
        qs = Staff.objects.filter(pk__in=qs).order_by("name")
        self.assertSequenceEqual(qs, [self.p1_o1, self.p2_o1, self.p3_o1])
        qs = Staff.objects.distinct("name").order_by("name", "-id")
        qs = Staff.objects.filter(pk__in=qs).order_by("name")
        self.assertSequenceEqual(qs, [self.p1_o2, self.p2_o1, self.p3_o1])

    def test_distinct_on_get_ordering_preserved(self):
        """
        Ordering shouldn't be cleared when distinct on fields are specified.
        refs #25081
        """
        staff = (
            Staff.objects.distinct("name")
            .order_by("name", "-organisation")
            .get(name="p1")
        )
        self.assertEqual(staff.organisation, "o2")

    def test_distinct_on_mixed_case_annotation(self):
        qs = (
            Staff.objects.annotate(
                nAmEAlIaS=F("name"),
            )
            .distinct("nAmEAlIaS")
            .order_by("nAmEAlIaS")
        )
        self.assertSequenceEqual(qs, [self.p1_o1, self.p2_o1, self.p3_o1])
