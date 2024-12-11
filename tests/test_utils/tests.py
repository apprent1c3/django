import os
import sys
import threading
import unittest
import warnings
from io import StringIO
from unittest import mock

from django.conf import STATICFILES_STORAGE_ALIAS, settings
from django.contrib.staticfiles.finders import get_finder, get_finders
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import default_storage
from django.db import (
    IntegrityError,
    connection,
    connections,
    models,
    router,
    transaction,
)
from django.forms import (
    CharField,
    EmailField,
    Form,
    IntegerField,
    ValidationError,
    formset_factory,
)
from django.http import HttpResponse
from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import (
    SimpleTestCase,
    TestCase,
    TransactionTestCase,
    skipIfDBFeature,
    skipUnlessDBFeature,
)
from django.test.html import HTMLParseError, parse_html
from django.test.testcases import DatabaseOperationForbidden
from django.test.utils import (
    CaptureQueriesContext,
    TestContextDecorator,
    isolate_apps,
    override_settings,
    setup_test_environment,
)
from django.urls import NoReverseMatch, path, reverse, reverse_lazy
from django.utils.html import VOID_ELEMENTS
from django.utils.version import PY311

from .models import Car, Person, PossessedCar
from .views import empty_response


class SkippingTestCase(SimpleTestCase):
    def _assert_skipping(self, func, expected_exc, msg=None):
        """
        Asserts that a given function raises the expected exception when called.

        Checks if the provided function `func` raises an exception of type `expected_exc`.
        If a message `msg` is specified, it also checks if the raised exception contains the given message.
        The function fails the test if the function call results in a skipped test instead of raising the expected exception.

        Use this method to verify that a function behaves correctly in error scenarios or when specific conditions are met.
        It provides a way to ensure that expected exceptions are raised with the correct error messages, making it easier to diagnose issues and maintain code quality.

        :param func: The function to be called and checked for the expected exception.
        :param expected_exc: The expected type of exception to be raised by `func`.
        :param msg: The expected error message to be present in the raised exception, defaults to None.

        """
        try:
            if msg is not None:
                with self.assertRaisesMessage(expected_exc, msg):
                    func()
            else:
                with self.assertRaises(expected_exc):
                    func()
        except unittest.SkipTest:
            self.fail("%s should not result in a skipped test." % func.__name__)

    def test_skip_unless_db_feature(self):
        """
        Testing the django.test.skipUnlessDBFeature decorator.
        """

        # Total hack, but it works, just want an attribute that's always true.
        @skipUnlessDBFeature("__class__")
        def test_func():
            raise ValueError

        @skipUnlessDBFeature("notprovided")
        def test_func2():
            raise ValueError

        @skipUnlessDBFeature("__class__", "__class__")
        def test_func3():
            raise ValueError

        @skipUnlessDBFeature("__class__", "notprovided")
        def test_func4():
            raise ValueError

        self._assert_skipping(test_func, ValueError)
        self._assert_skipping(test_func2, unittest.SkipTest)
        self._assert_skipping(test_func3, ValueError)
        self._assert_skipping(test_func4, unittest.SkipTest)

        class SkipTestCase(SimpleTestCase):
            @skipUnlessDBFeature("missing")
            def test_foo(self):
                pass

        self._assert_skipping(
            SkipTestCase("test_foo").test_foo,
            ValueError,
            "skipUnlessDBFeature cannot be used on test_foo (test_utils.tests."
            "SkippingTestCase.test_skip_unless_db_feature.<locals>.SkipTestCase%s) "
            "as SkippingTestCase.test_skip_unless_db_feature.<locals>.SkipTestCase "
            "doesn't allow queries against the 'default' database."
            # Python 3.11 uses fully qualified test name in the output.
            % (".test_foo" if PY311 else ""),
        )

    def test_skip_if_db_feature(self):
        """
        Testing the django.test.skipIfDBFeature decorator.
        """

        @skipIfDBFeature("__class__")
        def test_func():
            raise ValueError

        @skipIfDBFeature("notprovided")
        def test_func2():
            raise ValueError

        @skipIfDBFeature("__class__", "__class__")
        def test_func3():
            raise ValueError

        @skipIfDBFeature("__class__", "notprovided")
        def test_func4():
            raise ValueError

        @skipIfDBFeature("notprovided", "notprovided")
        def test_func5():
            raise ValueError

        self._assert_skipping(test_func, unittest.SkipTest)
        self._assert_skipping(test_func2, ValueError)
        self._assert_skipping(test_func3, unittest.SkipTest)
        self._assert_skipping(test_func4, unittest.SkipTest)
        self._assert_skipping(test_func5, ValueError)

        class SkipTestCase(SimpleTestCase):
            @skipIfDBFeature("missing")
            def test_foo(self):
                pass

        self._assert_skipping(
            SkipTestCase("test_foo").test_foo,
            ValueError,
            "skipIfDBFeature cannot be used on test_foo (test_utils.tests."
            "SkippingTestCase.test_skip_if_db_feature.<locals>.SkipTestCase%s) "
            "as SkippingTestCase.test_skip_if_db_feature.<locals>.SkipTestCase "
            "doesn't allow queries against the 'default' database."
            # Python 3.11 uses fully qualified test name in the output.
            % (".test_foo" if PY311 else ""),
        )


class SkippingClassTestCase(TransactionTestCase):
    available_apps = []

    def test_skip_class_unless_db_feature(self):
        @skipUnlessDBFeature("__class__")
        """

        Tests the skip_class_unless_db_feature decorator to ensure it correctly skips 
        or runs test classes based on the presence or absence of specified database features.

        Verifies that classes with matching database features are not skipped, while classes 
        with non-matching or conflicting features are skipped, including cases where a class 
        inherits from a skipped class.

        Checks for the expected number of tests being run and skipped, and validates the 
        skip reasons provided for the skipped tests.

        """
        class NotSkippedTests(TestCase):
            def test_dummy(self):
                return

        @skipUnlessDBFeature("missing")
        @skipIfDBFeature("__class__")
        class SkippedTests(TestCase):
            def test_will_be_skipped(self):
                self.fail("We should never arrive here.")

        @skipIfDBFeature("__dict__")
        class SkippedTestsSubclass(SkippedTests):
            pass

        test_suite = unittest.TestSuite()
        test_suite.addTest(NotSkippedTests("test_dummy"))
        try:
            test_suite.addTest(SkippedTests("test_will_be_skipped"))
            test_suite.addTest(SkippedTestsSubclass("test_will_be_skipped"))
        except unittest.SkipTest:
            self.fail("SkipTest should not be raised here.")
        result = unittest.TextTestRunner(stream=StringIO()).run(test_suite)
        # PY312: Python 3.12.1 does not include skipped tests in the number of
        # running tests.
        self.assertEqual(
            result.testsRun, 1 if sys.version_info[:3] == (3, 12, 1) else 3
        )
        self.assertEqual(len(result.skipped), 2)
        self.assertEqual(result.skipped[0][1], "Database has feature(s) __class__")
        self.assertEqual(result.skipped[1][1], "Database has feature(s) __class__")

    def test_missing_default_databases(self):
        @skipIfDBFeature("missing")
        class MissingDatabases(SimpleTestCase):
            def test_assertion_error(self):
                pass

        suite = unittest.TestSuite()
        try:
            suite.addTest(MissingDatabases("test_assertion_error"))
        except unittest.SkipTest:
            self.fail("SkipTest should not be raised at this stage")
        runner = unittest.TextTestRunner(stream=StringIO())
        msg = (
            "skipIfDBFeature cannot be used on <class 'test_utils.tests."
            "SkippingClassTestCase.test_missing_default_databases.<locals>."
            "MissingDatabases'> as it doesn't allow queries against the "
            "'default' database."
        )
        with self.assertRaisesMessage(ValueError, msg):
            runner.run(suite)


@override_settings(ROOT_URLCONF="test_utils.urls")
class AssertNumQueriesTests(TestCase):
    def test_assert_num_queries(self):
        def test_func():
            raise ValueError

        with self.assertRaises(ValueError):
            self.assertNumQueries(2, test_func)

    def test_assert_num_queries_with_client(self):
        """

        Test that the correct number of database queries are executed when using the client to make requests.

        This test case verifies that the number of queries executed when making requests to the '/test_utils/get_person/<id>/' endpoint is as expected.
        It checks the number of queries executed both when making individual requests and when making multiple requests within a single test function.

        The test creates a Person instance and then uses the client to make GET requests to the endpoint, asserting that the expected number of queries is executed in each case.

        """
        person = Person.objects.create(name="test")

        self.assertNumQueries(
            1, self.client.get, "/test_utils/get_person/%s/" % person.pk
        )

        self.assertNumQueries(
            1, self.client.get, "/test_utils/get_person/%s/" % person.pk
        )

        def test_func():
            self.client.get("/test_utils/get_person/%s/" % person.pk)
            self.client.get("/test_utils/get_person/%s/" % person.pk)

        self.assertNumQueries(2, test_func)


class AssertNumQueriesUponConnectionTests(TransactionTestCase):
    available_apps = []

    def test_ignores_connection_configuration_queries(self):
        """

        Tests that the connection configuration queries are ignored when checking the number of database queries.

        This test ensures that the database connection configuration queries, which are executed to set up the connection,
        are not counted towards the total number of queries. This is done by simulating a connection setup and then 
        querying the database to retrieve a list of Car objects, while mocking the ensure_connection method to 
        execute a configuration query. The test then asserts that only one query is executed, which is the query to 
        retrieve the Car objects.

        """
        real_ensure_connection = connection.ensure_connection
        connection.close()

        def make_configuration_query():
            """
            Establishes a connection to the database and executes a minimal query to ensure the connection is valid.

            This function first checks if a connection to the database is already established. If not, it initiates the connection. It then executes a simple SELECT query to test the connection, ensuring that it can successfully communicate with the database. The query executed is optimized for the specific database features, appending any necessary suffix required by the database backend. The function does not return any value, its purpose is to verify and set up a working database connection.
            """
            is_opening_connection = connection.connection is None
            real_ensure_connection()

            if is_opening_connection:
                # Avoid infinite recursion. Creating a cursor calls
                # ensure_connection() which is currently mocked by this method.
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1" + connection.features.bare_select_suffix)

        ensure_connection = (
            "django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection"
        )
        with mock.patch(ensure_connection, side_effect=make_configuration_query):
            with self.assertNumQueries(1):
                list(Car.objects.all())


class AssertQuerySetEqualTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """

        Sets up test data for the class, creating two Person objects for use in subsequent tests.

        The created objects include two people, 'p1' and 'p2', which can be referenced in tests as class attributes.

        """
        cls.p1 = Person.objects.create(name="p1")
        cls.p2 = Person.objects.create(name="p2")

    def test_empty(self):
        self.assertQuerySetEqual(Person.objects.filter(name="p3"), [])

    def test_ordered(self):
        self.assertQuerySetEqual(
            Person.objects.order_by("name"),
            [self.p1, self.p2],
        )

    def test_unordered(self):
        self.assertQuerySetEqual(
            Person.objects.order_by("name"), [self.p2, self.p1], ordered=False
        )

    def test_queryset(self):
        self.assertQuerySetEqual(
            Person.objects.order_by("name"),
            Person.objects.order_by("name"),
        )

    def test_flat_values_list(self):
        self.assertQuerySetEqual(
            Person.objects.order_by("name").values_list("name", flat=True),
            ["p1", "p2"],
        )

    def test_transform(self):
        self.assertQuerySetEqual(
            Person.objects.order_by("name"),
            [self.p1.pk, self.p2.pk],
            transform=lambda x: x.pk,
        )

    def test_repr_transform(self):
        self.assertQuerySetEqual(
            Person.objects.order_by("name"),
            [repr(self.p1), repr(self.p2)],
            transform=repr,
        )

    def test_undefined_order(self):
        # Using an unordered queryset with more than one ordered value
        # is an error.
        msg = (
            "Trying to compare non-ordered queryset against more than one "
            "ordered value."
        )
        with self.assertRaisesMessage(ValueError, msg):
            self.assertQuerySetEqual(
                Person.objects.all(),
                [self.p1, self.p2],
            )
        # No error for one value.
        self.assertQuerySetEqual(Person.objects.filter(name="p1"), [self.p1])

    def test_repeated_values(self):
        """
        assertQuerySetEqual checks the number of appearance of each item
        when used with option ordered=False.
        """
        batmobile = Car.objects.create(name="Batmobile")
        k2000 = Car.objects.create(name="K 2000")
        PossessedCar.objects.bulk_create(
            [
                PossessedCar(car=batmobile, belongs_to=self.p1),
                PossessedCar(car=batmobile, belongs_to=self.p1),
                PossessedCar(car=k2000, belongs_to=self.p1),
                PossessedCar(car=k2000, belongs_to=self.p1),
                PossessedCar(car=k2000, belongs_to=self.p1),
                PossessedCar(car=k2000, belongs_to=self.p1),
            ]
        )
        with self.assertRaises(AssertionError):
            self.assertQuerySetEqual(
                self.p1.cars.all(), [batmobile, k2000], ordered=False
            )
        self.assertQuerySetEqual(
            self.p1.cars.all(), [batmobile] * 2 + [k2000] * 4, ordered=False
        )

    def test_maxdiff(self):
        """
        Tests the behavior of the `assertQuerySetEqual` method when the difference between two sets exceeds the `maxDiff` limit.

         Verifies that an `AssertionError` is raised when the difference is too large, and that the error message suggests setting `maxDiff` to `None` to see the full difference.

         Then, it tests the same assertion with `maxDiff` set to `None`, ensuring that the full difference is included in the error message and that all elements from the expected set are present in the error message.
        """
        names = ["Joe Smith %s" % i for i in range(20)]
        Person.objects.bulk_create([Person(name=name) for name in names])
        names.append("Extra Person")

        with self.assertRaises(AssertionError) as ctx:
            self.assertQuerySetEqual(
                Person.objects.filter(name__startswith="Joe"),
                names,
                ordered=False,
                transform=lambda p: p.name,
            )
        self.assertIn("Set self.maxDiff to None to see it.", str(ctx.exception))

        original = self.maxDiff
        self.maxDiff = None
        try:
            with self.assertRaises(AssertionError) as ctx:
                self.assertQuerySetEqual(
                    Person.objects.filter(name__startswith="Joe"),
                    names,
                    ordered=False,
                    transform=lambda p: p.name,
                )
        finally:
            self.maxDiff = original
        exception_msg = str(ctx.exception)
        self.assertNotIn("Set self.maxDiff to None to see it.", exception_msg)
        for name in names:
            self.assertIn(name, exception_msg)


