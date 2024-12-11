import datetime
import pickle
import sys
import unittest
from operator import attrgetter

from django.core.exceptions import EmptyResultSet, FieldError, FullResultSet
from django.db import DEFAULT_DB_ALIAS, connection
from django.db.models import CharField, Count, Exists, F, Max, OuterRef, Q
from django.db.models.expressions import RawSQL
from django.db.models.functions import ExtractYear, Length, LTrim
from django.db.models.sql.constants import LOUTER
from django.db.models.sql.where import AND, OR, NothingNode, WhereNode
from django.test import SimpleTestCase, TestCase, skipUnlessDBFeature
from django.test.utils import CaptureQueriesContext, register_lookup

from .models import (
    FK1,
    Annotation,
    Article,
    Author,
    BaseA,
    BaseUser,
    Book,
    CategoryItem,
    CategoryRelationship,
    Celebrity,
    Channel,
    Chapter,
    Child,
    ChildObjectA,
    Classroom,
    CommonMixedCaseForeignKeys,
    Company,
    Cover,
    CustomPk,
    CustomPkTag,
    DateTimePK,
    Detail,
    DumbCategory,
    Eaten,
    Employment,
    ExtraInfo,
    Fan,
    Food,
    Identifier,
    Individual,
    Item,
    Job,
    JobResponsibilities,
    Join,
    LeafA,
    LeafB,
    LoopX,
    LoopZ,
    ManagedModel,
    Member,
    MixedCaseDbColumnCategoryItem,
    MixedCaseFieldCategoryItem,
    ModelA,
    ModelB,
    ModelC,
    ModelD,
    MyObject,
    NamedCategory,
    Node,
    Note,
    NullableName,
    Number,
    ObjectA,
    ObjectB,
    ObjectC,
    OneToOneCategory,
    Order,
    OrderItem,
    Page,
    Paragraph,
    Person,
    Plaything,
    PointerA,
    Program,
    ProxyCategory,
    ProxyObjectA,
    ProxyObjectB,
    Ranking,
    Related,
    RelatedIndividual,
    RelatedObject,
    Report,
    ReportComment,
    ReservedName,
    Responsibility,
    School,
    SharedConnection,
    SimpleCategory,
    SingleObject,
    SpecialCategory,
    Staff,
    StaffUser,
    Student,
    Tag,
    Task,
    Teacher,
    Ticket21203Child,
    Ticket21203Parent,
    Ticket23605A,
    Ticket23605B,
    Ticket23605C,
    TvChef,
    Valid,
    X,
)


class UnpickleableError(Exception):
    def __reduce__(self):
        raise type(self)("Cannot pickle.")


