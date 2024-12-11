import string
import uuid

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase
from django.test.utils import override_settings
from django.urls import (
    NoReverseMatch,
    Resolver404,
    path,
    re_path,
    register_converter,
    resolve,
    reverse,
)
from django.urls.converters import REGISTERED_CONVERTERS, IntConverter
from django.utils.deprecation import RemovedInDjango60Warning
from django.views import View

from .converters import Base64Converter, DynamicConverter
from .views import empty_view

included_kwargs = {"base": b"hello", "value": b"world"}
converter_test_data = (
    # ('url', ('url_name', 'app_name', {kwargs})),
    # aGVsbG8= is 'hello' encoded in base64.
    ("/base64/aGVsbG8=/", ("base64", "", {"value": b"hello"})),
    (
        "/base64/aGVsbG8=/subpatterns/d29ybGQ=/",
        ("subpattern-base64", "", included_kwargs),
    ),
    (
        "/base64/aGVsbG8=/namespaced/d29ybGQ=/",
        ("subpattern-base64", "namespaced-base64", included_kwargs),
    ),
)


@override_settings(ROOT_URLCONF="urlpatterns.path_urls")
class SimplifiedURLTests(SimpleTestCase):
    def test_path_lookup_without_parameters(self):
        """

        Tests the functionality of path lookup without any URL parameters.

        Verifies that the resolver correctly identifies the URL name, route, and empty arguments (both captured and extra keyword arguments) 
        for a given URL path. This ensures that the resolver behaves as expected when no parameters are specified in the URL.

        """
        match = resolve("/articles/2003/")
        self.assertEqual(match.url_name, "articles-2003")
        self.assertEqual(match.args, ())
        self.assertEqual(match.kwargs, {})
        self.assertEqual(match.route, "articles/2003/")
        self.assertEqual(match.captured_kwargs, {})
        self.assertEqual(match.extra_kwargs, {})

    def test_path_lookup_with_typed_parameters(self):
        """
        Tests the path lookup functionality with typed parameters, specifically checking the resolution of a URL path with an integer parameter. 

        This test case verifies that the URL '/articles/2015/' is correctly matched and its components are properly extracted, including the URL name, arguments, keyword arguments, route, captured keyword arguments, and extra keyword arguments. 

        The test ensures that the typed parameter 'year' is correctly identified and typed as an integer, with the value 2015, and that all other components of the match are as expected.
        """
        match = resolve("/articles/2015/")
        self.assertEqual(match.url_name, "articles-year")
        self.assertEqual(match.args, ())
        self.assertEqual(match.kwargs, {"year": 2015})
        self.assertEqual(match.route, "articles/<int:year>/")
        self.assertEqual(match.captured_kwargs, {"year": 2015})
        self.assertEqual(match.extra_kwargs, {})

    def test_path_lookup_with_multiple_parameters(self):
        """
        Tests the functionality of path lookup with multiple parameters.
        This function verifies that a given URL pattern can be correctly resolved
        into its constituent parts, including the URL name, route, and captured keyword arguments.
        Specifically, it checks that the path '/articles/2015/04/12/' is resolved to the 
        'articles-year-month-day' URL name, with the year, month, and day extracted as keyword arguments.
        """
        match = resolve("/articles/2015/04/12/")
        self.assertEqual(match.url_name, "articles-year-month-day")
        self.assertEqual(match.args, ())
        self.assertEqual(match.kwargs, {"year": 2015, "month": 4, "day": 12})
        self.assertEqual(match.route, "articles/<int:year>/<int:month>/<int:day>/")
        self.assertEqual(match.captured_kwargs, {"year": 2015, "month": 4, "day": 12})
        self.assertEqual(match.extra_kwargs, {})

    def test_path_lookup_with_multiple_parameters_and_extra_kwarg(self):
        match = resolve("/books/2015/04/12/")
        self.assertEqual(match.url_name, "books-year-month-day")
        self.assertEqual(match.args, ())
        self.assertEqual(
            match.kwargs, {"year": 2015, "month": 4, "day": 12, "extra": True}
        )
        self.assertEqual(match.route, "books/<int:year>/<int:month>/<int:day>/")
        self.assertEqual(match.captured_kwargs, {"year": 2015, "month": 4, "day": 12})
        self.assertEqual(match.extra_kwargs, {"extra": True})

    def test_path_lookup_with_extra_kwarg(self):
        match = resolve("/books/2007/")
        self.assertEqual(match.url_name, "books-2007")
        self.assertEqual(match.args, ())
        self.assertEqual(match.kwargs, {"extra": True})
        self.assertEqual(match.route, "books/2007/")
        self.assertEqual(match.captured_kwargs, {})
        self.assertEqual(match.extra_kwargs, {"extra": True})

    def test_two_variable_at_start_of_path_pattern(self):
        """
        .. method:: test_two_variable_at_start_of_path_pattern

           Tests the functionality of resolving a path pattern with two variables at the start of the path.

           This test case checks the resolution of a URL with a language code at the start of the path.
           It verifies that the resolved URL name is correctly identified, and that the language and path components are correctly captured and passed as keyword arguments.
           The test also checks that the route pattern and extra keyword arguments are correctly determined.
        """
        match = resolve("/en/foo/")
        self.assertEqual(match.url_name, "lang-and-path")
        self.assertEqual(match.kwargs, {"lang": "en", "url": "foo"})
        self.assertEqual(match.route, "<lang>/<path:url>/")
        self.assertEqual(match.captured_kwargs, {"lang": "en", "url": "foo"})
        self.assertEqual(match.extra_kwargs, {})

    def test_re_path(self):
        """
        Checks the functionality of URL resolver for a given regular expression URL path. 
        Verifies that the resolver correctly matches the URL and extracts the expected keyword arguments.
        The test case ensures that the resolved URL name, keyword arguments, route pattern, and captured keyword arguments are as expected, 
        while also checking for the absence of any extra keyword arguments.
        """
        match = resolve("/regex/1/")
        self.assertEqual(match.url_name, "regex")
        self.assertEqual(match.kwargs, {"pk": "1"})
        self.assertEqual(match.route, "^regex/(?P<pk>[0-9]+)/$")
        self.assertEqual(match.captured_kwargs, {"pk": "1"})
        self.assertEqual(match.extra_kwargs, {})

    def test_re_path_with_optional_parameter(self):
        """
        Tests the resolution of URLs against a regular expression path with an optional parameter.

        The function verifies that the URL resolver correctly matches URLs with both required and optional parameters, 
        and that the resulting match object contains the expected keyword arguments and route information.

        It checks the consistency of the matched URL name, keyword arguments, route regular expression, 
        captured keyword arguments, and extra keyword arguments, ensuring that the resolver behaves as expected 
        in different scenarios with optional parameters.
        """
        for url, kwargs in (
            ("/regex_optional/1/2/", {"arg1": "1", "arg2": "2"}),
            ("/regex_optional/1/", {"arg1": "1"}),
        ):
            with self.subTest(url=url):
                match = resolve(url)
                self.assertEqual(match.url_name, "regex_optional")
                self.assertEqual(match.kwargs, kwargs)
                self.assertEqual(
                    match.route,
                    r"^regex_optional/(?P<arg1>\d+)/(?:(?P<arg2>\d+)/)?",
                )
                self.assertEqual(match.captured_kwargs, kwargs)
                self.assertEqual(match.extra_kwargs, {})

    def test_re_path_with_missing_optional_parameter(self):
        match = resolve("/regex_only_optional/")
        self.assertEqual(match.url_name, "regex_only_optional")
        self.assertEqual(match.kwargs, {})
        self.assertEqual(match.args, ())
        self.assertEqual(
            match.route,
            r"^regex_only_optional/(?:(?P<arg1>\d+)/)?",
        )
        self.assertEqual(match.captured_kwargs, {})
        self.assertEqual(match.extra_kwargs, {})

    def test_path_lookup_with_inclusion(self):
        """

        Tests the path lookup functionality when using URL inclusion.

        Verifies that the resolve function correctly matches URLs that are part of an included URL configuration.
        The test checks that the resulting match object contains the expected URL name and route pattern.

        """
        match = resolve("/included_urls/extra/something/")
        self.assertEqual(match.url_name, "inner-extra")
        self.assertEqual(match.route, "included_urls/extra/<extra>/")

    def test_path_lookup_with_empty_string_inclusion(self):
        """

        Tests the path lookup functionality when an empty string is included.
        Verifies that the resolve function correctly handles the URL pattern
        '^more/(?P<extra>\\w+)/$' and extracts the expected keyword arguments.
        Ensures that the URL name, route, and keyword arguments are properly matched
        and separated into captured, extra, and regular keyword arguments.

        """
        match = resolve("/more/99/")
        self.assertEqual(match.url_name, "inner-more")
        self.assertEqual(match.route, r"^more/(?P<extra>\w+)/$")
        self.assertEqual(match.kwargs, {"extra": "99", "sub-extra": True})
        self.assertEqual(match.captured_kwargs, {"extra": "99"})
        self.assertEqual(match.extra_kwargs, {"sub-extra": True})

    def test_path_lookup_with_double_inclusion(self):
        """
        Tests the path lookup functionality with double inclusion.

        Verifies that a URL with multiple levels of inclusion is correctly resolved, 
        including the extraction of URL parameters. The test checks that the 
        resolved URL name and route pattern match the expected values, 
        ensuring that the path lookup mechanism handles nested inclusions correctly.
        """
        match = resolve("/included_urls/more/some_value/")
        self.assertEqual(match.url_name, "inner-more")
        self.assertEqual(match.route, r"included_urls/more/(?P<extra>\w+)/$")

    def test_path_reverse_without_parameter(self):
        url = reverse("articles-2003")
        self.assertEqual(url, "/articles/2003/")

    def test_path_reverse_with_parameter(self):
        url = reverse(
            "articles-year-month-day", kwargs={"year": 2015, "month": 4, "day": 12}
        )
        self.assertEqual(url, "/articles/2015/4/12/")

    @override_settings(ROOT_URLCONF="urlpatterns.path_base64_urls")
    def test_converter_resolve(self):
        """
        Tests the URL resolver for base64 encoded URLs.

        This function iterates over a set of predefined test data, containing URLs and their corresponding expected outcomes, 
        and checks that the `resolve` function correctly identifies the URL name, application name, and keyword arguments for each URL.
        Any discrepancies between the actual and expected results are reported as test failures.
        """
        for url, (url_name, app_name, kwargs) in converter_test_data:
            with self.subTest(url=url):
                match = resolve(url)
                self.assertEqual(match.url_name, url_name)
                self.assertEqual(match.app_name, app_name)
                self.assertEqual(match.kwargs, kwargs)

    @override_settings(ROOT_URLCONF="urlpatterns.path_base64_urls")
    def test_converter_reverse(self):
        """

        Tests the converter's ability to reverse URLs.

        This test iterates over a set of test data, where each item consists of an expected URL and 
        parameters to reverse a URL (URL name, app name, and keyword arguments). It then attempts 
        to reverse the URL using the provided parameters and checks if the result matches the 
        expected output. The test covers both URL names with and without app names.

        The test uses Django's override settings to ensure the test is run with a specific 
        root URL configuration. 

        Parameters and edge cases are covered through the use of sub-tests, allowing for easy 
        identification of failures.

        """
        for expected, (url_name, app_name, kwargs) in converter_test_data:
            if app_name:
                url_name = "%s:%s" % (app_name, url_name)
            with self.subTest(url=url_name):
                url = reverse(url_name, kwargs=kwargs)
                self.assertEqual(url, expected)

    @override_settings(ROOT_URLCONF="urlpatterns.path_base64_urls")
    def test_converter_reverse_with_second_layer_instance_namespace(self):
        """
        Test if the URL converter can correctly reverse a URL with base64-encoded values, 
            using a Namespaced URL pattern instance, and a second layer of URL patterns. 
            The test verifies that the reversed URL matches the expected output, 
            demonstrating proper handling of base64-encoded query parameters and nested URL patterns.
        """
        kwargs = included_kwargs.copy()
        kwargs["last_value"] = b"world"
        url = reverse("instance-ns-base64:subsubpattern-base64", kwargs=kwargs)
        self.assertEqual(url, "/base64/aGVsbG8=/subpatterns/d29ybGQ=/d29ybGQ=/")

    def test_path_inclusion_is_matchable(self):
        """
        Tests if a URL within an included path can be matched by the URL resolver.

        Verifies that a URL can be resolved and its corresponding URL name and keyword arguments can be correctly identified.
        The test checks if the resolver correctly handles URLs within an included path and extracts the expected URL name and keyword arguments.
        """
        match = resolve("/included_urls/extra/something/")
        self.assertEqual(match.url_name, "inner-extra")
        self.assertEqual(match.kwargs, {"extra": "something"})

    def test_path_inclusion_is_reversible(self):
        url = reverse("inner-extra", kwargs={"extra": "something"})
        self.assertEqual(url, "/included_urls/extra/something/")

    def test_invalid_kwargs(self):
        """
        Tests that passing invalid keyword arguments to path and re_path functions raises a TypeError.

        Specifically, this test case checks that passing a string instead of a dictionary as keyword arguments results in an error.

        The expected error message is 'kwargs argument must be a dict, but got str.'.

        This test ensures that the functions correctly validate their input and raise informative errors when necessary.
        """
        msg = "kwargs argument must be a dict, but got str."
        with self.assertRaisesMessage(TypeError, msg):
            path("hello/", empty_view, "name")
        with self.assertRaisesMessage(TypeError, msg):
            re_path("^hello/$", empty_view, "name")

    def test_invalid_converter(self):
        """
        Tests that using an invalid converter in a URL route raises an ImproperlyConfigured exception.

        The test checks that when an unknown converter (in this case, 'nonexistent') is used in a URL pattern, the application correctly detects and reports this as an error, providing a clear and informative error message.
        """
        msg = "URL route 'foo/<nonexistent:var>/' uses invalid converter 'nonexistent'."
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            path("foo/<nonexistent:var>/", empty_view)

    def test_warning_override_default_converter(self):
        # RemovedInDjango60Warning: when the deprecation ends, replace with
        # msg = "Converter 'int' is already registered."
        # with self.assertRaisesMessage(ValueError, msg):
        """
        ylabel
        Tests that overriding the default converter for 'int' type raises a RemovedInDjango60Warning.

        The function verifies that attempting to register a converter for a type that already has a registered converter triggers the expected deprecation warning.

        Args:
            None

        Returns:
            None

        Raises:
            RemovedInDjango60Warning: If the 'int' converter is already registered when attempting to override it.
        """
        msg = (
            "Converter 'int' is already registered. Support for overriding registered "
            "converters is deprecated and will be removed in Django 6.0."
        )
        try:
            with self.assertWarnsMessage(RemovedInDjango60Warning, msg):
                register_converter(IntConverter, "int")
        finally:
            REGISTERED_CONVERTERS.pop("int", None)

    def test_warning_override_converter(self):
        # RemovedInDjango60Warning: when the deprecation ends, replace with
        # msg = "Converter 'base64' is already registered."
        # with self.assertRaisesMessage(ValueError, msg):
        """
        Tests that overriding a registered converter issues a deprecation warning.

        The test checks that attempting to register a converter with a name that is already
        in use triggers a RemovedInDjango60Warning, indicating that this functionality
        will be removed in a future version of Django. This test ensures that the
        deprecation warning is correctly raised when trying to override an existing
        converter, specifically the 'base64' converter in this case.

        The test case verifies the expected warning message and cleans up after itself
        by removing the converter from the registered converters list, regardless of the
        test outcome.
        """
        msg = (
            "Converter 'base64' is already registered. Support for overriding "
            "registered converters is deprecated and will be removed in Django 6.0."
        )
        try:
            with self.assertWarnsMessage(RemovedInDjango60Warning, msg):
                register_converter(Base64Converter, "base64")
                register_converter(Base64Converter, "base64")
        finally:
            REGISTERED_CONVERTERS.pop("base64", None)

    def test_invalid_view(self):
        """
        Tests that a TypeError is raised when an invalid view is provided to the path function.

        The function checks that a view must be a callable or a list/tuple (in the case of include()) to be considered valid.
        It verifies that a meaningful error message is raised when this condition is not met, informing the user of the expected view format.
        """
        msg = "view must be a callable or a list/tuple in the case of include()."
        with self.assertRaisesMessage(TypeError, msg):
            path("articles/", "invalid_view")

    def test_invalid_view_instance(self):
        class EmptyCBV(View):
            pass

        msg = "view must be a callable, pass EmptyCBV.as_view(), not EmptyCBV()."
        with self.assertRaisesMessage(TypeError, msg):
            path("foo", EmptyCBV())

    def test_whitespace_in_route(self):
        msg = "URL route %r cannot contain whitespace in angle brackets <…>"
        for whitespace in string.whitespace:
            with self.subTest(repr(whitespace)):
                route = "space/<int:num>/extra/<str:%stest>" % whitespace
                with self.assertRaisesMessage(ImproperlyConfigured, msg % route):
                    path(route, empty_view)
        # Whitespaces are valid in paths.
        p = path("space%s/<int:num>/" % string.whitespace, empty_view)
        match = p.resolve("space%s/1/" % string.whitespace)
        self.assertEqual(match.kwargs, {"num": 1})

    def test_path_trailing_newlines(self):
        tests = [
            "/articles/2003/\n",
            "/articles/2010/\n",
            "/en/foo/\n",
            "/included_urls/extra/\n",
            "/regex/1/\n",
            "/users/1/\n",
        ]
        for url in tests:
            with self.subTest(url=url), self.assertRaises(Resolver404):
                resolve(url)


