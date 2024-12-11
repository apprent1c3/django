import json

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.prefetch import GenericPrefetch
from django.db import models
from django.test import TestCase
from django.test.utils import isolate_apps
from django.utils.deprecation import RemovedInDjango60Warning

from .models import Answer, Post, Question


@isolate_apps("contenttypes_tests")
class GenericForeignKeyTests(TestCase):
    def test_str(self):
        """
        Tests the string representation of a GenericForeignKey field in a model.

            Verifies that the string representation of the field is correctly formatted,
            including the app label and model name, to ensure proper identification of the field.

        """
        class Model(models.Model):
            field = GenericForeignKey()

        self.assertEqual(str(Model.field), "contenttypes_tests.Model.field")

    def test_get_content_type_no_arguments(self):
        """

         Tests that calling get_content_type without any arguments raises an exception.

         This test ensures that a meaningful error message is returned when get_content_type is invoked without
         providing the necessary parameters, indicating that the function requires specific arguments to operate.

        """
        with self.assertRaisesMessage(
            Exception, "Impossible arguments to GFK.get_content_type!"
        ):
            Answer.question.get_content_type()

    def test_get_object_cache_respects_deleted_objects(self):
        question = Question.objects.create(text="Who?")
        post = Post.objects.create(title="Answer", parent=question)

        question_pk = question.pk
        Question.objects.all().delete()

        post = Post.objects.get(pk=post.pk)
        with self.assertNumQueries(1):
            self.assertEqual(post.object_id, question_pk)
            self.assertIsNone(post.parent)
            self.assertIsNone(post.parent)

    def test_clear_cached_generic_relation(self):
        question = Question.objects.create(text="What is your name?")
        answer = Answer.objects.create(text="Answer", question=question)
        old_entity = answer.question
        answer.refresh_from_db()
        new_entity = answer.question
        self.assertIsNot(old_entity, new_entity)

    def test_clear_cached_generic_relation_explicit_fields(self):
        """

        Tests the behavior of clearing cached generic relation when explicit fields are specified.

        Verifies that when a model instance's fields are refreshed from the database with
        specific fields, the generic foreign key relationship is either preserved or
        reloaded accordingly. The test checks two scenarios: when the relation field is
        not included in the refresh and when it is explicitly included.

        The test ensures that the relation object remains the same when not included in the
        refresh and that it is reloaded with a new object when explicitly included,
        although the actual object being referred to remains the same.

        """
        question = Question.objects.create(text="question")
        answer = Answer.objects.create(text="answer", question=question)
        old_question_obj = answer.question
        # The reverse relation is not refreshed if not passed explicitly in
        # `fields`.
        answer.refresh_from_db(fields=["text"])
        self.assertIs(answer.question, old_question_obj)
        answer.refresh_from_db(fields=["question"])
        self.assertIsNot(answer.question, old_question_obj)
        self.assertEqual(answer.question, old_question_obj)


class GenericRelationTests(TestCase):
    def test_value_to_string(self):
        question = Question.objects.create(text="test")
        answer1 = Answer.objects.create(question=question)
        answer2 = Answer.objects.create(question=question)
        result = json.loads(Question.answer_set.field.value_to_string(question))
        self.assertCountEqual(result, [answer1.pk, answer2.pk])


class DeferredGenericRelationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        ..:class:`setUpTestData`: 
            Sets up test data for the test class. 
            This method is used to populate the database with a question and an answer, 
            which can be used throughout the test class. 
            It creates a question instance and an answer instance associated with the question, 
            and assigns them to class attributes for later use.
        """
        cls.question = Question.objects.create(text="question")
        cls.answer = Answer.objects.create(text="answer", question=cls.question)

    def test_defer_not_clear_cached_private_relations(self):
        obj = Answer.objects.defer("text").get(pk=self.answer.pk)
        with self.assertNumQueries(1):
            obj.question
        obj.text  # Accessing a deferred field.
        with self.assertNumQueries(0):
            obj.question

    def test_only_not_clear_cached_private_relations(self):
        """

        Tests that only fetching certain fields and not clearing cached private relations
        results in the expected database query behavior.

        This test ensures that when private relations are cached, subsequent accesses to those 
        relations do not result in additional database queries. It specifically checks the 
        case where the 'question' relation of an 'Answer' object is accessed after the object 
        has been fetched using 'only' to specify the fields to retrieve.

        """
        obj = Answer.objects.only("content_type", "object_id").get(pk=self.answer.pk)
        with self.assertNumQueries(1):
            obj.question
        obj.text  # Accessing a deferred field.
        with self.assertNumQueries(0):
            obj.question


class GetPrefetchQuerySetDeprecation(TestCase):
    def test_generic_relation_warning(self):
        """

        Tests the deprecation warning raised when using the get_prefetch_queryset method on a generic relation.

        This test case ensures that the RemovedInDjango60Warning is triggered when accessing the get_prefetch_queryset
        method on a related object set, with a message indicating that get_prefetch_querysets should be used instead.

        It verifies the correct behavior of the deprecation warning for a generic relation, helping to prevent
        unexpected errors when upgrading to Django 6.0.

        """
        Question.objects.create(text="test")
        questions = Question.objects.all()
        msg = (
            "get_prefetch_queryset() is deprecated. Use get_prefetch_querysets() "
            "instead."
        )
        with self.assertWarnsMessage(RemovedInDjango60Warning, msg):
            questions[0].answer_set.get_prefetch_queryset(questions)

    def test_generic_foreign_key_warning(self):
        answers = Answer.objects.all()
        msg = (
            "get_prefetch_queryset() is deprecated. Use get_prefetch_querysets() "
            "instead."
        )
        with self.assertWarnsMessage(RemovedInDjango60Warning, msg):
            Answer.question.get_prefetch_queryset(answers)


class GetPrefetchQuerySetsTests(TestCase):
    def test_duplicate_querysets(self):
        question = Question.objects.create(text="What is your name?")
        answer = Answer.objects.create(text="Joe", question=question)
        answer = Answer.objects.get(pk=answer.pk)
        msg = "Only one queryset is allowed for each content type."
        with self.assertRaisesMessage(ValueError, msg):
            models.prefetch_related_objects(
                [answer],
                GenericPrefetch(
                    "question",
                    [
                        Question.objects.all(),
                        Question.objects.filter(text__startswith="test"),
                    ],
                ),
            )

    def test_generic_relation_invalid_length(self):
        """

        Tests that the get_prefetch_querysets method raises a ValueError when the querysets argument has an invalid length.

        This test case creates a Question object and then attempts to fetch its prefetch querysets with an incorrect number of querysets.
        It verifies that a ValueError is raised with the expected error message, ensuring that the method enforces the correct length for the querysets argument.

        """
        Question.objects.create(text="test")
        questions = Question.objects.all()
        msg = (
            "querysets argument of get_prefetch_querysets() should have a length of 1."
        )
        with self.assertRaisesMessage(ValueError, msg):
            questions[0].answer_set.get_prefetch_querysets(
                instances=questions,
                querysets=[Answer.objects.all(), Question.objects.all()],
            )