class Queries1Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.nc1 = generic = NamedCategory.objects.create(name="Generic")
        cls.t1 = Tag.objects.create(name="t1", category=generic)
        cls.t2 = Tag.objects.create(name="t2", parent=cls.t1, category=generic)
        cls.t3 = Tag.objects.create(name="t3", parent=cls.t1)
        cls.t4 = Tag.objects.create(name="t4", parent=cls.t3)
        cls.t5 = Tag.objects.create(name="t5", parent=cls.t3)

        cls.n1 = Note.objects.create(note="n1", misc="foo", id=1)
        cls.n2 = Note.objects.create(note="n2", misc="bar", id=2)
        cls.n3 = Note.objects.create(note="n3", misc="foo", id=3, negate=False)

        cls.ann1 = Annotation.objects.create(name="a1", tag=cls.t1)
        cls.ann1.notes.add(cls.n1)
        ann2 = Annotation.objects.create(name="a2", tag=cls.t4)
        ann2.notes.add(cls.n2, cls.n3)

        # Create these out of order so that sorting by 'id' will be different to sorting
        # by 'info'. Helps detect some problems later.
        cls.e2 = ExtraInfo.objects.create(
            info="e2", note=cls.n2, value=41, filterable=False
        )
        e1 = ExtraInfo.objects.create(info="e1", note=cls.n1, value=42)

        cls.a1 = Author.objects.create(name="a1", num=1001, extra=e1)
        cls.a2 = Author.objects.create(name="a2", num=2002, extra=e1)
        cls.a3 = Author.objects.create(name="a3", num=3003, extra=cls.e2)
        cls.a4 = Author.objects.create(name="a4", num=4004, extra=cls.e2)

        cls.time1 = datetime.datetime(2007, 12, 19, 22, 25, 0)
        cls.time2 = datetime.datetime(2007, 12, 19, 21, 0, 0)
        time3 = datetime.datetime(2007, 12, 20, 22, 25, 0)
        time4 = datetime.datetime(2007, 12, 20, 21, 0, 0)
        cls.i1 = Item.objects.create(
            name="one",
            created=cls.time1,
            modified=cls.time1,
            creator=cls.a1,
            note=cls.n3,
        )
        cls.i1.tags.set([cls.t1, cls.t2])
        cls.i2 = Item.objects.create(
            name="two", created=cls.time2, creator=cls.a2, note=cls.n2
        )
        cls.i2.tags.set([cls.t1, cls.t3])
        cls.i3 = Item.objects.create(
            name="three", created=time3, creator=cls.a2, note=cls.n3
        )
        cls.i4 = Item.objects.create(
            name="four", created=time4, creator=cls.a4, note=cls.n3
        )
        cls.i4.tags.set([cls.t4])

        cls.r1 = Report.objects.create(name="r1", creator=cls.a1)
        cls.r2 = Report.objects.create(name="r2", creator=cls.a3)
        cls.r3 = Report.objects.create(name="r3")

        # Ordering by 'rank' gives us rank2, rank1, rank3. Ordering by the Meta.ordering
        # will be rank3, rank2, rank1.
        cls.rank1 = Ranking.objects.create(rank=2, author=cls.a2)

        cls.c1 = Cover.objects.create(title="first", item=cls.i4)
        cls.c2 = Cover.objects.create(title="second", item=cls.i2)

    def test_subquery_condition(self):
        """

        Tests the correctness of subquery conditions in database queries.

        This test case evaluates the behavior of nested subqueries and ensures that 
        the generated SQL query is correctly aliased and formatted. Specifically, 
        it verifies that the subquery aliases are properly assigned and that the 
        query contains the expected table references.

        The test covers scenarios where subqueries are nested, filtered, and 
        combined to ensure the robustness of the query generation mechanism.

        """
        qs1 = Tag.objects.filter(pk__lte=0)
        qs2 = Tag.objects.filter(parent__in=qs1)
        qs3 = Tag.objects.filter(parent__in=qs2)
        self.assertEqual(qs3.query.subq_aliases, {"T", "U", "V"})
        self.assertIn("v0", str(qs3.query).lower())
        qs4 = qs3.filter(parent__in=qs1)
        self.assertEqual(qs4.query.subq_aliases, {"T", "U", "V"})
        # It is possible to reuse U for the second subquery, no need to use W.
        self.assertNotIn("w0", str(qs4.query).lower())
        # So, 'U0."id"' is referenced in SELECT and WHERE twice.
        self.assertEqual(str(qs4.query).lower().count("u0."), 4)

    def test_ticket1050(self):
        """
        Test the behavior of filtering Items by null tags, verifying that both tags__isnull=True and tags__id__isnull=True correctly return Items without any associated tags, with a specific expectation of returning a single Item (i3) in this test scenario.
        """
        self.assertSequenceEqual(
            Item.objects.filter(tags__isnull=True),
            [self.i3],
        )
        self.assertSequenceEqual(
            Item.objects.filter(tags__id__isnull=True),
            [self.i3],
        )

    def test_ticket1801(self):
        self.assertSequenceEqual(
            Author.objects.filter(item=self.i2),
            [self.a2],
        )
        self.assertSequenceEqual(
            Author.objects.filter(item=self.i3),
            [self.a2],
        )
        self.assertSequenceEqual(
            Author.objects.filter(item=self.i2) & Author.objects.filter(item=self.i3),
            [self.a2],
        )

    def test_ticket2306(self):
        # Checking that no join types are "left outer" joins.
        query = Item.objects.filter(tags=self.t2).query
        self.assertNotIn(LOUTER, [x.join_type for x in query.alias_map.values()])

        self.assertSequenceEqual(
            Item.objects.filter(Q(tags=self.t1)).order_by("name"),
            [self.i1, self.i2],
        )
        self.assertSequenceEqual(
            Item.objects.filter(Q(tags=self.t1)).filter(Q(tags=self.t2)),
            [self.i1],
        )
        self.assertSequenceEqual(
            Item.objects.filter(Q(tags=self.t1)).filter(
                Q(creator__name="fred") | Q(tags=self.t2)
            ),
            [self.i1],
        )

        # Each filter call is processed "at once" against a single table, so this is
        # different from the previous example as it tries to find tags that are two
        # things at once (rather than two tags).
        self.assertSequenceEqual(
            Item.objects.filter(Q(tags=self.t1) & Q(tags=self.t2)), []
        )
        self.assertSequenceEqual(
            Item.objects.filter(
                Q(tags=self.t1), Q(creator__name="fred") | Q(tags=self.t2)
            ),
            [],
        )

        qs = Author.objects.filter(ranking__rank=2, ranking__id=self.rank1.id)
        self.assertSequenceEqual(list(qs), [self.a2])
        self.assertEqual(2, qs.query.count_active_tables(), 2)
        qs = Author.objects.filter(ranking__rank=2).filter(ranking__id=self.rank1.id)
        self.assertEqual(qs.query.count_active_tables(), 3)

    def test_ticket4464(self):
        self.assertSequenceEqual(
            Item.objects.filter(tags=self.t1).filter(tags=self.t2),
            [self.i1],
        )
        self.assertSequenceEqual(
            Item.objects.filter(tags__in=[self.t1, self.t2])
            .distinct()
            .order_by("name"),
            [self.i1, self.i2],
        )
        self.assertSequenceEqual(
            Item.objects.filter(tags__in=[self.t1, self.t2]).filter(tags=self.t3),
            [self.i2],
        )

        # Make sure .distinct() works with slicing (this was broken in Oracle).
        self.assertSequenceEqual(
            Item.objects.filter(tags__in=[self.t1, self.t2]).order_by("name")[:3],
            [self.i1, self.i1, self.i2],
        )
        self.assertSequenceEqual(
            Item.objects.filter(tags__in=[self.t1, self.t2])
            .distinct()
            .order_by("name")[:3],
            [self.i1, self.i2],
        )

    def test_tickets_2080_3592(self):
        self.assertSequenceEqual(
            Author.objects.filter(item__name="one") | Author.objects.filter(name="a3"),
            [self.a1, self.a3],
        )
        self.assertSequenceEqual(
            Author.objects.filter(Q(item__name="one") | Q(name="a3")),
            [self.a1, self.a3],
        )
        self.assertSequenceEqual(
            Author.objects.filter(Q(name="a3") | Q(item__name="one")),
            [self.a1, self.a3],
        )
        self.assertSequenceEqual(
            Author.objects.filter(Q(item__name="three") | Q(report__name="r3")),
            [self.a2],
        )

    def test_ticket6074(self):
        # Merging two empty result sets shouldn't leave a queryset with no constraints
        # (which would match everything).
        """

        Tests that filtering authors by empty lists produces an empty result set.

        This test ensures that the filter functionality handles empty input lists correctly,
        verifying that no authors are returned when filtering by an empty list of IDs,
        and also when combining multiple empty lists using a logical OR operator.

        """
        self.assertSequenceEqual(Author.objects.filter(Q(id__in=[])), [])
        self.assertSequenceEqual(Author.objects.filter(Q(id__in=[]) | Q(id__in=[])), [])

    def test_tickets_1878_2939(self):
        """

        Tests the proper counting and exclusion of items in the database.

        This test case focuses on the ability to count distinct items and exclude specific items from the results.
        It verifies the correctness of the Item model's database queries under various conditions, including
        the use of the `values` and `exclude` methods, as well as the `extra` method for adding custom SQL.
        The test ensures that the results are correctly filtered and that the counts are accurate, even when
        adding custom select parameters. It also covers the creation and deletion of test items to ensure
        that the database state is correctly updated.

        """
        self.assertEqual(Item.objects.values("creator").distinct().count(), 3)

        # Create something with a duplicate 'name' so that we can test multi-column
        # cases (which require some tricky SQL transformations under the covers).
        xx = Item(name="four", created=self.time1, creator=self.a2, note=self.n1)
        xx.save()
        self.assertEqual(
            Item.objects.exclude(name="two")
            .values("creator", "name")
            .distinct()
            .count(),
            4,
        )
        self.assertEqual(
            (
                Item.objects.exclude(name="two")
                .extra(select={"foo": "%s"}, select_params=(1,))
                .values("creator", "name", "foo")
                .distinct()
                .count()
            ),
            4,
        )
        self.assertEqual(
            (
                Item.objects.exclude(name="two")
                .extra(select={"foo": "%s"}, select_params=(1,))
                .values("creator", "name")
                .distinct()
                .count()
            ),
            4,
        )
        xx.delete()

    def test_ticket7323(self):
        self.assertEqual(Item.objects.values("creator", "name").count(), 4)

    def test_ticket2253(self):
        """

        Tests database query operations, specifically union and intersection of querysets.

        Verifies that combining querysets using the '|' and '&' operators produces the expected results.
        The tests cover ordering of results by a specified field and filtering by various criteria, such as item IDs, tags, notes, and creators.

        """
        q1 = Item.objects.order_by("name")
        q2 = Item.objects.filter(id=self.i1.id)
        self.assertSequenceEqual(q1, [self.i4, self.i1, self.i3, self.i2])
        self.assertSequenceEqual(q2, [self.i1])
        self.assertSequenceEqual(
            (q1 | q2).order_by("name"),
            [self.i4, self.i1, self.i3, self.i2],
        )
        self.assertSequenceEqual((q1 & q2).order_by("name"), [self.i1])

        q1 = Item.objects.filter(tags=self.t1)
        q2 = Item.objects.filter(note=self.n3, tags=self.t2)
        q3 = Item.objects.filter(creator=self.a4)
        self.assertSequenceEqual(
            ((q1 & q2) | q3).order_by("name"),
            [self.i4, self.i1],
        )

    def test_order_by_tables(self):
        """

        Tests the correct ordering of database tables in a combined query.

        This test case verifies that when two queries are combined using the '&' operator, 
        the resulting query contains the correct alias mapping for the ordered table.

        The test checks that only one table alias is present in the combined query's 
        alias map, indicating that the query is correctly ordered by the specified field.

        """
        q1 = Item.objects.order_by("name")
        q2 = Item.objects.filter(id=self.i1.id)
        list(q2)
        combined_query = (q1 & q2).order_by("name").query
        self.assertEqual(
            len(
                [
                    t
                    for t in combined_query.alias_map
                    if combined_query.alias_refcount[t]
                ]
            ),
            1,
        )

    def test_order_by_join_unref(self):
        """
        This test is related to the above one, testing that there aren't
        old JOINs in the query.
        """
        qs = Celebrity.objects.order_by("greatest_fan__fan_of")
        self.assertIn("OUTER JOIN", str(qs.query))
        qs = qs.order_by("id")
        self.assertNotIn("OUTER JOIN", str(qs.query))

    def test_order_by_related_field_transform(self):
        """

        Tests the functionality of ordering ExtraInfo objects by a related field, 
        specifically the 'month' attribute of the 'date' field. 

        This test case verifies that the order_by method correctly sorts ExtraInfo 
        objects based on the month of their associated date, ensuring that the objects 
        are returned in the expected sequence.

        """
        extra_12 = ExtraInfo.objects.create(
            info="extra 12",
            date=DateTimePK.objects.create(date=datetime.datetime(2021, 12, 10)),
        )
        extra_11 = ExtraInfo.objects.create(
            info="extra 11",
            date=DateTimePK.objects.create(date=datetime.datetime(2022, 11, 10)),
        )
        self.assertSequenceEqual(
            ExtraInfo.objects.filter(date__isnull=False).order_by("date__month"),
            [extra_11, extra_12],
        )

    def test_filter_by_related_field_transform(self):
        """
        Tests the filtering functionality of related fields using a custom transform.

        This test case verifies that the `ExtractYear` transform can be successfully applied
        to a related field, allowing for filtering by a specific year. It covers two main scenarios:
        - filtering objects directly by a related field
        - filtering objects through a foreign key relationship, using the related field's transform.

        The test creates sample objects with varying dates and then checks that the correct
        objects are returned when filtering by a specific year using the `__year` lookup.
        """
        extra_old = ExtraInfo.objects.create(
            info="extra 12",
            date=DateTimePK.objects.create(date=datetime.datetime(2020, 12, 10)),
        )
        ExtraInfo.objects.create(info="extra 11", date=DateTimePK.objects.create())
        a5 = Author.objects.create(name="a5", num=5005, extra=extra_old)

        fk_field = ExtraInfo._meta.get_field("date")
        with register_lookup(fk_field, ExtractYear):
            self.assertSequenceEqual(
                ExtraInfo.objects.filter(date__year=2020),
                [extra_old],
            )
            self.assertSequenceEqual(
                Author.objects.filter(extra__date__year=2020), [a5]
            )

    def test_filter_by_related_field_nested_transforms(self):
        extra = ExtraInfo.objects.create(info=" extra")
        a5 = Author.objects.create(name="a5", num=5005, extra=extra)
        info_field = ExtraInfo._meta.get_field("info")
        with register_lookup(info_field, Length), register_lookup(CharField, LTrim):
            self.assertSequenceEqual(
                Author.objects.filter(extra__info__ltrim__length=5), [a5]
            )

    def test_get_clears_ordering(self):
        """
        get() should clear ordering for optimization purposes.
        """
        with CaptureQueriesContext(connection) as captured_queries:
            Author.objects.order_by("name").get(pk=self.a1.pk)
        self.assertNotIn("order by", captured_queries[0]["sql"].lower())

    def test_tickets_4088_4306(self):
        self.assertSequenceEqual(Report.objects.filter(creator=1001), [self.r1])
        self.assertSequenceEqual(Report.objects.filter(creator__num=1001), [self.r1])
        self.assertSequenceEqual(Report.objects.filter(creator__id=1001), [])
        self.assertSequenceEqual(
            Report.objects.filter(creator__id=self.a1.id), [self.r1]
        )
        self.assertSequenceEqual(Report.objects.filter(creator__name="a1"), [self.r1])

    def test_ticket4510(self):
        self.assertSequenceEqual(
            Author.objects.filter(report__name="r1"),
            [self.a1],
        )

    def test_ticket7378(self):
        self.assertSequenceEqual(self.a1.report_set.all(), [self.r1])

    def test_tickets_5324_6704(self):
        """
        @pytest.mark.django_db
        def test_tickets_5324_6704(self):
            \"\"\"
            Tests the correct functionality of Django ORM queries, specifically focusing on 
            exclude, distinct, and join operations.

            This test case verifies the following scenarios:
            - Filtering items by tags and authors
            - Using distinct and order_by to retrieve unique items
            - Excluding specific tags and authors from queries
            - Using nested exclude and filter operations to retrieve items
            - Using Q objects to create complex queries
            - Checking the join type in the query alias map

            It also covers the usage of exclude and filter on nested relationships, such as 
            tags and authors, and uses Q objects to create complex queries.

        """
        self.assertSequenceEqual(
            Item.objects.filter(tags__name="t4"),
            [self.i4],
        )
        self.assertSequenceEqual(
            Item.objects.exclude(tags__name="t4").order_by("name").distinct(),
            [self.i1, self.i3, self.i2],
        )
        self.assertSequenceEqual(
            Item.objects.exclude(tags__name="t4").order_by("name").distinct().reverse(),
            [self.i2, self.i3, self.i1],
        )
        self.assertSequenceEqual(
            Author.objects.exclude(item__name="one").distinct().order_by("name"),
            [self.a2, self.a3, self.a4],
        )

        # Excluding across a m2m relation when there is more than one related
        # object associated was problematic.
        self.assertSequenceEqual(
            Item.objects.exclude(tags__name="t1").order_by("name"),
            [self.i4, self.i3],
        )
        self.assertSequenceEqual(
            Item.objects.exclude(tags__name="t1").exclude(tags__name="t4"),
            [self.i3],
        )

        # Excluding from a relation that cannot be NULL should not use outer joins.
        query = Item.objects.exclude(creator__in=[self.a1, self.a2]).query
        self.assertNotIn(LOUTER, [x.join_type for x in query.alias_map.values()])

        # Similarly, when one of the joins cannot possibly, ever, involve NULL
        # values (Author -> ExtraInfo, in the following), it should never be
        # promoted to a left outer join. So the following query should only
        # involve one "left outer" join (Author -> Item is 0-to-many).
        qs = Author.objects.filter(id=self.a1.id).filter(
            Q(extra__note=self.n1) | Q(item__note=self.n3)
        )
        self.assertEqual(
            len(
                [
                    x
                    for x in qs.query.alias_map.values()
                    if x.join_type == LOUTER and qs.query.alias_refcount[x.table_alias]
                ]
            ),
            1,
        )

        # The previous changes shouldn't affect nullable foreign key joins.
        self.assertSequenceEqual(
            Tag.objects.filter(parent__isnull=True).order_by("name"), [self.t1]
        )
        self.assertSequenceEqual(
            Tag.objects.exclude(parent__isnull=True).order_by("name"),
            [self.t2, self.t3, self.t4, self.t5],
        )
        self.assertSequenceEqual(
            Tag.objects.exclude(Q(parent__name="t1") | Q(parent__isnull=True)).order_by(
                "name"
            ),
            [self.t4, self.t5],
        )
        self.assertSequenceEqual(
            Tag.objects.exclude(Q(parent__isnull=True) | Q(parent__name="t1")).order_by(
                "name"
            ),
            [self.t4, self.t5],
        )
        self.assertSequenceEqual(
            Tag.objects.exclude(Q(parent__parent__isnull=True)).order_by("name"),
            [self.t4, self.t5],
        )
        self.assertSequenceEqual(
            Tag.objects.filter(~Q(parent__parent__isnull=True)).order_by("name"),
            [self.t4, self.t5],
        )

    def test_ticket2091(self):
        """
        Tests filtering Items by a specific Tag, ensuring that only Items associated with that Tag are returned. 

         Args:
            None

         Returns:
            None

         Note:
            Verifies that the Item query filtering by Tag 't4' returns a sequence containing only the Item 'i4', thus validating the correctness of the Tag-based filtering functionality.
        """
        t = Tag.objects.get(name="t4")
        self.assertSequenceEqual(Item.objects.filter(tags__in=[t]), [self.i4])

    def test_avoid_infinite_loop_on_too_many_subqueries(self):
        """

        Test that the ORM query builder avoids entering an infinite loop when dealing with too many subqueries.

        This test case checks that a :class:`RecursionError` is raised when the number of subqueries exceeds a certain threshold, 
        preventing a potential stack overflow. The error message 'Maximum recursion depth exceeded: too many subqueries.' 
        is expected to be raised when the recursion limit is exceeded.

        The test simulates a scenario where an ORM query is repeatedly filtered by a subquery, increasing the recursion depth 
        until it reaches the threshold, at which point the :class:`RecursionError` is expected to be raised.

        """
        x = Tag.objects.filter(pk=1)
        local_recursion_limit = sys.getrecursionlimit() // 16
        msg = "Maximum recursion depth exceeded: too many subqueries."
        with self.assertRaisesMessage(RecursionError, msg):
            for i in range(local_recursion_limit + 2):
                x = Tag.objects.filter(pk__in=x)

    def test_reasonable_number_of_subq_aliases(self):
        x = Tag.objects.filter(pk=1)
        for _ in range(20):
            x = Tag.objects.filter(pk__in=x)
        self.assertEqual(
            x.query.subq_aliases,
            {
                "T",
                "U",
                "V",
                "W",
                "X",
                "Y",
                "Z",
                "AA",
                "AB",
                "AC",
                "AD",
                "AE",
                "AF",
                "AG",
                "AH",
                "AI",
                "AJ",
                "AK",
                "AL",
                "AM",
                "AN",
            },
        )

    def test_heterogeneous_qs_combination(self):
        # Combining querysets built on different models should behave in a well-defined
        # fashion. We raise an error.
        """

        Test that combining QuerySets from different base models raises a TypeError.

        This test checks that attempting to use the bitwise AND (&) or OR (|) operators
        to combine QuerySets that are based on different models results in a TypeError
        with a specific error message. The goal is to ensure that such combinations are
        not allowed, as they would lead to ambiguous queries.

        """
        msg = "Cannot combine queries on two different base models."
        with self.assertRaisesMessage(TypeError, msg):
            Author.objects.all() & Tag.objects.all()
        with self.assertRaisesMessage(TypeError, msg):
            Author.objects.all() | Tag.objects.all()

    def test_ticket3141(self):
        """

        Tests the functionality of using the extra method with select parameters on a QuerySet.

        It verifies that specifying a select parameter as a string constant or as a parameter
        passed through select_params yields the expected count of objects.

        This test case is specifically related to issue #3141.

        """
        self.assertEqual(Author.objects.extra(select={"foo": "1"}).count(), 4)
        self.assertEqual(
            Author.objects.extra(select={"foo": "%s"}, select_params=(1,)).count(), 4
        )

    def test_ticket2400(self):
        """
        Tests the database query to filter Author and Tag objects where the associated item is null.

        It verifies that the expected Author and Tag objects are correctly retrieved when their corresponding item is not set, ensuring data integrity and query correctness in the data model.
        """
        self.assertSequenceEqual(
            Author.objects.filter(item__isnull=True),
            [self.a3],
        )
        self.assertSequenceEqual(
            Tag.objects.filter(item__isnull=True),
            [self.t5],
        )

    def test_ticket2496(self):
        self.assertSequenceEqual(
            Item.objects.extra(tables=["queries_author"])
            .select_related()
            .order_by("name")[:1],
            [self.i4],
        )

    def test_error_raised_on_filter_with_dictionary(self):
        with self.assertRaisesMessage(FieldError, "Cannot parse keyword query as dict"):
            Note.objects.filter({"note": "n1", "misc": "foo"})

    def test_tickets_2076_7256(self):
        # Ordering on related tables should be possible, even if the table is
        # not otherwise involved.
        """

        Tests advanced ordering operations on database querysets.

        Verifies that model instances can be ordered by various fields, including 
        related model fields, in both ascending and descending order. Also checks 
        that filtering by null fields and ordering by multiple fields works as expected.

        """
        self.assertSequenceEqual(
            Item.objects.order_by("note__note", "name"),
            [self.i2, self.i4, self.i1, self.i3],
        )

        # Ordering on a related field should use the remote model's default
        # ordering as a final step.
        self.assertSequenceEqual(
            Author.objects.order_by("extra", "-name"),
            [self.a2, self.a1, self.a4, self.a3],
        )

        # Using remote model default ordering can span multiple models (in this
        # case, Cover is ordered by Item's default, which uses Note's default).
        self.assertSequenceEqual(Cover.objects.all(), [self.c1, self.c2])

        # If the remote model does not have a default ordering, we order by its 'id'
        # field.
        self.assertSequenceEqual(
            Item.objects.order_by("creator", "name"),
            [self.i1, self.i3, self.i2, self.i4],
        )

        # Ordering by a many-valued attribute (e.g. a many-to-many or reverse
        # ForeignKey) is legal, but the results might not make sense. That
        # isn't Django's problem. Garbage in, garbage out.
        self.assertSequenceEqual(
            Item.objects.filter(tags__isnull=False).order_by("tags", "id"),
            [self.i1, self.i2, self.i1, self.i2, self.i4],
        )

        # If we replace the default ordering, Django adjusts the required
        # tables automatically. Item normally requires a join with Note to do
        # the default ordering, but that isn't needed here.
        qs = Item.objects.order_by("name")
        self.assertSequenceEqual(qs, [self.i4, self.i1, self.i3, self.i2])
        self.assertEqual(len(qs.query.alias_map), 1)

    def test_tickets_2874_3002(self):
        """

        Tests the retrieval and ordering of Item objects, specifically focusing on related Note objects.

        The test case verifies that a queryset of Item objects is correctly ordered by their associated Note objects and names.

        Additionally, it checks the representation of the Note objects associated with the Item objects, ensuring they are correctly referenced and displayed.

        """
        qs = Item.objects.select_related().order_by("note__note", "name")
        self.assertQuerySetEqual(qs, [self.i2, self.i4, self.i1, self.i3])

        # This is also a good select_related() test because there are multiple
        # Note entries in the SQL. The two Note items should be different.
        self.assertEqual(repr(qs[0].note), "<Note: n2>")
        self.assertEqual(repr(qs[0].creator.extra.note), "<Note: n1>")

    def test_ticket3037(self):
        self.assertSequenceEqual(
            Item.objects.filter(
                Q(creator__name="a3", name="two") | Q(creator__name="a4", name="four")
            ),
            [self.i4],
        )

    def test_tickets_5321_7070(self):
        # Ordering columns must be included in the output columns. Note that
        # this means results that might otherwise be distinct are not (if there
        # are multiple values in the ordering cols), as in this example. This
        # isn't a bug; it's a warning to be careful with the selection of
        # ordering columns.
        self.assertSequenceEqual(
            Note.objects.values("misc").distinct().order_by("note", "-misc"),
            [{"misc": "foo"}, {"misc": "bar"}, {"misc": "foo"}],
        )

    def test_ticket4358(self):
        # If you don't pass any fields to values(), relation fields are
        # returned as "foo_id" keys, not "foo". For consistency, you should be
        # able to pass "foo_id" in the fields list and have it work, too. We
        # actually allow both "foo" and "foo_id".
        # The *_id version is returned by default.
        """
        Tests the presence and correctness of specific fields in the ExtraInfo model.

        Ensures that the 'note_id' field is present in the model's values and that the
        'note_id' and 'note' fields contain the expected sequence of values. This test
        case is related to ticket #4358 and verifies that the data is correctly stored
        and retrieved from the database.
        """
        self.assertIn("note_id", ExtraInfo.objects.values()[0])
        # You can also pass it in explicitly.
        self.assertSequenceEqual(
            ExtraInfo.objects.values("note_id"), [{"note_id": 1}, {"note_id": 2}]
        )
        # ...or use the field name.
        self.assertSequenceEqual(
            ExtraInfo.objects.values("note"), [{"note": 1}, {"note": 2}]
        )

    def test_ticket6154(self):
        # Multiple filter statements are joined using "AND" all the time.

        """

        Tests the filtering behavior of Author objects with chained filters.

        This test verifies that the order of applying filters to Author objects does not affect the result.
        It checks that filtering by id and then by extra__note or item__note, and vice versa, yields the same result.
        The test case ensures that the Django ORM correctly handles the combination of filter methods and Q objects.

        """
        self.assertSequenceEqual(
            Author.objects.filter(id=self.a1.id).filter(
                Q(extra__note=self.n1) | Q(item__note=self.n3)
            ),
            [self.a1],
        )
        self.assertSequenceEqual(
            Author.objects.filter(
                Q(extra__note=self.n1) | Q(item__note=self.n3)
            ).filter(id=self.a1.id),
            [self.a1],
        )

    def test_ticket6981(self):
        self.assertSequenceEqual(
            Tag.objects.select_related("parent").order_by("name"),
            [self.t1, self.t2, self.t3, self.t4, self.t5],
        )

    def test_ticket9926(self):
        self.assertSequenceEqual(
            Tag.objects.select_related("parent", "category").order_by("name"),
            [self.t1, self.t2, self.t3, self.t4, self.t5],
        )
        self.assertSequenceEqual(
            Tag.objects.select_related("parent", "parent__category").order_by("name"),
            [self.t1, self.t2, self.t3, self.t4, self.t5],
        )

    def test_tickets_6180_6203(self):
        # Dates with limits and/or counts
        """

        Tests the retrieval of items based on creation date using datetimes method.

        This test case verifies the correct counting and retrieval of items by month and day,
        ensuring the datetimes method returns the expected number of results and correct date values.

        """
        self.assertEqual(Item.objects.count(), 4)
        self.assertEqual(Item.objects.datetimes("created", "month").count(), 1)
        self.assertEqual(Item.objects.datetimes("created", "day").count(), 2)
        self.assertEqual(len(Item.objects.datetimes("created", "day")), 2)
        self.assertEqual(
            Item.objects.datetimes("created", "day")[0],
            datetime.datetime(2007, 12, 19, 0, 0),
        )

    def test_tickets_7087_12242(self):
        # Dates with extra select columns
        """

        Tests the functionality of combining datetimes and extra query methods on the Item model.

        Specifically, this test ensures that calling datetimes() and extra() methods in different orders produces the same results.
        It also checks that applying a filter using the extra() method affects the results as expected.

        The test covers the following scenarios:
        - Datetimes with extra select
        - Extra select with datetimes
        - Datetimes with extra where clause
        - Extra where clause with datetimes

        """
        self.assertSequenceEqual(
            Item.objects.datetimes("created", "day").extra(select={"a": 1}),
            [
                datetime.datetime(2007, 12, 19, 0, 0),
                datetime.datetime(2007, 12, 20, 0, 0),
            ],
        )
        self.assertSequenceEqual(
            Item.objects.extra(select={"a": 1}).datetimes("created", "day"),
            [
                datetime.datetime(2007, 12, 19, 0, 0),
                datetime.datetime(2007, 12, 20, 0, 0),
            ],
        )

        name = "one"
        self.assertSequenceEqual(
            Item.objects.datetimes("created", "day").extra(
                where=["name=%s"], params=[name]
            ),
            [datetime.datetime(2007, 12, 19, 0, 0)],
        )

        self.assertSequenceEqual(
            Item.objects.extra(where=["name=%s"], params=[name]).datetimes(
                "created", "day"
            ),
            [datetime.datetime(2007, 12, 19, 0, 0)],
        )

    def test_ticket7155(self):
        # Nullable dates
        self.assertSequenceEqual(
            Item.objects.datetimes("modified", "day"),
            [datetime.datetime(2007, 12, 19, 0, 0)],
        )

    def test_order_by_rawsql(self):
        self.assertSequenceEqual(
            Item.objects.values("note__note").order_by(
                RawSQL("queries_note.note", ()),
                "id",
            ),
            [
                {"note__note": "n2"},
                {"note__note": "n3"},
                {"note__note": "n3"},
                {"note__note": "n3"},
            ],
        )

    def test_ticket7096(self):
        # Make sure exclude() with multiple conditions continues to work.
        self.assertSequenceEqual(
            Tag.objects.filter(parent=self.t1, name="t3").order_by("name"),
            [self.t3],
        )
        self.assertSequenceEqual(
            Tag.objects.exclude(parent=self.t1, name="t3").order_by("name"),
            [self.t1, self.t2, self.t4, self.t5],
        )
        self.assertSequenceEqual(
            Item.objects.exclude(tags__name="t1", name="one")
            .order_by("name")
            .distinct(),
            [self.i4, self.i3, self.i2],
        )
        self.assertSequenceEqual(
            Item.objects.filter(name__in=["three", "four"])
            .exclude(tags__name="t1")
            .order_by("name"),
            [self.i4, self.i3],
        )

        # More twisted cases, involving nested negations.
        self.assertSequenceEqual(
            Item.objects.exclude(~Q(tags__name="t1", name="one")),
            [self.i1],
        )
        self.assertSequenceEqual(
            Item.objects.filter(~Q(tags__name="t1", name="one"), name="two"),
            [self.i2],
        )
        self.assertSequenceEqual(
            Item.objects.exclude(~Q(tags__name="t1", name="one"), name="two"),
            [self.i4, self.i1, self.i3],
        )

    def test_tickets_7204_7506(self):
        # Make sure querysets with related fields can be pickled. If this
        # doesn't crash, it's a Good Thing.
        pickle.dumps(Item.objects.all())

    def test_ticket7813(self):
        # We should also be able to pickle things that use select_related().
        # The only tricky thing here is to ensure that we do the related
        # selections properly after unpickling.
        """
        Tests if the serialized query set is identical to the original query set.

        This test case ensures that the query generated by a serialized query set
        is the same as the query generated by the original query set. It performs this
        check by comparing the SQL queries produced by the original and deserialized
        query sets. The test uses the `select_related()` method to generate a query
        set and then serializes the query using the `pickle` module. It then compares
        the SQL queries produced by the original and deserialized query sets using the
        `assertEqual` method.

        This test covers bug #7813, which deals with the serialization of query sets
        and ensures that the serialization process does not alter the query in any way.
        """
        qs = Item.objects.select_related()
        query = qs.query.get_compiler(qs.db).as_sql()[0]
        query2 = pickle.loads(pickle.dumps(qs.query))
        self.assertEqual(query2.get_compiler(qs.db).as_sql()[0], query)

    def test_deferred_load_qs_pickling(self):
        # Check pickling of deferred-loading querysets
        """

        Tests whether deferred loading of querysets works correctly after pickling.

        This ensures that deferring fields in a queryset and then serializing and deserializing it
        using pickle does not break the deferred loading functionality. The test checks that
        the original queryset and its pickled and unpickled versions produce the same results when
        evaluated.

        """
        qs = Item.objects.defer("name", "creator")
        q2 = pickle.loads(pickle.dumps(qs))
        self.assertEqual(list(qs), list(q2))
        q3 = pickle.loads(pickle.dumps(qs, pickle.HIGHEST_PROTOCOL))
        self.assertEqual(list(qs), list(q3))

    def test_ticket7277(self):
        self.assertSequenceEqual(
            self.n1.annotation_set.filter(
                Q(tag=self.t5)
                | Q(tag__children=self.t5)
                | Q(tag__children__children=self.t5)
            ),
            [self.ann1],
        )

    def test_tickets_7448_7707(self):
        # Complex objects should be converted to strings before being used in
        # lookups.
        self.assertSequenceEqual(
            Item.objects.filter(created__in=[self.time1, self.time2]),
            [self.i1, self.i2],
        )

    def test_ticket7235(self):
        # An EmptyQuerySet should not raise exceptions if it is filtered.
        Eaten.objects.create(meal="m")
        q = Eaten.objects.none()
        with self.assertNumQueries(0):
            self.assertSequenceEqual(q.all(), [])
            self.assertSequenceEqual(q.filter(meal="m"), [])
            self.assertSequenceEqual(q.exclude(meal="m"), [])
            self.assertSequenceEqual(q.complex_filter({"pk": 1}), [])
            self.assertSequenceEqual(q.select_related("food"), [])
            self.assertSequenceEqual(q.annotate(Count("food")), [])
            self.assertSequenceEqual(q.order_by("meal", "food"), [])
            self.assertSequenceEqual(q.distinct(), [])
            self.assertSequenceEqual(q.extra(select={"foo": "1"}), [])
            self.assertSequenceEqual(q.reverse(), [])
            q.query.low_mark = 1
            msg = "Cannot change a query once a slice has been taken."
            with self.assertRaisesMessage(TypeError, msg):
                q.extra(select={"foo": "1"})
            self.assertSequenceEqual(q.defer("meal"), [])
            self.assertSequenceEqual(q.only("meal"), [])

    def test_ticket7791(self):
        # There were "issues" when ordering and distinct-ing on fields related
        # via ForeignKeys.
        """

        Tests the functionality of database queries involving distinct and datetime operations.

        This test case checks that the Note objects can be distinctively ordered based on the 'info' field of their associated 'extrainfo' objects, yielding the expected number of distinct results.

        Additionally, it verifies the pickling and unpickling of a QuerySet that retrieves the months of Item creation dates, ensuring that the query remains intact after serialization and deserialization.

        """
        self.assertEqual(len(Note.objects.order_by("extrainfo__info").distinct()), 3)

        # Pickling of QuerySets using datetimes() should work.
        qs = Item.objects.datetimes("created", "month")
        pickle.loads(pickle.dumps(qs))

    def test_ticket9997(self):
        # If a ValuesList or Values queryset is passed as an inner query, we
        # make sure it's only requesting a single value and use that as the
        # thing to select.
        """

        Test case for Django's ORM filtering functionality, specifically for the 'in' lookup type.

        This test verifies that filtering a model's objects by the 'in' lookup type works correctly when the right-hand side is a QuerySet of single-field values.
        It also checks that attempting to filter by multi-field values raises a TypeError with a meaningful error message.

        The test includes two assertions: one to check the correct filtering behavior and two to verify that the correct error is raised when trying to filter by multi-field values.

        """
        self.assertSequenceEqual(
            Tag.objects.filter(
                name__in=Tag.objects.filter(parent=self.t1).values("name")
            ),
            [self.t2, self.t3],
        )

        # Multi-valued values() and values_list() querysets should raise errors.
        with self.assertRaisesMessage(
            TypeError, "Cannot use multi-field values as a filter value."
        ):
            Tag.objects.filter(
                name__in=Tag.objects.filter(parent=self.t1).values("name", "id")
            )
        with self.assertRaisesMessage(
            TypeError, "Cannot use multi-field values as a filter value."
        ):
            Tag.objects.filter(
                name__in=Tag.objects.filter(parent=self.t1).values_list("name", "id")
            )

    def test_ticket9985(self):
        # qs.values_list(...).values(...) combinations should work.
        self.assertSequenceEqual(
            Note.objects.values_list("note", flat=True).values("id").order_by("id"),
            [{"id": 1}, {"id": 2}, {"id": 3}],
        )
        self.assertSequenceEqual(
            Annotation.objects.filter(
                notes__in=Note.objects.filter(note="n1")
                .values_list("note")
                .values("id")
            ),
            [self.ann1],
        )

    def test_ticket10205(self):
        # When bailing out early because of an empty "__in" filter, we need
        # to set things up correctly internally so that subqueries can continue
        # properly.
        self.assertEqual(Tag.objects.filter(name__in=()).update(name="foo"), 0)

    def test_ticket10432(self):
        # Testing an empty "__in" filter with a generator as the value.
        """

        Tests the behavior of the :class:`Note` model when filtering by primary key.

        This test ensures that the :meth:`filter` method of :class:`Note` objects behaves correctly when passed an empty iterator or a generator that yields a valid primary key.

        The test case covers two scenarios:
        - An empty iterator is passed to the :meth:`filter` method, verifying that an empty result set is returned.
        - A generator that yields a valid primary key is passed to the :meth:`filter` method, verifying that the corresponding :class:`Note` object is returned.

        """
        def f():
            return iter([])

        n_obj = Note.objects.all()[0]

        def g():
            yield n_obj.pk

        self.assertSequenceEqual(Note.objects.filter(pk__in=f()), [])
        self.assertEqual(list(Note.objects.filter(pk__in=g())), [n_obj])

    def test_ticket10742(self):
        # Queries used in an __in clause don't execute subqueries

        subq = Author.objects.filter(num__lt=3000)
        qs = Author.objects.filter(pk__in=subq)
        self.assertSequenceEqual(qs, [self.a1, self.a2])

        # The subquery result cache should not be populated
        self.assertIsNone(subq._result_cache)

        subq = Author.objects.filter(num__lt=3000)
        qs = Author.objects.exclude(pk__in=subq)
        self.assertSequenceEqual(qs, [self.a3, self.a4])

        # The subquery result cache should not be populated
        self.assertIsNone(subq._result_cache)

        subq = Author.objects.filter(num__lt=3000)
        self.assertSequenceEqual(
            Author.objects.filter(Q(pk__in=subq) & Q(name="a1")),
            [self.a1],
        )

        # The subquery result cache should not be populated
        self.assertIsNone(subq._result_cache)

    def test_ticket7076(self):
        # Excluding shouldn't eliminate NULL entries.
        """
        ..: Tests the correct ordering and exclusion of objects in the database.

            This test case verifies that the exclude and order_by methods are working as expected.
            It checks two scenarios: 
            1. Excluding items modified at a specific time and ordering the remaining items by name.
            2. Excluding tags that have a parent with a specific name and returning the remaining tags.
            The test ensures that the results are returned in the correct order and that the excluded items are not included in the results.
        """
        self.assertSequenceEqual(
            Item.objects.exclude(modified=self.time1).order_by("name"),
            [self.i4, self.i3, self.i2],
        )
        self.assertSequenceEqual(
            Tag.objects.exclude(parent__name=self.t1.name),
            [self.t1, self.t4, self.t5],
        )

    def test_ticket7181(self):
        # Ordering by related tables should accommodate nullable fields (this
        # test is a little tricky, since NULL ordering is database dependent.
        # Instead, we just count the number of results).
        """
        Tests the behavior of Django querysets when using union and intersection operations.

        This test case covers the following scenarios:

        * Verifies that sorting by related fields works correctly
        * Checks that the union operation between an empty queryset and a non-empty queryset produces the expected results
        * Validates that the intersection operation between an empty queryset and a non-empty queryset produces an empty queryset

        The test ensures that the resulting querysets have the correct length and contain the expected objects, in the expected order.

        """
        self.assertEqual(len(Tag.objects.order_by("parent__name")), 5)

        # Empty querysets can be merged with others.
        self.assertSequenceEqual(
            Note.objects.none() | Note.objects.all(),
            [self.n1, self.n2, self.n3],
        )
        self.assertSequenceEqual(
            Note.objects.all() | Note.objects.none(),
            [self.n1, self.n2, self.n3],
        )
        self.assertSequenceEqual(Note.objects.none() & Note.objects.all(), [])
        self.assertSequenceEqual(Note.objects.all() & Note.objects.none(), [])

    def test_ticket8439(self):
        # Complex combinations of conjunctions, disjunctions and nullable
        # relations.
        """

        Tests the correct filtering of objects using complex Q queries with OR conditions.

        Verifies that the function returns the correct set of objects when using
        Q queries with logical OR operations to filter based on multiple conditions.
        The test cases cover various scenarios, including filtering Authors, Annotations,
        and Notes based on different attributes and related objects.

        """
        self.assertSequenceEqual(
            Author.objects.filter(
                Q(item__note__extrainfo=self.e2) | Q(report=self.r1, name="xyz")
            ),
            [self.a2],
        )
        self.assertSequenceEqual(
            Author.objects.filter(
                Q(report=self.r1, name="xyz") | Q(item__note__extrainfo=self.e2)
            ),
            [self.a2],
        )
        self.assertSequenceEqual(
            Annotation.objects.filter(
                Q(tag__parent=self.t1) | Q(notes__note="n1", name="a1")
            ),
            [self.ann1],
        )
        xx = ExtraInfo.objects.create(info="xx", note=self.n3)
        self.assertSequenceEqual(
            Note.objects.filter(Q(extrainfo__author=self.a1) | Q(extrainfo=xx)),
            [self.n1, self.n3],
        )
        q = Note.objects.filter(Q(extrainfo__author=self.a1) | Q(extrainfo=xx)).query
        self.assertEqual(
            len(
                [
                    x
                    for x in q.alias_map.values()
                    if x.join_type == LOUTER and q.alias_refcount[x.table_alias]
                ]
            ),
            1,
        )

    def test_ticket17429(self):
        """
        Meta.ordering=None works the same as Meta.ordering=[]
        """
        original_ordering = Tag._meta.ordering
        Tag._meta.ordering = None
        try:
            self.assertCountEqual(
                Tag.objects.all(),
                [self.t1, self.t2, self.t3, self.t4, self.t5],
            )
        finally:
            Tag._meta.ordering = original_ordering

    def test_exclude(self):
        """
        Tests the exclude method of the Item model's QuerySet.

        Verifies that using the exclude method with various query parameters produces the same results as using the filter method with the negation of those parameters.

        Specifically, tests the following cases:
        - Excluding items with a specific tag name
        - Excluding items with multiple tag names using OR logic
        - Excluding items with a specific tag name and not excluding items with another tag name

        Ensures that the exclude method correctly filters out items based on the given conditions, resulting in the same QuerySet as using the filter method with the negation of those conditions.”
        """
        self.assertQuerySetEqual(
            Item.objects.exclude(tags__name="t4"),
            Item.objects.filter(~Q(tags__name="t4")),
        )
        self.assertQuerySetEqual(
            Item.objects.exclude(Q(tags__name="t4") | Q(tags__name="t3")),
            Item.objects.filter(~(Q(tags__name="t4") | Q(tags__name="t3"))),
        )
        self.assertQuerySetEqual(
            Item.objects.exclude(Q(tags__name="t4") | ~Q(tags__name="t3")),
            Item.objects.filter(~(Q(tags__name="t4") | ~Q(tags__name="t3"))),
        )

    def test_nested_exclude(self):
        self.assertQuerySetEqual(
            Item.objects.exclude(~Q(tags__name="t4")),
            Item.objects.filter(~~Q(tags__name="t4")),
        )

    def test_double_exclude(self):
        """

        Tests the correct functionality of the double exclude feature in Django querysets.

        This function checks if using the double negation operator (~~) or nested negation operators (~) 
        produces the same results as a standard queryset. Specifically, it verifies that filtering 
        items by a certain tag name ('t4') yields the same results in both cases.

        The test case covers two scenarios: 
        1. using the double negation operator (~~) to exclude items that do not match the tag 't4',
        2. using nested negation operators (~) to achieve the same result.

        Both scenarios should return the same queryset, containing items that match the specified tag.

        """
        self.assertQuerySetEqual(
            Item.objects.filter(Q(tags__name="t4")),
            Item.objects.filter(~~Q(tags__name="t4")),
        )
        self.assertQuerySetEqual(
            Item.objects.filter(Q(tags__name="t4")),
            Item.objects.filter(~Q(~Q(tags__name="t4"))),
        )

    def test_exclude_in(self):
        """
        Tests that the exclude method in the queryset API is functioning as expected by comparing the results of exclude and filter methods with negated query conditions. The function ensures that excluding items with specific tags ('t4', 't3') produces the same result as filtering items with the negation of the same condition, validating the correctness of exclusion logic. Additionally, it verifies that doubling the negation (~) of a query condition does not alter the result, confirming that the filter method behaves consistently when used with multiple negations.
        """
        self.assertQuerySetEqual(
            Item.objects.exclude(Q(tags__name__in=["t4", "t3"])),
            Item.objects.filter(~Q(tags__name__in=["t4", "t3"])),
        )
        self.assertQuerySetEqual(
            Item.objects.filter(Q(tags__name__in=["t4", "t3"])),
            Item.objects.filter(~~Q(tags__name__in=["t4", "t3"])),
        )

    def test_ticket_10790_1(self):
        # Querying direct fields with isnull should trim the left outer join.
        # It also should not create INNER JOIN.
        """
        Tests database queries for filtering and excluding tags based on their parent relationships.

        Checks that the ORM generates efficient queries without unnecessary joins when filtering or excluding tags with or without parents.
        Also tests more complex queries that exclude tags based on their grandparent relationships, ensuring the correct use of left outer joins.
        Verifies the expected results are returned and the generated SQL queries do not contain unnecessary join operations.
        """
        q = Tag.objects.filter(parent__isnull=True)

        self.assertSequenceEqual(q, [self.t1])
        self.assertNotIn("JOIN", str(q.query))

        q = Tag.objects.filter(parent__isnull=False)

        self.assertSequenceEqual(q, [self.t2, self.t3, self.t4, self.t5])
        self.assertNotIn("JOIN", str(q.query))

        q = Tag.objects.exclude(parent__isnull=True)
        self.assertSequenceEqual(q, [self.t2, self.t3, self.t4, self.t5])
        self.assertNotIn("JOIN", str(q.query))

        q = Tag.objects.exclude(parent__isnull=False)
        self.assertSequenceEqual(q, [self.t1])
        self.assertNotIn("JOIN", str(q.query))

        q = Tag.objects.exclude(parent__parent__isnull=False)

        self.assertSequenceEqual(q, [self.t1, self.t2, self.t3])
        self.assertEqual(str(q.query).count("LEFT OUTER JOIN"), 1)
        self.assertNotIn("INNER JOIN", str(q.query))

    def test_ticket_10790_2(self):
        # Querying across several tables should strip only the last outer join,
        # while preserving the preceding inner joins.
        """
        Tests the filtering of Tag objects based on their parent relationships. 

        This test case checks that the correct Tag objects are returned when filtering 
        by parent relationships with multiple levels of nesting. It verifies that the 
        generated SQL query uses an INNER JOIN to retrieve the results, without using 
        any LEFT OUTER JOINs. The test covers two scenarios: filtering by a 
        grandparent relationship and by a specific parent object.
        """
        q = Tag.objects.filter(parent__parent__isnull=False)

        self.assertSequenceEqual(q, [self.t4, self.t5])
        self.assertEqual(str(q.query).count("LEFT OUTER JOIN"), 0)
        self.assertEqual(str(q.query).count("INNER JOIN"), 1)

        # Querying without isnull should not convert anything to left outer join.
        q = Tag.objects.filter(parent__parent=self.t1)
        self.assertSequenceEqual(q, [self.t4, self.t5])
        self.assertEqual(str(q.query).count("LEFT OUTER JOIN"), 0)
        self.assertEqual(str(q.query).count("INNER JOIN"), 1)

    def test_ticket_10790_3(self):
        # Querying via indirect fields should populate the left outer join
        q = NamedCategory.objects.filter(tag__isnull=True)
        self.assertEqual(str(q.query).count("LEFT OUTER JOIN"), 1)
        # join to dumbcategory ptr_id
        self.assertEqual(str(q.query).count("INNER JOIN"), 1)
        self.assertSequenceEqual(q, [])

        # Querying across several tables should strip only the last join, while
        # preserving the preceding left outer joins.
        q = NamedCategory.objects.filter(tag__parent__isnull=True)
        self.assertEqual(str(q.query).count("INNER JOIN"), 1)
        self.assertEqual(str(q.query).count("LEFT OUTER JOIN"), 1)
        self.assertSequenceEqual(q, [self.nc1])

    def test_ticket_10790_4(self):
        # Querying across m2m field should not strip the m2m table from join.
        """

        Tests the correct application of left outer join logic when filtering Authors by specific item and tag conditions.

        Verifies that the generated SQL queries use the expected number of left outer joins and do not contain inner joins, 
        resulting in the correct Authors being returned. This encompasses two scenarios:

        1. Authors with items that have no tags associated.
        2. Authors with items that have tags with no parent tags.

        """
        q = Author.objects.filter(item__tags__isnull=True)
        self.assertSequenceEqual(q, [self.a2, self.a3])
        self.assertEqual(str(q.query).count("LEFT OUTER JOIN"), 2)
        self.assertNotIn("INNER JOIN", str(q.query))

        q = Author.objects.filter(item__tags__parent__isnull=True)
        self.assertSequenceEqual(q, [self.a1, self.a2, self.a2, self.a3])
        self.assertEqual(str(q.query).count("LEFT OUTER JOIN"), 3)
        self.assertNotIn("INNER JOIN", str(q.query))

    def test_ticket_10790_5(self):
        # Querying with isnull=False across m2m field should not create outer joins
        q = Author.objects.filter(item__tags__isnull=False)
        self.assertSequenceEqual(q, [self.a1, self.a1, self.a2, self.a2, self.a4])
        self.assertEqual(str(q.query).count("LEFT OUTER JOIN"), 0)
        self.assertEqual(str(q.query).count("INNER JOIN"), 2)

        q = Author.objects.filter(item__tags__parent__isnull=False)
        self.assertSequenceEqual(q, [self.a1, self.a2, self.a4])
        self.assertEqual(str(q.query).count("LEFT OUTER JOIN"), 0)
        self.assertEqual(str(q.query).count("INNER JOIN"), 3)

        q = Author.objects.filter(item__tags__parent__parent__isnull=False)
        self.assertSequenceEqual(q, [self.a4])
        self.assertEqual(str(q.query).count("LEFT OUTER JOIN"), 0)
        self.assertEqual(str(q.query).count("INNER JOIN"), 4)

    def test_ticket_10790_6(self):
        # Querying with isnull=True across m2m field should not create inner joins
        # and strip last outer join
        """
        Tests the filtering of Authors based on the tags of their related Items.

        The test covers two cases:

        - The first case checks that Authors are correctly filtered when the grandparent of the tag is null,
          and verifies that the resulting database query uses the correct number of LEFT OUTER JOINs.
        - The second case checks that Authors are correctly filtered when the parent of the tag is null,
          and verifies that the resulting database query uses the correct number of LEFT OUTER JOINs.

        The test ensures that the expected Authors are returned in the correct order, and that the generated SQL queries are optimized to use LEFT OUTER JOINs instead of INNER JOINs.
        """
        q = Author.objects.filter(item__tags__parent__parent__isnull=True)
        self.assertSequenceEqual(
            q,
            [self.a1, self.a1, self.a2, self.a2, self.a2, self.a3],
        )
        self.assertEqual(str(q.query).count("LEFT OUTER JOIN"), 4)
        self.assertEqual(str(q.query).count("INNER JOIN"), 0)

        q = Author.objects.filter(item__tags__parent__isnull=True)
        self.assertSequenceEqual(q, [self.a1, self.a2, self.a2, self.a3])
        self.assertEqual(str(q.query).count("LEFT OUTER JOIN"), 3)
        self.assertEqual(str(q.query).count("INNER JOIN"), 0)

    def test_ticket_10790_7(self):
        # Reverse querying with isnull should not strip the join
        q = Author.objects.filter(item__isnull=True)
        self.assertSequenceEqual(q, [self.a3])
        self.assertEqual(str(q.query).count("LEFT OUTER JOIN"), 1)
        self.assertEqual(str(q.query).count("INNER JOIN"), 0)

        q = Author.objects.filter(item__isnull=False)
        self.assertSequenceEqual(q, [self.a1, self.a2, self.a2, self.a4])
        self.assertEqual(str(q.query).count("LEFT OUTER JOIN"), 0)
        self.assertEqual(str(q.query).count("INNER JOIN"), 1)

    def test_ticket_10790_8(self):
        # Querying with combined q-objects should also strip the left outer join
        """
        Tests the filtering of tags based on parent tags, ensuring that the query 
        correctly returns top-level and child tags without using explicit inner or 
        outer joins.

        Verifies that a query filtering tags where the parent is either null (top-level) 
        or equals a specific tag (self.t1) returns the expected sequence of tags 
        (self.t1, self.t2, self.t3), and that the resulting database query does not 
        contain LEFT OUTER JOIN or INNER JOIN clauses.
        """
        q = Tag.objects.filter(Q(parent__isnull=True) | Q(parent=self.t1))
        self.assertSequenceEqual(q, [self.t1, self.t2, self.t3])
        self.assertEqual(str(q.query).count("LEFT OUTER JOIN"), 0)
        self.assertEqual(str(q.query).count("INNER JOIN"), 0)

    def test_ticket_10790_combine(self):
        # Combining queries should not re-populate the left outer join
        q1 = Tag.objects.filter(parent__isnull=True)
        q2 = Tag.objects.filter(parent__isnull=False)

        q3 = q1 | q2
        self.assertSequenceEqual(q3, [self.t1, self.t2, self.t3, self.t4, self.t5])
        self.assertEqual(str(q3.query).count("LEFT OUTER JOIN"), 0)
        self.assertEqual(str(q3.query).count("INNER JOIN"), 0)

        q3 = q1 & q2
        self.assertSequenceEqual(q3, [])
        self.assertEqual(str(q3.query).count("LEFT OUTER JOIN"), 0)
        self.assertEqual(str(q3.query).count("INNER JOIN"), 0)

        q2 = Tag.objects.filter(parent=self.t1)
        q3 = q1 | q2
        self.assertSequenceEqual(q3, [self.t1, self.t2, self.t3])
        self.assertEqual(str(q3.query).count("LEFT OUTER JOIN"), 0)
        self.assertEqual(str(q3.query).count("INNER JOIN"), 0)

        q3 = q2 | q1
        self.assertSequenceEqual(q3, [self.t1, self.t2, self.t3])
        self.assertEqual(str(q3.query).count("LEFT OUTER JOIN"), 0)
        self.assertEqual(str(q3.query).count("INNER JOIN"), 0)

        q1 = Tag.objects.filter(parent__isnull=True)
        q2 = Tag.objects.filter(parent__parent__isnull=True)

        q3 = q1 | q2
        self.assertSequenceEqual(q3, [self.t1, self.t2, self.t3])
        self.assertEqual(str(q3.query).count("LEFT OUTER JOIN"), 1)
        self.assertEqual(str(q3.query).count("INNER JOIN"), 0)

        q3 = q2 | q1
        self.assertSequenceEqual(q3, [self.t1, self.t2, self.t3])
        self.assertEqual(str(q3.query).count("LEFT OUTER JOIN"), 1)
        self.assertEqual(str(q3.query).count("INNER JOIN"), 0)

    def test_ticket19672(self):
        self.assertSequenceEqual(
            Report.objects.filter(
                Q(creator__isnull=False) & ~Q(creator__extra__value=41)
            ),
            [self.r1],
        )

    def test_ticket_20250(self):
        # A negated Q along with an annotated queryset failed in Django 1.4
        qs = Author.objects.annotate(Count("item"))
        qs = qs.filter(~Q(extra__value=0)).order_by("name")

        self.assertIn("SELECT", str(qs.query))
        self.assertSequenceEqual(qs, [self.a1, self.a2, self.a3, self.a4])

    def test_lookup_constraint_fielderror(self):
        msg = (
            "Cannot resolve keyword 'unknown_field' into field. Choices are: "
            "annotation, category, category_id, children, id, item, "
            "managedmodel, name, note, parent, parent_id"
        )
        with self.assertRaisesMessage(FieldError, msg):
            Tag.objects.filter(unknown_field__name="generic")

    def test_common_mixed_case_foreign_keys(self):
        """
        Valid query should be generated when fields fetched from joined tables
        include FKs whose names only differ by case.
        """
        c1 = SimpleCategory.objects.create(name="c1")
        c2 = SimpleCategory.objects.create(name="c2")
        c3 = SimpleCategory.objects.create(name="c3")
        category = CategoryItem.objects.create(category=c1)
        mixed_case_field_category = MixedCaseFieldCategoryItem.objects.create(
            CaTeGoRy=c2
        )
        mixed_case_db_column_category = MixedCaseDbColumnCategoryItem.objects.create(
            category=c3
        )
        CommonMixedCaseForeignKeys.objects.create(
            category=category,
            mixed_case_field_category=mixed_case_field_category,
            mixed_case_db_column_category=mixed_case_db_column_category,
        )
        qs = CommonMixedCaseForeignKeys.objects.values(
            "category",
            "mixed_case_field_category",
            "mixed_case_db_column_category",
            "category__category",
            "mixed_case_field_category__CaTeGoRy",
            "mixed_case_db_column_category__category",
        )
        self.assertTrue(qs.first())

    def test_excluded_intermediary_m2m_table_joined(self):
        self.assertSequenceEqual(
            Note.objects.filter(~Q(tag__annotation__name=F("note"))),
            [self.n1, self.n2, self.n3],
        )
        self.assertSequenceEqual(
            Note.objects.filter(tag__annotation__name="a1").filter(
                ~Q(tag__annotation__name=F("note"))
            ),
            [],
        )

    def test_field_with_filterable(self):
        self.assertSequenceEqual(
            Author.objects.filter(extra=self.e2),
            [self.a3, self.a4],
        )

    def test_negate_field(self):
        self.assertSequenceEqual(
            Note.objects.filter(negate=True),
            [self.n1, self.n2],
        )
        self.assertSequenceEqual(Note.objects.exclude(negate=True), [self.n3])

    def test_combining_does_not_mutate(self):
        """
        Tests that combining querysets using union and intersection operations does not mutate the original querysets.

        Ensures that the results of combining authors with and without reports remain unchanged,
        and that the items associated with these authors are still correctly filtered before and after combination.

        Verifies the correctness of combining querysets by comparing the items filtered by authors
        without reports, both before and after performing union and intersection operations on the authors querysets.
        """
        all_authors = Author.objects.all()
        authors_with_report = Author.objects.filter(
            Exists(Report.objects.filter(creator__pk=OuterRef("id")))
        )
        authors_without_report = all_authors.exclude(pk__in=authors_with_report)
        items_before = Item.objects.filter(creator__in=authors_without_report)
        self.assertCountEqual(items_before, [self.i2, self.i3, self.i4])
        # Combining querysets doesn't mutate them.
        all_authors | authors_with_report
        all_authors & authors_with_report

        authors_without_report = all_authors.exclude(pk__in=authors_with_report)
        items_after = Item.objects.filter(creator__in=authors_without_report)

        self.assertCountEqual(items_after, [self.i2, self.i3, self.i4])
        self.assertCountEqual(items_before, items_after)

    def test_union_values_subquery(self):
        """
        Tests the union of values from subqueries to identify authors who are creators of either items or reports.

        This test validates that the correct authors are identified as creators of items or reports by comparing the expected results with the actual values returned from the database.

        The test checks if the correct boolean values are returned for authors, indicating whether they are creators of items or reports, with an expected result of one author being a creator and one not being a creator.
        """
        items = Item.objects.filter(creator=OuterRef("pk"))
        item_authors = Author.objects.annotate(is_creator=Exists(items)).order_by()
        reports = Report.objects.filter(creator=OuterRef("pk"))
        report_authors = Author.objects.annotate(is_creator=Exists(reports)).order_by()
        all_authors = item_authors.union(report_authors).order_by("is_creator")
        self.assertEqual(
            list(all_authors.values_list("is_creator", flat=True)), [False, True]
        )