@override_settings(ROOT_URLCONF="urlpatterns.converter_urls")
class ConverterTests(SimpleTestCase):
    def test_matching_urls(self):
        def no_converter(x):
            return x

        test_data = (
            ("int", {"0", "1", "01", 1234567890}, int),
            ("str", {"abcxyz"}, no_converter),
            ("path", {"allows.ANY*characters"}, no_converter),
            ("slug", {"abcxyz-ABCXYZ_01234567890"}, no_converter),
            ("uuid", {"39da9369-838e-4750-91a5-f7805cd82839"}, uuid.UUID),
        )
        for url_name, url_suffixes, converter in test_data:
            for url_suffix in url_suffixes:
                url = "/%s/%s/" % (url_name, url_suffix)
                with self.subTest(url=url):
                    match = resolve(url)
                    self.assertEqual(match.url_name, url_name)
                    self.assertEqual(match.kwargs, {url_name: converter(url_suffix)})
                    # reverse() works with string parameters.
                    string_kwargs = {url_name: url_suffix}
                    self.assertEqual(reverse(url_name, kwargs=string_kwargs), url)
                    # reverse() also works with native types (int, UUID, etc.).
                    if converter is not no_converter:
                        # The converted value might be different for int (a
                        # leading zero is lost in the conversion).
                        converted_value = match.kwargs[url_name]
                        converted_url = "/%s/%s/" % (url_name, converted_value)
                        self.assertEqual(
                            reverse(url_name, kwargs={url_name: converted_value}),
                            converted_url,
                        )

    def test_nonmatching_urls(self):
        test_data = (
            ("int", {"-1", "letters"}),
            ("str", {"", "/"}),
            ("path", {""}),
            ("slug", {"", "stars*notallowed"}),
            (
                "uuid",
                {
                    "",
                    "9da9369-838e-4750-91a5-f7805cd82839",
                    "39da9369-838-4750-91a5-f7805cd82839",
                    "39da9369-838e-475-91a5-f7805cd82839",
                    "39da9369-838e-4750-91a-f7805cd82839",
                    "39da9369-838e-4750-91a5-f7805cd8283",
                },
            ),
        )
        for url_name, url_suffixes in test_data:
            for url_suffix in url_suffixes:
                url = "/%s/%s/" % (url_name, url_suffix)
                with self.subTest(url=url), self.assertRaises(Resolver404):
                    resolve(url)


