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

        Setup test data for the application.

        This method creates a set of test scenes, characters, and dialogue lines to be used in testing.
        It initializes scenes, characters, and verses from the story of Sir Robin and other scenes.
        The created data includes scenes with their settings, characters, and lines of dialogue.
        The method also creates specific lines of dialogue for certain characters and scenes, 
        including English and French dialogue configurations.

        The created test data can be accessed through class attributes, such as `robin`, `minstrel`, 
        `verses`, `witch_scene`, `bedemir0`, `bedemir1`, `duck`, `crowd`, `witch`, and `french`.

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
        """
        Tests that a simple search query returns the expected results.

        This test case checks if the `Line` objects are correctly filtered based on a search term.
        It verifies that searching for the term 'elbows' returns the `verse1` object as the only result.
        """
        searched = Line.objects.filter(dialogue__search="elbows")
        self.assertSequenceEqual(searched, [self.verse1])

    def test_non_exact_match(self):
        """
        Tests a non-exact text search query.

        Verifies that the default text search configuration returns the expected results 
        when searching for a word that is part of a phrase in the dialogue.

        The search query 'hearts' is used to test this functionality. The function checks 
        that only the verse containing the word 'hearts' is returned in the search results, 
        even if it's not an exact match for the entire dialogue text.
        """
        self.check_default_text_search_config()
        searched = Line.objects.filter(dialogue__search="hearts")
        self.assertSequenceEqual(searched, [self.verse2])

    def test_search_two_terms(self):
        self.check_default_text_search_config()
        searched = Line.objects.filter(dialogue__search="heart bowel")
        self.assertSequenceEqual(searched, [self.verse2])

    def test_search_two_terms_with_partial_match(self):
        """
        Tests searching for lines containing two terms with a partial match.

        Verifies that the search functionality correctly returns a line when the search query contains multiple terms, 
        and at least one term partially matches the dialogue. 

        The expected outcome is that only the line with the dialogue containing the partial match is returned in the search results.
        """
        searched = Line.objects.filter(dialogue__search="Robin killed")
        self.assertSequenceEqual(searched, [self.verse0])

    def test_search_query_config(self):
        """
        Tests the search query configuration for a specific keyword.

        Verifies that the search query function returns the expected results when 
        configured with the 'simple' configuration and searching for the term 'nostrils'.
        The function checks if the search query correctly filters objects and returns 
        the matching sequence of results.
        """
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
        """

        Tests the search functionality using an existing vector.

        This test case updates the search vector for all Line objects based on their dialogue field,
        then filters the objects using a specific search query. It asserts that the filtered results
        match the expected sequence of objects.

        The search query is performed using the 'dialogue_search_vector' field, which indexes the
        'dialogue' field of each Line object. The test verifies that the search functionality correctly
        returns the objects that match the given search query.

        """
        Line.objects.update(dialogue_search_vector=SearchVector("dialogue"))
        searched = Line.objects.filter(
            dialogue_search_vector=SearchQuery("Robin killed")
        )
        self.assertSequenceEqual(searched, [self.verse0])

    def test_existing_vector_config_explicit(self):
        """
        Tests the existing vector database configuration for searching dialogue lines.

        This test case verifies that an explicit search configuration can be applied 
        to the dialogue search vector, allowing for searching in different languages. 
        In this scenario, the search is performed in French, and the test asserts that 
        the result matches the expected outcome.
        """
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
        """
        Returns an instance of SearchConfig based on the provided parameter.

        If the parameter is None, returns None. If the parameter is a string,
        constructs a new SearchConfig instance with the given string. If the
        parameter is already a SearchConfig instance, returns the instance
        unchanged. This allows for convenient conversion from various input
        types to a standard SearchConfig representation.
        """
        self.assertIsNone(SearchConfig.from_parameter(None))
        self.assertEqual(SearchConfig.from_parameter("foo"), SearchConfig("foo"))
        self.assertEqual(
            SearchConfig.from_parameter(SearchConfig("bar")), SearchConfig("bar")
        )


