import os

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse, HttpResponsePermanentRedirect
from django.middleware.locale import LocaleMiddleware
from django.template import Context, Template
from django.test import SimpleTestCase, override_settings
from django.test.client import RequestFactory
from django.test.utils import override_script_prefix
from django.urls import clear_url_caches, resolve, reverse, translate_url
from django.utils import translation


class PermanentRedirectLocaleMiddleWare(LocaleMiddleware):
    response_redirect_class = HttpResponsePermanentRedirect


@override_settings(
    USE_I18N=True,
    LOCALE_PATHS=[
        os.path.join(os.path.dirname(__file__), "locale"),
    ],
    LANGUAGE_CODE="en-us",
    LANGUAGES=[
        ("nl", "Dutch"),
        ("en", "English"),
        ("pt-br", "Brazilian Portuguese"),
    ],
    MIDDLEWARE=[
        "django.middleware.locale.LocaleMiddleware",
        "django.middleware.common.CommonMiddleware",
    ],
    ROOT_URLCONF="i18n.patterns.urls.default",
    TEMPLATES=[
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "DIRS": [os.path.join(os.path.dirname(__file__), "templates")],
            "OPTIONS": {
                "context_processors": [
                    "django.template.context_processors.i18n",
                ],
            },
        }
    ],
)
class URLTestCaseBase(SimpleTestCase):
    """
    TestCase base-class for the URL tests.
    """

    def setUp(self):
        # Make sure the cache is empty before we are doing our tests.
        """

        Setup method to prepare the environment for testing.

        This method clears any existing URL caches and schedules a cleanup to occur after the test has completed,
        ensuring that the environment is restored to a clean state. This helps prevent test pollution and ensures
        consistent results across multiple test runs.

        """
        clear_url_caches()
        # Make sure we will leave an empty cache for other testcases.
        self.addCleanup(clear_url_caches)


class URLPrefixTests(URLTestCaseBase):
    """
    Tests if the `i18n_patterns` is adding the prefix correctly.
    """

    def test_not_prefixed(self):
        """
        Tests URL reversal for routes that are not prefixed with a language code.

        Verifies that URLs without a language prefix are correctly reversed in different language contexts.
        The test checks the reversal of a simple URL and a URL that is included in another URL pattern,
        under both English and Dutch translations, ensuring consistent results across languages.
        """
        with translation.override("en"):
            self.assertEqual(reverse("not-prefixed"), "/not-prefixed/")
            self.assertEqual(
                reverse("not-prefixed-included-url"), "/not-prefixed-include/foo/"
            )
        with translation.override("nl"):
            self.assertEqual(reverse("not-prefixed"), "/not-prefixed/")
            self.assertEqual(
                reverse("not-prefixed-included-url"), "/not-prefixed-include/foo/"
            )

    def test_prefixed(self):
        """

        Tests the URL prefixing functionality based on language settings.

        This function verifies that the URL prefix is correctly applied based on the current language setting.
        It tests the prefix for English ('en') and Dutch ('nl') languages, as well as when no language is specified,
        in which case it defaults to the language code defined in the project settings.

        The function ensures that the 'prefixed' URL pattern is correctly reversed and prefixed with the language code.

        """
        with translation.override("en"):
            self.assertEqual(reverse("prefixed"), "/en/prefixed/")
        with translation.override("nl"):
            self.assertEqual(reverse("prefixed"), "/nl/prefixed/")
        with translation.override(None):
            self.assertEqual(
                reverse("prefixed"), "/%s/prefixed/" % settings.LANGUAGE_CODE
            )

    @override_settings(ROOT_URLCONF="i18n.patterns.urls.wrong")
    def test_invalid_prefix_use(self):
        msg = "Using i18n_patterns in an included URLconf is not allowed."
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            reverse("account:register")


@override_settings(ROOT_URLCONF="i18n.patterns.urls.disabled")
class URLDisabledTests(URLTestCaseBase):
    @override_settings(USE_I18N=False)
    def test_prefixed_i18n_disabled(self):
        """
        Tests the behavior of URL reversal when internationalization is disabled.

        Verifies that the URL prefix remains unchanged when the language is switched,
        ensuring consistency in URL generation regardless of the current language setting.

        Checks the reversal of the 'prefixed' URL pattern in both English and Dutch languages,
        confirming that the resulting URL is '/prefixed/' in both cases.
        """
        with translation.override("en"):
            self.assertEqual(reverse("prefixed"), "/prefixed/")
        with translation.override("nl"):
            self.assertEqual(reverse("prefixed"), "/prefixed/")


