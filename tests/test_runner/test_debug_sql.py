import unittest
from io import StringIO

from django.db import connection
from django.test import TestCase
from django.test.runner import DiscoverRunner
from django.utils.version import PY311

from .models import Person


@unittest.skipUnless(
    connection.vendor == "sqlite", "Only run on sqlite so we can check output SQL."
)
class TestDebugSQL(unittest.TestCase):
    class PassingTest(TestCase):
        def runTest(self):
            Person.objects.filter(first_name="pass").count()

    class FailingTest(TestCase):
        def runTest(self):
            """
            Runs a test case that is expected to fail.

            This test deliberately attempts to retrieve objects from the database that do not exist,
            and then asserts failure, verifying the test framework's ability to detect and report test failures.

            Note: This test will always fail and is intended for testing the test framework itself, rather than the functionality being tested.
            """
            Person.objects.filter(first_name="fail").count()
            self.fail()

    class ErrorTest(TestCase):
        def runTest(self):
            """
            Triggers a test by filtering database objects and intentionally raising an exception.

            This method performs a database query to count the number of Person objects with a first name of 'error', 
            then explicitly raises an exception, presumably for testing purposes, such as testing error handling mechanisms.

            Note: This function will always raise an exception after executing the database query, and should be used in a controlled test environment.

            """
            Person.objects.filter(first_name="error").count()
            raise Exception

    class ErrorSetUpTestDataTest(TestCase):
        @classmethod
        def setUpTestData(cls):
            raise Exception

        def runTest(self):
            pass

    class PassingSubTest(TestCase):
        def runTest(self):
            """

            Runs a database query test to verify the existence of records.

            This test case uses Django's ORM to query the database for 'Person' objects 
            where the 'first_name' is 'subtest-pass'. The test counts the number of matching 
            records, implicitly verifying that the data exists as expected.

            The test is run within a subtest context, allowing for more detailed reporting 
            and flexibility in the event of test failures.

            """
            with self.subTest():
                Person.objects.filter(first_name="subtest-pass").count()

    class FailingSubTest(TestCase):
        def runTest(self):
            with self.subTest():
                Person.objects.filter(first_name="subtest-fail").count()
                self.fail()

    class ErrorSubTest(TestCase):
        def runTest(self):
            """
            Runs a test case to verify error handling in subtest scenarios.

            This method simulates an exception during the execution of a database query,
            specifically when attempting to retrieve Person objects with a first name of 'subtest-error'.
            The test case aims to validate that the testing framework correctly handles and reports errors
            occurring within a subtest context, ensuring that the test execution is robust and informative
            in the presence of failures.

            Raises:
                Exception: An exception is intentionally raised to trigger error handling mechanisms.

            """
            with self.subTest():
                Person.objects.filter(first_name="subtest-error").count()
                raise Exception

    def _test_output(self, verbosity):
        """
        Runs a test suite with various test cases and captures the output.

        This function creates a test suite consisting of passing, failing, and error tests,
        both standalone and as subtests. It then runs the suite with a specified verbosity
        level, capturing the output to a string. The function takes care of setting up and
        tearing down the test database.

        The verbosity level controls the amount of detail in the output. A higher verbosity
        level will result in more detailed output.

        Returns:
            str: The captured output of the test suite as a string.
        """
        runner = DiscoverRunner(debug_sql=True, verbosity=0)
        suite = runner.test_suite()
        suite.addTest(self.FailingTest())
        suite.addTest(self.ErrorTest())
        suite.addTest(self.PassingTest())
        suite.addTest(self.PassingSubTest())
        suite.addTest(self.FailingSubTest())
        suite.addTest(self.ErrorSubTest())
        old_config = runner.setup_databases()
        stream = StringIO()
        resultclass = runner.get_resultclass()
        runner.test_runner(
            verbosity=verbosity,
            stream=stream,
            resultclass=resultclass,
        ).run(suite)
        runner.teardown_databases(old_config)

        return stream.getvalue()

    def test_output_normal(self):
        """

        Verifies the normal output of a process by checking for the presence and absence of expected strings.

        This test ensures that all normal output strings are included in the full output, while verbose output strings are excluded.

        """
        full_output = self._test_output(1)
        for output in self.expected_outputs:
            self.assertIn(output, full_output)
        for output in self.verbose_expected_outputs:
            self.assertNotIn(output, full_output)

    def test_output_verbose(self):
        """

        Verifies the output of a test in verbose mode.

        This function checks that the test output contains all expected messages, 
        including both regular and verbose expected outputs. It ensures that 
        the test is producing the correct and complete output when run with 
        verbose mode enabled.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If any expected output messages are missing from the test output.

        """
        full_output = self._test_output(2)
        for output in self.expected_outputs:
            self.assertIn(output, full_output)
        for output in self.verbose_expected_outputs:
            self.assertIn(output, full_output)

    expected_outputs = [
        (
            """SELECT COUNT(*) AS "__count"\n"""
            """FROM "test_runner_person"\n"""
            """WHERE "test_runner_person"."first_name" = 'error';"""
        ),
        (
            """SELECT COUNT(*) AS "__count"\n"""
            """FROM "test_runner_person"\n"""
            """WHERE "test_runner_person"."first_name" = 'fail';"""
        ),
        (
            """SELECT COUNT(*) AS "__count"\n"""
            """FROM "test_runner_person"\n"""
            """WHERE "test_runner_person"."first_name" = 'subtest-error';"""
        ),
        (
            """SELECT COUNT(*) AS "__count"\n"""
            """FROM "test_runner_person"\n"""
            """WHERE "test_runner_person"."first_name" = 'subtest-fail';"""
        ),
    ]

    # Python 3.11 uses fully qualified test name in the output.
    method_name = ".runTest" if PY311 else ""
    test_class_path = "test_runner.test_debug_sql.TestDebugSQL"
    verbose_expected_outputs = [
        f"runTest ({test_class_path}.FailingTest{method_name}) ... FAIL",
        f"runTest ({test_class_path}.ErrorTest{method_name}) ... ERROR",
        f"runTest ({test_class_path}.PassingTest{method_name}) ... ok",
        # If there are errors/failures in subtests but not in test itself,
        # the status is not written. That behavior comes from Python.
        f"runTest ({test_class_path}.FailingSubTest{method_name}) ...",
        f"runTest ({test_class_path}.ErrorSubTest{method_name}) ...",
        (
            """SELECT COUNT(*) AS "__count" """
            """FROM "test_runner_person" WHERE """
            """"test_runner_person"."first_name" = 'pass';"""
        ),
        (
            """SELECT COUNT(*) AS "__count" """
            """FROM "test_runner_person" WHERE """
            """"test_runner_person"."first_name" = 'subtest-pass';"""
        ),
    ]

    def test_setupclass_exception(self):
        runner = DiscoverRunner(debug_sql=True, verbosity=0)
        suite = runner.test_suite()
        suite.addTest(self.ErrorSetUpTestDataTest())
        old_config = runner.setup_databases()
        stream = StringIO()
        runner.test_runner(
            verbosity=0,
            stream=stream,
            resultclass=runner.get_resultclass(),
        ).run(suite)
        runner.teardown_databases(old_config)
        output = stream.getvalue()
        self.assertIn(
            "ERROR: setUpClass "
            "(test_runner.test_debug_sql.TestDebugSQL.ErrorSetUpTestDataTest)",
            output,
        )