@override_settings(ROOT_URLCONF="urlpatterns.path_same_name_urls")
class SameNameTests(SimpleTestCase):
    def test_matching_urls_same_name(self):
        @DynamicConverter.register_to_url
        """
        Tests whether the URL reversal process correctly handles various types of URL patterns.

        This test case covers different scenarios, including:

        * Matching URLs with varying numbers of arguments
        * Using keyword arguments in URL reversal
        * Applying different converters to URL parameters (e.g., path, string, slug, integer, UUID)
        * Using regular expressions to handle specific character cases (e.g., uppercase, lowercase)
        * Registering custom converters to URLs (e.g., 'tiny_int') and ensuring they work as expected

        For each test scenario, the function verifies that the reversed URL matches the expected output. If any discrepancies are found, the test will fail, indicating a potential issue with the URL reversal process.
        """
        def requires_tiny_int(value):
            """

            Registers a dynamic converter to validate integer values.

            This function checks if the provided integer value is within a specific range,
            in this case, less than or equal to 5. If the value exceeds this threshold,
            it raises a ValueError. Otherwise, it returns the original value, allowing
            it to be used in URL conversion. This converter ensures that only tiny integers
            are accepted, providing a safeguard against unexpected or large values. 
            """
            if value > 5:
                raise ValueError
            return value

        tests = [
            (
                "number_of_args",
                [
                    ([], {}, "0/"),
                    ([1], {}, "1/1/"),
                ],
            ),
            (
                "kwargs_names",
                [
                    ([], {"a": 1}, "a/1/"),
                    ([], {"b": 1}, "b/1/"),
                ],
            ),
            (
                "converter",
                [
                    (["a/b"], {}, "path/a/b/"),
                    (["a b"], {}, "str/a%20b/"),
                    (["a-b"], {}, "slug/a-b/"),
                    (["2"], {}, "int/2/"),
                    (
                        ["39da9369-838e-4750-91a5-f7805cd82839"],
                        {},
                        "uuid/39da9369-838e-4750-91a5-f7805cd82839/",
                    ),
                ],
            ),
            (
                "regex",
                [
                    (["ABC"], {}, "uppercase/ABC/"),
                    (["abc"], {}, "lowercase/abc/"),
                ],
            ),
            (
                "converter_to_url",
                [
                    ([6], {}, "int/6/"),
                    ([1], {}, "tiny_int/1/"),
                ],
            ),
        ]
        for url_name, cases in tests:
            for args, kwargs, url_suffix in cases:
                expected_url = "/%s/%s" % (url_name, url_suffix)
                with self.subTest(url=expected_url):
                    self.assertEqual(
                        reverse(url_name, args=args, kwargs=kwargs),
                        expected_url,
                    )