class Queries2Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for the test class.

        This method is used to create and store test data that can be used across all test methods in the class.
        It creates three Number objects with values 4, 8, and 12, and assigns them to class attributes for later use.

        The purpose of this setup is to reduce duplication of test data creation in individual test methods and improve test efficiency.
        """
        cls.num4 = Number.objects.create(num=4)
        cls.num8 = Number.objects.create(num=8)
        cls.num12 = Number.objects.create(num=12)

    def test_ticket4289(self):
        # A slight variation on the restricting the filtering choices by the
        # lookup constraints.
        """

        Tests the filtering of Number objects using various query conditions.

        This test case covers different scenarios, including filtering by numeric ranges,
        combining conditions using logical operators, and ensuring that the expected
        results are returned.

        The test checks that the filter conditions are correctly applied, including cases
        where the conditions do not match any objects, as well as cases where multiple
        conditions are combined using logical OR and AND operators.

        """
        self.assertSequenceEqual(Number.objects.filter(num__lt=4), [])
        self.assertSequenceEqual(Number.objects.filter(num__gt=8, num__lt=12), [])
        self.assertSequenceEqual(
            Number.objects.filter(num__gt=8, num__lt=13),
            [self.num12],
        )
        self.assertSequenceEqual(
            Number.objects.filter(Q(num__lt=4) | Q(num__gt=8, num__lt=12)), []
        )
        self.assertSequenceEqual(
            Number.objects.filter(Q(num__gt=8, num__lt=12) | Q(num__lt=4)), []
        )
        self.assertSequenceEqual(
            Number.objects.filter(Q(num__gt=8) & Q(num__lt=12) | Q(num__lt=4)), []
        )
        self.assertSequenceEqual(
            Number.objects.filter(Q(num__gt=7) & Q(num__lt=12) | Q(num__lt=4)),
            [self.num8],
        )

    def test_ticket12239(self):
        # Custom lookups are registered to round float values correctly on gte
        # and lt IntegerField queries.
        """
        Tests the functionality of filtering Number objects based on comparison queries.

        This test case verifies that the `num` field of Number objects can be filtered using various comparison operators, 
        including greater than (`__gt`), less than (`__lt`), greater than or equal to (`__gte`), and less than or equal to (`__lte`).

        The test checks that these filters work correctly with both integer and floating-point numbers, 
        and that the results are returned in the expected order. 

        It also ensures that the filters are inclusive or exclusive of the given value as required by the operator used.
        """
        self.assertSequenceEqual(
            Number.objects.filter(num__gt=11.9),
            [self.num12],
        )
        self.assertSequenceEqual(Number.objects.filter(num__gt=12), [])
        self.assertSequenceEqual(Number.objects.filter(num__gt=12.0), [])
        self.assertSequenceEqual(Number.objects.filter(num__gt=12.1), [])
        self.assertCountEqual(
            Number.objects.filter(num__lt=12),
            [self.num4, self.num8],
        )
        self.assertCountEqual(
            Number.objects.filter(num__lt=12.0),
            [self.num4, self.num8],
        )
        self.assertCountEqual(
            Number.objects.filter(num__lt=12.1),
            [self.num4, self.num8, self.num12],
        )
        self.assertCountEqual(
            Number.objects.filter(num__gte=11.9),
            [self.num12],
        )
        self.assertCountEqual(
            Number.objects.filter(num__gte=12),
            [self.num12],
        )
        self.assertCountEqual(
            Number.objects.filter(num__gte=12.0),
            [self.num12],
        )
        self.assertSequenceEqual(Number.objects.filter(num__gte=12.1), [])
        self.assertSequenceEqual(Number.objects.filter(num__gte=12.9), [])
        self.assertCountEqual(
            Number.objects.filter(num__lte=11.9),
            [self.num4, self.num8],
        )
        self.assertCountEqual(
            Number.objects.filter(num__lte=12),
            [self.num4, self.num8, self.num12],
        )
        self.assertCountEqual(
            Number.objects.filter(num__lte=12.0),
            [self.num4, self.num8, self.num12],
        )
        self.assertCountEqual(
            Number.objects.filter(num__lte=12.1),
            [self.num4, self.num8, self.num12],
        )
        self.assertCountEqual(
            Number.objects.filter(num__lte=12.9),
            [self.num4, self.num8, self.num12],
        )

    def test_ticket7759(self):
        # Count should work with a partially read result set.
        """
        Test that the count of Number objects remains consistent when iterating over a QuerySet.

        This test ensures that the count of objects in the database does not change when
        iterating over a QuerySet of Number objects, verifying that the database state
        is consistent throughout the iteration process.

        The test retrieves the initial count of Number objects and then iterates over
        the QuerySet, verifying that the count remains the same after iteration.

        """
        count = Number.objects.count()
        qs = Number.objects.all()

        def run():
            """

            Returns whether the number of objects in the query set (qs) matches the expected count.

            :returns: bool indicating whether the counts match
            :rtype: bool

            """
            for obj in qs:
                return qs.count() == count

        self.assertTrue(run())


class Queries3Tests(TestCase):
    def test_ticket7107(self):
        # This shouldn't create an infinite loop.
        self.assertSequenceEqual(Valid.objects.all(), [])

    def test_datetimes_invalid_field(self):
        # An error should be raised when QuerySet.datetimes() is passed the
        # wrong type of field.
        msg = "'name' isn't a DateField, TimeField, or DateTimeField."
        with self.assertRaisesMessage(TypeError, msg):
            Item.objects.datetimes("name", "month")

    def test_ticket22023(self):
        """
        Tests that using only() or defer() after values() raises a TypeError.

        This test case covers the scenario where a query is using the values() method, 
        which returns dictionaries, and then attempts to use only() or defer() methods, 
        which are meant for use with querysets that return model instances. 

        The expected behavior is that calling only() or defer() after values() 
        should raise a TypeError with a message indicating that only() and defer() 
        cannot be used after values() or values_list(). 

        This ensures that developers receive an informative error message 
        when they attempt to use these methods in an invalid way, 
        preventing potential bugs and making it easier to identify the issue.
        """
        with self.assertRaisesMessage(
            TypeError, "Cannot call only() after .values() or .values_list()"
        ):
            Valid.objects.values().only()

        with self.assertRaisesMessage(
            TypeError, "Cannot call defer() after .values() or .values_list()"
        ):
            Valid.objects.values().defer()


class Queries4Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        generic = NamedCategory.objects.create(name="Generic")
        cls.t1 = Tag.objects.create(name="t1", category=generic)

        n1 = Note.objects.create(note="n1", misc="foo")
        n2 = Note.objects.create(note="n2", misc="bar")

        e1 = ExtraInfo.objects.create(info="e1", note=n1)
        e2 = ExtraInfo.objects.create(info="e2", note=n2)

        cls.a1 = Author.objects.create(name="a1", num=1001, extra=e1)
        cls.a3 = Author.objects.create(name="a3", num=3003, extra=e2)

        cls.r1 = Report.objects.create(name="r1", creator=cls.a1)
        cls.r2 = Report.objects.create(name="r2", creator=cls.a3)
        cls.r3 = Report.objects.create(name="r3")

        cls.i1 = Item.objects.create(
            name="i1", created=datetime.datetime.now(), note=n1, creator=cls.a1
        )
        cls.i2 = Item.objects.create(
            name="i2", created=datetime.datetime.now(), note=n1, creator=cls.a3
        )

    def test_ticket24525(self):
        """

        Tests the intersection of annotations for a specific note, excluding annotations 
        that contain a particular note.

        This test case verifies that annotations are correctly filtered based on their 
        associated notes, ensuring that only relevant annotations are returned when 
        excluding specific notes.

        """
        tag = Tag.objects.create()
        anth100 = tag.note_set.create(note="ANTH", misc="100")
        math101 = tag.note_set.create(note="MATH", misc="101")
        s1 = tag.annotation_set.create(name="1")
        s2 = tag.annotation_set.create(name="2")
        s1.notes.set([math101, anth100])
        s2.notes.set([math101])
        result = math101.annotation_set.all() & tag.annotation_set.exclude(
            notes__in=[anth100]
        )
        self.assertEqual(list(result), [s2])

    def test_ticket11811(self):
        unsaved_category = NamedCategory(name="Other")
        msg = (
            "Unsaved model instance <NamedCategory: Other> cannot be used in an ORM "
            "query."
        )
        with self.assertRaisesMessage(ValueError, msg):
            Tag.objects.filter(pk=self.t1.pk).update(category=unsaved_category)

    def test_ticket14876(self):
        # Note: when combining the query we need to have information available
        # about the join type of the trimmed "creator__isnull" join. If we
        # don't have that information, then the join is created as INNER JOIN
        # and results will be incorrect.
        q1 = Report.objects.filter(
            Q(creator__isnull=True) | Q(creator__extra__info="e1")
        )
        q2 = Report.objects.filter(Q(creator__isnull=True)) | Report.objects.filter(
            Q(creator__extra__info="e1")
        )
        self.assertCountEqual(q1, [self.r1, self.r3])
        self.assertEqual(str(q1.query), str(q2.query))

        q1 = Report.objects.filter(
            Q(creator__extra__info="e1") | Q(creator__isnull=True)
        )
        q2 = Report.objects.filter(
            Q(creator__extra__info="e1")
        ) | Report.objects.filter(Q(creator__isnull=True))
        self.assertCountEqual(q1, [self.r1, self.r3])
        self.assertEqual(str(q1.query), str(q2.query))

        q1 = Item.objects.filter(
            Q(creator=self.a1) | Q(creator__report__name="r1")
        ).order_by()
        q2 = (
            Item.objects.filter(Q(creator=self.a1)).order_by()
            | Item.objects.filter(Q(creator__report__name="r1")).order_by()
        )
        self.assertCountEqual(q1, [self.i1])
        self.assertEqual(str(q1.query), str(q2.query))

        q1 = Item.objects.filter(
            Q(creator__report__name="e1") | Q(creator=self.a1)
        ).order_by()
        q2 = (
            Item.objects.filter(Q(creator__report__name="e1")).order_by()
            | Item.objects.filter(Q(creator=self.a1)).order_by()
        )
        self.assertCountEqual(q1, [self.i1])
        self.assertEqual(str(q1.query), str(q2.query))

    def test_combine_join_reuse(self):
        # Joins having identical connections are correctly recreated in the
        # rhs query, in case the query is ORed together (#18748).
        """
        Tests the combination of two querysets using the OR operator, verifying that 
        the resulting queryset forms the expected number of JOIN operations in the SQL 
        query and returns the correct number of results with the expected attribute values.
        """
        Report.objects.create(name="r4", creator=self.a1)
        q1 = Author.objects.filter(report__name="r5")
        q2 = Author.objects.filter(report__name="r4").filter(report__name="r1")
        combined = q1 | q2
        self.assertEqual(str(combined.query).count("JOIN"), 2)
        self.assertEqual(len(combined), 1)
        self.assertEqual(combined[0].name, "a1")

    def test_combine_or_filter_reuse(self):
        """
        Tests the combination of two filters using the logical OR operator, 
        verifying that the resulting queryset can be correctly used to retrieve 
        specific objects. This ensures that filters are properly combined and 
        the resulting queryset can be used to fetch objects based on their 
        attributes.
        """
        combined = Author.objects.filter(name="a1") | Author.objects.filter(name="a3")
        self.assertEqual(combined.get(name="a1"), self.a1)

    def test_join_reuse_order(self):
        # Join aliases are reused in order. This shouldn't raise AssertionError
        # because change_map contains a circular reference (#26522).
        s1 = School.objects.create()
        s2 = School.objects.create()
        s3 = School.objects.create()
        t1 = Teacher.objects.create()
        otherteachers = Teacher.objects.exclude(pk=t1.pk).exclude(friends=t1)
        qs1 = otherteachers.filter(schools=s1).filter(schools=s2)
        qs2 = otherteachers.filter(schools=s1).filter(schools=s3)
        self.assertSequenceEqual(qs1 | qs2, [])

    def test_ticket7095(self):
        # Updates that are filtered on the model being updated are somewhat
        # tricky in MySQL.
        ManagedModel.objects.create(data="mm1", tag=self.t1, public=True)
        self.assertEqual(ManagedModel.objects.update(data="mm"), 1)

        # A values() or values_list() query across joined models must use outer
        # joins appropriately.
        # Note: In Oracle, we expect a null CharField to return '' instead of
        # None.
        if connection.features.interprets_empty_strings_as_nulls:
            expected_null_charfield_repr = ""
        else:
            expected_null_charfield_repr = None
        self.assertSequenceEqual(
            Report.objects.values_list("creator__extra__info", flat=True).order_by(
                "name"
            ),
            ["e1", "e2", expected_null_charfield_repr],
        )

        # Similarly for select_related(), joins beyond an initial nullable join
        # must use outer joins so that all results are included.
        self.assertSequenceEqual(
            Report.objects.select_related("creator", "creator__extra").order_by("name"),
            [self.r1, self.r2, self.r3],
        )

        # When there are multiple paths to a table from another table, we have
        # to be careful not to accidentally reuse an inappropriate join when
        # using select_related(). We used to return the parent's Detail record
        # here by mistake.

        d1 = Detail.objects.create(data="d1")
        d2 = Detail.objects.create(data="d2")
        m1 = Member.objects.create(name="m1", details=d1)
        m2 = Member.objects.create(name="m2", details=d2)
        Child.objects.create(person=m2, parent=m1)
        obj = m1.children.select_related("person__details")[0]
        self.assertEqual(obj.person.details.data, "d2")

    def test_order_by_resetting(self):
        # Calling order_by() with no parameters removes any existing ordering on the
        # model. But it should still be possible to add new ordering after that.
        qs = Author.objects.order_by().order_by("name")
        self.assertIn("ORDER BY", qs.query.get_compiler(qs.db).as_sql()[0])

    def test_order_by_reverse_fk(self):
        # It is possible to order by reverse of foreign key, although that can lead
        # to duplicate results.
        c1 = SimpleCategory.objects.create(name="category1")
        c2 = SimpleCategory.objects.create(name="category2")
        CategoryItem.objects.create(category=c1)
        CategoryItem.objects.create(category=c2)
        CategoryItem.objects.create(category=c1)
        self.assertSequenceEqual(
            SimpleCategory.objects.order_by("categoryitem", "pk"), [c1, c2, c1]
        )

    def test_filter_reverse_non_integer_pk(self):
        """

        Tests the filtering functionality of DateTimePK objects in reverse relation to ExtraInfo objects,
        specifically when the DateTimePK object primary key is not an integer.

        Verifies that a DateTimePK object can be successfully retrieved using the filter method
        on the reverse relation with an ExtraInfo object, ensuring the correct object is returned.

        """
        date_obj = DateTimePK.objects.create()
        extra_obj = ExtraInfo.objects.create(info="extra", date=date_obj)
        self.assertEqual(
            DateTimePK.objects.filter(extrainfo=extra_obj).get(),
            date_obj,
        )

    def test_ticket10181(self):
        # Avoid raising an EmptyResultSet if an inner query is probably
        # empty (and hence, not executed).
        self.assertSequenceEqual(
            Tag.objects.filter(id__in=Tag.objects.filter(id__in=[])), []
        )

    def test_ticket15316_filter_false(self):
        """

        Tests the filtering of CategoryItems based on the existence of a related SpecialCategory instance.

        This test creates various categories, including both SimpleCategory and SpecialCategory instances, and then creates CategoryItems associated with these categories.
        It then applies a filter to retrieve CategoryItems that have a related SpecialCategory (i.e., where the specialcategory attribute is not null).
        The test verifies that the filtered query set contains exactly the CategoryItems that are associated with SpecialCategory instances, demonstrating the correctness of the filtering logic.

        """
        c1 = SimpleCategory.objects.create(name="category1")
        c2 = SpecialCategory.objects.create(
            name="named category1", special_name="special1"
        )
        c3 = SpecialCategory.objects.create(
            name="named category2", special_name="special2"
        )

        CategoryItem.objects.create(category=c1)
        ci2 = CategoryItem.objects.create(category=c2)
        ci3 = CategoryItem.objects.create(category=c3)

        qs = CategoryItem.objects.filter(category__specialcategory__isnull=False)
        self.assertEqual(qs.count(), 2)
        self.assertCountEqual(qs, [ci2, ci3])

    def test_ticket15316_exclude_false(self):
        c1 = SimpleCategory.objects.create(name="category1")
        c2 = SpecialCategory.objects.create(
            name="named category1", special_name="special1"
        )
        c3 = SpecialCategory.objects.create(
            name="named category2", special_name="special2"
        )

        ci1 = CategoryItem.objects.create(category=c1)
        CategoryItem.objects.create(category=c2)
        CategoryItem.objects.create(category=c3)

        qs = CategoryItem.objects.exclude(category__specialcategory__isnull=False)
        self.assertEqual(qs.count(), 1)
        self.assertSequenceEqual(qs, [ci1])

    def test_ticket15316_filter_true(self):
        """

        Tests that a CategoryItem queryset can be filtered to exclude items 
        with a category that has a non-null special category association.

        The test case verifies that a CategoryItem associated with a SimpleCategory 
        is correctly identified when filtering by the absence of a SpecialCategory 
        (denoted by a null special category association).

        """
        c1 = SimpleCategory.objects.create(name="category1")
        c2 = SpecialCategory.objects.create(
            name="named category1", special_name="special1"
        )
        c3 = SpecialCategory.objects.create(
            name="named category2", special_name="special2"
        )

        ci1 = CategoryItem.objects.create(category=c1)
        CategoryItem.objects.create(category=c2)
        CategoryItem.objects.create(category=c3)

        qs = CategoryItem.objects.filter(category__specialcategory__isnull=True)
        self.assertEqual(qs.count(), 1)
        self.assertSequenceEqual(qs, [ci1])

    def test_ticket15316_exclude_true(self):
        """

        Tests the functionality of excluding objects from a query set based on the existence of a related object.

        This function verifies that CategoryItem objects can be filtered to only include those that have a related SpecialCategory object.
        It checks that the exclude() method correctly removes CategoryItem objects from the query set when their related category does not have a SpecialCategory object.

        The test covers the following scenarios:

        * Creating CategoryItem objects related to both SimpleCategory and SpecialCategory objects.
        * Using the exclude() method to filter out CategoryItem objects related to SimpleCategory objects.
        * Verifying the count and contents of the resulting query set.

        The expected outcome is that the query set should only contain CategoryItem objects related to SpecialCategory objects.

        """
        c1 = SimpleCategory.objects.create(name="category1")
        c2 = SpecialCategory.objects.create(
            name="named category1", special_name="special1"
        )
        c3 = SpecialCategory.objects.create(
            name="named category2", special_name="special2"
        )

        CategoryItem.objects.create(category=c1)
        ci2 = CategoryItem.objects.create(category=c2)
        ci3 = CategoryItem.objects.create(category=c3)

        qs = CategoryItem.objects.exclude(category__specialcategory__isnull=True)
        self.assertEqual(qs.count(), 2)
        self.assertCountEqual(qs, [ci2, ci3])

    def test_ticket15316_one2one_filter_false(self):
        """
        Tests that a one-to-one filter on the CategoryItem model correctly excludes instances without an associated OneToOneCategory.

        This test case creates multiple categories and category items, some of which have a corresponding OneToOneCategory instance. It then filters the CategoryItem instances to only include those with a non-null OneToOneCategory association and verifies that the correct instances are returned.

        The filter is ordered by primary key to ensure a consistent result set for comparison. The test asserts that the filtered query set contains exactly two instances, which are the two CategoryItem instances with associated OneToOneCategory instances, and that they are returned in the correct order.
        """
        c = SimpleCategory.objects.create(name="cat")
        c0 = SimpleCategory.objects.create(name="cat0")
        c1 = SimpleCategory.objects.create(name="category1")

        OneToOneCategory.objects.create(category=c1, new_name="new1")
        OneToOneCategory.objects.create(category=c0, new_name="new2")

        CategoryItem.objects.create(category=c)
        ci2 = CategoryItem.objects.create(category=c0)
        ci3 = CategoryItem.objects.create(category=c1)

        qs = CategoryItem.objects.filter(
            category__onetoonecategory__isnull=False
        ).order_by("pk")
        self.assertEqual(qs.count(), 2)
        self.assertSequenceEqual(qs, [ci2, ci3])

    def test_ticket15316_one2one_exclude_false(self):
        c = SimpleCategory.objects.create(name="cat")
        c0 = SimpleCategory.objects.create(name="cat0")
        c1 = SimpleCategory.objects.create(name="category1")

        OneToOneCategory.objects.create(category=c1, new_name="new1")
        OneToOneCategory.objects.create(category=c0, new_name="new2")

        ci1 = CategoryItem.objects.create(category=c)
        CategoryItem.objects.create(category=c0)
        CategoryItem.objects.create(category=c1)

        qs = CategoryItem.objects.exclude(category__onetoonecategory__isnull=False)
        self.assertEqual(qs.count(), 1)
        self.assertSequenceEqual(qs, [ci1])

    def test_ticket15316_one2one_filter_true(self):
        c = SimpleCategory.objects.create(name="cat")
        c0 = SimpleCategory.objects.create(name="cat0")
        c1 = SimpleCategory.objects.create(name="category1")

        OneToOneCategory.objects.create(category=c1, new_name="new1")
        OneToOneCategory.objects.create(category=c0, new_name="new2")

        ci1 = CategoryItem.objects.create(category=c)
        CategoryItem.objects.create(category=c0)
        CategoryItem.objects.create(category=c1)

        qs = CategoryItem.objects.filter(category__onetoonecategory__isnull=True)
        self.assertEqual(qs.count(), 1)
        self.assertSequenceEqual(qs, [ci1])

    def test_ticket15316_one2one_exclude_true(self):
        """

        Tests that One-To-One relationship exclusion is properly handled.

        This test verifies that CategoryItems are correctly excluded from a query
        when their associated category has a One-To-One relationship with another model
        and `exclude` is used with `isnull=True` on that relationship.

        The test covers a scenario where multiple categories have a One-To-One relationship
        with another model, and some categories do not. It checks that the query correctly
        returns only the CategoryItems associated with categories that have a One-To-One relationship.

        """
        c = SimpleCategory.objects.create(name="cat")
        c0 = SimpleCategory.objects.create(name="cat0")
        c1 = SimpleCategory.objects.create(name="category1")

        OneToOneCategory.objects.create(category=c1, new_name="new1")
        OneToOneCategory.objects.create(category=c0, new_name="new2")

        CategoryItem.objects.create(category=c)
        ci2 = CategoryItem.objects.create(category=c0)
        ci3 = CategoryItem.objects.create(category=c1)

        qs = CategoryItem.objects.exclude(
            category__onetoonecategory__isnull=True
        ).order_by("pk")
        self.assertEqual(qs.count(), 2)
        self.assertSequenceEqual(qs, [ci2, ci3])


class Queries5Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Ordering by 'rank' gives us rank2, rank1, rank3. Ordering by the
        # Meta.ordering will be rank3, rank2, rank1.
        cls.n1 = Note.objects.create(note="n1", misc="foo", id=1)
        cls.n2 = Note.objects.create(note="n2", misc="bar", id=2)
        e1 = ExtraInfo.objects.create(info="e1", note=cls.n1)
        e2 = ExtraInfo.objects.create(info="e2", note=cls.n2)
        a1 = Author.objects.create(name="a1", num=1001, extra=e1)
        a2 = Author.objects.create(name="a2", num=2002, extra=e1)
        a3 = Author.objects.create(name="a3", num=3003, extra=e2)
        cls.rank2 = Ranking.objects.create(rank=2, author=a2)
        cls.rank1 = Ranking.objects.create(rank=1, author=a3)
        cls.rank3 = Ranking.objects.create(rank=3, author=a1)

    def test_ordering(self):
        # Cross model ordering is possible in Meta, too.
        """

        Tests the correctness of ordering in Ranking queries.

        Checks the following scenarios:
        - Natural ordering of Ranking objects
        - Ordering by the 'rank' field in ascending order
        - Ordering by the 'id' of the related 'django_site' in descending order, followed by the 'rank' field
        - Ordering using a custom SQL expression
        - Ordering by a custom SQL expression with additional fields

        Verifies that the results match the expected order in each case.

        """
        self.assertSequenceEqual(
            Ranking.objects.all(),
            [self.rank3, self.rank2, self.rank1],
        )
        self.assertSequenceEqual(
            Ranking.objects.order_by("rank"),
            [self.rank1, self.rank2, self.rank3],
        )

        # Ordering of extra() pieces is possible, too and you can mix extra
        # fields and model fields in the ordering.
        self.assertSequenceEqual(
            Ranking.objects.extra(
                tables=["django_site"], order_by=["-django_site.id", "rank"]
            ),
            [self.rank1, self.rank2, self.rank3],
        )

        sql = "case when %s > 2 then 1 else 0 end" % connection.ops.quote_name("rank")
        qs = Ranking.objects.extra(select={"good": sql})
        self.assertEqual(
            [o.good for o in qs.extra(order_by=("-good",))], [True, False, False]
        )
        self.assertSequenceEqual(
            qs.extra(order_by=("-good", "id")),
            [self.rank3, self.rank2, self.rank1],
        )

        # Despite having some extra aliases in the query, we can still omit
        # them in a values() query.
        dicts = qs.values("id", "rank").order_by("id")
        self.assertEqual([d["rank"] for d in dicts], [2, 1, 3])

    def test_ticket7256(self):
        # An empty values() call includes all aliases, including those from an
        # extra()
        sql = "case when %s > 2 then 1 else 0 end" % connection.ops.quote_name("rank")
        qs = Ranking.objects.extra(select={"good": sql})
        dicts = qs.values().order_by("id")
        for d in dicts:
            del d["id"]
            del d["author_id"]
        self.assertEqual(
            [sorted(d.items()) for d in dicts],
            [
                [("good", 0), ("rank", 2)],
                [("good", 0), ("rank", 1)],
                [("good", 1), ("rank", 3)],
            ],
        )

    def test_ticket7045(self):
        # Extra tables used to crash SQL construction on the second use.
        qs = Ranking.objects.extra(tables=["django_site"])
        qs.query.get_compiler(qs.db).as_sql()
        # test passes if this doesn't raise an exception.
        qs.query.get_compiler(qs.db).as_sql()

    def test_ticket9848(self):
        # Make sure that updates which only filter on sub-tables don't
        # inadvertently update the wrong records (bug #9848).
        """

        Tests the behavior of the Ranking model when updating the rank of an existing author.

        This test case verifies that updating the rank of a ranking object associated with a specific author
        correctly updates the rank and preserves the author and object identities.

        It checks that the update operation affects only one object, and that the updated object retains its
        original id and author reference. The test also ensures that the overall ordering of rankings is
        maintained after the update.

        """
        author_start = Author.objects.get(name="a1")
        ranking_start = Ranking.objects.get(author__name="a1")

        # Make sure that the IDs from different tables don't happen to match.
        self.assertSequenceEqual(
            Ranking.objects.filter(author__name="a1"),
            [self.rank3],
        )
        self.assertEqual(Ranking.objects.filter(author__name="a1").update(rank=4636), 1)

        r = Ranking.objects.get(author__name="a1")
        self.assertEqual(r.id, ranking_start.id)
        self.assertEqual(r.author.id, author_start.id)
        self.assertEqual(r.rank, 4636)
        r.rank = 3
        r.save()
        self.assertSequenceEqual(
            Ranking.objects.all(),
            [self.rank3, self.rank2, self.rank1],
        )

    def test_ticket5261(self):
        # Test different empty excludes.
        """

        Tests the behavior of empty Q objects in database queries.

        Verifies that excluding or filtering with an empty Q object returns all objects.
        Additionally, checks the behavior of combining empty Q objects using logical operators
        such as NOT (~), OR (|), AND (&), and XOR (^).

        """
        self.assertSequenceEqual(
            Note.objects.exclude(Q()),
            [self.n1, self.n2],
        )
        self.assertSequenceEqual(
            Note.objects.filter(~Q()),
            [self.n1, self.n2],
        )
        self.assertSequenceEqual(
            Note.objects.filter(~Q() | ~Q()),
            [self.n1, self.n2],
        )
        self.assertSequenceEqual(
            Note.objects.exclude(~Q() & ~Q()),
            [self.n1, self.n2],
        )
        self.assertSequenceEqual(
            Note.objects.exclude(~Q() ^ ~Q()),
            [self.n1, self.n2],
        )

    def test_extra_select_literal_percent_s(self):
        # Allow %%s to escape select clauses
        self.assertEqual(Note.objects.extra(select={"foo": "'%%s'"})[0].foo, "%s")
        self.assertEqual(
            Note.objects.extra(select={"foo": "'%%s bar %%s'"})[0].foo, "%s bar %s"
        )
        self.assertEqual(
            Note.objects.extra(select={"foo": "'bar %%s'"})[0].foo, "bar %s"
        )

    def test_extra_select_alias_sql_injection(self):
        """
        Tests protection against SQL injection attacks through extra select alias in database queries, specifically when using the `extra` method with the `select` parameter. Verifies that an attempt to inject malicious SQL code via a crafted alias results in a `ValueError` exception, preventing potential SQL injection vulnerabilities.
        """
        crafted_alias = """injected_name" from "queries_note"; --"""
        msg = (
            "Column aliases cannot contain whitespace characters, quotation marks, "
            "semicolons, or SQL comments."
        )
        with self.assertRaisesMessage(ValueError, msg):
            Note.objects.extra(select={crafted_alias: "1"})

    def test_queryset_reuse(self):
        # Using querysets doesn't mutate aliases.
        """
        Tests the reusability of a queryset in filtering Ranking objects.

        This test case verifies that a queryset can be reused to filter related objects,
        in this case, Ranking objects that belong to a specific set of authors.
        It checks that the correct Ranking object is retrieved and that the query
        only returns a single author object, as expected when searching for a specific name.
        The test also confirms that the queryset can be reused for counting the number of authors,
        yielding the expected result of one author matching the specified criteria.
        """
        authors = Author.objects.filter(Q(name="a1") | Q(name="nonexistent"))
        self.assertEqual(Ranking.objects.filter(author__in=authors).get(), self.rank3)
        self.assertEqual(authors.count(), 1)

    def test_filter_unsaved_object(self):
        msg = "Model instances passed to related filters must be saved."
        company = Company.objects.create(name="Django")
        with self.assertRaisesMessage(ValueError, msg):
            Employment.objects.filter(employer=Company(name="unsaved"))
        with self.assertRaisesMessage(ValueError, msg):
            Employment.objects.filter(employer__in=[company, Company(name="unsaved")])
        with self.assertRaisesMessage(ValueError, msg):
            StaffUser.objects.filter(staff=Staff(name="unsaved"))