class RequestURLConfTests(SimpleTestCase):
    @override_settings(ROOT_URLCONF="i18n.patterns.urls.path_unused")
    def test_request_urlconf_considered(self):
        request = RequestFactory().get("/nl/")
        request.urlconf = "i18n.patterns.urls.default"
        middleware = LocaleMiddleware(lambda req: HttpResponse())
        with translation.override("nl"):
            middleware.process_request(request)
        self.assertEqual(request.LANGUAGE_CODE, "nl")


@override_settings(ROOT_URLCONF="i18n.patterns.urls.path_unused")
class PathUnusedTests(URLTestCaseBase):
    """
    If no i18n_patterns is used in root URLconfs, then no language activation
    activation happens based on url prefix.
    """

    def test_no_lang_activate(self):
        """
        Tests that a view without a specified language code activates the default language.

        Verifies that a GET request to a URL without a language prefix returns a successful response (200 status code),
        and that the response's content language and LANGUAGE_CODE context variable are set to the default language, English ('en').
        """
        response = self.client.get("/nl/foo/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-language"], "en")
        self.assertEqual(response.context["LANGUAGE_CODE"], "en")


class URLTranslationTests(URLTestCaseBase):
    """
    Tests if the pattern-strings are translated correctly (within the
    `i18n_patterns` and the normal `patterns` function).
    """

    def test_no_prefix_translated(self):
        with translation.override("en"):
            self.assertEqual(reverse("no-prefix-translated"), "/translated/")
            self.assertEqual(
                reverse("no-prefix-translated-regex"), "/translated-regex/"
            )
            self.assertEqual(
                reverse("no-prefix-translated-slug", kwargs={"slug": "yeah"}),
                "/translated/yeah/",
            )

        with translation.override("nl"):
            self.assertEqual(reverse("no-prefix-translated"), "/vertaald/")
            self.assertEqual(reverse("no-prefix-translated-regex"), "/vertaald-regex/")
            self.assertEqual(
                reverse("no-prefix-translated-slug", kwargs={"slug": "yeah"}),
                "/vertaald/yeah/",
            )

        with translation.override("pt-br"):
            self.assertEqual(reverse("no-prefix-translated"), "/traduzidos/")
            self.assertEqual(
                reverse("no-prefix-translated-regex"), "/traduzidos-regex/"
            )
            self.assertEqual(
                reverse("no-prefix-translated-slug", kwargs={"slug": "yeah"}),
                "/traduzidos/yeah/",
            )

    def test_users_url(self):
        """

        Tests the internationalization of URL reversal for specific routes.

        This function checks that the URL reversal for the 'users' route returns the 
        correct path based on the active language. It also tests the reversal of a 
        route that includes a prefix ('prefixed_xml'). The test covers languages 
        including English, Dutch, and Brazilian Portuguese, ensuring that the URL 
        reversal is correctly localized for each language.

        The test verifies that the reversed URLs match the expected format for each 
        language, including the language code in the URL path.

        """
        with translation.override("en"):
            self.assertEqual(reverse("users"), "/en/users/")

        with translation.override("nl"):
            self.assertEqual(reverse("users"), "/nl/gebruikers/")
            self.assertEqual(reverse("prefixed_xml"), "/nl/prefixed.xml")

        with translation.override("pt-br"):
            self.assertEqual(reverse("users"), "/pt-br/usuarios/")

    def test_translate_url_utility(self):
        """
        Tests the translation of URLs between different languages.

        This function checks the functionality of the translate_url utility by translating
        URLs from English to Dutch and vice versa, ensuring that the translation is
        accurate and preserves any path arguments. It covers various scenarios, including
        URLs with and without arguments, and verifies that the language context is correctly
        set during the translation process.

        The test cases include translating URLs for different sections of the site, such as
        user profiles and account registration, as well as URLs with regular and optional
        arguments. The function also checks that the translation is bidirectional, i.e.,
        it works correctly when translating from Dutch to English as well.

        By verifying the correctness of the translate_url utility, this test ensures that
        the site's URL translation functionality is working as expected, providing a good
        user experience for visitors using different languages. 
        """
        with translation.override("en"):
            self.assertEqual(
                translate_url("/en/nonexistent/", "nl"), "/en/nonexistent/"
            )
            self.assertEqual(translate_url("/en/users/", "nl"), "/nl/gebruikers/")
            # Namespaced URL
            self.assertEqual(
                translate_url("/en/account/register/", "nl"), "/nl/profiel/registreren/"
            )
            # path() URL pattern
            self.assertEqual(
                translate_url("/en/account/register-as-path/", "nl"),
                "/nl/profiel/registreren-als-pad/",
            )
            self.assertEqual(translation.get_language(), "en")
            # re_path() URL with parameters.
            self.assertEqual(
                translate_url("/en/with-arguments/regular-argument/", "nl"),
                "/nl/with-arguments/regular-argument/",
            )
            self.assertEqual(
                translate_url(
                    "/en/with-arguments/regular-argument/optional.html", "nl"
                ),
                "/nl/with-arguments/regular-argument/optional.html",
            )
            # path() URL with parameter.
            self.assertEqual(
                translate_url("/en/path-with-arguments/regular-argument/", "nl"),
                "/nl/path-with-arguments/regular-argument/",
            )

        with translation.override("nl"):
            self.assertEqual(translate_url("/nl/gebruikers/", "en"), "/en/users/")
            self.assertEqual(translation.get_language(), "nl")

    def test_reverse_translated_with_captured_kwargs(self):
        with translation.override("en"):
            match = resolve("/translated/apo/")
        # Links to the same page in other languages.
        tests = [
            ("nl", "/vertaald/apo/"),
            ("pt-br", "/traduzidos/apo/"),
        ]
        for lang, expected_link in tests:
            with translation.override(lang):
                self.assertEqual(
                    reverse(
                        match.url_name, args=match.args, kwargs=match.captured_kwargs
                    ),
                    expected_link,
                )

    def test_locale_not_interepreted_as_regex(self):
        with translation.override("e("):
            # Would previously error:
            # re.error: missing ), unterminated subpattern at position 1
            reverse("users")