@override_settings(ROOT_URLCONF="test_utils.urls")
class CaptureQueriesContextManagerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.person_pk = str(Person.objects.create(name="test").pk)

    def test_simple(self):
        """

        Tests the query capturing functionality to ensure it correctly captures and logs database queries.

        This test case verifies that a single query is captured when retrieving a Person object by primary key, 
        and that the primary key is correctly included in the captured query's SQL string. 

        Additionally, it checks that when no queries are executed, the captured queries list remains empty, 
        successfully demonstrating the context manager's ability to accurately track query execution.

        """
        with CaptureQueriesContext(connection) as captured_queries:
            Person.objects.get(pk=self.person_pk)
        self.assertEqual(len(captured_queries), 1)
        self.assertIn(self.person_pk, captured_queries[0]["sql"])

        with CaptureQueriesContext(connection) as captured_queries:
            pass
        self.assertEqual(0, len(captured_queries))

    def test_within(self):
        """
        Tests that retrieving a Person object by primary key results in a single database query.

        This test case verifies that the database query executed to retrieve the Person object
        includes the expected primary key value and that no unnecessary additional queries are made.

        It ensures that the database interaction is optimized and efficient for this specific use case.
        """
        with CaptureQueriesContext(connection) as captured_queries:
            Person.objects.get(pk=self.person_pk)
            self.assertEqual(len(captured_queries), 1)
            self.assertIn(self.person_pk, captured_queries[0]["sql"])

    def test_nested(self):
        with CaptureQueriesContext(connection) as captured_queries:
            Person.objects.count()
            with CaptureQueriesContext(connection) as nested_captured_queries:
                Person.objects.count()
        self.assertEqual(1, len(nested_captured_queries))
        self.assertEqual(2, len(captured_queries))

    def test_failure(self):
        """
        Tests that a TypeError is raised when an exception occurs within a CaptureQueriesContext.

        This test case verifies that the expected TypeError exception is propagated when an error happens 
        within the context, ensuring proper error handling and propagation. The test is designed to validate 
        the behavior of the CaptureQueriesContext when dealing with exceptions, providing confidence in its 
        ability to handle TypeErrors correctly.
        """
        with self.assertRaises(TypeError):
            with CaptureQueriesContext(connection):
                raise TypeError

    def test_with_client(self):
        """

        Tests the number of database queries executed when retrieving a person via the client.

        This test case verifies that the correct number of queries are captured when making 
        GET requests to the '/test_utils/get_person/<pk>/' endpoint. It checks the queries 
        executed for a single request, as well as for consecutive requests.

        The test asserts that the query count is as expected and that the person's primary 
        key is present in the SQL of the captured queries.

        """
        with CaptureQueriesContext(connection) as captured_queries:
            self.client.get("/test_utils/get_person/%s/" % self.person_pk)
        self.assertEqual(len(captured_queries), 1)
        self.assertIn(self.person_pk, captured_queries[0]["sql"])

        with CaptureQueriesContext(connection) as captured_queries:
            self.client.get("/test_utils/get_person/%s/" % self.person_pk)
        self.assertEqual(len(captured_queries), 1)
        self.assertIn(self.person_pk, captured_queries[0]["sql"])

        with CaptureQueriesContext(connection) as captured_queries:
            self.client.get("/test_utils/get_person/%s/" % self.person_pk)
            self.client.get("/test_utils/get_person/%s/" % self.person_pk)
        self.assertEqual(len(captured_queries), 2)
        self.assertIn(self.person_pk, captured_queries[0]["sql"])
        self.assertIn(self.person_pk, captured_queries[1]["sql"])


@override_settings(ROOT_URLCONF="test_utils.urls")
class AssertNumQueriesContextManagerTests(TestCase):
    def test_simple(self):
        with self.assertNumQueries(0):
            pass

        with self.assertNumQueries(1):
            Person.objects.count()

        with self.assertNumQueries(2):
            Person.objects.count()
            Person.objects.count()

    def test_failure(self):
        msg = "1 != 2 : 1 queries executed, 2 expected\nCaptured queries were:\n1."
        with self.assertRaisesMessage(AssertionError, msg):
            with self.assertNumQueries(2):
                Person.objects.count()

        with self.assertRaises(TypeError):
            with self.assertNumQueries(4000):
                raise TypeError

    def test_with_client(self):
        person = Person.objects.create(name="test")

        with self.assertNumQueries(1):
            self.client.get("/test_utils/get_person/%s/" % person.pk)

        with self.assertNumQueries(1):
            self.client.get("/test_utils/get_person/%s/" % person.pk)

        with self.assertNumQueries(2):
            self.client.get("/test_utils/get_person/%s/" % person.pk)
            self.client.get("/test_utils/get_person/%s/" % person.pk)


@override_settings(ROOT_URLCONF="test_utils.urls")
class AssertTemplateUsedContextManagerTests(SimpleTestCase):
    def test_usage(self):
        """

        Tests the usage of template rendering to ensure that the correct templates are being used.

        This test case covers various scenarios where the 'template_used/base.html' template is expected to be rendered.
        It verifies that the template is used when rendering directly, as well as when included or extended by other templates.
        The test also checks that multiple renders of the same template are correctly handled.

        The test uses the Django test client's `assertTemplateUsed` context manager to verify that the expected template is used.

        """
        with self.assertTemplateUsed("template_used/base.html"):
            render_to_string("template_used/base.html")

        with self.assertTemplateUsed(template_name="template_used/base.html"):
            render_to_string("template_used/base.html")

        with self.assertTemplateUsed("template_used/base.html"):
            render_to_string("template_used/include.html")

        with self.assertTemplateUsed("template_used/base.html"):
            render_to_string("template_used/extends.html")

        with self.assertTemplateUsed("template_used/base.html"):
            render_to_string("template_used/base.html")
            render_to_string("template_used/base.html")

    def test_nested_usage(self):
        with self.assertTemplateUsed("template_used/base.html"):
            with self.assertTemplateUsed("template_used/include.html"):
                render_to_string("template_used/include.html")

        with self.assertTemplateUsed("template_used/extends.html"):
            with self.assertTemplateUsed("template_used/base.html"):
                render_to_string("template_used/extends.html")

        with self.assertTemplateUsed("template_used/base.html"):
            with self.assertTemplateUsed("template_used/alternative.html"):
                render_to_string("template_used/alternative.html")
            render_to_string("template_used/base.html")

        with self.assertTemplateUsed("template_used/base.html"):
            render_to_string("template_used/extends.html")
            with self.assertTemplateNotUsed("template_used/base.html"):
                render_to_string("template_used/alternative.html")
            render_to_string("template_used/base.html")

    def test_not_used(self):
        """

        Tests that specific templates are not used during the execution of the test.

        This test verifies that the 'template_used/base.html' and 'template_used/alternative.html' templates are not rendered or loaded. 
        It is useful for ensuring that the correct templates are being used in different scenarios, and for catching unexpected template usage.

        """
        with self.assertTemplateNotUsed("template_used/base.html"):
            pass
        with self.assertTemplateNotUsed("template_used/alternative.html"):
            pass

    def test_error_message(self):
        msg = "No templates used to render the response"
        with self.assertRaisesMessage(AssertionError, msg):
            with self.assertTemplateUsed("template_used/base.html"):
                pass

        with self.assertRaisesMessage(AssertionError, msg):
            with self.assertTemplateUsed(template_name="template_used/base.html"):
                pass

        msg2 = (
            "Template 'template_used/base.html' was not a template used to render "
            "the response. Actual template(s) used: template_used/alternative.html"
        )
        with self.assertRaisesMessage(AssertionError, msg2):
            with self.assertTemplateUsed("template_used/base.html"):
                render_to_string("template_used/alternative.html")

        msg = "No templates used to render the response"
        with self.assertRaisesMessage(AssertionError, msg):
            response = self.client.get("/test_utils/no_template_used/")
            self.assertTemplateUsed(response, "template_used/base.html")

        with self.assertRaisesMessage(AssertionError, msg):
            with self.assertTemplateUsed("template_used/base.html"):
                self.client.get("/test_utils/no_template_used/")

        with self.assertRaisesMessage(AssertionError, msg):
            with self.assertTemplateUsed("template_used/base.html"):
                template = Template("template_used/alternative.html", name=None)
                template.render(Context())

    def test_msg_prefix(self):
        """
        Tests the behavior of assertTemplateUsed when a custom message prefix is provided.

        This function checks that the custom prefix is correctly included in the error message raised when the expected template is not used to render the response.

        It covers various scenarios, including when no templates are used and when a different template is used than the one expected.

        The purpose of this test is to ensure that the custom message prefix is properly propagated to the error message, making it easier to identify the source of the error when the assertion fails.
        """
        msg_prefix = "Prefix"
        msg = f"{msg_prefix}: No templates used to render the response"
        with self.assertRaisesMessage(AssertionError, msg):
            with self.assertTemplateUsed(
                "template_used/base.html", msg_prefix=msg_prefix
            ):
                pass

        with self.assertRaisesMessage(AssertionError, msg):
            with self.assertTemplateUsed(
                template_name="template_used/base.html",
                msg_prefix=msg_prefix,
            ):
                pass

        msg = (
            f"{msg_prefix}: Template 'template_used/base.html' was not a "
            f"template used to render the response. Actual template(s) used: "
            f"template_used/alternative.html"
        )
        with self.assertRaisesMessage(AssertionError, msg):
            with self.assertTemplateUsed(
                "template_used/base.html", msg_prefix=msg_prefix
            ):
                render_to_string("template_used/alternative.html")

    def test_count(self):
        with self.assertTemplateUsed("template_used/base.html", count=2):
            render_to_string("template_used/base.html")
            render_to_string("template_used/base.html")

        msg = (
            "Template 'template_used/base.html' was expected to be rendered "
            "3 time(s) but was actually rendered 2 time(s)."
        )
        with self.assertRaisesMessage(AssertionError, msg):
            with self.assertTemplateUsed("template_used/base.html", count=3):
                render_to_string("template_used/base.html")
                render_to_string("template_used/base.html")

    def test_failure(self):
        msg = "response and/or template_name argument must be provided"
        with self.assertRaisesMessage(TypeError, msg):
            with self.assertTemplateUsed():
                pass

        msg = "No templates used to render the response"
        with self.assertRaisesMessage(AssertionError, msg):
            with self.assertTemplateUsed(""):
                pass

        with self.assertRaisesMessage(AssertionError, msg):
            with self.assertTemplateUsed(""):
                render_to_string("template_used/base.html")

        with self.assertRaisesMessage(AssertionError, msg):
            with self.assertTemplateUsed(template_name=""):
                pass

        msg = (
            "Template 'template_used/base.html' was not a template used to "
            "render the response. Actual template(s) used: "
            "template_used/alternative.html"
        )
        with self.assertRaisesMessage(AssertionError, msg):
            with self.assertTemplateUsed("template_used/base.html"):
                render_to_string("template_used/alternative.html")

    def test_assert_used_on_http_response(self):
        """

        Tests that asserting template usage raises an error when used on an HttpResponse object not fetched via the Django test Client.

        This test check includes two assertions: one for ensuring a template is used and another for ensuring a template is not used.
        The test verifies that attempting to use these assertions on an HttpResponse object not obtained through the test Client results in a ValueError.

        """
        response = HttpResponse()
        msg = "%s() is only usable on responses fetched using the Django test Client."
        with self.assertRaisesMessage(ValueError, msg % "assertTemplateUsed"):
            self.assertTemplateUsed(response, "template.html")
        with self.assertRaisesMessage(ValueError, msg % "assertTemplateNotUsed"):
            self.assertTemplateNotUsed(response, "template.html")


