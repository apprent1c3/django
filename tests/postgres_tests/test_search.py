"""
Test PostgreSQL full text search.

These tests use dialogue from the 1975 film Monty Python and the Holy Grail.
All text copyright Python (Monty) Pictures. Thanks to sacred-texts.com for the
transcript.
"""

from django.db.models import F, Value

from . import PostgreSQLSimpleTestCase, PostgreSQLTestCase
from .models import Character, Line, LineSavedSearch, Scene

try:
    from django.contrib.postgres.search import (
        SearchConfig,
        SearchHeadline,
        SearchQuery,
        SearchRank,
        SearchVector,
    )
except ImportError:
    pass


class GrailTestData:
    @classmethod
    def setUpTestData(cls):
        cls.robin = Scene.objects.create(
            scene="Scene 10", setting="The dark forest of Ewing"
        )
        cls.minstrel = Character.objects.create(name="Minstrel")
        verses = [
            (
                "Bravely bold Sir Robin, rode forth from Camelot. "
                "He was not afraid to die, o Brave Sir Robin. "
                "He was not at all afraid to be killed in nasty ways. "
                "Brave, brave, brave, brave Sir Robin"
            ),
            (
                "He was not in the least bit scared to be mashed into a pulp, "
                "Or to have his eyes gouged out, and his elbows broken. "
                "To have his kneecaps split, and his body burned away, "
                "And his limbs all hacked and mangled, brave Sir Robin!"
            ),
            (
                "His head smashed in and his heart cut out, "
                "And his liver removed and his bowels unplugged, "
                "And his nostrils ripped and his bottom burned off,"
                "And his --"
            ),
        ]
        cls.verses = [
            Line.objects.create(
                scene=cls.robin,
                character=cls.minstrel,
                dialogue=verse,
            )
            for verse in verses
        ]
        cls.verse0, cls.verse1, cls.verse2 = cls.verses

        cls.witch_scene = Scene.objects.create(
            scene="Scene 5", setting="Sir Bedemir's Castle"
        )
        bedemir = Character.objects.create(name="Bedemir")
        crowd = Character.objects.create(name="Crowd")
        witch = Character.objects.create(name="Witch")
        duck = Character.objects.create(name="Duck")

        cls.bedemir0 = Line.objects.create(
            scene=cls.witch_scene,
            character=bedemir,
            dialogue="We shall use my larger scales!",
            dialogue_config="english",
        )
        cls.bedemir1 = Line.objects.create(
            scene=cls.witch_scene,
            character=bedemir,
            dialogue="Right, remove the supports!",
            dialogue_config="english",
        )
        cls.duck = Line.objects.create(
            scene=cls.witch_scene, character=duck, dialogue=None
        )
        cls.crowd = Line.objects.create(
            scene=cls.witch_scene, character=crowd, dialogue="A witch! A witch!"
        )
        cls.witch = Line.objects.create(
            scene=cls.witch_scene, character=witch, dialogue="It's a fair cop."
        )

        trojan_rabbit = Scene.objects.create(
            scene="Scene 8", setting="The castle of Our Master Ruiz' de lu la Ramper"
        )
        guards = Character.objects.create(name="French Guards")
        cls.french = Line.objects.create(
            scene=trojan_rabbit,
            character=guards,
            dialogue="Oh. Un beau cadeau. Oui oui.",
            dialogue_config="french",
        )


