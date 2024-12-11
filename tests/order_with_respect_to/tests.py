from operator import attrgetter

from django.db import models
from django.test import SimpleTestCase, TestCase
from django.test.utils import isolate_apps

from .base_tests import BaseOrderWithRespectToTests
from .models import Answer, Dimension, Entity, Post, Question


class OrderWithRespectToBaseTests(BaseOrderWithRespectToTests, TestCase):
    Answer = Answer
    Post = Post
    Question = Question


class OrderWithRespectToTests(SimpleTestCase):
    @isolate_apps("order_with_respect_to")
    def test_duplicate_order_field(self):
        """
        Tests that a model with an OrderWithRespectTo field does not create duplicate order fields. 

        The test creates a model hierarchy with a foreign key relationship and verifies that the OrderWithRespectTo field is only instantiated once in the model's metadata, ensuring that the ordering is applied correctly with respect to the related model.
        """
        class Bar(models.Model):
            class Meta:
                app_label = "order_with_respect_to"

        class Foo(models.Model):
            bar = models.ForeignKey(Bar, models.CASCADE)
            order = models.OrderWrt()

            class Meta:
                order_with_respect_to = "bar"
                app_label = "order_with_respect_to"

        count = 0
        for field in Foo._meta.local_fields:
            if isinstance(field, models.OrderWrt):
                count += 1

        self.assertEqual(count, 1)


class TestOrderWithRespectToOneToOnePK(TestCase):
    def test_set_order(self):
        """

        Tests the functionality of setting the order of components within a dimension.

        This function checks if the components of a dimension can be reordered correctly.
        It first creates an entity and a dimension associated with that entity,
        then creates two components and adds them to the dimension.
        It sets the order of the components and verifies that the components are retrieved
        in the correct order, confirming that the set order has been applied successfully.

        """
        e = Entity.objects.create()
        d = Dimension.objects.create(entity=e)
        c1 = d.component_set.create()
        c2 = d.component_set.create()
        d.set_component_order([c1.id, c2.id])
        self.assertQuerySetEqual(
            d.component_set.all(), [c1.id, c2.id], attrgetter("pk")
        )
