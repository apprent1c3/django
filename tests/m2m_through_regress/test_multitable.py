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
        result = self.chris.event_set.all()
        self.assertCountEqual(result, [self.event])

    def test_m2m_query_proxied(self):
        result = self.event.special_people.all()
        self.assertCountEqual(result, [self.chris, self.dan])

    def test_m2m_reverse_query_proxied(self):
        result = self.chris.special_event_set.all()
        self.assertCountEqual(result, [self.event])

    def test_m2m_prefetch_proxied(self):
        """

        Test case for Many-To-Many (M2M) prefetching of proxied relationships.

        Verifies that prefetching related objects for an Event instance works correctly,
        and that the results are returned in an efficient manner, minimizing database queries.

        Specifically, checks that the 'special_people' relationship is correctly prefetched
        for an Event instance with a given name, and that the expected individuals are
        associated with the event.

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
        """
        Test the efficiency of prefetching related objects in a many-to-many relationship in the reverse direction, specifically when the relationship is proxied.

        This test case checks that when fetching a Person object, it can efficiently retrieve the associated special events using prefetch_related, and verifies that the correct events are returned. It also ensures that the query is executed within the expected number of database queries.
        """
        result = Person.objects.filter(name="Dan").prefetch_related("special_event_set")
        with self.assertNumQueries(2):
            self.assertCountEqual(result, [self.dan])
            self.assertEqual(
                [event.name for event in result[0].special_event_set.all()],
                ["Exposition Match"],
            )