class MultipleFieldsTest(GrailTestData, PostgreSQLTestCase):
    def test_simple_on_dialogue(self):
        """
        Tests the simple full-text search functionality on dialogue content.

        This test case verifies that the search functionality can correctly identify and retrieve lines of dialogue 
        containing a specific search term. It checks if the search result matches the expected outcome, ensuring 
        the accuracy of the search functionality. The test is case-sensitive and searches for exact matches of the 
        specified term within the dialogue content.

        Parameters
        ----------
        None

        Returns
        -------
        None

        Notes
        -----
        This test case is part of the unit testing suite and should be run to ensure the search functionality is 
        working as expected. The test assumes that the database is populated with the necessary data, including 
        lines of dialogue and their corresponding scenes and settings. The test result is a boolean value indicating 
        whether the search result matches the expected outcome.
        """
        searched = Line.objects.annotate(
            search=SearchVector("scene__setting", "dialogue"),
        ).filter(search="elbows")
        self.assertSequenceEqual(searched, [self.verse1])

    def test_simple_on_scene(self):
        """
        Tests simple full-text search functionality on a scene.

        Checks if the function can correctly find and retrieve lines from the database 
        where the scene setting or dialogue contains the specified search term, in this case 'Forest'. 

        The test verifies that the results match the expected set of verses.
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
        """
        Checks that search functionality correctly handles adjacent terms in search queries.

        This test verifies that the search vector can find objects containing a single search term, 
        and that it handles cases where multiple terms are adjacent in the search query, ensuring 
        that the returned results are correct and empty when no matches are found.
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
        """

        Tests the search functionality with a specific query.

        This test case verifies that searching for the term 'bedemir' returns the expected results, 
        including scenes and characters associated with the search term.

        The search is performed across the 'setting' and 'dialogue' attributes of the Line model, 
        and the results are compared to a predefined set of expected matches.

        """
        searched = Line.objects.annotate(
            search=SearchVector("scene__setting", "dialogue"),
        ).filter(search="bedemir")
        self.assertCountEqual(
            searched, [self.bedemir0, self.bedemir1, self.crowd, self.witch, self.duck]
        )

    def test_search_with_non_text(self):
        """
        Tests the search functionality with non-text data by annotating a search vector on the 'id' field of Line objects and filtering the results based on a specific crowd id, verifying that the returned sequence matches the expected crowd object.
        """
        searched = Line.objects.annotate(
            search=SearchVector("id"),
        ).filter(search=str(self.crowd.id))
        self.assertSequenceEqual(searched, [self.crowd])

    def test_phrase_search(self):
        """
        Tests the functionality of phrase searching in the Line model.

        This test case verifies that phrase searches are executed correctly, ensuring that 
        exact phrase matches are returned, while non-matching phrases are not. The test 
        cases cover both exact and non-exact phrase matching, demonstrating the 
        functionality of the SearchVector and SearchQuery mechanisms in filtering Line 
        objects based on specific phrases in their dialogue field.

        The test also checks for the absence of results when the search phrase does not 
        match any dialogue, confirming the precision of the search mechanism. 

        A successful test run indicates that the phrase search functionality is working 
        as expected, providing reliable results for both exact and non-exact phrase queries.
        """
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
        """

        Tests the functionality of searching phrases in text using a specific language configuration.

        This test case checks the phrase search functionality with a custom configuration, 
        in this case, French. It verifies that the search correctly identifies phrases 
        and that the order of words in the search query matters, as it should match 
        the exact phrase. If the phrase is found, it should return the corresponding 
        results; otherwise, it should return an empty list.

        The search query uses a specific configuration, which determines the language 
        and grammar rules used for searching, allowing for more accurate results in 
        different languages.

        """
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
        """
        Tests raw search functionality on database entries using a custom search configuration.

        This test case verifies that the SearchVector and SearchQuery functions can be used together to find matching entries based on a raw search query, and that the search results are filtered correctly according to the specified search configuration.

        The test searches for lines that contain both 'cadeaux' and 'beaux' using the French search configuration, and checks that the result matches the expected line.

        :param none:
        :return: none
        :raises AssertionError: If the search result does not match the expected line.
        """
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
        """
        Tests the functionality of full-text search using websearch syntax.

        This test case checks the correctness of search queries using various websearch 
        operators, including phrase searching, negation, and OR operations. It verifies 
        that search results match the expected sequences of objects.

        The test scenario covers the following use cases:
        - Searching for multiple phrases
        - Searching for phrases with negation
        - Searching using the OR operator with phrases and parentheses for grouping
        """
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
        """
        Tests the web search functionality with a custom configuration.

        This test case verifies that the search functionality returns the expected results when using a specific configuration.
        It checks that the search query with a negated term returns no results and that the search query with a phrase returns the expected result.
        The test uses a French configuration to annotate and filter objects based on their scene setting and dialogue.
        The expected results are validated using assertions to ensure the correctness of the search functionality.
        """
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
        """
        Tests configuring the search query from a field explicitly.

        This test ensures that search queries can be successfully configured 
        using explicit field settings, allowing for precise control over 
        the search process. It verifies that the search results are 
        correctly filtered according to the specified configuration.

        :raises AssertionError: if the search results do not match the expected sequence

        """
        searched = Line.objects.annotate(
            search=SearchVector(
                "scene__setting", "dialogue", config=F("dialogue_config")
            ),
        ).filter(search=SearchQuery("cadeaux", config=F("dialogue_config")))
        self.assertSequenceEqual(searched, [self.french])

    def test_config_from_field_implicit(self):
        """
        Tests that a config is correctly loaded from a field when searching with an implicit config.

        This test ensures that the SearchVector is correctly annotated with the 
        dialogue_config when the search query is applied, and that the expected 
        result is returned. In this case, it checks that searching for 'cadeaux' 
        returns the expected object, verifying that the implicit config is 
        applied as expected during the search operation.
        """
        searched = Line.objects.annotate(
            search=SearchVector(
                "scene__setting", "dialogue", config=F("dialogue_config")
            ),
        ).filter(search="cadeaux")
        self.assertSequenceEqual(searched, [self.french])