class URLNamespaceTests(URLTestCaseBase):
    """
    Tests if the translations are still working within namespaces.
    """

    def test_account_register(self):
        """
        Tests account registration URL reversal for different languages.

        Verifies that the account registration URL is correctly resolved for both English and Dutch translations.
        Checks the standard registration URL as well as the 'register-as-path' variant for each language.

        The test ensures that URL reversal produces the expected paths, which are '/en/account/register/' and '/en/account/register-as-path/' for English,
        and '/nl/profiel/registreren/' and '/nl/profiel/registreren-als-pad/' for Dutch, respectively.
        """
        with translation.override("en"):
            self.assertEqual(reverse("account:register"), "/en/account/register/")
            self.assertEqual(
                reverse("account:register-as-path"), "/en/account/register-as-path/"
            )

        with translation.override("nl"):
            self.assertEqual(reverse("account:register"), "/nl/profiel/registreren/")
            self.assertEqual(
                reverse("account:register-as-path"), "/nl/profiel/registreren-als-pad/"
            )


class URLRedirectTests(URLTestCaseBase):
    """
    Tests if the user gets redirected to the right URL when there is no
    language-prefix in the request URL.
    """

    def test_no_prefix_response(self):
        """

        Tests that a successful HTTP response is returned when accessing a URL without a prefix.

        This test case verifies that the application correctly handles requests to URLs that do not contain a prefix, 
        returning a response with a status code of 200 (OK).

        """
        response = self.client.get("/not-prefixed/")
        self.assertEqual(response.status_code, 200)

    def test_en_redirect(self):
        """

        Tests that accessing the account registration page without a language prefix redirects to the English version of the page.

        The test sends a GET request to the registration page with the 'accept-language' header set to English, 
        verifies that the response is a redirect to the English version of the page, 
        and then checks that the subsequent GET request to the redirect location returns a successful response.

        """
        response = self.client.get(
            "/account/register/", headers={"accept-language": "en"}
        )
        self.assertRedirects(response, "/en/account/register/")

        response = self.client.get(response.headers["location"])
        self.assertEqual(response.status_code, 200)

    def test_en_redirect_wrong_url(self):
        """
        Tests that an English-speaking user is correctly redirected to a 404 page when attempting to access the Dutch registration profile URL.

        This test ensures that when a user with English locale settings tries to access a URL that is not supported in their language, the application responds with a 404 status code, indicating that the requested page was not found.

        The test covers a specific scenario where the URL '/profiel/registreren/' is requested with the 'accept-language' header set to 'en', which is not the correct URL for English-speaking users.

        By verifying the 404 status code, this test confirms that the application is correctly handling language-based redirects and providing a suitable error response when an unsupported URL is accessed.
        """
        response = self.client.get(
            "/profiel/registreren/", headers={"accept-language": "en"}
        )
        self.assertEqual(response.status_code, 404)

    def test_nl_redirect(self):
        response = self.client.get(
            "/profiel/registreren/", headers={"accept-language": "nl"}
        )
        self.assertRedirects(response, "/nl/profiel/registreren/")

        response = self.client.get(response.headers["location"])
        self.assertEqual(response.status_code, 200)

    def test_nl_redirect_wrong_url(self):
        """
        ..: 
            Tests that a request to the registration page with an 'accept-language' header set to Dutch ('nl') returns a 404 status code, 
            indicating that the page is not found, as the redirect to the correct URL for the given locale is not performed correctly.
        """
        response = self.client.get(
            "/account/register/", headers={"accept-language": "nl"}
        )
        self.assertEqual(response.status_code, 404)

    def test_pt_br_redirect(self):
        """

        Checks if a redirect to the Portuguese-Brazilian (pt-br) version of the registration page occurs when the accept-language header is set to pt-br.

        This test case verifies that a GET request to the registration page with the accept-language set to pt-br results in a redirect to the pt-br version of the page. After the redirect, it checks that the resulting page returns a successful response (200 status code).

        """
        response = self.client.get(
            "/conta/registre-se/", headers={"accept-language": "pt-br"}
        )
        self.assertRedirects(response, "/pt-br/conta/registre-se/")

        response = self.client.get(response.headers["location"])
        self.assertEqual(response.status_code, 200)

    def test_pl_pl_redirect(self):
        # language from outside of the supported LANGUAGES list
        """
        Tests that a request to the account registration page with Polish locale ('pl-pl') redirects to the English version of the page.

        The test verifies that the redirect occurs and that the subsequent request to the redirected page results in a successful response (200 status code).
        """
        response = self.client.get(
            "/account/register/", headers={"accept-language": "pl-pl"}
        )
        self.assertRedirects(response, "/en/account/register/")

        response = self.client.get(response.headers["location"])
        self.assertEqual(response.status_code, 200)

    @override_settings(
        MIDDLEWARE=[
            "i18n.patterns.tests.PermanentRedirectLocaleMiddleWare",
            "django.middleware.common.CommonMiddleware",
        ],
    )
    def test_custom_redirect_class(self):
        """
        Tests that a request to a non-prefixed URL is permanently redirected to its equivalent URL with the current language prefix.

        The test verifies that the redirect is correctly performed by the PermanentRedirectLocaleMiddleware,
        checking both the status code of the response and the target URL of the redirect.

        The test case covers the scenario where the request is made with the 'en' language specified in the Accept-Language header,
        and asserts that the response is a 301 permanent redirect to the URL with the 'en' language prefix.
        """
        response = self.client.get(
            "/account/register/", headers={"accept-language": "en"}
        )
        self.assertRedirects(response, "/en/account/register/", 301)


