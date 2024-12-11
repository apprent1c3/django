import collections.abc
from unittest import mock

from django.db.models import TextChoices
from django.test import SimpleTestCase
from django.utils.choices import (
    BaseChoiceIterator,
    CallableChoiceIterator,
    flatten_choices,
    normalize_choices,
)
from django.utils.translation import gettext_lazy as _


class SimpleChoiceIterator(BaseChoiceIterator):
    def __iter__(self):
        return ((i, f"Item #{i}") for i in range(1, 4))


class ChoiceIteratorTests(SimpleTestCase):
    def test_not_implemented_error_on_missing_iter(self):
        """
        Tests that a NotImplementedError is raised when a subclass of BaseChoiceIterator does not implement the __iter__() method.

        This test case ensures that any subclass of BaseChoiceIterator provides a valid implementation of the __iter__() method, which is a required interface for iteration. If this method is not implemented, a NotImplementedError is expected to be raised with a message indicating the requirement for implementation.

        The test creates an invalid iterator class that inherits from BaseChoiceIterator but does not provide an implementation for __iter__(), and then verifies that attempting to iterate over an instance of this class results in the expected error being raised.
        """
        class InvalidChoiceIterator(BaseChoiceIterator):
            pass  # Not overriding __iter__().

        msg = "BaseChoiceIterator subclasses must implement __iter__()."
        with self.assertRaisesMessage(NotImplementedError, msg):
            iter(InvalidChoiceIterator())

    def test_eq(self):
        unrolled = [(1, "Item #1"), (2, "Item #2"), (3, "Item #3")]
        self.assertEqual(SimpleChoiceIterator(), unrolled)
        self.assertEqual(unrolled, SimpleChoiceIterator())

    def test_eq_instances(self):
        self.assertEqual(SimpleChoiceIterator(), SimpleChoiceIterator())

    def test_not_equal_subset(self):
        self.assertNotEqual(SimpleChoiceIterator(), [(1, "Item #1"), (2, "Item #2")])

    def test_not_equal_superset(self):
        self.assertNotEqual(
            SimpleChoiceIterator(),
            [(1, "Item #1"), (2, "Item #2"), (3, "Item #3"), None],
        )

    def test_getitem(self):
        choices = SimpleChoiceIterator()
        for i, expected in [(0, (1, "Item #1")), (-1, (3, "Item #3"))]:
            with self.subTest(index=i):
                self.assertEqual(choices[i], expected)

    def test_getitem_indexerror(self):
        choices = SimpleChoiceIterator()
        for i in (4, -4):
            with self.subTest(index=i):
                with self.assertRaises(IndexError) as ctx:
                    choices[i]
                self.assertTrue(str(ctx.exception).endswith("index out of range"))


class FlattenChoicesTests(SimpleTestCase):
    def test_empty(self):
        def generator():
            yield from ()

        for choices in ({}, [], (), set(), frozenset(), generator(), None, ""):
            with self.subTest(choices=choices):
                result = flatten_choices(choices)
                self.assertIsInstance(result, collections.abc.Generator)
                self.assertEqual(list(result), [])

    def test_non_empty(self):
        choices = [
            ("C", _("Club")),
            ("D", _("Diamond")),
            ("H", _("Heart")),
            ("S", _("Spade")),
        ]
        result = flatten_choices(choices)
        self.assertIsInstance(result, collections.abc.Generator)
        self.assertEqual(list(result), choices)

    def test_nested_choices(self):
        """

        Flattens a nested list of choices into a single list of choices.

        The function takes a list of tuples, where each tuple contains a group name and a list of choices.
        It returns a generator that yields each choice in the nested list, without their group names.

        This function is useful for simplifying complex choice lists, where each choice is a tuple containing the choice value and its human-readable name.

        The function does not modify the original list and does not include the group names in the output.

        """
        choices = [
            ("Audio", [("vinyl", _("Vinyl")), ("cd", _("CD"))]),
            ("Video", [("vhs", _("VHS Tape")), ("dvd", _("DVD"))]),
            ("unknown", _("Unknown")),
        ]
        expected = [
            ("vinyl", _("Vinyl")),
            ("cd", _("CD")),
            ("vhs", _("VHS Tape")),
            ("dvd", _("DVD")),
            ("unknown", _("Unknown")),
        ]
        result = flatten_choices(choices)
        self.assertIsInstance(result, collections.abc.Generator)
        self.assertEqual(list(result), expected)


