import datetime
import decimal
import gettext as gettext_module
import os
import pickle
import re
import tempfile
from contextlib import contextmanager
from importlib import import_module
from pathlib import Path
from unittest import mock

from asgiref.local import Local

from django import forms
from django.apps import AppConfig
from django.conf import settings
from django.conf.locale import LANG_INFO
from django.conf.urls.i18n import i18n_patterns
from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.utils import translation
from django.utils.formats import (
    date_format,
    get_format,
    iter_format_modules,
    localize,
    localize_input,
    reset_format_cache,
    sanitize_separators,
    sanitize_strftime_format,
    time_format,
)
from django.utils.numberformat import format as nformat
from django.utils.safestring import SafeString, mark_safe
from django.utils.translation import (
    activate,
    check_for_language,
    deactivate,
    get_language,
    get_language_bidi,
    get_language_from_request,
    get_language_info,
    gettext,
    gettext_lazy,
    ngettext,
    ngettext_lazy,
    npgettext,
    npgettext_lazy,
    pgettext,
    round_away_from_one,
    to_language,
    to_locale,
    trans_null,
    trans_real,
)
from django.utils.translation.reloader import (
    translation_file_changed,
    watch_for_translation_changes,
)
from django.utils.translation.trans_real import LANGUAGE_CODE_MAX_LENGTH

from .forms import CompanyForm, I18nForm, SelectDateForm
from .models import Company, TestModel

here = os.path.dirname(os.path.abspath(__file__))
extended_locale_paths = settings.LOCALE_PATHS + [
    os.path.join(here, "other", "locale"),
]


class AppModuleStub:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


@contextmanager
def patch_formats(lang, **settings):
    """

    Temporary patches locale-specific format settings for a given language.

    This context manager allows you to override format settings for a specific language.
    The changes are applied immediately and automatically reset when exiting the context,
    regardless of whether an exception occurred or not.

    Parameters
    ----------
    lang : str
        The language code to patch the format settings for.
    **settings
        Keyword arguments where the key is the setting name and the value is the new setting value.

    Examples
    --------
    To temporarily change the date format for English language to 'Y-m-d', use::

        with patch_formats('en', DATE_FORMAT='Y-m-d'):
            # Code that will use the patched date format

    """
    from django.utils.formats import _format_cache

    # Populate _format_cache with temporary values
    for key, value in settings.items():
        _format_cache[(key, lang)] = value
    try:
        yield
    finally:
        reset_format_cache()


class TranslationTests(SimpleTestCase):
    @translation.override("fr")
    def test_plural(self):
        """
        Test plurals with ngettext. French differs from English in that 0 is singular.
        """
        self.assertEqual(
            ngettext("%(num)d year", "%(num)d years", 0) % {"num": 0},
            "0 année",
        )
        self.assertEqual(
            ngettext("%(num)d year", "%(num)d years", 2) % {"num": 2},
            "2 années",
        )
        self.assertEqual(
            ngettext("%(size)d byte", "%(size)d bytes", 0) % {"size": 0}, "0 octet"
        )
        self.assertEqual(
            ngettext("%(size)d byte", "%(size)d bytes", 2) % {"size": 2}, "2 octets"
        )

    def test_plural_null(self):
        """

        Tests the handling of plural forms with a null value.

        This test function verifies that the ngettext function correctly handles pluralization
        when the input value is zero or non-zero, ensuring that the correct form of the word
        (year or years) is used in the output string.

        """
        g = trans_null.ngettext
        self.assertEqual(g("%(num)d year", "%(num)d years", 0) % {"num": 0}, "0 years")
        self.assertEqual(g("%(num)d year", "%(num)d years", 1) % {"num": 1}, "1 year")
        self.assertEqual(g("%(num)d year", "%(num)d years", 2) % {"num": 2}, "2 years")

    @override_settings(LOCALE_PATHS=extended_locale_paths)
    @translation.override("fr")
    def test_multiple_plurals_per_language(self):
        """
        Normally, French has 2 plurals. As other/locale/fr/LC_MESSAGES/django.po
        has a different plural equation with 3 plurals, this tests if those
        plural are honored.
        """
        self.assertEqual(ngettext("%d singular", "%d plural", 0) % 0, "0 pluriel1")
        self.assertEqual(ngettext("%d singular", "%d plural", 1) % 1, "1 singulier")
        self.assertEqual(ngettext("%d singular", "%d plural", 2) % 2, "2 pluriel2")
        french = trans_real.catalog()
        # Internal _catalog can query subcatalogs (from different po files).
        self.assertEqual(french._catalog[("%d singular", 0)], "%d singulier")
        self.assertEqual(french._catalog[("%(num)d hour", 0)], "%(num)d heure")

    def test_override(self):
        """

        Tests the language override functionality.

        This test case verifies that the current language can be overridden temporarily
        using a context manager, and that it returns to its original state afterwards.
        It also checks that overriding with None resets the language to the default state.
        The test ensures that language changes are properly isolated within the override
        block and that deactivation reverts the language to its original value.

        """
        activate("de")
        try:
            with translation.override("pl"):
                self.assertEqual(get_language(), "pl")
            self.assertEqual(get_language(), "de")
            with translation.override(None):
                self.assertIsNone(get_language())
                with translation.override("pl"):
                    pass
                self.assertIsNone(get_language())
            self.assertEqual(get_language(), "de")
        finally:
            deactivate()

    def test_override_decorator(self):
        @translation.override("pl")
        """

        Test the override decorator functionality.

        This function checks the behavior of the translation override decorator 
        in different scenarios. It verifies that the decorator correctly sets 
        the language to a specified value ('pl' in this case) and then resets 
        it to None. It also checks that the language remains unchanged after 
        the decorator is applied, ensuring that the override is properly 
        isolated. The test covers both the activation and deactivation of 
        translation overrides, ensuring that the language setting is restored 
        to its original state after the override is deactivated.

        """
        def func_pl():
            self.assertEqual(get_language(), "pl")

        @translation.override(None)
        def func_none():
            self.assertIsNone(get_language())

        try:
            activate("de")
            func_pl()
            self.assertEqual(get_language(), "de")
            func_none()
            self.assertEqual(get_language(), "de")
        finally:
            deactivate()

    def test_override_exit(self):
        """
        The language restored is the one used when the function was
        called, not the one used when the decorator was initialized (#23381).
        """
        activate("fr")

        @translation.override("pl")
        def func_pl():
            pass

        deactivate()

        try:
            activate("en")
            func_pl()
            self.assertEqual(get_language(), "en")
        finally:
            deactivate()

    def test_lazy_objects(self):
        """
        Format string interpolation should work with *_lazy objects.
        """
        s = gettext_lazy("Add %(name)s")
        d = {"name": "Ringo"}
        self.assertEqual("Add Ringo", s % d)
        with translation.override("de", deactivate=True):
            self.assertEqual("Ringo hinzuf\xfcgen", s % d)
            with translation.override("pl"):
                self.assertEqual("Dodaj Ringo", s % d)

        # It should be possible to compare *_lazy objects.
        s1 = gettext_lazy("Add %(name)s")
        self.assertEqual(s, s1)
        s2 = gettext_lazy("Add %(name)s")
        s3 = gettext_lazy("Add %(name)s")
        self.assertEqual(s2, s3)
        self.assertEqual(s, s2)
        s4 = gettext_lazy("Some other string")
        self.assertNotEqual(s, s4)

    def test_lazy_pickle(self):
        s1 = gettext_lazy("test")
        self.assertEqual(str(s1), "test")
        s2 = pickle.loads(pickle.dumps(s1))
        self.assertEqual(str(s2), "test")

    @override_settings(LOCALE_PATHS=extended_locale_paths)
    def test_ngettext_lazy(self):
        """
        Tests the functionality of the ngettext_lazy and npgettext_lazy functions.

        This function checks if the lazy translation of singular and plural forms is working correctly.
        It tests both simple and complex cases, including format strings with placeholders and context.
        The tests are run with the 'de' locale and verify that the correct translations are used for different numbers.

        The function also checks that the deferred translation works correctly when the count is provided as a string.
        It raises a KeyError when the dictionary used to format the string lacks the required key.

        The tests cover various scenarios to ensure that the ngettext_lazy and npgettext_lazy functions behave as expected.

        """
        simple_with_format = ngettext_lazy("%d good result", "%d good results")
        simple_context_with_format = npgettext_lazy(
            "Exclamation", "%d good result", "%d good results"
        )
        simple_without_format = ngettext_lazy("good result", "good results")
        with translation.override("de"):
            self.assertEqual(simple_with_format % 1, "1 gutes Resultat")
            self.assertEqual(simple_with_format % 4, "4 guten Resultate")
            self.assertEqual(simple_context_with_format % 1, "1 gutes Resultat!")
            self.assertEqual(simple_context_with_format % 4, "4 guten Resultate!")
            self.assertEqual(simple_without_format % 1, "gutes Resultat")
            self.assertEqual(simple_without_format % 4, "guten Resultate")

        complex_nonlazy = ngettext_lazy(
            "Hi %(name)s, %(num)d good result", "Hi %(name)s, %(num)d good results", 4
        )
        complex_deferred = ngettext_lazy(
            "Hi %(name)s, %(num)d good result",
            "Hi %(name)s, %(num)d good results",
            "num",
        )
        complex_context_nonlazy = npgettext_lazy(
            "Greeting",
            "Hi %(name)s, %(num)d good result",
            "Hi %(name)s, %(num)d good results",
            4,
        )
        complex_context_deferred = npgettext_lazy(
            "Greeting",
            "Hi %(name)s, %(num)d good result",
            "Hi %(name)s, %(num)d good results",
            "num",
        )
        with translation.override("de"):
            self.assertEqual(
                complex_nonlazy % {"num": 4, "name": "Jim"},
                "Hallo Jim, 4 guten Resultate",
            )
            self.assertEqual(
                complex_deferred % {"name": "Jim", "num": 1},
                "Hallo Jim, 1 gutes Resultat",
            )
            self.assertEqual(
                complex_deferred % {"name": "Jim", "num": 5},
                "Hallo Jim, 5 guten Resultate",
            )
            with self.assertRaisesMessage(KeyError, "Your dictionary lacks key"):
                complex_deferred % {"name": "Jim"}
            self.assertEqual(
                complex_context_nonlazy % {"num": 4, "name": "Jim"},
                "Willkommen Jim, 4 guten Resultate",
            )
            self.assertEqual(
                complex_context_deferred % {"name": "Jim", "num": 1},
                "Willkommen Jim, 1 gutes Resultat",
            )
            self.assertEqual(
                complex_context_deferred % {"name": "Jim", "num": 5},
                "Willkommen Jim, 5 guten Resultate",
            )
            with self.assertRaisesMessage(KeyError, "Your dictionary lacks key"):
                complex_context_deferred % {"name": "Jim"}

    @override_settings(LOCALE_PATHS=extended_locale_paths)
    def test_ngettext_lazy_format_style(self):
        """

        Tests the functionality of ngettext_lazy and npgettext_lazy when used with format strings.
        This test case checks the correctness of translation for both simple and complex format strings.
        It verifies that the correct singular or plural form is chosen based on the provided number,
        and that the translation is correctly applied when using different languages.
        The test also covers the use of context with npgettext_lazy and checks for correct error handling
        when a required format key is missing.

        """
        simple_with_format = ngettext_lazy("{} good result", "{} good results")
        simple_context_with_format = npgettext_lazy(
            "Exclamation", "{} good result", "{} good results"
        )

        with translation.override("de"):
            self.assertEqual(simple_with_format.format(1), "1 gutes Resultat")
            self.assertEqual(simple_with_format.format(4), "4 guten Resultate")
            self.assertEqual(simple_context_with_format.format(1), "1 gutes Resultat!")
            self.assertEqual(simple_context_with_format.format(4), "4 guten Resultate!")

        complex_nonlazy = ngettext_lazy(
            "Hi {name}, {num} good result", "Hi {name}, {num} good results", 4
        )
        complex_deferred = ngettext_lazy(
            "Hi {name}, {num} good result", "Hi {name}, {num} good results", "num"
        )
        complex_context_nonlazy = npgettext_lazy(
            "Greeting",
            "Hi {name}, {num} good result",
            "Hi {name}, {num} good results",
            4,
        )
        complex_context_deferred = npgettext_lazy(
            "Greeting",
            "Hi {name}, {num} good result",
            "Hi {name}, {num} good results",
            "num",
        )
        with translation.override("de"):
            self.assertEqual(
                complex_nonlazy.format(num=4, name="Jim"),
                "Hallo Jim, 4 guten Resultate",
            )
            self.assertEqual(
                complex_deferred.format(name="Jim", num=1),
                "Hallo Jim, 1 gutes Resultat",
            )
            self.assertEqual(
                complex_deferred.format(name="Jim", num=5),
                "Hallo Jim, 5 guten Resultate",
            )
            with self.assertRaisesMessage(KeyError, "Your dictionary lacks key"):
                complex_deferred.format(name="Jim")
            self.assertEqual(
                complex_context_nonlazy.format(num=4, name="Jim"),
                "Willkommen Jim, 4 guten Resultate",
            )
            self.assertEqual(
                complex_context_deferred.format(name="Jim", num=1),
                "Willkommen Jim, 1 gutes Resultat",
            )
            self.assertEqual(
                complex_context_deferred.format(name="Jim", num=5),
                "Willkommen Jim, 5 guten Resultate",
            )
            with self.assertRaisesMessage(KeyError, "Your dictionary lacks key"):
                complex_context_deferred.format(name="Jim")

    def test_ngettext_lazy_bool(self):
        self.assertTrue(ngettext_lazy("%d good result", "%d good results"))
        self.assertFalse(ngettext_lazy("", ""))

    def test_ngettext_lazy_pickle(self):
        s1 = ngettext_lazy("%d good result", "%d good results")
        self.assertEqual(s1 % 1, "1 good result")
        self.assertEqual(s1 % 8, "8 good results")
        s2 = pickle.loads(pickle.dumps(s1))
        self.assertEqual(s2 % 1, "1 good result")
        self.assertEqual(s2 % 8, "8 good results")

    @override_settings(LOCALE_PATHS=extended_locale_paths)
    def test_pgettext(self):
        """

        Tests plural and non-plural translation functions using the pgettext and npgettext functions.

        The function checks translation in the 'de' locale, where it verifies that:
        - Non-existent context returns the original string.
        - Translation occurs correctly for known contexts (e.g., month names and verbs).
        - Plural forms are correctly translated and formatted.

        This ensures that translation functionality works as expected in different contexts and locales.

        """
        trans_real._active = Local()
        trans_real._translations = {}
        with translation.override("de"):
            self.assertEqual(pgettext("unexisting", "May"), "May")
            self.assertEqual(pgettext("month name", "May"), "Mai")
            self.assertEqual(pgettext("verb", "May"), "Kann")
            self.assertEqual(
                npgettext("search", "%d result", "%d results", 4) % 4, "4 Resultate"
            )

    def test_empty_value(self):
        """Empty value must stay empty after being translated (#23196)."""
        with translation.override("de"):
            self.assertEqual("", gettext(""))
            s = mark_safe("")
            self.assertEqual(s, gettext(s))

    @override_settings(LOCALE_PATHS=extended_locale_paths)
    def test_safe_status(self):
        """
        Translating a string requiring no auto-escaping with gettext or pgettext
        shouldn't change the "safe" status.
        """
        trans_real._active = Local()
        trans_real._translations = {}
        s1 = mark_safe("Password")
        s2 = mark_safe("May")
        with translation.override("de", deactivate=True):
            self.assertIs(type(gettext(s1)), SafeString)
            self.assertIs(type(pgettext("month name", s2)), SafeString)
        self.assertEqual("aPassword", SafeString("a") + s1)
        self.assertEqual("Passworda", s1 + SafeString("a"))
        self.assertEqual("Passworda", s1 + mark_safe("a"))
        self.assertEqual("aPassword", mark_safe("a") + s1)
        self.assertEqual("as", mark_safe("a") + mark_safe("s"))

    def test_maclines(self):
        """
        Translations on files with Mac or DOS end of lines will be converted
        to unix EOF in .po catalogs.
        """
        ca_translation = trans_real.translation("ca")
        ca_translation._catalog["Mac\nEOF\n"] = "Catalan Mac\nEOF\n"
        ca_translation._catalog["Win\nEOF\n"] = "Catalan Win\nEOF\n"
        with translation.override("ca", deactivate=True):
            self.assertEqual("Catalan Mac\nEOF\n", gettext("Mac\rEOF\r"))
            self.assertEqual("Catalan Win\nEOF\n", gettext("Win\r\nEOF\r\n"))

    def test_to_locale(self):
        """
        Tests the conversion of language codes to their corresponding locale codes.

        Checks that language codes in different formats are correctly converted to their
        standardized locale codes. The test cases cover various language codes, including
        those with country or script specifications, and verify that the conversion is
        case-insensitive.

        The function ensures that the :func:`to_locale` function correctly handles
        different input formats and produces the expected output. The test cases are run
        with the :meth:`subTest` context manager to provide detailed information about
        each test case in case of failures.
        """
        tests = (
            ("en", "en"),
            ("EN", "en"),
            ("en-us", "en_US"),
            ("EN-US", "en_US"),
            ("en_US", "en_US"),
            # With > 2 characters after the dash.
            ("sr-latn", "sr_Latn"),
            ("sr-LATN", "sr_Latn"),
            ("sr_Latn", "sr_Latn"),
            # 3-char language codes.
            ("ber-MA", "ber_MA"),
            ("BER-MA", "ber_MA"),
            ("BER_MA", "ber_MA"),
            ("ber_MA", "ber_MA"),
            # With private use subtag (x-informal).
            ("nl-nl-x-informal", "nl_NL-x-informal"),
            ("NL-NL-X-INFORMAL", "nl_NL-x-informal"),
            ("sr-latn-x-informal", "sr_Latn-x-informal"),
            ("SR-LATN-X-INFORMAL", "sr_Latn-x-informal"),
        )
        for lang, locale in tests:
            with self.subTest(lang=lang):
                self.assertEqual(to_locale(lang), locale)

    def test_to_language(self):
        """

        Converts a language code from underscore notation to hyphen notation.

        Args:
            language_code (str): The language code in underscore notation (e.g., 'en_US', 'sr_Lat').

        Returns:
            str: The language code in hyphen notation (e.g., 'en-us', 'sr-lat').

        Notes:
            This function is expected to standardize language codes by replacing underscores with hyphens, 
            following the standard convention for language tags (BCP 47).

        """
        self.assertEqual(to_language("en_US"), "en-us")
        self.assertEqual(to_language("sr_Lat"), "sr-lat")

    def test_language_bidi(self):
        """
        Tests the functionality of determining the bidirectional behavior of the current language.

        Verifies that the function correctly returns whether the current language is bidirectional or not.
        Additionally, checks the behavior when no language is set, ensuring the function still returns the expected result.

        This test is crucial to ensure proper rendering and handling of text in different languages, 
        especially those that read from right to left (e.g., Arabic, Hebrew).
        """
        self.assertIs(get_language_bidi(), False)
        with translation.override(None):
            self.assertIs(get_language_bidi(), False)

    def test_language_bidi_null(self):
        """

        Tests the functionality of determining language bidirectionality.

        This test case verifies that the function correctly identifies whether the
        current language is bidirectional or not. It checks the default case where
        the language is not bidirectional and then overrides the language setting to
        a bidirectional language (Hebrew) to confirm the function returns the correct
        result.

        The function's behavior is examined in two scenarios: the default language
        setting and an overridden language setting.

        """
        self.assertIs(trans_null.get_language_bidi(), False)
        with override_settings(LANGUAGE_CODE="he"):
            self.assertIs(get_language_bidi(), True)