class SimpleSearchTest(GrailTestData, PostgreSQLTestCase):
    def test_simple(self):
        """
        Tests filtering of lines based on a specific search term.

        This test checks if the Line.objects.filter method can correctly retrieve 
        lines of dialogue that contain a specified search string. In this case, 
        the string 'elbows' is used to find a matching line of dialogue.

        The test verifies that the filtered results match the expected sequence 
        of lines, ensuring that the search functionality works as intended.
        """
        searched = Line.objects.filter(dialogue__search="elbows")
        self.assertSequenceEqual(searched, [self.verse1])

    def test_non_exact_match(self):
        self.check_default_text_search_config()
        searched = Line.objects.filter(dialogue__search="hearts")
        self.assertSequenceEqual(searched, [self.verse2])

    def test_search_two_terms(self):
        """
        Tests searching for a line that contains two specific terms.

        Verifies that the default text search configuration is used and that a line
        containing both 'heart' and 'bowel' is correctly retrieved from the database.

        The expected result is a sequence containing a single line object that matches
        the specified search criteria.
        """
        self.check_default_text_search_config()
        searched = Line.objects.filter(dialogue__search="heart bowel")
        self.assertSequenceEqual(searched, [self.verse2])

    def test_search_two_terms_with_partial_match(self):
        """
        Tests searching for lines containing two terms with a partial match.

        Verifies that the search functionality correctly returns lines where the 
        search terms appear together, even if they are not exact consecutive words, 
        but in this case, it checks for the exact sequence 'Robin killed'.

        The test case verifies that only the expected line is returned as a result 
        of the search query, ensuring that the search functionality is working 
        correctly in the specified scenario.
        """
        searched = Line.objects.filter(dialogue__search="Robin killed")
        self.assertSequenceEqual(searched, [self.verse0])

    def test_search_query_config(self):
        searched = Line.objects.filter(
            dialogue__search=SearchQuery("nostrils", config="simple"),
        )
        self.assertSequenceEqual(searched, [self.verse2])

    def test_search_with_F_expression(self):
        # Non-matching query.
        LineSavedSearch.objects.create(line=self.verse1, query="hearts")
        # Matching query.
        match = LineSavedSearch.objects.create(line=self.verse1, query="elbows")
        for query_expression in [F("query"), SearchQuery(F("query"))]:
            with self.subTest(query_expression):
                searched = LineSavedSearch.objects.filter(
                    line__dialogue__search=query_expression,
                )
                self.assertSequenceEqual(searched, [match])


class SearchVectorFieldTest(GrailTestData, PostgreSQLTestCase):
    def test_existing_vector(self):
        Line.objects.update(dialogue_search_vector=SearchVector("dialogue"))
        searched = Line.objects.filter(
            dialogue_search_vector=SearchQuery("Robin killed")
        )
        self.assertSequenceEqual(searched, [self.verse0])

    def test_existing_vector_config_explicit(self):
        """
        Tests that searching with an explicit vector configuration retrieves the correct results.

        This test case checks if the search functionality, using a specific vector configuration, returns the expected objects.
        It covers the scenario where the search query is executed with a predefined configuration, in this case 'french', 
        to ensure that the correct objects are matched and retrieved based on the given search terms.

        The test verifies that searching for the term 'cadeaux' with the 'french' configuration returns the expected line object, 
        indicated by `self.french`, confirming the effectiveness of the search query and configuration setup.
        """
        Line.objects.update(dialogue_search_vector=SearchVector("dialogue"))
        searched = Line.objects.filter(
            dialogue_search_vector=SearchQuery("cadeaux", config="french")
        )
        self.assertSequenceEqual(searched, [self.french])

    def test_single_coalesce_expression(self):
        """

        Tests the query generation of a single coalesce expression.

        Verifies that the SQL query resulting from the annotation and filtering of a Line object does not contain nested COALESCE functions, 
        indicating that the coalesce expression is correctly simplified in the generated query.

        """
        searched = Line.objects.annotate(search=SearchVector("dialogue")).filter(
            search="cadeaux"
        )
        self.assertNotIn("COALESCE(COALESCE", str(searched.query))

    def test_values_with_percent(self):
        searched = Line.objects.annotate(
            search=SearchVector(Value("This week everything is 10% off"))
        ).filter(search="10 % off")
        self.assertEqual(len(searched), 9)


class SearchConfigTests(PostgreSQLSimpleTestCase):
    def test_from_parameter(self):
        """
        Creates a SearchConfig instance from a given parameter, 
        handling cases where the parameter is None, a string, or an existing SearchConfig object.

        Returns:
            SearchConfig: A new SearchConfig instance if the parameter is a string, 
            the original SearchConfig instance if it's already a SearchConfig object, 
            or None if the parameter is None.
        """
        self.assertIsNone(SearchConfig.from_parameter(None))
        self.assertEqual(SearchConfig.from_parameter("foo"), SearchConfig("foo"))
        self.assertEqual(
            SearchConfig.from_parameter(SearchConfig("bar")), SearchConfig("bar")
        )