class NormalizeFieldChoicesTests(SimpleTestCase):
    expected = [
        ("C", _("Club")),
        ("D", _("Diamond")),
        ("H", _("Heart")),
        ("S", _("Spade")),
    ]
    expected_nested = [
        ("Audio", [("vinyl", _("Vinyl")), ("cd", _("CD"))]),
        ("Video", [("vhs", _("VHS Tape")), ("dvd", _("DVD"))]),
        ("unknown", _("Unknown")),
    ]
    invalid = [
        1j,
        123,
        123.45,
        "invalid",
        b"invalid",
        _("invalid"),
        object(),
        None,
        True,
        False,
    ]
    invalid_iterable = [
        # Special cases of a string-likes which would unpack incorrectly.
        ["ab"],
        [b"ab"],
        [_("ab")],
        # Non-iterable items or iterable items with incorrect number of
        # elements that cannot be unpacked.
        [123],
        [("value",)],
        [("value", "label", "other")],
    ]
    invalid_nested = [
        # Nested choices can only be two-levels deep, so return callables,
        # mappings, iterables, etc. at deeper levels unmodified.
        [("Group", [("Value", lambda: "Label")])],
        [("Group", [("Value", {"Label 1?": "Label 2?"})])],
        [("Group", [("Value", [("Label 1?", "Label 2?")])])],
    ]

    def test_empty(self):
        def generator():
            yield from ()

        for choices in ({}, [], (), set(), frozenset(), generator()):
            with self.subTest(choices=choices):
                self.assertEqual(normalize_choices(choices), [])

    def test_choices(self):
        """
        Tests the normalization of choices for the Medal class, which is based on Django's TextChoices model.

        The test ensures that the normalize_choices function correctly converts the choices defined in the Medal class into a list of tuples, where each tuple contains the choice's value and its human-readable representation. 

        The test case covers the choices for gold, silver, and bronze medals, and verifies that the output of the normalize_choices function matches the expected list of normalized choices.
        """
        class Medal(TextChoices):
            GOLD = "GOLD", _("Gold")
            SILVER = "SILVER", _("Silver")
            BRONZE = "BRONZE", _("Bronze")

        expected = [
            ("GOLD", _("Gold")),
            ("SILVER", _("Silver")),
            ("BRONZE", _("Bronze")),
        ]
        self.assertEqual(normalize_choices(Medal), expected)

    def test_callable(self):
        """
        Tests whether the normalize_choices function is callable and returns the expected output.

        The function checks if the supplied callable is executed as expected and its output matches the predefined result.
        It verifies that the callable is not invoked prematurely and that its invocation occurs only once when needed.
        The test ensures that the function returns an instance of CallableChoiceIterator and that its contents match the expected value.
        """
        def get_choices():
            return {
                "C": _("Club"),
                "D": _("Diamond"),
                "H": _("Heart"),
                "S": _("Spade"),
            }

        get_choices_spy = mock.Mock(wraps=get_choices)
        output = normalize_choices(get_choices_spy)

        get_choices_spy.assert_not_called()
        self.assertIsInstance(output, CallableChoiceIterator)
        self.assertEqual(output, self.expected)
        get_choices_spy.assert_called_once()

    def test_mapping(self):
        """
        Tests the mapping of choices to their expected normalized values.

        Verifies that the function correctly maps a given set of choices, 
        represented as a dictionary with keys and translated values, 
        to the expected normalized output. 

        The test covers a specific set of choices related to card suits, 
        ensuring the function behaves as expected for this use case.

        :raises AssertionError: if the normalized choices do not match the expected output
        """
        choices = {
            "C": _("Club"),
            "D": _("Diamond"),
            "H": _("Heart"),
            "S": _("Spade"),
        }
        self.assertEqual(normalize_choices(choices), self.expected)

    def test_iterable(self):
        choices = [
            ("C", _("Club")),
            ("D", _("Diamond")),
            ("H", _("Heart")),
            ("S", _("Spade")),
        ]
        self.assertEqual(normalize_choices(choices), self.expected)

    def test_iterator(self):
        def generator():
            """
            Generates a sequence of tuples representing the suits in a standard deck of playing cards.

            Each tuple contains a single character code for the suit and its human-readable name.

            The generator yields the suits in the following order: Club, Diamond, Heart, Spade.

            :rtype: generator
            :returns: A generator yielding tuples of (str, str) containing the suit code and name.
            """
            yield "C", _("Club")
            yield "D", _("Diamond")
            yield "H", _("Heart")
            yield "S", _("Spade")

        choices = generator()
        self.assertEqual(normalize_choices(choices), self.expected)

    def test_nested_callable(self):
        """
        Tests the normalization of nested callable choices.

        Normalization of choices is expected to handle nested callables correctly, 
        by not calling them during the initial normalization process. The function 
        being tested should return a CallableChoiceIterator object, which contains 
        the nested choices. The test verifies that the nested callable is not 
        called until its contents are actually needed.

        The test case covers a scenario where the choices are structured into 
        different media types, with each type containing its own set of choices.
        The expected output is compared with a predefined result to ensure the 
        correctness of the normalization process.
        """
        def get_audio_choices():
            return [("vinyl", _("Vinyl")), ("cd", _("CD"))]

        def get_video_choices():
            return [("vhs", _("VHS Tape")), ("dvd", _("DVD"))]

        def get_media_choices():
            return [
                ("Audio", get_audio_choices),
                ("Video", get_video_choices),
                ("unknown", _("Unknown")),
            ]

        get_media_choices_spy = mock.Mock(wraps=get_media_choices)
        output = normalize_choices(get_media_choices_spy)

        get_media_choices_spy.assert_not_called()
        self.assertIsInstance(output, CallableChoiceIterator)
        self.assertEqual(output, self.expected_nested)
        get_media_choices_spy.assert_called_once()

    def test_nested_mapping(self):
        choices = {
            "Audio": {"vinyl": _("Vinyl"), "cd": _("CD")},
            "Video": {"vhs": _("VHS Tape"), "dvd": _("DVD")},
            "unknown": _("Unknown"),
        }
        self.assertEqual(normalize_choices(choices), self.expected_nested)

    def test_nested_iterable(self):
        """
        Tests the normalization of nested iterables containing choices.

        This function verifies that the normalization process correctly handles nested iterables
        with multiple levels of choices, including tuples and strings, and returns the expected output.

        The test case includes a mix of choices with sub-options (e.g., 'Audio' with 'vinyl' and 'cd') 
        and standalone choices (e.g., 'unknown'). The goal is to ensure that the normalization 
        function correctly flattens and processes these complex choices, resulting in a 
        well-structured output that matches the predefined expectations.
        """
        choices = [
            ("Audio", [("vinyl", _("Vinyl")), ("cd", _("CD"))]),
            ("Video", [("vhs", _("VHS Tape")), ("dvd", _("DVD"))]),
            ("unknown", _("Unknown")),
        ]
        self.assertEqual(normalize_choices(choices), self.expected_nested)

    def test_nested_iterator(self):
        """
        Tests the normalization of nested choices, ensuring that the output matches the expected structure for nested options.

        The function generates various test cases for media choices, including audio and video formats, 
        and then checks if the normalize_choices function can correctly process these nested options, 
        resulting in the expected output. This includes verifying that the nested structure is preserved 
        and the choices are correctly labeled and formatted.
        """
        def generate_audio_choices():
            """
            Generates a sequence of audio format choices as tuples.

            Each tuple contains a machine-readable identifier (e.g. 'vinyl', 'cd') and a human-readable label (e.g. 'Vinyl', 'CD').

            The function is designed to be used in iteration, allowing callers to easily populate dropdowns, menus, or other user interfaces with a list of available audio formats.

            Returns:
                A generator of tuples, where each tuple contains an audio format identifier and its corresponding label.

            """
            yield "vinyl", _("Vinyl")
            yield "cd", _("CD")

        def generate_video_choices():
            """
            Generate a sequence of video format choices.

            This function produces a series of tuples, each containing a unique identifier and a human-readable label for a video format. The identifiers and labels are suitable for use in user interfaces, such as dropdown menus or selection lists.

            The generated choices include the most common video formats. 

            :rtype: Iterator[Tuple[str, str]] 
            :yield: A tuple containing a video format identifier and its corresponding label.
            """
            yield "vhs", _("VHS Tape")
            yield "dvd", _("DVD")

        def generate_media_choices():
            yield "Audio", generate_audio_choices()
            yield "Video", generate_video_choices()
            yield "unknown", _("Unknown")

        choices = generate_media_choices()
        self.assertEqual(normalize_choices(choices), self.expected_nested)

    def test_callable_non_canonical(self):
        # Canonical form is list of 2-tuple, but nested lists should work.
        """

        Tests that the normalize_choices function handles non-canonical callable inputs correctly.

        The function is expected to not call the input callable initially, but instead return a CallableChoiceIterator object.
        This object should contain the expected choices when iterated over, at which point the input callable is called.

        The test verifies that the input callable is not called prematurely and is called only once when the iterator is used.

        """
        def get_choices():
            return [
                ["C", _("Club")],
                ["D", _("Diamond")],
                ["H", _("Heart")],
                ["S", _("Spade")],
            ]

        get_choices_spy = mock.Mock(wraps=get_choices)
        output = normalize_choices(get_choices_spy)

        get_choices_spy.assert_not_called()
        self.assertIsInstance(output, CallableChoiceIterator)
        self.assertEqual(output, self.expected)
        get_choices_spy.assert_called_once()

    def test_iterable_non_canonical(self):
        # Canonical form is list of 2-tuple, but nested lists should work.
        choices = [
            ["C", _("Club")],
            ["D", _("Diamond")],
            ["H", _("Heart")],
            ["S", _("Spade")],
        ]
        self.assertEqual(normalize_choices(choices), self.expected)

    def test_iterator_non_canonical(self):
        # Canonical form is list of 2-tuple, but nested lists should work.
        """
        Tests the normalize_choices function with a non-canonical iterator.

        This test case verifies that the normalize_choices function can handle an iterator
        that produces non-canonical choices and returns the expected normalized choices.

        The test uses a generator that yields a sequence of card suit choices and their
        corresponding translations, and checks that the normalized choices match the
        expected output. The test covers a scenario where the input choices are not in a
        standard format, ensuring that the function is robust and can handle different
        types of input iterators.
        """
        def generator():
            """
            Generates a sequence of tuples representing the suits in a standard deck of playing cards.
            Each tuple contains a single character code for the suit (e.g., 'C', 'D', 'H', 'S') and its corresponding full name.
            The full names are translated strings, allowing for localization support.
            The generator yields the suits in a specific order: Club, Diamond, Heart, and Spade.
            """
            yield ["C", _("Club")]
            yield ["D", _("Diamond")]
            yield ["H", _("Heart")]
            yield ["S", _("Spade")]

        choices = generator()
        self.assertEqual(normalize_choices(choices), self.expected)

    def test_nested_callable_non_canonical(self):
        # Canonical form is list of 2-tuple, but nested lists should work.

        """

        Tests the normalization of nested callable choices.

        This test ensures that the normalize_choices function can handle choices that are 
        callable objects, which return lists of choices when invoked. The test case 
        specifically checks for the following:

        * The normalize_choices function does not prematurely invoke the callable choices.
        * The output of the normalize_choices function is an instance of CallableChoiceIterator.
        * The normalized choices match the expected output.

        The test case utilizes mock objects to verify that the callable choices are 
        invoked as expected.

        """
        def get_audio_choices():
            return [["vinyl", _("Vinyl")], ["cd", _("CD")]]

        def get_video_choices():
            return [["vhs", _("VHS Tape")], ["dvd", _("DVD")]]

        def get_media_choices():
            return [
                ["Audio", get_audio_choices],
                ["Video", get_video_choices],
                ["unknown", _("Unknown")],
            ]

        get_media_choices_spy = mock.Mock(wraps=get_media_choices)
        output = normalize_choices(get_media_choices_spy)

        get_media_choices_spy.assert_not_called()
        self.assertIsInstance(output, CallableChoiceIterator)
        self.assertEqual(output, self.expected_nested)
        get_media_choices_spy.assert_called_once()

    def test_nested_iterable_non_canonical(self):
        # Canonical form is list of 2-tuple, but nested lists should work.
        """
        Tests the normalization of a non-canonical nested iterable of choices.

        The function checks if the normalize_choices function correctly transforms a nested list
        of choices into a standardized format, handling nested lists and tuples, as well as
        translatable display values. The test specifically verifies the case where the input
        choices are organized in a hierarchical structure, such as media types with sub-options.

        The expected output should match the predefined expected_nested result, ensuring that
        the normalization process preserves the original structure and content of the input choices.
        """
        choices = [
            ["Audio", [["vinyl", _("Vinyl")], ["cd", _("CD")]]],
            ["Video", [["vhs", _("VHS Tape")], ["dvd", _("DVD")]]],
            ["unknown", _("Unknown")],
        ]
        self.assertEqual(normalize_choices(choices), self.expected_nested)

    def test_nested_iterator_non_canonical(self):
        # Canonical form is list of 2-tuple, but nested lists should work.
        def generator():
            """

            Generates a sequence of media categories with their corresponding formats.

            This function yields tuples, where the first element is the category name and the second element is either a list of tuples containing the format code and its human-readable description, or a single human-readable description for categories with no specific formats.

            The generated categories include audio and video formats, as well as an 'unknown' category.

            Yields:
                list: A list containing the category name and its formats or description.

            """
            yield ["Audio", [["vinyl", _("Vinyl")], ["cd", _("CD")]]]
            yield ["Video", [["vhs", _("VHS Tape")], ["dvd", _("DVD")]]]
            yield ["unknown", _("Unknown")]

        choices = generator()
        self.assertEqual(normalize_choices(choices), self.expected_nested)

    def test_nested_mixed_mapping_and_iterable(self):
        # Although not documented, as it's better to stick to either mappings
        # or iterables, nesting of mappings within iterables and vice versa
        # works and is likely to occur in the wild. This is supported by the
        # recursive call to `normalize_choices()` which will normalize nested
        # choices.
        """
        Tests the normalization of choices that contain a mix of mappings and iterables.

            This function verifies that the normalize_choices function can handle
            complex choices that include both dictionaries and lists of tuples, as
            well as simple string values. It checks that the normalized output
            matches the expected result for two different input formats: a
            dictionary with list values and a list of tuples with dictionary values.

            The goal of this test is to ensure that the normalize_choices function
            can correctly handle nested and mixed data structures, providing a
            standardized output regardless of the input format. This is important
            for maintaining consistency in the application, especially when dealing
            with user-input data or data from external sources that may have varying
            formats.
        """
        choices = {
            "Audio": [("vinyl", _("Vinyl")), ("cd", _("CD"))],
            "Video": [("vhs", _("VHS Tape")), ("dvd", _("DVD"))],
            "unknown": _("Unknown"),
        }
        self.assertEqual(normalize_choices(choices), self.expected_nested)
        choices = [
            ("Audio", {"vinyl": _("Vinyl"), "cd": _("CD")}),
            ("Video", {"vhs": _("VHS Tape"), "dvd": _("DVD")}),
            ("unknown", _("Unknown")),
        ]
        self.assertEqual(normalize_choices(choices), self.expected_nested)

    def test_iterable_set(self):
        # Although not documented, as sets are unordered which results in
        # randomised order in form fields, passing a set of 2-tuples works.
        # Consistent ordering of choices on model fields in migrations is
        # enforced by the migrations serializer.
        """
        Test that the normalize_choices function correctly handles an iterable set of choices. 

        The test verifies that after normalizing a set of choices, which includes tuples representing card suits, the result matches the expected outcome. The comparison is done after sorting the resulting choices to ensure a consistent order, regardless of the original order in the input set.
        """
        choices = {
            ("C", _("Club")),
            ("D", _("Diamond")),
            ("H", _("Heart")),
            ("S", _("Spade")),
        }
        self.assertEqual(sorted(normalize_choices(choices)), sorted(self.expected))

    def test_unsupported_values_returned_unmodified(self):
        # Unsupported values must be returned unmodified for model system check
        # to work correctly.
        """
        Tests whether the normalize_choices function returns unsupported values unmodified.

        This test verifies that the function does not modify or alter the input when it encounters values that are not supported or recognized. It checks a variety of invalid inputs, including single values, iterable collections, and nested structures, to ensure that they are all returned in their original form without any changes.
        """
        for value in self.invalid + self.invalid_iterable + self.invalid_nested:
            with self.subTest(value=value):
                self.assertEqual(normalize_choices(value), value)

    def test_unsupported_values_from_callable_returned_unmodified(self):
        """

        Tests that unsupported values returned from a callable are left unmodified by the normalize_choices function.

        This test iterates over a range of invalid input values, checking that the normalize_choices function does not attempt to alter them when they are returned from a callable. It verifies that the output of the function remains identical to the original input value.

        """
        for value in self.invalid_iterable + self.invalid_nested:
            with self.subTest(value=value):
                self.assertEqual(normalize_choices(lambda: value), value)

    def test_unsupported_values_from_iterator_returned_unmodified(self):
        for value in self.invalid_nested:
            with self.subTest(value=value):
                self.assertEqual(
                    normalize_choices((lambda: (yield from value))()),
                    value,
                )
