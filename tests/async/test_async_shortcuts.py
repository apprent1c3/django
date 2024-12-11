from django.db.models import Q
from django.http import Http404
from django.shortcuts import aget_list_or_404, aget_object_or_404
from django.test import TestCase

from .models import RelatedModel, SimpleModel


class GetListObjectOr404Test(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.s1 = SimpleModel.objects.create(field=0)
        cls.s2 = SimpleModel.objects.create(field=1)
        cls.r1 = RelatedModel.objects.create(simple=cls.s1)

    async def test_aget_object_or_404(self):
        self.assertEqual(await aget_object_or_404(SimpleModel, field=1), self.s2)
        self.assertEqual(await aget_object_or_404(SimpleModel, Q(field=0)), self.s1)
        self.assertEqual(
            await aget_object_or_404(SimpleModel.objects.all(), field=1), self.s2
        )
        self.assertEqual(
            await aget_object_or_404(self.s1.relatedmodel_set, pk=self.r1.pk), self.r1
        )
        # Http404 is returned if the list is empty.
        msg = "No SimpleModel matches the given query."
        with self.assertRaisesMessage(Http404, msg):
            await aget_object_or_404(SimpleModel, field=2)

    async def test_get_list_or_404(self):
        """
        Tests the functionality of retrieving a list of objects or raising a 404 exception.

        This test case checks the behavior of aget_list_or_404 when retrieving a list of objects 
        based on different query parameters and sources. It verifies that the function returns 
        the expected list of objects when a match is found, and raises an Http404 exception with 
        a meaningful error message when no match is found. The test also covers scenarios where 
        the query is performed on a model class, a QuerySet, and a related manager.

        Args are not explicitly defined here, but typically this function accepts a model or 
        QuerySet and various query parameters (e.g. field filters, Q objects) to narrow down 
        the search. The exact parameters may vary depending on the specific use case and the 
        structure of the models involved. 

        Raises:
            Http404: If no objects match the given query.

        """
        self.assertEqual(await aget_list_or_404(SimpleModel, field=1), [self.s2])
        self.assertEqual(await aget_list_or_404(SimpleModel, Q(field=0)), [self.s1])
        self.assertEqual(
            await aget_list_or_404(SimpleModel.objects.all(), field=1), [self.s2]
        )
        self.assertEqual(
            await aget_list_or_404(self.s1.relatedmodel_set, pk=self.r1.pk), [self.r1]
        )
        # Http404 is returned if the list is empty.
        msg = "No SimpleModel matches the given query."
        with self.assertRaisesMessage(Http404, msg):
            await aget_list_or_404(SimpleModel, field=2)

    async def test_get_object_or_404_bad_class(self):
        """
        Tests that aget_object_or_404 raises a ValueError when given an invalid class type.

        This test case checks that the function correctly handles the case where the first argument is not a Model, Manager, or QuerySet.
        It verifies that the expected error message is raised when a string is passed instead of a valid model or query set.

        Args:
            None

        Raises:
            ValueError: If the first argument is not a Model, Manager, or QuerySet.

        Returns:
            None
        """
        msg = (
            "First argument to aget_object_or_404() must be a Model, Manager, or "
            "QuerySet, not 'str'."
        )
        with self.assertRaisesMessage(ValueError, msg):
            await aget_object_or_404("SimpleModel", field=0)

    async def test_get_list_or_404_bad_class(self):
        """
        Tests aget_list_or_404() function with an invalid first argument to verify correct error handling.

        The test checks that a ValueError is raised when the first argument is a list, rather than the expected Model, Manager, or QuerySet.

        It asserts that the error message matches the expected message, confirming proper exception handling in case of incorrect function usage.
        """
        msg = (
            "First argument to aget_list_or_404() must be a Model, Manager, or "
            "QuerySet, not 'list'."
        )
        with self.assertRaisesMessage(ValueError, msg):
            await aget_list_or_404([SimpleModel], field=1)