class HTMLEqualTests(SimpleTestCase):
    def test_html_parser(self):
        element = parse_html("<div><p>Hello</p></div>")
        self.assertEqual(len(element.children), 1)
        self.assertEqual(element.children[0].name, "p")
        self.assertEqual(element.children[0].children[0], "Hello")

        parse_html("<p>")
        parse_html("<p attr>")
        dom = parse_html("<p>foo")
        self.assertEqual(len(dom.children), 1)
        self.assertEqual(dom.name, "p")
        self.assertEqual(dom[0], "foo")

    def test_parse_html_in_script(self):
        """
        Tests the parse_html function's ability to handle HTML tags within script tags.

        This test case evaluates how the function interprets HTML code embedded within script tags,
        checking its capacity to correctly parse such constructs, including cases where HTML tags
        are broken across string concatenation operations in JavaScript.

        The function is expected to generate a correct DOM representation of the input HTML,
        where the HTML within the script tags is treated as literal content rather than executable code.

        It verifies that the parsed DOM structure reflects the original input, maintaining the integrity
        of the HTML tags and their content within the script tags, regardless of how they are structured
        or concatenated in the JavaScript code.
        """
        parse_html('<script>var a = "<p" + ">";</script>')
        parse_html(
            """
            <script>
            var js_sha_link='<p>***</p>';
            </script>
        """
        )

        # script content will be parsed to text
        dom = parse_html(
            """
            <script><p>foo</p> '</scr'+'ipt>' <span>bar</span></script>
        """
        )
        self.assertEqual(len(dom.children), 1)
        self.assertEqual(dom.children[0], "<p>foo</p> '</scr'+'ipt>' <span>bar</span>")

    def test_void_elements(self):
        """

        Test that HTML void elements are correctly parsed and represented in the DOM.

        This test checks that void elements, which are HTML elements that do not have a closing tag,
        are handled properly when they appear in HTML documents. It verifies that the elements are
        recognized and positioned correctly within the DOM, regardless of whether they are self-closed
        or not.

        The test covers a range of void elements, ensuring that the parsing behavior is consistent
        across different types of void elements.

        """
        for tag in VOID_ELEMENTS:
            with self.subTest(tag):
                dom = parse_html("<p>Hello <%s> world</p>" % tag)
                self.assertEqual(len(dom.children), 3)
                self.assertEqual(dom[0], "Hello")
                self.assertEqual(dom[1].name, tag)
                self.assertEqual(dom[2], "world")

                dom = parse_html("<p>Hello <%s /> world</p>" % tag)
                self.assertEqual(len(dom.children), 3)
                self.assertEqual(dom[0], "Hello")
                self.assertEqual(dom[1].name, tag)
                self.assertEqual(dom[2], "world")

    def test_simple_equal_html(self):
        """
        Tests whether two HTML strings are equal, ignoring differences in whitespace and tag formatting.

        This test case covers various scenarios, including:

        * Empty HTML strings
        * HTML strings with varying amounts of whitespace
        * HTML strings with different newline characters
        * HTML strings with self-closing tags
        * HTML strings with boolean attributes
        * HTML strings with different tag formatting

        The test asserts that the two input HTML strings are considered equal, even if they have different representations, as long as their structure and content are the same.
        """
        self.assertHTMLEqual("", "")
        self.assertHTMLEqual("<p></p>", "<p></p>")
        self.assertHTMLEqual("<p></p>", " <p> </p> ")
        self.assertHTMLEqual("<div><p>Hello</p></div>", "<div><p>Hello</p></div>")
        self.assertHTMLEqual("<div><p>Hello</p></div>", "<div> <p>Hello</p> </div>")
        self.assertHTMLEqual("<div>\n<p>Hello</p></div>", "<div><p>Hello</p></div>\n")
        self.assertHTMLEqual(
            "<div><p>Hello\nWorld !</p></div>", "<div><p>Hello World\n!</p></div>"
        )
        self.assertHTMLEqual(
            "<div><p>Hello\nWorld !</p></div>", "<div><p>Hello World\n!</p></div>"
        )
        self.assertHTMLEqual("<p>Hello  World   !</p>", "<p>Hello World\n\n!</p>")
        self.assertHTMLEqual("<p> </p>", "<p></p>")
        self.assertHTMLEqual("<p/>", "<p></p>")
        self.assertHTMLEqual("<p />", "<p></p>")
        self.assertHTMLEqual("<input checked>", '<input checked="checked">')
        self.assertHTMLEqual("<p>Hello", "<p> Hello")
        self.assertHTMLEqual("<p>Hello</p>World", "<p>Hello</p> World")

    def test_ignore_comments(self):
        self.assertHTMLEqual(
            "<div>Hello<!-- this is a comment --> World!</div>",
            "<div>Hello World!</div>",
        )

    def test_unequal_html(self):
        self.assertHTMLNotEqual("<p>Hello</p>", "<p>Hello!</p>")
        self.assertHTMLNotEqual("<p>foo&#20;bar</p>", "<p>foo&nbsp;bar</p>")
        self.assertHTMLNotEqual("<p>foo bar</p>", "<p>foo &nbsp;bar</p>")
        self.assertHTMLNotEqual("<p>foo nbsp</p>", "<p>foo &nbsp;</p>")
        self.assertHTMLNotEqual("<p>foo #20</p>", "<p>foo &#20;</p>")
        self.assertHTMLNotEqual(
            "<p><span>Hello</span><span>World</span></p>",
            "<p><span>Hello</span>World</p>",
        )
        self.assertHTMLNotEqual(
            "<p><span>Hello</span>World</p>",
            "<p><span>Hello</span><span>World</span></p>",
        )

    def test_attributes(self):
        self.assertHTMLEqual(
            '<input type="text" id="id_name" />', '<input id="id_name" type="text" />'
        )
        self.assertHTMLEqual(
            """<input type='text' id="id_name" />""",
            '<input id="id_name" type="text" />',
        )
        self.assertHTMLNotEqual(
            '<input type="text" id="id_name" />',
            '<input type="password" id="id_name" />',
        )

    def test_class_attribute(self):
        """

        Tests whether the order and formatting of class attributes in HTML elements are ignored during comparison.

        This function verifies that HTML elements with the same class attributes, 
        but different ordering or whitespace, are considered equal.
        It covers various scenarios, including different types of whitespace characters and extra spaces.
        The goal is to ensure that the comparison of HTML elements is robust and reliable, 
        regardless of the specific formatting used in the class attributes.

        """
        pairs = [
            ('<p class="foo bar"></p>', '<p class="bar foo"></p>'),
            ('<p class=" foo bar "></p>', '<p class="bar foo"></p>'),
            ('<p class="   foo    bar    "></p>', '<p class="bar foo"></p>'),
            ('<p class="foo\tbar"></p>', '<p class="bar foo"></p>'),
            ('<p class="\tfoo\tbar\t"></p>', '<p class="bar foo"></p>'),
            ('<p class="\t\t\tfoo\t\t\tbar\t\t\t"></p>', '<p class="bar foo"></p>'),
            ('<p class="\t \nfoo \t\nbar\n\t "></p>', '<p class="bar foo"></p>'),
        ]
        for html1, html2 in pairs:
            with self.subTest(html1):
                self.assertHTMLEqual(html1, html2)

    def test_boolean_attribute(self):
        """
        Tests the parsing and comparison of HTML input elements with a boolean attribute.

        This test case checks that different representations of a boolean attribute (e.g. \"checked\") 
        are parsed and compared correctly. It verifies that the attribute is handled consistently 
        regardless of whether it is specified with or without a value, and that an invalid value 
        is treated as distinct from the valid forms. The test also ensures that the parsed HTML 
        is correctly serialized back to its original string representation.
        """
        html1 = "<input checked>"
        html2 = '<input checked="">'
        html3 = '<input checked="checked">'
        self.assertHTMLEqual(html1, html2)
        self.assertHTMLEqual(html1, html3)
        self.assertHTMLEqual(html2, html3)
        self.assertHTMLNotEqual(html1, '<input checked="invalid">')
        self.assertEqual(str(parse_html(html1)), "<input checked>")
        self.assertEqual(str(parse_html(html2)), "<input checked>")
        self.assertEqual(str(parse_html(html3)), "<input checked>")

    def test_non_boolean_attibutes(self):
        html1 = "<input value>"
        html2 = '<input value="">'
        html3 = '<input value="value">'
        self.assertHTMLEqual(html1, html2)
        self.assertHTMLNotEqual(html1, html3)
        self.assertEqual(str(parse_html(html1)), '<input value="">')
        self.assertEqual(str(parse_html(html2)), '<input value="">')

    def test_normalize_refs(self):
        """

        Checks if HTML entities for single quote and ampersand are properly normalized.

        This test ensures that various representations of single quote and ampersand HTML entities
        are correctly converted to their standard forms, verifying if the function treats different
        notations as equivalent.

        The function tests multiple pairs of HTML entities to confirm that the normalization
        process correctly handles various input formats, including both named and numeric character references.

        """
        pairs = [
            ("&#39;", "&#x27;"),
            ("&#39;", "'"),
            ("&#x27;", "&#39;"),
            ("&#x27;", "'"),
            ("'", "&#39;"),
            ("'", "&#x27;"),
            ("&amp;", "&#38;"),
            ("&amp;", "&#x26;"),
            ("&amp;", "&"),
            ("&#38;", "&amp;"),
            ("&#38;", "&#x26;"),
            ("&#38;", "&"),
            ("&#x26;", "&amp;"),
            ("&#x26;", "&#38;"),
            ("&#x26;", "&"),
            ("&", "&amp;"),
            ("&", "&#38;"),
            ("&", "&#x26;"),
        ]
        for pair in pairs:
            with self.subTest(repr(pair)):
                self.assertHTMLEqual(*pair)

    def test_complex_examples(self):
        """
        Tests complex examples of HTML output and parsing, verifying that the generated HTML matches the expected output.
        The function covers two main test cases: 
        1. A table with form fields, including first name, last name, and birthday, ensuring that labels, input fields, and table structure are correctly rendered.
        2. An HTML document with a paragraph and a div, verifying that the parser correctly handles invalid HTML (e.g., a div inside a paragraph) by comparing the output to a version with the paragraph tag closed before the div.
        The test asserts that the actual HTML output is equal to the expected output in both cases.
        """
        self.assertHTMLEqual(
            """<tr><th><label for="id_first_name">First name:</label></th>
<td><input type="text" name="first_name" value="John" id="id_first_name" /></td></tr>
<tr><th><label for="id_last_name">Last name:</label></th>
<td><input type="text" id="id_last_name" name="last_name" value="Lennon" /></td></tr>
<tr><th><label for="id_birthday">Birthday:</label></th>
<td><input type="text" value="1940-10-9" name="birthday" id="id_birthday" /></td></tr>""",  # NOQA
            """
        <tr><th>
            <label for="id_first_name">First name:</label></th><td>
            <input type="text" name="first_name" value="John" id="id_first_name" />
        </td></tr>
        <tr><th>
            <label for="id_last_name">Last name:</label></th><td>
            <input type="text" name="last_name" value="Lennon" id="id_last_name" />
        </td></tr>
        <tr><th>
            <label for="id_birthday">Birthday:</label></th><td>
            <input type="text" name="birthday" value="1940-10-9" id="id_birthday" />
        </td></tr>
        """,
        )

        self.assertHTMLEqual(
            """<!DOCTYPE html>
        <html>
        <head>
            <link rel="stylesheet">
            <title>Document</title>
            <meta attribute="value">
        </head>
        <body>
            <p>
            This is a valid paragraph
            <div> this is a div AFTER the p</div>
        </body>
        </html>""",
            """
        <html>
        <head>
            <link rel="stylesheet">
            <title>Document</title>
            <meta attribute="value">
        </head>
        <body>
            <p> This is a valid paragraph
            <!-- browsers would close the p tag here -->
            <div> this is a div AFTER the p</div>
            </p> <!-- this is invalid HTML parsing, but it should make no
            difference in most cases -->
        </body>
        </html>""",
        )

    def test_html_contain(self):
        # equal html contains each other
        """

        Tests whether an HTML string contains another HTML string.

        This function checks for the presence of a given HTML string within another,
        regardless of the surrounding structure. The containment check is performed
        on the parsed HTML documents (DOMs) rather than the raw HTML strings.

        The function covers various scenarios, including:

        *   Containment within the same tag structure
        *   Containment within a more complex tag structure (e.g., a paragraph within a div)
        *   Presence of the contained HTML string within a larger document
        *   Non-containment of a more complex structure within a simpler one

        The tests verify that the containment check correctly identifies the presence
        or absence of the contained HTML string, and that it does so regardless of the
        specific tag structure or surrounding content.

        """
        dom1 = parse_html("<p>foo")
        dom2 = parse_html("<p>foo</p>")
        self.assertIn(dom1, dom2)
        self.assertIn(dom2, dom1)

        dom2 = parse_html("<div><p>foo</p></div>")
        self.assertIn(dom1, dom2)
        self.assertNotIn(dom2, dom1)

        self.assertNotIn("<p>foo</p>", dom2)
        self.assertIn("foo", dom2)

        # when a root element is used ...
        dom1 = parse_html("<p>foo</p><p>bar</p>")
        dom2 = parse_html("<p>foo</p><p>bar</p>")
        self.assertIn(dom1, dom2)
        dom1 = parse_html("<p>foo</p>")
        self.assertIn(dom1, dom2)
        dom1 = parse_html("<p>bar</p>")
        self.assertIn(dom1, dom2)
        dom1 = parse_html("<div><p>foo</p><p>bar</p></div>")
        self.assertIn(dom2, dom1)

    def test_count(self):
        # equal html contains each other one time
        dom1 = parse_html("<p>foo")
        dom2 = parse_html("<p>foo</p>")
        self.assertEqual(dom1.count(dom2), 1)
        self.assertEqual(dom2.count(dom1), 1)

        dom2 = parse_html("<p>foo</p><p>bar</p>")
        self.assertEqual(dom2.count(dom1), 1)

        dom2 = parse_html("<p>foo foo</p><p>foo</p>")
        self.assertEqual(dom2.count("foo"), 3)

        dom2 = parse_html('<p class="bar">foo</p>')
        self.assertEqual(dom2.count("bar"), 0)
        self.assertEqual(dom2.count("class"), 0)
        self.assertEqual(dom2.count("p"), 0)
        self.assertEqual(dom2.count("o"), 2)

        dom2 = parse_html("<p>foo</p><p>foo</p>")
        self.assertEqual(dom2.count(dom1), 2)

        dom2 = parse_html('<div><p>foo<input type=""></p><p>foo</p></div>')
        self.assertEqual(dom2.count(dom1), 1)

        dom2 = parse_html("<div><div><p>foo</p></div></div>")
        self.assertEqual(dom2.count(dom1), 1)

        dom2 = parse_html("<p>foo<p>foo</p></p>")
        self.assertEqual(dom2.count(dom1), 1)

        dom2 = parse_html("<p>foo<p>bar</p></p>")
        self.assertEqual(dom2.count(dom1), 0)

        # HTML with a root element contains the same HTML with no root element.
        dom1 = parse_html("<p>foo</p><p>bar</p>")
        dom2 = parse_html("<div><p>foo</p><p>bar</p></div>")
        self.assertEqual(dom2.count(dom1), 1)

        # Target of search is a sequence of child elements and appears more
        # than once.
        dom2 = parse_html("<div><p>foo</p><p>bar</p><p>foo</p><p>bar</p></div>")
        self.assertEqual(dom2.count(dom1), 2)

        # Searched HTML has additional children.
        dom1 = parse_html("<a/><b/>")
        dom2 = parse_html("<a/><b/><c/>")
        self.assertEqual(dom2.count(dom1), 1)

        # No match found in children.
        dom1 = parse_html("<b/><a/>")
        self.assertEqual(dom2.count(dom1), 0)

        # Target of search found among children and grandchildren.
        dom1 = parse_html("<b/><b/>")
        dom2 = parse_html("<a><b/><b/></a><b/><b/>")
        self.assertEqual(dom2.count(dom1), 2)

    def test_root_element_escaped_html(self):
        """
        Tests that the root element of parsed HTML is properly escaped.

        This test case verifies that HTML content containing escaped elements (e.g. &lt;, &gt;) 
        is correctly parsed and preserved in its original form, without any modifications or 
        interpretations of the escape sequences. The goal is to ensure that the parsed output 
        matches the original input HTML string, even when it contains escaped HTML characters.
        """
        html = "&lt;br&gt;"
        parsed = parse_html(html)
        self.assertEqual(str(parsed), html)

    def test_parsing_errors(self):
        with self.assertRaises(AssertionError):
            self.assertHTMLEqual("<p>", "")
        with self.assertRaises(AssertionError):
            self.assertHTMLEqual("", "<p>")
        error_msg = (
            "First argument is not valid HTML:\n"
            "('Unexpected end tag `div` (Line 1, Column 6)', (1, 6))"
        )
        with self.assertRaisesMessage(AssertionError, error_msg):
            self.assertHTMLEqual("< div></ div>", "<div></div>")
        with self.assertRaises(HTMLParseError):
            parse_html("</p>")

    def test_escaped_html_errors(self):
        msg = "<p>\n<foo>\n</p> != <p>\n&lt;foo&gt;\n</p>\n"
        with self.assertRaisesMessage(AssertionError, msg):
            self.assertHTMLEqual("<p><foo></p>", "<p>&lt;foo&gt;</p>")
        with self.assertRaisesMessage(AssertionError, msg):
            self.assertHTMLEqual("<p><foo></p>", "<p>&#60;foo&#62;</p>")

    def test_contains_html(self):
        """

        Tests that the assertContains and assertNotContains methods correctly check 
        for the presence or absence of HTML content in an HttpResponse.

        This function verifies that the methods can handle HTML content both as 
        plain text and as parsed HTML, ensuring that different comparison methods 
        produce the expected outcomes.

        It also includes negative test cases to validate that the methods raise an 
        AssertionError when given malformed or invalid HTML responses, or when 
        attempting to match invalid or non-existent content.

        """
        response = HttpResponse(
            """<body>
        This is a form: <form method="get">
            <input type="text" name="Hello" />
        </form></body>"""
        )

        self.assertNotContains(response, "<input name='Hello' type='text'>")
        self.assertContains(response, '<form method="get">')

        self.assertContains(response, "<input name='Hello' type='text'>", html=True)
        self.assertNotContains(response, '<form method="get">', html=True)

        invalid_response = HttpResponse("""<body <bad>>""")

        with self.assertRaises(AssertionError):
            self.assertContains(invalid_response, "<p></p>")

        with self.assertRaises(AssertionError):
            self.assertContains(response, '<p "whats" that>')

    def test_unicode_handling(self):
        response = HttpResponse(
            '<p class="help">Some help text for the title (with Unicode ŠĐĆŽćžšđ)</p>'
        )
        self.assertContains(
            response,
            '<p class="help">Some help text for the title (with Unicode ŠĐĆŽćžšđ)</p>',
            html=True,
        )