class URLVaryAcceptLanguageTests(URLTestCaseBase):
    """
    'Accept-Language' is not added to the Vary header when using prefixed URLs.
    """

    def test_no_prefix_response(self):
        response = self.client.get("/not-prefixed/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get("Vary"), "Accept-Language")

    def test_en_redirect(self):
        """
        The redirect to a prefixed URL depends on 'Accept-Language' and
        'Cookie', but once prefixed no header is set.
        """
        response = self.client.get(
            "/account/register/", headers={"accept-language": "en"}
        )
        self.assertRedirects(response, "/en/account/register/")
        self.assertEqual(response.get("Vary"), "Accept-Language, Cookie")

        response = self.client.get(response.headers["location"])
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get("Vary"))


class URLRedirectWithoutTrailingSlashTests(URLTestCaseBase):
    """
    Tests the redirect when the requested URL doesn't end with a slash
    (`settings.APPEND_SLASH=True`).
    """

    def test_not_prefixed_redirect(self):
        """

        Tests that a GET request to a URL without a trailing slash is correctly redirected.

        This test checks if the server properly handles a request to a URL that does not have a trailing slash,
        by redirecting the client to the same URL with a trailing slash appended. The test is performed with
        an English language preference and verifies that a 301 permanent redirect status code is returned.

        """
        response = self.client.get("/not-prefixed", headers={"accept-language": "en"})
        self.assertRedirects(response, "/not-prefixed/", 301)

    def test_en_redirect(self):
        """
        Tests English language redirects for the registration and prefixed.xml pages.

        This test ensures that when a user with an English language preference visits the 
        account registration and prefixed.xml pages without a language prefix, they are 
        properly redirected to the corresponding English language pages.

        The redirects are verified to occur with a 302 status code, indicating a 
        temporary redirect. The test covers both the registration page and a prefixed.xml 
        page to ensure consistent redirect behavior across different types of content.
        """
        response = self.client.get(
            "/account/register", headers={"accept-language": "en"}, follow=True
        )
        # We only want one redirect, bypassing CommonMiddleware
        self.assertEqual(response.redirect_chain, [("/en/account/register/", 302)])
        self.assertRedirects(response, "/en/account/register/", 302)

        response = self.client.get(
            "/prefixed.xml", headers={"accept-language": "en"}, follow=True
        )
        self.assertRedirects(response, "/en/prefixed.xml", 302)


