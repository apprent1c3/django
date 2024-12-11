from django.db.models import Value as V
from django.db.models.functions import Lower, StrIndex, Substr, Upper
from django.test import TestCase

from ..models import Author


class SubstrTests(TestCase):
    def test_basic(self):
        """

        Tests basic database query functionality.

        This function creates test author objects, performs queries using the Substr and Lower functions,
        and verifies that the results match the expected output. It checks the ability to extract substrings
        from author names and update author aliases accordingly. The test cases cover various scenarios,
        including extracting substrings of different lengths and updating null alias values.

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
        """

        Tests the start position of string substrings in Django model fields.

        Verifies that the substrings extracted from the 'name' field of an Author instance
        match as expected when starting from different positions. This ensures that the
        database backend correctly handles substrings of model field values, allowing for
        accurate data manipulation and analysis.

        """
        Author.objects.create(name="John Smith", alias="smithj")
        a = Author.objects.annotate(
            name_part_1=Substr("name", 1),
            name_part_2=Substr("name", 2),
        ).get(alias="smithj")

        self.assertEqual(a.name_part_1[1:], a.name_part_2)

    def test_pos_gt_zero(self):
        """
        Tests that a ValueError is raised with the correct message when the 'pos' argument passed to Substr is not greater than 0.

        This test case ensures that the validation of the 'pos' parameter is correctly enforced, preventing invalid usage of the Substr function.

        The expected exception message is \"'pos' must be greater than 0\", indicating that the function requires a positive position value.

        Args: None

        Returns: None

        Raises: 
            ValueError: If 'pos' is not greater than 0
        """
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
