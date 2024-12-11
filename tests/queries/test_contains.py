from django.test import TestCase

from .models import DumbCategory, NamedCategory, ProxyCategory


class ContainsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = DumbCategory.objects.create()
        cls.proxy_category = ProxyCategory.objects.create()

    def test_unsaved_obj(self):
        """

        Tests that attempting to use QuerySet.contains() on an unsaved object raises a ValueError.

        This test case verifies that the expected error message is raised when an unsaved
        DumbCategory object is passed to the contains() method of a QuerySet.

        """
        msg = "QuerySet.contains() cannot be used on unsaved objects."
        with self.assertRaisesMessage(ValueError, msg):
            DumbCategory.objects.contains(DumbCategory())

    def test_obj_type(self):
        msg = "'obj' must be a model instance."
        with self.assertRaisesMessage(TypeError, msg):
            DumbCategory.objects.contains(object())

    def test_values(self):
        msg = "Cannot call QuerySet.contains() after .values() or .values_list()."
        with self.assertRaisesMessage(TypeError, msg):
            DumbCategory.objects.values_list("pk").contains(self.category)
        with self.assertRaisesMessage(TypeError, msg):
            DumbCategory.objects.values("pk").contains(self.category)

    def test_basic(self):
        """
        Tests the basic functionality of DumbCategory object containment.

        Verifies that the contains method of DumbCategory objects returns the expected result, 
        specifically that a category is contained within itself, and does so with the expected 
        database query overhead, demonstrating efficient data retrieval.

        The test ensures that the contains method behaves consistently across multiple invocations, 
        yielding the same result without incurring excessive database query costs.
        """
        with self.assertNumQueries(1):
            self.assertIs(DumbCategory.objects.contains(self.category), True)
        # QuerySet.contains() doesn't evaluate a queryset.
        with self.assertNumQueries(1):
            self.assertIs(DumbCategory.objects.contains(self.category), True)

    def test_evaluated_queryset(self):
        """
        Tests the queryset evaluation for both DumbCategory and ProxyCategory models.

        This test ensures that the queryset contains method does not trigger any additional database queries 
        once the queryset has been evaluated. It checks that both native and proxy categories can be correctly 
        identified as being part of the evaluated querysets, verifying the effective lazy loading behavior.

        Checks are performed on both DumbCategory and ProxyCategory querysets to ensure consistent behavior.

        """
        qs = DumbCategory.objects.all()
        proxy_qs = ProxyCategory.objects.all()
        # Evaluate querysets.
        list(qs)
        list(proxy_qs)
        with self.assertNumQueries(0):
            self.assertIs(qs.contains(self.category), True)
            self.assertIs(qs.contains(self.proxy_category), True)
            self.assertIs(proxy_qs.contains(self.category), True)
            self.assertIs(proxy_qs.contains(self.proxy_category), True)

    def test_proxy_model(self):
        with self.assertNumQueries(1):
            self.assertIs(DumbCategory.objects.contains(self.proxy_category), True)
        with self.assertNumQueries(1):
            self.assertIs(ProxyCategory.objects.contains(self.category), True)

    def test_wrong_model(self):
        """

        Tests that a queryset does not contain an object of a different model.

        This test checks the behavior of a Django queryset's contains method when 
        passed an object of a different model type. It verifies that the method 
        correctly returns False, both before and after the queryset has been 
        evaluated, and does so without executing additional database queries.

        """
        qs = DumbCategory.objects.all()
        named_category = NamedCategory(name="category")
        with self.assertNumQueries(0):
            self.assertIs(qs.contains(named_category), False)
        # Evaluate the queryset.
        list(qs)
        with self.assertNumQueries(0):
            self.assertIs(qs.contains(named_category), False)