class SelectRelatedTests(TestCase):
    def test_tickets_3045_3288(self):
        # Once upon a time, select_related() with circular relations would loop
        # infinitely if you forgot to specify "depth". Now we set an arbitrary
        # default upper bound.
        self.assertSequenceEqual(X.objects.all(), [])
        self.assertSequenceEqual(X.objects.select_related(), [])


class SubclassFKTests(TestCase):
    def test_ticket7778(self):
        # Model subclasses could not be deleted if a nullable foreign key
        # relates to a model that relates back.

        num_celebs = Celebrity.objects.count()
        tvc = TvChef.objects.create(name="Huey")
        self.assertEqual(Celebrity.objects.count(), num_celebs + 1)
        Fan.objects.create(fan_of=tvc)
        Fan.objects.create(fan_of=tvc)
        tvc.delete()

        # The parent object should have been deleted as well.
        self.assertEqual(Celebrity.objects.count(), num_celebs)


class CustomPkTests(TestCase):
    def test_ticket7371(self):
        self.assertQuerySetEqual(Related.objects.order_by("custom"), [])


class NullableRelOrderingTests(TestCase):
    def test_ticket10028(self):
        # Ordering by model related to nullable relations(!) should use outer
        # joins, so that all results are included.
        """
        Tests that creating a single Plaything object results in the correct sequence of objects being returned by Plaything.objects.all(), ensuring that the created object is properly persisted and retrieved.
        """
        p1 = Plaything.objects.create(name="p1")
        self.assertSequenceEqual(Plaything.objects.all(), [p1])

    def test_join_already_in_query(self):
        # Ordering by model related to nullable relations should not change
        # the join type of already existing joins.
        """

        Tests the behavior of Django's ORM when joining related objects in a query.

        Verifies that an implicit join is not performed when filtering on a nullable
        foreign key field, but an explicit inner join is performed when filtering on
        a non-nullable foreign key field of a related object.

        Additionally, checks that the query correctly handles ordering by a related
        object's field, resulting in the correct type and number of joins.

        Ensures the final query returns the expected results, specifically the
        Plaything object that matches the filter criteria.

        """
        Plaything.objects.create(name="p1")
        s = SingleObject.objects.create(name="s")
        r = RelatedObject.objects.create(single=s, f=1)
        p2 = Plaything.objects.create(name="p2", others=r)
        qs = Plaything.objects.filter(others__isnull=False).order_by("pk")
        self.assertNotIn("JOIN", str(qs.query))
        qs = Plaything.objects.filter(others__f__isnull=False).order_by("pk")
        self.assertIn("INNER", str(qs.query))
        qs = qs.order_by("others__single__name")
        # The ordering by others__single__pk will add one new join (to single)
        # and that join must be LEFT join. The already existing join to related
        # objects must be kept INNER. So, we have both an INNER and a LEFT join
        # in the query.
        self.assertEqual(str(qs.query).count("LEFT"), 1)
        self.assertEqual(str(qs.query).count("INNER"), 1)
        self.assertSequenceEqual(qs, [p2])


class DisjunctiveFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """

        Set up test data for the class.

        This method creates a test note and related extra information, 
        which are then stored as class attributes for use in tests. 
        The created test data includes a note with a specific ID and 
        associated extra information, allowing for comprehensive testing 
        of related functionality.

        :returns: None

        """
        cls.n1 = Note.objects.create(note="n1", misc="foo", id=1)
        cls.e1 = ExtraInfo.objects.create(info="e1", note=cls.n1)

    def test_ticket7872(self):
        # Another variation on the disjunctive filtering theme.

        # For the purposes of this regression test, it's important that there is no
        # Join object related to the LeafA we create.
        """

        Tests the correct functionality of filtering LeafA objects based on data and join conditions.

        This test creates a LeafA object with 'data' set to 'first' and verifies that it is correctly retrieved when filtering by 'data' or by related 'join' object's 'b' attribute.

        """
        l1 = LeafA.objects.create(data="first")
        self.assertSequenceEqual(LeafA.objects.all(), [l1])
        self.assertSequenceEqual(
            LeafA.objects.filter(Q(data="first") | Q(join__b__data="second")),
            [l1],
        )

    def test_ticket8283(self):
        # Checking that applying filters after a disjunction works correctly.
        self.assertSequenceEqual(
            (
                ExtraInfo.objects.filter(note=self.n1)
                | ExtraInfo.objects.filter(info="e2")
            ).filter(note=self.n1),
            [self.e1],
        )
        self.assertSequenceEqual(
            (
                ExtraInfo.objects.filter(info="e2")
                | ExtraInfo.objects.filter(note=self.n1)
            ).filter(note=self.n1),
            [self.e1],
        )


class Queries6Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        generic = NamedCategory.objects.create(name="Generic")
        cls.t1 = Tag.objects.create(name="t1", category=generic)
        cls.t2 = Tag.objects.create(name="t2", parent=cls.t1, category=generic)
        cls.t3 = Tag.objects.create(name="t3", parent=cls.t1)
        cls.t4 = Tag.objects.create(name="t4", parent=cls.t3)
        cls.t5 = Tag.objects.create(name="t5", parent=cls.t3)
        n1 = Note.objects.create(note="n1", misc="foo", id=1)
        cls.ann1 = Annotation.objects.create(name="a1", tag=cls.t1)
        cls.ann1.notes.add(n1)
        cls.ann2 = Annotation.objects.create(name="a2", tag=cls.t4)

    def test_parallel_iterators(self):
        # Parallel iterators work.
        qs = Tag.objects.all()
        i1, i2 = iter(qs), iter(qs)
        self.assertEqual(repr(next(i1)), "<Tag: t1>")
        self.assertEqual(repr(next(i1)), "<Tag: t2>")
        self.assertEqual(repr(next(i2)), "<Tag: t1>")
        self.assertEqual(repr(next(i2)), "<Tag: t2>")
        self.assertEqual(repr(next(i2)), "<Tag: t3>")
        self.assertEqual(repr(next(i1)), "<Tag: t3>")

        qs = X.objects.all()
        self.assertFalse(qs)
        self.assertFalse(qs)

    def test_nested_queries_sql(self):
        # Nested queries should not evaluate the inner query as part of constructing the
        # SQL (so we should see a nested query here, indicated by two "SELECT" calls).
        """
        Tests the generation of SQL queries for nested queries using Django's ORM. 

        Verifies that the query resulting from filtering annotations based on a nested filter of notes contains the expected number of subqueries, ensuring efficient database querying.
        """
        qs = Annotation.objects.filter(notes__in=Note.objects.filter(note="xyzzy"))
        self.assertEqual(qs.query.get_compiler(qs.db).as_sql()[0].count("SELECT"), 2)

    def test_tickets_8921_9188(self):
        # Incorrect SQL was being generated for certain types of exclude()
        # queries that crossed multi-valued relations (#8921, #9188 and some
        # preemptively discovered cases).

        """

        Tests the correctness of various database queries involving related models.

        This test case ensures that the correct results are returned when using 
        filter and exclude methods on objects related through foreign keys. 
        Specifically, it checks the following scenarios:
        - Filtering and excluding PointerA objects based on a related PointerB object
        - Excluding Tag objects with children or a specific parent annotation
        - Excluding Annotation objects with a specific child tag
        - Filtering Annotation objects based on a related Note object

        The test verifies that the expected results are returned for each query, 
        ensuring that the database relationships and queries are functioning as expected.

        """
        self.assertSequenceEqual(
            PointerA.objects.filter(connection__pointerb__id=1), []
        )
        self.assertSequenceEqual(
            PointerA.objects.exclude(connection__pointerb__id=1), []
        )

        self.assertSequenceEqual(
            Tag.objects.exclude(children=None),
            [self.t1, self.t3],
        )

        # This example is tricky because the parent could be NULL, so only checking
        # parents with annotations omits some results (tag t1, in this case).
        self.assertSequenceEqual(
            Tag.objects.exclude(parent__annotation__name="a1"),
            [self.t1, self.t4, self.t5],
        )

        # The annotation->tag link is single values and tag->children links is
        # multi-valued. So we have to split the exclude filter in the middle
        # and then optimize the inner query without losing results.
        self.assertSequenceEqual(
            Annotation.objects.exclude(tag__children__name="t2"),
            [self.ann2],
        )

        # Nested queries are possible (although should be used with care, since
        # they have performance problems on backends like MySQL.
        self.assertSequenceEqual(
            Annotation.objects.filter(notes__in=Note.objects.filter(note="n1")),
            [self.ann1],
        )

    def test_ticket3739(self):
        # The all() method on querysets returns a copy of the queryset.
        """
        Tests the behavior of the `all()` method on a queryset ordered by a specific field.

        This test case verifies that calling `all()` on a queryset that has been ordered by a field (in this case, 'name') returns a new queryset object, rather than the original queryset itself.

        The purpose of this test is to ensure that the `all()` method behaves correctly and does not return the same object, which could potentially lead to unintended behavior or side effects.

        Related to ticket #3739.
        """
        q1 = Tag.objects.order_by("name")
        self.assertIsNot(q1, q1.all())

    def test_ticket_11320(self):
        """
        Tests the query optimization for Tag objects to ensure the correct use of INNER JOINs.

        This test case verifies that when excluding Tag objects based on specific category conditions, 
        the resulting query string contains the expected number of INNER JOIN operations, which is one.
        It covers the scenario where Tags are filtered by excluding those with a null category and those 
        belonging to a category named 'foo', thus ensuring efficient database querying.

        """
        qs = Tag.objects.exclude(category=None).exclude(category__name="foo")
        self.assertEqual(str(qs.query).count(" INNER JOIN "), 1)

    def test_distinct_ordered_sliced_subquery_aggregation(self):
        self.assertEqual(
            Tag.objects.distinct().order_by("category__name")[:3].count(), 3
        )

    def test_multiple_columns_with_the_same_name_slice(self):
        """

        Tests the functionality of querying and slicing data across multiple columns with the same name.

        This function verifies that the database queries correctly handle columns with identical names
        from different related tables. It checks both ascending and descending ordering, and ensures
        that the results are correctly sliced and returned.

        The tests cover the following scenarios:
        - Ordering by a column and retrieving values from related tables
        - Using select_related to fetch related objects and maintaining the correct order
        - Handling duplicate column names from different tables
        - Querying in both ascending and descending order, and slicing the results.

        """
        self.assertEqual(
            list(
                Tag.objects.order_by("name").values_list("name", "category__name")[:2]
            ),
            [("t1", "Generic"), ("t2", "Generic")],
        )
        self.assertSequenceEqual(
            Tag.objects.order_by("name").select_related("category")[:2],
            [self.t1, self.t2],
        )
        self.assertEqual(
            list(Tag.objects.order_by("-name").values_list("name", "parent__name")[:2]),
            [("t5", "t3"), ("t4", "t3")],
        )
        self.assertSequenceEqual(
            Tag.objects.order_by("-name").select_related("parent")[:2],
            [self.t5, self.t4],
        )

    def test_col_alias_quoted(self):
        with CaptureQueriesContext(connection) as captured_queries:
            self.assertEqual(
                Tag.objects.values("parent")
                .annotate(
                    tag_per_parent=Count("pk"),
                )
                .aggregate(Max("tag_per_parent")),
                {"tag_per_parent__max": 2},
            )
        sql = captured_queries[0]["sql"]
        self.assertIn("AS %s" % connection.ops.quote_name("parent"), sql)

    def test_xor_subquery(self):
        self.assertSequenceEqual(
            Tag.objects.filter(
                Exists(Tag.objects.filter(id=OuterRef("id"), name="t3"))
                ^ Exists(Tag.objects.filter(id=OuterRef("id"), parent=self.t1))
            ),
            [self.t2],
        )


class RawQueriesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Note.objects.create(note="n1", misc="foo", id=1)

    def test_ticket14729(self):
        # Test representation of raw query with one or few parameters passed as list
        """
        Test the raw SQL query functionality of the Note model by checking if the query string in the RawQuerySet representation matches the expected string. 

        The function tests two different raw SQL queries: 
        - One with a single parameter, and 
        - One with multiple parameters. 

        In both cases, it verifies that the RawQuerySet representation correctly reflects the query string and the parameters used. This ensures that the raw SQL queries are properly constructed and executed.
        """
        query = "SELECT * FROM queries_note WHERE note = %s"
        params = ["n1"]
        qs = Note.objects.raw(query, params=params)
        self.assertEqual(
            repr(qs), "<RawQuerySet: SELECT * FROM queries_note WHERE note = n1>"
        )

        query = "SELECT * FROM queries_note WHERE note = %s and misc = %s"
        params = ["n1", "foo"]
        qs = Note.objects.raw(query, params=params)
        self.assertEqual(
            repr(qs),
            "<RawQuerySet: SELECT * FROM queries_note WHERE note = n1 and misc = foo>",
        )


class GeneratorExpressionTests(SimpleTestCase):
    def test_ticket10432(self):
        # Using an empty iterator as the rvalue for an "__in"
        # lookup is legal.
        self.assertCountEqual(Note.objects.filter(pk__in=iter(())), [])


class ComparisonTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """

        Set up test data for a test class, creating a set of interconnected objects.

        This method initializes a basic dataset for testing, including a Note, its associated ExtraInfo, and an Author linked to the ExtraInfo.

        The created objects are stored as class attributes, allowing easy access and reuse throughout the test class.

        """
        cls.n1 = Note.objects.create(note="n1", misc="foo", id=1)
        e1 = ExtraInfo.objects.create(info="e1", note=cls.n1)
        cls.a2 = Author.objects.create(name="a2", num=2002, extra=e1)

    def test_ticket8597(self):
        # Regression tests for case-insensitive comparisons
        item_ab = Item.objects.create(
            name="a_b", created=datetime.datetime.now(), creator=self.a2, note=self.n1
        )
        item_xy = Item.objects.create(
            name="x%y", created=datetime.datetime.now(), creator=self.a2, note=self.n1
        )
        self.assertSequenceEqual(
            Item.objects.filter(name__iexact="A_b"),
            [item_ab],
        )
        self.assertSequenceEqual(
            Item.objects.filter(name__iexact="x%Y"),
            [item_xy],
        )
        self.assertSequenceEqual(
            Item.objects.filter(name__istartswith="A_b"),
            [item_ab],
        )
        self.assertSequenceEqual(
            Item.objects.filter(name__iendswith="A_b"),
            [item_ab],
        )


class ExistsSql(TestCase):
    def test_exists(self):
        """

        Tests whether the exists method of the Tag model does not 
        trigger a database query that includes the 'id' and 'name' 
        fields in the SQL string.

        This function first captures the database queries triggered 
        by the Tag model's exists method, then checks that only one 
        query was executed. It then verifies that the SQL query string 
        does not include the 'id' and 'name' fields, ensuring the 
        database query is optimized to only retrieve the minimum 
        necessary information.

        """
        with CaptureQueriesContext(connection) as captured_queries:
            self.assertFalse(Tag.objects.exists())
        # Ok - so the exist query worked - but did it include too many columns?
        self.assertEqual(len(captured_queries), 1)
        qstr = captured_queries[0]["sql"]
        id, name = connection.ops.quote_name("id"), connection.ops.quote_name("name")
        self.assertNotIn(id, qstr)
        self.assertNotIn(name, qstr)

    def test_distinct_exists(self):
        """

        Tests that the 'distinct' method does not include unnecessary columns in the SQL query.

        This test verifies that when using 'distinct' on a Django ORM query, 
        the generated SQL query only contains the required columns and does not 
        reference any columns that are not needed for distinctness (like 'id' or 'name' in this case).
        It also checks that the 'exists' method on a 'distinct' query returns the correct result 
        and that the query is executed efficiently, generating only one database query.

        """
        with CaptureQueriesContext(connection) as captured_queries:
            self.assertIs(Article.objects.distinct().exists(), False)
        self.assertEqual(len(captured_queries), 1)
        captured_sql = captured_queries[0]["sql"]
        self.assertNotIn(connection.ops.quote_name("id"), captured_sql)
        self.assertNotIn(connection.ops.quote_name("name"), captured_sql)

    def test_sliced_distinct_exists(self):
        """
        Tests the exists method on a sliced QuerySet with distinct results.

        This test case verifies that the exists method on a distinct QuerySet slice does not
        execute multiple database queries and checks the generated SQL to ensure it quotes 
        the 'id' and 'name' columns correctly.

        The test also confirms that the exists method returns False when the sliced QuerySet 
        is empty, as expected.

        The database queries generated during this test are captured and verified to ensure 
        only one query is executed, fulfilling the performance optimization goal of using 
        the exists method for QuerySet slices with distinct results.
        """
        with CaptureQueriesContext(connection) as captured_queries:
            self.assertIs(Article.objects.distinct()[1:3].exists(), False)
        self.assertEqual(len(captured_queries), 1)
        captured_sql = captured_queries[0]["sql"]
        self.assertIn(connection.ops.quote_name("id"), captured_sql)
        self.assertIn(connection.ops.quote_name("name"), captured_sql)

    def test_ticket_18414(self):
        """

        Test the functionality of Django's ORM to create and query database objects.

        This test case creates multiple Article objects with duplicate names and checks the
        existence of these objects in the database. It verifies that the exists() method
        correctly returns True for existing queries and False for non-existing queries,
        including when using the distinct() method to remove duplicates and slicing to
        limit the query results.

        The test covers the following scenarios:
        - Creating duplicate objects
        - Checking existence of all objects
        - Checking existence of distinct objects
        - Checking existence of a sliced query with multiple objects
        - Checking existence of a sliced query with no objects

        """
        Article.objects.create(name="one", created=datetime.datetime.now())
        Article.objects.create(name="one", created=datetime.datetime.now())
        Article.objects.create(name="two", created=datetime.datetime.now())
        self.assertTrue(Article.objects.exists())
        self.assertTrue(Article.objects.distinct().exists())
        self.assertTrue(Article.objects.distinct()[1:3].exists())
        self.assertFalse(Article.objects.distinct()[1:1].exists())

    @skipUnlessDBFeature("can_distinct_on_fields")
    def test_ticket_18414_distinct_on(self):
        """

        Tests the ability to select distinct objects based on specific fields.

        This test case verifies that the `distinct` method works correctly when 
        used on a model's queryset, ensuring that only unique objects are returned 
        based on the specified field. It also checks the correctness of pagination 
        when using the `distinct` method.

        It covers the following scenarios:
        - Selecting distinct objects based on a field with duplicate values.
        - Selecting a subset of distinct objects using slicing.
        - Verifying that an empty queryset is returned when the slice starts 
          after the last distinct object.

        """
        Article.objects.create(name="one", created=datetime.datetime.now())
        Article.objects.create(name="one", created=datetime.datetime.now())
        Article.objects.create(name="two", created=datetime.datetime.now())
        self.assertTrue(Article.objects.distinct("name").exists())
        self.assertTrue(Article.objects.distinct("name")[1:2].exists())
        self.assertFalse(Article.objects.distinct("name")[2:3].exists())


class QuerysetOrderedTests(unittest.TestCase):
    """
    Tests for the Queryset.ordered attribute.
    """

    def test_no_default_or_explicit_ordering(self):
        self.assertIs(Annotation.objects.all().ordered, False)

    def test_cleared_default_ordering(self):
        """

        Tests that the default ordering of Tag objects is cleared when ordering is explicitly reset.

        Checks if the default ordering of Tag objects is initially applied when retrieved from the database, 
        and then verifies that this ordering is removed when the `order_by` method is called without any arguments.

        """
        self.assertIs(Tag.objects.all().ordered, True)
        self.assertIs(Tag.objects.order_by().ordered, False)

    def test_explicit_ordering(self):
        self.assertIs(Annotation.objects.order_by("id").ordered, True)

    def test_empty_queryset(self):
        self.assertIs(Annotation.objects.none().ordered, True)

    def test_order_by_extra(self):
        self.assertIs(Annotation.objects.extra(order_by=["id"]).ordered, True)

    def test_annotated_ordering(self):
        qs = Annotation.objects.annotate(num_notes=Count("notes"))
        self.assertIs(qs.ordered, False)
        self.assertIs(qs.order_by("num_notes").ordered, True)

    def test_annotated_default_ordering(self):
        qs = Tag.objects.annotate(num_notes=Count("pk"))
        self.assertIs(qs.ordered, False)
        self.assertIs(qs.order_by("name").ordered, True)

    def test_annotated_values_default_ordering(self):
        """
        Tests that annotated values are not ordered by default, but can be ordered.

        Verifies that a QuerySet with annotated values does not have a default ordering,
        and that applying an order_by clause correctly sets the ordering.

        Checks the behavior of annotated QuerySets with default and explicit ordering,
        ensuring correct results for both cases.
        """
        qs = Tag.objects.values("name").annotate(num_notes=Count("pk"))
        self.assertIs(qs.ordered, False)
        self.assertIs(qs.order_by("name").ordered, True)


@skipUnlessDBFeature("allow_sliced_subqueries_with_in")
class SubqueryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        NamedCategory.objects.create(id=1, name="first")
        NamedCategory.objects.create(id=2, name="second")
        NamedCategory.objects.create(id=3, name="third")
        NamedCategory.objects.create(id=4, name="fourth")

    def test_ordered_subselect(self):
        "Subselects honor any manual ordering"
        query = DumbCategory.objects.filter(
            id__in=DumbCategory.objects.order_by("-id")[0:2]
        )
        self.assertEqual(set(query.values_list("id", flat=True)), {3, 4})

        query = DumbCategory.objects.filter(
            id__in=DumbCategory.objects.order_by("-id")[:2]
        )
        self.assertEqual(set(query.values_list("id", flat=True)), {3, 4})

        query = DumbCategory.objects.filter(
            id__in=DumbCategory.objects.order_by("-id")[1:2]
        )
        self.assertEqual(set(query.values_list("id", flat=True)), {3})

        query = DumbCategory.objects.filter(
            id__in=DumbCategory.objects.order_by("-id")[2:]
        )
        self.assertEqual(set(query.values_list("id", flat=True)), {1, 2})

    def test_slice_subquery_and_query(self):
        """
        Slice a query that has a sliced subquery
        """
        query = DumbCategory.objects.filter(
            id__in=DumbCategory.objects.order_by("-id")[0:2]
        ).order_by("id")[0:2]
        self.assertSequenceEqual([x.id for x in query], [3, 4])

        query = DumbCategory.objects.filter(
            id__in=DumbCategory.objects.order_by("-id")[1:3]
        ).order_by("id")[1:3]
        self.assertSequenceEqual([x.id for x in query], [3])

        query = DumbCategory.objects.filter(
            id__in=DumbCategory.objects.order_by("-id")[2:]
        ).order_by("id")[1:]
        self.assertSequenceEqual([x.id for x in query], [2])

    def test_related_sliced_subquery(self):
        """
        Related objects constraints can safely contain sliced subqueries.
        refs #22434
        """
        generic = NamedCategory.objects.create(id=5, name="Generic")
        t1 = Tag.objects.create(name="t1", category=generic)
        t2 = Tag.objects.create(name="t2", category=generic)
        ManagedModel.objects.create(data="mm1", tag=t1, public=True)
        mm2 = ManagedModel.objects.create(data="mm2", tag=t2, public=True)

        query = ManagedModel.normal_manager.filter(
            tag__in=Tag.objects.order_by("-id")[:1]
        )
        self.assertEqual({x.id for x in query}, {mm2.id})

    def test_sliced_delete(self):
        "Delete queries can safely contain sliced subqueries"
        DumbCategory.objects.filter(
            id__in=DumbCategory.objects.order_by("-id")[0:1]
        ).delete()
        self.assertEqual(
            set(DumbCategory.objects.values_list("id", flat=True)), {1, 2, 3}
        )

        DumbCategory.objects.filter(
            id__in=DumbCategory.objects.order_by("-id")[1:2]
        ).delete()
        self.assertEqual(set(DumbCategory.objects.values_list("id", flat=True)), {1, 3})

        DumbCategory.objects.filter(
            id__in=DumbCategory.objects.order_by("-id")[1:]
        ).delete()
        self.assertEqual(set(DumbCategory.objects.values_list("id", flat=True)), {3})

    def test_distinct_ordered_sliced_subquery(self):
        # Implicit values('id').
        """
        Tests the combination of distinct, ordered, and sliced subqueries in Django ORM queries.

        This function ensures that when using subqueries with distinct, order_by, and slicing,
        the resulting main query returns the expected values. The tests cover different scenarios,
        including ordering by a specific field, using distinct with ordering, and applying annotations
        before ordering and slicing. The results are then compared to the expected ordered sequence.

        """
        self.assertSequenceEqual(
            NamedCategory.objects.filter(
                id__in=NamedCategory.objects.distinct().order_by("name")[0:2],
            )
            .order_by("name")
            .values_list("name", flat=True),
            ["first", "fourth"],
        )
        # Explicit values('id').
        self.assertSequenceEqual(
            NamedCategory.objects.filter(
                id__in=NamedCategory.objects.distinct()
                .order_by("-name")
                .values("id")[0:2],
            )
            .order_by("name")
            .values_list("name", flat=True),
            ["second", "third"],
        )
        # Annotated value.
        self.assertSequenceEqual(
            DumbCategory.objects.filter(
                id__in=DumbCategory.objects.annotate(double_id=F("id") * 2)
                .order_by("id")
                .distinct()
                .values("double_id")[0:2],
            )
            .order_by("id")
            .values_list("id", flat=True),
            [2, 4],
        )


class QuerySetBitwiseOperationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for the test class.

        This method creates a school, multiple classrooms with varying attributes, 
        annotations, base users, a task, and their respective associations. 
        It populates the test class with class-level attributes that can be 
        used throughout the tests, providing a consistent test environment.

        The created test data includes:
        - A school instance
        - Multiple classroom instances with different attributes
        - Annotation instances with associated tags
        - Base user instances associated with annotations
        - A task instance associated with a base user and note
        """
        cls.school = School.objects.create()
        cls.room_1 = Classroom.objects.create(
            school=cls.school, has_blackboard=False, name="Room 1"
        )
        cls.room_2 = Classroom.objects.create(
            school=cls.school, has_blackboard=True, name="Room 2"
        )
        cls.room_3 = Classroom.objects.create(
            school=cls.school, has_blackboard=True, name="Room 3"
        )
        cls.room_4 = Classroom.objects.create(
            school=cls.school, has_blackboard=False, name="Room 4"
        )
        tag = Tag.objects.create()
        cls.annotation_1 = Annotation.objects.create(tag=tag)
        annotation_2 = Annotation.objects.create(tag=tag)
        note = cls.annotation_1.notes.create(tag=tag)
        cls.base_user_1 = BaseUser.objects.create(annotation=cls.annotation_1)
        cls.base_user_2 = BaseUser.objects.create(annotation=annotation_2)
        cls.task = Task.objects.create(
            owner=cls.base_user_2,
            creator=cls.base_user_2,
            note=note,
        )

    @skipUnlessDBFeature("allow_sliced_subqueries_with_in")
    def test_or_with_rhs_slice(self):
        """
        Tests that the OR operator works correctly with a right-hand side slice.

        Verifies that combining two querysets using the OR operator (|) preserves the
        expected results, even when the right-hand side queryset is sliced. The test
        ensures that the resulting combined queryset contains all elements from both
        the original querysets.

        Requirements:
            - A database backend that supports sliced subqueries with IN.

        """
        qs1 = Classroom.objects.filter(has_blackboard=True)
        qs2 = Classroom.objects.filter(has_blackboard=False)[:1]
        self.assertCountEqual(qs1 | qs2, [self.room_1, self.room_2, self.room_3])

    @skipUnlessDBFeature("allow_sliced_subqueries_with_in")
    def test_or_with_lhs_slice(self):
        qs1 = Classroom.objects.filter(has_blackboard=True)[:1]
        qs2 = Classroom.objects.filter(has_blackboard=False)
        self.assertCountEqual(qs1 | qs2, [self.room_1, self.room_2, self.room_4])

    @skipUnlessDBFeature("allow_sliced_subqueries_with_in")
    def test_or_with_both_slice(self):
        """
        Tests the OR operation with sliced querysets that use the IN operator.

        This test checks if the union of two sliced querysets, one containing classrooms without a blackboard and the other containing classrooms with a blackboard, returns the expected combined results.

        The test relies on the database feature to allow sliced subqueries with IN, ensuring that the querysets are properly handled and merged.

        Validates that the resulting queryset contains the expected classrooms, demonstrating correct handling of the OR operation with sliced querysets.
        """
        qs1 = Classroom.objects.filter(has_blackboard=False)[:1]
        qs2 = Classroom.objects.filter(has_blackboard=True)[:1]
        self.assertCountEqual(qs1 | qs2, [self.room_1, self.room_2])

    @skipUnlessDBFeature("allow_sliced_subqueries_with_in")
    def test_or_with_both_slice_and_ordering(self):
        qs1 = Classroom.objects.filter(has_blackboard=False).order_by("-pk")[:1]
        qs2 = Classroom.objects.filter(has_blackboard=True).order_by("-name")[:1]
        self.assertCountEqual(qs1 | qs2, [self.room_3, self.room_4])

    @skipUnlessDBFeature("allow_sliced_subqueries_with_in")
    def test_xor_with_rhs_slice(self):
        """
        Tests the XOR operator (^) with a sliced right-hand side queryset.

        This test case covers the scenario where the right-hand side of the XOR
        operation is a sliced queryset. It verifies that the resulting queryset
        contains the expected objects, demonstrating the correct application of
        the XOR operator in this context. The test requires a database feature
        that allows sliced subqueries with IN operators to be executed.

        The test evaluates the XOR operation between two querysets: one filtering
        Classrooms with a blackboard and the other filtering Classrooms without
        a blackboard, with the latter being limited to a single result. The
        resulting queryset should contain the expected set of Classrooms, with
        the XOR operation correctly combining the two querysets.
        """
        qs1 = Classroom.objects.filter(has_blackboard=True)
        qs2 = Classroom.objects.filter(has_blackboard=False)[:1]
        self.assertCountEqual(qs1 ^ qs2, [self.room_1, self.room_2, self.room_3])

    @skipUnlessDBFeature("allow_sliced_subqueries_with_in")
    def test_xor_with_lhs_slice(self):
        """
        Tests the XOR operation between a sliced queryset and a full queryset on the Classroom model, 
        verifying that the result includes the expected rooms. This test case is skipped unless 
        the database feature 'allow_sliced_subqueries_with_in' is supported. The test asserts that 
        the count of rooms in the resulting queryset is equal to the count of the expected rooms, 
        which are rooms that have a blackboard and those that do not, demonstrating the correctness 
        of the XOR operation in this specific database setup.
        """
        qs1 = Classroom.objects.filter(has_blackboard=True)[:1]
        qs2 = Classroom.objects.filter(has_blackboard=False)
        self.assertCountEqual(qs1 ^ qs2, [self.room_1, self.room_2, self.room_4])

    @skipUnlessDBFeature("allow_sliced_subqueries_with_in")
    def test_xor_with_both_slice(self):
        """

        Tests the exclusivity operator (^) on querysets with sliced subqueries 
        containing the IN operator, checking for correct results when combining
        two querysets for classrooms that have or do not have a blackboard.

        The function compares the union of two querysets, one for classrooms 
        with a blackboard and another for classrooms without a blackboard, 
        both limited to a single result, and verifies that the combined result 
        contains the expected classrooms.

        Requires the 'allow_sliced_subqueries_with_in' database feature.

        """
        qs1 = Classroom.objects.filter(has_blackboard=False)[:1]
        qs2 = Classroom.objects.filter(has_blackboard=True)[:1]
        self.assertCountEqual(qs1 ^ qs2, [self.room_1, self.room_2])

    @skipUnlessDBFeature("allow_sliced_subqueries_with_in")
    def test_xor_with_both_slice_and_ordering(self):
        """

        Tests the XOR (^) operator on two querysets with both slicing and ordering applied.

        This test case verifies that the XOR operation correctly combines two querysets, 
        which are filtered by different conditions, ordered by different fields, and limited to a single result.
        It checks if the resulting queryset contains the expected objects, 
        demonstrating the correct application of the XOR operator in this scenario.

        """
        qs1 = Classroom.objects.filter(has_blackboard=False).order_by("-pk")[:1]
        qs2 = Classroom.objects.filter(has_blackboard=True).order_by("-name")[:1]
        self.assertCountEqual(qs1 ^ qs2, [self.room_3, self.room_4])

    def test_subquery_aliases(self):
        """
        Tests the usage of subquery aliases in database queries.

        Verifies that the School objects are correctly filtered using subqueries
        with aliasing, ensuring that the resulting query returns the expected
        School instance. Additionally, tests the re-use of the combined query
        in a nested query, confirming that the same School instance is returned.

        """
        combined = School.objects.filter(pk__isnull=False) & School.objects.filter(
            Exists(
                Classroom.objects.filter(
                    has_blackboard=True,
                    school=OuterRef("pk"),
                )
            ),
        )
        self.assertSequenceEqual(combined, [self.school])
        nested_combined = School.objects.filter(pk__in=combined.values("pk"))
        self.assertSequenceEqual(nested_combined, [self.school])

    def test_conflicting_aliases_during_combine(self):
        qs1 = self.annotation_1.baseuser_set.all()
        qs2 = BaseUser.objects.filter(
            Q(owner__note__in=self.annotation_1.notes.all())
            | Q(creator__note__in=self.annotation_1.notes.all())
        )
        self.assertSequenceEqual(qs1, [self.base_user_1])
        self.assertSequenceEqual(qs2, [self.base_user_2])
        self.assertCountEqual(qs2 | qs1, qs1 | qs2)
        self.assertCountEqual(qs2 | qs1, [self.base_user_1, self.base_user_2])


class CloneTests(TestCase):
    def test_evaluated_queryset_as_argument(self):
        """
        If a queryset is already evaluated, it can still be used as a query arg.
        """
        n = Note(note="Test1", misc="misc")
        n.save()
        e = ExtraInfo(info="good", note=n)
        e.save()

        n_list = Note.objects.all()
        # Evaluate the Note queryset, populating the query cache
        list(n_list)
        # Make one of cached results unpickable.
        n_list._result_cache[0].error = UnpickleableError()
        with self.assertRaises(UnpickleableError):
            pickle.dumps(n_list)
        # Use the note queryset in a query, and evaluate
        # that query in a way that involves cloning.
        self.assertEqual(ExtraInfo.objects.filter(note__in=n_list)[0].info, "good")

    def test_no_model_options_cloning(self):
        """
        Cloning a queryset does not get out of hand. While complete
        testing is impossible, this is a sanity check against invalid use of
        deepcopy. refs #16759.
        """
        opts_class = type(Note._meta)
        note_deepcopy = getattr(opts_class, "__deepcopy__", None)
        opts_class.__deepcopy__ = lambda obj, memo: self.fail(
            "Model options shouldn't be cloned."
        )
        try:
            Note.objects.filter(pk__lte=F("pk") + 1).all()
        finally:
            if note_deepcopy is None:
                delattr(opts_class, "__deepcopy__")
            else:
                opts_class.__deepcopy__ = note_deepcopy

    def test_no_fields_cloning(self):
        """
        Cloning a queryset does not get out of hand. While complete
        testing is impossible, this is a sanity check against invalid use of
        deepcopy. refs #16759.
        """
        opts_class = type(Note._meta.get_field("misc"))
        note_deepcopy = getattr(opts_class, "__deepcopy__", None)
        opts_class.__deepcopy__ = lambda obj, memo: self.fail(
            "Model fields shouldn't be cloned"
        )
        try:
            Note.objects.filter(note=F("misc")).all()
        finally:
            if note_deepcopy is None:
                delattr(opts_class, "__deepcopy__")
            else:
                opts_class.__deepcopy__ = note_deepcopy


class EmptyQuerySetTests(SimpleTestCase):
    def test_emptyqueryset_values(self):
        # #14366 -- Calling .values() on an empty QuerySet and then cloning
        # that should not cause an error
        self.assertCountEqual(Number.objects.none().values("num").order_by("num"), [])

    def test_values_subquery(self):
        """
        Tests the behavior of Django ORM subqueries when using empty querysets.

        Verifies that filtering by primary key on an empty queryset results in an empty queryset, 
        both when using the values() and values_list() methods. Ensures that the resulting 
        querysets are identical and contain no elements, confirming the expected behavior 
        of database subqueries in this edge case.
        """
        self.assertCountEqual(
            Number.objects.filter(pk__in=Number.objects.none().values("pk")), []
        )
        self.assertCountEqual(
            Number.objects.filter(pk__in=Number.objects.none().values_list("pk")), []
        )

    def test_ticket_19151(self):
        # #19151 -- Calling .values() or .values_list() on an empty QuerySet
        # should return an empty QuerySet and not cause an error.
        q = Author.objects.none()
        self.assertCountEqual(q.values(), [])
        self.assertCountEqual(q.values_list(), [])


class ValuesQuerysetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Number.objects.create(num=72)

    def test_flat_values_list(self):
        """

        Tests the retrieval of flat values from a values_list query.

        This test case ensures that flat values can be correctly extracted from a 
        values_list query. It checks if the result of the query matches the expected 
        sequence of values.

        """
        qs = Number.objects.values_list("num")
        qs = qs.values_list("num", flat=True)
        self.assertSequenceEqual(qs, [72])

    def test_extra_values(self):
        # testing for ticket 14930 issues
        """
        Tests adding extra values to a database query.

        This test case checks the functionality of adding custom calculated fields
        to a Django query. It uses the extra() method to add two new fields, 'value_plus_x' and 'value_minus_x',
        which are calculated based on the 'num' field of the Number model. The test then orders the results
        by the 'value_minus_x' field and verifies that the query returns the expected value for 'num'. 

        The purpose of this test is to ensure that the extra() method can be used to perform complex calculations
        and that the results are correct and consistent with the expected output.

        """
        qs = Number.objects.extra(
            select={"value_plus_x": "num+%s", "value_minus_x": "num-%s"},
            select_params=(1, 2),
        )
        qs = qs.order_by("value_minus_x")
        qs = qs.values("num")
        self.assertSequenceEqual(qs, [{"num": 72}])

    def test_extra_values_order_twice(self):
        # testing for ticket 14930 issues
        """

        Tests the ordering of extra selected values in a query.

        Verifies that when using :meth:`extra` to add custom database columns and 
        :meth:`order_by` to sort the results, the ordering is applied correctly. 
        The query sorts the results by two custom columns ('value_minus_one' and 'value_plus_one') 
        and checks that the resulting values match the expected sequence.

        """
        qs = Number.objects.extra(
            select={"value_plus_one": "num+1", "value_minus_one": "num-1"}
        )
        qs = qs.order_by("value_minus_one").order_by("value_plus_one")
        qs = qs.values("num")
        self.assertSequenceEqual(qs, [{"num": 72}])

    def test_extra_values_order_multiple(self):
        # Postgres doesn't allow constants in order by, so check for that.
        qs = Number.objects.extra(
            select={
                "value_plus_one": "num+1",
                "value_minus_one": "num-1",
                "constant_value": "1",
            }
        )
        qs = qs.order_by("value_plus_one", "value_minus_one", "constant_value")
        qs = qs.values("num")
        self.assertSequenceEqual(qs, [{"num": 72}])

    def test_extra_values_order_in_extra(self):
        # testing for ticket 14930 issues
        """

        Tests that the order of extra values in a Django ORM query is maintained when specifying an order by clause.

        The test case verifies that when adding extra fields to a query using the `extra` method and specifying an `order_by` clause,
        the resulting query produces the expected ordering of results based on the specified extra field.

        This ensures that the ordering of query results is correctly applied when using the `extra` method to add custom fields to a query.

        """
        qs = Number.objects.extra(
            select={"value_plus_one": "num+1", "value_minus_one": "num-1"},
            order_by=["value_minus_one"],
        )
        qs = qs.values("num")

    def test_extra_select_params_values_order_in_extra(self):
        # testing for 23259 issue
        qs = Number.objects.extra(
            select={"value_plus_x": "num+%s"},
            select_params=[1],
            order_by=["value_plus_x"],
        )
        qs = qs.filter(num=72)
        qs = qs.values("num")
        self.assertSequenceEqual(qs, [{"num": 72}])

    def test_extra_multiple_select_params_values_order_by(self):
        # testing for 23259 issue
        """
        Tests the ordering of query results when using extra select parameters with multiple values.

        This test case verifies that the values are correctly applied to the select parameters, 
        and the results are ordered as expected. It also checks that the filtering and 
        retrieval of specific values work as intended.

        The test checks for the correct ordering of the query results when using the 
        'extra' method with multiple select parameters, and ensures that the filter and 
        values methods produce the expected output.

        It checks that when applying an extra select with multiple values and ordering 
        by one of the calculated fields, the filtered results are correct and empty in 
        this specific test case, as no result should match the given filter criteria.
        """
        qs = Number.objects.extra(
            select={"value_plus_x": "num+%s", "value_minus_x": "num-%s"},
            select_params=(72, 72),
        )
        qs = qs.order_by("value_minus_x")
        qs = qs.filter(num=1)
        qs = qs.values("num")
        self.assertSequenceEqual(qs, [])

    def test_extra_values_list(self):
        # testing for ticket 14930 issues
        """

        Test that the extra values list query is correctly ordered and returns the expected values.

        This test case adds a custom select clause to a query, orders the results by the calculated value,
        and then checks that the returned values match the expected sequence.

        The test verifies that the database query is correctly constructed and executed, 
        ensuring that the returned data is accurate and in the correct order.

        """
        qs = Number.objects.extra(select={"value_plus_one": "num+1"})
        qs = qs.order_by("value_plus_one")
        qs = qs.values_list("num")
        self.assertSequenceEqual(qs, [(72,)])

    def test_flat_extra_values_list(self):
        # testing for ticket 14930 issues
        qs = Number.objects.extra(select={"value_plus_one": "num+1"})
        qs = qs.order_by("value_plus_one")
        qs = qs.values_list("num", flat=True)
        self.assertSequenceEqual(qs, [72])

    def test_field_error_values_list(self):
        # see #23443
        msg = (
            "Cannot resolve keyword %r into field. Join on 'name' not permitted."
            % "foo"
        )
        with self.assertRaisesMessage(FieldError, msg):
            Tag.objects.values_list("name__foo")

    def test_named_values_list_flat(self):
        msg = "'flat' and 'named' can't be used together."
        with self.assertRaisesMessage(TypeError, msg):
            Number.objects.values_list("num", flat=True, named=True)

    def test_named_values_list_bad_field_name(self):
        """
        Tests that :func:`values_list` with named=True raises an error when given an invalid field name.

        The function attempts to create a named values list with a field name that is not a valid identifier,
        and checks that a ValueError is raised with the expected error message.

        This test case ensures that the database query correctly handles field names and raises an error
        when an invalid field name is provided, preventing potential data corruption or unexpected behavior.
        """
        msg = "Type names and field names must be valid identifiers: '1'"
        with self.assertRaisesMessage(ValueError, msg):
            Number.objects.extra(select={"1": "num+1"}).values_list(
                "1", named=True
            ).first()

    def test_named_values_list_with_fields(self):
        qs = Number.objects.extra(select={"num2": "num+1"}).annotate(Count("id"))
        values = qs.values_list("num", "num2", named=True).first()
        self.assertEqual(type(values).__name__, "Row")
        self.assertEqual(values._fields, ("num", "num2"))
        self.assertEqual(values.num, 72)
        self.assertEqual(values.num2, 73)

    def test_named_values_list_without_fields(self):
        """
        Tests retrieving named values from a queryset with extra select and annotate clauses.

        This test case verifies that the values_list method with the named=True argument returns
        a Row object containing the expected field names and values. It checks the field names,
        their data types, and the actual values for specific fields. The test ensures that the 
        extra select and annotate clauses are correctly incorporated into the resulting Row object.

        The test covers the following aspects:
            * Type of the returned object
            * Field names in the returned Row object
            * Values of specific fields in the returned Row object
        """
        qs = Number.objects.extra(select={"num2": "num+1"}).annotate(Count("id"))
        values = qs.values_list(named=True).first()
        self.assertEqual(type(values).__name__, "Row")
        self.assertEqual(
            values._fields,
            ("num2", "id", "num", "other_num", "another_num", "id__count"),
        )
        self.assertEqual(values.num, 72)
        self.assertEqual(values.num2, 73)
        self.assertEqual(values.id__count, 1)

    def test_named_values_list_expression_with_default_alias(self):
        expr = Count("id")
        values = (
            Number.objects.annotate(id__count1=expr)
            .values_list(expr, "id__count1", named=True)
            .first()
        )
        self.assertEqual(values._fields, ("id__count2", "id__count1"))

    def test_named_values_list_expression(self):
        """
        Tests the generation of a named values list from an annotated queryset using an expression.

        This test case verifies the correctness of the annotated queryset by checking 
        if the resulting values list has the expected field names.

        The test annotates a queryset with a custom expression, retrieves the values list 
        with the specified fields, and asserts that the field names in the resulting 
        values list match the expected names.

        The goal of this test is to ensure that the named values list functionality works 
        correctly when using expressions in the annotation and retrieval of values.
        """
        expr = F("num") + 1
        qs = Number.objects.annotate(combinedexpression1=expr).values_list(
            expr, "combinedexpression1", named=True
        )
        values = qs.first()
        self.assertEqual(values._fields, ("combinedexpression2", "combinedexpression1"))

    def test_named_values_pickle(self):
        value = Number.objects.values_list("num", "other_num", named=True).get()
        self.assertEqual(value, (72, None))
        self.assertEqual(pickle.loads(pickle.dumps(value)), value)


class QuerySetSupportsPythonIdioms(TestCase):
    @classmethod
    def setUpTestData(cls):
        """

        Setup test data for the class.

        This class method creates a set of test articles with predefined attributes.
        The test data consists of seven articles, each with a unique name and a fixed creation date.
        The test data is stored in the class attribute 'articles' and can be accessed by other test methods.

        """
        some_date = datetime.datetime(2014, 5, 16, 12, 1)
        cls.articles = [
            Article.objects.create(name=f"Article {i}", created=some_date)
            for i in range(1, 8)
        ]

    def get_ordered_articles(self):
        return Article.objects.order_by("name")

    def test_can_get_items_using_index_and_slice_notation(self):
        """
        Tests whether articles can be retrieved using index and slice notation.

        This test case verifies that the get_ordered_articles method supports accessing
        individual articles by their index and retrieving a subset of articles using
        slice notation, ensuring the correct ordering of the articles is maintained.

        """
        self.assertEqual(self.get_ordered_articles()[0].name, "Article 1")
        self.assertSequenceEqual(
            self.get_ordered_articles()[1:3],
            [self.articles[1], self.articles[2]],
        )

    def test_slicing_with_steps_can_be_used(self):
        self.assertSequenceEqual(
            self.get_ordered_articles()[::2],
            [
                self.articles[0],
                self.articles[2],
                self.articles[4],
                self.articles[6],
            ],
        )

    def test_slicing_without_step_is_lazy(self):
        """
        Tests that slicing a query set without specifying a step does not execute the query immediately, verifying lazy loading behavior.

        This test case checks that the `get_ordered_articles` method's result is not evaluated until it is actually needed, minimizing database queries when using slicing operations without a step.

        """
        with self.assertNumQueries(0):
            self.get_ordered_articles()[0:5]

    def test_slicing_with_tests_is_not_lazy(self):
        """
        Tests that slicing on a query set is not lazy by verifying it executes a single database query.

        The test checks that retrieving a subset of ordered articles using slicing does not lead to additional queries, ensuring efficient database interaction.

        :returns: None
        :raises: AssertionError if more than one query is executed
        """
        with self.assertNumQueries(1):
            self.get_ordered_articles()[0:5:3]

    def test_slicing_can_slice_again_after_slicing(self):
        """
        Tests that slicing can be applied in a chained manner to the result of `get_ordered_articles`.

        Verifies that subsequent slicing operations correctly subset the intermediate results,
        enabling flexible and nested slicing of the returned article sequence.

        Checks various slice combinations, including slicing from the start, end, and middle of the sequence,
        as well as slicing with empty results and single-element results.

        Ensures that the resulting sliced sequences match the expected article ordering and content.
        """
        self.assertSequenceEqual(
            self.get_ordered_articles()[0:5][0:2],
            [self.articles[0], self.articles[1]],
        )
        self.assertSequenceEqual(
            self.get_ordered_articles()[0:5][4:], [self.articles[4]]
        )
        self.assertSequenceEqual(self.get_ordered_articles()[0:5][5:], [])

        # Some more tests!
        self.assertSequenceEqual(
            self.get_ordered_articles()[2:][0:2],
            [self.articles[2], self.articles[3]],
        )
        self.assertSequenceEqual(
            self.get_ordered_articles()[2:][:2],
            [self.articles[2], self.articles[3]],
        )
        self.assertSequenceEqual(
            self.get_ordered_articles()[2:][2:3], [self.articles[4]]
        )

        # Using an offset without a limit is also possible.
        self.assertSequenceEqual(
            self.get_ordered_articles()[5:],
            [self.articles[5], self.articles[6]],
        )

    def test_slicing_cannot_filter_queryset_once_sliced(self):
        msg = "Cannot filter a query once a slice has been taken."
        with self.assertRaisesMessage(TypeError, msg):
            Article.objects.all()[0:5].filter(id=1)

    def test_slicing_cannot_reorder_queryset_once_sliced(self):
        """

        Tests that attempting to reorder a query set after it has been sliced raises a TypeError.

        This test case verifies that once a slice has been applied to a query set, it is no longer possible to reorder the results.
        The expected error message is 'Cannot reorder a query once a slice has been taken.'.

        :param none:
        :raises TypeError: If attempting to reorder a sliced query set.
        :return: None

        """
        msg = "Cannot reorder a query once a slice has been taken."
        with self.assertRaisesMessage(TypeError, msg):
            Article.objects.all()[0:5].order_by("id")

    def test_slicing_cannot_combine_queries_once_sliced(self):
        """
        Tests that attempting to combine queries using the bitwise AND operator (&) on sliced QuerySets results in a TypeError.

        The function verifies that once a slice has been taken from a QuerySet, it is no longer possible to combine it with another QuerySet using the bitwise AND operator. This ensures that Django's ORM behaves correctly and raises an informative error message when attempting such an operation. The expected error message is 'Cannot combine queries once a slice has been taken.'
        """
        msg = "Cannot combine queries once a slice has been taken."
        with self.assertRaisesMessage(TypeError, msg):
            Article.objects.all()[0:1] & Article.objects.all()[4:5]

    def test_slicing_negative_indexing_not_supported_for_single_element(self):
        """hint: inverting your ordering might do what you need"""
        msg = "Negative indexing is not supported."
        with self.assertRaisesMessage(ValueError, msg):
            Article.objects.all()[-1]

    def test_slicing_negative_indexing_not_supported_for_range(self):
        """hint: inverting your ordering might do what you need"""
        msg = "Negative indexing is not supported."
        with self.assertRaisesMessage(ValueError, msg):
            Article.objects.all()[0:-5]
        with self.assertRaisesMessage(ValueError, msg):
            Article.objects.all()[-1:]

    def test_invalid_index(self):
        """
        Test that attempting to access a QuerySet with a string index raises a TypeError.

        The test verifies that trying to use a string as an index to access a QuerySet results in an error, as QuerySet indices must be either integers or slices. 

        This test ensures that the proper error message is raised when a string index is used, providing a clear indication of the supported index types.
        """
        msg = "QuerySet indices must be integers or slices, not str."
        with self.assertRaisesMessage(TypeError, msg):
            Article.objects.all()["foo"]

    def test_can_get_number_of_items_in_queryset_using_standard_len(self):
        self.assertEqual(len(Article.objects.filter(name__exact="Article 1")), 1)

    def test_can_combine_queries_using_and_and_or_operators(self):
        s1 = Article.objects.filter(name__exact="Article 1")
        s2 = Article.objects.filter(name__exact="Article 2")
        self.assertSequenceEqual(
            (s1 | s2).order_by("name"),
            [self.articles[0], self.articles[1]],
        )
        self.assertSequenceEqual(s1 & s2, [])


class WeirdQuerysetSlicingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for the application, creating initial records in the database.

         This method creates a set of predefined Number, Article, Food, and Eaten objects, 
         which can be used as a starting point for testing purposes.

         It includes four articles and a set of numbers, as well as a food item and an instance 
         of it being eaten, providing a basic dataset to work with in a test environment.
        """
        Number.objects.create(num=1)
        Number.objects.create(num=2)

        Article.objects.create(name="one", created=datetime.datetime.now())
        Article.objects.create(name="two", created=datetime.datetime.now())
        Article.objects.create(name="three", created=datetime.datetime.now())
        Article.objects.create(name="four", created=datetime.datetime.now())

        food = Food.objects.create(name="spam")
        Eaten.objects.create(meal="spam with eggs", food=food)

    def test_tickets_7698_10202(self):
        # People like to slice with '0' as the high-water mark.
        self.assertSequenceEqual(Article.objects.all()[0:0], [])
        self.assertSequenceEqual(Article.objects.all()[0:0][:10], [])
        self.assertEqual(Article.objects.all()[:0].count(), 0)
        msg = "Cannot change a query once a slice has been taken."
        with self.assertRaisesMessage(TypeError, msg):
            Article.objects.all()[:0].latest("created")

    def test_empty_resultset_sql(self):
        # ticket #12192
        self.assertNumQueries(0, lambda: list(Number.objects.all()[1:1]))

    def test_empty_sliced_subquery(self):
        self.assertEqual(
            Eaten.objects.filter(food__in=Food.objects.all()[0:0]).count(), 0
        )

    def test_empty_sliced_subquery_exclude(self):
        self.assertEqual(
            Eaten.objects.exclude(food__in=Food.objects.all()[0:0]).count(), 1
        )

    def test_zero_length_values_slicing(self):
        n = 42
        with self.assertNumQueries(0):
            self.assertQuerySetEqual(Article.objects.values()[n:n], [])
            self.assertQuerySetEqual(Article.objects.values_list()[n:n], [])


