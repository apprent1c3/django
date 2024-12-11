"""
Unit tests for reverse URL lookups.
"""

import pickle
import sys
import threading

from admin_scripts.tests import AdminScriptTestCase

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured, ViewDoesNotExist
from django.http import HttpRequest, HttpResponsePermanentRedirect, HttpResponseRedirect
from django.shortcuts import redirect
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.test.utils import override_script_prefix
from django.urls import (
    NoReverseMatch,
    Resolver404,
    ResolverMatch,
    URLPattern,
    URLResolver,
    get_callable,
    get_resolver,
    get_urlconf,
    include,
    path,
    re_path,
    resolve,
    reverse,
    reverse_lazy,
)
from django.urls.resolvers import RegexPattern

from . import middleware, urlconf_outer, views
from .utils import URLObject
from .views import empty_view

resolve_test_data = (
    # These entries are in the format:
    #   (path, url_name, app_name, namespace, view_name, func, args, kwargs)
    # Simple case
    (
        "/normal/42/37/",
        "normal-view",
        "",
        "",
        "normal-view",
        views.empty_view,
        (),
        {"arg1": "42", "arg2": "37"},
    ),
    (
        "/view_class/42/37/",
        "view-class",
        "",
        "",
        "view-class",
        views.view_class_instance,
        (),
        {"arg1": "42", "arg2": "37"},
    ),
    (
        "/included/normal/42/37/",
        "inc-normal-view",
        "included_namespace_urls",
        "included_namespace_urls",
        "included_namespace_urls:inc-normal-view",
        views.empty_view,
        (),
        {"arg1": "42", "arg2": "37"},
    ),
    (
        "/included/view_class/42/37/",
        "inc-view-class",
        "included_namespace_urls",
        "included_namespace_urls",
        "included_namespace_urls:inc-view-class",
        views.view_class_instance,
        (),
        {"arg1": "42", "arg2": "37"},
    ),
    # Unnamed args are dropped if you have *any* kwargs in a pattern
    (
        "/mixed_args/42/37/",
        "mixed-args",
        "",
        "",
        "mixed-args",
        views.empty_view,
        (),
        {"extra": True, "arg2": "37"},
    ),
    (
        "/included/mixed_args/42/37/",
        "inc-mixed-args",
        "included_namespace_urls",
        "included_namespace_urls",
        "included_namespace_urls:inc-mixed-args",
        views.empty_view,
        (),
        {"arg2": "37"},
    ),
    (
        "/included/12/mixed_args/42/37/",
        "inc-mixed-args",
        "included_namespace_urls",
        "included_namespace_urls",
        "included_namespace_urls:inc-mixed-args",
        views.empty_view,
        (),
        {"arg2": "37"},
    ),
    # Unnamed views should have None as the url_name. Regression data for #21157.
    (
        "/unnamed/normal/42/37/",
        None,
        "",
        "",
        "urlpatterns_reverse.views.empty_view",
        views.empty_view,
        (),
        {"arg1": "42", "arg2": "37"},
    ),
    (
        "/unnamed/view_class/42/37/",
        None,
        "",
        "",
        "urlpatterns_reverse.views.ViewClass",
        views.view_class_instance,
        (),
        {"arg1": "42", "arg2": "37"},
    ),
    # If you have no kwargs, you get an args list.
    (
        "/no_kwargs/42/37/",
        "no-kwargs",
        "",
        "",
        "no-kwargs",
        views.empty_view,
        ("42", "37"),
        {},
    ),
    (
        "/included/no_kwargs/42/37/",
        "inc-no-kwargs",
        "included_namespace_urls",
        "included_namespace_urls",
        "included_namespace_urls:inc-no-kwargs",
        views.empty_view,
        ("42", "37"),
        {},
    ),
    (
        "/included/12/no_kwargs/42/37/",
        "inc-no-kwargs",
        "included_namespace_urls",
        "included_namespace_urls",
        "included_namespace_urls:inc-no-kwargs",
        views.empty_view,
        ("12", "42", "37"),
        {},
    ),
    # Namespaces
    (
        "/test1/inner/42/37/",
        "urlobject-view",
        "testapp",
        "test-ns1",
        "test-ns1:urlobject-view",
        views.empty_view,
        (),
        {"arg1": "42", "arg2": "37"},
    ),
    (
        "/included/test3/inner/42/37/",
        "urlobject-view",
        "included_namespace_urls:testapp",
        "included_namespace_urls:test-ns3",
        "included_namespace_urls:test-ns3:urlobject-view",
        views.empty_view,
        (),
        {"arg1": "42", "arg2": "37"},
    ),
    (
        "/ns-included1/normal/42/37/",
        "inc-normal-view",
        "included_namespace_urls",
        "inc-ns1",
        "inc-ns1:inc-normal-view",
        views.empty_view,
        (),
        {"arg1": "42", "arg2": "37"},
    ),
    (
        "/included/test3/inner/42/37/",
        "urlobject-view",
        "included_namespace_urls:testapp",
        "included_namespace_urls:test-ns3",
        "included_namespace_urls:test-ns3:urlobject-view",
        views.empty_view,
        (),
        {"arg1": "42", "arg2": "37"},
    ),
    (
        "/default/inner/42/37/",
        "urlobject-view",
        "testapp",
        "testapp",
        "testapp:urlobject-view",
        views.empty_view,
        (),
        {"arg1": "42", "arg2": "37"},
    ),
    (
        "/other2/inner/42/37/",
        "urlobject-view",
        "nodefault",
        "other-ns2",
        "other-ns2:urlobject-view",
        views.empty_view,
        (),
        {"arg1": "42", "arg2": "37"},
    ),
    (
        "/other1/inner/42/37/",
        "urlobject-view",
        "nodefault",
        "other-ns1",
        "other-ns1:urlobject-view",
        views.empty_view,
        (),
        {"arg1": "42", "arg2": "37"},
    ),
    # Nested namespaces
    (
        "/ns-included1/test3/inner/42/37/",
        "urlobject-view",
        "included_namespace_urls:testapp",
        "inc-ns1:test-ns3",
        "inc-ns1:test-ns3:urlobject-view",
        views.empty_view,
        (),
        {"arg1": "42", "arg2": "37"},
    ),
    (
        "/ns-included1/ns-included4/ns-included2/test3/inner/42/37/",
        "urlobject-view",
        "included_namespace_urls:namespace_urls:included_namespace_urls:testapp",
        "inc-ns1:inc-ns4:inc-ns2:test-ns3",
        "inc-ns1:inc-ns4:inc-ns2:test-ns3:urlobject-view",
        views.empty_view,
        (),
        {"arg1": "42", "arg2": "37"},
    ),
    (
        "/app-included/test3/inner/42/37/",
        "urlobject-view",
        "included_namespace_urls:testapp",
        "inc-app:test-ns3",
        "inc-app:test-ns3:urlobject-view",
        views.empty_view,
        (),
        {"arg1": "42", "arg2": "37"},
    ),
    (
        "/app-included/ns-included4/ns-included2/test3/inner/42/37/",
        "urlobject-view",
        "included_namespace_urls:namespace_urls:included_namespace_urls:testapp",
        "inc-app:inc-ns4:inc-ns2:test-ns3",
        "inc-app:inc-ns4:inc-ns2:test-ns3:urlobject-view",
        views.empty_view,
        (),
        {"arg1": "42", "arg2": "37"},
    ),
    # Namespaces capturing variables
    (
        "/inc70/",
        "inner-nothing",
        "included_urls",
        "inc-ns5",
        "inc-ns5:inner-nothing",
        views.empty_view,
        (),
        {"outer": "70"},
    ),
    (
        "/inc78/extra/foobar/",
        "inner-extra",
        "included_urls",
        "inc-ns5",
        "inc-ns5:inner-extra",
        views.empty_view,
        (),
        {"outer": "78", "extra": "foobar"},
    ),
)