class URLRedirectWithoutTrailingSlashSettingTests(URLTestCaseBase):
    """
    Tests the redirect when the requested URL doesn't end with a slash
    (`settings.APPEND_SLASH=False`).
    """

    @override_settings(APPEND_SLASH=False)
    def test_not_prefixed_redirect(self):
        """
        Tests that a GET request to a non-prefixed URL returns a 404 status code.

        This test case verifies that when the APPEND_SLASH setting is disabled, the application correctly handles URLs without a trailing slash and does not incorrectly redirect to a prefixed URL.

        Issues tested include:
            * Handling of non-prefixed URLs
            * Error handling for 404 status codes
            * Integration with the APPEND_SLASH setting
        """
        response = self.client.get("/not-prefixed", headers={"accept-language": "en"})
        self.assertEqual(response.status_code, 404)

    @override_settings(APPEND_SLASH=False)
    def test_en_redirect(self):
        """
        Tests that an English-speaking user is correctly redirected to the English version of the registration page when accessing the URL without a language prefix. 

        The test sends a GET request to the registration page without a trailing slash and verifies that the response is a 302 redirect to the same page with the English language prefix added. It then follows this redirect and checks that the resulting page returns a 200 status code, indicating a successful request.
        """
        response = self.client.get(
            "/account/register-without-slash", headers={"accept-language": "en"}
        )
        self.assertRedirects(response, "/en/account/register-without-slash", 302)

        response = self.client.get(response.headers["location"])
        self.assertEqual(response.status_code, 200)


