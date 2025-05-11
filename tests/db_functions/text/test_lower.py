from django.db.models import CharField
from django.db.models.functions import Lower
from django.test import TestCase
from django.test.utils import register_lookup

from ..models import Author


class LowerTests(TestCase):
    def test_basic(self):
        """
        Tests basic database operations on Author objects, including annotation, ordering, and updating of names to ensure correct case sensitivity handling.
        """
        Author.objects.create(name="John Smith", alias="smithj")
        Author.objects.create(name="Rhonda")
        authors = Author.objects.annotate(lower_name=Lower("name"))
        self.assertQuerySetEqual(
            authors.order_by("name"), ["john smith", "rhonda"], lambda a: a.lower_name
        )
        Author.objects.update(name=Lower("name"))
        self.assertQuerySetEqual(
            authors.order_by("name"),
            [
                ("john smith", "john smith"),
                ("rhonda", "rhonda"),
            ],
            lambda a: (a.lower_name, a.name),
        )

    def test_num_args(self):
        with self.assertRaisesMessage(
            TypeError, "'Lower' takes exactly 1 argument (2 given)"
        ):
            Author.objects.update(name=Lower("name", "name"))

    def test_transform(self):
        """
        Tests the transformation of a model field to lowercase for exact case-insensitive matching in database queries.
        """
        with register_lookup(CharField, Lower):
            Author.objects.create(name="John Smith", alias="smithj")
            Author.objects.create(name="Rhonda")
            authors = Author.objects.filter(name__lower__exact="john smith")
            self.assertQuerySetEqual(
                authors.order_by("name"), ["John Smith"], lambda a: a.name
            )