test_data = (
    ("places", "/places/3/", [3], {}),
    ("places", "/places/3/", ["3"], {}),
    ("places", NoReverseMatch, ["a"], {}),
    ("places", NoReverseMatch, [], {}),
    ("places?", "/place/", [], {}),
    ("places+", "/places/", [], {}),
    ("places*", "/place/", [], {}),
    ("places2?", "/", [], {}),
    ("places2+", "/places/", [], {}),
    ("places2*", "/", [], {}),
    ("places3", "/places/4/", [4], {}),
    ("places3", "/places/harlem/", ["harlem"], {}),
    ("places3", NoReverseMatch, ["harlem64"], {}),
    ("places4", "/places/3/", [], {"id": 3}),
    ("people", NoReverseMatch, [], {}),
    ("people", "/people/adrian/", ["adrian"], {}),
    ("people", "/people/adrian/", [], {"name": "adrian"}),
    ("people", NoReverseMatch, ["name with spaces"], {}),
    ("people", NoReverseMatch, [], {"name": "name with spaces"}),
    ("people2", "/people/name/", [], {}),
    ("people2a", "/people/name/fred/", ["fred"], {}),
    ("people_backref", "/people/nate-nate/", ["nate"], {}),
    ("people_backref", "/people/nate-nate/", [], {"name": "nate"}),
    ("optional", "/optional/fred/", [], {"name": "fred"}),
    ("optional", "/optional/fred/", ["fred"], {}),
    ("named_optional", "/optional/1/", [1], {}),
    ("named_optional", "/optional/1/", [], {"arg1": 1}),
    ("named_optional", "/optional/1/2/", [1, 2], {}),
    ("named_optional", "/optional/1/2/", [], {"arg1": 1, "arg2": 2}),
    ("named_optional_terminated", "/optional/1/", [1], {}),
    ("named_optional_terminated", "/optional/1/", [], {"arg1": 1}),
    ("named_optional_terminated", "/optional/1/2/", [1, 2], {}),
    ("named_optional_terminated", "/optional/1/2/", [], {"arg1": 1, "arg2": 2}),
    ("hardcoded", "/hardcoded/", [], {}),
    ("hardcoded2", "/hardcoded/doc.pdf", [], {}),
    ("people3", "/people/il/adrian/", [], {"state": "il", "name": "adrian"}),
    ("people3", NoReverseMatch, [], {"state": "il"}),
    ("people3", NoReverseMatch, [], {"name": "adrian"}),
    ("people4", NoReverseMatch, [], {"state": "il", "name": "adrian"}),
    ("people6", "/people/il/test/adrian/", ["il/test", "adrian"], {}),
    ("people6", "/people//adrian/", ["adrian"], {}),
    ("range", "/character_set/a/", [], {}),
    ("range2", "/character_set/x/", [], {}),
    ("price", "/price/$10/", ["10"], {}),
    ("price2", "/price/$10/", ["10"], {}),
    ("price3", "/price/$10/", ["10"], {}),
    (
        "product",
        "/product/chocolate+($2.00)/",
        [],
        {"price": "2.00", "product": "chocolate"},
    ),
    ("headlines", "/headlines/2007.5.21/", [], {"year": 2007, "month": 5, "day": 21}),
    (
        "windows",
        r"/windows_path/C:%5CDocuments%20and%20Settings%5Cspam/",
        [],
        {"drive_name": "C", "path": r"Documents and Settings\spam"},
    ),
    ("special", r"/special_chars/~@+%5C$*%7C/", [r"~@+\$*|"], {}),
    ("special", r"/special_chars/some%20resource/", [r"some resource"], {}),
    ("special", r"/special_chars/10%25%20complete/", [r"10% complete"], {}),
    ("special", r"/special_chars/some%20resource/", [], {"chars": r"some resource"}),
    ("special", r"/special_chars/10%25%20complete/", [], {"chars": r"10% complete"}),
    ("special", NoReverseMatch, [""], {}),
    ("mixed", "/john/0/", [], {"name": "john"}),
    ("repeats", "/repeats/a/", [], {}),
    ("repeats2", "/repeats/aa/", [], {}),
    ("repeats3", "/repeats/aa/", [], {}),
    ("test", "/test/1", [], {}),
    ("inner-nothing", "/outer/42/", [], {"outer": "42"}),
    ("inner-nothing", "/outer/42/", ["42"], {}),
    ("inner-nothing", NoReverseMatch, ["foo"], {}),
    ("inner-extra", "/outer/42/extra/inner/", [], {"extra": "inner", "outer": "42"}),
    ("inner-extra", "/outer/42/extra/inner/", ["42", "inner"], {}),
    ("inner-extra", NoReverseMatch, ["fred", "inner"], {}),
    ("inner-no-kwargs", "/outer-no-kwargs/42/inner-no-kwargs/1/", ["42", "1"], {}),
    ("disjunction", NoReverseMatch, ["foo"], {}),
    ("inner-disjunction", NoReverseMatch, ["10", "11"], {}),
    ("extra-places", "/e-places/10/", ["10"], {}),
    ("extra-people", "/e-people/fred/", ["fred"], {}),
    ("extra-people", "/e-people/fred/", [], {"name": "fred"}),
    ("part", "/part/one/", [], {"value": "one"}),
    ("part", "/prefix/xx/part/one/", [], {"value": "one", "prefix": "xx"}),
    ("part2", "/part2/one/", [], {"value": "one"}),
    ("part2", "/part2/", [], {}),
    ("part2", "/prefix/xx/part2/one/", [], {"value": "one", "prefix": "xx"}),
    ("part2", "/prefix/xx/part2/", [], {"prefix": "xx"}),
    # Tests for nested groups. Nested capturing groups will only work if you
    # *only* supply the correct outer group.
    ("nested-noncapture", "/nested/noncapture/opt", [], {"p": "opt"}),
    ("nested-capture", "/nested/capture/opt/", ["opt/"], {}),
    ("nested-capture", NoReverseMatch, [], {"p": "opt"}),
    ("nested-mixedcapture", "/nested/capture/mixed/opt", ["opt"], {}),
    ("nested-mixedcapture", NoReverseMatch, [], {"p": "opt"}),
    ("nested-namedcapture", "/nested/capture/named/opt/", [], {"outer": "opt/"}),
    ("nested-namedcapture", NoReverseMatch, [], {"outer": "opt/", "inner": "opt"}),
    ("nested-namedcapture", NoReverseMatch, [], {"inner": "opt"}),
    ("non_path_include", "/includes/non_path_include/", [], {}),
    # Tests for #13154
    ("defaults", "/defaults_view1/3/", [], {"arg1": 3, "arg2": 1}),
    ("defaults", "/defaults_view2/3/", [], {"arg1": 3, "arg2": 2}),
    ("defaults", NoReverseMatch, [], {"arg1": 3, "arg2": 3}),
    ("defaults", NoReverseMatch, [], {"arg2": 1}),
    # Security tests
    ("security", "/%2Fexample.com/security/", ["/example.com"], {}),
)


@override_settings(ROOT_URLCONF="urlpatterns_reverse.no_urls")
class NoURLPatternsTests(SimpleTestCase):
    def test_no_urls_exception(self):
        """
        URLResolver should raise an exception when no urlpatterns exist.
        """
        resolver = URLResolver(RegexPattern(r"^$"), settings.ROOT_URLCONF)

        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "The included URLconf 'urlpatterns_reverse.no_urls' does not "
            "appear to have any patterns in it. If you see the 'urlpatterns' "
            "variable with valid patterns in the file then the issue is "
            "probably caused by a circular import.",
        ):
            getattr(resolver, "url_patterns")


@override_settings(ROOT_URLCONF="urlpatterns_reverse.urls")
class URLPatternReverse(SimpleTestCase):
    def test_urlpattern_reverse(self):
        """

        Tests the reversing of URL patterns.

        This function iterates over a set of test data, where each test case contains a URL pattern name, 
        expected reversed URL, positional arguments, and keyword arguments. 

        It attempts to reverse the URL pattern using the provided arguments and checks if the result 
        matches the expected output. If reversing the URL pattern fails (i.e., it raises a NoReverseMatch 
        exception), it verifies that the expected result is indeed a NoReverseMatch exception.

        Each test case is run as a sub-test to provide more detailed information in case of failures.

        """
        for name, expected, args, kwargs in test_data:
            with self.subTest(name=name, args=args, kwargs=kwargs):
                try:
                    got = reverse(name, args=args, kwargs=kwargs)
                except NoReverseMatch:
                    self.assertEqual(NoReverseMatch, expected)
                else:
                    self.assertEqual(got, expected)

    def test_reverse_none(self):
        # Reversing None should raise an error, not return the last un-named view.
        """
        Tests that reversing a None URL pattern raises a NoReverseMatch exception.

        This test case verifies that the reverse function correctly handles None as input and raises an exception as expected, indicating that the function cannot reverse a URL pattern that does not exist.

        Raises:
            NoReverseMatch: When attempting to reverse a None URL pattern.
        """
        with self.assertRaises(NoReverseMatch):
            reverse(None)

    def test_mixing_args_and_kwargs(self):
        msg = "Don't mix *args and **kwargs in call to reverse()!"
        with self.assertRaisesMessage(ValueError, msg):
            reverse("name", args=["a"], kwargs={"b": "c"})

    @override_script_prefix("/{{invalid}}/")
    def test_prefix_braces(self):
        self.assertEqual(
            "/%7B%7Binvalid%7D%7D/includes/non_path_include/",
            reverse("non_path_include"),
        )

    def test_prefix_parenthesis(self):
        # Parentheses are allowed and should not cause errors or be escaped
        """
        Tests the handling of prefix parentheses in script prefixes when reversing URLs, 
        ensuring that parentheses in the prefix are properly included in the resulting URL.
        """
        with override_script_prefix("/bogus)/"):
            self.assertEqual(
                "/bogus)/includes/non_path_include/", reverse("non_path_include")
            )
        with override_script_prefix("/(bogus)/"):
            self.assertEqual(
                "/(bogus)/includes/non_path_include/", reverse("non_path_include")
            )

    @override_script_prefix("/bump%20map/")
    def test_prefix_format_char(self):
        self.assertEqual(
            "/bump%2520map/includes/non_path_include/", reverse("non_path_include")
        )

    @override_script_prefix("/%7Eme/")
    def test_non_urlsafe_prefix_with_args(self):
        # Regression for #20022, adjusted for #24013 because ~ is an unreserved
        # character. Tests whether % is escaped.
        self.assertEqual("/%257Eme/places/1/", reverse("places", args=[1]))

    def test_patterns_reported(self):
        # Regression for #17076
        """
        Tests that an exception with a detailed message is raised when attempting to reverse a URL pattern with missing arguments.

        Verifies that the reverse operation fails with a NoReverseMatch exception when the provided arguments do not match the expected pattern.

        The exception message is expected to include information about the patterns that were attempted during the reversal process, which can aid in debugging and troubleshooting URL reversal issues.

        This test ensures that the URL reversal mechanism provides informative error messages when it encounters invalid or incomplete arguments, helping developers identify and fix URL configuration issues more efficiently.
        """
        with self.assertRaisesMessage(
            NoReverseMatch, r"1 pattern(s) tried: ['people/(?P<name>\\w+)/$']"
        ):
            # this url exists, but requires an argument
            reverse("people", args=[])

    @override_script_prefix("/script:name/")
    def test_script_name_escaping(self):
        self.assertEqual(
            reverse("optional", args=["foo:bar"]), "/script:name/optional/foo:bar/"
        )

    def test_view_not_found_message(self):
        """
        Tests that a NoReverseMatch exception is raised when attempting to reverse a non-existent view.

        This test case checks if the reverse function correctly handles the case where the view name is not recognized.
        It verifies that the expected error message is raised, containing the name of the non-existent view and a description of the error.
        The goal of this test is to ensure that the view reversal mechanism behaves as expected when encountering invalid view names.
        """
        msg = (
            "Reverse for 'nonexistent-view' not found. 'nonexistent-view' "
            "is not a valid view function or pattern name."
        )
        with self.assertRaisesMessage(NoReverseMatch, msg):
            reverse("nonexistent-view")

    def test_no_args_message(self):
        msg = "Reverse for 'places' with no arguments not found. 1 pattern(s) tried:"
        with self.assertRaisesMessage(NoReverseMatch, msg):
            reverse("places")

    def test_illegal_args_message(self):
        """
        Tests that attempting to reverse the 'places' URL with the arguments (1, 2) raises a NoReverseMatch exception with the expected error message.

        This test case ensures that the reverse URL resolver behaves correctly when given invalid or non-existent URL patterns, providing a descriptive error message to help with debugging.

        Parameters
        ----------
        None

        Returns
        -------
        None

        Raises
        ------
        NoReverseMatch
            If the URL pattern 'places' with arguments (1, 2) is not found.

        Note
        ----
        This test case relies on the definition of the 'places' URL pattern and its associated view function. The test will fail if the URL pattern is not defined or if it does not match the given arguments.
        """
        msg = (
            "Reverse for 'places' with arguments '(1, 2)' not found. 1 pattern(s) "
            "tried:"
        )
        with self.assertRaisesMessage(NoReverseMatch, msg):
            reverse("places", args=(1, 2))

    def test_illegal_kwargs_message(self):
        msg = (
            "Reverse for 'places' with keyword arguments '{'arg1': 2}' not found. 1 "
            "pattern(s) tried:"
        )
        with self.assertRaisesMessage(NoReverseMatch, msg):
            reverse("places", kwargs={"arg1": 2})