class TranslationLoadingTests(SimpleTestCase):
    def setUp(self):
        """Clear translation state."""
        self._old_language = get_language()
        self._old_translations = trans_real._translations
        deactivate()
        trans_real._translations = {}

    def tearDown(self):
        trans_real._translations = self._old_translations
        activate(self._old_language)

    @override_settings(
        USE_I18N=True,
        LANGUAGE_CODE="en",
        LANGUAGES=[
            ("en", "English"),
            ("en-ca", "English (Canada)"),
            ("en-nz", "English (New Zealand)"),
            ("en-au", "English (Australia)"),
        ],
        LOCALE_PATHS=[os.path.join(here, "loading")],
        INSTALLED_APPS=["i18n.loading_app"],
    )
    def test_translation_loading(self):
        """
        "loading_app" does not have translations for all languages provided by
        "loading". Catalogs are merged correctly.
        """
        tests = [
            ("en", "local country person"),
            ("en_AU", "aussie"),
            ("en_NZ", "kiwi"),
            ("en_CA", "canuck"),
        ]
        # Load all relevant translations.
        for language, _ in tests:
            activate(language)
        # Catalogs are merged correctly.
        for language, nickname in tests:
            with self.subTest(language=language):
                activate(language)
                self.assertEqual(gettext("local country person"), nickname)


class TranslationThreadSafetyTests(SimpleTestCase):
    def setUp(self):
        """

        Sets up the environment for testing by storing the current language and 
        replacing the translations dictionary with a modified version. 
        This allows for isolation of tests from the actual translation data.
        The replacement dictionary contains a special string class that triggers 
        a side effect when its split method is called, which resets the 'en-YY' 
        translation to None.

        """
        self._old_language = get_language()
        self._translations = trans_real._translations

        # here we rely on .split() being called inside the _fetch()
        # in trans_real.translation()
        class sideeffect_str(str):
            def split(self, *args, **kwargs):
                """

                Splits a string into a list of substrings based on the provided arguments.

                This function behaves similarly to the built-in string split method, 
                accepting any number of positional and keyword arguments to specify the 
                separator, maximum splits, and other parameters.

                In addition to splitting the string, this function also clears the 
                translation configuration for the 'en-YY' locale.

                Returns:
                    list: A list of substrings resulting from the split operation.

                """
                res = str.split(self, *args, **kwargs)
                trans_real._translations["en-YY"] = None
                return res

        trans_real._translations = {sideeffect_str("en-XX"): None}

    def tearDown(self):
        trans_real._translations = self._translations
        activate(self._old_language)

    def test_bug14894_translation_activate_thread_safety(self):
        """
        Tests the thread safety of activating translations.

        Verifies that the translation system correctly handles activation of a new translation,
        by checking that the number of translations increases after activation.

        This test case covers a specific bug fix (bug #14894) related to translation activation
        in multi-threaded environments, ensuring that the translation system does not lose track
        of translations when activated in different threads.

        The test checks the 'pl' (Polish) translation, but the principle applies to any translation
        activation scenario. The test passes if the translation count increases after activation,
        indicating that the translation system correctly handles the activation request in a thread-safe manner.
        """
        translation_count = len(trans_real._translations)
        # May raise RuntimeError if translation.activate() isn't thread-safe.
        translation.activate("pl")
        # make sure sideeffect_str actually added a new translation
        self.assertLess(translation_count, len(trans_real._translations))


