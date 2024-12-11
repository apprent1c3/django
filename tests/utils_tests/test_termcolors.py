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
        """

        Tests the parsing of foreground color options.

        This function verifies that the parse_color_setting function correctly interprets the
        foreground color and styling options (such as blink and bold) from a given string.

        The tests cover various scenarios, including the specification of a single styling option
        and multiple styling options, to ensure that the function behaves as expected in different cases.

        """
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

        Tests the functionality of parsing foreground and background color options.

        This test case verifies that the parse_color_setting function correctly interprets 
        color settings with foreground, background, and additional options. It checks that 
        the function returns a dictionary with the expected palette, foreground and background 
        colors, and styles.

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
        Tests the parsing of color settings with empty or partially filled definitions.

        Checks that the function correctly handles cases where the input string is
        empty, contains a single palette name, or consists of multiple consecutive
        semicolons. Verifies that the function returns the expected output for each
        scenario, including None when the input is invalid or ambiguous, and the
        corresponding color palette when a valid palette name is provided.
        """
        self.assertIsNone(parse_color_setting(";"))
        self.assertEqual(parse_color_setting("light;"), PALETTES[LIGHT_PALETTE])
        self.assertIsNone(parse_color_setting(";;;"))

    def test_empty_options(self):
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
        self.assertIsNone(parse_color_setting("unknown="))
        self.assertIsNone(parse_color_setting("unknown=green"))
        self.assertEqual(
            parse_color_setting("unknown=green;sql_field=blue"),
            dict(PALETTES[NOCOLOR_PALETTE], SQL_FIELD={"fg": "blue"}),
        )

    def test_bad_color(self):
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
        self.assertEqual(
            parse_color_setting("error=green,BLINK"),
            dict(PALETTES[NOCOLOR_PALETTE], ERROR={"fg": "green", "opts": ("blink",)}),
        )
        self.assertEqual(
            parse_color_setting("error=green,bLiNk"),
            dict(PALETTES[NOCOLOR_PALETTE], ERROR={"fg": "green", "opts": ("blink",)}),
        )

    def test_colorize_empty_text(self):
        self.assertEqual(colorize(text=None), "\x1b[m\x1b[0m")
        self.assertEqual(colorize(text=""), "\x1b[m\x1b[0m")

        self.assertEqual(colorize(text=None, opts=("noreset",)), "\x1b[m")
        self.assertEqual(colorize(text="", opts=("noreset",)), "\x1b[m")

    def test_colorize_reset(self):
        self.assertEqual(colorize(text="", opts=("reset",)), "\x1b[0m")

    def test_colorize_fg_bg(self):
        """

        Tests the colorize function to ensure it correctly applies ANSI escape codes for text colorization.

        This test case covers various scenarios, including setting the foreground and background colors of the text.
        It verifies that the function returns the expected string with applied ANSI escape codes.

        """
        self.assertEqual(colorize(text="Test", fg="red"), "\x1b[31mTest\x1b[0m")
        self.assertEqual(colorize(text="Test", bg="red"), "\x1b[41mTest\x1b[0m")
        # Ignored kwarg.
        self.assertEqual(colorize(text="Test", other="red"), "\x1b[mTest\x1b[0m")

    def test_colorize_opts(self):
        """

        Tests the colorize function's ability to apply various formatting options to a given text.

        The function is verified to correctly apply options such as 'bold' and 'underscore' 
        which result in the corresponding ANSI escape sequences being prepended and appended to the text.
        It also checks that invalid options are handled by resetting the text formatting.

        The test cases cover different scenarios to ensure the function behaves as expected, 
        including applying multiple options and handling unknown options.

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
