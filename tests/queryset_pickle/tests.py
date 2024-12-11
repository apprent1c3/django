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
        """

        Tests the correct serialization of BinaryField data.

        Verifies that BinaryField data can be successfully pickled and unpickled,
        ensuring the integrity of binary data stored in the database. This test case
        covers the creation of a model instance with binary data and checks if the
        pickling process works as expected for all instances of the model.

        """
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
        """
        Tests that a DoesNotExist exception is properly pickled and unpickled, 
        preserving its class and arguments, to ensure the original exception information 
        is retained after serialization and deserialization.
        """
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
        """

        Tests that the MultipleObjectsReturned class from the Event module is successfully pickled and unpickled.

        Verifies that the class can be serialized and deserialized using pickle, ensuring its identity is preserved.

        """
        klass = Event.MultipleObjectsReturned
        self.assertIs(pickle.loads(pickle.dumps(klass)), klass)

    def test_forward_relatedobjectdoesnotexist_class(self):
        # ForwardManyToOneDescriptor
        """
        Tests the pickle serialization of RelatedObjectDoesNotExist classes.

        Checks that the RelatedObjectDoesNotExist classes from Event and Happening can be successfully pickled and unpickled without losing their identity.

        Verifies that the pickled and unpickled classes are equivalent to the originals, ensuring that the serialization process does not introduce any unexpected changes or errors.
        """
        klass = Event.group.RelatedObjectDoesNotExist
        self.assertIs(pickle.loads(pickle.dumps(klass)), klass)
        # ForwardOneToOneDescriptor
        klass = Happening.event.RelatedObjectDoesNotExist
        self.assertIs(pickle.loads(pickle.dumps(klass)), klass)

    def test_reverse_one_to_one_relatedobjectdoesnotexist_class(self):
        """

        Tests the serialization of the RelatedObjectDoesNotExist exception class for one-to-one related objects in the Event happening model.

        Verifies that the class can be successfully pickled and unpicled, ensuring that its identity is preserved after the serialization process.

        """
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

        Tests the ability to pickle and unpickle an instance of a dynamically created Event subclass.

        This test creates a dynamic subclass of Event, instantiates it, serializes it using pickle, 
        deserializes it, and then verifies that the original and reloaded instances are equal 
        and that the reloaded instance is of the correct class.

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
        Group.objects.create(name="foo")
        events = Event.objects.order_by("id")
        Group.objects.prefetch_related(models.Prefetch("event_set", queryset=events))
        with self.assertNumQueries(1):
            events2 = pickle.loads(pickle.dumps(events))
        with self.assertNumQueries(0):
            list(events2)

    def test_pickle_prefetch_queryset_still_usable(self):
        """

        Tests that a prefetched queryset is still usable after being pickled.

        This test checks if a queryset that has been prefetched using the `prefetch_related`
        method can be successfully pickled and unpickled without losing its functionality.
        It verifies that the unpickled queryset can still be filtered and returns the expected results.

        """
        g = Group.objects.create(name="foo")
        groups = Group.objects.prefetch_related(
            models.Prefetch("event_set", queryset=Event.objects.order_by("id"))
        )
        groups2 = pickle.loads(pickle.dumps(groups))
        self.assertSequenceEqual(groups2.filter(id__gte=0), [g])

    def test_pickle_prefetch_queryset_not_evaluated(self):
        """

        Tests whether a prefetched queryset is not evaluated when pickled and unpickled.

        This test case checks that using :func:`pickle.dumps` and :func:`pickle.loads` on a
        prefetched queryset does not trigger a database query. The prefetching is done using
        :func:`~django.db.models.QuerySet.prefetch_related` and :class:`~django.db.models.Prefetch`.
        The test ensures that the queryset remains unevaluated by checking that no queries are
        executed when the unpickled queryset is accessed.

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

        Tests the behavior of pickling a QuerySet that uses a boolean expression in a Django Q object.

        This test verifies that the resulting QuerySet remains unchanged after being pickled and unpickled, ensuring that the complex query is correctly serialized and deserialized.

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

        Tests that a QuerySet remains usable after being pickled and unpickled, 
        specifically when it has been annotated with an Exists aggregation.

        This function verifies that the pickling and unpickling process does not affect 
        the ability to filter the QuerySet based on the annotated field, ensuring 
        that the Results are as expected.

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
        Tests whether a queryset containing an Exists subquery can be pickled without evaluating the queryset.

        Checks that the pickling process does not trigger the evaluation of the queryset, 
        which would normally execute a database query, by ensuring no queries are executed 
        when the pickled queryset is accessed.

        This is a critical test as pickling a queryset that has not been evaluated is a common use case, 
        and ensuring it works correctly prevents unexpected database queries and potential performance issues.
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

        Tests that a queryset with Exists annotation and keyword arguments can be pickled without evaluating the underlying query.

        This test ensures that the pickling mechanism can handle querysets that use the Exists annotation with keyword arguments, 
        such as the 'group_id' in the filter clause. The test verifies that the queryset is pickled without triggering any additional 
        database queries, which is crucial for performance and efficiency.

        The test case involves creating a group and an event, then using the Exists annotation to filter groups that have associated events.
        The test then checks if the resulting queryset can be pickled without evaluating the underlying query, which is a key premise of querysets.

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

        Tests the serialization of a QuerySet that utilizes a FilteredRelation 
        to calculate the sum of a related field.

        The test creates a group with two events, each having a number of happenings. 
        It then creates a QuerySet that annotates the group with a filtered relation 
        to big events and calculates the sum of happenings for those big events. 
        The QuerySet is then pickled and unpickled to ensure that the filtered relation 
        is correctly serialized.

        The test asserts that the sum of happenings for the big events is correctly 
        calculated and retrieved after unpickling the QuerySet.

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

        Tests the pickling of filtered relation querysets on many-to-many fields.

        This test ensures that a queryset with a filtered relation can be pickled and
        unpickled without losing its filter conditions. The test creates a group and
        an M2M model instance, then annotates the group queryset with a filtered relation
        to count the number of M2M models added in the year 2020. The queryset is then
        pickled and unpickled, and the test asserts that the count is correctly applied.

        The test verifies the correct functioning of pickling on querysets with complex
        annotations, specifically those involving filtered relations on many-to-many fields.

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
        """
        Tests that a QuerySet with a deferred filter can be properly pickled.

        This test ensures that when a filter is applied to a QuerySet with deferred
        filtering enabled, the resulting QuerySet can be successfully serialized and
        deserialized using the pickle module.

        The test creates a QuerySet of all Happening objects, enables deferred filtering,
        and applies a filter to the QuerySet. It then asserts that the filtered QuerySet
        can be pickled without any issues.
        """
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
        """
        Tests the ordering of model instances using the 'order_by' method, 
        specifically with abstract inheritance and meta ordering.

        Ensures that the model instances can be correctly ordered and that 
        the resulting query is picklable, maintaining the expected ordering 
        even after serialization and deserialization. 
        The test scenario involves creating a group, an event, and an edition 
        associated with the event, and then verifying the ordering of the 
        edition set by the event attribute.
        """
        group = Group.objects.create(name="test")
        event = MyEvent.objects.create(title="test event", group=group)
        event.edition_set.create()
        self.assert_pickles(event.edition_set.order_by("event"))


class InLookupTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for the test class.

        This method creates two groups and one event associated with the last created group.
        The event is added to the test class as a class attribute for further use in tests.

        The resulting test data includes two groups named 'Group 1' and 'Group 2', and one event named 'Event 1' belonging to 'Group 2'.
        """
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

        Tests whether an ``in`` lookup query in a database query can be properly 
        evaluated, serialized, and deserialized without any additional database 
        queries.

        The test verifies that pickle serialization and deserialization of a 
         Django ORM query containing an ``in`` lookup does not trigger any 
        additional database queries during the process. Finally, it checks whether 
        the reloaded query yields the expected results.

        """
        events = Event.objects.filter(group__in=Group.objects.values("id").query)

        with self.assertNumQueries(0):
            dumped = pickle.dumps(events.query)

        with self.assertNumQueries(0):
            reloaded = pickle.loads(dumped)
            reloaded_events = Event.objects.none()
            reloaded_events.query = reloaded

        self.assertSequenceEqual(reloaded_events, [self.e1])