class ParameterRestrictionTests(SimpleTestCase):
    def test_integer_parameter_name_causes_exception(self):
        """

        Tests that defining a URL route with an integer as a parameter name raises an ImproperlyConfigured exception.

        This check ensures that parameter names in URL routes adhere to Python's identifier naming conventions, 
        which disallow names starting with digits. The test confirms that using an integer as a parameter name 
        results in an error message indicating the invalid parameter name.

        """
        msg = (
            "URL route 'hello/<int:1>/' uses parameter name '1' which isn't "
            "a valid Python identifier."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            path(r"hello/<int:1>/", lambda r: None)

    def test_non_identifier_parameter_name_causes_exception(self):
        """
        Tests that using a non-standard Python identifier as a parameter name in a URL route raises an ImproperlyConfigured exception. 

        This ensures that the router correctly validates parameter names, enforcing that they adhere to Python's identifier naming conventions. 

        The test simulates a URL route with an invalid parameter name and verifies that the expected error message is raised, providing a clear indication of the issue.
        """
        msg = (
            "URL route 'b/<int:book.id>/' uses parameter name 'book.id' which "
            "isn't a valid Python identifier."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            path(r"b/<int:book.id>/", lambda r: None)

    def test_allows_non_ascii_but_valid_identifiers(self):
        # \u0394 is "GREEK CAPITAL LETTER DELTA", a valid identifier.
        """

        Tests that the router allows Unicode characters that are valid identifiers in URLs.

        This function verifies that the router correctly handles non-ASCII characters in 
        URL patterns, as long as they are valid identifier characters. It checks that the 
        router can match URLs containing these characters and extract the corresponding 
        keyword arguments.

        """
        p = path("hello/<str:\u0394>/", lambda r: None)
        match = p.resolve("hello/1/")
        self.assertEqual(match.kwargs, {"\u0394": "1"})


@override_settings(ROOT_URLCONF="urlpatterns.path_dynamic_urls")
class ConversionExceptionTests(SimpleTestCase):
    """How are errors in Converter.to_python() and to_url() handled?"""

    def test_resolve_value_error_means_no_match(self):
        @DynamicConverter.register_to_python
        """
        Tests that the resolve function correctly handles a ValueError raised by a DynamicConverter, 
        expecting it to result in a Resolver404 exception, indicating that no match was found.
        """
        def raises_value_error(value):
            raise ValueError()

        with self.assertRaises(Resolver404):
            resolve("/dynamic/abc/")

    def test_resolve_type_error_propagates(self):
        @DynamicConverter.register_to_python
        def raises_type_error(value):
            raise TypeError("This type error propagates.")

        with self.assertRaisesMessage(TypeError, "This type error propagates."):
            resolve("/dynamic/abc/")

    def test_reverse_value_error_means_no_match(self):
        @DynamicConverter.register_to_url
        def raises_value_error(value):
            raise ValueError

        with self.assertRaises(NoReverseMatch):
            reverse("dynamic", kwargs={"value": object()})

    def test_reverse_type_error_propagates(self):
        @DynamicConverter.register_to_url
        def raises_type_error(value):
            raise TypeError("This type error propagates.")

        with self.assertRaisesMessage(TypeError, "This type error propagates."):
            reverse("dynamic", kwargs={"value": object()})
