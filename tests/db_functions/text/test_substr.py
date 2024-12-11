from django.db.models import Value as V
from django.db.models.functions import Lower, StrIndex, Substr, Upper
from django.test import TestCase

from ..models import Author


class SubstrTests(TestCase):
    def test_basic(self):
        """

        Tests basic queries and annotation functionality for Author objects.

        This test case creates Author instances, annotates their names with substrings,
        and then checks that the resulting query sets are ordered correctly and contain
        the expected values.

        It covers the following scenarios:

        - Extracting substrings from author names at specific positions and lengths
        - Ordering query sets by author name
        - Updating author aliases based on their names

        """
        Author.objects.create(name="John Smith", alias="smithj")
        Author.objects.create(name="Rhonda")
        authors = Author.objects.annotate(name_part=Substr("name", 5, 3))
        self.assertQuerySetEqual(
            authors.order_by("name"), [" Sm", "da"], lambda a: a.name_part
        )
        authors = Author.objects.annotate(name_part=Substr("name", 2))
        self.assertQuerySetEqual(
            authors.order_by("name"), ["ohn Smith", "honda"], lambda a: a.name_part
        )
        # If alias is null, set to first 5 lower characters of the name.
        Author.objects.filter(alias__isnull=True).update(
            alias=Lower(Substr("name", 1, 5)),
        )
        self.assertQuerySetEqual(
            authors.order_by("name"), ["smithj", "rhond"], lambda a: a.alias
        )

    def test_start(self):
        Author.objects.create(name="John Smith", alias="smithj")
        a = Author.objects.annotate(
            name_part_1=Substr("name", 1),
            name_part_2=Substr("name", 2),
        ).get(alias="smithj")

        self.assertEqual(a.name_part_1[1:], a.name_part_2)

    def test_pos_gt_zero(self):
        with self.assertRaisesMessage(ValueError, "'pos' must be greater than 0"):
            Author.objects.annotate(raises=Substr("name", 0))

    def test_expressions(self):
        Author.objects.create(name="John Smith", alias="smithj")
        Author.objects.create(name="Rhonda")
        substr = Substr(Upper("name"), StrIndex("name", V("h")), 5)
        authors = Author.objects.annotate(name_part=substr)
        self.assertQuerySetEqual(
            authors.order_by("name"), ["HN SM", "HONDA"], lambda a: a.name_part
        )