class ResolverTests(SimpleTestCase):
    def test_resolver_repr(self):
        """
        Test repr of URLResolver, especially when urlconf_name is a list
        (#17892).
        """
        # Pick a resolver from a namespaced URLconf
        resolver = get_resolver("urlpatterns_reverse.namespace_urls")
        sub_resolver = resolver.namespace_dict["test-ns1"][1]
        self.assertIn("<URLPattern list>", repr(sub_resolver))

    def test_reverse_lazy_object_coercion_by_resolve(self):
        """
        Verifies lazy object returned by reverse_lazy is coerced to
        text by resolve(). Previous to #21043, this would raise a TypeError.
        """
        urls = "urlpatterns_reverse.named_urls"
        proxy_url = reverse_lazy("named-url1", urlconf=urls)
        resolver = get_resolver(urls)
        resolver.resolve(proxy_url)

    def test_resolver_reverse(self):
        """

        Tests the reverse functionality of the URL resolver.

        The test verifies that the resolver correctly generates URLs for named URLs
        with varying arguments and keyword arguments. It covers cases with and without
        positional arguments and keyword arguments.

        The test cases include:
        - Reversing named URLs with no arguments
        - Reversing named URLs with positional arguments
        - Reversing named URLs with keyword arguments

        The test ensures that the generated URLs match the expected output for each case.

        """
        resolver = get_resolver("urlpatterns_reverse.named_urls")
        test_urls = [
            # (name, args, kwargs, expected)
            ("named-url1", (), {}, ""),
            ("named-url2", ("arg",), {}, "extra/arg/"),
            ("named-url2", (), {"extra": "arg"}, "extra/arg/"),
        ]
        for name, args, kwargs, expected in test_urls:
            with self.subTest(name=name, args=args, kwargs=kwargs):
                self.assertEqual(resolver.reverse(name, *args, **kwargs), expected)

    def test_resolver_reverse_conflict(self):
        """
        URL pattern name arguments don't need to be unique. The last registered
        pattern takes precedence for conflicting names.
        """
        resolver = get_resolver("urlpatterns_reverse.named_urls_conflict")
        test_urls = [
            # (name, args, kwargs, expected)
            # Without arguments, the last URL in urlpatterns has precedence.
            ("name-conflict", (), {}, "conflict/"),
            # With an arg, the last URL in urlpatterns has precedence.
            ("name-conflict", ("arg",), {}, "conflict-last/arg/"),
            # With a kwarg, other URL patterns can be reversed.
            ("name-conflict", (), {"first": "arg"}, "conflict-first/arg/"),
            ("name-conflict", (), {"middle": "arg"}, "conflict-middle/arg/"),
            ("name-conflict", (), {"last": "arg"}, "conflict-last/arg/"),
            # The number and order of the arguments don't interfere with reversing.
            ("name-conflict", ("arg", "arg"), {}, "conflict/arg/arg/"),
        ]
        for name, args, kwargs, expected in test_urls:
            with self.subTest(name=name, args=args, kwargs=kwargs):
                self.assertEqual(resolver.reverse(name, *args, **kwargs), expected)

    def test_non_regex(self):
        """
        A Resolver404 is raised if resolving doesn't meet the basic
        requirements of a path to match - i.e., at the very least, it matches
        the root pattern '^/'. Never return None from resolve() to prevent a
        TypeError from occurring later (#10834).
        """
        test_urls = ["", "a", "\\", "."]
        for path_ in test_urls:
            with self.subTest(path=path_):
                with self.assertRaises(Resolver404):
                    resolve(path_)

    def test_404_tried_urls_have_names(self):
        """
        The list of URLs that come back from a Resolver404 exception contains
        a list in the right format for printing out in the DEBUG 404 page with
        both the patterns and URL names, if available.
        """
        urls = "urlpatterns_reverse.named_urls"
        # this list matches the expected URL types and names returned when
        # you try to resolve a nonexistent URL in the first level of included
        # URLs in named_urls.py (e.g., '/included/nonexistent-url')
        url_types_names = [
            [{"type": URLPattern, "name": "named-url1"}],
            [{"type": URLPattern, "name": "named-url2"}],
            [{"type": URLPattern, "name": None}],
            [{"type": URLResolver}, {"type": URLPattern, "name": "named-url3"}],
            [{"type": URLResolver}, {"type": URLPattern, "name": "named-url4"}],
            [{"type": URLResolver}, {"type": URLPattern, "name": None}],
            [{"type": URLResolver}, {"type": URLResolver}],
        ]
        with self.assertRaisesMessage(Resolver404, "tried") as cm:
            resolve("/included/nonexistent-url", urlconf=urls)
        e = cm.exception
        # make sure we at least matched the root ('/') url resolver:
        self.assertIn("tried", e.args[0])
        self.assertEqual(
            len(e.args[0]["tried"]),
            len(url_types_names),
            "Wrong number of tried URLs returned.  Expected %s, got %s."
            % (len(url_types_names), len(e.args[0]["tried"])),
        )
        for tried, expected in zip(e.args[0]["tried"], url_types_names):
            for t, e in zip(tried, expected):
                with self.subTest(t):
                    self.assertIsInstance(
                        t, e["type"]
                    ), "%s is not an instance of %s" % (t, e["type"])
                    if "name" in e:
                        if not e["name"]:
                            self.assertIsNone(
                                t.name, "Expected no URL name but found %s." % t.name
                            )
                        else:
                            self.assertEqual(
                                t.name,
                                e["name"],
                                'Wrong URL name.  Expected "%s", got "%s".'
                                % (e["name"], t.name),
                            )

    def test_namespaced_view_detail(self):
        resolver = get_resolver("urlpatterns_reverse.nested_urls")
        self.assertTrue(resolver._is_callback("urlpatterns_reverse.nested_urls.view1"))
        self.assertTrue(resolver._is_callback("urlpatterns_reverse.nested_urls.view2"))
        self.assertTrue(resolver._is_callback("urlpatterns_reverse.nested_urls.View3"))
        self.assertFalse(resolver._is_callback("urlpatterns_reverse.nested_urls.blub"))

    def test_view_detail_as_method(self):
        # Views which have a class name as part of their path.
        resolver = get_resolver("urlpatterns_reverse.method_view_urls")
        self.assertTrue(
            resolver._is_callback(
                "urlpatterns_reverse.method_view_urls.ViewContainer.method_view"
            )
        )
        self.assertTrue(
            resolver._is_callback(
                "urlpatterns_reverse.method_view_urls.ViewContainer.classmethod_view"
            )
        )

    def test_populate_concurrency(self):
        """
        URLResolver._populate() can be called concurrently, but not more
        than once per thread (#26888).
        """
        resolver = URLResolver(RegexPattern(r"^/"), "urlpatterns_reverse.urls")
        resolver._local.populating = True
        thread = threading.Thread(target=resolver._populate)
        thread.start()
        thread.join()
        self.assertNotEqual(resolver._reverse_dict, {})


@override_settings(ROOT_URLCONF="urlpatterns_reverse.reverse_lazy_urls")
class ReverseLazyTest(TestCase):
    def test_redirect_with_lazy_reverse(self):
        response = self.client.get("/redirect/")
        self.assertRedirects(response, "/redirected_to/", status_code=302)

    def test_user_permission_with_lazy_reverse(self):
        alfred = User.objects.create_user(
            "alfred", "alfred@example.com", password="testpw"
        )
        response = self.client.get("/login_required_view/")
        self.assertRedirects(
            response, "/login/?next=/login_required_view/", status_code=302
        )
        self.client.force_login(alfred)
        response = self.client.get("/login_required_view/")
        self.assertEqual(response.status_code, 200)

    def test_inserting_reverse_lazy_into_string(self):
        self.assertEqual(
            "Some URL: %s" % reverse_lazy("some-login-page"), "Some URL: /login/"
        )

    def test_build_absolute_uri(self):
        """

        Tests the construction of an absolute URI for a given URL pattern.

        Verifies that the :meth:`build_absolute_uri` method correctly generates a full URL,
        including the scheme and domain, when given a reversed URL pattern.

        The test ensures that the resulting absolute URI matches the expected output.

        """
        factory = RequestFactory()
        request = factory.get("/")
        self.assertEqual(
            request.build_absolute_uri(reverse_lazy("some-login-page")),
            "http://testserver/login/",
        )


