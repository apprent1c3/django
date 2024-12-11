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
        Tests the functionality of retrieving the previous and next answers in order.

        This test case verifies that the :meth:`get_next_in_order` and :meth:`get_previous_in_order`
        methods of an answer object return the correct adjacent answers in a sequence.
        It checks that the answer objects are correctly ordered and that the methods
        return the expected answers based on their position in the sequence, handling
        both the case where an answer is at the beginning or end of the sequence, and
        where it is in the middle.

        The test case assumes the presence of a set of answers with known ordering and
        verifies the correct operation of the methods in a specific scenario.
        """
        a1 = self.q1.answer_set.all()[0]
        self.assertEqual(a1.text, "John")
        self.assertEqual(a1.get_next_in_order().text, "Paul")

        a2 = list(self.q1.answer_set.all())[-1]
        self.assertEqual(a2.text, "Ringo")
        self.assertEqual(a2.get_previous_in_order().text, "George")

    def test_item_ordering(self):
        # We can retrieve the ordering of the queryset from a particular item.
        """
        Tests if answers are ordered as expected when retrieved from a question.

        Checks if the order of answers matches their original order, by comparing the 
        primary keys of all answers with the order returned by the question. Then, it adds 
        a new answer and verifies if the order remains the same for different answers of 
        the question. This ensures that the ordering is stable and consistent, regardless 
        of which answer is used to retrieve the order.
        """
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

        Tests if the answer ordering for a question can be changed successfully.

        This function creates an answer object and checks if the initial answer order
        is different from the expected order. It then updates the answer order for the
        associated question and verifies that the updated order matches the expected
        order.

        The test case covers the scenario where an answer is moved to a different
        position in the ordering, ensuring that the changes are reflected correctly
        in the question's answer set.

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
        """
        Tests the retrieval of post ordering in a recursive manner.

        This test case verifies the correctness of the post ordering logic by creating a hierarchical structure of posts and checking that the ordering of child posts within a parent is correctly retrieved. The test covers a scenario with multiple child posts under a single parent, ensuring that the ordering is consistent and predictable. The expected output is a list of post identifiers in the correct order.
        """
        p1 = self.Post.objects.create(title="1")
        p2 = self.Post.objects.create(title="2")
        p1_1 = self.Post.objects.create(title="1.1", parent=p1)
        p1_2 = self.Post.objects.create(title="1.2", parent=p1)
        self.Post.objects.create(title="2.1", parent=p2)
        p1_3 = self.Post.objects.create(title="1.3", parent=p1)
        self.assertSequenceEqual(p1.get_post_order(), [p1_1.pk, p1_2.pk, p1_3.pk])

    def test_delete_and_insert(self):
        """
        Tests the deletion and insertion of answers associated with a question.

        This test case verifies that when an answer is deleted and a new one is inserted,
        the answer set for the corresponding question is updated correctly.

        It also checks that when an answer is reassigned to a different question,
        it is removed from the original question's answer set.

        The test includes the following scenarios:
        - Creation of questions and answers
        - Reassignment of an answer to a different question
        - Deletion of an existing answer
        - Insertion of a new answer

        The test asserts that the expected answer sequence is maintained after each operation.
        """
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
