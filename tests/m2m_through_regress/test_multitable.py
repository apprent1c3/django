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
        """

        Tests the many-to-many query for event team membership.

        Verifies that the teams associated with a given event are correctly retrieved.
        In this case, it checks that the event is associated with exactly one team,
        which is the team alpha, and that no other teams are returned.

        """
        result = self.event.teams.all()
        self.assertCountEqual(result, [self.team_alpha])

    def test_m2m_reverse_query(self):
        """
        Tests the reverse query for a many-to-many relationship.

        Verifies that the inverse relationship from the related object to the original object 
        works as expected, by checking that the result of the reverse query matches the 
        expected related object.

        Note: This test case ensures data consistency and correct setup of many-to-many 
        relationships in the application's data model.
        """
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

        Tests the prefetching of proxied many-to-many relationships in the Event model.

        This test ensures that the special_people related objects are correctly prefetched
        when the Event objects are retrieved from the database, reducing the number of database queries.
        It verifies that the results match the expected Event and that the prefetched special_people
        objects are returned in the correct order.

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