class MultipleFieldsTest(GrailTestData, PostgreSQLTestCase):
    def test_simple_on_dialogue(self):
        searched = Line.objects.annotate(
            search=SearchVector("scene__setting", "dialogue"),
        ).filter(search="elbows")
        self.assertSequenceEqual(searched, [self.verse1])

    def test_simple_on_scene(self):
        """
        Tests if the full-text search functionality correctly identifies lines 
        that contain the specified keyword 'Forest' in their scene setting or dialogue.

        Verifies that the search query returns the expected results by comparing 
        the searched lines with the predefined set of verses, ensuring the search 
        functionality is working as intended in the given scene context.
        """
        searched = Line.objects.annotate(
            search=SearchVector("scene__setting", "dialogue"),
        ).filter(search="Forest")
        self.assertCountEqual(searched, self.verses)

    def test_non_exact_match(self):
        searched = Line.objects.annotate(
            search=SearchVector("scene__setting", "dialogue"),
        ).filter(search="heart")
        self.assertSequenceEqual(searched, [self.verse2])

    def test_search_two_terms(self):
        searched = Line.objects.annotate(
            search=SearchVector("scene__setting", "dialogue"),
        ).filter(search="heart forest")
        self.assertSequenceEqual(searched, [self.verse2])

    def test_terms_adjacent(self):
        searched = Line.objects.annotate(
            search=SearchVector("character__name", "dialogue"),
        ).filter(search="minstrel")
        self.assertCountEqual(searched, self.verses)
        searched = Line.objects.annotate(
            search=SearchVector("scene__setting", "dialogue"),
        ).filter(search="minstrelbravely")
        self.assertSequenceEqual(searched, [])

    def test_search_with_null(self):
        searched = Line.objects.annotate(
            search=SearchVector("scene__setting", "dialogue"),
        ).filter(search="bedemir")
        self.assertCountEqual(
            searched, [self.bedemir0, self.bedemir1, self.crowd, self.witch, self.duck]
        )

    def test_search_with_non_text(self):
        """
        Tests the search functionality with a non-text search query.

        This test case verifies that searching using a non-text field, such as an integer id, 
        returns the expected results. It checks if the search function correctly filters 
        objects based on the specified id.

        The test searches for objects with an id matching the crowd id and asserts that 
        the result matches the expected crowd object.

        :param none:
        :return: none
        :raises: AssertionError if the search results do not match the expected outcome
        """
        searched = Line.objects.annotate(
            search=SearchVector("id"),
        ).filter(search=str(self.crowd.id))
        self.assertSequenceEqual(searched, [self.crowd])

    def test_phrase_search(self):
        line_qs = Line.objects.annotate(search=SearchVector("dialogue"))
        searched = line_qs.filter(
            search=SearchQuery("burned body his away", search_type="phrase")
        )
        self.assertSequenceEqual(searched, [])
        searched = line_qs.filter(
            search=SearchQuery("his body burned away", search_type="phrase")
        )
        self.assertSequenceEqual(searched, [self.verse1])

    def test_phrase_search_with_config(self):
        line_qs = Line.objects.annotate(
            search=SearchVector("scene__setting", "dialogue", config="french"),
        )
        searched = line_qs.filter(
            search=SearchQuery("cadeau beau un", search_type="phrase", config="french"),
        )
        self.assertSequenceEqual(searched, [])
        searched = line_qs.filter(
            search=SearchQuery("un beau cadeau", search_type="phrase", config="french"),
        )
        self.assertSequenceEqual(searched, [self.french])

    def test_raw_search(self):
        line_qs = Line.objects.annotate(search=SearchVector("dialogue"))
        searched = line_qs.filter(search=SearchQuery("Robin", search_type="raw"))
        self.assertCountEqual(searched, [self.verse0, self.verse1])
        searched = line_qs.filter(
            search=SearchQuery("Robin & !'Camelot'", search_type="raw")
        )
        self.assertSequenceEqual(searched, [self.verse1])

    def test_raw_search_with_config(self):
        line_qs = Line.objects.annotate(
            search=SearchVector("dialogue", config="french")
        )
        searched = line_qs.filter(
            search=SearchQuery(
                "'cadeaux' & 'beaux'", search_type="raw", config="french"
            ),
        )
        self.assertSequenceEqual(searched, [self.french])

    def test_web_search(self):
        line_qs = Line.objects.annotate(search=SearchVector("dialogue"))
        searched = line_qs.filter(
            search=SearchQuery(
                '"burned body" "split kneecaps"',
                search_type="websearch",
            ),
        )
        self.assertSequenceEqual(searched, [])
        searched = line_qs.filter(
            search=SearchQuery(
                '"body burned" "kneecaps split" -"nostrils"',
                search_type="websearch",
            ),
        )
        self.assertSequenceEqual(searched, [self.verse1])
        searched = line_qs.filter(
            search=SearchQuery(
                '"Sir Robin" ("kneecaps" OR "Camelot")',
                search_type="websearch",
            ),
        )
        self.assertSequenceEqual(searched, [self.verse0, self.verse1])

    def test_web_search_with_config(self):
        line_qs = Line.objects.annotate(
            search=SearchVector("scene__setting", "dialogue", config="french"),
        )
        searched = line_qs.filter(
            search=SearchQuery(
                "cadeau -beau", search_type="websearch", config="french"
            ),
        )
        self.assertSequenceEqual(searched, [])
        searched = line_qs.filter(
            search=SearchQuery("beau cadeau", search_type="websearch", config="french"),
        )
        self.assertSequenceEqual(searched, [self.french])

    def test_bad_search_type(self):
        """
        Tests that a ValueError is raised when an unknown search type is passed to the SearchQuery constructor. This ensures that only valid search types are accepted, preventing potential errors or unexpected behavior.
        """
        with self.assertRaisesMessage(
            ValueError, "Unknown search_type argument 'foo'."
        ):
            SearchQuery("kneecaps", search_type="foo")

    def test_config_query_explicit(self):
        searched = Line.objects.annotate(
            search=SearchVector("scene__setting", "dialogue", config="french"),
        ).filter(search=SearchQuery("cadeaux", config="french"))
        self.assertSequenceEqual(searched, [self.french])

    def test_config_query_implicit(self):
        searched = Line.objects.annotate(
            search=SearchVector("scene__setting", "dialogue", config="french"),
        ).filter(search="cadeaux")
        self.assertSequenceEqual(searched, [self.french])

    def test_config_from_field_explicit(self):
        searched = Line.objects.annotate(
            search=SearchVector(
                "scene__setting", "dialogue", config=F("dialogue_config")
            ),
        ).filter(search=SearchQuery("cadeaux", config=F("dialogue_config")))
        self.assertSequenceEqual(searched, [self.french])

    def test_config_from_field_implicit(self):
        searched = Line.objects.annotate(
            search=SearchVector(
                "scene__setting", "dialogue", config=F("dialogue_config")
            ),
        ).filter(search="cadeaux")
        self.assertSequenceEqual(searched, [self.french])


