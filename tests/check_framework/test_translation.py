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
        """

        Set up test data for language tag validation.

        This method initializes two class attributes: 
        - valid_tags: a collection of valid language tags according to the language tag syntax rules.
        - invalid_tags: a collection of invalid language tags that are used to test validation error handling.

        These tags are used to test the validity of language tags, ensuring that they conform to the expected format.

        """
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
        """
        Checks if the LANGUAGE_CODE setting is valid by iterating over a list of valid language codes.

        This test case ensures that the check_setting_language_code function behaves correctly when given a valid LANGUAGE_CODE.
        It tests each valid language code in isolation, verifying that no errors are raised when the LANGUAGE_CODE is set to a valid value.

        :raises AssertionError: If any of the valid language codes cause an error when passed to check_setting_language_code.
        """
        for tag in self.valid_tags:
            with self.subTest(tag), self.settings(LANGUAGE_CODE=tag):
                self.assertEqual(check_setting_language_code(None), [])

    def test_invalid_language_code(self):
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
        """

        Verifies the correctness of valid language settings.

        This test case checks each valid language tag to ensure that the check_setting_languages function properly handles them.
        It iterates through a list of valid tags, sets the language setting for each one, and asserts that the function returns an empty list as expected.
        The test is run once for each valid language tag, allowing for precise identification of any issues that may arise during the validation process.

        """
        for tag in self.valid_tags:
            with self.subTest(tag), self.settings(LANGUAGES=[(tag, tag)]):
                self.assertEqual(check_setting_languages(None), [])

    def test_invalid_languages(self):
        """

        Tests the validation of the LANGUAGES setting by passing an invalid language code.

        This test checks that the `check_setting_languages` function correctly identifies and reports
        invalid language codes provided in the LANGUAGES setting. It iterates over a set of predefined
        invalid language tags, simulating a scenario where each tag is used in the setting.
        The test verifies that for each invalid tag, the function returns an error with the expected
        message, indicating that the language code is invalid.

        The test does not cover the functionality of the `check_setting_languages` function itself,
        but rather its behavior when handling invalid input.

        """
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
        Tests that the check_setting_languages_bidi function correctly handles invalid language codes in the LANGUAGES_BIDI setting.

        It checks for each invalid language tag that the function returns an error message, indicating that the provided language code is not valid.

        The expected error message includes the invalid language code and the error ID 'translation.E003', which is specific to translation settings errors.

        The test covers multiple invalid language codes to ensure that the function behaves correctly in different scenarios.
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
        """
        Tests that the application's language settings are consistent for various valid language variants, ensuring proper internationalization support. 

        The function verifies that the language settings for multiple locale tags, such as regional variations of French, Spanish, German, and Catalan, are correctly configured and do not produce any inconsistencies. 

        The test covers different scenarios where the language code includes a region or dialect, and asserts that the check for consistent language settings returns an empty list, indicating no inconsistencies. 

        This test is crucial for maintaining a seamless user experience across different languages and regions, and ensures that the application's language support is robust and reliable.
        """
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
