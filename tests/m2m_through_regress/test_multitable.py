from django.test import TestCase

from .models import (
    CompetingTeam,
    Event,
    Group,
    IndividualCompetitor,
    Membership,
    Person,
)


class MultiTableTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = Person.objects.create(name="Alice")
        cls.bob = Person.objects.create(name="Bob")
        cls.chris = Person.objects.create(name="Chris")
        cls.dan = Person.objects.create(name="Dan")
        cls.team_alpha = Group.objects.create(name="Alpha")
        Membership.objects.create(person=cls.alice, group=cls.team_alpha)
        Membership.objects.create(person=cls.bob, group=cls.team_alpha)
        cls.event = Event.objects.create(name="Exposition Match")
        IndividualCompetitor.objects.create(event=cls.event, person=cls.chris)
        IndividualCompetitor.objects.create(event=cls.event, person=cls.dan)
        CompetingTeam.objects.create(event=cls.event, team=cls.team_alpha)

    def test_m2m_query(self):
        result = self.event.teams.all()
        self.assertCountEqual(result, [self.team_alpha])

    def test_m2m_reverse_query(self):
        """
        Tests the reverse query for many-to-many relationship in the Chris model.

        Verifies that the event_set attribute of a Chris instance correctly retrieves
        the associated events, and that the result matches the expected event.

        This test case ensures data consistency and validates the functionality of
        the many-to-many relationship between Chris and Event models.
        """
        result = self.chris.event_set.all()
        self.assertCountEqual(result, [self.event])

    def test_m2m_query_proxied(self):
        result = self.event.special_people.all()
        self.assertCountEqual(result, [self.chris, self.dan])

    def test_m2m_reverse_query_proxied(self):
        """
        Tests the many-to-many reverse query with a proxied relation.

        This test case verifies that the special event set associated with a given object can be successfully queried and that the result matches the expected event.

        It checks that the count of events in the result set is equal to one and that the single event in the result set is the expected event, ensuring the proxy relation is correctly established and queried.

        Raises:
            AssertionError: If the count of events in the result set is not equal to one or if the event in the result set does not match the expected event.

        """
        result = self.chris.special_event_set.all()
        self.assertCountEqual(result, [self.event])

    def test_m2m_prefetch_proxied(self):
        """

        Tests the m2m prefetching functionality through a proxied relationship.

        Verifies that the correct results are retrieved from the database when using
        prefetch_related on a many-to-many relationship. The test checks that the query
        is executed efficiently and that the correct data is returned. Specifically,
        it ensures that the Event object with the name 'Exposition Match' is retrieved,
        and that its associated 'special_people' are correctly prefetched, containing
        the expected individuals.

        """
        result = Event.objects.filter(name="Exposition Match").prefetch_related(
            "special_people"
        )
        with self.assertNumQueries(2):
            self.assertCountEqual(result, [self.event])
            self.assertEqual(
                sorted(p.name for p in result[0].special_people.all()), ["Chris", "Dan"]
            )

    def test_m2m_prefetch_reverse_proxied(self):
        result = Person.objects.filter(name="Dan").prefetch_related("special_event_set")
        with self.assertNumQueries(2):
            self.assertCountEqual(result, [self.dan])
            self.assertEqual(
                [event.name for event in result[0].special_event_set.all()],
                ["Exposition Match"],
            )