class TestCombinations(GrailTestData, PostgreSQLTestCase):
    def test_vector_add(self):
        """
        Tests the ability to add SearchVectors for full-text searching across multiple model fields.

        This test case verifies that a search query can correctly combine search vectors
        from different related models, specifically 'scene' and 'character', to retrieve
        relevant objects. The test uses a sample search term 'bedemir' and asserts that
        the retrieved objects match the expected set of results.\"\"\"
        ```
        """
        searched = Line.objects.annotate(
            search=SearchVector("scene__setting") + SearchVector("character__name"),
        ).filter(search="bedemir")
        self.assertCountEqual(
            searched, [self.bedemir0, self.bedemir1, self.crowd, self.witch, self.duck]
        )

    def test_vector_add_multi(self):
        """

        Tests the ability to add multiple search vectors and filter results.

        This test verifies that searching across multiple fields ('scene setting', 'character name', and 'dialogue') returns the expected results.
        It checks if a search term is found in any of these fields, and if the resulting set of objects matches the expected set.

        """
        searched = Line.objects.annotate(
            search=(
                SearchVector("scene__setting")
                + SearchVector("character__name")
                + SearchVector("dialogue")
            ),
        ).filter(search="bedemir")
        self.assertCountEqual(
            searched, [self.bedemir0, self.bedemir1, self.crowd, self.witch, self.duck]
        )

    def test_vector_combined_mismatch(self):
        msg = (
            "SearchVector can only be combined with other SearchVector "
            "instances, got NoneType."
        )
        with self.assertRaisesMessage(TypeError, msg):
            Line.objects.filter(dialogue__search=None + SearchVector("character__name"))

    def test_combine_different_vector_configs(self):
        self.check_default_text_search_config()
        searched = Line.objects.annotate(
            search=(
                SearchVector("dialogue", config="english")
                + SearchVector("dialogue", config="french")
            ),
        ).filter(
            search=SearchQuery("cadeaux", config="french") | SearchQuery("nostrils")
        )
        self.assertCountEqual(searched, [self.french, self.verse2])

    def test_query_and(self):
        searched = Line.objects.annotate(
            search=SearchVector("scene__setting", "dialogue"),
        ).filter(search=SearchQuery("bedemir") & SearchQuery("scales"))
        self.assertSequenceEqual(searched, [self.bedemir0])

    def test_query_multiple_and(self):
        """

        Tests the functionality of querying the database with multiple 'and' conditions.

        This test case checks if the search functionality correctly filters the results when 
        multiple search queries are combined with logical 'and' operators. It verifies that 
        only the lines containing all the specified keywords are returned, and that an empty 
        result set is returned when the search criteria cannot be met.

        The test covers two scenarios: one where no lines match the search criteria, and 
        another where a single line matches the criteria. 

        It ensures that the SearchVector and SearchQuery functions work correctly together 
        to filter the results based on the specified search terms in the scene setting and 
        dialogue fields of the Line objects.

        """
        searched = Line.objects.annotate(
            search=SearchVector("scene__setting", "dialogue"),
        ).filter(
            search=SearchQuery("bedemir")
            & SearchQuery("scales")
            & SearchQuery("nostrils")
        )
        self.assertSequenceEqual(searched, [])

        searched = Line.objects.annotate(
            search=SearchVector("scene__setting", "dialogue"),
        ).filter(
            search=SearchQuery("shall") & SearchQuery("use") & SearchQuery("larger")
        )
        self.assertSequenceEqual(searched, [self.bedemir0])

    def test_query_or(self):
        searched = Line.objects.filter(
            dialogue__search=SearchQuery("kneecaps") | SearchQuery("nostrils")
        )
        self.assertCountEqual(searched, [self.verse1, self.verse2])

    def test_query_multiple_or(self):
        """
        .. function:: test_query_multiple_or()
           Tests the ability to query multiple objects with an 'OR' condition using SearchQuery.
           This function verifies that filtering based on multiple search criteria correctly returns all matching objects.
           It checks for the presence of specific phrases ('kneecaps', 'nostrils', 'Sir Robin') in the dialogue and ensures the resulting set matches the expected collection of objects.
        """
        searched = Line.objects.filter(
            dialogue__search=SearchQuery("kneecaps")
            | SearchQuery("nostrils")
            | SearchQuery("Sir Robin")
        )
        self.assertCountEqual(searched, [self.verse1, self.verse2, self.verse0])

    def test_query_invert(self):
        searched = Line.objects.filter(
            character=self.minstrel, dialogue__search=~SearchQuery("kneecaps")
        )
        self.assertCountEqual(searched, [self.verse0, self.verse2])

    def test_combine_different_configs(self):
        searched = Line.objects.filter(
            dialogue__search=(
                SearchQuery("cadeau", config="french")
                | SearchQuery("nostrils", config="english")
            )
        )
        self.assertCountEqual(searched, [self.french, self.verse2])

    def test_combined_configs(self):
        """

        Tests the combination of multiple search queries across different configurations.

        This function verifies that a search for lines containing both 'nostrils' and 'bowels' 
        using a simple configuration returns the expected line, demonstrating the ability 
        to filter results based on multiple criteria. The simple configuration is applied 
        to each search query, ensuring that the search results are accurate and relevant.

        """
        searched = Line.objects.filter(
            dialogue__search=(
                SearchQuery("nostrils", config="simple")
                & SearchQuery("bowels", config="simple")
            ),
        )
        self.assertSequenceEqual(searched, [self.verse2])

    def test_combine_raw_phrase(self):
        """

        Tests combining raw phrase searches in a single query.

        This function verifies that a search query containing both a raw search term and a phrase can correctly retrieve relevant results.
        It checks that the search configuration is set to default, then performs a search for lines containing either the raw term 'burn:*' or the phrase 'rode forth from Camelot'.
        The function asserts that the results of this search match the expected set of lines.

        """
        self.check_default_text_search_config()
        searched = Line.objects.filter(
            dialogue__search=(
                SearchQuery("burn:*", search_type="raw", config="simple")
                | SearchQuery("rode forth from Camelot", search_type="phrase")
            )
        )
        self.assertCountEqual(searched, [self.verse0, self.verse1, self.verse2])

    def test_query_combined_mismatch(self):
        msg = (
            "SearchQuery can only be combined with other SearchQuery "
            "instances, got NoneType."
        )
        with self.assertRaisesMessage(TypeError, msg):
            Line.objects.filter(dialogue__search=None | SearchQuery("kneecaps"))

        with self.assertRaisesMessage(TypeError, msg):
            Line.objects.filter(dialogue__search=None & SearchQuery("kneecaps"))


