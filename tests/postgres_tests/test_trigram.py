from . import PostgreSQLTestCase
from .models import CharFieldModel, TextFieldModel

try:
    from django.contrib.postgres.search import (
        TrigramDistance,
        TrigramSimilarity,
        TrigramStrictWordDistance,
        TrigramStrictWordSimilarity,
        TrigramWordDistance,
        TrigramWordSimilarity,
    )
except ImportError:
    pass


class TrigramTest(PostgreSQLTestCase):
    Model = CharFieldModel

    @classmethod
    def setUpTestData(cls):
        cls.Model.objects.bulk_create(
            [
                cls.Model(field="Matthew"),
                cls.Model(field="Cat sat on mat."),
                cls.Model(field="Dog sat on rug."),
            ]
        )

    def test_trigram_search(self):
        self.assertQuerySetEqual(
            self.Model.objects.filter(field__trigram_similar="Mathew"),
            ["Matthew"],
            transform=lambda instance: instance.field,
        )

    def test_trigram_word_search(self):
        """
        Tests the trigram word search functionality of the model.

        This test case checks the ability to query the model based on trigram word similarity.
        It verifies that objects can be retrieved using a trigram word similar match, 
        including full words and substrings, ensuring the functionality works as expected.

        The test covers two scenarios: exact word matching and prefix matching, 
        validating that the results returned are correct and in the expected order.
        """
        obj = self.Model.objects.create(
            field="Gumby rides on the path of Middlesbrough",
        )
        self.assertSequenceEqual(
            self.Model.objects.filter(field__trigram_word_similar="Middlesborough"),
            [obj],
        )
        self.assertSequenceEqual(
            self.Model.objects.filter(field__trigram_word_similar="Middle"),
            [obj],
        )

    def test_trigram_strict_word_search_matched(self):
        obj = self.Model.objects.create(
            field="Gumby rides on the path of Middlesbrough",
        )
        self.assertSequenceEqual(
            self.Model.objects.filter(
                field__trigram_strict_word_similar="Middlesborough"
            ),
            [obj],
        )
        self.assertSequenceEqual(
            self.Model.objects.filter(field__trigram_strict_word_similar="Middle"),
            [],
        )

    def test_trigram_similarity(self):
        """

        Tests the TrigramSimilarity functionality by filtering model objects based on their similarity to a given search string.

        The function verifies that the TrigramSimilarity function correctly ranks model objects by their similarity to the search string, 
        and that the similarity values are accurately calculated.

        It checks that the objects are ordered in descending order of similarity, with the most similar objects appearing first in the results.

        """
        search = "Bat sat on cat."
        # Round result of similarity because PostgreSQL uses greater precision.
        self.assertQuerySetEqual(
            self.Model.objects.filter(
                field__trigram_similar=search,
            )
            .annotate(similarity=TrigramSimilarity("field", search))
            .order_by("-similarity"),
            [("Cat sat on mat.", 0.625), ("Dog sat on rug.", 0.333333)],
            transform=lambda instance: (instance.field, round(instance.similarity, 6)),
            ordered=True,
        )

    def test_trigram_word_similarity(self):
        search = "mat"
        self.assertSequenceEqual(
            self.Model.objects.filter(
                field__trigram_word_similar=search,
            )
            .annotate(
                word_similarity=TrigramWordSimilarity(search, "field"),
            )
            .values("field", "word_similarity")
            .order_by("-word_similarity"),
            [
                {"field": "Cat sat on mat.", "word_similarity": 1.0},
                {"field": "Matthew", "word_similarity": 0.75},
            ],
        )

    def test_trigram_strict_word_similarity(self):
        """

        Tests the strict word similarity using trigrams for a given search term.

        The function verifies that the model returns the expected results when filtering
        objects based on the trigram word similarity between the search term and a
        specific field. The results are ordered by the word similarity score in
        descending order.

        The test case checks that the model correctly annotates the objects with their
        corresponding word similarity scores and returns the expected fields and scores.

        """
        search = "matt"
        self.assertSequenceEqual(
            self.Model.objects.filter(field__trigram_word_similar=search)
            .annotate(word_similarity=TrigramStrictWordSimilarity(search, "field"))
            .values("field", "word_similarity")
            .order_by("-word_similarity"),
            [
                {"field": "Cat sat on mat.", "word_similarity": 0.5},
                {"field": "Matthew", "word_similarity": 0.44444445},
            ],
        )

    def test_trigram_similarity_alternate(self):
        # Round result of distance because PostgreSQL uses greater precision.
        self.assertQuerySetEqual(
            self.Model.objects.annotate(
                distance=TrigramDistance("field", "Bat sat on cat."),
            )
            .filter(distance__lte=0.7)
            .order_by("distance"),
            [("Cat sat on mat.", 0.375), ("Dog sat on rug.", 0.666667)],
            transform=lambda instance: (instance.field, round(instance.distance, 6)),
            ordered=True,
        )

    def test_trigram_word_similarity_alternate(self):
        self.assertSequenceEqual(
            self.Model.objects.annotate(
                word_distance=TrigramWordDistance("mat", "field"),
            )
            .filter(
                word_distance__lte=0.7,
            )
            .values("field", "word_distance")
            .order_by("word_distance"),
            [
                {"field": "Cat sat on mat.", "word_distance": 0},
                {"field": "Matthew", "word_distance": 0.25},
            ],
        )

    def test_trigram_strict_word_distance(self):
        self.assertSequenceEqual(
            self.Model.objects.annotate(
                word_distance=TrigramStrictWordDistance("matt", "field"),
            )
            .filter(word_distance__lte=0.7)
            .values("field", "word_distance")
            .order_by("word_distance"),
            [
                {"field": "Cat sat on mat.", "word_distance": 0.5},
                {"field": "Matthew", "word_distance": 0.5555556},
            ],
        )


class TrigramTextFieldTest(TrigramTest):
    """
    TextField has the same behavior as CharField regarding trigram lookups.
    """

    Model = TextFieldModel