class FormattingTests(SimpleTestCase):
    def setUp(self):
        """

        Sets up test data for a test case.

        Initializes various test attributes, including decimal, float, date, datetime, time, and integer values.
        These attributes are then used to create a Context object, which stores them for later use.
        This method is called before each test is run and ensures a consistent starting point for tests.

        """
        super().setUp()
        self.n = decimal.Decimal("66666.666")
        self.f = 99999.999
        self.d = datetime.date(2009, 12, 31)
        self.dt = datetime.datetime(2009, 12, 31, 20, 50)
        self.t = datetime.time(10, 15, 48)
        self.long = 10000
        self.ctxt = Context(
            {
                "n": self.n,
                "t": self.t,
                "d": self.d,
                "dt": self.dt,
                "f": self.f,
                "l": self.long,
            }
        )

    def test_all_format_strings(self):
        all_locales = LANG_INFO.keys()
        some_date = datetime.date(2017, 10, 14)
        some_datetime = datetime.datetime(2017, 10, 14, 10, 23)
        for locale in all_locales:
            with self.subTest(locale=locale), translation.override(locale):
                self.assertIn(
                    "2017", date_format(some_date)
                )  # Uses DATE_FORMAT by default
                self.assertIn(
                    "23", time_format(some_datetime)
                )  # Uses TIME_FORMAT by default
                self.assertIn("2017", date_format(some_datetime, "DATETIME_FORMAT"))
                self.assertIn("2017", date_format(some_date, "YEAR_MONTH_FORMAT"))
                self.assertIn("14", date_format(some_date, "MONTH_DAY_FORMAT"))
                self.assertIn("2017", date_format(some_date, "SHORT_DATE_FORMAT"))
                self.assertIn(
                    "2017",
                    date_format(some_datetime, "SHORT_DATETIME_FORMAT"),
                )

    def test_locale_independent(self):
        """
        Localization of numbers
        """
        with self.settings(USE_THOUSAND_SEPARATOR=False):
            self.assertEqual(
                "66666.66",
                nformat(
                    self.n, decimal_sep=".", decimal_pos=2, grouping=3, thousand_sep=","
                ),
            )
            self.assertEqual(
                "66666A6",
                nformat(
                    self.n, decimal_sep="A", decimal_pos=1, grouping=1, thousand_sep="B"
                ),
            )
            self.assertEqual(
                "66666",
                nformat(
                    self.n, decimal_sep="X", decimal_pos=0, grouping=1, thousand_sep="Y"
                ),
            )

        with self.settings(USE_THOUSAND_SEPARATOR=True):
            self.assertEqual(
                "66,666.66",
                nformat(
                    self.n, decimal_sep=".", decimal_pos=2, grouping=3, thousand_sep=","
                ),
            )
            self.assertEqual(
                "6B6B6B6B6A6",
                nformat(
                    self.n, decimal_sep="A", decimal_pos=1, grouping=1, thousand_sep="B"
                ),
            )
            self.assertEqual(
                "-66666.6", nformat(-66666.666, decimal_sep=".", decimal_pos=1)
            )
            self.assertEqual(
                "-66666.0", nformat(int("-66666"), decimal_sep=".", decimal_pos=1)
            )
            self.assertEqual(
                "10000.0", nformat(self.long, decimal_sep=".", decimal_pos=1)
            )
            self.assertEqual(
                "10,00,00,000.00",
                nformat(
                    100000000.00,
                    decimal_sep=".",
                    decimal_pos=2,
                    grouping=(3, 2, 0),
                    thousand_sep=",",
                ),
            )
            self.assertEqual(
                "1,0,00,000,0000.00",
                nformat(
                    10000000000.00,
                    decimal_sep=".",
                    decimal_pos=2,
                    grouping=(4, 3, 2, 1, 0),
                    thousand_sep=",",
                ),
            )
            self.assertEqual(
                "10000,00,000.00",
                nformat(
                    1000000000.00,
                    decimal_sep=".",
                    decimal_pos=2,
                    grouping=(3, 2, -1),
                    thousand_sep=",",
                ),
            )
            # This unusual grouping/force_grouping combination may be triggered
            # by the intcomma filter.
            self.assertEqual(
                "10000",
                nformat(
                    self.long,
                    decimal_sep=".",
                    decimal_pos=0,
                    grouping=0,
                    force_grouping=True,
                ),
            )
            # date filter
            self.assertEqual(
                "31.12.2009 в 20:50",
                Template('{{ dt|date:"d.m.Y в H:i" }}').render(self.ctxt),
            )
            self.assertEqual(
                "⌚ 10:15", Template('{{ t|time:"⌚ H:i" }}').render(self.ctxt)
            )

    def test_false_like_locale_formats(self):
        """
        The active locale's formats take precedence over the default settings
        even if they would be interpreted as False in a conditional test
        (e.g. 0 or empty string) (#16938).
        """
        with translation.override("fr"):
            with self.settings(USE_THOUSAND_SEPARATOR=True, THOUSAND_SEPARATOR="!"):
                self.assertEqual("\xa0", get_format("THOUSAND_SEPARATOR"))
                # Even a second time (after the format has been cached)...
                self.assertEqual("\xa0", get_format("THOUSAND_SEPARATOR"))

            with self.settings(FIRST_DAY_OF_WEEK=0):
                self.assertEqual(1, get_format("FIRST_DAY_OF_WEEK"))
                # Even a second time (after the format has been cached)...
                self.assertEqual(1, get_format("FIRST_DAY_OF_WEEK"))

    def test_l10n_enabled(self):
        """
        Tests that internationalization (L10N) is enabled in the application.

        Tests various L10N settings, including date and time formats, decimal
        separators, and thousand separators. Verifies that these settings are
        applied correctly in different contexts, such as templates, forms, and
        localized values.

        Also tests date and time formats for different languages, including
        Catalan, Russian, and English.

        Ensures that forms are correctly validated and rendered with L10N
        settings applied, including select date widgets and localized field
        values.

        Covers multiple scenarios, including:

        * Different languages (Catalan, Russian, English)
        * Various date and time formats
        * Decimal and thousand separators
        * Form validation and rendering
        * Localized field values and templates

        By verifying these scenarios, this test ensures that L10N is properly
        configured and functional in the application.
        """
        self.maxDiff = 3000
        # Catalan locale
        with translation.override("ca", deactivate=True):
            self.assertEqual(r"j E \d\e Y", get_format("DATE_FORMAT"))
            self.assertEqual(1, get_format("FIRST_DAY_OF_WEEK"))
            self.assertEqual(",", get_format("DECIMAL_SEPARATOR"))
            self.assertEqual("10:15", time_format(self.t))
            self.assertEqual("31 desembre de 2009", date_format(self.d))
            self.assertEqual("1 abril de 2009", date_format(datetime.date(2009, 4, 1)))
            self.assertEqual(
                "desembre del 2009", date_format(self.d, "YEAR_MONTH_FORMAT")
            )
            self.assertEqual(
                "31/12/2009 20:50", date_format(self.dt, "SHORT_DATETIME_FORMAT")
            )
            self.assertEqual("No localizable", localize("No localizable"))

            with self.settings(USE_THOUSAND_SEPARATOR=True):
                self.assertEqual("66.666,666", localize(self.n))
                self.assertEqual("99.999,999", localize(self.f))
                self.assertEqual("10.000", localize(self.long))
                self.assertEqual("True", localize(True))

            with self.settings(USE_THOUSAND_SEPARATOR=False):
                self.assertEqual("66666,666", localize(self.n))
                self.assertEqual("99999,999", localize(self.f))
                self.assertEqual("10000", localize(self.long))
                self.assertEqual("31 desembre de 2009", localize(self.d))
                self.assertEqual("31 desembre de 2009 a les 20:50", localize(self.dt))

            with self.settings(USE_THOUSAND_SEPARATOR=True):
                self.assertEqual("66.666,666", Template("{{ n }}").render(self.ctxt))
                self.assertEqual("99.999,999", Template("{{ f }}").render(self.ctxt))
                self.assertEqual("10.000", Template("{{ l }}").render(self.ctxt))

            with self.settings(USE_THOUSAND_SEPARATOR=True):
                form3 = I18nForm(
                    {
                        "decimal_field": "66.666,666",
                        "float_field": "99.999,999",
                        "date_field": "31/12/2009",
                        "datetime_field": "31/12/2009 20:50",
                        "time_field": "20:50",
                        "integer_field": "1.234",
                    }
                )
                self.assertTrue(form3.is_valid())
                self.assertEqual(
                    decimal.Decimal("66666.666"), form3.cleaned_data["decimal_field"]
                )
                self.assertEqual(99999.999, form3.cleaned_data["float_field"])
                self.assertEqual(
                    datetime.date(2009, 12, 31), form3.cleaned_data["date_field"]
                )
                self.assertEqual(
                    datetime.datetime(2009, 12, 31, 20, 50),
                    form3.cleaned_data["datetime_field"],
                )
                self.assertEqual(
                    datetime.time(20, 50), form3.cleaned_data["time_field"]
                )
                self.assertEqual(1234, form3.cleaned_data["integer_field"])

            with self.settings(USE_THOUSAND_SEPARATOR=False):
                self.assertEqual("66666,666", Template("{{ n }}").render(self.ctxt))
                self.assertEqual("99999,999", Template("{{ f }}").render(self.ctxt))
                self.assertEqual(
                    "31 desembre de 2009", Template("{{ d }}").render(self.ctxt)
                )
                self.assertEqual(
                    "31 desembre de 2009 a les 20:50",
                    Template("{{ dt }}").render(self.ctxt),
                )
                self.assertEqual(
                    "66666,67", Template("{{ n|floatformat:2 }}").render(self.ctxt)
                )
                self.assertEqual(
                    "100000,0", Template("{{ f|floatformat }}").render(self.ctxt)
                )
                self.assertEqual(
                    "66.666,67",
                    Template('{{ n|floatformat:"2g" }}').render(self.ctxt),
                )
                self.assertEqual(
                    "100.000,0",
                    Template('{{ f|floatformat:"g" }}').render(self.ctxt),
                )
                self.assertEqual(
                    "10:15", Template('{{ t|time:"TIME_FORMAT" }}').render(self.ctxt)
                )
                self.assertEqual(
                    "31/12/2009",
                    Template('{{ d|date:"SHORT_DATE_FORMAT" }}').render(self.ctxt),
                )
                self.assertEqual(
                    "31/12/2009 20:50",
                    Template('{{ dt|date:"SHORT_DATETIME_FORMAT" }}').render(self.ctxt),
                )
                self.assertEqual(
                    date_format(datetime.datetime.now()),
                    Template('{% now "DATE_FORMAT" %}').render(self.ctxt),
                )

            with self.settings(USE_THOUSAND_SEPARATOR=False):
                form4 = I18nForm(
                    {
                        "decimal_field": "66666,666",
                        "float_field": "99999,999",
                        "date_field": "31/12/2009",
                        "datetime_field": "31/12/2009 20:50",
                        "time_field": "20:50",
                        "integer_field": "1234",
                    }
                )
                self.assertTrue(form4.is_valid())
                self.assertEqual(
                    decimal.Decimal("66666.666"), form4.cleaned_data["decimal_field"]
                )
                self.assertEqual(99999.999, form4.cleaned_data["float_field"])
                self.assertEqual(
                    datetime.date(2009, 12, 31), form4.cleaned_data["date_field"]
                )
                self.assertEqual(
                    datetime.datetime(2009, 12, 31, 20, 50),
                    form4.cleaned_data["datetime_field"],
                )
                self.assertEqual(
                    datetime.time(20, 50), form4.cleaned_data["time_field"]
                )
                self.assertEqual(1234, form4.cleaned_data["integer_field"])

            form5 = SelectDateForm(
                {
                    "date_field_month": "12",
                    "date_field_day": "31",
                    "date_field_year": "2009",
                }
            )
            self.assertTrue(form5.is_valid())
            self.assertEqual(
                datetime.date(2009, 12, 31), form5.cleaned_data["date_field"]
            )
            self.assertHTMLEqual(
                '<select name="mydate_day" id="id_mydate_day">'
                '<option value="">---</option>'
                '<option value="1">1</option>'
                '<option value="2">2</option>'
                '<option value="3">3</option>'
                '<option value="4">4</option>'
                '<option value="5">5</option>'
                '<option value="6">6</option>'
                '<option value="7">7</option>'
                '<option value="8">8</option>'
                '<option value="9">9</option>'
                '<option value="10">10</option>'
                '<option value="11">11</option>'
                '<option value="12">12</option>'
                '<option value="13">13</option>'
                '<option value="14">14</option>'
                '<option value="15">15</option>'
                '<option value="16">16</option>'
                '<option value="17">17</option>'
                '<option value="18">18</option>'
                '<option value="19">19</option>'
                '<option value="20">20</option>'
                '<option value="21">21</option>'
                '<option value="22">22</option>'
                '<option value="23">23</option>'
                '<option value="24">24</option>'
                '<option value="25">25</option>'
                '<option value="26">26</option>'
                '<option value="27">27</option>'
                '<option value="28">28</option>'
                '<option value="29">29</option>'
                '<option value="30">30</option>'
                '<option value="31" selected>31</option>'
                "</select>"
                '<select name="mydate_month" id="id_mydate_month">'
                '<option value="">---</option>'
                '<option value="1">gener</option>'
                '<option value="2">febrer</option>'
                '<option value="3">mar\xe7</option>'
                '<option value="4">abril</option>'
                '<option value="5">maig</option>'
                '<option value="6">juny</option>'
                '<option value="7">juliol</option>'
                '<option value="8">agost</option>'
                '<option value="9">setembre</option>'
                '<option value="10">octubre</option>'
                '<option value="11">novembre</option>'
                '<option value="12" selected>desembre</option>'
                "</select>"
                '<select name="mydate_year" id="id_mydate_year">'
                '<option value="">---</option>'
                '<option value="2009" selected>2009</option>'
                '<option value="2010">2010</option>'
                '<option value="2011">2011</option>'
                '<option value="2012">2012</option>'
                '<option value="2013">2013</option>'
                '<option value="2014">2014</option>'
                '<option value="2015">2015</option>'
                '<option value="2016">2016</option>'
                '<option value="2017">2017</option>'
                '<option value="2018">2018</option>'
                "</select>",
                forms.SelectDateWidget(years=range(2009, 2019)).render(
                    "mydate", datetime.date(2009, 12, 31)
                ),
            )

        # Russian locale (with E as month)
        with translation.override("ru", deactivate=True):
            self.assertHTMLEqual(
                '<select name="mydate_day" id="id_mydate_day">'
                '<option value="">---</option>'
                '<option value="1">1</option>'
                '<option value="2">2</option>'
                '<option value="3">3</option>'
                '<option value="4">4</option>'
                '<option value="5">5</option>'
                '<option value="6">6</option>'
                '<option value="7">7</option>'
                '<option value="8">8</option>'
                '<option value="9">9</option>'
                '<option value="10">10</option>'
                '<option value="11">11</option>'
                '<option value="12">12</option>'
                '<option value="13">13</option>'
                '<option value="14">14</option>'
                '<option value="15">15</option>'
                '<option value="16">16</option>'
                '<option value="17">17</option>'
                '<option value="18">18</option>'
                '<option value="19">19</option>'
                '<option value="20">20</option>'
                '<option value="21">21</option>'
                '<option value="22">22</option>'
                '<option value="23">23</option>'
                '<option value="24">24</option>'
                '<option value="25">25</option>'
                '<option value="26">26</option>'
                '<option value="27">27</option>'
                '<option value="28">28</option>'
                '<option value="29">29</option>'
                '<option value="30">30</option>'
                '<option value="31" selected>31</option>'
                "</select>"
                '<select name="mydate_month" id="id_mydate_month">'
                '<option value="">---</option>'
                '<option value="1">\u042f\u043d\u0432\u0430\u0440\u044c</option>'
                '<option value="2">\u0424\u0435\u0432\u0440\u0430\u043b\u044c</option>'
                '<option value="3">\u041c\u0430\u0440\u0442</option>'
                '<option value="4">\u0410\u043f\u0440\u0435\u043b\u044c</option>'
                '<option value="5">\u041c\u0430\u0439</option>'
                '<option value="6">\u0418\u044e\u043d\u044c</option>'
                '<option value="7">\u0418\u044e\u043b\u044c</option>'
                '<option value="8">\u0410\u0432\u0433\u0443\u0441\u0442</option>'
                '<option value="9">\u0421\u0435\u043d\u0442\u044f\u0431\u0440\u044c'
                "</option>"
                '<option value="10">\u041e\u043a\u0442\u044f\u0431\u0440\u044c</option>'
                '<option value="11">\u041d\u043e\u044f\u0431\u0440\u044c</option>'
                '<option value="12" selected>\u0414\u0435\u043a\u0430\u0431\u0440\u044c'
                "</option>"
                "</select>"
                '<select name="mydate_year" id="id_mydate_year">'
                '<option value="">---</option>'
                '<option value="2009" selected>2009</option>'
                '<option value="2010">2010</option>'
                '<option value="2011">2011</option>'
                '<option value="2012">2012</option>'
                '<option value="2013">2013</option>'
                '<option value="2014">2014</option>'
                '<option value="2015">2015</option>'
                '<option value="2016">2016</option>'
                '<option value="2017">2017</option>'
                '<option value="2018">2018</option>'
                "</select>",
                forms.SelectDateWidget(years=range(2009, 2019)).render(
                    "mydate", datetime.date(2009, 12, 31)
                ),
            )

        # English locale
        with translation.override("en", deactivate=True):
            self.assertEqual("N j, Y", get_format("DATE_FORMAT"))
            self.assertEqual(0, get_format("FIRST_DAY_OF_WEEK"))
            self.assertEqual(".", get_format("DECIMAL_SEPARATOR"))
            self.assertEqual("Dec. 31, 2009", date_format(self.d))
            self.assertEqual("December 2009", date_format(self.d, "YEAR_MONTH_FORMAT"))
            self.assertEqual(
                "12/31/2009 8:50 p.m.", date_format(self.dt, "SHORT_DATETIME_FORMAT")
            )
            self.assertEqual("No localizable", localize("No localizable"))

            with self.settings(USE_THOUSAND_SEPARATOR=True):
                self.assertEqual("66,666.666", localize(self.n))
                self.assertEqual("99,999.999", localize(self.f))
                self.assertEqual("10,000", localize(self.long))

            with self.settings(USE_THOUSAND_SEPARATOR=False):
                self.assertEqual("66666.666", localize(self.n))
                self.assertEqual("99999.999", localize(self.f))
                self.assertEqual("10000", localize(self.long))
                self.assertEqual("Dec. 31, 2009", localize(self.d))
                self.assertEqual("Dec. 31, 2009, 8:50 p.m.", localize(self.dt))

            with self.settings(USE_THOUSAND_SEPARATOR=True):
                self.assertEqual("66,666.666", Template("{{ n }}").render(self.ctxt))
                self.assertEqual("99,999.999", Template("{{ f }}").render(self.ctxt))
                self.assertEqual("10,000", Template("{{ l }}").render(self.ctxt))

            with self.settings(USE_THOUSAND_SEPARATOR=False):
                self.assertEqual("66666.666", Template("{{ n }}").render(self.ctxt))
                self.assertEqual("99999.999", Template("{{ f }}").render(self.ctxt))
                self.assertEqual("Dec. 31, 2009", Template("{{ d }}").render(self.ctxt))
                self.assertEqual(
                    "Dec. 31, 2009, 8:50 p.m.", Template("{{ dt }}").render(self.ctxt)
                )
                self.assertEqual(
                    "66666.67", Template("{{ n|floatformat:2 }}").render(self.ctxt)
                )
                self.assertEqual(
                    "100000.0", Template("{{ f|floatformat }}").render(self.ctxt)
                )
                self.assertEqual(
                    "66,666.67",
                    Template('{{ n|floatformat:"2g" }}').render(self.ctxt),
                )
                self.assertEqual(
                    "100,000.0",
                    Template('{{ f|floatformat:"g" }}').render(self.ctxt),
                )
                self.assertEqual(
                    "12/31/2009",
                    Template('{{ d|date:"SHORT_DATE_FORMAT" }}').render(self.ctxt),
                )
                self.assertEqual(
                    "12/31/2009 8:50 p.m.",
                    Template('{{ dt|date:"SHORT_DATETIME_FORMAT" }}').render(self.ctxt),
                )

            form5 = I18nForm(
                {
                    "decimal_field": "66666.666",
                    "float_field": "99999.999",
                    "date_field": "12/31/2009",
                    "datetime_field": "12/31/2009 20:50",
                    "time_field": "20:50",
                    "integer_field": "1234",
                }
            )
            self.assertTrue(form5.is_valid())
            self.assertEqual(
                decimal.Decimal("66666.666"), form5.cleaned_data["decimal_field"]
            )
            self.assertEqual(99999.999, form5.cleaned_data["float_field"])
            self.assertEqual(
                datetime.date(2009, 12, 31), form5.cleaned_data["date_field"]
            )
            self.assertEqual(
                datetime.datetime(2009, 12, 31, 20, 50),
                form5.cleaned_data["datetime_field"],
            )
            self.assertEqual(datetime.time(20, 50), form5.cleaned_data["time_field"])
            self.assertEqual(1234, form5.cleaned_data["integer_field"])

            form6 = SelectDateForm(
                {
                    "date_field_month": "12",
                    "date_field_day": "31",
                    "date_field_year": "2009",
                }
            )
            self.assertTrue(form6.is_valid())
            self.assertEqual(
                datetime.date(2009, 12, 31), form6.cleaned_data["date_field"]
            )
            self.assertHTMLEqual(
                '<select name="mydate_month" id="id_mydate_month">'
                '<option value="">---</option>'
                '<option value="1">January</option>'
                '<option value="2">February</option>'
                '<option value="3">March</option>'
                '<option value="4">April</option>'
                '<option value="5">May</option>'
                '<option value="6">June</option>'
                '<option value="7">July</option>'
                '<option value="8">August</option>'
                '<option value="9">September</option>'
                '<option value="10">October</option>'
                '<option value="11">November</option>'
                '<option value="12" selected>December</option>'
                "</select>"
                '<select name="mydate_day" id="id_mydate_day">'
                '<option value="">---</option>'
                '<option value="1">1</option>'
                '<option value="2">2</option>'
                '<option value="3">3</option>'
                '<option value="4">4</option>'
                '<option value="5">5</option>'
                '<option value="6">6</option>'
                '<option value="7">7</option>'
                '<option value="8">8</option>'
                '<option value="9">9</option>'
                '<option value="10">10</option>'
                '<option value="11">11</option>'
                '<option value="12">12</option>'
                '<option value="13">13</option>'
                '<option value="14">14</option>'
                '<option value="15">15</option>'
                '<option value="16">16</option>'
                '<option value="17">17</option>'
                '<option value="18">18</option>'
                '<option value="19">19</option>'
                '<option value="20">20</option>'
                '<option value="21">21</option>'
                '<option value="22">22</option>'
                '<option value="23">23</option>'
                '<option value="24">24</option>'
                '<option value="25">25</option>'
                '<option value="26">26</option>'
                '<option value="27">27</option>'
                '<option value="28">28</option>'
                '<option value="29">29</option>'
                '<option value="30">30</option>'
                '<option value="31" selected>31</option>'
                "</select>"
                '<select name="mydate_year" id="id_mydate_year">'
                '<option value="">---</option>'
                '<option value="2009" selected>2009</option>'
                '<option value="2010">2010</option>'
                '<option value="2011">2011</option>'
                '<option value="2012">2012</option>'
                '<option value="2013">2013</option>'
                '<option value="2014">2014</option>'
                '<option value="2015">2015</option>'
                '<option value="2016">2016</option>'
                '<option value="2017">2017</option>'
                '<option value="2018">2018</option>'
                "</select>",
                forms.SelectDateWidget(years=range(2009, 2019)).render(
                    "mydate", datetime.date(2009, 12, 31)
                ),
            )

    def test_sub_locales(self):
        """
        Check if sublocales fall back to the main locale
        """
        with self.settings(USE_THOUSAND_SEPARATOR=True):
            with translation.override("de-at", deactivate=True):
                self.assertEqual("66.666,666", Template("{{ n }}").render(self.ctxt))
            with translation.override("es-us", deactivate=True):
                self.assertEqual("31 de diciembre de 2009", date_format(self.d))

    def test_localized_input(self):
        """
        Tests if form input is correctly localized
        """
        self.maxDiff = 1200
        with translation.override("de-at", deactivate=True):
            form6 = CompanyForm(
                {
                    "name": "acme",
                    "date_added": datetime.datetime(2009, 12, 31, 6, 0, 0),
                    "cents_paid": decimal.Decimal("59.47"),
                    "products_delivered": 12000,
                }
            )
            self.assertTrue(form6.is_valid())
            self.assertHTMLEqual(
                form6.as_ul(),
                '<li><label for="id_name">Name:</label>'
                '<input id="id_name" type="text" name="name" value="acme" '
                '   maxlength="50" required></li>'
                '<li><label for="id_date_added">Date added:</label>'
                '<input type="text" name="date_added" value="31.12.2009 06:00:00" '
                '   id="id_date_added" required></li>'
                '<li><label for="id_cents_paid">Cents paid:</label>'
                '<input type="text" name="cents_paid" value="59,47" id="id_cents_paid" '
                "   required></li>"
                '<li><label for="id_products_delivered">Products delivered:</label>'
                '<input type="text" name="products_delivered" value="12000" '
                '   id="id_products_delivered" required>'
                "</li>",
            )
            self.assertEqual(
                localize_input(datetime.datetime(2009, 12, 31, 6, 0, 0)),
                "31.12.2009 06:00:00",
            )
            self.assertEqual(
                datetime.datetime(2009, 12, 31, 6, 0, 0),
                form6.cleaned_data["date_added"],
            )
            with self.settings(USE_THOUSAND_SEPARATOR=True):
                # Checking for the localized "products_delivered" field
                self.assertInHTML(
                    '<input type="text" name="products_delivered" '
                    'value="12.000" id="id_products_delivered" required>',
                    form6.as_ul(),
                )

    def test_localized_input_func(self):
        """

        Tests the localize_input function with various input types and values.

        This test case checks if the localized input function correctly formats different data types such as boolean, date, and datetime. 
        It also verifies that the function handles localization settings, specifically the USE_THOUSAND_SEPARATOR setting, and generates the expected output strings.

        The test iterates over a set of test values and their corresponding expected localized strings, asserting that the actual output matches the expected result for each test case.

        """
        tests = (
            (True, "True"),
            (datetime.date(1, 1, 1), "0001-01-01"),
            (datetime.datetime(1, 1, 1), "0001-01-01 00:00:00"),
        )
        with self.settings(USE_THOUSAND_SEPARATOR=True):
            for value, expected in tests:
                with self.subTest(value=value):
                    self.assertEqual(localize_input(value), expected)

    def test_sanitize_strftime_format(self):
        """

        Tests the sanitation of strftime format strings to ensure compatibility with different year values.

        This test case checks the transformation of various strftime directives, including century (%C), ISO 8601 date (%F), ISO week date year (%G), and calendar year (%Y), 
        for years with different number of digits (1, 2, 3, and 4). It verifies that the sanitized format strings produce the expected output when used with the strftime method of a date object.

        """
        for year in (1, 99, 999, 1000):
            dt = datetime.date(year, 1, 1)
            for fmt, expected in [
                ("%C", "%02d" % (year // 100)),
                ("%F", "%04d-01-01" % year),
                ("%G", "%04d" % year),
                ("%Y", "%04d" % year),
            ]:
                with self.subTest(year=year, fmt=fmt):
                    fmt = sanitize_strftime_format(fmt)
                    self.assertEqual(dt.strftime(fmt), expected)

    def test_sanitize_strftime_format_with_escaped_percent(self):
        """
        Tests the sanitize_strftime_format function to ensure it properly handles escaped percent signs in strftime format strings.

        The function is expected to replace escaped percent signs ('%%') with a single percent sign ('%') while leaving double escaped percent signs ('%%%%') as is. It also ensures that the sanitized format strings produce the correct output when used with the strftime method of a date object.

        The test covers various cases, including different numbers of escaped percent signs and different years to account for varying format requirements. If the function is working correctly, the sanitized format strings should produce the expected output for each test case.
        """
        dt = datetime.date(1, 1, 1)
        for fmt, expected in [
            ("%%C", "%C"),
            ("%%F", "%F"),
            ("%%G", "%G"),
            ("%%Y", "%Y"),
            ("%%%%C", "%%C"),
            ("%%%%F", "%%F"),
            ("%%%%G", "%%G"),
            ("%%%%Y", "%%Y"),
        ]:
            with self.subTest(fmt=fmt):
                fmt = sanitize_strftime_format(fmt)
                self.assertEqual(dt.strftime(fmt), expected)

        for year in (1, 99, 999, 1000):
            dt = datetime.date(year, 1, 1)
            for fmt, expected in [
                ("%%%C", "%%%02d" % (year // 100)),
                ("%%%F", "%%%04d-01-01" % year),
                ("%%%G", "%%%04d" % year),
                ("%%%Y", "%%%04d" % year),
                ("%%%%%C", "%%%%%02d" % (year // 100)),
                ("%%%%%F", "%%%%%04d-01-01" % year),
                ("%%%%%G", "%%%%%04d" % year),
                ("%%%%%Y", "%%%%%04d" % year),
            ]:
                with self.subTest(year=year, fmt=fmt):
                    fmt = sanitize_strftime_format(fmt)
                    self.assertEqual(dt.strftime(fmt), expected)

    def test_sanitize_separators(self):
        """
        Tests django.utils.formats.sanitize_separators.
        """
        # Non-strings are untouched
        self.assertEqual(sanitize_separators(123), 123)

        with translation.override("ru", deactivate=True):
            # Russian locale has non-breaking space (\xa0) as thousand separator
            # Usual space is accepted too when sanitizing inputs
            with self.settings(USE_THOUSAND_SEPARATOR=True):
                self.assertEqual(sanitize_separators("1\xa0234\xa0567"), "1234567")
                self.assertEqual(sanitize_separators("77\xa0777,777"), "77777.777")
                self.assertEqual(sanitize_separators("12 345"), "12345")
                self.assertEqual(sanitize_separators("77 777,777"), "77777.777")
            with translation.override(None):
                with self.settings(USE_THOUSAND_SEPARATOR=True, THOUSAND_SEPARATOR="."):
                    self.assertEqual(sanitize_separators("12\xa0345"), "12\xa0345")

        with self.settings(USE_THOUSAND_SEPARATOR=True):
            with patch_formats(
                get_language(), THOUSAND_SEPARATOR=".", DECIMAL_SEPARATOR=","
            ):
                self.assertEqual(sanitize_separators("10.234"), "10234")
                # Suspicion that user entered dot as decimal separator (#22171)
                self.assertEqual(sanitize_separators("10.10"), "10.10")

        with translation.override(None):
            with self.settings(DECIMAL_SEPARATOR=","):
                self.assertEqual(sanitize_separators("1001,10"), "1001.10")
                self.assertEqual(sanitize_separators("1001.10"), "1001.10")
            with self.settings(
                DECIMAL_SEPARATOR=",",
                THOUSAND_SEPARATOR=".",
                USE_THOUSAND_SEPARATOR=True,
            ):
                self.assertEqual(sanitize_separators("1.001,10"), "1001.10")
                self.assertEqual(sanitize_separators("1001,10"), "1001.10")
                self.assertEqual(sanitize_separators("1001.10"), "1001.10")
                # Invalid output.
                self.assertEqual(sanitize_separators("1,001.10"), "1.001.10")

    def test_iter_format_modules(self):
        """
        Tests the iter_format_modules function.
        """
        # Importing some format modules so that we can compare the returned
        # modules with these expected modules
        default_mod = import_module("django.conf.locale.de.formats")
        test_mod = import_module("i18n.other.locale.de.formats")
        test_mod2 = import_module("i18n.other2.locale.de.formats")

        with translation.override("de-at", deactivate=True):
            # Should return the correct default module when no setting is set
            self.assertEqual(list(iter_format_modules("de")), [default_mod])

            # When the setting is a string, should return the given module and
            # the default module
            self.assertEqual(
                list(iter_format_modules("de", "i18n.other.locale")),
                [test_mod, default_mod],
            )

            # When setting is a list of strings, should return the given
            # modules and the default module
            self.assertEqual(
                list(
                    iter_format_modules(
                        "de", ["i18n.other.locale", "i18n.other2.locale"]
                    )
                ),
                [test_mod, test_mod2, default_mod],
            )

    def test_iter_format_modules_stability(self):
        """
        Tests the iter_format_modules function always yields format modules in
        a stable and correct order in presence of both base ll and ll_CC formats.
        """
        en_format_mod = import_module("django.conf.locale.en.formats")
        en_gb_format_mod = import_module("django.conf.locale.en_GB.formats")
        self.assertEqual(
            list(iter_format_modules("en-gb")), [en_gb_format_mod, en_format_mod]
        )

    def test_get_format_modules_lang(self):
        with translation.override("de", deactivate=True):
            self.assertEqual(".", get_format("DECIMAL_SEPARATOR", lang="en"))

    def test_get_format_lazy_format(self):
        self.assertEqual(get_format(gettext_lazy("DATE_FORMAT")), "N j, Y")

    def test_localize_templatetag_and_filter(self):
        """
        Test the {% localize %} templatetag and the localize/unlocalize filters.
        """
        context = Context(
            {"int": 1455, "float": 3.14, "date": datetime.date(2016, 12, 31)}
        )
        template1 = Template(
            "{% load l10n %}{% localize %}"
            "{{ int }}/{{ float }}/{{ date }}{% endlocalize %}; "
            "{% localize on %}{{ int }}/{{ float }}/{{ date }}{% endlocalize %}"
        )
        template2 = Template(
            "{% load l10n %}{{ int }}/{{ float }}/{{ date }}; "
            "{% localize off %}{{ int }}/{{ float }}/{{ date }};{% endlocalize %} "
            "{{ int }}/{{ float }}/{{ date }}"
        )
        template3 = Template(
            "{% load l10n %}{{ int }}/{{ float }}/{{ date }}; "
            "{{ int|unlocalize }}/{{ float|unlocalize }}/{{ date|unlocalize }}"
        )
        expected_localized = "1.455/3,14/31. Dezember 2016"
        expected_unlocalized = "1455/3.14/Dez. 31, 2016"
        output1 = "; ".join([expected_localized, expected_localized])
        output2 = "; ".join(
            [expected_localized, expected_unlocalized, expected_localized]
        )
        output3 = "; ".join([expected_localized, expected_unlocalized])
        with translation.override("de", deactivate=True):
            with self.settings(USE_THOUSAND_SEPARATOR=True):
                self.assertEqual(template1.render(context), output1)
                self.assertEqual(template2.render(context), output2)
                self.assertEqual(template3.render(context), output3)

    def test_localized_off_numbers(self):
        """A string representation is returned for unlocalized numbers."""
        template = Template(
            "{% load l10n %}{% localize off %}"
            "{{ int }}/{{ float }}/{{ decimal }}{% endlocalize %}"
        )
        context = Context(
            {"int": 1455, "float": 3.14, "decimal": decimal.Decimal("24.1567")}
        )
        with self.settings(
            DECIMAL_SEPARATOR=",",
            USE_THOUSAND_SEPARATOR=True,
            THOUSAND_SEPARATOR="°",
            NUMBER_GROUPING=2,
        ):
            self.assertEqual(template.render(context), "1455/3.14/24.1567")

    def test_localized_as_text_as_hidden_input(self):
        """
        Form input with 'as_hidden' or 'as_text' is correctly localized.
        """
        self.maxDiff = 1200

        with translation.override("de-at", deactivate=True):
            template = Template(
                "{% load l10n %}{{ form.date_added }}; {{ form.cents_paid }}"
            )
            template_as_text = Template(
                "{% load l10n %}"
                "{{ form.date_added.as_text }}; {{ form.cents_paid.as_text }}"
            )
            template_as_hidden = Template(
                "{% load l10n %}"
                "{{ form.date_added.as_hidden }}; {{ form.cents_paid.as_hidden }}"
            )
            form = CompanyForm(
                {
                    "name": "acme",
                    "date_added": datetime.datetime(2009, 12, 31, 6, 0, 0),
                    "cents_paid": decimal.Decimal("59.47"),
                    "products_delivered": 12000,
                }
            )
            context = Context({"form": form})
            self.assertTrue(form.is_valid())

            self.assertHTMLEqual(
                template.render(context),
                '<input id="id_date_added" name="date_added" type="text" '
                'value="31.12.2009 06:00:00" required>;'
                '<input id="id_cents_paid" name="cents_paid" type="text" value="59,47" '
                "required>",
            )
            self.assertHTMLEqual(
                template_as_text.render(context),
                '<input id="id_date_added" name="date_added" type="text" '
                'value="31.12.2009 06:00:00" required>;'
                '<input id="id_cents_paid" name="cents_paid" type="text" value="59,47" '
                "required>",
            )
            self.assertHTMLEqual(
                template_as_hidden.render(context),
                '<input id="id_date_added" name="date_added" type="hidden" '
                'value="31.12.2009 06:00:00">;'
                '<input id="id_cents_paid" name="cents_paid" type="hidden" '
                'value="59,47">',
            )

    def test_format_arbitrary_settings(self):
        self.assertEqual(get_format("DEBUG"), "DEBUG")

    def test_get_custom_format(self):
        reset_format_cache()
        with self.settings(FORMAT_MODULE_PATH="i18n.other.locale"):
            with translation.override("fr", deactivate=True):
                self.assertEqual("d/m/Y CUSTOM", get_format("CUSTOM_DAY_FORMAT"))

    def test_admin_javascript_supported_input_formats(self):
        """
        The first input format for DATE_INPUT_FORMATS, TIME_INPUT_FORMATS, and
        DATETIME_INPUT_FORMATS must not contain %f since that's unsupported by
        the admin's time picker widget.
        """
        regex = re.compile("%([^BcdHImMpSwxXyY%])")
        for language_code, language_name in settings.LANGUAGES:
            for format_name in (
                "DATE_INPUT_FORMATS",
                "TIME_INPUT_FORMATS",
                "DATETIME_INPUT_FORMATS",
            ):
                with self.subTest(language=language_code, format=format_name):
                    formatter = get_format(format_name, lang=language_code)[0]
                    self.assertEqual(
                        regex.findall(formatter),
                        [],
                        "%s locale's %s uses an unsupported format code."
                        % (language_code, format_name),
                    )


class MiscTests(SimpleTestCase):
    rf = RequestFactory()

    @override_settings(LANGUAGE_CODE="de")
    def test_english_fallback(self):
        """
        With a non-English LANGUAGE_CODE and if the active language is English
        or one of its variants, the untranslated string should be returned
        (instead of falling back to LANGUAGE_CODE) (See #24413).
        """
        self.assertEqual(gettext("Image"), "Bild")
        with translation.override("en"):
            self.assertEqual(gettext("Image"), "Image")
        with translation.override("en-us"):
            self.assertEqual(gettext("Image"), "Image")
        with translation.override("en-ca"):
            self.assertEqual(gettext("Image"), "Image")

    def test_parse_spec_http_header(self):
        """
        Testing HTTP header parsing. First, we test that we can parse the
        values according to the spec (and that we extract all the pieces in
        the right order).
        """
        tests = [
            # Good headers
            ("de", [("de", 1.0)]),
            ("en-AU", [("en-au", 1.0)]),
            ("es-419", [("es-419", 1.0)]),
            ("*;q=1.00", [("*", 1.0)]),
            ("en-AU;q=0.123", [("en-au", 0.123)]),
            ("en-au;q=0.5", [("en-au", 0.5)]),
            ("en-au;q=1.0", [("en-au", 1.0)]),
            ("da, en-gb;q=0.25, en;q=0.5", [("da", 1.0), ("en", 0.5), ("en-gb", 0.25)]),
            ("en-au-xx", [("en-au-xx", 1.0)]),
            (
                "de,en-au;q=0.75,en-us;q=0.5,en;q=0.25,es;q=0.125,fa;q=0.125",
                [
                    ("de", 1.0),
                    ("en-au", 0.75),
                    ("en-us", 0.5),
                    ("en", 0.25),
                    ("es", 0.125),
                    ("fa", 0.125),
                ],
            ),
            ("*", [("*", 1.0)]),
            ("de;q=0.", [("de", 0.0)]),
            ("en; q=1,", [("en", 1.0)]),
            ("en; q=1.0, * ; q=0.5", [("en", 1.0), ("*", 0.5)]),
            (
                "en" + "-x" * 20,
                [("en-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x", 1.0)],
            ),
            (
                ", ".join(["en; q=1.0"] * 20),
                [("en", 1.0)] * 20,
            ),
            # Bad headers
            ("en-gb;q=1.0000", []),
            ("en;q=0.1234", []),
            ("en;q=.2", []),
            ("abcdefghi-au", []),
            ("**", []),
            ("en,,gb", []),
            ("en-au;q=0.1.0", []),
            (("X" * 97) + "Z,en", []),
            ("da, en-gb;q=0.8, en;q=0.7,#", []),
            ("de;q=2.0", []),
            ("de;q=0.a", []),
            ("12-345", []),
            ("", []),
            ("en;q=1e0", []),
            ("en-au;q=１.０", []),
            # Invalid as language-range value too long.
            ("xxxxxxxx" + "-xxxxxxxx" * 500, []),
            # Header value too long, only parse up to limit.
            (", ".join(["en; q=1.0"] * 500), [("en", 1.0)] * 45),
        ]
        for value, expected in tests:
            with self.subTest(value=value):
                self.assertEqual(
                    trans_real.parse_accept_lang_header(value), tuple(expected)
                )

    def test_parse_literal_http_header(self):
        """
        Tests the parsing of the Accept-Language HTTP header to determine the language.

        This test case covers various scenarios, including languages with country codes, 
        languages with dialects, and languages with different script variations. It 
        verifies that the function correctly extracts the language code from the header 
        and returns the expected language code.

        The test cases include languages such as Portuguese, Spanish, German, Chinese, 
        Dutch, Frisian, Interlingua, and Serbian, ensuring that the function handles 
        different language codes and formats correctly. 

        The goal of this test is to ensure that the function correctly determines the 
        language from the Accept-Language header, allowing for proper language handling 
        in web applications.
        """
        tests = [
            ("pt-br", "pt-br"),
            ("pt", "pt"),
            ("es,de", "es"),
            ("es-a,de", "es"),
            # There isn't a Django translation to a US variation of the Spanish
            # language, a safe assumption. When the user sets it as the
            # preferred language, the main 'es' translation should be selected
            # instead.
            ("es-us", "es"),
            # There isn't a main language (zh) translation of Django but there
            # is a translation to variation (zh-hans) the user sets zh-hans as
            # the preferred language, it should be selected without falling
            # back nor ignoring it.
            ("zh-hans,de", "zh-hans"),
            ("NL", "nl"),
            ("fy", "fy"),
            ("ia", "ia"),
            ("sr-latn", "sr-latn"),
            ("zh-hans", "zh-hans"),
            ("zh-hant", "zh-hant"),
        ]
        for header, expected in tests:
            with self.subTest(header=header):
                request = self.rf.get("/", headers={"accept-language": header})
                self.assertEqual(get_language_from_request(request), expected)

    @override_settings(
        LANGUAGES=[
            ("en", "English"),
            ("zh-hans", "Simplified Chinese"),
            ("zh-hant", "Traditional Chinese"),
        ]
    )
    def test_support_for_deprecated_chinese_language_codes(self):
        """
        Some browsers (Firefox, IE, etc.) use deprecated language codes. As these
        language codes will be removed in Django 1.9, these will be incorrectly
        matched. For example zh-tw (traditional) will be interpreted as zh-hans
        (simplified), which is wrong. So we should also accept these deprecated
        language codes.

        refs #18419 -- this is explicitly for browser compatibility
        """
        g = get_language_from_request
        request = self.rf.get("/", headers={"accept-language": "zh-cn,en"})
        self.assertEqual(g(request), "zh-hans")

        request = self.rf.get("/", headers={"accept-language": "zh-tw,en"})
        self.assertEqual(g(request), "zh-hant")

    def test_special_fallback_language(self):
        """
        Some languages may have special fallbacks that don't follow the simple
        'fr-ca' -> 'fr' logic (notably Chinese codes).
        """
        request = self.rf.get("/", headers={"accept-language": "zh-my,en"})
        self.assertEqual(get_language_from_request(request), "zh-hans")

    def test_subsequent_code_fallback_language(self):
        """
        Subsequent language codes should be used when the language code is not
        supported.
        """
        tests = [
            ("zh-Hans-CN", "zh-hans"),
            ("zh-hans-mo", "zh-hans"),
            ("zh-hans-HK", "zh-hans"),
            ("zh-Hant-HK", "zh-hant"),
            ("zh-hant-tw", "zh-hant"),
            ("zh-hant-SG", "zh-hant"),
        ]
        for value, expected in tests:
            with self.subTest(value=value):
                request = self.rf.get("/", headers={"accept-language": f"{value},en"})
                self.assertEqual(get_language_from_request(request), expected)

    def test_parse_language_cookie(self):
        """

        Tests the parsing of language from a request's cookie.

        This test case checks the functionality of retrieving the user's preferred language
        from a cookie in various scenarios, including different language codes and locales.
        It verifies that the language is correctly extracted from the cookie, even when
        the Accept-Language header is present or when the language code has a locale suffix.

        The test covers the following cases:
        - Language codes with or without a locale suffix (e.g., 'pt-br', 'pt')
        - Presence of an Accept-Language header with a different language code
        - Language codes with different formats (e.g., 'es-us', 'zh-hans')

        """
        g = get_language_from_request
        request = self.rf.get("/")
        request.COOKIES[settings.LANGUAGE_COOKIE_NAME] = "pt-br"
        self.assertEqual("pt-br", g(request))

        request.COOKIES[settings.LANGUAGE_COOKIE_NAME] = "pt"
        self.assertEqual("pt", g(request))

        request = self.rf.get("/", headers={"accept-language": "de"})
        request.COOKIES[settings.LANGUAGE_COOKIE_NAME] = "es"
        self.assertEqual("es", g(request))

        # There isn't a Django translation to a US variation of the Spanish
        # language, a safe assumption. When the user sets it as the preferred
        # language, the main 'es' translation should be selected instead.
        request = self.rf.get("/")
        request.COOKIES[settings.LANGUAGE_COOKIE_NAME] = "es-us"
        self.assertEqual(g(request), "es")
        # There isn't a main language (zh) translation of Django but there is a
        # translation to variation (zh-hans) the user sets zh-hans as the
        # preferred language, it should be selected without falling back nor
        # ignoring it.
        request = self.rf.get("/", headers={"accept-language": "de"})
        request.COOKIES[settings.LANGUAGE_COOKIE_NAME] = "zh-hans"
        self.assertEqual(g(request), "zh-hans")

    @override_settings(
        USE_I18N=True,
        LANGUAGES=[
            ("en", "English"),
            ("ar-dz", "Algerian Arabic"),
            ("de", "German"),
            ("de-at", "Austrian German"),
            ("pt-BR", "Portuguese (Brazil)"),
        ],
    )
    def test_get_supported_language_variant_real(self):
        g = trans_real.get_supported_language_variant
        self.assertEqual(g("en"), "en")
        self.assertEqual(g("en-gb"), "en")
        self.assertEqual(g("de"), "de")
        self.assertEqual(g("de-at"), "de-at")
        self.assertEqual(g("de-ch"), "de")
        self.assertEqual(g("pt-br"), "pt-br")
        self.assertEqual(g("pt-BR"), "pt-BR")
        self.assertEqual(g("pt"), "pt-br")
        self.assertEqual(g("pt-pt"), "pt-br")
        self.assertEqual(g("ar-dz"), "ar-dz")
        self.assertEqual(g("ar-DZ"), "ar-DZ")
        with self.assertRaises(LookupError):
            g("pt", strict=True)
        with self.assertRaises(LookupError):
            g("pt-pt", strict=True)
        with self.assertRaises(LookupError):
            g("xyz")
        with self.assertRaises(LookupError):
            g("xy-zz")
        with self.assertRaises(LookupError):
            g("x" * LANGUAGE_CODE_MAX_LENGTH)
        with self.assertRaises(LookupError):
            g("x" * (LANGUAGE_CODE_MAX_LENGTH + 1))
        # 167 * 3 = 501 which is LANGUAGE_CODE_MAX_LENGTH + 1.
        self.assertEqual(g("en-" * 167), "en")
        with self.assertRaises(LookupError):
            g("en-" * 167, strict=True)
        self.assertEqual(g("en-" * 30000), "en")  # catastrophic test

    def test_get_supported_language_variant_null(self):
        g = trans_null.get_supported_language_variant
        self.assertEqual(g(settings.LANGUAGE_CODE), settings.LANGUAGE_CODE)
        with self.assertRaises(LookupError):
            g("pt")
        with self.assertRaises(LookupError):
            g("de")
        with self.assertRaises(LookupError):
            g("de-at")
        with self.assertRaises(LookupError):
            g("de", strict=True)
        with self.assertRaises(LookupError):
            g("de-at", strict=True)
        with self.assertRaises(LookupError):
            g("xyz")

    @override_settings(
        LANGUAGES=[
            ("en", "English"),
            ("en-latn-us", "Latin English"),
            ("de", "German"),
            ("de-1996", "German, orthography of 1996"),
            ("de-at", "Austrian German"),
            ("de-ch-1901", "German, Swiss variant, traditional orthography"),
            ("i-mingo", "Mingo"),
            ("kl-tunumiit", "Tunumiisiut"),
            ("nan-hani-tw", "Hanji"),
            ("pl", "Polish"),
        ],
    )
    def test_get_language_from_path_real(self):
        """

        Determines the language code from a given URL path.

        This function takes a URL path as input and returns the corresponding language code
        if the path matches a language code in the available languages. The function is
        case-insensitive and supports language codes with regional variants.

        The function returns None if the path does not match any known language code.

        Examples of supported language codes include 'en', 'de', 'pl', and regional variants
        such as 'en-latn-us', 'de-at', and 'de-ch-1901'.

        """
        g = trans_real.get_language_from_path
        tests = [
            ("/pl/", "pl"),
            ("/pl", "pl"),
            ("/xyz/", None),
            ("/en/", "en"),
            ("/en-gb/", "en"),
            ("/en-latn-us/", "en-latn-us"),
            ("/en-Latn-US/", "en-Latn-US"),
            ("/de/", "de"),
            ("/de-1996/", "de-1996"),
            ("/de-at/", "de-at"),
            ("/de-AT/", "de-AT"),
            ("/de-ch/", "de"),
            ("/de-ch-1901/", "de-ch-1901"),
            ("/de-simple-page-test/", None),
            ("/i-mingo/", "i-mingo"),
            ("/kl-tunumiit/", "kl-tunumiit"),
            ("/nan-hani-tw/", "nan-hani-tw"),
            (f"/{'a' * 501}/", None),
        ]
        for path, language in tests:
            with self.subTest(path=path):
                self.assertEqual(g(path), language)

    def test_get_language_from_path_null(self):
        """
        Tests the get_language_from_path function with null values.

        Verifies that the function returns None for various invalid or incomplete path inputs.
        This ensures that the function is correctly handling edge cases where the path does not contain a valid language code.

        Parameters are tested for both trailing and non-trailing slash cases, as well as for completely unknown or non-language path segments.
        """
        g = trans_null.get_language_from_path
        self.assertIsNone(g("/pl/"))
        self.assertIsNone(g("/pl"))
        self.assertIsNone(g("/xyz/"))

    def test_cache_resetting(self):
        """
        After setting LANGUAGE, the cache should be cleared and languages
        previously valid should not be used (#14170).
        """
        g = get_language_from_request
        request = self.rf.get("/", headers={"accept-language": "pt-br"})
        self.assertEqual("pt-br", g(request))
        with self.settings(LANGUAGES=[("en", "English")]):
            self.assertNotEqual("pt-br", g(request))

    def test_i18n_patterns_returns_list(self):
        with override_settings(USE_I18N=False):
            self.assertIsInstance(i18n_patterns([]), list)
        with override_settings(USE_I18N=True):
            self.assertIsInstance(i18n_patterns([]), list)


class ResolutionOrderI18NTests(SimpleTestCase):
    def setUp(self):
        """
        Sets up the test environment by activating the 'de' locale and scheduling its deactivation after the test is complete.
        """
        super().setUp()
        activate("de")
        self.addCleanup(deactivate)

    def assertGettext(self, msgid, msgstr):
        """

        Checks if a given msgid's translation contains the expected msgstr.

        This assertion verifies that the gettext translation of msgid includes msgstr.
        It fails if msgstr is not found in the translation, providing the actual result for debugging purposes.

        :param msgid: The message id to be translated.
        :param msgstr: The expected translation string.

        """
        result = gettext(msgid)
        self.assertIn(
            msgstr,
            result,
            "The string '%s' isn't in the translation of '%s'; the actual result is "
            "'%s'." % (msgstr, msgid, result),
        )


class AppResolutionOrderI18NTests(ResolutionOrderI18NTests):
    @override_settings(LANGUAGE_CODE="de")
    def test_app_translation(self):
        # Original translation.
        """

        Tests the translation of an application in the German language.

        This test case verifies that the correct translation is used for a given string,
        both with and without the 'i18n.resolution' app installed, and with the Django admin app enabled and disabled.

        The test covers the following scenarios:

        * Translation with default settings
        * Translation with 'i18n.resolution' app installed
        * Translation with 'i18n.resolution' app installed and Django admin app disabled

        In each scenario, the test asserts that the translated string matches the expected value.

        """
        self.assertGettext("Date/time", "Datum/Zeit")

        # Different translation.
        with self.modify_settings(INSTALLED_APPS={"append": "i18n.resolution"}):
            # Force refreshing translations.
            activate("de")

            # Doesn't work because it's added later in the list.
            self.assertGettext("Date/time", "Datum/Zeit")

            with self.modify_settings(
                INSTALLED_APPS={"remove": "django.contrib.admin.apps.SimpleAdminConfig"}
            ):
                # Force refreshing translations.
                activate("de")

                # Unless the original is removed from the list.
                self.assertGettext("Date/time", "Datum/Zeit (APP)")


@override_settings(LOCALE_PATHS=extended_locale_paths)
class LocalePathsResolutionOrderI18NTests(ResolutionOrderI18NTests):
    def test_locale_paths_translation(self):
        self.assertGettext("Time", "LOCALE_PATHS")

    def test_locale_paths_override_app_translation(self):
        """
        Tests that the LOCALE_PATHS setting can override translation defaults for an application, verifying that a specific translation is correctly retrieved from the specified locale path.
        """
        with self.settings(INSTALLED_APPS=["i18n.resolution"]):
            self.assertGettext("Time", "LOCALE_PATHS")


class DjangoFallbackResolutionOrderI18NTests(ResolutionOrderI18NTests):
    def test_django_fallback(self):
        self.assertEqual(gettext("Date/time"), "Datum/Zeit")


@override_settings(INSTALLED_APPS=["i18n.territorial_fallback"])
class TranslationFallbackI18NTests(ResolutionOrderI18NTests):
    def test_sparse_territory_catalog(self):
        """
        Untranslated strings for territorial language variants use the
        translations of the generic language. In this case, the de-de
        translation falls back to de.
        """
        with translation.override("de-de"):
            self.assertGettext("Test 1 (en)", "(de-de)")
            self.assertGettext("Test 2 (en)", "(de)")


class TestModels(TestCase):
    def test_lazy(self):
        """
        Tests the lazy loading functionality of the model.

        This method creates an instance of TestModel, saves it, and verifies that the 
        lazy loading mechanism works as expected, allowing the model to be properly 
        initialized and persisted without immediate loading of related objects.

        Returns:
            None
        """
        tm = TestModel()
        tm.save()

    def test_safestr(self):
        c = Company(cents_paid=12, products_delivered=1)
        c.name = SafeString("Iñtërnâtiônàlizætiøn1")
        c.save()


class TestLanguageInfo(SimpleTestCase):
    def test_localized_language_info(self):
        """
        Tests the retrieval of language information for a specific locale.

        This test case verifies that language information for a given language code
        ('de' in this case) returns the correct language code, local name, and name
        in a fallback language, as well as the bidirectional text support status.

        Ensures that the language information dictionary contains the expected keys
        and values for a language with a left-to-right writing direction.
        """
        li = get_language_info("de")
        self.assertEqual(li["code"], "de")
        self.assertEqual(li["name_local"], "Deutsch")
        self.assertEqual(li["name"], "German")
        self.assertIs(li["bidi"], False)

    def test_unknown_language_code(self):
        """
        Tests the behavior of the application when an unknown language code is provided, 
        verifying that a KeyError is raised with the expected error message and 
        ensuring that when the translation is overridden with the unknown language code, 
        the gettext function returns the original string unchanged.
        """
        with self.assertRaisesMessage(KeyError, "Unknown language code xx"):
            get_language_info("xx")
        with translation.override("xx"):
            # A language with no translation catalogs should fallback to the
            # untranslated string.
            self.assertEqual(gettext("Title"), "Title")

    def test_unknown_only_country_code(self):
        """

        Tests that language information is correctly extracted when only the country code is unknown.

        Verifies that the language code is truncated, and the remaining language information such as 
        the local name, English name, and bidirectional status are correctly identified.

        """
        li = get_language_info("de-xx")
        self.assertEqual(li["code"], "de")
        self.assertEqual(li["name_local"], "Deutsch")
        self.assertEqual(li["name"], "German")
        self.assertIs(li["bidi"], False)

    def test_unknown_language_code_and_country_code(self):
        """
        Test that a KeyError is raised when an unknown language code and country code are provided.

        This test verifies that the get_language_info function correctly handles invalid language codes
        by raising a KeyError with a descriptive error message, indicating that the language code is unknown.

        """
        with self.assertRaisesMessage(KeyError, "Unknown language code xx-xx and xx"):
            get_language_info("xx-xx")

    def test_fallback_language_code(self):
        """
        get_language_info return the first fallback language info if the lang_info
        struct does not contain the 'name' key.
        """
        li = get_language_info("zh-my")
        self.assertEqual(li["code"], "zh-hans")
        li = get_language_info("zh-hans")
        self.assertEqual(li["code"], "zh-hans")


@override_settings(
    USE_I18N=True,
    LANGUAGES=[
        ("en", "English"),
        ("fr", "French"),
    ],
    MIDDLEWARE=[
        "django.middleware.locale.LocaleMiddleware",
        "django.middleware.common.CommonMiddleware",
    ],
    ROOT_URLCONF="i18n.urls",
)
class LocaleMiddlewareTests(TestCase):
    def test_streaming_response(self):
        # Regression test for #5241
        """

        Test case for streaming response functionality.

        This test checks that the streaming response feature returns the correct content 
        for different languages. It verifies that the French ('fr') version contains 
        'Yes/No' equivalent in French ('Oui/Non') and the English ('en') version contains 
        'Yes/No' in English. 

        The test uses the test client to simulate HTTP GET requests to the streaming 
        endpoint for both French and English languages, and then asserts that the 
        expected phrases are present in the response.

        """
        response = self.client.get("/fr/streaming/")
        self.assertContains(response, "Oui/Non")
        response = self.client.get("/en/streaming/")
        self.assertContains(response, "Yes/No")


@override_settings(
    USE_I18N=True,
    LANGUAGES=[
        ("en", "English"),
        ("de", "German"),
        ("fr", "French"),
    ],
    MIDDLEWARE=[
        "django.middleware.locale.LocaleMiddleware",
        "django.middleware.common.CommonMiddleware",
    ],
    ROOT_URLCONF="i18n.urls_default_unprefixed",
    LANGUAGE_CODE="en",
)
class UnprefixedDefaultLanguageTests(SimpleTestCase):
    def test_default_lang_without_prefix(self):
        """
        With i18n_patterns(..., prefix_default_language=False), the default
        language (settings.LANGUAGE_CODE) should be accessible without a prefix.
        """
        response = self.client.get("/simple/")
        self.assertEqual(response.content, b"Yes")

    @override_settings(LANGUAGE_CODE="en-us")
    def test_default_lang_fallback_without_prefix(self):
        response = self.client.get("/simple/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"Yes")

    def test_other_lang_with_prefix(self):
        """
        Tests that the application correctly handles requests for pages in languages other than the default, 
        using a URL prefix to specify the language. The test case verifies the response content matches the 
        expected translation for a French page with a simple URL path (/fr/simple/).
        """
        response = self.client.get("/fr/simple/")
        self.assertEqual(response.content, b"Oui")

    def test_unprefixed_language_other_than_accept_language(self):
        response = self.client.get("/simple/", HTTP_ACCEPT_LANGUAGE="fr")
        self.assertEqual(response.content, b"Yes")

    def test_page_with_dash(self):
        # A page starting with /de* shouldn't match the 'de' language code.
        response = self.client.get("/de-simple-page-test/")
        self.assertEqual(response.content, b"Yes")

    def test_no_redirect_on_404(self):
        """
        A request for a nonexistent URL shouldn't cause a redirect to
        /<default_language>/<request_url> when prefix_default_language=False and
        /<default_language>/<request_url> has a URL match (#27402).
        """
        # A match for /group1/group2/ must exist for this to act as a
        # regression test.
        response = self.client.get("/group1/group2/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/nonexistent/")
        self.assertEqual(response.status_code, 404)


@override_settings(
    USE_I18N=True,
    LANGUAGES=[
        ("bg", "Bulgarian"),
        ("en-us", "English"),
        ("pt-br", "Portuguese (Brazil)"),
    ],
    MIDDLEWARE=[
        "django.middleware.locale.LocaleMiddleware",
        "django.middleware.common.CommonMiddleware",
    ],
    ROOT_URLCONF="i18n.urls",
)
class CountrySpecificLanguageTests(SimpleTestCase):
    rf = RequestFactory()

    def test_check_for_language(self):
        self.assertTrue(check_for_language("en"))
        self.assertTrue(check_for_language("en-us"))
        self.assertTrue(check_for_language("en-US"))
        self.assertFalse(check_for_language("en_US"))
        self.assertTrue(check_for_language("be"))
        self.assertTrue(check_for_language("be@latin"))
        self.assertTrue(check_for_language("sr-RS@latin"))
        self.assertTrue(check_for_language("sr-RS@12345"))
        self.assertFalse(check_for_language("en-ü"))
        self.assertFalse(check_for_language("en\x00"))
        self.assertFalse(check_for_language(None))
        self.assertFalse(check_for_language("be@ "))
        # Specifying encoding is not supported (Django enforces UTF-8)
        self.assertFalse(check_for_language("tr-TR.UTF-8"))
        self.assertFalse(check_for_language("tr-TR.UTF8"))
        self.assertFalse(check_for_language("de-DE.utf-8"))

    def test_check_for_language_null(self):
        self.assertIs(trans_null.check_for_language("en"), True)

    def test_get_language_from_request(self):
        # issue 19919
        """

        Determines the language from a given HTTP request.

        This function analyzes the 'Accept-Language' header in the request to identify the 
        preferred language. The function follows the standard convention for parsing 
        language codes and their respective quality values.

        The function returns the language code in lowercase and in the format 'language' 
        or 'language-country' (e.g., 'en' or 'en-us'), as defined by the locale.

        The returned language code can be used for further processing, such as 
        localization or internationalization of the application.

        """
        request = self.rf.get(
            "/", headers={"accept-language": "en-US,en;q=0.8,bg;q=0.6,ru;q=0.4"}
        )
        lang = get_language_from_request(request)
        self.assertEqual("en-us", lang)

        request = self.rf.get(
            "/", headers={"accept-language": "bg-bg,en-US;q=0.8,en;q=0.6,ru;q=0.4"}
        )
        lang = get_language_from_request(request)
        self.assertEqual("bg", lang)

    def test_get_language_from_request_code_too_long(self):
        """

        Tests that the get_language_from_request function handles request codes that are too long.

        When an accept-language header exceeds the maximum allowed length, this function should 
        return a default language code ('en-us') instead of raising an error or returning an 
        incorrect value. This test case verifies that the function behaves as expected in such 
        situations, ensuring robust handling of malformed or malicious input. 

        :param none:
        :returns: none

        """
        request = self.rf.get("/", headers={"accept-language": "a" * 501})
        lang = get_language_from_request(request)
        self.assertEqual("en-us", lang)

    def test_get_language_from_request_null(self):
        """
        Tests the get_language_from_request function with a null request.

        This test case verifies that the function returns the default language ('en') when 
        the request object is None. Additionally, it checks that the function correctly 
        returns the language code specified in the LANGUAGE_CODE setting when it is 
        overridden. The test ensures that the function behaves as expected in scenarios 
        where the request object is absent or the language setting is modified.
        """
        lang = trans_null.get_language_from_request(None)
        self.assertEqual(lang, "en")
        with override_settings(LANGUAGE_CODE="de"):
            lang = trans_null.get_language_from_request(None)
            self.assertEqual(lang, "de")

    def test_specific_language_codes(self):
        # issue 11915
        request = self.rf.get(
            "/", headers={"accept-language": "pt,en-US;q=0.8,en;q=0.6,ru;q=0.4"}
        )
        lang = get_language_from_request(request)
        self.assertEqual("pt-br", lang)

        request = self.rf.get(
            "/", headers={"accept-language": "pt-pt,en-US;q=0.8,en;q=0.6,ru;q=0.4"}
        )
        lang = get_language_from_request(request)
        self.assertEqual("pt-br", lang)


class TranslationFilesMissing(SimpleTestCase):
    def setUp(self):
        """
        Set up the test environment.

        This method is called before each test to initialize the necessary setup.
        It inherits the setup from the parent class and assigns the gettext find
        builtin function from the gettext module to an instance variable for later use.
        """
        super().setUp()
        self.gettext_find_builtin = gettext_module.find

    def tearDown(self):
        """
        Reverts the gettext module's find function to its original state and performs the standard teardown procedure.

        Restores the gettext find function to its built-in behavior, ensuring that any modifications made during the test are undone.
        Then calls the superclass's tearDown method to complete any additional cleanup tasks.
        This method is typically used in a testing context to ensure that the environment is properly cleaned up after each test case.

        """
        gettext_module.find = self.gettext_find_builtin
        super().tearDown()

    def patchGettextFind(self):
        gettext_module.find = lambda *args, **kw: None

    def test_failure_finding_default_mo_files(self):
        """OSError is raised if the default language is unparseable."""
        self.patchGettextFind()
        trans_real._translations = {}
        with self.assertRaises(OSError):
            activate("en")


class NonDjangoLanguageTests(SimpleTestCase):
    """
    A language non present in default Django languages can still be
    installed/used by a Django project.
    """

    @override_settings(
        USE_I18N=True,
        LANGUAGES=[
            ("en-us", "English"),
            ("xxx", "Somelanguage"),
        ],
        LANGUAGE_CODE="xxx",
        LOCALE_PATHS=[os.path.join(here, "commands", "locale")],
    )
    def test_non_django_language(self):
        """
        Tests the functionality when a non-Django language is set.

        This test case simulates the environment where a language code not officially 
        supported by Django is used. It verifies that the language settings are 
        applied correctly and that translations are retrieved as expected.

        The test covers the usage of the gettext function to retrieve translations 
        for a given message, ensuring the correct translation is returned for the 
        specified language code. 

        It asserts that the language code is correctly set and that the translation 
        for a specific message ('year') matches the expected translation ('reay') 
        for the non-Django language. 

        This ensures the system behaves as expected when dealing with languages that 
        are not part of the standard Django language set.
        """
        self.assertEqual(get_language(), "xxx")
        self.assertEqual(gettext("year"), "reay")

    @override_settings(USE_I18N=True)
    def test_check_for_language(self):
        with tempfile.TemporaryDirectory() as app_dir:
            os.makedirs(os.path.join(app_dir, "locale", "dummy_Lang", "LC_MESSAGES"))
            open(
                os.path.join(
                    app_dir, "locale", "dummy_Lang", "LC_MESSAGES", "django.mo"
                ),
                "w",
            ).close()
            app_config = AppConfig("dummy_app", AppModuleStub(__path__=[app_dir]))
            with mock.patch(
                "django.apps.apps.get_app_configs", return_value=[app_config]
            ):
                self.assertIs(check_for_language("dummy-lang"), True)

    @override_settings(
        USE_I18N=True,
        LANGUAGES=[
            ("en-us", "English"),
            # xyz language has no locale files
            ("xyz", "XYZ"),
        ],
    )
    @translation.override("xyz")
    def test_plural_non_django_language(self):
        self.assertEqual(get_language(), "xyz")
        self.assertEqual(ngettext("year", "years", 2), "years")


@override_settings(USE_I18N=True)
class WatchForTranslationChangesTests(SimpleTestCase):
    @override_settings(USE_I18N=False)
    def test_i18n_disabled(self):
        mocked_sender = mock.MagicMock()
        watch_for_translation_changes(mocked_sender)
        mocked_sender.watch_dir.assert_not_called()

    def test_i18n_enabled(self):
        """

        Tests whether internationalization (i18n) is enabled by verifying that the 
        watch_for_translation_changes function is successfully watching for directory changes.

        The test checks that the watch_dir method of the mocked sender object is called 
        more than once, indicating that the watch_for_translation_changes function is 
        actively monitoring for translation changes.

        """
        mocked_sender = mock.MagicMock()
        watch_for_translation_changes(mocked_sender)
        self.assertGreater(mocked_sender.watch_dir.call_count, 1)

    def test_i18n_locale_paths(self):
        """

        Tests that the watch_for_translation_changes function correctly monitors the locale paths for changes to translation files.

        This test verifies that the function is watching the directories specified in the LOCALE_PATHS setting for any changes to.mo files,
        which contain compiled translations. A mock sender object is used to track the calls made to it, and a temporary directory is created
        to simulate the locale paths. The test passes if the watch_dir method of the mock sender is called with the correct directory path and
        pattern (**/*.mo) indicating that the function is indeed monitoring the locale paths for translation changes.

        """
        mocked_sender = mock.MagicMock()
        with tempfile.TemporaryDirectory() as app_dir:
            with self.settings(LOCALE_PATHS=[app_dir]):
                watch_for_translation_changes(mocked_sender)
            mocked_sender.watch_dir.assert_any_call(Path(app_dir), "**/*.mo")

    def test_i18n_app_dirs(self):
        """

        Checks the i18n application's directory watching functionality.

        Verifies that the function responsible for watching translation changes correctly
        monitors the locale directory of an installed application for translation files.

        This test ensures that the directory watching functionality is properly configured
        and that it detects translation file changes in the expected location.

        """
        mocked_sender = mock.MagicMock()
        with self.settings(INSTALLED_APPS=["i18n.sampleproject"]):
            watch_for_translation_changes(mocked_sender)
        project_dir = Path(__file__).parent / "sampleproject" / "locale"
        mocked_sender.watch_dir.assert_any_call(project_dir, "**/*.mo")

    def test_i18n_app_dirs_ignore_django_apps(self):
        mocked_sender = mock.MagicMock()
        with self.settings(INSTALLED_APPS=["django.contrib.admin"]):
            watch_for_translation_changes(mocked_sender)
        mocked_sender.watch_dir.assert_called_once_with(Path("locale"), "**/*.mo")

    def test_i18n_local_locale(self):
        """
        Tests the i18n functionality by verifying the watch_for_translation_changes function correctly monitors the local locale directory for translation file changes.

        * It uses a mocked sender object to intercept and verify the directory watch calls.
        * The test checks if the function watches the correct directory for.mo translation files.
        """
        mocked_sender = mock.MagicMock()
        watch_for_translation_changes(mocked_sender)
        locale_dir = Path(__file__).parent / "locale"
        mocked_sender.watch_dir.assert_any_call(locale_dir, "**/*.mo")


class TranslationFileChangedTests(SimpleTestCase):
    def setUp(self):
        self.gettext_translations = gettext_module._translations.copy()
        self.trans_real_translations = trans_real._translations.copy()

    def tearDown(self):
        """

        Reset the translation tables after each test.

        This method undoes the changes made during the test by restoring the original translation tables.
        It ensures that each test starts with a clean slate, unaffected by the translations set up in previous tests.

        """
        gettext._translations = self.gettext_translations
        trans_real._translations = self.trans_real_translations

    def test_ignores_non_mo_files(self):
        gettext_module._translations = {"foo": "bar"}
        path = Path("test.py")
        self.assertIsNone(translation_file_changed(None, path))
        self.assertEqual(gettext_module._translations, {"foo": "bar"})

    def test_resets_cache_with_mo_files(self):
        """

        Test that the translation cache is properly reset when a.mo file is detected.

        This function verifies that when a.mo file is present, the gettext module's
        translations are cleared, and the translation cache is reset, including the
        default and active translation objects. It checks that the translation cache
        is properly updated to reflect the changes, ensuring that stale translations
        are removed and new ones are loaded correctly.

        The test covers the following scenarios:

        * The gettext module's translations dictionary is emptied
        * The trans_real module's translations dictionary and default translation object are reset
        * The trans_real module's active translation object is updated to an instance of Local

        """
        gettext_module._translations = {"foo": "bar"}
        trans_real._translations = {"foo": "bar"}
        trans_real._default = 1
        trans_real._active = False
        path = Path("test.mo")
        self.assertIs(translation_file_changed(None, path), True)
        self.assertEqual(gettext_module._translations, {})
        self.assertEqual(trans_real._translations, {})
        self.assertIsNone(trans_real._default)
        self.assertIsInstance(trans_real._active, Local)


class UtilsTests(SimpleTestCase):
    def test_round_away_from_one(self):
        """

        Tests the round_away_from_one function, which rounds a given number away from 1.

        The function is tested with a variety of positive and negative decimal values, 
        including integers and non-integer values, to ensure that it behaves correctly 
        across different inputs. The test checks that the function correctly rounds the 
        input value away from 1 to the nearest integer.

        """
        tests = [
            (0, 0),
            (0.0, 0),
            (0.25, 0),
            (0.5, 0),
            (0.75, 0),
            (1, 1),
            (1.0, 1),
            (1.25, 2),
            (1.5, 2),
            (1.75, 2),
            (-0.0, 0),
            (-0.25, -1),
            (-0.5, -1),
            (-0.75, -1),
            (-1, -1),
            (-1.0, -1),
            (-1.25, -2),
            (-1.5, -2),
            (-1.75, -2),
        ]
        for value, expected in tests:
            with self.subTest(value=value):
                self.assertEqual(round_away_from_one(value), expected)