class TestRankingAndWeights(GrailTestData, PostgreSQLTestCase):
    def test_ranking(self):
        searched = (
            Line.objects.filter(character=self.minstrel)
            .annotate(
                rank=SearchRank(
                    SearchVector("dialogue"), SearchQuery("brave sir robin")
                ),
            )
            .order_by("rank")
        )
        self.assertSequenceEqual(searched, [self.verse2, self.verse1, self.verse0])

    def test_rank_passing_untyped_args(self):
        searched = (
            Line.objects.filter(character=self.minstrel)
            .annotate(
                rank=SearchRank("dialogue", "brave sir robin"),
            )
            .order_by("rank")
        )
        self.assertSequenceEqual(searched, [self.verse2, self.verse1, self.verse0])

    def test_weights_in_vector(self):
        vector = SearchVector("dialogue", weight="A") + SearchVector(
            "character__name", weight="D"
        )
        searched = (
            Line.objects.filter(scene=self.witch_scene)
            .annotate(
                rank=SearchRank(vector, SearchQuery("witch")),
            )
            .order_by("-rank")[:2]
        )
        self.assertSequenceEqual(searched, [self.crowd, self.witch])

        vector = SearchVector("dialogue", weight="D") + SearchVector(
            "character__name", weight="A"
        )
        searched = (
            Line.objects.filter(scene=self.witch_scene)
            .annotate(
                rank=SearchRank(vector, SearchQuery("witch")),
            )
            .order_by("-rank")[:2]
        )
        self.assertSequenceEqual(searched, [self.witch, self.crowd])

    def test_ranked_custom_weights(self):
        vector = SearchVector("dialogue", weight="D") + SearchVector(
            "character__name", weight="A"
        )
        weights = [1.0, 0.0, 0.0, 0.5]
        searched = (
            Line.objects.filter(scene=self.witch_scene)
            .annotate(
                rank=SearchRank(vector, SearchQuery("witch"), weights=weights),
            )
            .order_by("-rank")[:2]
        )
        self.assertSequenceEqual(searched, [self.crowd, self.witch])

    def test_ranking_chaining(self):
        searched = (
            Line.objects.filter(character=self.minstrel)
            .annotate(
                rank=SearchRank(
                    SearchVector("dialogue"), SearchQuery("brave sir robin")
                ),
            )
            .filter(rank__gt=0.3)
        )
        self.assertSequenceEqual(searched, [self.verse0])

    def test_cover_density_ranking(self):
        not_dense_verse = Line.objects.create(
            scene=self.robin,
            character=self.minstrel,
            dialogue=(
                "Bravely taking to his feet, he beat a very brave retreat. "
                "A brave retreat brave Sir Robin."
            ),
        )
        searched = (
            Line.objects.filter(character=self.minstrel)
            .annotate(
                rank=SearchRank(
                    SearchVector("dialogue"),
                    SearchQuery("brave robin"),
                    cover_density=True,
                ),
            )
            .order_by("rank", "-pk")
        )
        self.assertSequenceEqual(
            searched,
            [self.verse2, not_dense_verse, self.verse1, self.verse0],
        )

    def test_ranking_with_normalization(self):
        short_verse = Line.objects.create(
            scene=self.robin,
            character=self.minstrel,
            dialogue="A brave retreat brave Sir Robin.",
        )
        searched = (
            Line.objects.filter(character=self.minstrel)
            .annotate(
                rank=SearchRank(
                    SearchVector("dialogue"),
                    SearchQuery("brave sir robin"),
                    # Divide the rank by the document length.
                    normalization=2,
                ),
            )
            .order_by("rank")
        )
        self.assertSequenceEqual(
            searched,
            [self.verse2, self.verse1, self.verse0, short_verse],
        )

    def test_ranking_with_masked_normalization(self):
        """

        Tests the ranking of search results with masked normalization.

        This test case verifies that the `SearchRank` annotation correctly ranks search results
        based on the relevance of the search query to the dialogue field, using a masked normalization
        approach to fine-tune the ranking. The test queries lines spoken by a specific character and
        searches for a phrase, then asserts that the results are returned in the correct order of relevance.

        """
        short_verse = Line.objects.create(
            scene=self.robin,
            character=self.minstrel,
            dialogue="A brave retreat brave Sir Robin.",
        )
        searched = (
            Line.objects.filter(character=self.minstrel)
            .annotate(
                rank=SearchRank(
                    SearchVector("dialogue"),
                    SearchQuery("brave sir robin"),
                    # Divide the rank by the document length and by the number of
                    # unique words in document.
                    normalization=Value(2).bitor(Value(8)),
                ),
            )
            .order_by("rank")
        )
        self.assertSequenceEqual(
            searched,
            [self.verse2, self.verse1, self.verse0, short_verse],
        )


