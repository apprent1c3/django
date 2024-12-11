import os

from django.template import Context, Template
from django.test import SimpleTestCase, override_settings
from django.utils.translation import activate, get_language, trans_real

from .utils import POFileAssertionMixin

SAMPLEPROJECT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "sampleproject"
)
SAMPLEPROJECT_LOCALE = os.path.join(SAMPLEPROJECT_DIR, "locale")


@override_settings(LOCALE_PATHS=[SAMPLEPROJECT_LOCALE])
class FrenchTestCase(SimpleTestCase):
    """Tests using the French translations of the sampleproject."""

    PO_FILE = os.path.join(SAMPLEPROJECT_LOCALE, "fr", "LC_MESSAGES", "django.po")

    def setUp(self):
        self._language = get_language()
        self._translations = trans_real._translations
        activate("fr")

    def tearDown(self):
        trans_real._translations = self._translations
        activate(self._language)


class ExtractingStringsWithPercentSigns(POFileAssertionMixin, FrenchTestCase):
    """
    Tests the extracted string found in the gettext catalog.

    Percent signs are python formatted.

    These tests should all have an analogous translation tests below, ensuring
    the Python formatting does not persist through to a rendered template.
    """

    def setUp(self):
        """
        Set up the test environment by initializing the parent class and loading the contents of a gettext portable object (PO) file.

        This method is called before each test to ensure a clean and consistent state. It reads the PO file specified by `self.PO_FILE` and stores its contents in the `self.po_contents` attribute, making it available for use in subsequent tests.

        The PO file contents are loaded from disk to facilitate testing of functionality that relies on the file's contents, allowing for more accurate and reliable test results.
        """
        super().setUp()
        with open(self.PO_FILE) as fp:
            self.po_contents = fp.read()

    def test_trans_tag_with_percent_symbol_at_the_end(self):
        self.assertMsgId(
            "Literal with a percent symbol at the end %%", self.po_contents
        )

    def test_trans_tag_with_percent_symbol_in_the_middle(self):
        self.assertMsgId(
            "Literal with a percent %% symbol in the middle", self.po_contents
        )
        self.assertMsgId("It is 100%%", self.po_contents)

    def test_trans_tag_with_string_that_look_like_fmt_spec(self):
        """
        Tests translation tags containing strings that resemble format specifications.

        Verifies that translation tags with contents similar to string format specifications
        (e.g. '%s', '% o') are not misinterpreted as actual format specifiers, ensuring
        correct translation handling in such edge cases.
        """
        self.assertMsgId(
            "Looks like a str fmt spec %%s but should not be interpreted as such",
            self.po_contents,
        )
        self.assertMsgId(
            "Looks like a str fmt spec %% o but should not be interpreted as such",
            self.po_contents,
        )

    def test_adds_python_format_to_all_percent_signs(self):
        """
        Tests if the function correctly escapes all percent signs in a string by replacing them with the appropriate Python format to prevent incorrect string formatting. This includes checking for a single percent sign, multiple consecutive percent signs, and percent signs within a string that uses Python's named placeholders.
        """
        self.assertMsgId(
            "1 percent sign %%, 2 percent signs %%%%, 3 percent signs %%%%%%",
            self.po_contents,
        )
        self.assertMsgId(
            "%(name)s says: 1 percent sign %%, 2 percent signs %%%%", self.po_contents
        )