class InHTMLTests(SimpleTestCase):
    def test_needle_msg(self):
        msg = (
            "False is not true : Couldn't find '<b>Hello</b>' in the following "
            "response\n'<p>Test</p>'"
        )
        with self.assertRaisesMessage(AssertionError, msg):
            self.assertInHTML("<b>Hello</b>", "<p>Test</p>")

    def test_msg_prefix(self):
        """
        Tests that an AssertionError is raised with a custom message prefix when the 'assertInHTML' method fails to find an HTML element.

        The test checks that the error message includes the specified prefix, the expected HTML element, and the actual HTML response where the element was not found.

        :raises AssertionError: When the expected HTML element is not found in the actual HTML response
        """
        msg = (
            "False is not true : Prefix: Couldn't find '<b>Hello</b>' in the following "
            'response\n\'<input type="text" name="Hello" />\''
        )
        with self.assertRaisesMessage(AssertionError, msg):
            self.assertInHTML(
                "<b>Hello</b>",
                '<input type="text" name="Hello" />',
                msg_prefix="Prefix",
            )

    def test_count_msg_prefix(self):
        """
        Tests the functionality of a method when it counts HTML occurrences with a custom message prefix.

        This test case checks if the method correctly asserts an error when the actual count does not match the expected count and if the custom message prefix is correctly included in the error message.

        The function verifies that the error message contains the specified prefix, allowing for more informative and targeted error reporting in case of assertion failures.

        The test covers a scenario where the expected count is 1, but the actual count is 2, demonstrating the handling of mismatched counts and the inclusion of the provided message prefix in the resulting error message.
        """
        msg = (
            "2 != 1 : Prefix: Found 2 instances of '<b>Hello</b>' (expected 1) in the "
            "following response\n'<b>Hello</b><b>Hello</b>'"
            ""
        )
        with self.assertRaisesMessage(AssertionError, msg):
            self.assertInHTML(
                "<b>Hello</b>",
                "<b>Hello</b><b>Hello</b>",
                count=1,
                msg_prefix="Prefix",
            )

    def test_base(self):
        """

        Tests if substrings can be correctly found within a larger HTML string.

        This function checks for the presence of specific HTML elements within a given
        haystack string, verifying both their existence and count. It also tests that
        the function correctly raises an AssertionError when the expected HTML element
        is not found or when the count of the element does not match the expected value.

        """
        haystack = "<p><b>Hello</b> <span>there</span>! Hi <span>there</span>!</p>"

        self.assertInHTML("<b>Hello</b>", haystack=haystack)
        msg = f"Couldn't find '<p>Howdy</p>' in the following response\n{haystack!r}"
        with self.assertRaisesMessage(AssertionError, msg):
            self.assertInHTML("<p>Howdy</p>", haystack)

        self.assertInHTML("<span>there</span>", haystack=haystack, count=2)
        msg = (
            "Found 1 instances of '<b>Hello</b>' (expected 2) in the following response"
            f"\n{haystack!r}"
        )
        with self.assertRaisesMessage(AssertionError, msg):
            self.assertInHTML("<b>Hello</b>", haystack=haystack, count=2)

    def test_long_haystack(self):
        """

        Tests the behavior of assertInHTML when the haystack is extremely long and exceeds the truncation limit.

        This test case verifies that an AssertionError is raised when the expected HTML is not found in the long haystack,
        and another AssertionError is raised when the expected HTML is found but the count of occurrences does not match the expected count.

        """
        haystack = (
            "<p>This is a very very very very very very very very long message which "
            "exceedes the max limit of truncation.</p>"
        )
        msg = f"Couldn't find '<b>Hello</b>' in the following response\n{haystack!r}"
        with self.assertRaisesMessage(AssertionError, msg):
            self.assertInHTML("<b>Hello</b>", haystack)

        msg = (
            "Found 0 instances of '<b>This</b>' (expected 3) in the following response"
            f"\n{haystack!r}"
        )
        with self.assertRaisesMessage(AssertionError, msg):
            self.assertInHTML("<b>This</b>", haystack, 3)

    def test_assert_not_in_html(self):
        """
        Tests that the :meth:`assertNotInHTML` method correctly checks if a given HTML snippet is not present in a larger HTML string.

        This method verifies that the assertion is triggered when the snippet is found, and that it is not triggered when the snippet is not found. The error message raised by the assertion includes the original HTML string for debugging purposes.

        The method covers two main scenarios: 
        - A successful assertion where the HTML snippet is not found in the given HTML string, and 
        - A failed assertion where the HTML snippet is found, verifying that the correct error message is raised.

        """
        haystack = "<p><b>Hello</b> <span>there</span>! Hi <span>there</span>!</p>"
        self.assertNotInHTML("<b>Hi</b>", haystack=haystack)
        msg = (
            "'<b>Hello</b>' unexpectedly found in the following response"
            f"\n{haystack!r}"
        )
        with self.assertRaisesMessage(AssertionError, msg):
            self.assertNotInHTML("<b>Hello</b>", haystack=haystack)


class JSONEqualTests(SimpleTestCase):
    def test_simple_equal(self):
        """
        Tests that two identical JSON strings are considered equal.

        This test case checks if the :meth:`assertJSONEqual` method correctly identifies
        two JSON strings as equal when they contain the same attributes and values.
        The test uses a simple JSON object with two attributes to verify the functionality.

        """
        json1 = '{"attr1": "foo", "attr2":"baz"}'
        json2 = '{"attr1": "foo", "attr2":"baz"}'
        self.assertJSONEqual(json1, json2)

    def test_simple_equal_unordered(self):
        json1 = '{"attr1": "foo", "attr2":"baz"}'
        json2 = '{"attr2":"baz", "attr1": "foo"}'
        self.assertJSONEqual(json1, json2)

    def test_simple_equal_raise(self):
        """
        Tests that assertJSONEqual raises an AssertionError when comparing two JSON objects that are not equal.

        This test case verifies that the function correctly identifies when two JSON objects do not have the same attributes, 
        even if they have some attributes in common. The test expects an AssertionError to be raised when comparing the 
        two JSON objects, one with an additional attribute, to ensure the function's error handling behaves as expected.
        """
        json1 = '{"attr1": "foo", "attr2":"baz"}'
        json2 = '{"attr2":"baz"}'
        with self.assertRaises(AssertionError):
            self.assertJSONEqual(json1, json2)

    def test_equal_parsing_errors(self):
        """
        Tests that the assertJSONEqual method correctly raises an AssertionError when comparing JSON strings with and without parsing errors.

        The test case checks two scenarios: 
        1. When the first JSON string has a parsing error and the second is valid.
        2. When the first JSON string is valid and the second has a parsing error.

        This test ensures that the assertJSONEqual method behaves as expected in cases where one or both of the input JSON strings contain syntax errors.
        """
        invalid_json = '{"attr1": "foo, "attr2":"baz"}'
        valid_json = '{"attr1": "foo", "attr2":"baz"}'
        with self.assertRaises(AssertionError):
            self.assertJSONEqual(invalid_json, valid_json)
        with self.assertRaises(AssertionError):
            self.assertJSONEqual(valid_json, invalid_json)

    def test_simple_not_equal(self):
        """

        Tests that two JSON strings are not equal.

        This test case checks if two JSON objects with differing attributes and values 
        are correctly identified as not equal, verifying the functionality of the 
        assertJSONNotEqual method in handling JSON comparisons with varied key sets.

        """
        json1 = '{"attr1": "foo", "attr2":"baz"}'
        json2 = '{"attr2":"baz"}'
        self.assertJSONNotEqual(json1, json2)

    def test_simple_not_equal_raise(self):
        """

        Tests that assertJSONNotEqual raises an AssertionError when comparing two identical JSON strings.

        This function validates the behavior of assertJSONNotEqual in the case where the input JSON strings are equal.
        It ensures that an AssertionError is raised, as expected, when the JSON strings being compared are identical.

        """
        json1 = '{"attr1": "foo", "attr2":"baz"}'
        json2 = '{"attr1": "foo", "attr2":"baz"}'
        with self.assertRaises(AssertionError):
            self.assertJSONNotEqual(json1, json2)

    def test_not_equal_parsing_errors(self):
        invalid_json = '{"attr1": "foo, "attr2":"baz"}'
        valid_json = '{"attr1": "foo", "attr2":"baz"}'
        with self.assertRaises(AssertionError):
            self.assertJSONNotEqual(invalid_json, valid_json)
        with self.assertRaises(AssertionError):
            self.assertJSONNotEqual(valid_json, invalid_json)


class XMLEqualTests(SimpleTestCase):
    def test_simple_equal(self):
        """

        Tests that two simple XML elements with identical attributes are considered equal.

        This test case verifies the functionality of comparing XML elements based on their tag name and attribute values.
        The test checks if the assertXMLEqual method correctly identifies two XML elements as equal when they have the same tag name and attribute key-value pairs.

        """
        xml1 = "<elem attr1='a' attr2='b' />"
        xml2 = "<elem attr1='a' attr2='b' />"
        self.assertXMLEqual(xml1, xml2)

    def test_simple_equal_unordered(self):
        """

        Tests that XML elements are considered equal when their attributes are in a different order.

        This test case verifies that the assertXMLEqual method treats XML elements as equal
        even if the order of their attributes differs, as long as the attribute names and values are the same.

        """
        xml1 = "<elem attr1='a' attr2='b' />"
        xml2 = "<elem attr2='b' attr1='a' />"
        self.assertXMLEqual(xml1, xml2)

    def test_simple_equal_raise(self):
        xml1 = "<elem attr1='a' />"
        xml2 = "<elem attr2='b' attr1='a' />"
        with self.assertRaises(AssertionError):
            self.assertXMLEqual(xml1, xml2)

    def test_simple_equal_raises_message(self):
        xml1 = "<elem attr1='a' />"
        xml2 = "<elem attr2='b' attr1='a' />"

        msg = """{xml1} != {xml2}
- <elem attr1='a' />
+ <elem attr2='b' attr1='a' />
?      ++++++++++
""".format(
            xml1=repr(xml1), xml2=repr(xml2)
        )

        with self.assertRaisesMessage(AssertionError, msg):
            self.assertXMLEqual(xml1, xml2)

    def test_simple_not_equal(self):
        """

        Tests that two XML strings with different attribute values are considered not equal.

        This test case checks the functionality of comparing XML elements when one attribute value differs between the two elements.

        """
        xml1 = "<elem attr1='a' attr2='c' />"
        xml2 = "<elem attr1='a' attr2='b' />"
        self.assertXMLNotEqual(xml1, xml2)

    def test_simple_not_equal_raise(self):
        """

        Checks that the assertXMLNotEqual method raises an AssertionError when comparing two XML strings that are identical except for attribute order.

        This test ensures that the comparison is sensitive to the order of attributes in the XML elements, and does not simply ignore differences in attribute order.

        :raises: AssertionError if the XML strings are considered equal

        """
        xml1 = "<elem attr1='a' attr2='b' />"
        xml2 = "<elem attr2='b' attr1='a' />"
        with self.assertRaises(AssertionError):
            self.assertXMLNotEqual(xml1, xml2)

    def test_parsing_errors(self):
        xml_unvalid = "<elem attr1='a attr2='b' />"
        xml2 = "<elem attr2='b' attr1='a' />"
        with self.assertRaises(AssertionError):
            self.assertXMLNotEqual(xml_unvalid, xml2)

    def test_comment_root(self):
        """
        Tests whether XML comments at the root level are ignored during XML comparison, ensuring that two XML documents are considered equal if they have the same structure and attributes, but differ in their comments.
        """
        xml1 = "<?xml version='1.0'?><!-- comment1 --><elem attr1='a' attr2='b' />"
        xml2 = "<?xml version='1.0'?><!-- comment2 --><elem attr2='b' attr1='a' />"
        self.assertXMLEqual(xml1, xml2)

    def test_simple_equal_with_leading_or_trailing_whitespace(self):
        xml1 = "<elem>foo</elem> \t\n"
        xml2 = " \t\n<elem>foo</elem>"
        self.assertXMLEqual(xml1, xml2)

    def test_simple_not_equal_with_whitespace_in_the_middle(self):
        """
        Tests that two XML strings are not considered equal when whitespace is present between elements in one string but not the other, verifying the functionality of XML comparison with respect to whitespace differences.
        """
        xml1 = "<elem>foo</elem><elem>bar</elem>"
        xml2 = "<elem>foo</elem> <elem>bar</elem>"
        self.assertXMLNotEqual(xml1, xml2)

    def test_doctype_root(self):
        """

        Checks if XML documents with different doctype declarations are considered equal.

        This test verifies that the function being tested ignores the differences in 
        DOCTYPE declarations when comparing two XML documents. It uses two XML strings 
        with the same root element but different external DTD references, and checks 
        that they are reported as identical.

        """
        xml1 = '<?xml version="1.0"?><!DOCTYPE root SYSTEM "example1.dtd"><root />'
        xml2 = '<?xml version="1.0"?><!DOCTYPE root SYSTEM "example2.dtd"><root />'
        self.assertXMLEqual(xml1, xml2)

    def test_processing_instruction(self):
        """

        Tests the processing instruction of XML documents.

        This function checks if two XML documents with different processing instructions 
        are considered equal. It tests the case where the documents have different 
        xml-model processing instructions and the case where they have different 
        xml-stylesheet processing instructions. The test passes if the documents are 
        considered equal despite the differences in the processing instructions.

        """
        xml1 = (
            '<?xml version="1.0"?>'
            '<?xml-model href="http://www.example1.com"?><root />'
        )
        xml2 = (
            '<?xml version="1.0"?>'
            '<?xml-model href="http://www.example2.com"?><root />'
        )
        self.assertXMLEqual(xml1, xml2)
        self.assertXMLEqual(
            '<?xml-stylesheet href="style1.xslt" type="text/xsl"?><root />',
            '<?xml-stylesheet href="style2.xslt" type="text/xsl"?><root />',
        )


