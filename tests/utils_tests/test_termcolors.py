import unittest

from django.utils.termcolors import (
    DARK_PALETTE,
    DEFAULT_PALETTE,
    LIGHT_PALETTE,
    NOCOLOR_PALETTE,
    PALETTES,
    colorize,
    parse_color_setting,
)


class TermColorTests(unittest.TestCase):
    def test_empty_string(self):
        self.assertEqual(parse_color_setting(""), PALETTES[DEFAULT_PALETTE])

    def test_simple_palette(self):
        """
        Tests the functionality of the color palette parsing.

        This test case verifies that the parse_color_setting function correctly 
        returns the expected color palettes for 'light' and 'dark' themes and 
        returns None when an invalid theme ('nocolor') is provided.

        The test covers the following scenarios:
            - Parsing of the 'light' theme
            - Parsing of the 'dark' theme
            - Parsing of an invalid theme ('nocolor')
        """
        self.assertEqual(parse_color_setting("light"), PALETTES[LIGHT_PALETTE])
        self.assertEqual(parse_color_setting("dark"), PALETTES[DARK_PALETTE])
        self.assertIsNone(parse_color_setting("nocolor"))

    def test_fg(self):
        self.assertEqual(
            parse_color_setting("error=green"),
            dict(PALETTES[NOCOLOR_PALETTE], ERROR={"fg": "green"}),
        )

    def test_fg_bg(self):
        self.assertEqual(
            parse_color_setting("error=green/blue"),
            dict(PALETTES[NOCOLOR_PALETTE], ERROR={"fg": "green", "bg": "blue"}),
        )

    def test_fg_opts(self):
        self.assertEqual(
            parse_color_setting("error=green,blink"),
            dict(PALETTES[NOCOLOR_PALETTE], ERROR={"fg": "green", "opts": ("blink",)}),
        )
        self.assertEqual(
            parse_color_setting("error=green,bold,blink"),
            dict(
                PALETTES[NOCOLOR_PALETTE],
                ERROR={"fg": "green", "opts": ("blink", "bold")},
            ),
        )

    def test_fg_bg_opts(self):
        """

        Tests the parsing of color settings for foreground and background options.

        This test case verifies that the function correctly interprets and splits the input string into its constituent parts, 
        including the foreground color, background color, and additional options. It ensures that the parsed output matches the 
        expected result, which is a dictionary containing the color settings for a specific palette. The test covers different 
        scenarios, including the presence of multiple options, to ensure the function behaves as expected in various situations.

        """
        self.assertEqual(
            parse_color_setting("error=green/blue,blink"),
            dict(
                PALETTES[NOCOLOR_PALETTE],
                ERROR={"fg": "green", "bg": "blue", "opts": ("blink",)},
            ),
        )
        self.assertEqual(
            parse_color_setting("error=green/blue,bold,blink"),
            dict(
                PALETTES[NOCOLOR_PALETTE],
                ERROR={"fg": "green", "bg": "blue", "opts": ("blink", "bold")},
            ),
        )

    def test_override_palette(self):
        self.assertEqual(
            parse_color_setting("light;error=green"),
            dict(PALETTES[LIGHT_PALETTE], ERROR={"fg": "green"}),
        )

    def test_override_nocolor(self):
        self.assertEqual(
            parse_color_setting("nocolor;error=green"),
            dict(PALETTES[NOCOLOR_PALETTE], ERROR={"fg": "green"}),
        )

    def test_reverse_override(self):
        self.assertEqual(
            parse_color_setting("error=green;light"), PALETTES[LIGHT_PALETTE]
        )

    def test_multiple_roles(self):
        self.assertEqual(
            parse_color_setting("error=green;sql_field=blue"),
            dict(
                PALETTES[NOCOLOR_PALETTE],
                ERROR={"fg": "green"},
                SQL_FIELD={"fg": "blue"},
            ),
        )

    def test_override_with_multiple_roles(self):
        self.assertEqual(
            parse_color_setting("light;error=green;sql_field=blue"),
            dict(
                PALETTES[LIGHT_PALETTE], ERROR={"fg": "green"}, SQL_FIELD={"fg": "blue"}
            ),
        )

    def test_empty_definition(self):
        """
        Tests the parsing of color settings for empty or incomplete definitions.

        This test case checks the behavior of the `parse_color_setting` function when given input strings 
        with no settings or missing values, ensuring that it correctly handles these edge cases and returns 
        the expected results, including `None` for invalid or empty input and the correct palette for a 
        valid but incomplete setting.
        """
        self.assertIsNone(parse_color_setting(";"))
        self.assertEqual(parse_color_setting("light;"), PALETTES[LIGHT_PALETTE])
        self.assertIsNone(parse_color_setting(";;;"))

    def test_empty_options(self):
        """
        Tests the parse_color_setting function with various empty options.

        This function verifies that the parse_color_setting function correctly handles
        empty options and returns the expected color palette with the specified error color.

        It checks three different scenarios: an option with a single value, an option with
        multiple empty values, and an option with a value and additional empty values
        followed by another option with a value. The expected output is a dictionary
        representing the color palette with the specified error color and options applied. 
        """
        self.assertEqual(
            parse_color_setting("error=green,"),
            dict(PALETTES[NOCOLOR_PALETTE], ERROR={"fg": "green"}),
        )
        self.assertEqual(
            parse_color_setting("error=green,,,"),
            dict(PALETTES[NOCOLOR_PALETTE], ERROR={"fg": "green"}),
        )
        self.assertEqual(
            parse_color_setting("error=green,,blink,,"),
            dict(PALETTES[NOCOLOR_PALETTE], ERROR={"fg": "green", "opts": ("blink",)}),
        )

    def test_bad_palette(self):
        self.assertIsNone(parse_color_setting("unknown"))

    def test_bad_role(self):
        """
        Tests the handling of invalid or unknown roles in the color setting parser.

        This test case checks the parser's behavior when confronted with an unrecognized role,
        ensuring it correctly ignores the unknown role and only applies valid settings.

        Specifically, it verifies that the parser returns None when given an unknown role with
        or without a color specification, and that it correctly applies a valid setting for
        a known role (in this case, 'sql_field') when paired with an unknown role.
        """
        self.assertIsNone(parse_color_setting("unknown="))
        self.assertIsNone(parse_color_setting("unknown=green"))
        self.assertEqual(
            parse_color_setting("unknown=green;sql_field=blue"),
            dict(PALETTES[NOCOLOR_PALETTE], SQL_FIELD={"fg": "blue"}),
        )

    def test_bad_color(self):
        """
        Tests the parse_color_setting function to ensure it correctly handles various color setting inputs.

        The function should return None if an invalid color is specified, and a dictionary representing the color palette if valid colors are provided.
        It also tests the parsing of different formats, including specifying a foreground color, background color, and additional options.
        The function should correctly merge the provided colors with the default palette, and handle cases where multiple colors are specified for a single setting.
        """
        self.assertIsNone(parse_color_setting("error="))
        self.assertEqual(
            parse_color_setting("error=;sql_field=blue"),
            dict(PALETTES[NOCOLOR_PALETTE], SQL_FIELD={"fg": "blue"}),
        )
        self.assertIsNone(parse_color_setting("error=unknown"))
        self.assertEqual(
            parse_color_setting("error=unknown;sql_field=blue"),
            dict(PALETTES[NOCOLOR_PALETTE], SQL_FIELD={"fg": "blue"}),
        )
        self.assertEqual(
            parse_color_setting("error=green/unknown"),
            dict(PALETTES[NOCOLOR_PALETTE], ERROR={"fg": "green"}),
        )
        self.assertEqual(
            parse_color_setting("error=green/blue/something"),
            dict(PALETTES[NOCOLOR_PALETTE], ERROR={"fg": "green", "bg": "blue"}),
        )
        self.assertEqual(
            parse_color_setting("error=green/blue/something,blink"),
            dict(
                PALETTES[NOCOLOR_PALETTE],
                ERROR={"fg": "green", "bg": "blue", "opts": ("blink",)},
            ),
        )

    def test_bad_option(self):
        self.assertEqual(
            parse_color_setting("error=green,unknown"),
            dict(PALETTES[NOCOLOR_PALETTE], ERROR={"fg": "green"}),
        )
        self.assertEqual(
            parse_color_setting("error=green,unknown,blink"),
            dict(PALETTES[NOCOLOR_PALETTE], ERROR={"fg": "green", "opts": ("blink",)}),
        )

    def test_role_case(self):
        """
        Tests the case sensitivity of role names in color settings parsing.

        Verifies that the function correctly handles role names regardless of their case, 
        ensuring that roles such as 'ERROR' and 'eRrOr' are treated equivalently and 
        result in the expected color setting configuration.

        The test checks for the role 'ERROR' being correctly parsed and its color set 
        to 'green', demonstrating the parsing function's case-insensitive behavior 
        and its ability to merge the role with the default color palette settings.
        """
        self.assertEqual(
            parse_color_setting("ERROR=green"),
            dict(PALETTES[NOCOLOR_PALETTE], ERROR={"fg": "green"}),
        )
        self.assertEqual(
            parse_color_setting("eRrOr=green"),
            dict(PALETTES[NOCOLOR_PALETTE], ERROR={"fg": "green"}),
        )

    def test_color_case(self):
        self.assertEqual(
            parse_color_setting("error=GREEN"),
            dict(PALETTES[NOCOLOR_PALETTE], ERROR={"fg": "green"}),
        )
        self.assertEqual(
            parse_color_setting("error=GREEN/BLUE"),
            dict(PALETTES[NOCOLOR_PALETTE], ERROR={"fg": "green", "bg": "blue"}),
        )
        self.assertEqual(
            parse_color_setting("error=gReEn"),
            dict(PALETTES[NOCOLOR_PALETTE], ERROR={"fg": "green"}),
        )
        self.assertEqual(
            parse_color_setting("error=gReEn/bLuE"),
            dict(PALETTES[NOCOLOR_PALETTE], ERROR={"fg": "green", "bg": "blue"}),
        )

    def test_opts_case(self):
        """
        Tests the parsing of color settings with varying case for the option specification.

        This function verifies that the `parse_color_setting` function correctly interprets the option specifier, 
        regardless of the case used, by comparing the parsed result to the expected output. The test case 
        specifically exercises the parsing of the 'error' setting with the 'BLINK' option specified in both 
        uppercase and mixed-case formats, ensuring that the resulting dictionary matches the expected 
        palette settings with the correct foreground color and option flags.
        """
        self.assertEqual(
            parse_color_setting("error=green,BLINK"),
            dict(PALETTES[NOCOLOR_PALETTE], ERROR={"fg": "green", "opts": ("blink",)}),
        )
        self.assertEqual(
            parse_color_setting("error=green,bLiNk"),
            dict(PALETTES[NOCOLOR_PALETTE], ERROR={"fg": "green", "opts": ("blink",)}),
        )

    def test_colorize_empty_text(self):
        """
        Tests the colorize function with empty or None text inputs.

         This function checks the behavior of the colorize function when given no text to colorize.
         It verifies the function returns the expected escape sequences for resetting the terminal color, 
         covering cases where the text is None or an empty string, with and without the 'noreset' option.
        """
        self.assertEqual(colorize(text=None), "\x1b[m\x1b[0m")
        self.assertEqual(colorize(text=""), "\x1b[m\x1b[0m")

        self.assertEqual(colorize(text=None, opts=("noreset",)), "\x1b[m")
        self.assertEqual(colorize(text="", opts=("noreset",)), "\x1b[m")

    def test_colorize_reset(self):
        self.assertEqual(colorize(text="", opts=("reset",)), "\x1b[0m")

    def test_colorize_fg_bg(self):
        self.assertEqual(colorize(text="Test", fg="red"), "\x1b[31mTest\x1b[0m")
        self.assertEqual(colorize(text="Test", bg="red"), "\x1b[41mTest\x1b[0m")
        # Ignored kwarg.
        self.assertEqual(colorize(text="Test", other="red"), "\x1b[mTest\x1b[0m")

    def test_colorize_opts(self):
        """
        Tests the colorize function with various options.

        This function verifies that the colorize function correctly applies different 
        ANSI escape codes to a given text based on the provided options.

        The test cases cover the application of styles such as bold and underscore, 
        as well as the handling of invalid options. The expected output for each test 
        case is compared to the actual output of the colorize function to ensure 
        correct behavior.

        The colorize function is expected to return a string with the applied ANSI 
        escape codes, and reset the styling back to default at the end of the string. 

        Parameters are not directly tested here, but the test function indirectly tests 
        that colorize function behaves according to its parameters, that are text and opts.
        """
        self.assertEqual(
            colorize(text="Test", opts=("bold", "underscore")),
            "\x1b[1;4mTest\x1b[0m",
        )
        self.assertEqual(
            colorize(text="Test", opts=("blink",)),
            "\x1b[5mTest\x1b[0m",
        )
        # Ignored opts.
        self.assertEqual(
            colorize(text="Test", opts=("not_an_option",)),
            "\x1b[mTest\x1b[0m",
        )
