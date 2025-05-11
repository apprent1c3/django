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
        class Model(models.Model):
            field = GenericForeignKey()

        self.assertEqual(str(Model.field), "contenttypes_tests.Model.field")

    def test_get_content_type_no_arguments(self):
        with self.assertRaisesMessage(
            Exception, "Impossible arguments to GFK.get_content_type!"
        ):
            Answer.question.get_content_type()

    def test_get_object_cache_respects_deleted_objects(self):
        """
        Tests that the object cache respects deleted objects by verifying that a post's parent is None after its parent question has been deleted, while still maintaining the correct object_id reference.
        """
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
        """
        Checks that the generic relation to a question is properly updated after refreshing the answer object from the database, ensuring the cache is cleared.
        """
        question = Question.objects.create(text="What is your name?")
        answer = Answer.objects.create(text="Answer", question=question)
        old_entity = answer.question
        answer.refresh_from_db()
        new_entity = answer.question
        self.assertIsNot(old_entity, new_entity)

    def test_clear_cached_generic_relation_explicit_fields(self):
        """

        Tests the behavior of Django's model instance refresh from database functionality,
        specifically when using explicit fields to update a generic relation. 
        Verifies that related objects are cleared from cache when refreshed with explicit fields.

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
        """
        Tests the conversion of Question's answer set foreign key values to a string representation, 
        verifying that the resulting string matches the expected list of answer IDs.
        """
        question = Question.objects.create(text="test")
        answer1 = Answer.objects.create(question=question)
        answer2 = Answer.objects.create(question=question)
        result = json.loads(Question.answer_set.field.value_to_string(question))
        self.assertCountEqual(result, [answer1.pk, answer2.pk])


class DeferredGenericRelationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.question = Question.objects.create(text="question")
        cls.answer = Answer.objects.create(text="answer", question=cls.question)

    def test_defer_not_clear_cached_private_relations(self):
        """
        Tests that deferred fields do not affect the caching of related objects, specifically private relations. Verifies that the related object is cached after accessing a deferred field, reducing subsequent query counts.
        """
        obj = Answer.objects.defer("text").get(pk=self.answer.pk)
        with self.assertNumQueries(1):
            obj.question
        obj.text  # Accessing a deferred field.
        with self.assertNumQueries(0):
            obj.question

    def test_only_not_clear_cached_private_relations(self):
        """
        Tests that Django's private relation caching works correctly when using select_related=False, by verifying that the related object 'question' is fetched only once, even after accessing another attribute 'text'.
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
        Tests that a deprecation warning is emitted when get_prefetch_queryset() is used instead of the plural get_prefetch_querysets().
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
        """
        Tests that the GenericPrefetch function raises a ValueError when attempting to prefetch multiple querysets for the same content type, enforcing the one queryset per content type rule.
        """
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
        Tests that attempting to prefetch related instances with multiple querysets raises a ValueError when the length of the querysets list exceeds 1.
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
