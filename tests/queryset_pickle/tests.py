import datetime
import pickle

import django
from django.db import models
from django.test import TestCase

from .models import (
    BinaryFieldModel,
    Container,
    Event,
    Group,
    Happening,
    M2MModel,
    MyEvent,
)


class PickleabilityTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.happening = (
            Happening.objects.create()
        )  # make sure the defaults are working (#20158)

    def assert_pickles(self, qs):
        self.assertEqual(list(pickle.loads(pickle.dumps(qs))), list(qs))

    def test_binaryfield(self):
        BinaryFieldModel.objects.create(data=b"binary data")
        self.assert_pickles(BinaryFieldModel.objects.all())

    def test_related_field(self):
        g = Group.objects.create(name="Ponies Who Own Maybachs")
        self.assert_pickles(Event.objects.filter(group=g.id))

    def test_datetime_callable_default_all(self):
        self.assert_pickles(Happening.objects.all())

    def test_datetime_callable_default_filter(self):
        self.assert_pickles(Happening.objects.filter(when=datetime.datetime.now()))

    def test_string_as_default(self):
        self.assert_pickles(Happening.objects.filter(name="test"))

    def test_standalone_method_as_default(self):
        self.assert_pickles(Happening.objects.filter(number1=1))

    def test_staticmethod_as_default(self):
        self.assert_pickles(Happening.objects.filter(number2=1))

    def test_filter_reverse_fk(self):
        self.assert_pickles(Group.objects.filter(event=1))

    def test_doesnotexist_exception(self):
        # Ticket #17776
        original = Event.DoesNotExist("Doesn't exist")
        unpickled = pickle.loads(pickle.dumps(original))

        # Exceptions are not equal to equivalent instances of themselves, so
        # can't just use assertEqual(original, unpickled)
        self.assertEqual(original.__class__, unpickled.__class__)
        self.assertEqual(original.args, unpickled.args)

    def test_doesnotexist_class(self):
        klass = Event.DoesNotExist
        self.assertIs(pickle.loads(pickle.dumps(klass)), klass)

    def test_multipleobjectsreturned_class(self):
        klass = Event.MultipleObjectsReturned
        self.assertIs(pickle.loads(pickle.dumps(klass)), klass)

    def test_forward_relatedobjectdoesnotexist_class(self):
        # ForwardManyToOneDescriptor
        klass = Event.group.RelatedObjectDoesNotExist
        self.assertIs(pickle.loads(pickle.dumps(klass)), klass)
        # ForwardOneToOneDescriptor
        klass = Happening.event.RelatedObjectDoesNotExist
        self.assertIs(pickle.loads(pickle.dumps(klass)), klass)

    def test_reverse_one_to_one_relatedobjectdoesnotexist_class(self):
        klass = Event.happening.RelatedObjectDoesNotExist
        self.assertIs(pickle.loads(pickle.dumps(klass)), klass)

    def test_manager_pickle(self):
        pickle.loads(pickle.dumps(Happening.objects))

    def test_model_pickle(self):
        """
        A model not defined on module level is picklable.
        """
        original = Container.SomeModel(pk=1)
        dumped = pickle.dumps(original)
        reloaded = pickle.loads(dumped)
        self.assertEqual(original, reloaded)
        # Also, deferred dynamic model works
        Container.SomeModel.objects.create(somefield=1)
        original = Container.SomeModel.objects.defer("somefield")[0]
        dumped = pickle.dumps(original)
        reloaded = pickle.loads(dumped)
        self.assertEqual(original, reloaded)
        self.assertEqual(original.somefield, reloaded.somefield)

    def test_model_pickle_m2m(self):
        """
        Test intentionally the automatically created through model.
        """
        m1 = M2MModel.objects.create()
        g1 = Group.objects.create(name="foof")
        m1.groups.add(g1)
        m2m_through = M2MModel._meta.get_field("groups").remote_field.through
        original = m2m_through.objects.get()
        dumped = pickle.dumps(original)
        reloaded = pickle.loads(dumped)
        self.assertEqual(original, reloaded)

    def test_model_pickle_dynamic(self):
        """
        Tests the ability to pickle and unpickle a dynamically created subclass of Event, ensuring that the original and reloaded instances are equal and the class type is preserved.
        """
        class Meta:
            proxy = True

        dynclass = type(
            "DynamicEventSubclass",
            (Event,),
            {"Meta": Meta, "__module__": Event.__module__},
        )
        original = dynclass(pk=1)
        dumped = pickle.dumps(original)
        reloaded = pickle.loads(dumped)
        self.assertEqual(original, reloaded)
        self.assertIs(reloaded.__class__, dynclass)

    def test_specialized_queryset(self):
        self.assert_pickles(Happening.objects.values("name"))
        self.assert_pickles(Happening.objects.values("name").dates("when", "year"))
        # With related field (#14515)
        self.assert_pickles(
            Event.objects.select_related("group")
            .order_by("title")
            .values_list("title", "group__name")
        )

    def test_pickle_prefetch_related_idempotence(self):
        """
        Tests that prefetching related objects in a QuerySet remains idempotent after pickling and unpickling, ensuring the same results are returned each time the pickled QuerySet is loaded.
        """
        g = Group.objects.create(name="foo")
        groups = Group.objects.prefetch_related("event_set")

        # First pickling
        groups = pickle.loads(pickle.dumps(groups))
        self.assertSequenceEqual(groups, [g])

        # Second pickling
        groups = pickle.loads(pickle.dumps(groups))
        self.assertSequenceEqual(groups, [g])

    def test_pickle_prefetch_queryset_usable_outside_of_prefetch(self):
        # Prefetch shouldn't affect the fetch-on-pickle behavior of the
        # queryset passed to it.
        """
        Tests if a prefetched queryset remains usable outside of its prefetch context after pickling and unpickling, ensuring that no additional database queries are executed when its results are accessed.
        """
        Group.objects.create(name="foo")
        events = Event.objects.order_by("id")
        Group.objects.prefetch_related(models.Prefetch("event_set", queryset=events))
        with self.assertNumQueries(1):
            events2 = pickle.loads(pickle.dumps(events))
        with self.assertNumQueries(0):
            list(events2)

    def test_pickle_prefetch_queryset_still_usable(self):
        g = Group.objects.create(name="foo")
        groups = Group.objects.prefetch_related(
            models.Prefetch("event_set", queryset=Event.objects.order_by("id"))
        )
        groups2 = pickle.loads(pickle.dumps(groups))
        self.assertSequenceEqual(groups2.filter(id__gte=0), [g])

    def test_pickle_prefetch_queryset_not_evaluated(self):
        """
        Tests that a prefetched queryset is not re-evaluated when pickled and unpickled, ensuring that the queryset cache is preserved, thus avoiding additional database queries.
        """
        Group.objects.create(name="foo")
        groups = Group.objects.prefetch_related(
            models.Prefetch("event_set", queryset=Event.objects.order_by("id"))
        )
        list(groups)  # evaluate QuerySet
        with self.assertNumQueries(0):
            pickle.loads(pickle.dumps(groups))

    def test_pickle_prefetch_related_with_m2m_and_objects_deletion(self):
        """
        #24831 -- Cached properties on ManyToOneRel created in QuerySet.delete()
        caused subsequent QuerySet pickling to fail.
        """
        g = Group.objects.create(name="foo")
        m2m = M2MModel.objects.create()
        m2m.groups.add(g)
        Group.objects.all().delete()

        m2ms = M2MModel.objects.prefetch_related("groups")
        m2ms = pickle.loads(pickle.dumps(m2ms))
        self.assertSequenceEqual(m2ms, [m2m])

    def test_pickle_boolean_expression_in_Q__queryset(self):
        """

        Tests the functionality of pickling a QuerySet that filters groups based on the existence of related events.
        Verifies that the pickled QuerySet returns the same results as the original when unpickled.

        """
        group = Group.objects.create(name="group")
        Event.objects.create(title="event", group=group)
        groups = Group.objects.filter(
            models.Q(
                models.Exists(
                    Event.objects.filter(group_id=models.OuterRef("id")),
                )
            ),
        )
        groups2 = pickle.loads(pickle.dumps(groups))
        self.assertSequenceEqual(groups2, [group])

    def test_pickle_exists_queryset_still_usable(self):
        """
        Tests that a queryset remains usable after being pickled and unpickled, specifically when using annotation with exists subquery.
        """
        group = Group.objects.create(name="group")
        Event.objects.create(title="event", group=group)
        groups = Group.objects.annotate(
            has_event=models.Exists(
                Event.objects.filter(group_id=models.OuterRef("id")),
            ),
        )
        groups2 = pickle.loads(pickle.dumps(groups))
        self.assertSequenceEqual(groups2.filter(has_event=True), [group])

    def test_pickle_exists_queryset_not_evaluated(self):
        """
        Tests that a queryset with an Exists annotation can be pickled without triggering additional database queries after the initial evaluation.
        """
        group = Group.objects.create(name="group")
        Event.objects.create(title="event", group=group)
        groups = Group.objects.annotate(
            has_event=models.Exists(
                Event.objects.filter(group_id=models.OuterRef("id")),
            ),
        )
        list(groups)  # evaluate QuerySet.
        with self.assertNumQueries(0):
            self.assert_pickles(groups)

    def test_pickle_exists_kwargs_queryset_not_evaluated(self):
        """
        Tests that a queryset with Exists annotation can be pickled, without causing additional database queries.
        """
        group = Group.objects.create(name="group")
        Event.objects.create(title="event", group=group)
        groups = Group.objects.annotate(
            has_event=models.Exists(
                queryset=Event.objects.filter(group_id=models.OuterRef("id")),
            ),
        )
        list(groups)  # evaluate QuerySet.
        with self.assertNumQueries(0):
            self.assert_pickles(groups)

    def test_pickle_subquery_queryset_not_evaluated(self):
        """
        Tests that a queryset with a subquery annotation is not evaluated when pickled, 
        preventing unnecessary database queries during the unpickling process.
        """
        group = Group.objects.create(name="group")
        Event.objects.create(title="event", group=group)
        groups = Group.objects.annotate(
            event_title=models.Subquery(
                Event.objects.filter(group_id=models.OuterRef("id")).values("title"),
            ),
        )
        list(groups)  # evaluate QuerySet.
        with self.assertNumQueries(0):
            self.assert_pickles(groups)

    def test_pickle_filteredrelation(self):
        """

        Test that a FilteredRelation can be pickled and loaded without losing its annotation.

        """
        group = Group.objects.create(name="group")
        event_1 = Event.objects.create(title="Big event", group=group)
        event_2 = Event.objects.create(title="Small event", group=group)
        Happening.objects.bulk_create(
            [
                Happening(event=event_1, number1=5),
                Happening(event=event_2, number1=3),
            ]
        )
        groups = Group.objects.annotate(
            big_events=models.FilteredRelation(
                "event",
                condition=models.Q(event__title__startswith="Big"),
            ),
        ).annotate(sum_number=models.Sum("big_events__happening__number1"))
        groups_query = pickle.loads(pickle.dumps(groups.query))
        groups = Group.objects.all()
        groups.query = groups_query
        self.assertEqual(groups.get().sum_number, 5)

    def test_pickle_filteredrelation_m2m(self):
        """

        Tests the pickling and unpickling of a Django ORM query that uses a FilteredRelation
        to annotate a model, ensuring that the filtered relation and subsequent aggregations are properly preserved.

        """
        group = Group.objects.create(name="group")
        m2mmodel = M2MModel.objects.create(added=datetime.date(2020, 1, 1))
        m2mmodel.groups.add(group)
        groups = Group.objects.annotate(
            first_m2mmodels=models.FilteredRelation(
                "m2mmodel",
                condition=models.Q(m2mmodel__added__year=2020),
            ),
        ).annotate(count_groups=models.Count("first_m2mmodels__groups"))
        groups_query = pickle.loads(pickle.dumps(groups.query))
        groups = Group.objects.all()
        groups.query = groups_query
        self.assertEqual(groups.get().count_groups, 1)

    def test_annotation_with_callable_default(self):
        # Happening.when has a callable default of datetime.datetime.now.
        qs = Happening.objects.annotate(latest_time=models.Max("when"))
        self.assert_pickles(qs)

    def test_annotation_values(self):
        qs = Happening.objects.values("name").annotate(latest_time=models.Max("when"))
        reloaded = Happening.objects.all()
        reloaded.query = pickle.loads(pickle.dumps(qs.query))
        self.assertEqual(
            reloaded.get(),
            {"name": "test", "latest_time": self.happening.when},
        )

    def test_annotation_values_list(self):
        # values_list() is reloaded to values() when using a pickled query.
        """
        enslies to test whether Annotation values lists can be properly pickled and unpickled to store and retrieve query results from the database, ensuring data integrity by comparing reloaded query results with expected values.
        """
        tests = [
            Happening.objects.values_list("name"),
            Happening.objects.values_list("name", flat=True),
            Happening.objects.values_list("name", named=True),
        ]
        for qs in tests:
            with self.subTest(qs._iterable_class.__name__):
                reloaded = Happening.objects.all()
                reloaded.query = pickle.loads(pickle.dumps(qs.query))
                self.assertEqual(reloaded.get(), {"name": "test"})

    def test_filter_deferred(self):
        qs = Happening.objects.all()
        qs._defer_next_filter = True
        qs = qs.filter(id=0)
        self.assert_pickles(qs)

    def test_missing_django_version_unpickling(self):
        """
        #21430 -- Verifies a warning is raised for querysets that are
        unpickled without a Django version
        """
        qs = Group.missing_django_version_objects.all()
        msg = "Pickled queryset instance's Django version is not specified."
        with self.assertRaisesMessage(RuntimeWarning, msg):
            pickle.loads(pickle.dumps(qs))

    def test_unsupported_unpickle(self):
        """
        #21430 -- Verifies a warning is raised for querysets that are
        unpickled with a different Django version than the current
        """
        qs = Group.previous_django_version_objects.all()
        msg = (
            "Pickled queryset instance's Django version 1.0 does not match "
            "the current version %s." % django.__version__
        )
        with self.assertRaisesMessage(RuntimeWarning, msg):
            pickle.loads(pickle.dumps(qs))

    def test_order_by_model_with_abstract_inheritance_and_meta_ordering(self):
        group = Group.objects.create(name="test")
        event = MyEvent.objects.create(title="test event", group=group)
        event.edition_set.create()
        self.assert_pickles(event.edition_set.order_by("event"))


class InLookupTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for i in range(1, 3):
            group = Group.objects.create(name="Group {}".format(i))
        cls.e1 = Event.objects.create(title="Event 1", group=group)

    def test_in_lookup_queryset_evaluation(self):
        """
        Neither pickling nor unpickling a QuerySet.query with an __in=inner_qs
        lookup should evaluate inner_qs.
        """
        events = Event.objects.filter(group__in=Group.objects.all())

        with self.assertNumQueries(0):
            dumped = pickle.dumps(events.query)

        with self.assertNumQueries(0):
            reloaded = pickle.loads(dumped)
            reloaded_events = Event.objects.none()
            reloaded_events.query = reloaded

        self.assertSequenceEqual(reloaded_events, [self.e1])

    def test_in_lookup_query_evaluation(self):
        """
        Tests that an `Event` query using `in_lookup` can be pickled and reloaded without executing any database queries, and that the resulting events are correctly filtered.
        """
        events = Event.objects.filter(group__in=Group.objects.values("id").query)

        with self.assertNumQueries(0):
            dumped = pickle.dumps(events.query)

        with self.assertNumQueries(0):
            reloaded = pickle.loads(dumped)
            reloaded_events = Event.objects.none()
            reloaded_events.query = reloaded

        self.assertSequenceEqual(reloaded_events, [self.e1])