class ReverseLazySettingsTest(AdminScriptTestCase):
    """
    reverse_lazy can be used in settings without causing a circular
    import error.
    """

    def setUp(self):
        """
        Sets up the test environment bycalling the superclass's setup method and writing settings to a 'settings.py' file.

        The settings include importing `reverse_lazy` from `django.urls` and setting `LOGIN_URL` to the reverse lazy 'login' URL, providing a default login URL for testing purposes.
        """
        super().setUp()
        self.write_settings(
            "settings.py",
            extra=(
                "from django.urls import reverse_lazy\n"
                "LOGIN_URL = reverse_lazy('login')"
            ),
        )

    def test_lazy_in_settings(self):
        """
        Tests that lazy settings are properly handled by the manage command.

        Verifies that running the check management command does not produce any errors, 
        indicating that lazy settings are correctly resolved and do not cause any issues.

        """
        out, err = self.run_manage(["check"])
        self.assertNoOutput(err)


@override_settings(ROOT_URLCONF="urlpatterns_reverse.urls")
class ReverseShortcutTests(SimpleTestCase):
    def test_redirect_to_object(self):
        # We don't really need a model; just something with a get_absolute_url
        """
        Tests the redirect function by attempting to redirect to an object with a get_absolute_url method.
        The test case covers both permanent and non-permanent redirects.
        The object's get_absolute_url method is called to determine the redirect URL.
        The function verifies that the correct type of HTTP response is generated (HttpResponseRedirect for non-permanent and HttpResponsePermanentRedirect for permanent redirects) and that the redirect URL matches the object's absolute URL.
        """
        class FakeObj:
            def get_absolute_url(self):
                return "/hi-there/"

        res = redirect(FakeObj())
        self.assertIsInstance(res, HttpResponseRedirect)
        self.assertEqual(res.url, "/hi-there/")

        res = redirect(FakeObj(), permanent=True)
        self.assertIsInstance(res, HttpResponsePermanentRedirect)
        self.assertEqual(res.url, "/hi-there/")

    def test_redirect_to_view_name(self):
        """

        Test cases for the redirect function to ensure it correctly generates URLs for given view names.

        This function tests the redirect function with different view names and arguments, checking that the resulting URLs match the expected patterns. It also verifies that an error is raised when attempting to redirect to a non-existent view.

        The test cases cover redirects with hardcoded view names, view names with positional arguments, and view names with keyword arguments. The expected URLs are compared with the actual URLs generated by the redirect function to ensure correctness.

        """
        res = redirect("hardcoded2")
        self.assertEqual(res.url, "/hardcoded/doc.pdf")
        res = redirect("places", 1)
        self.assertEqual(res.url, "/places/1/")
        res = redirect("headlines", year="2008", month="02", day="17")
        self.assertEqual(res.url, "/headlines/2008.02.17/")
        with self.assertRaises(NoReverseMatch):
            redirect("not-a-view")

    def test_redirect_to_url(self):
        """

        Tests the functionality of redirecting to a specified URL.

        The function verifies that the redirect function correctly handles various URL formats, 
        including absolute paths, external URLs, and URLs containing special characters. It checks 
        that the URLs are properly encoded and stored in the response object.

        The test cases cover different scenarios, such as redirecting to a local path, an external 
        URL, and a URL with non-ASCII characters, ensuring that the redirect function behaves as 
        expected in each case.

        """
        res = redirect("/foo/")
        self.assertEqual(res.url, "/foo/")
        res = redirect("http://example.com/")
        self.assertEqual(res.url, "http://example.com/")
        # Assert that we can redirect using UTF-8 strings
        res = redirect("/æøå/abc/")
        self.assertEqual(res.url, "/%C3%A6%C3%B8%C3%A5/abc/")
        # Assert that no imports are attempted when dealing with a relative path
        # (previously, the below would resolve in a UnicodeEncodeError from __import__ )
        res = redirect("/æøå.abc/")
        self.assertEqual(res.url, "/%C3%A6%C3%B8%C3%A5.abc/")
        res = redirect("os.path")
        self.assertEqual(res.url, "os.path")

    def test_no_illegal_imports(self):
        # modules that are not listed in urlpatterns should not be importable
        redirect("urlpatterns_reverse.nonimported_module.view")
        self.assertNotIn("urlpatterns_reverse.nonimported_module", sys.modules)

    def test_reverse_by_path_nested(self):
        # Views added to urlpatterns using include() should be reversible.
        """
        Tests the reversal of a URL path for a nested view.

        This test case checks if the reverse function correctly generates the URL path 
        for a view that is nested within another path. The expected output is compared 
        to the actual reversed URL to ensure they match.

        The view in question is a nested view, which is expected to have a URL path 
        that is nested under another path. The test verifies that the reverse 
        function can correctly handle this nesting and produce the correct URL.

        """
        from .views import nested_view

        self.assertEqual(reverse(nested_view), "/includes/nested_path/")

    def test_redirect_view_object(self):
        from .views import absolute_kwargs_view

        res = redirect(absolute_kwargs_view)
        self.assertEqual(res.url, "/absolute_arg_view/")
        with self.assertRaises(NoReverseMatch):
            redirect(absolute_kwargs_view, wrong_argument=None)