class EscapingTests(TestCase):
    def test_ticket_7302(self):
        # Reserved names are appropriately escaped
        """
        Tests that ReservedName objects are correctly ordered by their 'order' attribute and also by 'order' and 'name' when using the 'extra' method to include additional selected fields. Verifies that the correct sequence of ReservedName objects is returned, taking into account the specified order.
        """
        r_a = ReservedName.objects.create(name="a", order=42)
        r_b = ReservedName.objects.create(name="b", order=37)
        self.assertSequenceEqual(
            ReservedName.objects.order_by("order"),
            [r_b, r_a],
        )
        self.assertSequenceEqual(
            ReservedName.objects.extra(
                select={"stuff": "name"}, order_by=("order", "stuff")
            ),
            [r_b, r_a],
        )


class ToFieldTests(TestCase):
    def test_in_query(self):
        """

        Tests the filtering of eaten food instances by multiple food objects.

        Verifies that the :meth:`Eaten.objects.filter` method correctly returns 
        all eaten instances that correspond to the specified food objects.

        In this test case, it checks that filtering by 'apple' and 'pear' food 
        objects returns the corresponding 'lunch' and 'dinner' eaten instances.

        """
        apple = Food.objects.create(name="apple")
        pear = Food.objects.create(name="pear")
        lunch = Eaten.objects.create(food=apple, meal="lunch")
        dinner = Eaten.objects.create(food=pear, meal="dinner")

        self.assertEqual(
            set(Eaten.objects.filter(food__in=[apple, pear])),
            {lunch, dinner},
        )

    def test_in_subquery(self):
        apple = Food.objects.create(name="apple")
        lunch = Eaten.objects.create(food=apple, meal="lunch")
        self.assertEqual(
            set(Eaten.objects.filter(food__in=Food.objects.filter(name="apple"))),
            {lunch},
        )
        self.assertEqual(
            set(
                Eaten.objects.filter(
                    food__in=Food.objects.filter(name="apple").values("eaten__meal")
                )
            ),
            set(),
        )
        self.assertEqual(
            set(Food.objects.filter(eaten__in=Eaten.objects.filter(meal="lunch"))),
            {apple},
        )

    def test_nested_in_subquery(self):
        """
        Tests filtering of report comments that are nested within subqueries.

        This function creates a report comment and verifies that it can be successfully retrieved
        using a nested query that filters report comments based on the creator of their reports.
        The filter checks if the report's creator is in the set of authors associated with an extra info object.
        The test asserts that the filtered comments match the expected result, confirming the correctness of the nested query.

        Note:
            The test case covers the following models: ExtraInfo, Author, Report, ReportComment.

        """
        extra = ExtraInfo.objects.create()
        author = Author.objects.create(num=42, extra=extra)
        report = Report.objects.create(creator=author)
        comment = ReportComment.objects.create(report=report)
        comments = ReportComment.objects.filter(
            report__in=Report.objects.filter(
                creator__in=extra.author_set.all(),
            ),
        )
        self.assertSequenceEqual(comments, [comment])

    def test_reverse_in(self):
        apple = Food.objects.create(name="apple")
        pear = Food.objects.create(name="pear")
        lunch_apple = Eaten.objects.create(food=apple, meal="lunch")
        lunch_pear = Eaten.objects.create(food=pear, meal="dinner")

        self.assertEqual(
            set(Food.objects.filter(eaten__in=[lunch_apple, lunch_pear])), {apple, pear}
        )

    def test_single_object(self):
        """
        Tests that a single food object can be associated with multiple eaten instances for different meals.

        Verifies that filtering eaten instances by a specific food object returns the correct set of eaten instances, 
        regardless of the meal type. This ensures data consistency and correct database query results.
        """
        apple = Food.objects.create(name="apple")
        lunch = Eaten.objects.create(food=apple, meal="lunch")
        dinner = Eaten.objects.create(food=apple, meal="dinner")

        self.assertEqual(set(Eaten.objects.filter(food=apple)), {lunch, dinner})

    def test_single_object_reverse(self):
        """

        Tests that a single food object is correctly associated with an eaten object in reverse.

        This test case verifies that when a food item is eaten during a specific meal, 
        it can be retrieved from the Food model using the eaten object. The test creates 
        a food item and an eaten object, then checks that the food item can be filtered 
        from the Food model using the eaten object, ensuring the correct relationship is established.

        """
        apple = Food.objects.create(name="apple")
        lunch = Eaten.objects.create(food=apple, meal="lunch")

        self.assertEqual(set(Food.objects.filter(eaten=lunch)), {apple})

    def test_recursive_fk(self):
        """

        Tests the recursive foreign key relationship in the Node model.

        This test case verifies that a node can have a parent-child relationship with another node,
        and that the child node can be correctly retrieved based on its parent.

        """
        node1 = Node.objects.create(num=42)
        node2 = Node.objects.create(num=1, parent=node1)

        self.assertEqual(list(Node.objects.filter(parent=node1)), [node2])

    def test_recursive_fk_reverse(self):
        """
        Checks the reverse relationship of a foreign key in a recursive manner, ensuring that a node's parent can be correctly retrieved through the node. Tests the creation of a parent-child relationship between two nodes and verifies that querying for a node's parent returns the expected result.
        """
        node1 = Node.objects.create(num=42)
        node2 = Node.objects.create(num=1, parent=node1)

        self.assertEqual(list(Node.objects.filter(node=node2)), [node1])


class IsNullTests(TestCase):
    def test_primary_key(self):
        """

        Tests the primary key relationship between CustomPk and Related models.

        Verifies that the relationship is correctly established when a Related object 
        is created with a CustomPk instance, and that it is properly queried using 
        the isnull filter.

        Ensures that Related objects with a non-null primary key are correctly 
        identified, and those with a null primary key are filtered separately.

        """
        custom = CustomPk.objects.create(name="pk")
        null = Related.objects.create()
        notnull = Related.objects.create(custom=custom)
        self.assertSequenceEqual(
            Related.objects.filter(custom__isnull=False), [notnull]
        )
        self.assertSequenceEqual(Related.objects.filter(custom__isnull=True), [null])

    def test_to_field(self):
        apple = Food.objects.create(name="apple")
        e1 = Eaten.objects.create(food=apple, meal="lunch")
        e2 = Eaten.objects.create(meal="lunch")
        self.assertSequenceEqual(
            Eaten.objects.filter(food__isnull=False),
            [e1],
        )
        self.assertSequenceEqual(
            Eaten.objects.filter(food__isnull=True),
            [e2],
        )


class ConditionalTests(TestCase):
    """Tests whose execution depend on different environment conditions like
    Python version or DB backend features"""

    @classmethod
    def setUpTestData(cls):
        generic = NamedCategory.objects.create(name="Generic")
        t1 = Tag.objects.create(name="t1", category=generic)
        Tag.objects.create(name="t2", parent=t1, category=generic)
        t3 = Tag.objects.create(name="t3", parent=t1)
        Tag.objects.create(name="t4", parent=t3)
        Tag.objects.create(name="t5", parent=t3)

    def test_infinite_loop(self):
        # If you're not careful, it's possible to introduce infinite loops via
        # default ordering on foreign keys in a cycle. We detect that.
        """
        Tests whether the model's ordering causes an infinite loop due to recursive relations.
        Verifies that a FieldError is raised when attempting to retrieve objects from LoopX and LoopZ models.
        Additionally, checks that the Tag model can be ordered by its 'parent' field without issues.
        Lastly, confirms that an empty sequence is returned when ordering LoopX objects through a deeply nested relation, which should prevent infinite recursion.
        """
        with self.assertRaisesMessage(FieldError, "Infinite loop caused by ordering."):
            list(LoopX.objects.all())  # Force queryset evaluation with list()
        with self.assertRaisesMessage(FieldError, "Infinite loop caused by ordering."):
            list(LoopZ.objects.all())  # Force queryset evaluation with list()

        # Note that this doesn't cause an infinite loop, since the default
        # ordering on the Tag model is empty (and thus defaults to using "id"
        # for the related field).
        self.assertEqual(len(Tag.objects.order_by("parent")), 5)

        # ... but you can still order in a non-recursive fashion among linked
        # fields (the previous test failed because the default ordering was
        # recursive).
        self.assertSequenceEqual(LoopX.objects.order_by("y__x__y__x__id"), [])

    # When grouping without specifying ordering, we add an explicit "ORDER BY NULL"
    # portion in MySQL to prevent unnecessary sorting.
    @skipUnlessDBFeature("requires_explicit_null_ordering_when_grouping")
    def test_null_ordering_added(self):
        """
        Tests that ordering by NULL is explicitly added when grouping in a query.

        Verifies that an ORDER BY NULL clause is correctly appended to a SQL query when
        grouping by a field, ensuring that the results are properly ordered.

        The test checks for the presence of the ORDER BY NULL clause in the generated SQL
        and ensures that it is correctly positioned in the query, with no duplicate ORDER BY
        clauses present.
        """
        query = Tag.objects.values_list("parent_id", flat=True).order_by().query
        query.group_by = ["parent_id"]
        sql = query.get_compiler(DEFAULT_DB_ALIAS).as_sql()[0]
        fragment = "ORDER BY "
        pos = sql.find(fragment)
        self.assertEqual(sql.find(fragment, pos + 1), -1)
        self.assertEqual(sql.find("NULL", pos + len(fragment)), pos + len(fragment))

    def test_in_list_limit(self):
        # The "in" lookup works with lists of 1000 items or more.
        # The numbers amount is picked to force three different IN batches
        # for Oracle, yet to be less than 2100 parameter limit for MSSQL.
        """
        Tests the limit of using the 'in' lookup in database queries.

        This function checks the performance of the 'in' lookup by creating a list of numbers and then
        querying the database to retrieve objects with numbers within a certain range. It verifies that
        the correct number of objects is returned for different ranges, ensuring that the 'in' lookup
        works as expected within the database's limits.

        The test covers scenarios where the number of query parameters is within and exceeds the
        database's maximum allowed query parameters, if applicable. This helps to ensure that the
        database's query parameter limit does not interfere with the 'in' lookup functionality.

        The test cases cover various edge cases, including small and large ranges, to provide a
        comprehensive understanding of the 'in' lookup functionality under different conditions.

        Returns:
            None

        Raises:
            AssertionError: If the count of retrieved objects does not match the expected count.

        """
        numbers = list(range(2050))
        max_query_params = connection.features.max_query_params
        if max_query_params is None or max_query_params >= len(numbers):
            Number.objects.bulk_create(Number(num=num) for num in numbers)
            for number in [1000, 1001, 2000, len(numbers)]:
                with self.subTest(number=number):
                    self.assertEqual(
                        Number.objects.filter(num__in=numbers[:number]).count(), number
                    )