class RenderingTemplatesWithPercentSigns(FrenchTestCase):
    """
    Test rendering of templates that use percent signs.

    Ensures both translate and blocktranslate tags behave consistently.

    Refs #11240, #11966, #24257
    """

    def test_translates_with_a_percent_symbol_at_the_end(self):
        expected = "Littérale avec un symbole de pour cent à la fin %"

        trans_tpl = Template(
            "{% load i18n %}"
            '{% translate "Literal with a percent symbol at the end %" %}'
        )
        self.assertEqual(trans_tpl.render(Context({})), expected)

        block_tpl = Template(
            "{% load i18n %}{% blocktranslate %}Literal with a percent symbol at "
            "the end %{% endblocktranslate %}"
        )
        self.assertEqual(block_tpl.render(Context({})), expected)

    def test_translates_with_percent_symbol_in_the_middle(self):
        expected = "Pour cent littérale % avec un symbole au milieu"

        trans_tpl = Template(
            "{% load i18n %}"
            '{% translate "Literal with a percent % symbol in the middle" %}'
        )
        self.assertEqual(trans_tpl.render(Context({})), expected)

        block_tpl = Template(
            "{% load i18n %}{% blocktranslate %}Literal with a percent % symbol "
            "in the middle{% endblocktranslate %}"
        )
        self.assertEqual(block_tpl.render(Context({})), expected)

    def test_translates_with_percent_symbol_using_context(self):
        trans_tpl = Template('{% load i18n %}{% translate "It is 100%" %}')
        self.assertEqual(trans_tpl.render(Context({})), "Il est de 100%")
        trans_tpl = Template(
            '{% load i18n %}{% translate "It is 100%" context "female" %}'
        )
        self.assertEqual(trans_tpl.render(Context({})), "Elle est de 100%")

        block_tpl = Template(
            "{% load i18n %}{% blocktranslate %}It is 100%{% endblocktranslate %}"
        )
        self.assertEqual(block_tpl.render(Context({})), "Il est de 100%")
        block_tpl = Template(
            "{% load i18n %}"
            '{% blocktranslate context "female" %}It is 100%{% endblocktranslate %}'
        )
        self.assertEqual(block_tpl.render(Context({})), "Elle est de 100%")

    def test_translates_with_string_that_look_like_fmt_spec_with_trans(self):
        # tests "%s"
        """
        Tests translation functionality with strings that resemble format specification.

        Verifies that translation templates correctly interpret strings containing format specifiers,
        ensuring they are not mistakenly treated as actual format specifiers.

        Checks the functionality of both the ``translate`` and ``blocktranslate`` template tags,
        confirming they produce the expected translated output when given strings that contain percentage
        symbols followed by characters, such as ``%s`` or ``% o``.

        Ensures that the translation process preserves these sequences, translating the surrounding text
        while leaving the format-like sequences intact, thus maintaining the original intent and meaning
        of the text being translated.
        """
        expected = (
            "On dirait un spec str fmt %s mais ne devrait pas être interprété comme "
            "plus disponible"
        )
        trans_tpl = Template(
            '{% load i18n %}{% translate "Looks like a str fmt spec %s but '
            'should not be interpreted as such" %}'
        )
        self.assertEqual(trans_tpl.render(Context({})), expected)
        block_tpl = Template(
            "{% load i18n %}{% blocktranslate %}Looks like a str fmt spec %s but "
            "should not be interpreted as such{% endblocktranslate %}"
        )
        self.assertEqual(block_tpl.render(Context({})), expected)

        # tests "% o"
        expected = (
            "On dirait un spec str fmt % o mais ne devrait pas être interprété comme "
            "plus disponible"
        )
        trans_tpl = Template(
            "{% load i18n %}"
            '{% translate "Looks like a str fmt spec % o but should not be '
            'interpreted as such" %}'
        )
        self.assertEqual(trans_tpl.render(Context({})), expected)
        block_tpl = Template(
            "{% load i18n %}"
            "{% blocktranslate %}Looks like a str fmt spec % o but should not be "
            "interpreted as such{% endblocktranslate %}"
        )
        self.assertEqual(block_tpl.render(Context({})), expected)

    def test_translates_multiple_percent_signs(self):
        expected = (
            "1 % signe pour cent, signes %% 2 pour cent, trois signes de pourcentage "
            "%%%"
        )
        trans_tpl = Template(
            '{% load i18n %}{% translate "1 percent sign %, 2 percent signs %%, '
            '3 percent signs %%%" %}'
        )
        self.assertEqual(trans_tpl.render(Context({})), expected)
        block_tpl = Template(
            "{% load i18n %}{% blocktranslate %}1 percent sign %, 2 percent signs "
            "%%, 3 percent signs %%%{% endblocktranslate %}"
        )
        self.assertEqual(block_tpl.render(Context({})), expected)

        block_tpl = Template(
            "{% load i18n %}{% blocktranslate %}{{name}} says: 1 percent sign %, "
            "2 percent signs %%{% endblocktranslate %}"
        )
        self.assertEqual(
            block_tpl.render(Context({"name": "Django"})),
            "Django dit: 1 pour cent signe %, deux signes de pourcentage %%",
        )