class URLResponseTests(URLTestCaseBase):
    """Tests if the response has the correct language code."""

    def test_not_prefixed_with_prefix(self):
        """

        Tests that a URL not prefixed with a language code returns a 404 status code.

        This test case verifies that the application correctly handles URLs that do not include a language prefix.
        It checks that the server returns a \"Not Found\" response, indicating that the requested URL is not valid.

        """
        response = self.client.get("/en/not-prefixed/")
        self.assertEqual(response.status_code, 404)

    def test_en_url(self):
        """
        Tests the registration page for English language support.

        Verifies that a GET request to the English registration page returns a successful response (200 status code),
        and that the response is properly localized for English, including the Content-Language header and LANGUAGE_CODE context variable.

        This test ensures that the application correctly handles English language settings for the registration page.
        """
        response = self.client.get("/en/account/register/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-language"], "en")
        self.assertEqual(response.context["LANGUAGE_CODE"], "en")

    def test_nl_url(self):
        """
        Tests to ensure the Dutch ('nl') registration profile URL returns a successful response.

        Verifies that the HTTP request to the '/nl/profiel/registreren/' URL results in a status code of 200 (OK), 
        and that the response is correctly set to use the Dutch language, both in the 'content-language' header and 
        the 'LANGUAGE_CODE' context variable.
        """
        response = self.client.get("/nl/profiel/registreren/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-language"], "nl")
        self.assertEqual(response.context["LANGUAGE_CODE"], "nl")

    def test_wrong_en_prefix(self):
        """

        Tests that accessing the English registration profile page with a wrong prefix returns a 404 status code.

        This test case verifies that the URL '/en/profiel/registreren/' does not exist and the server responds with a 'Not Found' error.

        """
        response = self.client.get("/en/profiel/registreren/")
        self.assertEqual(response.status_code, 404)

    def test_wrong_nl_prefix(self):
        """
        Tests that accessing the Dutch account registration page without the correct language prefix results in a 404 Not Found status code, verifying that language prefixes are properly enforced for the specified URL.
        """
        response = self.client.get("/nl/account/register/")
        self.assertEqual(response.status_code, 404)

    def test_pt_br_url(self):
        """

        Tests whether the Portuguese (Brazil) language version of the registration page URL 
        returns a successful response, with the correct language code set in the response headers 
        and context.

        The test case checks for the following conditions:
        - A HTTP status code of 200 (OK) is returned.
        - The 'content-language' header is set to 'pt-br'.
        - The LANGUAGE_CODE in the response context is set to 'pt-br'.

        """
        response = self.client.get("/pt-br/conta/registre-se/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-language"], "pt-br")
        self.assertEqual(response.context["LANGUAGE_CODE"], "pt-br")

    def test_en_path(self):
        """
        Tests the English (/en) path for the account registration page.

        Verifies that the page returns a successful HTTP response (200 OK), 
        that the content language is set to English, and that the language 
        code in the response context is also English.
        """
        response = self.client.get("/en/account/register-as-path/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-language"], "en")
        self.assertEqual(response.context["LANGUAGE_CODE"], "en")

    def test_nl_path(self):
        response = self.client.get("/nl/profiel/registreren-als-pad/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-language"], "nl")
        self.assertEqual(response.context["LANGUAGE_CODE"], "nl")


@override_settings(ROOT_URLCONF="i18n.urls_default_unprefixed", LANGUAGE_CODE="nl")
class URLPrefixedFalseTranslatedTests(URLTestCaseBase):
    def test_translated_path_unprefixed_language_other_than_accepted_header(self):
        response = self.client.get("/gebruikers/", headers={"accept-language": "en"})
        self.assertEqual(response.status_code, 200)

    def test_translated_path_unprefixed_language_other_than_cookie_language(self):
        """
        Tests that a translated path without a language prefix is correctly handled when the language of the request differs from the language stored in the cookie.

        This test case verifies that the server returns a successful response (200 OK) when the client requests a translated URL path without a language prefix, while the language cookie is set to a different language ('en' in this case).

        The test covers the scenario where the client's preferred language (as indicated by the cookie) does not match the language of the requested path, ensuring that the server can correctly resolve the path and return the expected response.
        """
        self.client.cookies.load({settings.LANGUAGE_COOKIE_NAME: "en"})
        response = self.client.get("/gebruikers/")
        self.assertEqual(response.status_code, 200)

    def test_translated_path_prefixed_language_other_than_accepted_header(self):
        """
        Tests that a translated path with a language prefix other than the accepted language header returns a successful response.

        This test scenario ensures that the server can handle requests where the language prefix in the URL differs from the language specified in the Accept-Language header. It verifies that the response status code is 200, indicating a successful request.

        The test uses a specific example where the URL has an English language prefix ('/en/'), but the Accept-Language header is set to Dutch ('nl').
        """
        response = self.client.get("/en/users/", headers={"accept-language": "nl"})
        self.assertEqual(response.status_code, 200)

    def test_translated_path_prefixed_language_other_than_cookie_language(self):
        """

        Checks that a URL prefixed with a language code other than the one specified in the language cookie redirects correctly.

        This test verifies that the server responds with a successful status code (200) when a request is made to a URL with a language prefix
        different from the language set in the cookie. 

        In this case, the language cookie is set to 'nl' (Dutch), but the URL requested is '/en/users/', which is prefixed with 'en' (English).

        The test ensures that the server handles such requests correctly and returns the expected content without attempting to redirect to the 
        language specified in the cookie.

        """
        self.client.cookies.load({settings.LANGUAGE_COOKIE_NAME: "nl"})
        response = self.client.get("/en/users/")
        self.assertEqual(response.status_code, 200)