class SkippingExtraTests(TestCase):
    fixtures = ["should_not_be_loaded.json"]

    # HACK: This depends on internals of our TestCase subclasses
    def __call__(self, result=None):
        # Detect fixture loading by counting SQL queries, should be zero
        """
        Calls the parent class method while suppressing database query assertions.

        Ensure no database queries are executed when invoking the parent class's
        __call__ method, allowing for silent execution of the parent method. 
        The result of the parent method call is then propagated as per normal 
        invocation rules, with the provided result being optionally passed to 
        the parent class method.

        :param result: The result to be passed to the parent class's __call__ method

        """
        with self.assertNumQueries(0):
            super().__call__(result)

    @unittest.skip("Fixture loading should not be performed for skipped tests.")
    def test_fixtures_are_skipped(self):
        pass


class AssertRaisesMsgTest(SimpleTestCase):
    def test_assert_raises_message(self):
        msg = "'Expected message' not found in 'Unexpected message'"
        # context manager form of assertRaisesMessage()
        with self.assertRaisesMessage(AssertionError, msg):
            with self.assertRaisesMessage(ValueError, "Expected message"):
                raise ValueError("Unexpected message")

        # callable form
        def func():
            raise ValueError("Unexpected message")

        with self.assertRaisesMessage(AssertionError, msg):
            self.assertRaisesMessage(ValueError, "Expected message", func)

    def test_special_re_chars(self):
        """assertRaisesMessage shouldn't interpret RE special chars."""

        def func1():
            raise ValueError("[.*x+]y?")

        with self.assertRaisesMessage(ValueError, "[.*x+]y?"):
            func1()


class AssertWarnsMessageTests(SimpleTestCase):
    def test_context_manager(self):
        with self.assertWarnsMessage(UserWarning, "Expected message"):
            warnings.warn("Expected message", UserWarning)

    def test_context_manager_failure(self):
        """
        Tests that a context manager correctly handles a failure by raising an AssertionError when an expected warning message is not found in the actual warning message raised by the warnings.warn function. The test case checks for a specific expected message and verifies if an AssertionError is raised with the expected error message when an unexpected warning message is encountered.
        """
        msg = "Expected message' not found in 'Unexpected message'"
        with self.assertRaisesMessage(AssertionError, msg):
            with self.assertWarnsMessage(UserWarning, "Expected message"):
                warnings.warn("Unexpected message", UserWarning)

    def test_callable(self):
        """
        Tests if a given callable function triggers a specific warning message.

        This test function takes no arguments and executes an internal function that
        raises a UserWarning with a predefined message. It then asserts that the
        expected warning message is indeed raised.

        The purpose of this test is to verify that the warning system behaves as
        expected, issuing the correct warnings when certain conditions are met.

        :raises AssertionError: If the expected warning message is not raised
        """
        def func():
            warnings.warn("Expected message", UserWarning)

        self.assertWarnsMessage(UserWarning, "Expected message", func)

    def test_special_re_chars(self):
        """

        Tests the handling of special regular expression characters in warning messages.

        Verifies that warning messages containing special regex characters, such as '.', '*', '+', 
        and '?', are correctly issued and matched without causing any issues.

        """
        def func1():
            warnings.warn("[.*x+]y?", UserWarning)

        with self.assertWarnsMessage(UserWarning, "[.*x+]y?"):
            func1()


class AssertFieldOutputTests(SimpleTestCase):
    def test_assert_field_output(self):
        """

        Tests the assertFieldOutput method for validating the output of the EmailField.

        This test case checks that the assertFieldOutput method correctly validates the output of the EmailField.
        It tests the following scenarios:
        - Valid output: The output matches the expected output for valid input.
        - Invalid error message: The output does not match the expected error message for invalid input.
        - Mismatched output: The output does not match the expected output for valid input.
        - Unrecognized error message: The output contains an error message that is not recognized as valid.

        Raises:
            AssertionError: If any of the test scenarios fail. 

        """
        error_invalid = ["Enter a valid email address."]
        self.assertFieldOutput(
            EmailField, {"a@a.com": "a@a.com"}, {"aaa": error_invalid}
        )
        with self.assertRaises(AssertionError):
            self.assertFieldOutput(
                EmailField,
                {"a@a.com": "a@a.com"},
                {"aaa": error_invalid + ["Another error"]},
            )
        with self.assertRaises(AssertionError):
            self.assertFieldOutput(
                EmailField, {"a@a.com": "Wrong output"}, {"aaa": error_invalid}
            )
        with self.assertRaises(AssertionError):
            self.assertFieldOutput(
                EmailField,
                {"a@a.com": "a@a.com"},
                {"aaa": ["Come on, gimme some well formatted data, dude."]},
            )

    def test_custom_required_message(self):
        """
        Test that a custom required message is used when a field is required.

        This test case verifies that a custom error message defined in a field's
        default_error_messages dictionary is displayed when the field is required
        and no value is provided. The test uses a custom IntegerField with a
        custom 'required' error message to validate this behavior.
        """
        class MyCustomField(IntegerField):
            default_error_messages = {
                "required": "This is really required.",
            }

        self.assertFieldOutput(MyCustomField, {}, {}, empty_value=None)


@override_settings(ROOT_URLCONF="test_utils.urls")
class AssertURLEqualTests(SimpleTestCase):
    def test_equal(self):
        valid_tests = (
            ("http://example.com/?", "http://example.com/"),
            ("http://example.com/?x=1&", "http://example.com/?x=1"),
            ("http://example.com/?x=1&y=2", "http://example.com/?y=2&x=1"),
            ("http://example.com/?x=1&y=2", "http://example.com/?y=2&x=1"),
            (
                "http://example.com/?x=1&y=2&a=1&a=2",
                "http://example.com/?a=1&a=2&y=2&x=1",
            ),
            ("/path/to/?x=1&y=2&z=3", "/path/to/?z=3&y=2&x=1"),
            ("?x=1&y=2&z=3", "?z=3&y=2&x=1"),
            ("/test_utils/no_template_used/", reverse_lazy("no_template_used")),
        )
        for url1, url2 in valid_tests:
            with self.subTest(url=url1):
                self.assertURLEqual(url1, url2)

    def test_not_equal(self):
        """

        Tests that the assertURLEqual function correctly raises an AssertionError 
        when comparing two URLs that are not equal.

        The test cases cover various scenarios, including different protocols (http/https), 
        query parameter ordering, and duplicate query parameters.

        """
        invalid_tests = (
            # Protocol must be the same.
            ("http://example.com/", "https://example.com/"),
            ("http://example.com/?x=1&x=2", "https://example.com/?x=2&x=1"),
            ("http://example.com/?x=1&y=bar&x=2", "https://example.com/?y=bar&x=2&x=1"),
            # Parameters of the same name must be in the same order.
            ("/path/to?a=1&a=2", "/path/to/?a=2&a=1"),
        )
        for url1, url2 in invalid_tests:
            with self.subTest(url=url1), self.assertRaises(AssertionError):
                self.assertURLEqual(url1, url2)

    def test_message(self):
        msg = (
            "Expected 'http://example.com/?x=1&x=2' to equal "
            "'https://example.com/?x=2&x=1'"
        )
        with self.assertRaisesMessage(AssertionError, msg):
            self.assertURLEqual(
                "http://example.com/?x=1&x=2", "https://example.com/?x=2&x=1"
            )

    def test_msg_prefix(self):
        msg = (
            "Prefix: Expected 'http://example.com/?x=1&x=2' to equal "
            "'https://example.com/?x=2&x=1'"
        )
        with self.assertRaisesMessage(AssertionError, msg):
            self.assertURLEqual(
                "http://example.com/?x=1&x=2",
                "https://example.com/?x=2&x=1",
                msg_prefix="Prefix",
            )


class TestForm(Form):
    field = CharField()

    def clean_field(self):
        value = self.cleaned_data.get("field", "")
        if value == "invalid":
            raise ValidationError("invalid value")
        return value

    def clean(self):
        if self.cleaned_data.get("field") == "invalid_non_field":
            raise ValidationError("non-field error")
        return self.cleaned_data

    @classmethod
    def _get_cleaned_form(cls, field_value):
        form = cls({"field": field_value})
        form.full_clean()
        return form

    @classmethod
    def valid(cls):
        return cls._get_cleaned_form("valid")

    @classmethod
    def invalid(cls, nonfield=False):
        return cls._get_cleaned_form("invalid_non_field" if nonfield else "invalid")


class TestFormset(formset_factory(TestForm)):
    @classmethod
    def _get_cleaned_formset(cls, field_value):
        formset = cls(
            {
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "0",
                "form-0-field": field_value,
            }
        )
        formset.full_clean()
        return formset

    @classmethod
    def valid(cls):
        return cls._get_cleaned_formset("valid")

    @classmethod
    def invalid(cls, nonfield=False, nonform=False):
        """
        Returns a formset instance in an invalid state.

        This class method creates a formset with specific error conditions, allowing for
        testing and validation of invalid form states. It can be used to test formset
        behavior when a non-field error or a non-form error occurs.

        :param bool nonfield: If True, returns a formset with a non-field error.
        :param bool nonform: If True, returns a formset with a non-form error, specifically
            a missing management form error.

        :return: A formset instance in an invalid state.

        """
        if nonform:
            formset = cls({}, error_messages={"missing_management_form": "error"})
            formset.full_clean()
            return formset
        return cls._get_cleaned_formset("invalid_non_field" if nonfield else "invalid")


