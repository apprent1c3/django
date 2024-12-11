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
        """

        Sets up test data for the application.

        This method creates various scenes, characters, and lines for testing purposes.
        It establishes two main scenes: 'Scene 10' (the dark forest of Ewing) and 'Scene 5' (Sir Bedemir's Castle),
        with associated characters and lines of dialogue.

        Additionally, it creates another scene, 'Scene 8' (the castle of Our Master Ruiz' de lu la Ramper),
        with a character and a line of dialogue in French.

        The created test data is stored as class attributes, making it accessible for subsequent tests.

        """
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
        searched = Line.objects.filter(dialogue__search="elbows")
        self.assertSequenceEqual(searched, [self.verse1])

    def test_non_exact_match(self):
        self.check_default_text_search_config()
        searched = Line.objects.filter(dialogue__search="hearts")
        self.assertSequenceEqual(searched, [self.verse2])

    def test_search_two_terms(self):
        self.check_default_text_search_config()
        searched = Line.objects.filter(dialogue__search="heart bowel")
        self.assertSequenceEqual(searched, [self.verse2])

    def test_search_two_terms_with_partial_match(self):
        searched = Line.objects.filter(dialogue__search="Robin killed")
        self.assertSequenceEqual(searched, [self.verse0])

    def test_search_query_config(self):
        searched = Line.objects.filter(
            dialogue__search=SearchQuery("nostrils", config="simple"),
        )
        self.assertSequenceEqual(searched, [self.verse2])

    def test_search_with_F_expression(self):
        # Non-matching query.
        """

        Tests searching for LineSavedSearch objects using F expressions.

        This test creates LineSavedSearch objects with specific queries, then filters these objects using F expressions.
        It verifies that the filtered results match the expected objects, ensuring that the search functionality works correctly.

        The test covers two types of query expressions: simple F expressions and SearchQuery with F expressions.
        It checks that both types of expressions can successfully filter the LineSavedSearch objects based on the query.

        """
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
        Line.objects.update(dialogue_search_vector=SearchVector("dialogue"))
        searched = Line.objects.filter(
            dialogue_search_vector=SearchQuery("cadeaux", config="french")
        )
        self.assertSequenceEqual(searched, [self.french])

    def test_single_coalesce_expression(self):
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
        """
        Test that search terms are correctly identified as adjacent in the database.

        The function checks two scenarios: 
        1. When multiple terms are adjacent in a single field (e.g. 'character__name', 'dialogue'), it verifies that the search results are correctly returned and match the expected output.
        2. When terms are adjacent across multiple fields (e.g. 'scene__setting', 'dialogue'), it checks that no results are returned, as the search is intended to find terms within a single field, not across different fields.
        """
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
        searched = Line.objects.annotate(
            search=SearchVector("scene__setting") + SearchVector("character__name"),
        ).filter(search="bedemir")
        self.assertCountEqual(
            searched, [self.bedemir0, self.bedemir1, self.crowd, self.witch, self.duck]
        )

    def test_vector_add_multi(self):
        """

        Tests the addition of multiple search vectors for annotating model instances.

        This test case verifies that multiple search vectors can be combined using the
        addition operator (+) to create a new search vector. The test searches for a
        specific term ('bedemir') in the 'scene__setting', 'character__name', and
        'dialogue' fields of the Line model, and checks that the resulting query returns
        the expected set of instances.

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
        searched = Line.objects.filter(
            dialogue__search=(
                SearchQuery("nostrils", config="simple")
                & SearchQuery("bowels", config="simple")
            ),
        )
        self.assertSequenceEqual(searched, [self.verse2])

    def test_combine_raw_phrase(self):
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
        """

        Tests the ranking functionality with normalization in search queries.

        This function verifies that lines of dialogue are correctly ranked based on their relevance to a given search query, 
        with the normalization factor influencing the scoring. It checks that the lines are ordered by their rank, 
        with the most relevant lines appearing first.

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
        Tests the ranking functionality with masked normalization, verifying that lines of dialogue are correctly ordered based on their relevance to a search query. 

        The function creates a new dialogue line with specific content and then searches for lines containing the phrase 'brave sir robin', applying a masked normalization to the search ranking. 

        It checks that the result sequence matches the expected order, which is determined by the search rank. The test case covers the interaction between the search query, normalization, and the resulting ranking of dialogue lines.
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
        """

        Tests the string representation of SearchQuery objects.

        This test checks that the string representation of various SearchQuery 
        objects is correctly generated. It covers different query types, 
        including negated queries, disjunctions (OR operations), and 
        conjunctions (AND operations), as well as nested queries.

        The test ensures that the generated strings accurately reflect the 
        structure and content of the SearchQuery objects, which is essential 
        for correct serialization, deserialization, and debugging of these objects.

        """
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
        Tests that the SearchHeadline function correctly generates headline fragments with the specified word options.

        The test verifies that the headline fragments are generated based on the provided search query, with a maximum of 4 fragments and 3 words per fragment, and a minimum of 1 word per fragment. The fragment delimiter is also customized to include a line break.

        The function checks the generated headline against an expected output, ensuring that the search query terms are highlighted in bold and that the fragments are properly truncated and separated by the delimiter.
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
