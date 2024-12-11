"""
The tests are shared with contenttypes_tests and so shouldn't import or
reference any models directly. Subclasses should inherit django.test.TestCase.
"""

from operator import attrgetter


class BaseOrderWithRespectToTests:
    databases = {"default", "other"}

    # Hook to allow subclasses to run these tests with alternate models.
    Answer = None
    Post = None
    Question = None

    @classmethod
    def setUpTestData(cls):
        """
        Set up test data for the class, creating a question and associated answers.

        This class method is used to establish a baseline for testing, populating the
        database with a specific question and its corresponding answer options. The
        question created is \"Which Beatle starts with the letter 'R'?\" with four possible
        answers: John, Paul, George, and Ringo. This setup allows for more efficient and
        consistent testing of the class's functionality with a predefined set of data.
        """
        cls.q1 = cls.Question.objects.create(
            text="Which Beatle starts with the letter 'R'?"
        )
        cls.Answer.objects.create(text="John", question=cls.q1)
        cls.Answer.objects.create(text="Paul", question=cls.q1)
        cls.Answer.objects.create(text="George", question=cls.q1)
        cls.Answer.objects.create(text="Ringo", question=cls.q1)

    def test_default_to_insertion_order(self):
        # Answers will always be ordered in the order they were inserted.
        self.assertQuerySetEqual(
            self.q1.answer_set.all(),
            [
                "John",
                "Paul",
                "George",
                "Ringo",
            ],
            attrgetter("text"),
        )

    def test_previous_and_next_in_order(self):
        # We can retrieve the answers related to a particular object, in the
        # order they were created, once we have a particular object.
        """

        Tests the correct ordering and navigation of answers within a question.

        This test case verifies that answers are properly ordered and that the 
        get_next_in_order and get_previous_in_order methods correctly return the 
        adjacent answers in the sequence. Specifically, it checks that the first 
        answer's next answer is correctly identified, and the last answer's previous 
        answer is correctly identified.

        """
        a1 = self.q1.answer_set.all()[0]
        self.assertEqual(a1.text, "John")
        self.assertEqual(a1.get_next_in_order().text, "Paul")

        a2 = list(self.q1.answer_set.all())[-1]
        self.assertEqual(a2.text, "Ringo")
        self.assertEqual(a2.get_previous_in_order().text, "George")

    def test_item_ordering(self):
        # We can retrieve the ordering of the queryset from a particular item.
        a1 = self.q1.answer_set.all()[1]
        id_list = [o.pk for o in self.q1.answer_set.all()]
        self.assertSequenceEqual(a1.question.get_answer_order(), id_list)

        # It doesn't matter which answer we use to check the order, it will
        # always be the same.
        a2 = self.Answer.objects.create(text="Number five", question=self.q1)
        self.assertEqual(
            list(a1.question.get_answer_order()), list(a2.question.get_answer_order())
        )

    def test_set_order_unrelated_object(self):
        """An answer that's not related isn't updated."""
        q = self.Question.objects.create(text="other")
        a = self.Answer.objects.create(text="Number five", question=q)
        self.q1.set_answer_order([o.pk for o in self.q1.answer_set.all()] + [a.pk])
        self.assertEqual(self.Answer.objects.get(pk=a.pk)._order, 0)

    def test_change_ordering(self):
        # The ordering can be altered
        """
        Tests the functionality of changing the ordering of answers for a given question.

        This test case covers the creation of an answer, adjustment of the answer order, 
        and verification that the updated order is correctly reflected in the answer set. 

        It checks for the correct implementation of the `set_answer_order` method and 
        the `get_answer_order` method, ensuring that the answer order is updated as expected. 

        The test scenario involves moving an answer to a different position in the order, 
        then asserting that the resulting answer set matches the expected order. 

        This test is crucial for ensuring the correct functionality of the answer ordering 
        mechanism in the application.
        """
        a = self.Answer.objects.create(text="Number five", question=self.q1)

        # Swap the last two items in the order list
        id_list = [o.pk for o in self.q1.answer_set.all()]
        x = id_list.pop()
        id_list.insert(-1, x)

        # By default, the ordering is different from the swapped version
        self.assertNotEqual(list(a.question.get_answer_order()), id_list)

        # Change the ordering to the swapped version -
        # this changes the ordering of the queryset.
        a.question.set_answer_order(id_list)
        self.assertQuerySetEqual(
            self.q1.answer_set.all(),
            ["John", "Paul", "George", "Number five", "Ringo"],
            attrgetter("text"),
        )

    def test_recursive_ordering(self):
        p1 = self.Post.objects.create(title="1")
        p2 = self.Post.objects.create(title="2")
        p1_1 = self.Post.objects.create(title="1.1", parent=p1)
        p1_2 = self.Post.objects.create(title="1.2", parent=p1)
        self.Post.objects.create(title="2.1", parent=p2)
        p1_3 = self.Post.objects.create(title="1.3", parent=p1)
        self.assertSequenceEqual(p1.get_post_order(), [p1_1.pk, p1_2.pk, p1_3.pk])

    def test_delete_and_insert(self):
        q1 = self.Question.objects.create(text="What is your favorite color?")
        q2 = self.Question.objects.create(text="What color is it?")
        a1 = self.Answer.objects.create(text="Blue", question=q1)
        a2 = self.Answer.objects.create(text="Red", question=q1)
        a3 = self.Answer.objects.create(text="Green", question=q1)
        a4 = self.Answer.objects.create(text="Yellow", question=q1)
        self.assertSequenceEqual(q1.answer_set.all(), [a1, a2, a3, a4])
        a3.question = q2
        a3.save()
        a1.delete()
        new_answer = self.Answer.objects.create(text="Black", question=q1)
        self.assertSequenceEqual(q1.answer_set.all(), [a2, a4, new_answer])

    def test_database_routing(self):
        class WriteToOtherRouter:
            def db_for_write(self, model, **hints):
                return "other"

        with self.settings(DATABASE_ROUTERS=[WriteToOtherRouter()]):
            with (
                self.assertNumQueries(0, using="default"),
                self.assertNumQueries(
                    1,
                    using="other",
                ),
            ):
                self.q1.set_answer_order([3, 1, 2, 4])