class AssertFormErrorTests(SimpleTestCase):
    def test_single_error(self):
        self.assertFormError(TestForm.invalid(), "field", "invalid value")

    def test_error_list(self):
        self.assertFormError(TestForm.invalid(), "field", ["invalid value"])

    def test_empty_errors_valid_form(self):
        self.assertFormError(TestForm.valid(), "field", [])

    def test_empty_errors_valid_form_non_field_errors(self):
        self.assertFormError(TestForm.valid(), None, [])

    def test_field_not_in_form(self):
        """
        Tests that attempting to assert a form error for a field not present in the form raises an AssertionError.

        The function checks that the expected error message is raised when trying to assert an error on a non-existent field in a form.
        It also verifies that the error message can be customized with a prefix.

        Raises:
            AssertionError: If the form error assertion does not raise an AssertionError with the expected message.

        """
        msg = (
            "The form <TestForm bound=True, valid=False, fields=(field)> does not "
            "contain the field 'other_field'."
        )
        with self.assertRaisesMessage(AssertionError, msg):
            self.assertFormError(TestForm.invalid(), "other_field", "invalid value")
        msg_prefix = "Custom prefix"
        with self.assertRaisesMessage(AssertionError, f"{msg_prefix}: {msg}"):
            self.assertFormError(
                TestForm.invalid(),
                "other_field",
                "invalid value",
                msg_prefix=msg_prefix,
            )

    def test_field_with_no_errors(self):
        """

        Tests that the function correctly handles a form field with no errors.

        This test ensures that an AssertionError is raised when attempting to assert that a
        form field has a specific error message when it actually has none. It also checks that
        the error message provided in the assertion matches the expected message, and that
        a custom prefix can be added to the error message.

        The test covers two scenarios: one with the default error message and one with a
        custom prefix. In both cases, it verifies that the raised AssertionError contains
        the expected error message and that the field's errors are correctly compared to the
        expected errors.

        """
        msg = (
            "The errors of field 'field' on form <TestForm bound=True, valid=True, "
            "fields=(field)> don't match."
        )
        with self.assertRaisesMessage(AssertionError, msg) as ctx:
            self.assertFormError(TestForm.valid(), "field", "invalid value")
        self.assertIn("[] != ['invalid value']", str(ctx.exception))
        msg_prefix = "Custom prefix"
        with self.assertRaisesMessage(AssertionError, f"{msg_prefix}: {msg}"):
            self.assertFormError(
                TestForm.valid(), "field", "invalid value", msg_prefix=msg_prefix
            )

    def test_field_with_different_error(self):
        """

        Tests the form error assertion functionality when the error message for a specific field does not match the expected error.

        This test case covers the scenario where the error message of a form field is verified against an expected error message.
        If the error messages do not match, an AssertionError is raised with a message describing the mismatch.

        The test also covers the ability to prefix the error message with a custom string, allowing for more flexible error reporting.

        """
        msg = (
            "The errors of field 'field' on form <TestForm bound=True, valid=False, "
            "fields=(field)> don't match."
        )
        with self.assertRaisesMessage(AssertionError, msg) as ctx:
            self.assertFormError(TestForm.invalid(), "field", "other error")
        self.assertIn("['invalid value'] != ['other error']", str(ctx.exception))
        msg_prefix = "Custom prefix"
        with self.assertRaisesMessage(AssertionError, f"{msg_prefix}: {msg}"):
            self.assertFormError(
                TestForm.invalid(), "field", "other error", msg_prefix=msg_prefix
            )

    def test_unbound_form(self):
        """
        Tests that attempting to assert form errors on an unbound form raises an AssertionError with a descriptive message, 
        indicating that an unbound form will never have any errors. 
        The test also verifies that a custom error message prefix can be provided and is prepended to the standard error message.
        """
        msg = (
            "The form <TestForm bound=False, valid=Unknown, fields=(field)> is not "
            "bound, it will never have any errors."
        )
        with self.assertRaisesMessage(AssertionError, msg):
            self.assertFormError(TestForm(), "field", [])
        msg_prefix = "Custom prefix"
        with self.assertRaisesMessage(AssertionError, f"{msg_prefix}: {msg}"):
            self.assertFormError(TestForm(), "field", [], msg_prefix=msg_prefix)

    def test_empty_errors_invalid_form(self):
        """

        Tests that the assertFormError method correctly raises an AssertionError when the form field's errors do not match the expected errors.

        Checks that the assertion error contains the expected error message, including the name of the field, the form it belongs to, and the expected and actual error values. This test case specifically covers the scenario where the form is invalid and the field has an error, but the expected errors are empty.

        """
        msg = (
            "The errors of field 'field' on form <TestForm bound=True, valid=False, "
            "fields=(field)> don't match."
        )
        with self.assertRaisesMessage(AssertionError, msg) as ctx:
            self.assertFormError(TestForm.invalid(), "field", [])
        self.assertIn("['invalid value'] != []", str(ctx.exception))

    def test_non_field_errors(self):
        self.assertFormError(TestForm.invalid(nonfield=True), None, "non-field error")

    def test_different_non_field_errors(self):
        """

        Test that the non-field errors of a form do not match the expected errors.

        This test case checks that an AssertionError is raised when the non-field errors
        of a form do not match the specified errors. It also verifies that the error
        message contains the correct information about the mismatched errors.

        The test covers two scenarios: one with the default error message and another
        with a custom error message prefix. The test ensures that the custom prefix is
        included in the error message when provided.

        This test is useful for ensuring that form validation is working correctly and
        that errors are being reported as expected.

        """
        msg = (
            "The non-field errors of form <TestForm bound=True, valid=False, "
            "fields=(field)> don't match."
        )
        with self.assertRaisesMessage(AssertionError, msg) as ctx:
            self.assertFormError(
                TestForm.invalid(nonfield=True), None, "other non-field error"
            )
        self.assertIn(
            "['non-field error'] != ['other non-field error']", str(ctx.exception)
        )
        msg_prefix = "Custom prefix"
        with self.assertRaisesMessage(AssertionError, f"{msg_prefix}: {msg}"):
            self.assertFormError(
                TestForm.invalid(nonfield=True),
                None,
                "other non-field error",
                msg_prefix=msg_prefix,
            )


class AssertFormSetErrorTests(SimpleTestCase):
    def test_single_error(self):
        self.assertFormSetError(TestFormset.invalid(), 0, "field", "invalid value")

    def test_error_list(self):
        self.assertFormSetError(TestFormset.invalid(), 0, "field", ["invalid value"])

    def test_empty_errors_valid_formset(self):
        self.assertFormSetError(TestFormset.valid(), 0, "field", [])

    def test_multiple_forms(self):
        """

        Tests the behavior of a formset with multiple forms when validating user input.

        This test checks that the formset correctly identifies and reports validation errors 
        for each individual form in the set. It verifies that a form with valid input does 
        not generate any errors, while a form with invalid input returns the expected error message.

        """
        formset = TestFormset(
            {
                "form-TOTAL_FORMS": "2",
                "form-INITIAL_FORMS": "0",
                "form-0-field": "valid",
                "form-1-field": "invalid",
            }
        )
        formset.full_clean()
        self.assertFormSetError(formset, 0, "field", [])
        self.assertFormSetError(formset, 1, "field", ["invalid value"])

    def test_field_not_in_form(self):
        """

        Tests that an error is raised when attempting to access a field not present in a formset.

        This test case checks that an :class:`AssertionError` is raised with the correct error message
        when trying to access a non-existent field in a formset using :meth:`assertFormSetError`.
        The test also verifies that a custom error message prefix can be provided and is correctly included
        in the raised :class:`AssertionError` message.

        """
        msg = (
            "The form 0 of formset <TestFormset: bound=True valid=False total_forms=1> "
            "does not contain the field 'other_field'."
        )
        with self.assertRaisesMessage(AssertionError, msg):
            self.assertFormSetError(
                TestFormset.invalid(), 0, "other_field", "invalid value"
            )
        msg_prefix = "Custom prefix"
        with self.assertRaisesMessage(AssertionError, f"{msg_prefix}: {msg}"):
            self.assertFormSetError(
                TestFormset.invalid(),
                0,
                "other_field",
                "invalid value",
                msg_prefix=msg_prefix,
            )

    def test_field_with_no_errors(self):
        """
        Lorem ipsum text has been removed. Here is the documentation string:

        \"\"\"
        Test that the function used to assert field specific formset errors raises 
        the expected AssertionError when no errors are found on a field.

        The function checks the case where the formset is valid and contains no 
        errors on the specified field, but the test expects an error to be present. 
        It verifies that the AssertionError has the correct message and that a 
        custom message prefix can be provided.

        """
        msg = (
            "The errors of field 'field' on form 0 of formset <TestFormset: bound=True "
            "valid=True total_forms=1> don't match."
        )
        with self.assertRaisesMessage(AssertionError, msg) as ctx:
            self.assertFormSetError(TestFormset.valid(), 0, "field", "invalid value")
        self.assertIn("[] != ['invalid value']", str(ctx.exception))
        msg_prefix = "Custom prefix"
        with self.assertRaisesMessage(AssertionError, f"{msg_prefix}: {msg}"):
            self.assertFormSetError(
                TestFormset.valid(), 0, "field", "invalid value", msg_prefix=msg_prefix
            )

    def test_field_with_different_error(self):
        """
        Args the validity of a field within a formset by comparing its error message with an expected value.

        This function checks if the error of a specified field in a formset matches the provided error message.
        It verifies that the assertion fails when the error messages do not match and that the correct error message is raised.
        The function also supports a custom prefix for the error message.
        """
        msg = (
            "The errors of field 'field' on form 0 of formset <TestFormset: bound=True "
            "valid=False total_forms=1> don't match."
        )
        with self.assertRaisesMessage(AssertionError, msg) as ctx:
            self.assertFormSetError(TestFormset.invalid(), 0, "field", "other error")
        self.assertIn("['invalid value'] != ['other error']", str(ctx.exception))
        msg_prefix = "Custom prefix"
        with self.assertRaisesMessage(AssertionError, f"{msg_prefix}: {msg}"):
            self.assertFormSetError(
                TestFormset.invalid(), 0, "field", "other error", msg_prefix=msg_prefix
            )

    def test_unbound_formset(self):
        """
        Tests that an unbound formset raises an AssertionError when attempting to check for errors on a specific field, as unbound formsets cannot have errors by definition.
        """
        msg = (
            "The formset <TestFormset: bound=False valid=Unknown total_forms=1> is not "
            "bound, it will never have any errors."
        )
        with self.assertRaisesMessage(AssertionError, msg):
            self.assertFormSetError(TestFormset(), 0, "field", [])

    def test_empty_errors_invalid_formset(self):
        """

        Tests that an :class:`AssertionError` is raised when checking the errors of an empty field
        in an invalid formset, if the expected errors do not match the actual errors.

        Checks that the error message is correctly formatted and contains the expected information,
        including the formset name, whether it is bound, its validity, and the total number of forms.
        Also verifies that the exception message contains a comparison of the expected and actual error values.

        """
        msg = (
            "The errors of field 'field' on form 0 of formset <TestFormset: bound=True "
            "valid=False total_forms=1> don't match."
        )
        with self.assertRaisesMessage(AssertionError, msg) as ctx:
            self.assertFormSetError(TestFormset.invalid(), 0, "field", [])
        self.assertIn("['invalid value'] != []", str(ctx.exception))

    def test_non_field_errors(self):
        self.assertFormSetError(
            TestFormset.invalid(nonfield=True), 0, None, "non-field error"
        )

    def test_different_non_field_errors(self):
        """

        Tests that the non-field errors of a formset are correctly asserted.

        This test checks that the :func:`assertFormSetError` method raises an :class:`AssertionError`
        when the non-field errors of a formset do not match the expected errors. It also verifies
        that the error message is correctly formatted and can be customized with a prefix.

        The test case covers the scenario where the formset has a single form with non-field errors,
        and the expected error message does not match the actual errors.

        """
        msg = (
            "The non-field errors of form 0 of formset <TestFormset: bound=True "
            "valid=False total_forms=1> don't match."
        )
        with self.assertRaisesMessage(AssertionError, msg) as ctx:
            self.assertFormSetError(
                TestFormset.invalid(nonfield=True), 0, None, "other non-field error"
            )
        self.assertIn(
            "['non-field error'] != ['other non-field error']", str(ctx.exception)
        )
        msg_prefix = "Custom prefix"
        with self.assertRaisesMessage(AssertionError, f"{msg_prefix}: {msg}"):
            self.assertFormSetError(
                TestFormset.invalid(nonfield=True),
                0,
                None,
                "other non-field error",
                msg_prefix=msg_prefix,
            )

    def test_no_non_field_errors(self):
        msg = (
            "The non-field errors of form 0 of formset <TestFormset: bound=True "
            "valid=False total_forms=1> don't match."
        )
        with self.assertRaisesMessage(AssertionError, msg) as ctx:
            self.assertFormSetError(TestFormset.invalid(), 0, None, "non-field error")
        self.assertIn("[] != ['non-field error']", str(ctx.exception))
        msg_prefix = "Custom prefix"
        with self.assertRaisesMessage(AssertionError, f"{msg_prefix}: {msg}"):
            self.assertFormSetError(
                TestFormset.invalid(), 0, None, "non-field error", msg_prefix=msg_prefix
            )

    def test_non_form_errors(self):
        self.assertFormSetError(TestFormset.invalid(nonform=True), None, None, "error")

    def test_different_non_form_errors(self):
        """

        Tests whether the function :func:`~.assertFormSetError` correctly identifies and raises an exception when the non-form errors of a formset do not match the expected errors.

        Checks that the error message raised by :func:`~.assertFormSetError` includes the details of the mismatch and that a custom prefix can be added to the error message if required.

        """
        msg = (
            "The non-form errors of formset <TestFormset: bound=True valid=False "
            "total_forms=0> don't match."
        )
        with self.assertRaisesMessage(AssertionError, msg) as ctx:
            self.assertFormSetError(
                TestFormset.invalid(nonform=True), None, None, "other error"
            )
        self.assertIn("['error'] != ['other error']", str(ctx.exception))
        msg_prefix = "Custom prefix"
        with self.assertRaisesMessage(AssertionError, f"{msg_prefix}: {msg}"):
            self.assertFormSetError(
                TestFormset.invalid(nonform=True),
                None,
                None,
                "other error",
                msg_prefix=msg_prefix,
            )

    def test_no_non_form_errors(self):
        msg = (
            "The non-form errors of formset <TestFormset: bound=True valid=False "
            "total_forms=1> don't match."
        )
        with self.assertRaisesMessage(AssertionError, msg) as ctx:
            self.assertFormSetError(TestFormset.invalid(), None, None, "error")
        self.assertIn("[] != ['error']", str(ctx.exception))
        msg_prefix = "Custom prefix"
        with self.assertRaisesMessage(AssertionError, f"{msg_prefix}: {msg}"):
            self.assertFormSetError(
                TestFormset.invalid(),
                None,
                None,
                "error",
                msg_prefix=msg_prefix,
            )

    def test_non_form_errors_with_field(self):
        """
        Tests that a ValueError is raised when attempting to assert a non-form error without specifying a field when form_index is None.

        This test case verifies that the function correctly handles the scenario where a non-form error is encountered and the field parameter is not provided, ensuring that the expected error message is raised.

        Parameters are tested to validate that they satisfy the required conditions, specifically that the field must be set to None when the form_index is also None. The error message 'You must use field=None with form_index=None.' is expected to be raised, confirming the correct handling of this specific validation rule.
        """
        msg = "You must use field=None with form_index=None."
        with self.assertRaisesMessage(ValueError, msg):
            self.assertFormSetError(
                TestFormset.invalid(nonform=True), None, "field", "error"
            )

    def test_form_index_too_big(self):
        """
        Tests that an :class:`AssertionError` is raised when attempting to access a form index that is out of range.

        Specifically, this test case verifies that trying to access a form index that is larger than the total number of forms in the formset results in an :class:`AssertionError` with a descriptive error message.

        The error message is expected to indicate the total number of forms in the formset and the fact that the form index is invalid.
        """
        msg = (
            "The formset <TestFormset: bound=True valid=False total_forms=1> only has "
            "1 form."
        )
        with self.assertRaisesMessage(AssertionError, msg):
            self.assertFormSetError(TestFormset.invalid(), 2, "field", "error")

    def test_form_index_too_big_plural(self):
        formset = TestFormset(
            {
                "form-TOTAL_FORMS": "2",
                "form-INITIAL_FORMS": "0",
                "form-0-field": "valid",
                "form-1-field": "valid",
            }
        )
        formset.full_clean()
        msg = (
            "The formset <TestFormset: bound=True valid=True total_forms=2> only has 2 "
            "forms."
        )
        with self.assertRaisesMessage(AssertionError, msg):
            self.assertFormSetError(formset, 2, "field", "error")


class FirstUrls:
    urlpatterns = [path("first/", empty_response, name="first")]


class SecondUrls:
    urlpatterns = [path("second/", empty_response, name="second")]