class SearchQueryTests(PostgreSQLSimpleTestCase):
    def test_str(self):
        tests = (
            (~SearchQuery("a"), "~SearchQuery(Value('a'))"),
            (
                (SearchQuery("a") | SearchQuery("b"))
                & (SearchQuery("c") | SearchQuery("d")),
                "((SearchQuery(Value('a')) || SearchQuery(Value('b'))) && "
                "(SearchQuery(Value('c')) || SearchQuery(Value('d'))))",
            ),
            (
                SearchQuery("a") & (SearchQuery("b") | SearchQuery("c")),
                "(SearchQuery(Value('a')) && (SearchQuery(Value('b')) || "
                "SearchQuery(Value('c'))))",
            ),
            (
                (SearchQuery("a") | SearchQuery("b")) & SearchQuery("c"),
                "((SearchQuery(Value('a')) || SearchQuery(Value('b'))) && "
                "SearchQuery(Value('c')))",
            ),
            (
                SearchQuery("a")
                & (SearchQuery("b") & (SearchQuery("c") | SearchQuery("d"))),
                "(SearchQuery(Value('a')) && (SearchQuery(Value('b')) && "
                "(SearchQuery(Value('c')) || SearchQuery(Value('d')))))",
            ),
        )
        for query, expected_str in tests:
            with self.subTest(query=query):
                self.assertEqual(str(query), expected_str)