@override_settings(ROOT_URLCONF="urlpatterns_reverse.namespace_urls")
class NamespaceTests(SimpleTestCase):
    def test_ambiguous_object(self):
        """
        Names deployed via dynamic URL objects that require namespaces can't
        be resolved.
        """
        test_urls = [
            ("urlobject-view", [], {}),
            ("urlobject-view", [37, 42], {}),
            ("urlobject-view", [], {"arg1": 42, "arg2": 37}),
        ]
        for name, args, kwargs in test_urls:
            with self.subTest(name=name, args=args, kwargs=kwargs):
                with self.assertRaises(NoReverseMatch):
                    reverse(name, args=args, kwargs=kwargs)

    def test_ambiguous_urlpattern(self):
        """
        Names deployed via dynamic URL objects that require namespaces can't
        be resolved.
        """
        test_urls = [
            ("inner-nothing", [], {}),
            ("inner-nothing", [37, 42], {}),
            ("inner-nothing", [], {"arg1": 42, "arg2": 37}),
        ]
        for name, args, kwargs in test_urls:
            with self.subTest(name=name, args=args, kwargs=kwargs):
                with self.assertRaises(NoReverseMatch):
                    reverse(name, args=args, kwargs=kwargs)

    def test_non_existent_namespace(self):
        """Nonexistent namespaces raise errors."""
        test_urls = [
            "blahblah:urlobject-view",
            "test-ns1:blahblah:urlobject-view",
        ]
        for name in test_urls:
            with self.subTest(name=name):
                with self.assertRaises(NoReverseMatch):
                    reverse(name)

    def test_normal_name(self):
        """Normal lookups work as expected."""
        test_urls = [
            ("normal-view", [], {}, "/normal/"),
            ("normal-view", [37, 42], {}, "/normal/37/42/"),
            ("normal-view", [], {"arg1": 42, "arg2": 37}, "/normal/42/37/"),
            ("special-view", [], {}, "/+%5C$*/"),
        ]
        for name, args, kwargs, expected in test_urls:
            with self.subTest(name=name, args=args, kwargs=kwargs):
                self.assertEqual(reverse(name, args=args, kwargs=kwargs), expected)

    def test_simple_included_name(self):
        """Normal lookups work on names included from other patterns."""
        test_urls = [
            ("included_namespace_urls:inc-normal-view", [], {}, "/included/normal/"),
            (
                "included_namespace_urls:inc-normal-view",
                [37, 42],
                {},
                "/included/normal/37/42/",
            ),
            (
                "included_namespace_urls:inc-normal-view",
                [],
                {"arg1": 42, "arg2": 37},
                "/included/normal/42/37/",
            ),
            ("included_namespace_urls:inc-special-view", [], {}, "/included/+%5C$*/"),
        ]
        for name, args, kwargs, expected in test_urls:
            with self.subTest(name=name, args=args, kwargs=kwargs):
                self.assertEqual(reverse(name, args=args, kwargs=kwargs), expected)

    def test_namespace_object(self):
        """Dynamic URL objects can be found using a namespace."""
        test_urls = [
            ("test-ns1:urlobject-view", [], {}, "/test1/inner/"),
            ("test-ns1:urlobject-view", [37, 42], {}, "/test1/inner/37/42/"),
            (
                "test-ns1:urlobject-view",
                [],
                {"arg1": 42, "arg2": 37},
                "/test1/inner/42/37/",
            ),
            ("test-ns1:urlobject-special-view", [], {}, "/test1/inner/+%5C$*/"),
        ]
        for name, args, kwargs, expected in test_urls:
            with self.subTest(name=name, args=args, kwargs=kwargs):
                self.assertEqual(reverse(name, args=args, kwargs=kwargs), expected)

    def test_app_object(self):
        """
        Dynamic URL objects can return a (pattern, app_name) 2-tuple, and
        include() can set the namespace.
        """
        test_urls = [
            ("new-ns1:urlobject-view", [], {}, "/newapp1/inner/"),
            ("new-ns1:urlobject-view", [37, 42], {}, "/newapp1/inner/37/42/"),
            (
                "new-ns1:urlobject-view",
                [],
                {"arg1": 42, "arg2": 37},
                "/newapp1/inner/42/37/",
            ),
            ("new-ns1:urlobject-special-view", [], {}, "/newapp1/inner/+%5C$*/"),
        ]
        for name, args, kwargs, expected in test_urls:
            with self.subTest(name=name, args=args, kwargs=kwargs):
                self.assertEqual(reverse(name, args=args, kwargs=kwargs), expected)

    def test_app_object_default_namespace(self):
        """
        Namespace defaults to app_name when including a (pattern, app_name)
        2-tuple.
        """
        test_urls = [
            ("newapp:urlobject-view", [], {}, "/new-default/inner/"),
            ("newapp:urlobject-view", [37, 42], {}, "/new-default/inner/37/42/"),
            (
                "newapp:urlobject-view",
                [],
                {"arg1": 42, "arg2": 37},
                "/new-default/inner/42/37/",
            ),
            ("newapp:urlobject-special-view", [], {}, "/new-default/inner/+%5C$*/"),
        ]
        for name, args, kwargs, expected in test_urls:
            with self.subTest(name=name, args=args, kwargs=kwargs):
                self.assertEqual(reverse(name, args=args, kwargs=kwargs), expected)

    def test_embedded_namespace_object(self):
        """Namespaces can be installed anywhere in the URL pattern tree."""
        test_urls = [
            (
                "included_namespace_urls:test-ns3:urlobject-view",
                [],
                {},
                "/included/test3/inner/",
            ),
            (
                "included_namespace_urls:test-ns3:urlobject-view",
                [37, 42],
                {},
                "/included/test3/inner/37/42/",
            ),
            (
                "included_namespace_urls:test-ns3:urlobject-view",
                [],
                {"arg1": 42, "arg2": 37},
                "/included/test3/inner/42/37/",
            ),
            (
                "included_namespace_urls:test-ns3:urlobject-special-view",
                [],
                {},
                "/included/test3/inner/+%5C$*/",
            ),
        ]
        for name, args, kwargs, expected in test_urls:
            with self.subTest(name=name, args=args, kwargs=kwargs):
                self.assertEqual(reverse(name, args=args, kwargs=kwargs), expected)

    def test_namespace_pattern(self):
        """Namespaces can be applied to include()'d urlpatterns."""
        test_urls = [
            ("inc-ns1:inc-normal-view", [], {}, "/ns-included1/normal/"),
            ("inc-ns1:inc-normal-view", [37, 42], {}, "/ns-included1/normal/37/42/"),
            (
                "inc-ns1:inc-normal-view",
                [],
                {"arg1": 42, "arg2": 37},
                "/ns-included1/normal/42/37/",
            ),
            ("inc-ns1:inc-special-view", [], {}, "/ns-included1/+%5C$*/"),
        ]
        for name, args, kwargs, expected in test_urls:
            with self.subTest(name=name, args=args, kwargs=kwargs):
                self.assertEqual(reverse(name, args=args, kwargs=kwargs), expected)

    def test_app_name_pattern(self):
        """
        Namespaces can be applied to include()'d urlpatterns that set an
        app_name attribute.
        """
        test_urls = [
            ("app-ns1:inc-normal-view", [], {}, "/app-included1/normal/"),
            ("app-ns1:inc-normal-view", [37, 42], {}, "/app-included1/normal/37/42/"),
            (
                "app-ns1:inc-normal-view",
                [],
                {"arg1": 42, "arg2": 37},
                "/app-included1/normal/42/37/",
            ),
            ("app-ns1:inc-special-view", [], {}, "/app-included1/+%5C$*/"),
        ]
        for name, args, kwargs, expected in test_urls:
            with self.subTest(name=name, args=args, kwargs=kwargs):
                self.assertEqual(reverse(name, args=args, kwargs=kwargs), expected)

    def test_namespace_pattern_with_variable_prefix(self):
        """
        Using include() with namespaces when there is a regex variable in front
        of it.
        """
        test_urls = [
            ("inc-outer:inc-normal-view", [], {"outer": 42}, "/ns-outer/42/normal/"),
            ("inc-outer:inc-normal-view", [42], {}, "/ns-outer/42/normal/"),
            (
                "inc-outer:inc-normal-view",
                [],
                {"arg1": 37, "arg2": 4, "outer": 42},
                "/ns-outer/42/normal/37/4/",
            ),
            ("inc-outer:inc-normal-view", [42, 37, 4], {}, "/ns-outer/42/normal/37/4/"),
            ("inc-outer:inc-special-view", [], {"outer": 42}, "/ns-outer/42/+%5C$*/"),
            ("inc-outer:inc-special-view", [42], {}, "/ns-outer/42/+%5C$*/"),
        ]
        for name, args, kwargs, expected in test_urls:
            with self.subTest(name=name, args=args, kwargs=kwargs):
                self.assertEqual(reverse(name, args=args, kwargs=kwargs), expected)

    def test_multiple_namespace_pattern(self):
        """Namespaces can be embedded."""
        test_urls = [
            ("inc-ns1:test-ns3:urlobject-view", [], {}, "/ns-included1/test3/inner/"),
            (
                "inc-ns1:test-ns3:urlobject-view",
                [37, 42],
                {},
                "/ns-included1/test3/inner/37/42/",
            ),
            (
                "inc-ns1:test-ns3:urlobject-view",
                [],
                {"arg1": 42, "arg2": 37},
                "/ns-included1/test3/inner/42/37/",
            ),
            (
                "inc-ns1:test-ns3:urlobject-special-view",
                [],
                {},
                "/ns-included1/test3/inner/+%5C$*/",
            ),
        ]
        for name, args, kwargs, expected in test_urls:
            with self.subTest(name=name, args=args, kwargs=kwargs):
                self.assertEqual(reverse(name, args=args, kwargs=kwargs), expected)

    def test_nested_namespace_pattern(self):
        """Namespaces can be nested."""
        test_urls = [
            (
                "inc-ns1:inc-ns4:inc-ns1:test-ns3:urlobject-view",
                [],
                {},
                "/ns-included1/ns-included4/ns-included1/test3/inner/",
            ),
            (
                "inc-ns1:inc-ns4:inc-ns1:test-ns3:urlobject-view",
                [37, 42],
                {},
                "/ns-included1/ns-included4/ns-included1/test3/inner/37/42/",
            ),
            (
                "inc-ns1:inc-ns4:inc-ns1:test-ns3:urlobject-view",
                [],
                {"arg1": 42, "arg2": 37},
                "/ns-included1/ns-included4/ns-included1/test3/inner/42/37/",
            ),
            (
                "inc-ns1:inc-ns4:inc-ns1:test-ns3:urlobject-special-view",
                [],
                {},
                "/ns-included1/ns-included4/ns-included1/test3/inner/+%5C$*/",
            ),
        ]
        for name, args, kwargs, expected in test_urls:
            with self.subTest(name=name, args=args, kwargs=kwargs):
                self.assertEqual(reverse(name, args=args, kwargs=kwargs), expected)

    def test_app_lookup_object(self):
        """A default application namespace can be used for lookup."""
        test_urls = [
            ("testapp:urlobject-view", [], {}, "/default/inner/"),
            ("testapp:urlobject-view", [37, 42], {}, "/default/inner/37/42/"),
            (
                "testapp:urlobject-view",
                [],
                {"arg1": 42, "arg2": 37},
                "/default/inner/42/37/",
            ),
            ("testapp:urlobject-special-view", [], {}, "/default/inner/+%5C$*/"),
        ]
        for name, args, kwargs, expected in test_urls:
            with self.subTest(name=name, args=args, kwargs=kwargs):
                self.assertEqual(reverse(name, args=args, kwargs=kwargs), expected)

    def test_app_lookup_object_with_default(self):
        """A default application namespace is sensitive to the current app."""
        test_urls = [
            ("testapp:urlobject-view", [], {}, "test-ns3", "/default/inner/"),
            (
                "testapp:urlobject-view",
                [37, 42],
                {},
                "test-ns3",
                "/default/inner/37/42/",
            ),
            (
                "testapp:urlobject-view",
                [],
                {"arg1": 42, "arg2": 37},
                "test-ns3",
                "/default/inner/42/37/",
            ),
            (
                "testapp:urlobject-special-view",
                [],
                {},
                "test-ns3",
                "/default/inner/+%5C$*/",
            ),
        ]
        for name, args, kwargs, current_app, expected in test_urls:
            with self.subTest(
                name=name, args=args, kwargs=kwargs, current_app=current_app
            ):
                self.assertEqual(
                    reverse(name, args=args, kwargs=kwargs, current_app=current_app),
                    expected,
                )

    def test_app_lookup_object_without_default(self):
        """
        An application namespace without a default is sensitive to the current
        app.
        """
        test_urls = [
            ("nodefault:urlobject-view", [], {}, None, "/other2/inner/"),
            ("nodefault:urlobject-view", [37, 42], {}, None, "/other2/inner/37/42/"),
            (
                "nodefault:urlobject-view",
                [],
                {"arg1": 42, "arg2": 37},
                None,
                "/other2/inner/42/37/",
            ),
            ("nodefault:urlobject-special-view", [], {}, None, "/other2/inner/+%5C$*/"),
            ("nodefault:urlobject-view", [], {}, "other-ns1", "/other1/inner/"),
            (
                "nodefault:urlobject-view",
                [37, 42],
                {},
                "other-ns1",
                "/other1/inner/37/42/",
            ),
            (
                "nodefault:urlobject-view",
                [],
                {"arg1": 42, "arg2": 37},
                "other-ns1",
                "/other1/inner/42/37/",
            ),
            (
                "nodefault:urlobject-special-view",
                [],
                {},
                "other-ns1",
                "/other1/inner/+%5C$*/",
            ),
        ]
        for name, args, kwargs, current_app, expected in test_urls:
            with self.subTest(
                name=name, args=args, kwargs=kwargs, current_app=current_app
            ):
                self.assertEqual(
                    reverse(name, args=args, kwargs=kwargs, current_app=current_app),
                    expected,
                )

    def test_special_chars_namespace(self):
        """
        Tests URL reversal for views within special character namespaces.

        This function checks the correctness of the reverse function when dealing with URLs 
        that contain special characters in their namespace. It verifies that the function 
        correctly handles URL arguments and keyword arguments to produce the expected URL.

        The test cases cover various scenarios, including URLs with and without arguments, 
        as well as keyword arguments, to ensure the reverse function behaves as expected 
        for different use cases.

        Tested scenarios include:

        - Normal views within a namespace containing special characters
        - Views within a namespace containing special characters and requiring arguments
        - Views within a namespace containing special characters and requiring keyword arguments

        Each test case asserts that the reversed URL matches the expected output, 
        providing assurance that the reverse function handles special character namespaces 
        correctly and consistently across different scenarios.
        """
        test_urls = [
            (
                "special:included_namespace_urls:inc-normal-view",
                [],
                {},
                "/+%5C$*/included/normal/",
            ),
            (
                "special:included_namespace_urls:inc-normal-view",
                [37, 42],
                {},
                "/+%5C$*/included/normal/37/42/",
            ),
            (
                "special:included_namespace_urls:inc-normal-view",
                [],
                {"arg1": 42, "arg2": 37},
                "/+%5C$*/included/normal/42/37/",
            ),
            (
                "special:included_namespace_urls:inc-special-view",
                [],
                {},
                "/+%5C$*/included/+%5C$*/",
            ),
        ]
        for name, args, kwargs, expected in test_urls:
            with self.subTest(name=name, args=args, kwargs=kwargs):
                self.assertEqual(reverse(name, args=args, kwargs=kwargs), expected)

    def test_namespaces_with_variables(self):
        """Namespace prefixes can capture variables."""
        test_urls = [
            ("inc-ns5:inner-nothing", [], {"outer": "70"}, "/inc70/"),
            (
                "inc-ns5:inner-extra",
                [],
                {"extra": "foobar", "outer": "78"},
                "/inc78/extra/foobar/",
            ),
            ("inc-ns5:inner-nothing", ["70"], {}, "/inc70/"),
            ("inc-ns5:inner-extra", ["78", "foobar"], {}, "/inc78/extra/foobar/"),
        ]
        for name, args, kwargs, expected in test_urls:
            with self.subTest(name=name, args=args, kwargs=kwargs):
                self.assertEqual(reverse(name, args=args, kwargs=kwargs), expected)

    def test_nested_app_lookup(self):
        """
        A nested current_app should be split in individual namespaces (#24904).
        """
        test_urls = [
            (
                "inc-ns1:testapp:urlobject-view",
                [],
                {},
                None,
                "/ns-included1/test4/inner/",
            ),
            (
                "inc-ns1:testapp:urlobject-view",
                [37, 42],
                {},
                None,
                "/ns-included1/test4/inner/37/42/",
            ),
            (
                "inc-ns1:testapp:urlobject-view",
                [],
                {"arg1": 42, "arg2": 37},
                None,
                "/ns-included1/test4/inner/42/37/",
            ),
            (
                "inc-ns1:testapp:urlobject-special-view",
                [],
                {},
                None,
                "/ns-included1/test4/inner/+%5C$*/",
            ),
            (
                "inc-ns1:testapp:urlobject-view",
                [],
                {},
                "inc-ns1:test-ns3",
                "/ns-included1/test3/inner/",
            ),
            (
                "inc-ns1:testapp:urlobject-view",
                [37, 42],
                {},
                "inc-ns1:test-ns3",
                "/ns-included1/test3/inner/37/42/",
            ),
            (
                "inc-ns1:testapp:urlobject-view",
                [],
                {"arg1": 42, "arg2": 37},
                "inc-ns1:test-ns3",
                "/ns-included1/test3/inner/42/37/",
            ),
            (
                "inc-ns1:testapp:urlobject-special-view",
                [],
                {},
                "inc-ns1:test-ns3",
                "/ns-included1/test3/inner/+%5C$*/",
            ),
        ]
        for name, args, kwargs, current_app, expected in test_urls:
            with self.subTest(
                name=name, args=args, kwargs=kwargs, current_app=current_app
            ):
                self.assertEqual(
                    reverse(name, args=args, kwargs=kwargs, current_app=current_app),
                    expected,
                )

    def test_current_app_no_partial_match(self):
        """current_app shouldn't be used unless it matches the whole path."""
        test_urls = [
            (
                "inc-ns1:testapp:urlobject-view",
                [],
                {},
                "nonexistent:test-ns3",
                "/ns-included1/test4/inner/",
            ),
            (
                "inc-ns1:testapp:urlobject-view",
                [37, 42],
                {},
                "nonexistent:test-ns3",
                "/ns-included1/test4/inner/37/42/",
            ),
            (
                "inc-ns1:testapp:urlobject-view",
                [],
                {"arg1": 42, "arg2": 37},
                "nonexistent:test-ns3",
                "/ns-included1/test4/inner/42/37/",
            ),
            (
                "inc-ns1:testapp:urlobject-special-view",
                [],
                {},
                "nonexistent:test-ns3",
                "/ns-included1/test4/inner/+%5C$*/",
            ),
        ]
        for name, args, kwargs, current_app, expected in test_urls:
            with self.subTest(
                name=name, args=args, kwargs=kwargs, current_app=current_app
            ):
                self.assertEqual(
                    reverse(name, args=args, kwargs=kwargs, current_app=current_app),
                    expected,
                )