class SetupTestEnvironmentTests(SimpleTestCase):
    def test_setup_test_environment_calling_more_than_once(self):
        """
        Tests that calling setup_test_environment more than once raises a RuntimeError.

        This test ensures that the setup_test_environment function can only be called once,
        preventing multiple initializations of the test environment. If setup_test_environment
        is called again after its initial invocation, it should raise a RuntimeError with
        a message indicating that it was already called.

        raises:
            RuntimeError: If setup_test_environment is called more than once.

        """
        with self.assertRaisesMessage(
            RuntimeError, "setup_test_environment() was already called"
        ):
            setup_test_environment()

    def test_allowed_hosts(self):
        for type_ in (list, tuple):
            with self.subTest(type_=type_):
                allowed_hosts = type_("*")
                with mock.patch("django.test.utils._TestState") as x:
                    del x.saved_data
                    with self.settings(ALLOWED_HOSTS=allowed_hosts):
                        setup_test_environment()
                        self.assertEqual(settings.ALLOWED_HOSTS, ["*", "testserver"])


class OverrideSettingsTests(SimpleTestCase):
    # #21518 -- If neither override_settings nor a setting_changed receiver
    # clears the URL cache between tests, then one of test_first or
    # test_second will fail.

    @override_settings(ROOT_URLCONF=FirstUrls)
    def test_urlconf_first(self):
        reverse("first")

    @override_settings(ROOT_URLCONF=SecondUrls)
    def test_urlconf_second(self):
        reverse("second")

    def test_urlconf_cache(self):
        """

        Tests the caching behavior of the URL resolver in the context of overriding the root URL configuration.

        The test verifies that the URL resolver correctly updates its cache when the root URL configuration is changed.
        It checks that reversing URLs that are not present in the current configuration raises a NoReverseMatch exception,
        and that reversing URLs that are present in the current configuration succeeds.

        The test covers the following scenarios:

        * The initial state, where neither of the test URLs can be reversed.
        * Overriding the root URL configuration with the first set of URLs, and verifying that only the first URL can be reversed.
        * Overriding the root URL configuration with the second set of URLs, and verifying that only the second URL can be reversed.
        * Reverting back to the original configuration, and verifying that the first URL can still be reversed.
        * The final state, where neither of the test URLs can be reversed again.

        This test ensures that the URL resolver's cache is correctly updated when the root URL configuration changes,
        and that the resolver raises exceptions when attempting to reverse URLs that are not present in the current configuration.

        """
        with self.assertRaises(NoReverseMatch):
            reverse("first")
        with self.assertRaises(NoReverseMatch):
            reverse("second")

        with override_settings(ROOT_URLCONF=FirstUrls):
            self.client.get(reverse("first"))
            with self.assertRaises(NoReverseMatch):
                reverse("second")

            with override_settings(ROOT_URLCONF=SecondUrls):
                with self.assertRaises(NoReverseMatch):
                    reverse("first")
                self.client.get(reverse("second"))

            self.client.get(reverse("first"))
            with self.assertRaises(NoReverseMatch):
                reverse("second")

        with self.assertRaises(NoReverseMatch):
            reverse("first")
        with self.assertRaises(NoReverseMatch):
            reverse("second")

    def test_override_media_root(self):
        """
        Overriding the MEDIA_ROOT setting should be reflected in the
        base_location attribute of django.core.files.storage.default_storage.
        """
        self.assertEqual(default_storage.base_location, "")
        with self.settings(MEDIA_ROOT="test_value"):
            self.assertEqual(default_storage.base_location, "test_value")

    def test_override_media_url(self):
        """
        Overriding the MEDIA_URL setting should be reflected in the
        base_url attribute of django.core.files.storage.default_storage.
        """
        self.assertEqual(default_storage.base_location, "")
        with self.settings(MEDIA_URL="/test_value/"):
            self.assertEqual(default_storage.base_url, "/test_value/")

    def test_override_file_upload_permissions(self):
        """
        Overriding the FILE_UPLOAD_PERMISSIONS setting should be reflected in
        the file_permissions_mode attribute of
        django.core.files.storage.default_storage.
        """
        self.assertEqual(default_storage.file_permissions_mode, 0o644)
        with self.settings(FILE_UPLOAD_PERMISSIONS=0o777):
            self.assertEqual(default_storage.file_permissions_mode, 0o777)

    def test_override_file_upload_directory_permissions(self):
        """
        Overriding the FILE_UPLOAD_DIRECTORY_PERMISSIONS setting should be
        reflected in the directory_permissions_mode attribute of
        django.core.files.storage.default_storage.
        """
        self.assertIsNone(default_storage.directory_permissions_mode)
        with self.settings(FILE_UPLOAD_DIRECTORY_PERMISSIONS=0o777):
            self.assertEqual(default_storage.directory_permissions_mode, 0o777)

    def test_override_database_routers(self):
        """
        Overriding DATABASE_ROUTERS should update the base router.
        """
        test_routers = [object()]
        with self.settings(DATABASE_ROUTERS=test_routers):
            self.assertEqual(router.routers, test_routers)

    def test_override_static_url(self):
        """
        Overriding the STATIC_URL setting should be reflected in the
        base_url attribute of
        django.contrib.staticfiles.storage.staticfiles_storage.
        """
        with self.settings(STATIC_URL="/test/"):
            self.assertEqual(staticfiles_storage.base_url, "/test/")

    def test_override_static_root(self):
        """
        Overriding the STATIC_ROOT setting should be reflected in the
        location attribute of
        django.contrib.staticfiles.storage.staticfiles_storage.
        """
        with self.settings(STATIC_ROOT="/tmp/test"):
            self.assertEqual(staticfiles_storage.location, os.path.abspath("/tmp/test"))

    def test_override_staticfiles_storage(self):
        """
        Overriding the STORAGES setting should be reflected in
        the value of django.contrib.staticfiles.storage.staticfiles_storage.
        """
        new_class = "ManifestStaticFilesStorage"
        new_storage = "django.contrib.staticfiles.storage." + new_class
        with self.settings(
            STORAGES={STATICFILES_STORAGE_ALIAS: {"BACKEND": new_storage}}
        ):
            self.assertEqual(staticfiles_storage.__class__.__name__, new_class)

    def test_override_staticfiles_finders(self):
        """
        Overriding the STATICFILES_FINDERS setting should be reflected in
        the return value of django.contrib.staticfiles.finders.get_finders.
        """
        current = get_finders()
        self.assertGreater(len(list(current)), 1)
        finders = ["django.contrib.staticfiles.finders.FileSystemFinder"]
        with self.settings(STATICFILES_FINDERS=finders):
            self.assertEqual(len(list(get_finders())), len(finders))

    def test_override_staticfiles_dirs(self):
        """
        Overriding the STATICFILES_DIRS setting should be reflected in
        the locations attribute of the
        django.contrib.staticfiles.finders.FileSystemFinder instance.
        """
        finder = get_finder("django.contrib.staticfiles.finders.FileSystemFinder")
        test_path = "/tmp/test"
        expected_location = ("", test_path)
        self.assertNotIn(expected_location, finder.locations)
        with self.settings(STATICFILES_DIRS=[test_path]):
            finder = get_finder("django.contrib.staticfiles.finders.FileSystemFinder")
            self.assertIn(expected_location, finder.locations)


@skipUnlessDBFeature("supports_transactions")
class TestBadSetUpTestData(TestCase):
    """
    An exception in setUpTestData() shouldn't leak a transaction which would
    cascade across the rest of the test suite.
    """

    class MyException(Exception):
        pass

    @classmethod
    def setUpClass(cls):
        """

        Sets up the class for testing.

        This method is a class-level setup hook that is called before any tests in the class are run.
        It ensures that the superclass setup is completed successfully, and if an exception of type :class:`MyException` occurs,
        it checks if a database transaction is currently in an atomic block.

        The purpose of this method is to prepare the test environment and handle any potential exceptions that may arise during setup.

        """
        try:
            super().setUpClass()
        except cls.MyException:
            cls._in_atomic_block = connection.in_atomic_block

    @classmethod
    def tearDownClass(Cls):
        # override to avoid a second cls._rollback_atomics() which would fail.
        # Normal setUpClass() methods won't have exception handling so this
        # method wouldn't typically be run.
        pass

    @classmethod
    def setUpTestData(cls):
        # Simulate a broken setUpTestData() method.
        raise cls.MyException()

    def test_failure_in_setUpTestData_should_rollback_transaction(self):
        # setUpTestData() should call _rollback_atomics() so that the
        # transaction doesn't leak.
        self.assertFalse(self._in_atomic_block)


@skipUnlessDBFeature("supports_transactions")
class CaptureOnCommitCallbacksTests(TestCase):
    databases = {"default", "other"}
    callback_called = False

    def enqueue_callback(self, using="default"):
        """
        Enqueue a callback function to be executed after the current database transaction has been committed.

        The callback function is automatically generated and its sole purpose is to mark the callback as called.

        :param using: The database alias to use for the commit hook. Defaults to 'default'. 
        :returns: None
        """
        def hook():
            self.callback_called = True

        transaction.on_commit(hook, using=using)

    def test_no_arguments(self):
        """
        Tests that a callback is successfully enqueued and executed.

        This test case verifies that a callback is properly stored and invoked when
        committed. It checks that the callback is initially not called, is successfully
        enqueued, and then executed when the stored callback is invoked, resulting in the
        expected behavior of setting the callback_called flag to True.
        """
        with self.captureOnCommitCallbacks() as callbacks:
            self.enqueue_callback()

        self.assertEqual(len(callbacks), 1)
        self.assertIs(self.callback_called, False)
        callbacks[0]()
        self.assertIs(self.callback_called, True)

    def test_using(self):
        """

        Tests the usage of commit callbacks by enqueuing a callback using a specific database connection.

        This function verifies that a callback is properly enqueued and executed. It checks that the callback is not executed
        immediately upon enqueueing, but rather is stored for later execution. The test then manually executes the callback
        and verifies that it has run successfully.

        """
        with self.captureOnCommitCallbacks(using="other") as callbacks:
            self.enqueue_callback(using="other")

        self.assertEqual(len(callbacks), 1)
        self.assertIs(self.callback_called, False)
        callbacks[0]()
        self.assertIs(self.callback_called, True)

    def test_different_using(self):
        """
        Tests that callbacks are not captured when using a different database.

        This test case verifies that callbacks are isolated to their respective databases.
        It checks that a callback enqueued on a different database does not trigger the
        capture of callbacks on the default database, resulting in an empty list of
        captured callbacks.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the captured callbacks list is not empty.

        """
        with self.captureOnCommitCallbacks(using="default") as callbacks:
            self.enqueue_callback(using="other")

        self.assertEqual(callbacks, [])

    def test_execute(self):
        """
        Tests the execution of a callback function.

        This test case verifies that a callback is successfully executed when 
        the enqueue_callback function is invoked. It checks that the callback 
        is triggered only once and that the callback_called flag is set to True 
        after execution, ensuring that the callback was properly executed.

        Returns:
            None

        Raises:
            AssertionError: If the callback is not executed as expected.
        """
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.enqueue_callback()

        self.assertEqual(len(callbacks), 1)
        self.assertIs(self.callback_called, True)

    def test_pre_callback(self):
        def pre_hook():
            pass

        transaction.on_commit(pre_hook, using="default")
        with self.captureOnCommitCallbacks() as callbacks:
            self.enqueue_callback()

        self.assertEqual(len(callbacks), 1)
        self.assertNotEqual(callbacks[0], pre_hook)

    def test_with_rolled_back_savepoint(self):
        """
        Tests that a savepoint is properly rolled back when an exception occurs during a database transaction.

        This test case verifies that when an IntegrityError is raised within a transaction, the changes are successfully rolled back, 
        and no on-commit callbacks are triggered. The transactional behavior ensures data consistency and prevents partial updates 
        in the event of an error. 

        :raises IntegrityError: An integrity error is intentionally raised to simulate an exception within the transaction.
        :returns: None
        """
        with self.captureOnCommitCallbacks() as callbacks:
            try:
                with transaction.atomic():
                    self.enqueue_callback()
                    raise IntegrityError
            except IntegrityError:
                # Inner transaction.atomic() has been rolled back.
                pass

        self.assertEqual(callbacks, [])

    def test_execute_recursive(self):
        """
        Tests the execution of callbacks registered with the transaction using a recursive approach.

        This test case checks that the on_commit callbacks are properly triggered and executed after a transaction is committed. It verifies that the expected number of callbacks are registered and that the callbacks are indeed called when the transaction is committed. The test specifically focuses on the recursive behavior of callback execution to ensure that it functions as expected.
        """
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            transaction.on_commit(self.enqueue_callback)

        self.assertEqual(len(callbacks), 2)
        self.assertIs(self.callback_called, True)

    def test_execute_tree(self):
        """
        A visualisation of the callback tree tested. Each node is expected to
        be visited only once:

        └─branch_1
          ├─branch_2
          │ ├─leaf_1
          │ └─leaf_2
          └─leaf_3
        """
        branch_1_call_counter = 0
        branch_2_call_counter = 0
        leaf_1_call_counter = 0
        leaf_2_call_counter = 0
        leaf_3_call_counter = 0

        def leaf_1():
            nonlocal leaf_1_call_counter
            leaf_1_call_counter += 1

        def leaf_2():
            nonlocal leaf_2_call_counter
            leaf_2_call_counter += 1

        def leaf_3():
            """
            Increments the leaf_3 call counter.

            This function is used to track the number of times it is invoked, likely for debugging or logging purposes.

            Returns:
                None

            Notes:
                The call counter is assumed to be defined in an outer scope, and is modified in-place by this function.
            """
            nonlocal leaf_3_call_counter
            leaf_3_call_counter += 1

        def branch_1():
            nonlocal branch_1_call_counter
            branch_1_call_counter += 1
            transaction.on_commit(branch_2)
            transaction.on_commit(leaf_3)

        def branch_2():
            nonlocal branch_2_call_counter
            branch_2_call_counter += 1
            transaction.on_commit(leaf_1)
            transaction.on_commit(leaf_2)

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            transaction.on_commit(branch_1)

        self.assertEqual(branch_1_call_counter, 1)
        self.assertEqual(branch_2_call_counter, 1)
        self.assertEqual(leaf_1_call_counter, 1)
        self.assertEqual(leaf_2_call_counter, 1)
        self.assertEqual(leaf_3_call_counter, 1)

        self.assertEqual(callbacks, [branch_1, branch_2, leaf_3, leaf_1, leaf_2])

    def test_execute_robust(self):
        """

        Tests the execution of a robust on-commit callback, ensuring that the callback is executed, 
        an exception is raised and caught, and the error is properly logged.

        The test verifies that the callback is executed successfully, despite raising an exception, 
        and that the exception is logged with the correct error message. Additionally, it checks 
        that the log record contains the exception information and that the exception type and 
        message are as expected.

        """
        class MyException(Exception):
            pass

        def hook():
            self.callback_called = True
            raise MyException("robust callback")

        with self.assertLogs("django.test", "ERROR") as cm:
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                transaction.on_commit(hook, robust=True)

        self.assertEqual(len(callbacks), 1)
        self.assertIs(self.callback_called, True)

        log_record = cm.records[0]
        self.assertEqual(
            log_record.getMessage(),
            "Error calling CaptureOnCommitCallbacksTests.test_execute_robust.<locals>."
            "hook in on_commit() (robust callback).",
        )
        self.assertIsNotNone(log_record.exc_info)
        raised_exception = log_record.exc_info[1]
        self.assertIsInstance(raised_exception, MyException)
        self.assertEqual(str(raised_exception), "robust callback")


