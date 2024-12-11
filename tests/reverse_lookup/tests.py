from django.core.exceptions import FieldError
from django.test import TestCase

from .models import Choice, Poll, User


class ReverseLookupTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Set up test data for the application, including users and polls.

        This method creates two users, John Doe and Jim Bo, and two polls, one created by each user.
        It also creates a choice that relates the two polls, providing a basic setup for testing poll functionality.

        The test data includes:
            - Two users with names John Doe and Jim Bo
            - Two polls with questions \"What's the first question?\" and \"What's the second question?\"
            - A choice that connects the two polls, providing an example of a related poll answer.

        This data is intended to be used as a foundation for further testing and can be extended or modified as needed to support specific test cases.
        """
        john = User.objects.create(name="John Doe")
        jim = User.objects.create(name="Jim Bo")
        first_poll = Poll.objects.create(
            question="What's the first question?", creator=john
        )
        second_poll = Poll.objects.create(
            question="What's the second question?", creator=jim
        )
        Choice.objects.create(
            poll=first_poll, related_poll=second_poll, name="This is the answer."
        )

    def test_reverse_by_field(self):
        u1 = User.objects.get(poll__question__exact="What's the first question?")
        self.assertEqual(u1.name, "John Doe")

        u2 = User.objects.get(poll__question__exact="What's the second question?")
        self.assertEqual(u2.name, "Jim Bo")

    def test_reverse_by_related_name(self):
        """

        Tests the reverse relationship of the Poll model.

        Verifies that a Poll instance can be retrieved from the related Choice instance,
        both by the standard 'poll_choice' attribute and the 'related_choice' attribute,
        and that the resulting Poll instance has the expected question.

        The test covers two cases, ensuring that the correct poll is retrieved regardless
        of the related choice used. The test assumes the presence of specific poll choices
        and questions in the database.

        """
        p1 = Poll.objects.get(poll_choice__name__exact="This is the answer.")
        self.assertEqual(p1.question, "What's the first question?")

        p2 = Poll.objects.get(related_choice__name__exact="This is the answer.")
        self.assertEqual(p2.question, "What's the second question?")

    def test_reverse_field_name_disallowed(self):
        """
        If a related_name is given you can't use the field name instead
        """
        msg = (
            "Cannot resolve keyword 'choice' into field. Choices are: "
            "creator, creator_id, id, poll_choice, question, related_choice"
        )
        with self.assertRaisesMessage(FieldError, msg):
            Poll.objects.get(choice__name__exact="This is the answer")