class URLRedirectWithScriptAliasTests(URLTestCaseBase):
    """
    #21579 - LocaleMiddleware should respect the script prefix.
    """

    def test_language_prefix_with_script_prefix(self):
        prefix = "/script_prefix"
        with override_script_prefix(prefix):
            response = self.client.get(
                "/prefixed/", headers={"accept-language": "en"}, SCRIPT_NAME=prefix
            )
            self.assertRedirects(
                response, "%s/en/prefixed/" % prefix, target_status_code=404
            )


class URLTagTests(URLTestCaseBase):
    """
    Test if the language tag works.
    """

    def test_strings_only(self):
        t = Template(
            """{% load i18n %}
            {% language 'nl' %}{% url 'no-prefix-translated' %}{% endlanguage %}
            {% language 'pt-br' %}{% url 'no-prefix-translated' %}{% endlanguage %}"""
        )
        self.assertEqual(
            t.render(Context({})).strip().split(), ["/vertaald/", "/traduzidos/"]
        )

    def test_context(self):
        """

        Tests the rendering of a template with language context.

        This function verifies that a template using the language context tag renders correctly,
        producing the expected URL output for each language. It checks that the language-specific
        URLs are correctly translated and rendered in the output.

        """
        ctx = Context({"lang1": "nl", "lang2": "pt-br"})
        tpl = Template(
            """{% load i18n %}
            {% language lang1 %}{% url 'no-prefix-translated' %}{% endlanguage %}
            {% language lang2 %}{% url 'no-prefix-translated' %}{% endlanguage %}"""
        )
        self.assertEqual(
            tpl.render(ctx).strip().split(), ["/vertaald/", "/traduzidos/"]
        )

    def test_args(self):
        tpl = Template(
            """
            {% load i18n %}
            {% language 'nl' %}
            {% url 'no-prefix-translated-slug' 'apo' %}{% endlanguage %}
            {% language 'pt-br' %}
            {% url 'no-prefix-translated-slug' 'apo' %}{% endlanguage %}
            """
        )
        self.assertEqual(
            tpl.render(Context({})).strip().split(),
            ["/vertaald/apo/", "/traduzidos/apo/"],
        )

    def test_kwargs(self):
        """
        Tests the creation of URLs with translated slugs using keyword arguments.

        This test case checks if the ``url`` template tag correctly generates URLs for different languages, 
        when the slug is passed as a keyword argument. It verifies that the resulting URLs are correctly 
        translated and prefixed according to the language code.

        The test covers two languages: Dutch (nl) and Brazilian Portuguese (pt-br), with the expected 
        URLs being '/vertaald/apo/' and '/traduzidos/apo/' respectively.

        The purpose of this test is to ensure that the translation and URL generation functionality works 
        correctly when using keyword arguments, providing a reliable way to create translated URLs in templates.
        """
        tpl = Template(
            """
            {% load i18n %}
            {% language 'nl'  %}
            {% url 'no-prefix-translated-slug' slug='apo' %}{% endlanguage %}
            {% language 'pt-br' %}
            {% url 'no-prefix-translated-slug' slug='apo' %}{% endlanguage %}
            """
        )
        self.assertEqual(
            tpl.render(Context({})).strip().split(),
            ["/vertaald/apo/", "/traduzidos/apo/"],
        )
