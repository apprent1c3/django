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

            Runs a test case that intentionally fails.

            This function queries the database for Person objects with a first name of 'fail' 
            and then immediately fails the test using the fail method, regardless of the query result.

            Use this function to test error handling and assertions in the testing framework.

            """
            Person.objects.filter(first_name="fail").count()
            self.fail()

    class ErrorTest(TestCase):
        def runTest(self):
            """

            Run a test case that deliberately raises an exception.

            This method is intended to test error handling mechanisms. It starts by 
            querying the database for Person objects with a specific first name, 
            and then immediately raises an exception to simulate an error condition.

            Raises:
                Exception: An exception is always raised when this method is called.

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
            with self.subTest():
                Person.objects.filter(first_name="subtest-pass").count()

    class FailingSubTest(TestCase):
        def runTest(self):
            """

            Run a test case that intentionally fails.

            This test is designed to demonstrate the functionality of subtests, where a test case can be divided into multiple independent test runs.
            The test queries the database for Person objects with a specific first name, then immediately fails, triggering a test failure.
            The use of subTest context manager allows the test to provide more detailed information about the failure.

            """
            with self.subTest():
                Person.objects.filter(first_name="subtest-fail").count()
                self.fail()

    class ErrorSubTest(TestCase):
        def runTest(self):
            """
            Run a test to verify exception handling within a subtest context.

            This method executes a database query to count Person objects with a specific first name, 
            then intentionally raises an exception to evaluate the test framework's behavior 
            when handling errors within a subtest. The outcome of this test helps ensure that 
            the testing infrastructure correctly handles and reports exceptions in a subtest scenario.
            """
            with self.subTest():
                Person.objects.filter(first_name="subtest-error").count()
                raise Exception

    def _test_output(self, verbosity):
        """
        Runs a test suite with various test cases and returns the output as a string.

        The test suite includes tests that pass, fail, and raise errors, as well as sub-tests with the same outcomes.
        The function configures a test runner with debug SQL enabled and verbosity set to the provided level,
        then runs the test suite and captures the output.
        Finally, it tears down the test databases and returns the captured output.

        :param int verbosity: The level of detail to include in the test output
        :returns: The test output as a string
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

        Tests that the normal output of the function contains the expected output strings and does not contain verbose output strings.

        This test checks for the presence of each expected output string in the full output, ensuring that all required information is included.
        Additionally, it verifies that the full output does not include any verbose output strings, maintaining the correct level of detail.

        """
        full_output = self._test_output(1)
        for output in self.expected_outputs:
            self.assertIn(output, full_output)
        for output in self.verbose_expected_outputs:
            self.assertNotIn(output, full_output)

    def test_output_verbose(self):
        """
        Tests the output of a function in verbose mode.

        Checks if all expected and verbose expected outputs are present in the full output.
        The test asserts that each expected output and each verbose expected output is a substring of the full output.
        This test is used to verify that the function produces the correct output when run in verbose mode, including both regular and verbose output messages.
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
        """
        Tests whether the setup class method raises an exception when setting up test data.

        This test case validates the error handling behavior of the test runner when the
        setUpClass method encounters an issue during test data setup. It checks if the
        test runner correctly reports the error message in the output.

        The test involves running a test suite with a test case that intentionally
        raises an exception in its setUpClass method, and then verifying that the
        expected error message is present in the test output.

        Parameters: None

        Returns: None

        Raises: AssertionError if the expected error message is not found in the test output.
        """
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
