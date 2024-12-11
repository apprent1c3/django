from django.core.checks import Error
from django.core.checks.translation import (
    check_language_settings_consistent,
    check_setting_language_code,
    check_setting_languages,
    check_setting_languages_bidi,
)
from django.test import SimpleTestCase, override_settings


class TranslationCheckTests(SimpleTestCase):
    def setUp(self):
        self.valid_tags = (
            "en",  # language
            "mas",  # language
            "sgn-ase",  # language+extlang
            "fr-CA",  # language+region
            "es-419",  # language+region
            "zh-Hans",  # language+script
            "ca-ES-valencia",  # language+region+variant
            # FIXME: The following should be invalid:
            "sr@latin",  # language+script
        )
        self.invalid_tags = (
            None,  # invalid type: None.
            123,  # invalid type: int.
            b"en",  # invalid type: bytes.
            "eü",  # non-latin characters.
            "en_US",  # locale format.
            "en--us",  # empty subtag.
            "-en",  # leading separator.
            "en-",  # trailing separator.
            "en-US.UTF-8",  # language tag w/ locale encoding.
            "en_US.UTF-8",  # locale format - language w/ region and encoding.
            "ca_ES@valencia",  # locale format - language w/ region and variant.
            # FIXME: The following should be invalid:
            # 'sr@latin',      # locale instead of language tag.
        )

    def test_valid_language_code(self):
        for tag in self.valid_tags:
            with self.subTest(tag), self.settings(LANGUAGE_CODE=tag):
                self.assertEqual(check_setting_language_code(None), [])

    def test_invalid_language_code(self):
        """
        Tests that the `check_setting_language_code` function correctly identifies and reports invalid language codes.

        The function iterates over a set of known invalid language tags, simulating the LANGUAGE_CODE setting with each tag, and verifies that the expected error message is returned. The error message includes the specific invalid language code that was provided. This ensures that the function accurately detects and reports invalid language codes, providing helpful feedback to users.
        """
        msg = "You have provided an invalid value for the LANGUAGE_CODE setting: %r."
        for tag in self.invalid_tags:
            with self.subTest(tag), self.settings(LANGUAGE_CODE=tag):
                self.assertEqual(
                    check_setting_language_code(None),
                    [
                        Error(msg % tag, id="translation.E001"),
                    ],
                )

    def test_valid_languages(self):
        for tag in self.valid_tags:
            with self.subTest(tag), self.settings(LANGUAGES=[(tag, tag)]):
                self.assertEqual(check_setting_languages(None), [])

    def test_invalid_languages(self):
        msg = "You have provided an invalid language code in the LANGUAGES setting: %r."
        for tag in self.invalid_tags:
            with self.subTest(tag), self.settings(LANGUAGES=[(tag, tag)]):
                self.assertEqual(
                    check_setting_languages(None),
                    [
                        Error(msg % tag, id="translation.E002"),
                    ],
                )

    def test_valid_languages_bidi(self):
        for tag in self.valid_tags:
            with self.subTest(tag), self.settings(LANGUAGES_BIDI=[tag]):
                self.assertEqual(check_setting_languages_bidi(None), [])

    def test_invalid_languages_bidi(self):
        """
        Tests the validation of invalid language codes in the LANGUAGES_BIDI setting.

        Checks that providing an invalid language code in the LANGUAGES_BIDI setting raises an error with a descriptive message.

        The test iterates over a set of predefined invalid language tags, verifying that each invalid tag triggers the expected error.

        The error message includes the specific invalid language code provided, allowing for easy identification and correction of the issue.

        The test result is a list of errors, each containing the error message and a unique error identifier ('translation.E003').
        """
        msg = (
            "You have provided an invalid language code in the LANGUAGES_BIDI setting: "
            "%r."
        )
        for tag in self.invalid_tags:
            with self.subTest(tag), self.settings(LANGUAGES_BIDI=[tag]):
                self.assertEqual(
                    check_setting_languages_bidi(None),
                    [
                        Error(msg % tag, id="translation.E003"),
                    ],
                )

    @override_settings(USE_I18N=True, LANGUAGES=[("en", "English")])
    def test_inconsistent_language_settings(self):
        msg = (
            "You have provided a value for the LANGUAGE_CODE setting that is "
            "not in the LANGUAGES setting."
        )
        for tag in ["fr", "fr-CA", "fr-357"]:
            with self.subTest(tag), self.settings(LANGUAGE_CODE=tag):
                self.assertEqual(
                    check_language_settings_consistent(None),
                    [
                        Error(msg, id="translation.E004"),
                    ],
                )

    @override_settings(
        USE_I18N=True,
        LANGUAGES=[
            ("de", "German"),
            ("es", "Spanish"),
            ("fr", "French"),
            ("ca", "Catalan"),
        ],
    )
    def test_valid_variant_consistent_language_settings(self):
        tests = [
            # language + region.
            "fr-CA",
            "es-419",
            "de-at",
            # language + region + variant.
            "ca-ES-valencia",
        ]
        for tag in tests:
            with self.subTest(tag), self.settings(LANGUAGE_CODE=tag):
                self.assertEqual(check_language_settings_consistent(None), [])