@override_settings(ROOT_URLCONF=urlconf_outer.__name__)
class RequestURLconfTests(SimpleTestCase):
    def test_urlconf(self):
        response = self.client.get("/test/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.content, b"outer:/test/me/,inner:/inner_urlconf/second_test/"
        )
        response = self.client.get("/inner_urlconf/second_test/")
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/second_test/")
        self.assertEqual(response.status_code, 404)

    @override_settings(
        MIDDLEWARE=[
            "%s.ChangeURLconfMiddleware" % middleware.__name__,
        ]
    )
    def test_urlconf_overridden(self):
        response = self.client.get("/test/me/")
        self.assertEqual(response.status_code, 404)
        response = self.client.get("/inner_urlconf/second_test/")
        self.assertEqual(response.status_code, 404)
        response = self.client.get("/second_test/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"outer:,inner:/second_test/")

    @override_settings(
        MIDDLEWARE=[
            "%s.NullChangeURLconfMiddleware" % middleware.__name__,
        ]
    )
    def test_urlconf_overridden_with_null(self):
        """
        Overriding request.urlconf with None will fall back to the default
        URLconf.
        """
        response = self.client.get("/test/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.content, b"outer:/test/me/,inner:/inner_urlconf/second_test/"
        )
        response = self.client.get("/inner_urlconf/second_test/")
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/second_test/")
        self.assertEqual(response.status_code, 404)

    @override_settings(
        MIDDLEWARE=[
            "%s.ChangeURLconfMiddleware" % middleware.__name__,
            "%s.ReverseInnerInResponseMiddleware" % middleware.__name__,
        ]
    )
    def test_reverse_inner_in_response_middleware(self):
        """
        Test reversing an URL from the *overridden* URLconf from inside
        a response middleware.
        """
        response = self.client.get("/second_test/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"/second_test/")

    @override_settings(
        MIDDLEWARE=[
            "%s.ChangeURLconfMiddleware" % middleware.__name__,
            "%s.ReverseOuterInResponseMiddleware" % middleware.__name__,
        ]
    )
    def test_reverse_outer_in_response_middleware(self):
        """
        Test reversing an URL from the *default* URLconf from inside
        a response middleware.
        """
        msg = (
            "Reverse for 'outer' not found. 'outer' is not a valid view "
            "function or pattern name."
        )
        with self.assertRaisesMessage(NoReverseMatch, msg):
            self.client.get("/second_test/")

    @override_settings(
        MIDDLEWARE=[
            "%s.ChangeURLconfMiddleware" % middleware.__name__,
            "%s.ReverseInnerInStreaming" % middleware.__name__,
        ]
    )
    def test_reverse_inner_in_streaming(self):
        """
        Test reversing an URL from the *overridden* URLconf from inside
        a streaming response.
        """
        response = self.client.get("/second_test/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response), b"/second_test/")

    @override_settings(
        MIDDLEWARE=[
            "%s.ChangeURLconfMiddleware" % middleware.__name__,
            "%s.ReverseOuterInStreaming" % middleware.__name__,
        ]
    )
    def test_reverse_outer_in_streaming(self):
        """
        Test reversing an URL from the *default* URLconf from inside
        a streaming response.
        """
        message = "Reverse for 'outer' not found."
        with self.assertRaisesMessage(NoReverseMatch, message):
            self.client.get("/second_test/")
            b"".join(self.client.get("/second_test/"))

    def test_urlconf_is_reset_after_request(self):
        """The URLconf is reset after each request."""
        self.assertIsNone(get_urlconf())
        with override_settings(
            MIDDLEWARE=["%s.ChangeURLconfMiddleware" % middleware.__name__]
        ):
            self.client.get(reverse("inner"))
        self.assertIsNone(get_urlconf())


class ErrorHandlerResolutionTests(SimpleTestCase):
    """Tests for handler400, handler403, handler404 and handler500"""

    def setUp(self):
        """
        Set up URL resolvers for testing error handlers.

        This method initializes two URL resolvers: one for error handlers defined in the project's URL configuration, 
        and another for error handlers that are callable. The resolvers are used to resolve URLs against the project's 
        URL patterns, allowing for testing of error handling behavior in different scenarios.
        """
        urlconf = "urlpatterns_reverse.urls_error_handlers"
        urlconf_callables = "urlpatterns_reverse.urls_error_handlers_callables"
        self.resolver = URLResolver(RegexPattern(r"^$"), urlconf)
        self.callable_resolver = URLResolver(RegexPattern(r"^$"), urlconf_callables)

    def test_named_handlers(self):
        """
        Test the named error handlers for specific HTTP error codes.

        This test case verifies that the error resolver returns the expected view
        function (empty_view) for a set of predefined HTTP error codes, including 
        Bad Request (400), Forbidden (403), Not Found (404), and Internal Server Error (500).
        It ensures that each error code is correctly handled by the resolver and 
        returns the appropriate view response.
        """
        for code in [400, 403, 404, 500]:
            with self.subTest(code=code):
                self.assertEqual(self.resolver.resolve_error_handler(code), empty_view)

    def test_callable_handlers(self):
        """
        Tests the callable handlers for resolving error handlers.

        This function iterates over a list of HTTP error codes and verifies that the corresponding error handlers are resolved correctly.
        The error codes tested include bad request, forbidden, not found, and internal server error.
        For each error code, it checks that the callable resolver returns the expected empty view handler.
        """
        for code in [400, 403, 404, 500]:
            with self.subTest(code=code):
                self.assertEqual(
                    self.callable_resolver.resolve_error_handler(code), empty_view
                )


@override_settings(ROOT_URLCONF="urlpatterns_reverse.urls_without_handlers")
class DefaultErrorHandlerTests(SimpleTestCase):
    def test_default_handler(self):
        "If the urls.py doesn't specify handlers, the defaults are used"
        response = self.client.get("/test/")
        self.assertEqual(response.status_code, 404)

        msg = "I don't think I'm getting good value for this view"
        with self.assertRaisesMessage(ValueError, msg):
            self.client.get("/bad_view/")


@override_settings(ROOT_URLCONF=None)
class NoRootUrlConfTests(SimpleTestCase):
    """Tests for handler404 and handler500 if ROOT_URLCONF is None"""

    def test_no_handler_exception(self):
        """

        Tests that a 500 error with a clear message is raised when no handler is found 
        for a URL, likely due to an empty or improperly configured URLconf.

        Verifies that an ImproperlyConfigured exception is raised with a specific 
        error message when attempting to access a URL that has not been defined 
        in the URL patterns. The error message suggests checking for circular 
        imports and ensures that the 'urlpatterns' variable is correctly defined.

        """
        msg = (
            "The included URLconf 'None' does not appear to have any patterns "
            "in it. If you see the 'urlpatterns' variable with valid patterns "
            "in the file then the issue is probably caused by a circular "
            "import."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            self.client.get("/test/me/")


@override_settings(ROOT_URLCONF="urlpatterns_reverse.namespace_urls")
class ResolverMatchTests(SimpleTestCase):
    def test_urlpattern_resolve(self):
        for (
            path_,
            url_name,
            app_name,
            namespace,
            view_name,
            func,
            args,
            kwargs,
        ) in resolve_test_data:
            with self.subTest(path=path_):
                # Legacy support for extracting "function, args, kwargs".
                match_func, match_args, match_kwargs = resolve(path_)
                self.assertEqual(match_func, func)
                self.assertEqual(match_args, args)
                self.assertEqual(match_kwargs, kwargs)
                # ResolverMatch capabilities.
                match = resolve(path_)
                self.assertEqual(match.__class__, ResolverMatch)
                self.assertEqual(match.url_name, url_name)
                self.assertEqual(match.app_name, app_name)
                self.assertEqual(match.namespace, namespace)
                self.assertEqual(match.view_name, view_name)
                self.assertEqual(match.func, func)
                self.assertEqual(match.args, args)
                self.assertEqual(match.kwargs, kwargs)
                # and for legacy purposes:
                self.assertEqual(match[0], func)
                self.assertEqual(match[1], args)
                self.assertEqual(match[2], kwargs)

    def test_resolver_match_on_request(self):
        """
        Tests that the resolver match URL name is correctly set on a request.

        Verifies that the resolver match object returned by the request contains the
        expected URL name, ensuring that the resolver is correctly matching the URL
        pattern for the given request route.

        The test case checks the 'test-resolver-match' URL name, which is expected to be
        resolved to the corresponding URL pattern when a GET request is made to the
        '/resolver_match/' endpoint.
        """
        response = self.client.get("/resolver_match/")
        resolver_match = response.resolver_match
        self.assertEqual(resolver_match.url_name, "test-resolver-match")

    def test_resolver_match_on_request_before_resolution(self):
        """
        Tests that the resolver match attribute is None on an HttpRequest object before resolution.

        This test case verifies the initial state of the resolver match attribute, 
        ensuring it is correctly set to None prior to the resolution process.

        :raises AssertionError: If the resolver match attribute is not None.

        """
        request = HttpRequest()
        self.assertIsNone(request.resolver_match)

    def test_repr(self):
        self.assertEqual(
            repr(resolve("/no_kwargs/42/37/")),
            "ResolverMatch(func=urlpatterns_reverse.views.empty_view, "
            "args=('42', '37'), kwargs={}, url_name='no-kwargs', app_names=[], "
            "namespaces=[], route='^no_kwargs/([0-9]+)/([0-9]+)/$')",
        )

    def test_repr_extra_kwargs(self):
        self.assertEqual(
            repr(resolve("/mixed_args/1986/11/")),
            "ResolverMatch(func=urlpatterns_reverse.views.empty_view, args=(), "
            "kwargs={'arg2': '11', 'extra': True}, url_name='mixed-args', "
            "app_names=[], namespaces=[], "
            "route='^mixed_args/([0-9]+)/(?P<arg2>[0-9]+)/$', "
            "captured_kwargs={'arg2': '11'}, extra_kwargs={'extra': True})",
        )

    @override_settings(ROOT_URLCONF="urlpatterns_reverse.reverse_lazy_urls")
    def test_classbased_repr(self):
        self.assertEqual(
            repr(resolve("/redirect/")),
            "ResolverMatch(func=urlpatterns_reverse.views.LazyRedirectView, "
            "args=(), kwargs={}, url_name=None, app_names=[], "
            "namespaces=[], route='redirect/')",
        )

    @override_settings(ROOT_URLCONF="urlpatterns_reverse.urls")
    def test_repr_functools_partial(self):
        tests = [
            ("partial", "template.html"),
            ("partial_nested", "nested_partial.html"),
            ("partial_wrapped", "template.html"),
        ]
        for name, template_name in tests:
            with self.subTest(name=name):
                func = (
                    f"functools.partial({views.empty_view!r}, "
                    f"template_name='{template_name}')"
                )
                self.assertEqual(
                    repr(resolve(f"/{name}/")),
                    f"ResolverMatch(func={func}, args=(), kwargs={{}}, "
                    f"url_name='{name}', app_names=[], namespaces=[], "
                    f"route='{name}/')",
                )

    @override_settings(ROOT_URLCONF="urlpatterns.path_urls")
    def test_pickling(self):
        msg = "Cannot pickle ResolverMatch."
        with self.assertRaisesMessage(pickle.PicklingError, msg):
            pickle.dumps(resolve("/users/"))


@override_settings(ROOT_URLCONF="urlpatterns_reverse.erroneous_urls")
class ErroneousViewTests(SimpleTestCase):
    def test_noncallable_view(self):
        # View is not a callable (explicit import; arbitrary Python object)
        """

        Tests that a TypeError is raised when a non-callable object is passed as a view to the path function.

        The test verifies that the error message 'view must be a callable' is correctly raised when an uncallable object is used as a view.

        """
        with self.assertRaisesMessage(TypeError, "view must be a callable"):
            path("uncallable-object/", views.uncallable)

    def test_invalid_regex(self):
        # Regex contains an error (refs #6170)
        """
        Tests that an invalid regular expression raises an ImproperlyConfigured exception.

        Verifies that the reverse function correctly handles invalid regex patterns,
        ensuring that the application is properly configured and handles errors as expected.

        The test case checks for a specific error message indicating that the provided
        regex pattern is not valid, demonstrating the function's validation capabilities.

        Raises:
            ImproperlyConfigured: If the regex pattern is invalid.

        """
        msg = '(regex_error/$" is not a valid regular expression'
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            reverse(views.empty_view)


class ViewLoadingTests(SimpleTestCase):
    def test_view_loading(self):
        """

        Tests the proper loading of views.

        Verifies that the :func:`get_callable` function correctly resolves view callables, 
        both when provided with a string reference to a view and when provided with a view 
        object itself. The test confirms that the function returns the expected view object 
        in both scenarios, ensuring that view loading and resolution behave as expected.

        """
        self.assertEqual(
            get_callable("urlpatterns_reverse.views.empty_view"), empty_view
        )
        self.assertEqual(get_callable(empty_view), empty_view)

    def test_view_does_not_exist(self):
        """

        Tests that a specific view does not exist in the module.

        Verifies that attempting to retrieve a non-existent view raises a 'ViewDoesNotExist' exception
        with a descriptive error message, ensuring proper error handling and view validation.

        """
        msg = "View does not exist in module urlpatterns_reverse.views."
        with self.assertRaisesMessage(ViewDoesNotExist, msg):
            get_callable("urlpatterns_reverse.views.i_should_not_exist")

    def test_attributeerror_not_hidden(self):
        """
        Tests that an AttributeError is properly raised and its error message is not hidden 
        when Django's get_callable function fails to find a callable object.

        This test ensures that when get_callable is given a string representing a non-existent 
        view, it correctly raises an AttributeError with a descriptive error message, 
        indicating the source of the problem rather than masking it with a generic error.
        """
        msg = "I am here to confuse django.urls.get_callable"
        with self.assertRaisesMessage(AttributeError, msg):
            get_callable("urlpatterns_reverse.views_broken.i_am_broken")

    def test_non_string_value(self):
        """
        Test that passing a non-string value to the get_callable function raises a ViewDoesNotExist exception with a descriptive error message, ensuring the function enforces its input type requirements.
        """
        msg = "'1' is not a callable or a dot-notation path"
        with self.assertRaisesMessage(ViewDoesNotExist, msg):
            get_callable(1)

    def test_string_without_dot(self):
        msg = "Could not import 'test'. The path must be fully qualified."
        with self.assertRaisesMessage(ImportError, msg):
            get_callable("test")

    def test_module_does_not_exist(self):
        """
        Test that attempting to retrieve a callable from a non-existent module raises an ImportError.

        This test case verifies that the correct error message is raised when trying to
        access a module that does not exist. The expected error message indicates that
        the module 'foo' cannot be found, which is the expected behavior when trying to
        access a non-existent module.

        :raises ImportError: If the module 'foo' is not found.

        """
        with self.assertRaisesMessage(ImportError, "No module named 'foo'"):
            get_callable("foo.bar")

    def test_parent_module_does_not_exist(self):
        """
        Tests that a ViewDoesNotExist exception is raised when the parent module for a given view does not exist.

        This test case covers the scenario where the parent module 'urlpatterns_reverse.foo' is not defined,
        and verifies that the get_callable function correctly handles this situation by raising a ViewDoesNotExist exception
        with a descriptive error message, indicating that the parent module does not exist.
        """
        msg = "Parent module urlpatterns_reverse.foo does not exist."
        with self.assertRaisesMessage(ViewDoesNotExist, msg):
            get_callable("urlpatterns_reverse.foo.bar")

    def test_not_callable(self):
        """
        Tests that a non-callable object raises a ViewDoesNotExist exception when attempting to retrieve it as a callable view.

        This test case verifies that the get_callable function correctly handles the case where the specified object is not callable, 
        by checking that it raises a ViewDoesNotExist exception with the expected error message.
        """
        msg = (
            "Could not import 'urlpatterns_reverse.tests.resolve_test_data'. "
            "View is not callable."
        )
        with self.assertRaisesMessage(ViewDoesNotExist, msg):
            get_callable("urlpatterns_reverse.tests.resolve_test_data")


class IncludeTests(SimpleTestCase):
    url_patterns = [
        path("inner/", views.empty_view, name="urlobject-view"),
        re_path(
            r"^inner/(?P<arg1>[0-9]+)/(?P<arg2>[0-9]+)/$",
            views.empty_view,
            name="urlobject-view",
        ),
        re_path(r"^inner/\+\\\$\*/$", views.empty_view, name="urlobject-special-view"),
    ]
    app_urls = URLObject("inc-app")

    def test_include_urls(self):
        self.assertEqual(include(self.url_patterns), (self.url_patterns, None, None))

    def test_include_namespace(self):
        """
        Tests that including a URL pattern with a namespace raises an ImproperlyConfigured exception if an app_name is not provided.

        This test case ensures that the include function behaves correctly when a namespace is specified without an accompanying app_name, validating that it raises the expected exception with a clear error message.
        """
        msg = (
            "Specifying a namespace in include() without providing an "
            "app_name is not supported."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            include(self.url_patterns, "namespace")

    def test_include_4_tuple(self):
        """
        Tests that passing a 4-tuple to the include function raises an ImproperlyConfigured exception.

        The test verifies that the include function correctly identifies and rejects 4-tuple arguments, ensuring that only supported tuple lengths are accepted.

        Raises:
            ImproperlyConfigured: if a 4-tuple is passed to the include function.

        Notes:
            This test is used to enforce the proper usage of the include function and prevent potential errors that may arise from passing unsupported tuple lengths.
        """
        msg = "Passing a 4-tuple to include() is not supported."
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            include((self.url_patterns, "app_name", "namespace", "blah"))

    def test_include_3_tuple(self):
        """
        Tests that passing a 3-tuple to the include() function raises an ImproperlyConfigured exception.

        This test verifies that the include() function correctly handles invalid input by
        raising an exception when a 3-tuple is passed, as this is not a supported syntax.

        The expected exception message indicates that the 3-tuple is not a valid argument
        for the include() function, providing a clear error message for users who may
        encounter this issue.

        Raises:
            ImproperlyConfigured: If a 3-tuple is passed to the include() function.

        """
        msg = "Passing a 3-tuple to include() is not supported."
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            include((self.url_patterns, "app_name", "namespace"))

    def test_include_3_tuple_namespace(self):
        msg = (
            "Cannot override the namespace for a dynamic module that provides a "
            "namespace."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            include((self.url_patterns, "app_name", "namespace"), "namespace")

    def test_include_2_tuple(self):
        self.assertEqual(
            include((self.url_patterns, "app_name")),
            (self.url_patterns, "app_name", "app_name"),
        )

    def test_include_2_tuple_namespace(self):
        self.assertEqual(
            include((self.url_patterns, "app_name"), namespace="namespace"),
            (self.url_patterns, "app_name", "namespace"),
        )

    def test_include_app_name(self):
        self.assertEqual(include(self.app_urls), (self.app_urls, "inc-app", "inc-app"))

    def test_include_app_name_namespace(self):
        self.assertEqual(
            include(self.app_urls, "namespace"), (self.app_urls, "inc-app", "namespace")
        )


@override_settings(ROOT_URLCONF="urlpatterns_reverse.urls")
class LookaheadTests(SimpleTestCase):
    def test_valid_resolve(self):
        """
        Test that the resolve function correctly extracts the city from a given URL.

        The test checks for various URL patterns, including those with lookahead and lookbehind characters,
        to ensure that the function returns the expected keyword argument 'city'.

        Parameters
        ----------
        None

        Returns
        -------
        None

        Notes
        -----
        This test case verifies that the resolve function behaves as expected for different types of URLs,
        with the goal of ensuring that the city is correctly extracted and passed as a keyword argument.
        """
        test_urls = [
            "/lookahead-/a-city/",
            "/lookbehind-/a-city/",
            "/lookahead+/a-city/",
            "/lookbehind+/a-city/",
        ]
        for test_url in test_urls:
            with self.subTest(url=test_url):
                self.assertEqual(resolve(test_url).kwargs, {"city": "a-city"})

    def test_invalid_resolve(self):
        """

        Tests that the resolver correctly raises a 404 error for invalid URLs.

        This test checks that URLs with invalid lookahead and lookbehind patterns
        do not resolve successfully. The test cases cover both negative and
        positive lookahead and lookbehind patterns.

        Raises:
            Resolver404: If the URL is successfully resolved.

        """
        test_urls = [
            "/lookahead-/not-a-city/",
            "/lookbehind-/not-a-city/",
            "/lookahead+/other-city/",
            "/lookbehind+/other-city/",
        ]
        for test_url in test_urls:
            with self.subTest(url=test_url):
                with self.assertRaises(Resolver404):
                    resolve(test_url)

    def test_valid_reverse(self):
        test_urls = [
            ("lookahead-positive", {"city": "a-city"}, "/lookahead+/a-city/"),
            ("lookahead-negative", {"city": "a-city"}, "/lookahead-/a-city/"),
            ("lookbehind-positive", {"city": "a-city"}, "/lookbehind+/a-city/"),
            ("lookbehind-negative", {"city": "a-city"}, "/lookbehind-/a-city/"),
        ]
        for name, kwargs, expected in test_urls:
            with self.subTest(name=name, kwargs=kwargs):
                self.assertEqual(reverse(name, kwargs=kwargs), expected)

    def test_invalid_reverse(self):
        """

        Tests the reverse URL resolution with invalid input to ensure it correctly raises a NoReverseMatch exception.

        This test case covers different scenarios, including lookahead and lookbehind conditions with both positive and negative matches.
        It verifies that the reverse function fails as expected when attempting to resolve URLs with mismatched or invalid city parameters.

        """
        test_urls = [
            ("lookahead-positive", {"city": "other-city"}),
            ("lookahead-negative", {"city": "not-a-city"}),
            ("lookbehind-positive", {"city": "other-city"}),
            ("lookbehind-negative", {"city": "not-a-city"}),
        ]
        for name, kwargs in test_urls:
            with self.subTest(name=name, kwargs=kwargs):
                with self.assertRaises(NoReverseMatch):
                    reverse(name, kwargs=kwargs)


@override_settings(ROOT_URLCONF="urlpatterns_reverse.urls")
class ReverseResolvedTests(SimpleTestCase):
    def test_rereverse(self):
        """

        Tests the reverse URL functionality to ensure correct URL reconstruction.

        Verifies that the reverse function correctly generates the original URL from the 
        resolved URL match, including cases where URL patterns may have been overridden.

        The test covers the reversal of URLs with both regular and overridden patterns, 
        checking that the resulting URLs match the originals, thereby validating the 
        correctness of the reverse function's behavior.

        """
        match = resolve("/resolved/12/")
        self.assertEqual(
            reverse(match.url_name, args=match.args, kwargs=match.kwargs),
            "/resolved/12/",
        )
        match = resolve("/resolved-overridden/12/url/")
        self.assertEqual(
            reverse(match.url_name, args=match.args, kwargs=match.captured_kwargs),
            "/resolved-overridden/12/url/",
        )