class DisallowedDatabaseQueriesTests(SimpleTestCase):
    def test_disallowed_database_connections(self):
        """

        Tests that database connections to 'default' are not allowed in SimpleTestCase subclasses.

        This test checks that attempting to establish a connection to the default database or create a temporary connection raises a DatabaseOperationForbidden exception.
        The expected error message provides guidance on how to resolve the issue by either subclassing TestCase or TransactionTestCase, or by adding the 'default' database to the list of allowed databases in DisallowedDatabaseQueriesTests.

        The purpose of this test is to ensure proper test isolation, preventing tests from interfering with each other through the database.

        """
        expected_message = (
            "Database connections to 'default' are not allowed in SimpleTestCase "
            "subclasses. Either subclass TestCase or TransactionTestCase to "
            "ensure proper test isolation or add 'default' to "
            "test_utils.tests.DisallowedDatabaseQueriesTests.databases to "
            "silence this failure."
        )
        with self.assertRaisesMessage(DatabaseOperationForbidden, expected_message):
            connection.connect()
        with self.assertRaisesMessage(DatabaseOperationForbidden, expected_message):
            connection.temporary_connection()

    def test_disallowed_database_queries(self):
        expected_message = (
            "Database queries to 'default' are not allowed in SimpleTestCase "
            "subclasses. Either subclass TestCase or TransactionTestCase to "
            "ensure proper test isolation or add 'default' to "
            "test_utils.tests.DisallowedDatabaseQueriesTests.databases to "
            "silence this failure."
        )
        with self.assertRaisesMessage(DatabaseOperationForbidden, expected_message):
            Car.objects.first()

    def test_disallowed_database_chunked_cursor_queries(self):
        """
        Tests that chunked cursor queries against the 'default' database are disallowed in SimpleTestCase subclasses.

        This test ensures that attempting to execute a database query using a chunked cursor 
        will raise a DatabaseOperationForbidden exception. The exception is expected to 
        contain a message indicating that queries to the 'default' database are not allowed 
        in SimpleTestCase subclasses and providing guidance on how to resolve the issue.

        The test passes if the correct exception is raised with the expected message, 
        indicating that proper test isolation has been maintained and database queries are 
        being restricted as intended.
        """
        expected_message = (
            "Database queries to 'default' are not allowed in SimpleTestCase "
            "subclasses. Either subclass TestCase or TransactionTestCase to "
            "ensure proper test isolation or add 'default' to "
            "test_utils.tests.DisallowedDatabaseQueriesTests.databases to "
            "silence this failure."
        )
        with self.assertRaisesMessage(DatabaseOperationForbidden, expected_message):
            next(Car.objects.iterator())

    def test_disallowed_thread_database_connection(self):
        """
        Tests that a DatabaseOperationForbidden exception is raised when attempting to access the database from a separate thread in a SimpleTestCase subclass. 

        This test simulates a common mistake where a test case attempts to use a database connection from a separate thread, which can lead to test isolation issues. 

        Verifies that the correct error message is raised and that proper exception handling is in place to prevent unintended database access.
        """
        expected_message = (
            "Database threaded connections to 'default' are not allowed in "
            "SimpleTestCase subclasses. Either subclass TestCase or TransactionTestCase"
            " to ensure proper test isolation or add 'default' to "
            "test_utils.tests.DisallowedDatabaseQueriesTests.databases to "
            "silence this failure."
        )

        exceptions = []

        def thread_func():
            """

            Attempts to retrieve the first Car object from the database to test database connectivity.

            Raises a DatabaseOperationForbidden exception if the database operation is forbidden, 
            which is then appended to the list of exceptions for further handling.

            This function is typically used in a multi-threaded environment to validate database access.

            """
            try:
                Car.objects.first()
            except DatabaseOperationForbidden as e:
                exceptions.append(e)

        t = threading.Thread(target=thread_func)
        t.start()
        t.join()
        self.assertEqual(len(exceptions), 1)
        self.assertEqual(exceptions[0].args[0], expected_message)


class AllowedDatabaseQueriesTests(SimpleTestCase):
    databases = {"default"}

    def test_allowed_database_queries(self):
        Car.objects.first()

    def test_allowed_database_chunked_cursor_queries(self):
        next(Car.objects.iterator(), None)

    def test_allowed_threaded_database_queries(self):
        """

        Tests that database queries can be executed in a threaded environment.

        This function creates a new thread that issues a database query and checks 
        that the connection is properly shared between threads. After the thread 
        has finished, it ensures that any connections that were used are properly 
        closed and thread sharing is validated.

        The purpose of this test is to verify that the database backend correctly 
        handles concurrent queries from multiple threads, and that it correctly 
        implements thread sharing to prevent connections from being used by 
        multiple threads at the same time.

        """
        connections_dict = {}

        def thread_func():
            # Passing django.db.connection between threads doesn't work while
            # connections[DEFAULT_DB_ALIAS] does.
            """
            Initialize and configure a database connection for the current thread.

            This function sets up a thread-specific database connection, ensuring that it can be safely shared and reused within the thread.
            It also retrieves an iterator for Car objects, likely to lazy-load related data or verify the connection.
            The connection is then marked for thread sharing, allowing other parts of the application to safely access and utilize the connection.
            The configured connection is stored in a dictionary for later retrieval, based on its unique identifier.

            Returns:
                None

            Note:
                This function is intended for internal use, likely as part of a larger threading or asynchronous processing system.
                It assumes a Django application context and relies on the 'default' database connection being properly configured.

            """
            from django.db import connections

            connection = connections["default"]

            next(Car.objects.iterator(), None)

            # Allow thread sharing so the connection can be closed by the main
            # thread.
            connection.inc_thread_sharing()
            connections_dict[id(connection)] = connection

        try:
            t = threading.Thread(target=thread_func)
            t.start()
            t.join()
        finally:
            # Finish by closing the connections opened by the other threads
            # (the connection opened in the main thread will automatically be
            # closed on teardown).
            for conn in connections_dict.values():
                if conn is not connection and conn.allow_thread_sharing:
                    conn.validate_thread_sharing()
                    conn._close()
                    conn.dec_thread_sharing()

    def test_allowed_database_copy_queries(self):
        """

        Test the execution of allowed copy queries on a dynamically copied database connection.

        This test case creates a new copy of a database connection, executes a simple SQL query,
        and verifies that the query returns the expected result. The query is a basic SELECT
        statement that can be executed on the database without any special privileges or setup.

        The test ensures that the copied connection is functional and can be used to execute
        queries, and also verifies that the connection is properly cleaned up after use.

        """
        new_connection = connection.copy("dynamic_connection")
        try:
            with new_connection.cursor() as cursor:
                sql = f"SELECT 1{new_connection.features.bare_select_suffix}"
                cursor.execute(sql)
                self.assertEqual(cursor.fetchone()[0], 1)
        finally:
            new_connection.validate_thread_sharing()
            new_connection._close()


class DatabaseAliasTests(SimpleTestCase):
    def setUp(self):
        self.addCleanup(setattr, self.__class__, "databases", self.databases)

    def test_no_close_match(self):
        self.__class__.databases = {"void"}
        message = (
            "test_utils.tests.DatabaseAliasTests.databases refers to 'void' which is "
            "not defined in settings.DATABASES."
        )
        with self.assertRaisesMessage(ImproperlyConfigured, message):
            self._validate_databases()

    def test_close_match(self):
        self.__class__.databases = {"defualt"}
        message = (
            "test_utils.tests.DatabaseAliasTests.databases refers to 'defualt' which "
            "is not defined in settings.DATABASES. Did you mean 'default'?"
        )
        with self.assertRaisesMessage(ImproperlyConfigured, message):
            self._validate_databases()

    def test_match(self):
        """

        Tests if the _validate_databases method correctly matches and returns the set of databases.

        The function sets up a test scenario with a predefined set of databases and then asserts that 
        the _validate_databases method returns the expected set of databases.

        This test ensures that the _validate_databases method functions as expected and 
        returns a consistent result.

        """
        self.__class__.databases = {"default", "other"}
        self.assertEqual(self._validate_databases(), frozenset({"default", "other"}))

    def test_all(self):
        """

        Tests the validation of all databases by verifying that the function returns 
        a set of all available connections when the databases attribute is set to '__all__'.

        The test case checks if the _validate_databases method correctly returns a 
        frozenset of all connections when all databases are specified.

        """
        self.__class__.databases = "__all__"
        self.assertEqual(self._validate_databases(), frozenset(connections))


@isolate_apps("test_utils", attr_name="class_apps")
class IsolatedAppsTests(SimpleTestCase):
    def test_installed_apps(self):
        self.assertEqual(
            [app_config.label for app_config in self.class_apps.get_app_configs()],
            ["test_utils"],
        )

    def test_class_decoration(self):
        """

        Tests the class decoration functionality to ensure it correctly assigns the application configuration.

        This test case verifies that the application instance is properly associated with the model class
        during the decoration process.

        The test checks if the application instance stored in the model class metadata matches the expected
        application instance.

        """
        class ClassDecoration(models.Model):
            pass

        self.assertEqual(ClassDecoration._meta.apps, self.class_apps)

    @isolate_apps("test_utils", kwarg_name="method_apps")
    def test_method_decoration(self, method_apps):
        class MethodDecoration(models.Model):
            pass

        self.assertEqual(MethodDecoration._meta.apps, method_apps)

    def test_context_manager(self):
        """

        Tests that the context manager returned by isolate_apps correctly isolates 
        the specified app ('test_utils') and sets it as the apps registry for models 
        defined within its context.

        Verifies that models created within the context manager's 'with' block 
        reference the isolated app registry as their Meta.apps attribute.

        """
        with isolate_apps("test_utils") as context_apps:

            class ContextManager(models.Model):
                pass

        self.assertEqual(ContextManager._meta.apps, context_apps)

    @isolate_apps("test_utils", kwarg_name="method_apps")
    def test_nested(self, method_apps):
        """
        Tests the isolation of Django applications in a nested context.

        This test function verifies that models defined within isolated application
        scopes have their `apps` attribute set correctly, ensuring proper app registration
        and management.

        Args:
            method_apps: The isolated application registry for the test method.

        The test scenario covers three levels of isolation: method-level, context manager,
        and nested context manager. It checks that each model's app registry is set
        accordingly, demonstrating the correct functioning of application isolation
        mechanisms in different scopes.
        """
        class MethodDecoration(models.Model):
            pass

        with isolate_apps("test_utils") as context_apps:

            class ContextManager(models.Model):
                pass

            with isolate_apps("test_utils") as nested_context_apps:

                class NestedContextManager(models.Model):
                    pass

        self.assertEqual(MethodDecoration._meta.apps, method_apps)
        self.assertEqual(ContextManager._meta.apps, context_apps)
        self.assertEqual(NestedContextManager._meta.apps, nested_context_apps)


class DoNothingDecorator(TestContextDecorator):
    def enable(self):
        pass

    def disable(self):
        pass


class TestContextDecoratorTests(SimpleTestCase):
    @mock.patch.object(DoNothingDecorator, "disable")
    def test_exception_in_setup(self, mock_disable):
        """An exception is setUp() is reraised after disable() is called."""

        class ExceptionInSetUp(unittest.TestCase):
            def setUp(self):
                raise NotImplementedError("reraised")

        decorator = DoNothingDecorator()
        decorated_test_class = decorator.__call__(ExceptionInSetUp)()
        self.assertFalse(mock_disable.called)
        with self.assertRaisesMessage(NotImplementedError, "reraised"):
            decorated_test_class.setUp()
        decorated_test_class.doCleanups()
        self.assertTrue(mock_disable.called)

    def test_cleanups_run_after_tearDown(self):
        """

        Verifies that test cleanups are executed after the tearDown method.

        This test case checks the order of operations when a test class utilizes a decorator and the addCleanup method.
        The verification process ensures that cleanups are run after tearDown, in the correct sequence, for proper test context management.

        The test outcome is a pass if the cleanups occur in the expected order, which includes:
        - Enabling the decorator
        - Setting up the test
        - Executing the cleanup
        - Disabling the decorator

        """
        calls = []

        class SaveCallsDecorator(TestContextDecorator):
            def enable(self):
                calls.append("enable")

            def disable(self):
                calls.append("disable")

        class AddCleanupInSetUp(unittest.TestCase):
            def setUp(self):
                """

                Set up the test environment.

                This method is called before each test to initialize the setup. 
                It registers a cleanup function to be executed after the test, 
                ensuring that the test environment is properly cleaned up after execution.

                """
                calls.append("setUp")
                self.addCleanup(lambda: calls.append("cleanup"))

        decorator = SaveCallsDecorator()
        decorated_test_class = decorator.__call__(AddCleanupInSetUp)()
        decorated_test_class.setUp()
        decorated_test_class.tearDown()
        decorated_test_class.doCleanups()
        self.assertEqual(calls, ["enable", "setUp", "cleanup", "disable"])