class TestCombinations(GrailTestData, PostgreSQLTestCase):
    def test_vector_add(self):
        """
        Test the vector addition feature of the database search functionality.

        This test case annotates a queryset of Line objects with a SearchVector that combines two fields: the setting of the scene and the name of the character.
        It then filters the results to include only those where the search vector matches the term 'bedemir'.
        The test verifies that the resulting queryset contains the expected Line objects, demonstrating the correct functionality of the search vector addition.
        """
        searched = Line.objects.annotate(
            search=SearchVector("scene__setting") + SearchVector("character__name"),
        ).filter(search="bedemir")
        self.assertCountEqual(
            searched, [self.bedemir0, self.bedemir1, self.crowd, self.witch, self.duck]
        )

    def test_vector_add_multi(self):
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
        """
        Tests that attempting to combine a SearchVector with a None value raises a TypeError, as SearchVectors can only be combined with other SearchVector instances.
        """
        msg = (
            "SearchVector can only be combined with other SearchVector "
            "instances, got NoneType."
        )
        with self.assertRaisesMessage(TypeError, msg):
            Line.objects.filter(dialogue__search=None + SearchVector("character__name"))

    def test_combine_different_vector_configs(self):
        """

        Tests combining different vector configurations for text search.

        This test checks if search queries can be executed using multiple search vector configurations.
        It verifies that the search results match the expected list of objects when using both English and French search configurations.
        The test case covers searching for terms in multiple languages and ensures that the results are correctly filtered and returned.

        """
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
        """
        Test the query functionality with 'and' operator.

        This function verifies that the full-text search functionality is working correctly when searching for multiple terms using the 'and' operator.
        It searches for lines that contain both 'bedemir' and 'scales' in their scene setting or dialogue, 
        and checks that the result matches the expected outcome, which is a single line containing the term 'bedemir0'. 

        This test case ensures that the correct results are returned when filtering using multiple search queries joined by the 'and' operator.
        """
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
        """
        Tests the functionality of querying multiple search terms using an OR operator.

        This function verifies that the database is properly searched when given a 
        disjunction of search queries, confirming that all relevant records are 
        retrieved as expected. The test case specifically checks for the presence of 
        multiple search terms ('kneecaps', 'nostrils', 'Sir Robin') in the dialogue 
        of Line objects, ensuring the result set matches the anticipated list of 
        objects.
        """
        searched = Line.objects.filter(
            dialogue__search=SearchQuery("kneecaps")
            | SearchQuery("nostrils")
            | SearchQuery("Sir Robin")
        )
        self.assertCountEqual(searched, [self.verse1, self.verse2, self.verse0])

    def test_query_invert(self):
        """

         Tests that querying with an inverted SearchQuery correctly retrieves matching objects.

         This test case verifies that searching for dialogue that does not contain the specified term ('kneecaps') 
         returns the expected results. The function checks if the count of objects returned by the query 
         is equal to the count of expected objects, ensuring that the query behaves as expected.

        """
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
        """

        Tests the combination of a raw phrase search query with a simple search configuration.

        This test case verifies that the search functionality correctly retrieves objects 
        -containing a raw phrase 'burn:*' or a phrase 'rode forth from Camelot' by 
        combining the results of both search queries using the default text search 
        configuration. The expected outcome is a list of objects containing the 
        combined search results.

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
        """

        Tests the ranking of search results for a specific character's dialogue.

        Verifies that the search results are ordered by relevance, with the most relevant
        result appearing first. In this case, the search query is 'brave sir robin' and
        the character is the minstrel.

        """
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
        """

        Test weighting of vectors in search queries.

        This test case examines how different weightings of search vectors impact the ranking of search results.
        Two search vectors are created, each combining 'dialogue' and 'character__name' fields with different weightings.
        The test verifies that the weighted search correctly orders the results based on the assigned weights.

        The test covers two scenarios:
        - One where 'dialogue' is weighted higher than 'character__name'
        - One where 'character__name' is weighted higher than 'dialogue'

        In each scenario, the test checks that the top results match the expected ordering based on the weights assigned.

        """
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
        """
        Tests the ranking of search results using custom weights.

        This test case checks if the ranking of search results is correctly applied
        when using custom weights for different fields in the search vector.
        It verifies that the results are ordered by their rank in descending order
        and that the correct objects are returned.

        The test queries the database for lines in a specific scene, using a search
        query with custom weights assigned to the 'dialogue' and 'character__name' fields.
        The weights are used to influence the ranking of the search results, with higher
        weights giving more importance to the corresponding field.

        The test then asserts that the top-ranked results match the expected objects,
        demonstrating that the custom weights are correctly applied to the search ranking.
        """
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
        """
        Test the ranking and chaining of search results for a specific query.

        This test case verifies that the search functionality correctly ranks and filters results based on the relevance to the search query.
        In this scenario, the query is 'brave sir robin' and the test checks that the function returns the expected sequence of search results that have a rank greater than 0.3, ensuring the most relevant results are returned.

        The test uses a specific character (the minstrel) and a predefined verse (verse0) to validate the correctness of the search functionality.
        """
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

        Tests the ranking functionality with normalization.

        This test case creates a new verse with dialogue containing the search query,
        then searches for lines spoken by a specific character using a search query with normalization.
        The result set is ordered by the relevance rank and verified to match the expected sequence.

        The test ensures that the ranking function correctly calculates the relevance of each line
        based on the search query and normalization factor, and returns them in the correct order.

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
        ..:Tests the string representation of various search queries, including negations, conjunctions, and disjunctions, to ensure they are converted to the expected string format.


            Args:
                None

            Returns:
                None

            Raises:
                AssertionError: If any of the search query string representations do not match the expected format.
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
        """

        Tests the SearchHeadline functionality with untyped arguments.

        Verifies that the headline search functionality correctly annotates and retrieves
        a Line object based on a given search term. The test checks that the annotated
        headline field matches the expected text with the searched term highlighted.

        """
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
        """

        Tests the SearchHeadline feature with a specified configuration.

        This test case verifies that the SearchHeadline functionality correctly annotates
        a Line object with a highlighted headline, based on a provided search query and
        language configuration. It checks if the resulting headline matches the expected
        output.

        The test focuses on the French configuration, ensuring that the search query and
        highlighting rules are applied correctly for this language.

        """
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

        Tests the options for the headline separator feature.

        This test checks that the SearchHeadline annotation correctly highlights search terms 
        in a dialogue. It verifies that the start and stop selectors, such as HTML span tags, 
        are properly applied to the highlighted terms in the resulting headline. The test 
        ensures that the headline accurately reflects the search query and the specified 
        formatting options.

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