class SearchHeadlineTests(GrailTestData, PostgreSQLTestCase):
    def test_headline(self):
        """

        Tests the functionality of generating a headline from a search query.

        Verifies that the :func:`headline` method correctly annotates the results of a text search
        with the relevant fragments of the dialogue, surrounding matched keywords with HTML bold tags.

        """
        self.check_default_text_search_config()
        searched = Line.objects.annotate(
            headline=SearchHeadline(
                F("dialogue"),
                SearchQuery("brave sir robin"),
                config=SearchConfig("english"),
            ),
        ).get(pk=self.verse0.pk)
        self.assertEqual(
            searched.headline,
            "<b>Robin</b>. He was not at all afraid to be killed in nasty "
            "ways. <b>Brave</b>, <b>brave</b>, <b>brave</b>, <b>brave</b> "
            "<b>Sir</b> <b>Robin</b>",
        )

    def test_headline_untyped_args(self):
        self.check_default_text_search_config()
        searched = Line.objects.annotate(
            headline=SearchHeadline("dialogue", "killed", config="english"),
        ).get(pk=self.verse0.pk)
        self.assertEqual(
            searched.headline,
            "Robin. He was not at all afraid to be <b>killed</b> in nasty "
            "ways. Brave, brave, brave, brave Sir Robin",
        )

    def test_headline_with_config(self):
        searched = Line.objects.annotate(
            headline=SearchHeadline(
                "dialogue",
                SearchQuery("cadeaux", config="french"),
                config="french",
            ),
        ).get(pk=self.french.pk)
        self.assertEqual(
            searched.headline,
            "Oh. Un beau <b>cadeau</b>. Oui oui.",
        )

    def test_headline_with_config_from_field(self):
        searched = Line.objects.annotate(
            headline=SearchHeadline(
                "dialogue",
                SearchQuery("cadeaux", config=F("dialogue_config")),
                config=F("dialogue_config"),
            ),
        ).get(pk=self.french.pk)
        self.assertEqual(
            searched.headline,
            "Oh. Un beau <b>cadeau</b>. Oui oui.",
        )

    def test_headline_separator_options(self):
        """

        Tests the headline separator options functionality.

        This test ensures that the SearchHeadline annotation correctly highlights
        the specified search terms within a given text, using customizable start
        and stop selectors to format the highlighted terms.

        The test verifies that the annotation produces the expected output,
        including the properly formatted highlighted terms and the surrounding text.

        """
        searched = Line.objects.annotate(
            headline=SearchHeadline(
                "dialogue",
                "brave sir robin",
                start_sel="<span>",
                stop_sel="</span>",
            ),
        ).get(pk=self.verse0.pk)
        self.assertEqual(
            searched.headline,
            "<span>Robin</span>. He was not at all afraid to be killed in "
            "nasty ways. <span>Brave</span>, <span>brave</span>, <span>brave"
            "</span>, <span>brave</span> <span>Sir</span> <span>Robin</span>",
        )

    def test_headline_highlight_all_option(self):
        self.check_default_text_search_config()
        searched = Line.objects.annotate(
            headline=SearchHeadline(
                "dialogue",
                SearchQuery("brave sir robin", config="english"),
                highlight_all=True,
            ),
        ).get(pk=self.verse0.pk)
        self.assertIn(
            "<b>Bravely</b> bold <b>Sir</b> <b>Robin</b>, rode forth from "
            "Camelot. He was not afraid to die, o ",
            searched.headline,
        )

    def test_headline_short_word_option(self):
        self.check_default_text_search_config()
        searched = Line.objects.annotate(
            headline=SearchHeadline(
                "dialogue",
                SearchQuery("Camelot", config="english"),
                short_word=5,
                min_words=8,
            ),
        ).get(pk=self.verse0.pk)
        self.assertEqual(
            searched.headline,
            (
                "<b>Camelot</b>. He was not afraid to die, o Brave Sir Robin. He "
                "was not at all afraid"
            ),
        )

    def test_headline_fragments_words_options(self):
        """
        Tests the headline fragments functionality with specific words options.

        This test case checks the SearchHeadline functionality by annotating a Line object
        with a headline that uses a specific search query and configuration. It then 
        compares the resulting headline with an expected output to ensure the fragment 
        delimiter, maximum and minimum number of words per fragment, and maximum number 
        of fragments are correctly applied to the search results. The test verifies that 
        the search query is correctly highlighted in the resulting headline.
        """
        self.check_default_text_search_config()
        searched = Line.objects.annotate(
            headline=SearchHeadline(
                "dialogue",
                SearchQuery("brave sir robin", config="english"),
                fragment_delimiter="...<br>",
                max_fragments=4,
                max_words=3,
                min_words=1,
            ),
        ).get(pk=self.verse0.pk)
        self.assertEqual(
            searched.headline,
            "<b>Sir</b> <b>Robin</b>, rode...<br>"
            "<b>Brave</b> <b>Sir</b> <b>Robin</b>...<br>"
            "<b>Brave</b>, <b>brave</b>, <b>brave</b>...<br>"
            "<b>brave</b> <b>Sir</b> <b>Robin</b>",
        )
