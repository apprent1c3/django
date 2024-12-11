import datetime

from django.db import models
from django.test import TestCase
from django.test.utils import isolate_apps

from .models import InternationalArticle


class SimpleTests(TestCase):
    def test_international(self):
        """
        Tests the string representation of an InternationalArticle instance.

        Verifies that the string representation of an InternationalArticle object is 
        equal to its headline attribute, handling international characters correctly.

        Checks if the __str__ method of the InternationalArticle class returns the 
        expected string, which is the headline of the article, for an article with 
        international characters in its headline.

        The test case creates an InternationalArticle instance with a headline 
        containing the Euro symbol (€) and checks that its string representation 
        matches the headline, ensuring correct handling of international characters.
        """
        a = InternationalArticle.objects.create(
            headline="Girl wins €12.500 in lottery",
            pub_date=datetime.datetime(2005, 7, 28),
        )
        self.assertEqual(str(a), "Girl wins €12.500 in lottery")

    @isolate_apps("str")
    def test_defaults(self):
        """
        The default implementation of __str__ and __repr__ should return
        instances of str.
        """

        class Default(models.Model):
            pass

        obj = Default()
        # Explicit call to __str__/__repr__ to make sure str()/repr() don't
        # coerce the returned value.
        self.assertIsInstance(obj.__str__(), str)
        self.assertIsInstance(obj.__repr__(), str)
        self.assertEqual(str(obj), "Default object (None)")
        self.assertEqual(repr(obj), "<Default: Default object (None)>")
        obj2 = Default(pk=100)
        self.assertEqual(str(obj2), "Default object (100)")
        self.assertEqual(repr(obj2), "<Default: Default object (100)>")