class UnionTests(unittest.TestCase):
    """
    Tests for the union of two querysets. Bug #12252.
    """

    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for the application by creating instances of ObjectA, ObjectB, and ObjectC.

        The function populates the database with a predefined set of objects, including three ObjectA instances, 
        three ObjectB instances associated with the ObjectA instances, and two ObjectC instances linked to 
        the ObjectA and ObjectB instances. This data is used to support testing of the application's 
        functionality.

        The test data includes the following:

        - Three ObjectA instances with names 'one', 'two', and 'three'
        - Three ObjectB instances with names 'un', 'deux', and 'trois', each associated with an ObjectA instance
        - Two ObjectC instances with names 'ein' and 'zwei', each linked to an ObjectA and ObjectB instance
        """
        objectas = []
        objectbs = []
        objectcs = []
        a_info = ["one", "two", "three"]
        for name in a_info:
            o = ObjectA(name=name)
            o.save()
            objectas.append(o)
        b_info = [
            ("un", 1, objectas[0]),
            ("deux", 2, objectas[0]),
            ("trois", 3, objectas[2]),
        ]
        for name, number, objecta in b_info:
            o = ObjectB(name=name, num=number, objecta=objecta)
            o.save()
            objectbs.append(o)
        c_info = [("ein", objectas[2], objectbs[2]), ("zwei", objectas[1], objectbs[1])]
        for name, objecta, objectb in c_info:
            o = ObjectC(name=name, objecta=objecta, objectb=objectb)
            o.save()
            objectcs.append(o)

    def check_union(self, model, Q1, Q2):
        """

        Checks the union operation between two Django querysets (Q1 and Q2) on a given model.

        This function verifies that the union of Q1 and Q2 is commutative, i.e., 
        Q1 union Q2 equals Q2 union Q1, and both equal the union of Q1 and Q2 combined 
        into a single query. The results are compared as sets, which means the order 
        of the objects does not affect the comparison.

        The function uses assertions to validate these equalities, ensuring that the 
        union operation behaves as expected when chaining queries or combining them 
        into a single query.

        """
        filter = model.objects.filter
        self.assertEqual(set(filter(Q1) | filter(Q2)), set(filter(Q1 | Q2)))
        self.assertEqual(set(filter(Q2) | filter(Q1)), set(filter(Q1 | Q2)))

    def test_A_AB(self):
        """

        Tests the union operation of query objects Q1 and Q2 on ObjectA.

        The test cases involve two query objects: one that filters by the 'name' attribute and 
        another that filters by the 'name' attribute of a related object 'objectb'. 
        This test ensures that the union of these queries correctly combines their results.

        """
        Q1 = Q(name="two")
        Q2 = Q(objectb__name="deux")
        self.check_union(ObjectA, Q1, Q2)

    def test_A_AB2(self):
        Q1 = Q(name="two")
        Q2 = Q(objectb__name="deux", objectb__num=2)
        self.check_union(ObjectA, Q1, Q2)

    def test_AB_ACB(self):
        """

        Tests the union of two queries on model ObjectA, one filtering on attribute 'objectb__name' and the other on nested attribute 'objectc__objectb__name', both matching the value 'deux'.

        This test case verifies that the union of these two queries returns the expected results, ensuring correct handling of filters across related models.

        """
        Q1 = Q(objectb__name="deux")
        Q2 = Q(objectc__objectb__name="deux")
        self.check_union(ObjectA, Q1, Q2)

    def test_BAB_BAC(self):
        """

        Tests the union of queries on object B.

        This test case checks the union of two queries, Q1 and Q2, 
        on the ObjectB class. Q1 filters object B instances based 
        on the 'name' attribute of the related 'objectb' object, 
        while Q2 filters based on the 'name' attribute of the 
        related 'objectc' object. The test verifies that the 
        resulting union of these queries is correct.

        :param: None
        :returns: None
        :raises: AssertionError if the union of queries is incorrect

        """
        Q1 = Q(objecta__objectb__name="deux")
        Q2 = Q(objecta__objectc__name="ein")
        self.check_union(ObjectB, Q1, Q2)

    def test_BAB_BACB(self):
        """

        Tests the union of two complex queries on ObjectB instances.

        This test case verifies that the union of queries with nested relationships 
        between objects A, B, and C is correctly handled. It checks that the 
        resulting query returns the expected ObjectB instances when the name of 
        the related ObjectB instance is 'deux' or the name of the related ObjectB 
        instance through ObjectC is 'trois'.

        """
        Q1 = Q(objecta__objectb__name="deux")
        Q2 = Q(objecta__objectc__objectb__name="trois")
        self.check_union(ObjectB, Q1, Q2)

    def test_BA_BCA__BAB_BAC_BCA(self):
        Q1 = Q(objecta__name="one", objectc__objecta__name="two")
        Q2 = Q(
            objecta__objectc__name="ein",
            objectc__objecta__name="three",
            objecta__objectb__name="trois",
        )
        self.check_union(ObjectB, Q1, Q2)


class DefaultValuesInsertTest(TestCase):
    def test_no_extra_params(self):
        """
        Can create an instance of a model with only the PK field (#17056)."
        """
        DumbCategory.objects.create()


class ExcludeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for use in unit tests.

        This method creates a set of predefined food, meal, job, and responsibility objects.
        It includes two food items (apples and oranges), two job roles (Manager and Programmer),
        and two associated responsibilities (Playing golf and Programming), as well as a single
        meal instance where apples were eaten for dinner. These objects are made available
        as class attributes for use in subsequent tests.

        The test data provides a basic structure for testing relationships between foods, meals,
        jobs, and responsibilities, allowing for more comprehensive testing of application logic.

        """
        f1 = Food.objects.create(name="apples")
        cls.f2 = Food.objects.create(name="oranges")
        Eaten.objects.create(food=f1, meal="dinner")
        cls.j1 = Job.objects.create(name="Manager")
        cls.r1 = Responsibility.objects.create(description="Playing golf")
        cls.j2 = Job.objects.create(name="Programmer")
        cls.r2 = Responsibility.objects.create(description="Programming")
        JobResponsibilities.objects.create(job=cls.j1, responsibility=cls.r1)
        JobResponsibilities.objects.create(job=cls.j2, responsibility=cls.r2)

    def test_to_field(self):
        self.assertSequenceEqual(
            Food.objects.exclude(eaten__meal="dinner"),
            [self.f2],
        )
        self.assertSequenceEqual(
            Job.objects.exclude(responsibilities__description="Playing golf"),
            [self.j2],
        )
        self.assertSequenceEqual(
            Responsibility.objects.exclude(jobs__name="Manager"),
            [self.r2],
        )

    def test_exclude_m2m_through(self):
        alex = Person.objects.get_or_create(name="Alex")[0]
        jane = Person.objects.get_or_create(name="Jane")[0]

        oracle = Company.objects.get_or_create(name="Oracle")[0]
        google = Company.objects.get_or_create(name="Google")[0]
        microsoft = Company.objects.get_or_create(name="Microsoft")[0]
        intel = Company.objects.get_or_create(name="Intel")[0]

        def employ(employer, employee, title):
            Employment.objects.get_or_create(
                employee=employee, employer=employer, title=title
            )

        employ(oracle, alex, "Engineer")
        employ(oracle, alex, "Developer")
        employ(google, alex, "Engineer")
        employ(google, alex, "Manager")
        employ(microsoft, alex, "Manager")
        employ(intel, alex, "Manager")

        employ(microsoft, jane, "Developer")
        employ(intel, jane, "Manager")

        alex_tech_employers = (
            alex.employers.filter(employment__title__in=("Engineer", "Developer"))
            .distinct()
            .order_by("name")
        )
        self.assertSequenceEqual(alex_tech_employers, [google, oracle])

        alex_nontech_employers = (
            alex.employers.exclude(employment__title__in=("Engineer", "Developer"))
            .distinct()
            .order_by("name")
        )
        with self.assertNumQueries(1) as ctx:
            self.assertSequenceEqual(alex_nontech_employers, [google, intel, microsoft])
        sql = ctx.captured_queries[0]["sql"]
        # Company's ID should appear in SELECT and INNER JOIN, not in EXISTS as
        # the outer query reference is not necessary when an alias is reused.
        company_id = "%s.%s" % (
            connection.ops.quote_name(Company._meta.db_table),
            connection.ops.quote_name(Company._meta.get_field("id").column),
        )
        self.assertEqual(sql.count(company_id), 2)

    def test_exclude_reverse_fk_field_ref(self):
        """
        Tests excluding annotations based on the reverse foreign key relationship between Tag and Note models.

        Specifically, this test verifies that an annotation can be excluded from a queryset 
        based on the existence of a note associated with its tag, where the note's text 
        matches the annotation's name. The test checks that annotations without matching 
        notes are correctly retrieved after applying the exclude filter.

        If the test passes, it confirms that the exclude filter is correctly applied to 
        the reverse foreign key relationship, ensuring that only annotations without 
        matching notes are returned in the queryset.
        """
        tag = Tag.objects.create()
        Note.objects.create(tag=tag, note="note")
        annotation = Annotation.objects.create(name="annotation", tag=tag)
        self.assertEqual(
            Annotation.objects.exclude(tag__note__note=F("name")).get(), annotation
        )

    def test_exclude_with_circular_fk_relation(self):
        self.assertEqual(
            ObjectB.objects.exclude(objecta__objectb__name=F("name")).count(), 0
        )

    def test_subquery_exclude_outerref(self):
        """

        Tests the functionality of excluding outer references in subqueries.

        This test case ensures that the subquery correctly filters out job responsibilities 
        where the responsibility is associated with the outer job. It verifies that 
        at least one job responsibility exists initially, and then checks that no job 
        responsibilities exist after deleting a responsibility, thus validating the 
        subquery's exclude logic.

        """
        qs = JobResponsibilities.objects.filter(
            Exists(Responsibility.objects.exclude(jobs=OuterRef("job"))),
        )
        self.assertTrue(qs.exists())
        self.r1.delete()
        self.assertFalse(qs.exists())

    def test_exclude_nullable_fields(self):
        number = Number.objects.create(num=1, other_num=1)
        Number.objects.create(num=2, other_num=2, another_num=2)
        self.assertSequenceEqual(
            Number.objects.exclude(other_num=F("another_num")),
            [number],
        )
        self.assertSequenceEqual(
            Number.objects.exclude(num=F("another_num")),
            [number],
        )

    def test_exclude_multivalued_exists(self):
        """

        Tests the exclude method on a model's multivalued attribute.

        This test case verifies that the exclude method correctly filters out objects 
        based on a specified condition. It checks that the resulting query uses an 
        'exists' clause in the SQL query. The test ensures that only objects that do 
        not match the condition are returned.

        In this specific test, it checks that jobs with responsibilities that do not 
        have a description of 'Programming' are correctly excluded.

        """
        with CaptureQueriesContext(connection) as captured_queries:
            self.assertSequenceEqual(
                Job.objects.exclude(responsibilities__description="Programming"),
                [self.j1],
            )
        self.assertIn("exists", captured_queries[0]["sql"].lower())

    def test_exclude_subquery(self):
        subquery = JobResponsibilities.objects.filter(
            responsibility__description="bar",
        ) | JobResponsibilities.objects.exclude(
            job__responsibilities__description="foo",
        )
        self.assertCountEqual(
            Job.objects.annotate(
                responsibility=subquery.filter(job=OuterRef("name")).values("id")[:1]
            ),
            [self.j1, self.j2],
        )

    def test_exclude_unsaved_object(self):
        """
        Tests that filtering QuerySets with unsaved model instances raises a ValueError.

        This test ensures that attempting to exclude unsaved objects from a QuerySet
        results in an error, as Django requires model instances to be saved before they
        can be used in related filters.

        The test covers several scenarios, including filtering by a single unsaved
        instance, as well as filtering by a list of instances that includes both saved
        and unsaved objects. In each case, a ValueError is expected to be raised with
        a message indicating that model instances passed to related filters must be saved.
        """
        company = Company.objects.create(name="Django")
        msg = "Model instances passed to related filters must be saved."
        with self.assertRaisesMessage(ValueError, msg):
            Employment.objects.exclude(employer=Company(name="unsaved"))
        with self.assertRaisesMessage(ValueError, msg):
            Employment.objects.exclude(employer__in=[company, Company(name="unsaved")])
        with self.assertRaisesMessage(ValueError, msg):
            StaffUser.objects.exclude(staff=Staff(name="unsaved"))


class ExcludeTest17600(TestCase):
    """
    Some regressiontests for ticket #17600. Some of these likely duplicate
    other existing tests.
    """

    @classmethod
    def setUpTestData(cls):
        # Create a few Orders.
        """

        Sets up test data for the class.

        This class method creates a set of test orders and order items with predefined
        statuses. It establishes a fixed set of orders (o1, o2, o3) and their associated
        order items (oi1-oi9), allowing for consistent testing across different test cases.

        The created orders and order items have the following characteristics:
        - o1 has three order items with status 1
        - o2 has three order items with statuses 1, 2, and 3
        - o3 has three order items with statuses 2, 3, and 4

        This setup provides a foundation for testing various scenarios involving orders and
        order items.

        """
        cls.o1 = Order.objects.create(pk=1)
        cls.o2 = Order.objects.create(pk=2)
        cls.o3 = Order.objects.create(pk=3)

        # Create some OrderItems for the first order with homogeneous
        # status_id values
        cls.oi1 = OrderItem.objects.create(order=cls.o1, status=1)
        cls.oi2 = OrderItem.objects.create(order=cls.o1, status=1)
        cls.oi3 = OrderItem.objects.create(order=cls.o1, status=1)

        # Create some OrderItems for the second order with heterogeneous
        # status_id values
        cls.oi4 = OrderItem.objects.create(order=cls.o2, status=1)
        cls.oi5 = OrderItem.objects.create(order=cls.o2, status=2)
        cls.oi6 = OrderItem.objects.create(order=cls.o2, status=3)

        # Create some OrderItems for the second order with heterogeneous
        # status_id values
        cls.oi7 = OrderItem.objects.create(order=cls.o3, status=2)
        cls.oi8 = OrderItem.objects.create(order=cls.o3, status=3)
        cls.oi9 = OrderItem.objects.create(order=cls.o3, status=4)

    def test_exclude_plain(self):
        """
        This should exclude Orders which have some items with status 1
        """
        self.assertSequenceEqual(
            Order.objects.exclude(items__status=1),
            [self.o3],
        )

    def test_exclude_plain_distinct(self):
        """
        This should exclude Orders which have some items with status 1
        """
        self.assertSequenceEqual(
            Order.objects.exclude(items__status=1).distinct(),
            [self.o3],
        )

    def test_exclude_with_q_object_distinct(self):
        """
        This should exclude Orders which have some items with status 1
        """
        self.assertSequenceEqual(
            Order.objects.exclude(Q(items__status=1)).distinct(),
            [self.o3],
        )

    def test_exclude_with_q_object_no_distinct(self):
        """
        This should exclude Orders which have some items with status 1
        """
        self.assertSequenceEqual(
            Order.objects.exclude(Q(items__status=1)),
            [self.o3],
        )

    def test_exclude_with_q_is_equal_to_plain_exclude(self):
        """
        Using exclude(condition) and exclude(Q(condition)) should
        yield the same QuerySet
        """
        self.assertEqual(
            list(Order.objects.exclude(items__status=1).distinct()),
            list(Order.objects.exclude(Q(items__status=1)).distinct()),
        )

    def test_exclude_with_q_is_equal_to_plain_exclude_variation(self):
        """
        Using exclude(condition) and exclude(Q(condition)) should
        yield the same QuerySet
        """
        self.assertEqual(
            list(Order.objects.exclude(items__status=1)),
            list(Order.objects.exclude(Q(items__status=1)).distinct()),
        )

    @unittest.expectedFailure
    def test_only_orders_with_all_items_having_status_1(self):
        """
        This should only return orders having ALL items set to status 1, or
        those items not having any orders at all. The correct way to write
        this query in SQL seems to be using two nested subqueries.
        """
        self.assertSequenceEqual(
            Order.objects.exclude(~Q(items__status=1)).distinct(),
            [self.o1],
        )


class Exclude15786(TestCase):
    """Regression test for #15786"""

    def test_ticket15786(self):
        """

        Tests the creation of a CategoryRelationship instance between two categories (c1 and c2)
        with each category having a corresponding OneToOneCategory instance, and verifies that
        the relationship can be correctly queried and retrieved by excluding instances where
        the related categories have matching OneToOneCategory instances.

        """
        c1 = SimpleCategory.objects.create(name="c1")
        c2 = SimpleCategory.objects.create(name="c2")
        OneToOneCategory.objects.create(category=c1)
        OneToOneCategory.objects.create(category=c2)
        rel = CategoryRelationship.objects.create(first=c1, second=c2)
        self.assertEqual(
            CategoryRelationship.objects.exclude(
                first__onetoonecategory=F("second__onetoonecategory")
            ).get(),
            rel,
        )


class NullInExcludeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        ..:class_method:: 
            Setup test data for the test class.

            This method creates initial test data in the database, specifically two instances of :class:`~NullableName`. 
            The first instance has a name set to 'i1', while the second instance has a null name. 
            This data is used as a foundation for testing and can be relied upon to exist at the start of each test.
        """
        NullableName.objects.create(name="i1")
        NullableName.objects.create()

    def test_null_in_exclude_qs(self):
        """

        Tests the functionality of excluding querysets with null values.

        This test case verifies that the `exclude` method behaves correctly when the 
        `name__in` lookup is used with an empty list or a list containing a single value. 
        It checks that null values are properly excluded or included in the result, 
        depending on the specified condition.

        Additionally, it tests that using an inner queryset with a `values_list` 
        call does not trigger a cache result and that the `exclude` method still 
        produces the expected output.

        """
        none_val = "" if connection.features.interprets_empty_strings_as_nulls else None
        self.assertQuerySetEqual(
            NullableName.objects.exclude(name__in=[]),
            ["i1", none_val],
            attrgetter("name"),
        )
        self.assertQuerySetEqual(
            NullableName.objects.exclude(name__in=["i1"]),
            [none_val],
            attrgetter("name"),
        )
        self.assertQuerySetEqual(
            NullableName.objects.exclude(name__in=["i3"]),
            ["i1", none_val],
            attrgetter("name"),
        )
        inner_qs = NullableName.objects.filter(name="i1").values_list("name")
        self.assertQuerySetEqual(
            NullableName.objects.exclude(name__in=inner_qs),
            [none_val],
            attrgetter("name"),
        )
        # The inner queryset wasn't executed - it should be turned
        # into subquery above
        self.assertIs(inner_qs._result_cache, None)

    @unittest.expectedFailure
    def test_col_not_in_list_containing_null(self):
        """
        The following case is not handled properly because
        SQL's COL NOT IN (list containing null) handling is too weird to
        abstract away.
        """
        self.assertQuerySetEqual(
            NullableName.objects.exclude(name__in=[None]), ["i1"], attrgetter("name")
        )

    def test_double_exclude(self):
        """

        Tests the behavior of the ORM exclude functionality when using a double negation operator (~).

        Verifies that applying a double negation to a query filter results in the same query as the original filter, 
        without modifying the SQL query to incorrectly include an 'IS NOT NULL' condition.

        """
        self.assertEqual(
            list(NullableName.objects.filter(~~Q(name="i1"))),
            list(NullableName.objects.filter(Q(name="i1"))),
        )
        self.assertNotIn(
            "IS NOT NULL", str(NullableName.objects.filter(~~Q(name="i1")).query)
        )


class EmptyStringsAsNullTest(TestCase):
    """
    Filtering on non-null character fields works as expected.
    The reason for these tests is that Oracle treats '' as NULL, and this
    can cause problems in query construction. Refs #17957.
    """

    @classmethod
    def setUpTestData(cls):
        cls.nc = NamedCategory.objects.create(name="")

    def test_direct_exclude(self):
        self.assertQuerySetEqual(
            NamedCategory.objects.exclude(name__in=["nonexistent"]),
            [self.nc.pk],
            attrgetter("pk"),
        )

    def test_joined_exclude(self):
        self.assertQuerySetEqual(
            DumbCategory.objects.exclude(namedcategory__name__in=["nonexistent"]),
            [self.nc.pk],
            attrgetter("pk"),
        )

    def test_21001(self):
        foo = NamedCategory.objects.create(name="foo")
        self.assertQuerySetEqual(
            NamedCategory.objects.exclude(name=""), [foo.pk], attrgetter("pk")
        )


class ProxyQueryCleanupTest(TestCase):
    def test_evaluated_proxy_count(self):
        """
        Generating the query string doesn't alter the query's state
        in irreversible ways. Refs #18248.
        """
        ProxyCategory.objects.create()
        qs = ProxyCategory.objects.all()
        self.assertEqual(qs.count(), 1)
        str(qs.query)
        self.assertEqual(qs.count(), 1)


class WhereNodeTest(SimpleTestCase):
    class DummyNode:
        def as_sql(self, compiler, connection):
            return "dummy", []

    class MockCompiler:
        def compile(self, node):
            return node.as_sql(self, connection)

        def __call__(self, name):
            return connection.ops.quote_name(name)

    def test_empty_full_handling_conjunction(self):
        """

        Tests the handling of conjunctions within the WhereNode.

        This function ensures that the WhereNode class behaves correctly when dealing with
        empty or full result sets, and when handling conjunctions of different nodes.
        It verifies the following scenarios:

        - When a WhereNode contains a NothingNode, it raises an EmptyResultSet exception.
        - When a WhereNode contains a NothingNode and is negated, it raises a FullResultSet exception.
        - When a WhereNode contains multiple nodes connected by a conjunction, it generates the correct SQL.
        - When a WhereNode contains multiple nodes connected by a conjunction and is negated, it generates the correct negated SQL.
        - When a WhereNode contains a combination of NothingNode and other nodes connected by a conjunction, it raises the correct exception based on the node types and negation.

        These tests cover various edge cases and ensure the WhereNode class handles conjunctions correctly.

        """
        compiler = WhereNodeTest.MockCompiler()
        w = WhereNode(children=[NothingNode()])
        with self.assertRaises(EmptyResultSet):
            w.as_sql(compiler, connection)
        w.negate()
        with self.assertRaises(FullResultSet):
            w.as_sql(compiler, connection)
        w = WhereNode(children=[self.DummyNode(), self.DummyNode()])
        self.assertEqual(w.as_sql(compiler, connection), ("(dummy AND dummy)", []))
        w.negate()
        self.assertEqual(w.as_sql(compiler, connection), ("NOT (dummy AND dummy)", []))
        w = WhereNode(children=[NothingNode(), self.DummyNode()])
        with self.assertRaises(EmptyResultSet):
            w.as_sql(compiler, connection)
        w.negate()
        with self.assertRaises(FullResultSet):
            w.as_sql(compiler, connection)

    def test_empty_full_handling_disjunction(self):
        compiler = WhereNodeTest.MockCompiler()
        w = WhereNode(children=[NothingNode()], connector=OR)
        with self.assertRaises(EmptyResultSet):
            w.as_sql(compiler, connection)
        w.negate()
        with self.assertRaises(FullResultSet):
            w.as_sql(compiler, connection)
        w = WhereNode(children=[self.DummyNode(), self.DummyNode()], connector=OR)
        self.assertEqual(w.as_sql(compiler, connection), ("(dummy OR dummy)", []))
        w.negate()
        self.assertEqual(w.as_sql(compiler, connection), ("NOT (dummy OR dummy)", []))
        w = WhereNode(children=[NothingNode(), self.DummyNode()], connector=OR)
        self.assertEqual(w.as_sql(compiler, connection), ("dummy", []))
        w.negate()
        self.assertEqual(w.as_sql(compiler, connection), ("NOT (dummy)", []))

    def test_empty_nodes(self):
        compiler = WhereNodeTest.MockCompiler()
        empty_w = WhereNode()
        w = WhereNode(children=[empty_w, empty_w])
        with self.assertRaises(FullResultSet):
            w.as_sql(compiler, connection)
        w.negate()
        with self.assertRaises(EmptyResultSet):
            w.as_sql(compiler, connection)
        w.connector = OR
        with self.assertRaises(EmptyResultSet):
            w.as_sql(compiler, connection)
        w.negate()
        with self.assertRaises(FullResultSet):
            w.as_sql(compiler, connection)
        w = WhereNode(children=[empty_w, NothingNode()], connector=OR)
        with self.assertRaises(FullResultSet):
            w.as_sql(compiler, connection)
        w = WhereNode(children=[empty_w, NothingNode()], connector=AND)
        with self.assertRaises(EmptyResultSet):
            w.as_sql(compiler, connection)


class QuerySetExceptionTests(SimpleTestCase):
    def test_invalid_order_by(self):
        msg = "Cannot resolve keyword '*' into field. Choices are: created, id, name"
        with self.assertRaisesMessage(FieldError, msg):
            Article.objects.order_by("*")

    def test_invalid_order_by_raw_column_alias(self):
        msg = (
            "Cannot resolve keyword 'queries_author.name' into field. Choices "
            "are: cover, created, creator, creator_id, id, modified, name, "
            "note, note_id, tags"
        )
        with self.assertRaisesMessage(FieldError, msg):
            Item.objects.values("creator__name").order_by("queries_author.name")

    def test_invalid_queryset_model(self):
        """

        Tests that using a QuerySet for the wrong model raises an exception.

        Specifically, this test checks that attempting to use a QuerySet for the \"Article\" model
        in place of the \"ExtraInfo\" model results in a ValueError with a descriptive error message.

        The test verifies that the correct error message is raised when trying to filter authors
        based on a QuerySet of articles, ensuring that the correct model is used for the QuerySet.

        """
        msg = 'Cannot use QuerySet for "Article": Use a QuerySet for "ExtraInfo".'
        with self.assertRaisesMessage(ValueError, msg):
            list(Author.objects.filter(extra=Article.objects.all()))


class NullJoinPromotionOrTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        """

        Sets up test data for the class.

        This method creates a set of objects that can be used to test the functionality of the class.
        It creates instances of ModelD, ModelA, ModelB, and ModelC, and establishes relationships between them.
        The created objects are stored as class attributes, allowing them to be accessed and used in subsequent tests.

        The resulting test data includes two ModelA instances (a1 and a2) with different associated models (ModelD and ModelB).

        """
        cls.d1 = ModelD.objects.create(name="foo")
        d2 = ModelD.objects.create(name="bar")
        cls.a1 = ModelA.objects.create(name="a1", d=cls.d1)
        c = ModelC.objects.create(name="c")
        b = ModelB.objects.create(name="b", c=c)
        cls.a2 = ModelA.objects.create(name="a2", b=b, d=d2)

    def test_ticket_17886(self):
        # The first Q-object is generating the match, the rest of the filters
        # should not remove the match even if they do not match anything. The
        # problem here was that b__name generates a LOUTER JOIN, then
        # b__c__name generates join to c, which the ORM tried to promote but
        # failed as that join isn't nullable.
        q_obj = Q(d__name="foo") | Q(b__name="foo") | Q(b__c__name="foo")
        qset = ModelA.objects.filter(q_obj)
        self.assertEqual(list(qset), [self.a1])
        # We generate one INNER JOIN to D. The join is direct and not nullable
        # so we can use INNER JOIN for it. However, we can NOT use INNER JOIN
        # for the b->c join, as a->b is nullable.
        self.assertEqual(str(qset.query).count("INNER JOIN"), 1)

    def test_isnull_filter_promotion(self):
        qs = ModelA.objects.filter(Q(b__name__isnull=True))
        self.assertEqual(str(qs.query).count("LEFT OUTER"), 1)
        self.assertEqual(list(qs), [self.a1])

        qs = ModelA.objects.filter(~Q(b__name__isnull=True))
        self.assertEqual(str(qs.query).count("INNER JOIN"), 1)
        self.assertEqual(list(qs), [self.a2])

        qs = ModelA.objects.filter(~~Q(b__name__isnull=True))
        self.assertEqual(str(qs.query).count("LEFT OUTER"), 1)
        self.assertEqual(list(qs), [self.a1])

        qs = ModelA.objects.filter(Q(b__name__isnull=False))
        self.assertEqual(str(qs.query).count("INNER JOIN"), 1)
        self.assertEqual(list(qs), [self.a2])

        qs = ModelA.objects.filter(~Q(b__name__isnull=False))
        self.assertEqual(str(qs.query).count("LEFT OUTER"), 1)
        self.assertEqual(list(qs), [self.a1])

        qs = ModelA.objects.filter(~~Q(b__name__isnull=False))
        self.assertEqual(str(qs.query).count("INNER JOIN"), 1)
        self.assertEqual(list(qs), [self.a2])

    def test_null_join_demotion(self):
        """

        Tests the demotion of join types in ORM queries when null checks are performed.

        This test case verifies that the ORM correctly applies join types based on null checks.
        It checks the behavior of both intersection (`&` operator) and union (`|` operator) of null checks.
        The test ensures that the ORM demotes an inner join to a left outer join when a null check is performed with a union operator, 
        and that an inner join is used when a null check is performed with an intersection operator.

        """
        qs = ModelA.objects.filter(Q(b__name__isnull=False) & Q(b__name__isnull=True))
        self.assertIn(" INNER JOIN ", str(qs.query))
        qs = ModelA.objects.filter(Q(b__name__isnull=True) & Q(b__name__isnull=False))
        self.assertIn(" INNER JOIN ", str(qs.query))
        qs = ModelA.objects.filter(Q(b__name__isnull=False) | Q(b__name__isnull=True))
        self.assertIn(" LEFT OUTER JOIN ", str(qs.query))
        qs = ModelA.objects.filter(Q(b__name__isnull=True) | Q(b__name__isnull=False))
        self.assertIn(" LEFT OUTER JOIN ", str(qs.query))

    def test_ticket_21366(self):
        """
        Tests the filtering of reports based on creator's ranking and report name.

        This test case creates several models including a note, extra info, author, ranking, and reports. 
        It then filters reports where the creator's ranking is null or the creator's ranking is 1 and the report name is 'Foo'. 
        The test asserts that the correct SQL query is generated and the filtered reports are ordered correctly by name.

        The test covers the usage of Q objects for filtering and ensuring the correct joins are used in the SQL query.

        The expected outcome is to have a query with two left outer joins and two joins, 
        and to return reports in the correct order when sorted by name.
        """
        n = Note.objects.create(note="n", misc="m")
        e = ExtraInfo.objects.create(info="info", note=n)
        a = Author.objects.create(name="Author1", num=1, extra=e)
        Ranking.objects.create(rank=1, author=a)
        r1 = Report.objects.create(name="Foo", creator=a)
        r2 = Report.objects.create(name="Bar")
        Report.objects.create(name="Bar", creator=a)
        qs = Report.objects.filter(
            Q(creator__ranking__isnull=True) | Q(creator__ranking__rank=1, name="Foo")
        )
        self.assertEqual(str(qs.query).count("LEFT OUTER JOIN"), 2)
        self.assertEqual(str(qs.query).count(" JOIN "), 2)
        self.assertSequenceEqual(qs.order_by("name"), [r2, r1])

    def test_ticket_21748(self):
        i1 = Identifier.objects.create(name="i1")
        i2 = Identifier.objects.create(name="i2")
        i3 = Identifier.objects.create(name="i3")
        Program.objects.create(identifier=i1)
        Channel.objects.create(identifier=i1)
        Program.objects.create(identifier=i2)
        self.assertSequenceEqual(
            Identifier.objects.filter(program=None, channel=None), [i3]
        )
        self.assertSequenceEqual(
            Identifier.objects.exclude(program=None, channel=None).order_by("name"),
            [i1, i2],
        )

    def test_ticket_21748_double_negated_and(self):
        """
        Tests the correctness of the query built by excluding the double negation of identifiers 
        that are both in a specific program and channel, ensuring it produces the same results 
        as a filter query. Also validates that the number of JOIN operations in the queries 
        is equivalent, with a specific focus on INNER JOIN operations, to verify the 
        optimization of the query execution plan.
        """
        i1 = Identifier.objects.create(name="i1")
        i2 = Identifier.objects.create(name="i2")
        Identifier.objects.create(name="i3")
        p1 = Program.objects.create(identifier=i1)
        c1 = Channel.objects.create(identifier=i1)
        Program.objects.create(identifier=i2)
        # Check the ~~Q() (or equivalently .exclude(~Q)) works like Q() for
        # join promotion.
        qs1_doubleneg = Identifier.objects.exclude(
            ~Q(program__id=p1.id, channel__id=c1.id)
        ).order_by("pk")
        qs1_filter = Identifier.objects.filter(
            program__id=p1.id, channel__id=c1.id
        ).order_by("pk")
        self.assertQuerySetEqual(qs1_doubleneg, qs1_filter, lambda x: x)
        self.assertEqual(
            str(qs1_filter.query).count("JOIN"), str(qs1_doubleneg.query).count("JOIN")
        )
        self.assertEqual(2, str(qs1_doubleneg.query).count("INNER JOIN"))
        self.assertEqual(
            str(qs1_filter.query).count("INNER JOIN"),
            str(qs1_doubleneg.query).count("INNER JOIN"),
        )

    def test_ticket_21748_double_negated_or(self):
        """

        Tests that using double negation in a query filter (e.g., `exclude(~Q(...))`) 
        produces the same results as a direct filter (e.g., `filter(Q(...))`) 
        when using `Q` objects with logical OR operations.

        Verifies that the queries generate the same SQL, including JOIN operations.

        """
        i1 = Identifier.objects.create(name="i1")
        i2 = Identifier.objects.create(name="i2")
        Identifier.objects.create(name="i3")
        p1 = Program.objects.create(identifier=i1)
        c1 = Channel.objects.create(identifier=i1)
        p2 = Program.objects.create(identifier=i2)
        # Test OR + doubleneg. The expected result is that channel is LOUTER
        # joined, program INNER joined
        qs1_filter = Identifier.objects.filter(
            Q(program__id=p2.id, channel__id=c1.id) | Q(program__id=p1.id)
        ).order_by("pk")
        qs1_doubleneg = Identifier.objects.exclude(
            ~Q(Q(program__id=p2.id, channel__id=c1.id) | Q(program__id=p1.id))
        ).order_by("pk")
        self.assertQuerySetEqual(qs1_doubleneg, qs1_filter, lambda x: x)
        self.assertEqual(
            str(qs1_filter.query).count("JOIN"), str(qs1_doubleneg.query).count("JOIN")
        )
        self.assertEqual(1, str(qs1_doubleneg.query).count("INNER JOIN"))
        self.assertEqual(
            str(qs1_filter.query).count("INNER JOIN"),
            str(qs1_doubleneg.query).count("INNER JOIN"),
        )

    def test_ticket_21748_complex_filter(self):
        i1 = Identifier.objects.create(name="i1")
        i2 = Identifier.objects.create(name="i2")
        Identifier.objects.create(name="i3")
        p1 = Program.objects.create(identifier=i1)
        c1 = Channel.objects.create(identifier=i1)
        p2 = Program.objects.create(identifier=i2)
        # Finally, a more complex case, one time in a way where each
        # NOT is pushed to lowest level in the boolean tree, and
        # another query where this isn't done.
        qs1 = Identifier.objects.filter(
            ~Q(~Q(program__id=p2.id, channel__id=c1.id) & Q(program__id=p1.id))
        ).order_by("pk")
        qs2 = Identifier.objects.filter(
            Q(Q(program__id=p2.id, channel__id=c1.id) | ~Q(program__id=p1.id))
        ).order_by("pk")
        self.assertQuerySetEqual(qs1, qs2, lambda x: x)
        self.assertEqual(str(qs1.query).count("JOIN"), str(qs2.query).count("JOIN"))
        self.assertEqual(0, str(qs1.query).count("INNER JOIN"))
        self.assertEqual(
            str(qs1.query).count("INNER JOIN"), str(qs2.query).count("INNER JOIN")
        )


class ReverseJoinTrimmingTest(TestCase):
    def test_reverse_trimming(self):
        # We don't accidentally trim reverse joins - we can't know if there is
        # anything on the other side of the join, so trimming reverse joins
        # can't be done, ever.
        t = Tag.objects.create()
        qs = Tag.objects.filter(annotation__tag=t.pk)
        self.assertIn("INNER JOIN", str(qs.query))
        self.assertEqual(list(qs), [])


class JoinReuseTest(TestCase):
    """
    The queries reuse joins sensibly (for example, direct joins
    are always reused).
    """

    def test_fk_reuse(self):
        qs = Annotation.objects.filter(tag__name="foo").filter(tag__name="bar")
        self.assertEqual(str(qs.query).count("JOIN"), 1)

    def test_fk_reuse_select_related(self):
        """
        Tests the reuse of foreign keys when using select_related in a query.

        This test ensures that when a foreign key is reused in a query, the related
        objects are fetched correctly and only one join is performed. It verifies
        that the query is optimized to reduce database overhead by minimizing the
        number of joins required to retrieve the related data.

        The test case checks the query generated by the ORM to confirm that only
        a single join is performed, which is essential for maintaining efficient
        database queries and preventing potential performance issues.
        """
        qs = Annotation.objects.filter(tag__name="foo").select_related("tag")
        self.assertEqual(str(qs.query).count("JOIN"), 1)

    def test_fk_reuse_annotation(self):
        """

        Tests the foreign key reuse annotation functionality.

        Verifies that when using Django's ORM to annotate a queryset with a Count 
        aggregation on a column from a related model, the generated SQL query 
        contains the expected number of joins.

        Specifically, this test checks that a single join is performed when 
        annotating the queryset with a count of tags, ensuring that the 
         relationship between the models is properly leveraged.

        """
        qs = Annotation.objects.filter(tag__name="foo").annotate(cnt=Count("tag__name"))
        self.assertEqual(str(qs.query).count("JOIN"), 1)

    def test_fk_reuse_disjunction(self):
        """
        Tests that the Django ORM generates the correct SQL query when using a disjunction (`|`) operator with foreign key lookups, specifically that it reuses the same join for matching conditions.

        The test case verifies that a query with disjunctive conditions on a related model's attribute, in this case filtering annotations by tags named 'foo' or 'bar', results in a SQL query with only one join operation.
        """
        qs = Annotation.objects.filter(Q(tag__name="foo") | Q(tag__name="bar"))
        self.assertEqual(str(qs.query).count("JOIN"), 1)

    def test_fk_reuse_order_by(self):
        """
         Tests that the foreign key 'reuse' optimization is applied correctly when ordering by a foreign key field.

            Verifies that Django's ORM generates a single JOIN operation for the given query, 
            demonstrating the optimal reuse of the foreign key relationship in the ordering process. 
        """
        qs = Annotation.objects.filter(tag__name="foo").order_by("tag__name")
        self.assertEqual(str(qs.query).count("JOIN"), 1)

    def test_revo2o_reuse(self):
        qs = Detail.objects.filter(member__name="foo").filter(member__name="foo")
        self.assertEqual(str(qs.query).count("JOIN"), 1)

    def test_revfk_noreuse(self):
        qs = Author.objects.filter(report__name="r4").filter(report__name="r1")
        self.assertEqual(str(qs.query).count("JOIN"), 2)

    def test_inverted_q_across_relations(self):
        """
        When a trimmable join is specified in the query (here school__), the
        ORM detects it and removes unnecessary joins. The set of reusable joins
        are updated after trimming the query so that other lookups don't
        consider that the outer query's filters are in effect for the subquery
        (#26551).
        """
        springfield_elementary = School.objects.create()
        hogward = School.objects.create()
        Student.objects.create(school=springfield_elementary)
        hp = Student.objects.create(school=hogward)
        Classroom.objects.create(school=hogward, name="Potion")
        Classroom.objects.create(school=springfield_elementary, name="Main")
        qs = Student.objects.filter(
            ~(
                Q(school__classroom__name="Main")
                & Q(school__classroom__has_blackboard=None)
            )
        )
        self.assertSequenceEqual(qs, [hp])


class DisjunctionPromotionTests(TestCase):
    def test_disjunction_promotion_select_related(self):
        """
        Tests whether disjunction promotion is handled correctly when using select_related.

        This function verifies that a query with a disjunction operation (i.e., an \"or\" condition)
        does not produce incorrect join operations when using the `select_related` method. It checks
        that both an empty join and an inner join are not present in the generated SQL, and that
        instead, a left outer join is used for each related field. It also ensures that the query
        can be executed in a single database query and returns the expected results.
        """
        fk1 = FK1.objects.create(f1="f1", f2="f2")
        basea = BaseA.objects.create(a=fk1)
        qs = BaseA.objects.filter(Q(a=fk1) | Q(b=2))
        self.assertEqual(str(qs.query).count(" JOIN "), 0)
        qs = qs.select_related("a", "b")
        self.assertEqual(str(qs.query).count(" INNER JOIN "), 0)
        self.assertEqual(str(qs.query).count(" LEFT OUTER JOIN "), 2)
        with self.assertNumQueries(1):
            self.assertSequenceEqual(qs, [basea])
            self.assertEqual(qs[0].a, fk1)
            self.assertIs(qs[0].b, None)

    def test_disjunction_promotion1(self):
        # Pre-existing join, add two ORed filters to the same join,
        # all joins can be INNER JOINS.
        """
        Tests the promotion of disjunctions in database queries.

        Verifies the correct generation of SQL joins when applying filters with 
        disjunctions (logical OR operations) to querysets. It checks the number 
        of INNER JOINs in the resulting query to ensure that the disjunction 
        promotes the correct join behavior.

        The test covers scenarios where a disjunction is applied to an existing 
        queryset with a filter, as well as when a disjunction is applied directly 
        to a model's objects. The expected outcome is that the disjunction 
        promotes an additional INNER JOIN when applied to an existing queryset 
        with a filter, but not when applied directly to a model's objects.
        """
        qs = BaseA.objects.filter(a__f1="foo")
        self.assertEqual(str(qs.query).count("INNER JOIN"), 1)
        qs = qs.filter(Q(b__f1="foo") | Q(b__f2="foo"))
        self.assertEqual(str(qs.query).count("INNER JOIN"), 2)
        # Reverse the order of AND and OR filters.
        qs = BaseA.objects.filter(Q(b__f1="foo") | Q(b__f2="foo"))
        self.assertEqual(str(qs.query).count("INNER JOIN"), 1)
        qs = qs.filter(a__f1="foo")
        self.assertEqual(str(qs.query).count("INNER JOIN"), 2)

    def test_disjunction_promotion2(self):
        """

        Test disjunction promotion in Django ORM queries.

        This test case verifies the correct promotion of disjunctions in filtered queries,
        ensuring that the resulting SQL query uses the expected types and number of joins.

        Specifically, it checks that filtering a base query with a disjunction of related
        fields results in the correct number of inner and left outer joins in the generated
        SQL query, both when the disjunction is applied directly to the base query and
        when it is applied to a previously filtered query.

        """
        qs = BaseA.objects.filter(a__f1="foo")
        self.assertEqual(str(qs.query).count("INNER JOIN"), 1)
        # Now we have two different joins in an ORed condition, these
        # must be OUTER joins. The pre-existing join should remain INNER.
        qs = qs.filter(Q(b__f1="foo") | Q(c__f2="foo"))
        self.assertEqual(str(qs.query).count("INNER JOIN"), 1)
        self.assertEqual(str(qs.query).count("LEFT OUTER JOIN"), 2)
        # Reverse case.
        qs = BaseA.objects.filter(Q(b__f1="foo") | Q(c__f2="foo"))
        self.assertEqual(str(qs.query).count("LEFT OUTER JOIN"), 2)
        qs = qs.filter(a__f1="foo")
        self.assertEqual(str(qs.query).count("INNER JOIN"), 1)
        self.assertEqual(str(qs.query).count("LEFT OUTER JOIN"), 2)

    def test_disjunction_promotion3(self):
        """

        Tests the promotion of disjunctions in query filtering.

        This test case verifies that when applying a disjunction filter to an existing query,
        the resulting database query performs the expected joins, ensuring efficient data retrieval.
        It checks that the use of the disjunction operator does not introduce unnecessary joins.

        The test specifically examines the number of INNER JOIN and LEFT OUTER JOIN operations
        performed in the generated SQL query, ensuring that the query is optimized as expected.

        """
        qs = BaseA.objects.filter(a__f2="bar")
        self.assertEqual(str(qs.query).count("INNER JOIN"), 1)
        # The ANDed a__f2 filter allows us to use keep using INNER JOIN
        # even inside the ORed case. If the join to a__ returns nothing,
        # the ANDed filter for a__f2 can't be true.
        qs = qs.filter(Q(a__f1="foo") | Q(b__f2="foo"))
        self.assertEqual(str(qs.query).count("INNER JOIN"), 1)
        self.assertEqual(str(qs.query).count("LEFT OUTER JOIN"), 1)

    def test_disjunction_promotion3_demote(self):
        # This one needs demotion logic: the first filter causes a to be
        # outer joined, the second filter makes it inner join again.
        """

        Tests the promotion of disjunctions in query filters.

        Ensures that when filtering on a disjunction of fields from different models,
        the resulting query uses an optimal join strategy, reducing the number of joins.

        Verifies that in cases where a disjunction involves a field from a related model
        and a subsequent filter is applied to the primary model, the query still uses
        an efficient join approach, minimizing the number of joins to achieve the desired result.

        """
        qs = BaseA.objects.filter(Q(a__f1="foo") | Q(b__f2="foo")).filter(a__f2="bar")
        self.assertEqual(str(qs.query).count("INNER JOIN"), 1)
        self.assertEqual(str(qs.query).count("LEFT OUTER JOIN"), 1)

    def test_disjunction_promotion4_demote(self):
        """
        Tests the promotion and demotion behavior of disjunction queries in the ORM.

        This test case checks two scenarios:

        1. Initially, it verifies that a query with a disjunction (OR operation) does not result in any joins.
        2. Then, it tests that adding a subsequent filter on a related field correctly promotes the query to include a join operation.
        """
        qs = BaseA.objects.filter(Q(a=1) | Q(a=2))
        self.assertEqual(str(qs.query).count("JOIN"), 0)
        # Demote needed for the "a" join. It is marked as outer join by
        # above filter (even if it is trimmed away).
        qs = qs.filter(a__f1="foo")
        self.assertEqual(str(qs.query).count("INNER JOIN"), 1)

    def test_disjunction_promotion4(self):
        qs = BaseA.objects.filter(a__f1="foo")
        self.assertEqual(str(qs.query).count("INNER JOIN"), 1)
        qs = qs.filter(Q(a=1) | Q(a=2))
        self.assertEqual(str(qs.query).count("INNER JOIN"), 1)

    def test_disjunction_promotion5_demote(self):
        qs = BaseA.objects.filter(Q(a=1) | Q(a=2))
        # Note that the above filters on a force the join to an
        # inner join even if it is trimmed.
        self.assertEqual(str(qs.query).count("JOIN"), 0)
        qs = qs.filter(Q(a__f1="foo") | Q(b__f1="foo"))
        # So, now the a__f1 join doesn't need promotion.
        self.assertEqual(str(qs.query).count("INNER JOIN"), 1)
        # But b__f1 does.
        self.assertEqual(str(qs.query).count("LEFT OUTER JOIN"), 1)
        qs = BaseA.objects.filter(Q(a__f1="foo") | Q(b__f1="foo"))
        # Now the join to a is created as LOUTER
        self.assertEqual(str(qs.query).count("LEFT OUTER JOIN"), 2)
        qs = qs.filter(Q(a=1) | Q(a=2))
        self.assertEqual(str(qs.query).count("INNER JOIN"), 1)
        self.assertEqual(str(qs.query).count("LEFT OUTER JOIN"), 1)

    def test_disjunction_promotion6(self):
        """

        Tests the promotion and combination of disjunctions in Django ORM queries.

        Verifies that filter operations with disjunctions (OR conditions) are correctly
        translated to SQL queries without unnecessary joins, and that conjunctions (AND
        conditions) involving lookup types that require joins result in the expected
        number of inner joins.

        Also checks that subsequent filter operations do not alter the expected join
        structure of the query.

        """
        qs = BaseA.objects.filter(Q(a=1) | Q(a=2))
        self.assertEqual(str(qs.query).count("JOIN"), 0)
        qs = BaseA.objects.filter(Q(a__f1="foo") & Q(b__f1="foo"))
        self.assertEqual(str(qs.query).count("INNER JOIN"), 2)
        self.assertEqual(str(qs.query).count("LEFT OUTER JOIN"), 0)

        qs = BaseA.objects.filter(Q(a__f1="foo") & Q(b__f1="foo"))
        self.assertEqual(str(qs.query).count("LEFT OUTER JOIN"), 0)
        self.assertEqual(str(qs.query).count("INNER JOIN"), 2)
        qs = qs.filter(Q(a=1) | Q(a=2))
        self.assertEqual(str(qs.query).count("INNER JOIN"), 2)
        self.assertEqual(str(qs.query).count("LEFT OUTER JOIN"), 0)

    def test_disjunction_promotion7(self):
        qs = BaseA.objects.filter(Q(a=1) | Q(a=2))
        self.assertEqual(str(qs.query).count("JOIN"), 0)
        qs = BaseA.objects.filter(Q(a__f1="foo") | (Q(b__f1="foo") & Q(a__f1="bar")))
        self.assertEqual(str(qs.query).count("INNER JOIN"), 1)
        self.assertEqual(str(qs.query).count("LEFT OUTER JOIN"), 1)
        qs = BaseA.objects.filter(
            (Q(a__f1="foo") | Q(b__f1="foo")) & (Q(a__f1="bar") | Q(c__f1="foo"))
        )
        self.assertEqual(str(qs.query).count("LEFT OUTER JOIN"), 3)
        self.assertEqual(str(qs.query).count("INNER JOIN"), 0)
        qs = BaseA.objects.filter(
            Q(a__f1="foo") | Q(a__f1="bar") & (Q(b__f1="bar") | Q(c__f1="foo"))
        )
        self.assertEqual(str(qs.query).count("LEFT OUTER JOIN"), 2)
        self.assertEqual(str(qs.query).count("INNER JOIN"), 1)

    def test_disjunction_promotion_fexpression(self):
        """

        Tests the promotion of disjunction in filter expressions, ensuring that the correct number of LEFT OUTER JOIN and INNER JOIN operations are performed.

        This test case covers various scenarios where disjunction is used in filter expressions, including the use of F expressions and Q objects. The goal is to verify that the Django ORM correctly handles disjunction and generates the expected SQL query with the correct join operations.

        The test checks the count of LEFT OUTER JOIN and INNER JOIN operations in the generated SQL query, ensuring that it matches the expected number in different scenarios. This helps to validate the correctness of the disjunction promotion logic in the Django ORM.

        """
        qs = BaseA.objects.filter(Q(a__f1=F("b__f1")) | Q(b__f1="foo"))
        self.assertEqual(str(qs.query).count("LEFT OUTER JOIN"), 1)
        self.assertEqual(str(qs.query).count("INNER JOIN"), 1)
        qs = BaseA.objects.filter(Q(a__f1=F("c__f1")) | Q(b__f1="foo"))
        self.assertEqual(str(qs.query).count("LEFT OUTER JOIN"), 3)
        qs = BaseA.objects.filter(
            Q(a__f1=F("b__f1")) | Q(a__f2=F("b__f2")) | Q(c__f1="foo")
        )
        self.assertEqual(str(qs.query).count("LEFT OUTER JOIN"), 3)
        qs = BaseA.objects.filter(Q(a__f1=F("c__f1")) | (Q(pk=1) & Q(pk=2)))
        self.assertEqual(str(qs.query).count("LEFT OUTER JOIN"), 2)
        self.assertEqual(str(qs.query).count("INNER JOIN"), 0)


class ManyToManyExcludeTest(TestCase):
    def test_exclude_many_to_many(self):
        """

        Tests the exclude operation on many-to-many relationships in the Identifier model.

        This function verifies that the exclude method correctly filters out identifiers
        based on the relationships between programs and channels.

        It checks two scenarios:

        * Excluding identifiers where the associated program belongs to a specific channel.
        * Excluding identifiers where the associated program does not belong to any channel.

        The function ensures that the results are ordered alphabetically by identifier name.

        """
        i_extra = Identifier.objects.create(name="extra")
        i_program = Identifier.objects.create(name="program")
        program = Program.objects.create(identifier=i_program)
        i_channel = Identifier.objects.create(name="channel")
        channel = Channel.objects.create(identifier=i_channel)
        channel.programs.add(program)

        # channel contains 'program1', so all Identifiers except that one
        # should be returned
        self.assertSequenceEqual(
            Identifier.objects.exclude(program__channel=channel).order_by("name"),
            [i_channel, i_extra],
        )
        self.assertSequenceEqual(
            Identifier.objects.exclude(program__channel=None).order_by("name"),
            [i_program],
        )

    def test_ticket_12823(self):
        pg3 = Page.objects.create(text="pg3")
        pg2 = Page.objects.create(text="pg2")
        pg1 = Page.objects.create(text="pg1")
        pa1 = Paragraph.objects.create(text="pa1")
        pa1.page.set([pg1, pg2])
        pa2 = Paragraph.objects.create(text="pa2")
        pa2.page.set([pg2, pg3])
        pa3 = Paragraph.objects.create(text="pa3")
        ch1 = Chapter.objects.create(title="ch1", paragraph=pa1)
        ch2 = Chapter.objects.create(title="ch2", paragraph=pa2)
        ch3 = Chapter.objects.create(title="ch3", paragraph=pa3)
        b1 = Book.objects.create(title="b1", chapter=ch1)
        b2 = Book.objects.create(title="b2", chapter=ch2)
        b3 = Book.objects.create(title="b3", chapter=ch3)
        q = Book.objects.exclude(chapter__paragraph__page__text="pg1")
        self.assertNotIn("IS NOT NULL", str(q.query))
        self.assertEqual(len(q), 2)
        self.assertNotIn(b1, q)
        self.assertIn(b2, q)
        self.assertIn(b3, q)


class RelabelCloneTest(TestCase):
    def test_ticket_19964(self):
        """

        Tests the case where an object is its own parent and has a child object.

        Verifies that an object can be successfully saved with itself as its parent,
        and that querying for objects with themselves as parents returns the correct results.
        Also checks that querying for child objects of these self-parenting objects works as expected.

        """
        my1 = MyObject.objects.create(data="foo")
        my1.parent = my1
        my1.save()
        my2 = MyObject.objects.create(data="bar", parent=my1)
        parents = MyObject.objects.filter(parent=F("id"))
        children = MyObject.objects.filter(parent__in=parents).exclude(parent=F("id"))
        self.assertEqual(list(parents), [my1])
        # Evaluating the children query (which has parents as part of it) does
        # not change results for the parents query.
        self.assertEqual(list(children), [my2])
        self.assertEqual(list(parents), [my1])


class Ticket20101Tests(TestCase):
    def test_ticket_20101(self):
        """
        Tests QuerySet ORed combining in exclude subquery case.
        """
        t = Tag.objects.create(name="foo")
        a1 = Annotation.objects.create(tag=t, name="a1")
        a2 = Annotation.objects.create(tag=t, name="a2")
        a3 = Annotation.objects.create(tag=t, name="a3")
        n = Note.objects.create(note="foo", misc="bar")
        qs1 = Note.objects.exclude(annotation__in=[a1, a2])
        qs2 = Note.objects.filter(annotation__in=[a3])
        self.assertIn(n, qs1)
        self.assertNotIn(n, qs2)
        self.assertIn(n, (qs1 | qs2))


class EmptyStringPromotionTests(SimpleTestCase):
    def test_empty_string_promotion(self):
        qs = RelatedObject.objects.filter(single__name="")
        if connection.features.interprets_empty_strings_as_nulls:
            self.assertIn("LEFT OUTER JOIN", str(qs.query))
        else:
            self.assertNotIn("LEFT OUTER JOIN", str(qs.query))


class ValuesSubqueryTests(TestCase):
    def test_values_in_subquery(self):
        # If a values() queryset is used, then the given values
        # will be used instead of forcing use of the relation's field.
        """
        Tests that the values_in_subquery functionality works as expected.

        This test creates a set of Order and OrderItem objects with specific statuses, 
        then checks that the query to find Orders with items matching those statuses 
        returns the expected results.

        Specifically, it verifies that an Order is returned if it has an item 
        with a status that matches its own id, and another Order is not returned 
        if its item's status does not match its id.

        The test uses assertSequenceEqual to ensure that the order of the results 
        matches the expected order, in addition to checking that the results are 
        correct.
        """
        o1 = Order.objects.create(id=-2)
        o2 = Order.objects.create(id=-1)
        oi1 = OrderItem.objects.create(order=o1, status=0)
        oi1.status = oi1.pk
        oi1.save()
        OrderItem.objects.create(order=o2, status=0)

        # The query below should match o1 as it has related order_item
        # with id == status.
        self.assertSequenceEqual(
            Order.objects.filter(items__in=OrderItem.objects.values_list("status")),
            [o1],
        )


class DoubleInSubqueryTests(TestCase):
    def test_double_subquery_in(self):
        """
        Test case for evaluating the result of a double subquery operation.

        This test verifies that a query which filters objects based on a nested subquery correctly returns the expected results. Specifically, it checks that a query on LeafB objects, filtered through a join table and a subquery on LeafA objects, returns only the LeafB objects that are associated with the LeafA object matching the specified criteria.

        The test uses sample data to establish relationships between LeafA and LeafB objects via a join table, and then constructs a query that applies a double subquery to filter the results. The expected outcome is a single LeafB object that matches the specified conditions, which is asserted to match the actual query result.
        """
        lfa1 = LeafA.objects.create(data="foo")
        lfa2 = LeafA.objects.create(data="bar")
        lfb1 = LeafB.objects.create(data="lfb1")
        lfb2 = LeafB.objects.create(data="lfb2")
        Join.objects.create(a=lfa1, b=lfb1)
        Join.objects.create(a=lfa2, b=lfb2)
        leaf_as = LeafA.objects.filter(data="foo").values_list("pk", flat=True)
        joins = Join.objects.filter(a__in=leaf_as).values_list("b__id", flat=True)
        qs = LeafB.objects.filter(pk__in=joins)
        self.assertSequenceEqual(qs, [lfb1])


class Ticket18785Tests(SimpleTestCase):
    def test_ticket_18785(self):
        # Test join trimming from ticket18785
        """
        Tests that the database query for a specific item filter does not generate unnecessary join operations, ensuring efficient database access. 

        The test verifies that only an inner join is used in the query, with no outer joins, when filtering items by name and specific conditions on the creator and note fields. The expected count of join operations is checked to confirm the query's efficiency.
        """
        qs = (
            Item.objects.exclude(note__isnull=False)
            .filter(name="something", creator__extra__isnull=True)
            .order_by()
        )
        self.assertEqual(1, str(qs.query).count("INNER JOIN"))
        self.assertEqual(0, str(qs.query).count("OUTER JOIN"))


class Ticket20788Tests(TestCase):
    def test_ticket_20788(self):
        """

        Tests the filtering of books that do not contain a specific page in their chapters.

        This test creates a complex structure of books, chapters, paragraphs, and pages to verify
        that the exclude method correctly identifies books whose chapters do not contain a given page.
        It checks that only books with chapters containing paragraphs not associated with the specified page are returned.

        """
        Paragraph.objects.create()
        paragraph = Paragraph.objects.create()
        page = paragraph.page.create()
        chapter = Chapter.objects.create(paragraph=paragraph)
        Book.objects.create(chapter=chapter)

        paragraph2 = Paragraph.objects.create()
        Page.objects.create()
        chapter2 = Chapter.objects.create(paragraph=paragraph2)
        book2 = Book.objects.create(chapter=chapter2)

        sentences_not_in_pub = Book.objects.exclude(chapter__paragraph__page=page)
        self.assertSequenceEqual(sentences_not_in_pub, [book2])


class Ticket12807Tests(TestCase):
    def test_ticket_12807(self):
        p1 = Paragraph.objects.create()
        p2 = Paragraph.objects.create()
        # The ORed condition below should have no effect on the query - the
        # ~Q(pk__in=[]) will always be True.
        qs = Paragraph.objects.filter((Q(pk=p2.pk) | ~Q(pk__in=[])) & Q(pk=p1.pk))
        self.assertSequenceEqual(qs, [p1])


class RelatedLookupTypeTests(TestCase):
    error = 'Cannot query "%s": Must be "%s" instance.'

    @classmethod
    def setUpTestData(cls):
        cls.oa = ObjectA.objects.create(name="oa")
        cls.poa = ProxyObjectA.objects.get(name="oa")
        cls.coa = ChildObjectA.objects.create(name="coa")
        cls.wrong_type = Order.objects.create(id=cls.oa.pk)
        cls.ob = ObjectB.objects.create(name="ob", objecta=cls.oa, num=1)
        cls.pob1 = ProxyObjectB.objects.create(name="pob", objecta=cls.oa, num=2)
        cls.pob = ProxyObjectB.objects.all()
        cls.c = ObjectC.objects.create(childobjecta=cls.coa)

    def test_wrong_type_lookup(self):
        """
        A ValueError is raised when the incorrect object type is passed to a
        query lookup.
        """
        # Passing incorrect object type
        with self.assertRaisesMessage(
            ValueError, self.error % (self.wrong_type, ObjectA._meta.object_name)
        ):
            ObjectB.objects.get(objecta=self.wrong_type)

        with self.assertRaisesMessage(
            ValueError, self.error % (self.wrong_type, ObjectA._meta.object_name)
        ):
            ObjectB.objects.filter(objecta__in=[self.wrong_type])

        with self.assertRaisesMessage(
            ValueError, self.error % (self.wrong_type, ObjectA._meta.object_name)
        ):
            ObjectB.objects.filter(objecta=self.wrong_type)

        with self.assertRaisesMessage(
            ValueError, self.error % (self.wrong_type, ObjectB._meta.object_name)
        ):
            ObjectA.objects.filter(objectb__in=[self.wrong_type, self.ob])

        # Passing an object of the class on which query is done.
        with self.assertRaisesMessage(
            ValueError, self.error % (self.ob, ObjectA._meta.object_name)
        ):
            ObjectB.objects.filter(objecta__in=[self.poa, self.ob])

        with self.assertRaisesMessage(
            ValueError, self.error % (self.ob, ChildObjectA._meta.object_name)
        ):
            ObjectC.objects.exclude(childobjecta__in=[self.coa, self.ob])

    def test_wrong_backward_lookup(self):
        """
        A ValueError is raised when the incorrect object type is passed to a
        query lookup for backward relations.
        """
        with self.assertRaisesMessage(
            ValueError, self.error % (self.oa, ObjectB._meta.object_name)
        ):
            ObjectA.objects.filter(objectb__in=[self.oa, self.ob])

        with self.assertRaisesMessage(
            ValueError, self.error % (self.oa, ObjectB._meta.object_name)
        ):
            ObjectA.objects.exclude(objectb=self.oa)

        with self.assertRaisesMessage(
            ValueError, self.error % (self.wrong_type, ObjectB._meta.object_name)
        ):
            ObjectA.objects.get(objectb=self.wrong_type)

    def test_correct_lookup(self):
        """
        When passing proxy model objects, child objects, or parent objects,
        lookups work fine.
        """
        out_a = [self.oa]
        out_b = [self.ob, self.pob1]
        out_c = [self.c]

        # proxy model objects
        self.assertSequenceEqual(
            ObjectB.objects.filter(objecta=self.poa).order_by("name"), out_b
        )
        self.assertSequenceEqual(
            ObjectA.objects.filter(objectb__in=self.pob).order_by("pk"), out_a * 2
        )

        # child objects
        self.assertSequenceEqual(ObjectB.objects.filter(objecta__in=[self.coa]), [])
        self.assertSequenceEqual(
            ObjectB.objects.filter(objecta__in=[self.poa, self.coa]).order_by("name"),
            out_b,
        )
        self.assertSequenceEqual(
            ObjectB.objects.filter(objecta__in=iter([self.poa, self.coa])).order_by(
                "name"
            ),
            out_b,
        )

        # parent objects
        self.assertSequenceEqual(ObjectC.objects.exclude(childobjecta=self.oa), out_c)

        # QuerySet related object type checking shouldn't issue queries
        # (the querysets aren't evaluated here, hence zero queries) (#23266).
        with self.assertNumQueries(0):
            ObjectB.objects.filter(objecta__in=ObjectA.objects.all())

    def test_values_queryset_lookup(self):
        """
        ValueQuerySets are not checked for compatibility with the lookup field.
        """
        # Make sure the num and objecta field values match.
        ob = ObjectB.objects.get(name="ob")
        ob.num = ob.objecta.pk
        ob.save()
        pob = ObjectB.objects.get(name="pob")
        pob.num = pob.objecta.pk
        pob.save()
        self.assertSequenceEqual(
            ObjectB.objects.filter(
                objecta__in=ObjectB.objects.values_list("num")
            ).order_by("pk"),
            [ob, pob],
        )


class Ticket14056Tests(TestCase):
    def test_ticket_14056(self):
        """

        Tests the ordering of SharedConnection objects based on the presence of a related PointerA object.

        The test creates three SharedConnection objects and associates one of them with a PointerA object.
        It then verifies that the SharedConnection objects are ordered correctly, taking into account the database's null ordering behavior.
        The expected ordering depends on whether the database orders null values as largest or smallest.

        """
        s1 = SharedConnection.objects.create(data="s1")
        s2 = SharedConnection.objects.create(data="s2")
        s3 = SharedConnection.objects.create(data="s3")
        PointerA.objects.create(connection=s2)
        expected_ordering = (
            [s1, s3, s2] if connection.features.nulls_order_largest else [s2, s1, s3]
        )
        self.assertSequenceEqual(
            SharedConnection.objects.order_by("-pointera__connection", "pk"),
            expected_ordering,
        )


class Ticket20955Tests(TestCase):
    def test_ticket_20955(self):
        """
        Tests the effectiveness of using select_related to prefetch related objects in the Task model.

        The test creates staff members, assigns them to tasks, and then queries the tasks using select_related to 
        prefetch the creator and owner's staff information. It verifies that using select_related reduces the 
        number of database queries made when accessing the staff information, resulting in improved performance.

        Specifically, it checks that the query generated by select_related includes the required JOIN statements 
        and that accessing the staff information does not result in additional database queries.
        """
        jack = Staff.objects.create(name="jackstaff")
        jackstaff = StaffUser.objects.create(staff=jack)
        jill = Staff.objects.create(name="jillstaff")
        jillstaff = StaffUser.objects.create(staff=jill)
        task = Task.objects.create(creator=jackstaff, owner=jillstaff, title="task")
        task_get = Task.objects.get(pk=task.pk)
        # Load data so that assertNumQueries doesn't complain about the get
        # version's queries.
        task_get.creator.staffuser.staff
        task_get.owner.staffuser.staff
        qs = Task.objects.select_related(
            "creator__staffuser__staff", "owner__staffuser__staff"
        )
        self.assertEqual(str(qs.query).count(" JOIN "), 6)
        task_select_related = qs.get(pk=task.pk)
        with self.assertNumQueries(0):
            self.assertEqual(
                task_select_related.creator.staffuser.staff,
                task_get.creator.staffuser.staff,
            )
            self.assertEqual(
                task_select_related.owner.staffuser.staff,
                task_get.owner.staffuser.staff,
            )


class Ticket21203Tests(TestCase):
    def test_ticket_21203(self):
        p = Ticket21203Parent.objects.create(parent_bool=True)
        c = Ticket21203Child.objects.create(parent=p)
        qs = Ticket21203Child.objects.select_related("parent").defer("parent__created")
        self.assertSequenceEqual(qs, [c])
        self.assertIs(qs[0].parent.parent_bool, True)


class ValuesJoinPromotionTests(TestCase):
    def test_values_no_promotion_for_existing(self):
        qs = Node.objects.filter(parent__parent__isnull=False)
        self.assertIn(" INNER JOIN ", str(qs.query))
        qs = qs.values("parent__parent__id")
        self.assertIn(" INNER JOIN ", str(qs.query))
        # Make sure there is a left outer join without the filter.
        qs = Node.objects.values("parent__parent__id")
        self.assertIn(" LEFT OUTER JOIN ", str(qs.query))

    def test_non_nullable_fk_not_promoted(self):
        qs = ObjectB.objects.values("objecta__name")
        self.assertIn(" INNER JOIN ", str(qs.query))

    def test_ticket_21376(self):
        """

        Tests the database query optimization for a complex filter scenario.

        This test case verifies that the ORM correctly generates a LEFT OUTER JOIN
        when filtering on a related object. The test setup involves creating instances
        of ObjectA and ObjectC, and then querying ObjectC with a filter that includes
        optional related objects (ObjectB). The test asserts that the resulting query
        uses a LEFT OUTER JOIN and returns the expected number of results.

        The test covers the following scenarios:
        - Creating objects with relationships
        - Querying with complex filters involving related objects
        - Verifying the generated SQL query for correctness

        """
        a = ObjectA.objects.create()
        ObjectC.objects.create(objecta=a)
        qs = ObjectC.objects.filter(
            Q(objecta=a) | Q(objectb__objecta=a),
        )
        qs = qs.filter(
            Q(objectb=1) | Q(objecta=a),
        )
        self.assertEqual(qs.count(), 1)
        tblname = connection.ops.quote_name(ObjectB._meta.db_table)
        self.assertIn(" LEFT OUTER JOIN %s" % tblname, str(qs.query))


class ForeignKeyToBaseExcludeTests(TestCase):
    def test_ticket_21787(self):
        sc1 = SpecialCategory.objects.create(special_name="sc1", name="sc1")
        sc2 = SpecialCategory.objects.create(special_name="sc2", name="sc2")
        sc3 = SpecialCategory.objects.create(special_name="sc3", name="sc3")
        c1 = CategoryItem.objects.create(category=sc1)
        CategoryItem.objects.create(category=sc2)
        self.assertSequenceEqual(
            SpecialCategory.objects.exclude(categoryitem__id=c1.pk).order_by("name"),
            [sc2, sc3],
        )
        self.assertSequenceEqual(
            SpecialCategory.objects.filter(categoryitem__id=c1.pk), [sc1]
        )


class ReverseM2MCustomPkTests(TestCase):
    def test_ticket_21879(self):
        """

        Tests the correct relationship between CustomPk and CustomPkTag models.

        Verifies that a CustomPkTag is correctly associated with a CustomPk instance and 
        vice versa, ensuring that the many-to-one relationship is properly established.

        The test creates a CustomPkTag and a CustomPk instance, associates them, and 
        then checks that filtering by the tag returns the correct CustomPk instance and 
        filtering by the CustomPk instance returns the correct CustomPkTag instance.

        """
        cpt1 = CustomPkTag.objects.create(id="cpt1", tag="cpt1")
        cp1 = CustomPk.objects.create(name="cp1", extra="extra")
        cp1.custompktag_set.add(cpt1)
        self.assertSequenceEqual(CustomPk.objects.filter(custompktag=cpt1), [cp1])
        self.assertSequenceEqual(CustomPkTag.objects.filter(custom_pk=cp1), [cpt1])


class Ticket22429Tests(TestCase):
    def test_ticket_22429(self):
        """

        Tests that the queryset of students who are not enrolled in a classroom of their own school is correctly filtered.

        This test case creates two schools, each with a student, and a classroom in the first school with the first student enrolled.
        It then checks that the student from the second school, who is not enrolled in a classroom of their own school, is correctly returned in the queryset.

        """
        sc1 = School.objects.create()
        st1 = Student.objects.create(school=sc1)

        sc2 = School.objects.create()
        st2 = Student.objects.create(school=sc2)

        cr = Classroom.objects.create(school=sc1)
        cr.students.add(st1)

        queryset = Student.objects.filter(~Q(classroom__school=F("school")))
        self.assertSequenceEqual(queryset, [st2])


class Ticket23605Tests(TestCase):
    def test_ticket_23605(self):
        # Test filtering on a complicated q-object from ticket's report.
        # The query structure is such that we have multiple nested subqueries.
        # The original problem was that the inner queries weren't relabeled
        # correctly.
        # See also #24090.
        """
        ..: 
            Tests a specific query on the Ticket23605A model.

            This test case verifies the correctness of a complex Django ORM query involving 
            multiple models (Ticket23605A, Ticket23605B, and Ticket23605C) with specific 
            conditions, filters, and lookups. It ensures that the query properly handles 
            relationships between models, uses of Q objects, and exclusion of certain 
            conditions. The test creates instances of the relevant models, constructs a 
            complex query, and then asserts that the query returns the expected results 
            when applied to the model instances.
        """
        a1 = Ticket23605A.objects.create()
        a2 = Ticket23605A.objects.create()
        c1 = Ticket23605C.objects.create(field_c0=10000.0)
        Ticket23605B.objects.create(
            field_b0=10000.0, field_b1=True, modelc_fk=c1, modela_fk=a1
        )
        complex_q = Q(
            pk__in=Ticket23605A.objects.filter(
                Q(
                    # True for a1 as field_b0 = 10000, field_c0=10000
                    # False for a2 as no ticket23605b found
                    ticket23605b__field_b0__gte=1000000
                    / F("ticket23605b__modelc_fk__field_c0")
                )
                &
                # True for a1 (field_b1=True)
                Q(ticket23605b__field_b1=True)
                & ~Q(
                    ticket23605b__pk__in=Ticket23605B.objects.filter(
                        ~(
                            # Same filters as above commented filters, but
                            # double-negated (one for Q() above, one for
                            # parentheses). So, again a1 match, a2 not.
                            Q(field_b1=True)
                            & Q(field_b0__gte=1000000 / F("modelc_fk__field_c0"))
                        )
                    )
                )
            ).filter(ticket23605b__field_b1=True)
        )
        qs1 = Ticket23605A.objects.filter(complex_q)
        self.assertSequenceEqual(qs1, [a1])
        qs2 = Ticket23605A.objects.exclude(complex_q)
        self.assertSequenceEqual(qs2, [a2])


class TestTicket24279(TestCase):
    def test_ticket_24278(self):
        """
        Tests an edge case for filtering School objects.

        Verifies that if no primary keys are specified to filter on and no additional
        conditions are provided, an empty queryset is returned, indicating no schools
        match the given criteria. This ensures the correct handling of empty filters
        and conditional queries in the School model.

        Returns:
            None

        Raises:
            AssertionError: If the queryset is not empty when filtering with no conditions.

        """
        School.objects.create()
        qs = School.objects.filter(Q(pk__in=()) | Q())
        self.assertSequenceEqual(qs, [])


class TestInvalidValuesRelation(SimpleTestCase):
    def test_invalid_values(self):
        """

        Tests that the Annotation.objects.filter method correctly raises a ValueError 
        when provided with invalid values for the 'id' field, specifically when a string 
        is passed instead of a number. The test checks both a single invalid value and 
        a list of values containing an invalid string. 

        """
        msg = "Field 'id' expected a number but got 'abc'."
        with self.assertRaisesMessage(ValueError, msg):
            Annotation.objects.filter(tag="abc")
        with self.assertRaisesMessage(ValueError, msg):
            Annotation.objects.filter(tag__in=[123, "abc"])


class TestTicket24605(TestCase):
    def test_ticket_24605(self):
        """
        Subquery table names should be quoted.
        """
        i1 = Individual.objects.create(alive=True)
        RelatedIndividual.objects.create(related=i1)
        i2 = Individual.objects.create(alive=False)
        RelatedIndividual.objects.create(related=i2)
        i3 = Individual.objects.create(alive=True)
        i4 = Individual.objects.create(alive=False)

        self.assertSequenceEqual(
            Individual.objects.filter(
                Q(alive=False), Q(related_individual__isnull=True)
            ),
            [i4],
        )
        self.assertSequenceEqual(
            Individual.objects.exclude(
                Q(alive=False), Q(related_individual__isnull=True)
            ).order_by("pk"),
            [i1, i2, i3],
        )


class Ticket23622Tests(TestCase):
    @skipUnlessDBFeature("can_distinct_on_fields")
    def test_ticket_23622(self):
        """
        Make sure __pk__in and __in work the same for related fields when
        using a distinct on subquery.
        """
        a1 = Ticket23605A.objects.create()
        a2 = Ticket23605A.objects.create()
        c1 = Ticket23605C.objects.create(field_c0=0.0)
        Ticket23605B.objects.create(
            modela_fk=a1,
            field_b0=123,
            field_b1=True,
            modelc_fk=c1,
        )
        Ticket23605B.objects.create(
            modela_fk=a1,
            field_b0=23,
            field_b1=True,
            modelc_fk=c1,
        )
        Ticket23605B.objects.create(
            modela_fk=a1,
            field_b0=234,
            field_b1=True,
            modelc_fk=c1,
        )
        Ticket23605B.objects.create(
            modela_fk=a1,
            field_b0=12,
            field_b1=True,
            modelc_fk=c1,
        )
        Ticket23605B.objects.create(
            modela_fk=a2,
            field_b0=567,
            field_b1=True,
            modelc_fk=c1,
        )
        Ticket23605B.objects.create(
            modela_fk=a2,
            field_b0=76,
            field_b1=True,
            modelc_fk=c1,
        )
        Ticket23605B.objects.create(
            modela_fk=a2,
            field_b0=7,
            field_b1=True,
            modelc_fk=c1,
        )
        Ticket23605B.objects.create(
            modela_fk=a2,
            field_b0=56,
            field_b1=True,
            modelc_fk=c1,
        )
        qx = Q(
            ticket23605b__pk__in=Ticket23605B.objects.order_by(
                "modela_fk", "-field_b1"
            ).distinct("modela_fk")
        ) & Q(ticket23605b__field_b0__gte=300)
        qy = Q(
            ticket23605b__in=Ticket23605B.objects.order_by(
                "modela_fk", "-field_b1"
            ).distinct("modela_fk")
        ) & Q(ticket23605b__field_b0__gte=300)
        self.assertEqual(
            set(Ticket23605A.objects.filter(qx).values_list("pk", flat=True)),
            set(Ticket23605A.objects.filter(qy).values_list("pk", flat=True)),
        )
        self.assertSequenceEqual(Ticket23605A.objects.filter(qx), [a2])
