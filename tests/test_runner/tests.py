"""
Tests for django test runner
"""

import collections.abc
import multiprocessing
import os
import sys
import unittest
from unittest import mock

from admin_scripts.tests import AdminScriptTestCase

from django import db
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError, SystemCheckError
from django.test import SimpleTestCase, TransactionTestCase, skipUnlessDBFeature
from django.test.runner import (
    DiscoverRunner,
    Shuffler,
    _init_worker,
    reorder_test_bin,
    reorder_tests,
    shuffle_tests,
)
from django.test.testcases import connections_support_transactions
from django.test.utils import (
    captured_stderr,
    dependency_ordered,
    get_unique_databases_and_mirrors,
    iter_test_cases,
)
from django.utils.version import PY312

from .models import B, Person, Through


class MySuite:
    def __init__(self):
        self.tests = []

    def addTest(self, test):
        self.tests.append(test)

    def __iter__(self):
        yield from self.tests


class TestSuiteTests(SimpleTestCase):
    def build_test_suite(self, test_classes, suite=None, suite_class=None):
        if suite_class is None:
            suite_class = unittest.TestSuite
        if suite is None:
            suite = suite_class()

        loader = unittest.defaultTestLoader
        for test_class in test_classes:
            tests = loader.loadTestsFromTestCase(test_class)
            subsuite = suite_class()
            # Only use addTest() to simplify testing a custom TestSuite.
            for test in tests:
                subsuite.addTest(test)
            suite.addTest(subsuite)

        return suite

    def make_test_suite(self, suite=None, suite_class=None):
        """
        Creates a test suite containing multiple test cases.

        This method constructs a test suite by combining two predefined test case classes, 
        Tests1 and Tests2, which contain test methods test1 and test2. 

        The test suite can be customized by providing a specific suite or suite class.
        The suite and suite_class parameters allow for flexibility in the construction of 
        the test suite, enabling the integration of the generated test cases into a 
        larger testing framework.

        Parameters
        ----------
        suite : object, optional
            A predefined test suite to which the test cases will be added.
        suite_class : class, optional
            A custom test suite class to use for constructing the test suite.

        Returns
        -------
        A test suite containing the combined test cases.

        """
        class Tests1(unittest.TestCase):
            def test1(self):
                pass

            def test2(self):
                pass

        class Tests2(unittest.TestCase):
            def test1(self):
                pass

            def test2(self):
                pass

        return self.build_test_suite(
            (Tests1, Tests2),
            suite=suite,
            suite_class=suite_class,
        )

    def assertTestNames(self, tests, expected):
        # Each test.id() has a form like the following:
        # "test_runner.tests.IterTestCasesTests.test_iter_test_cases.<locals>.Tests1.test1".
        # It suffices to check only the last two parts.
        """

        Verifies that the names of the provided test cases match the expected names.

        This function takes in a list of test cases and a list of expected test names,
        then checks that the actual test names match the expected ones. The actual test
        names are determined by taking the last two components of each test's ID, 
        separated by a dot.

        :param tests: A list of test cases to check.
        :param expected: A list of expected test names.

        """
        names = [".".join(test.id().split(".")[-2:]) for test in tests]
        self.assertEqual(names, expected)

    def test_iter_test_cases_basic(self):
        suite = self.make_test_suite()
        tests = iter_test_cases(suite)
        self.assertTestNames(
            tests,
            expected=[
                "Tests1.test1",
                "Tests1.test2",
                "Tests2.test1",
                "Tests2.test2",
            ],
        )

    def test_iter_test_cases_string_input(self):
        """
        Tests that the iter_test_cases function raises a TypeError when given a string input.

        This test case verifies that the function correctly identifies and handles a string input, 
        which is not a valid test case or test suite. The expected error message is checked to ensure 
        it accurately describes the problem encountered.

        Raises:
            TypeError: If the input to iter_test_cases is a string.

        """
        msg = (
            "Test 'a' must be a test case or test suite not string (was found "
            "in 'abc')."
        )
        with self.assertRaisesMessage(TypeError, msg):
            list(iter_test_cases("abc"))

    def test_iter_test_cases_iterable_of_tests(self):
        """

        Iterates over a list of test cases and yields each test case.

        This function takes an iterable of test cases as input and returns an iterator 
        that yields each test case individually. It is designed to work with test cases 
        loaded using unittest's default test loader.

        The function is useful when you need to process each test case separately, 
        such as when checking the names of the test cases or filtering out certain tests.

        :returns: An iterator over the test cases in the input iterable.
        :rtype: iterator

        """
        class Tests(unittest.TestCase):
            def test1(self):
                pass

            def test2(self):
                pass

        tests = list(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
        actual_tests = iter_test_cases(tests)
        self.assertTestNames(
            actual_tests,
            expected=[
                "Tests.test1",
                "Tests.test2",
            ],
        )

    def test_iter_test_cases_custom_test_suite_class(self):
        """
        #: Tests iteration over test cases in a custom test suite class.
        #: 
        #: This function verifies that the :func:`iter_test_cases` function correctly 
        #: iterates over test cases in a test suite created with a custom test suite class.
        #: 
        #: The test suite is generated using the :meth:`make_test_suite` method with 
        #: :class:`MySuite` as the suite class. The function then checks if the 
        #: :func:`iter_test_cases` function returns the expected test case names. 
        #: 
        #: :returns: None
        """
        suite = self.make_test_suite(suite_class=MySuite)
        tests = iter_test_cases(suite)
        self.assertTestNames(
            tests,
            expected=[
                "Tests1.test1",
                "Tests1.test2",
                "Tests2.test1",
                "Tests2.test2",
            ],
        )

    def test_iter_test_cases_mixed_test_suite_classes(self):
        """
        Tests that the :func:`iter_test_cases` function correctly iterates over test cases 
        in a mixed test suite containing various test suite classes.

        It verifies that the function returns the expected number of test cases and that 
        the returned test cases are not instances of :class:`unittest.TestSuite`, confirming 
        that the function yields individual test cases rather than nested suites.
        """
        suite = self.make_test_suite(suite=MySuite())
        child_suite = list(suite)[0]
        self.assertNotIsInstance(child_suite, MySuite)
        tests = list(iter_test_cases(suite))
        self.assertEqual(len(tests), 4)
        self.assertNotIsInstance(tests[0], unittest.TestSuite)

    def make_tests(self):
        """Return an iterable of tests."""
        suite = self.make_test_suite()
        return list(iter_test_cases(suite))

    def test_shuffle_tests(self):
        """
        Tests the functionality of shuffling test cases by confirming the output is an iterator and verifying the shuffled test names match the expected order.
        """
        tests = self.make_tests()
        # Choose a seed that shuffles both the classes and methods.
        shuffler = Shuffler(seed=9)
        shuffled_tests = shuffle_tests(tests, shuffler)
        self.assertIsInstance(shuffled_tests, collections.abc.Iterator)
        self.assertTestNames(
            shuffled_tests,
            expected=[
                "Tests2.test1",
                "Tests2.test2",
                "Tests1.test2",
                "Tests1.test1",
            ],
        )

    def test_reorder_test_bin_no_arguments(self):
        tests = self.make_tests()
        reordered_tests = reorder_test_bin(tests)
        self.assertIsInstance(reordered_tests, collections.abc.Iterator)
        self.assertTestNames(
            reordered_tests,
            expected=[
                "Tests1.test1",
                "Tests1.test2",
                "Tests2.test1",
                "Tests2.test2",
            ],
        )

    def test_reorder_test_bin_reverse(self):
        """
        Tests the reorder_test_bin function when reordering tests in reverse order.

        This function checks that the reordered tests are returned as an iterator and 
        that the test order is reversed as expected. The test names are verified to be 
        in the correct reverse order, demonstrating the correct functionality of the 
        reorder_test_bin function when the reverse parameter is set to True.

        :raises AssertionError: If the reordered tests are not an iterator or if the 
                                test names are not in the expected reverse order.
        """
        tests = self.make_tests()
        reordered_tests = reorder_test_bin(tests, reverse=True)
        self.assertIsInstance(reordered_tests, collections.abc.Iterator)
        self.assertTestNames(
            reordered_tests,
            expected=[
                "Tests2.test2",
                "Tests2.test1",
                "Tests1.test2",
                "Tests1.test1",
            ],
        )

    def test_reorder_test_bin_random(self):
        tests = self.make_tests()
        # Choose a seed that shuffles both the classes and methods.
        shuffler = Shuffler(seed=9)
        reordered_tests = reorder_test_bin(tests, shuffler=shuffler)
        self.assertIsInstance(reordered_tests, collections.abc.Iterator)
        self.assertTestNames(
            reordered_tests,
            expected=[
                "Tests2.test1",
                "Tests2.test2",
                "Tests1.test2",
                "Tests1.test1",
            ],
        )

    def test_reorder_test_bin_random_and_reverse(self):
        """
        Tests the reordering of test bins by shuffling and reversing the order of test cases.

        This test case verifies that the reorder_test_bin function correctly rearranges a list of tests
        using a provided shuffler and reorder strategy. It checks that the result is an iterator and
        contains the expected test cases in the correct order after shuffling and reversing.

        The test includes validation to ensure the reordered test cases match the expected output,
        providing confidence in the reorder_test_bin function's ability to correctly reorder test bins.

        """
        tests = self.make_tests()
        # Choose a seed that shuffles both the classes and methods.
        shuffler = Shuffler(seed=9)
        reordered_tests = reorder_test_bin(tests, shuffler=shuffler, reverse=True)
        self.assertIsInstance(reordered_tests, collections.abc.Iterator)
        self.assertTestNames(
            reordered_tests,
            expected=[
                "Tests1.test1",
                "Tests1.test2",
                "Tests2.test2",
                "Tests2.test1",
            ],
        )

    def test_reorder_tests_same_type_consecutive(self):
        """Tests of the same type are made consecutive."""
        tests = self.make_tests()
        # Move the last item to the front.
        tests.insert(0, tests.pop())
        self.assertTestNames(
            tests,
            expected=[
                "Tests2.test2",
                "Tests1.test1",
                "Tests1.test2",
                "Tests2.test1",
            ],
        )
        reordered_tests = reorder_tests(tests, classes=[])
        self.assertTestNames(
            reordered_tests,
            expected=[
                "Tests2.test2",
                "Tests2.test1",
                "Tests1.test1",
                "Tests1.test2",
            ],
        )

    def test_reorder_tests_random(self):
        tests = self.make_tests()
        # Choose a seed that shuffles both the classes and methods.
        shuffler = Shuffler(seed=9)
        reordered_tests = reorder_tests(tests, classes=[], shuffler=shuffler)
        self.assertIsInstance(reordered_tests, collections.abc.Iterator)
        self.assertTestNames(
            reordered_tests,
            expected=[
                "Tests2.test1",
                "Tests2.test2",
                "Tests1.test2",
                "Tests1.test1",
            ],
        )

    def test_reorder_tests_random_mixed_classes(self):
        tests = self.make_tests()
        # Move the last item to the front.
        tests.insert(0, tests.pop())
        shuffler = Shuffler(seed=9)
        self.assertTestNames(
            tests,
            expected=[
                "Tests2.test2",
                "Tests1.test1",
                "Tests1.test2",
                "Tests2.test1",
            ],
        )
        reordered_tests = reorder_tests(tests, classes=[], shuffler=shuffler)
        self.assertTestNames(
            reordered_tests,
            expected=[
                "Tests2.test1",
                "Tests2.test2",
                "Tests1.test2",
                "Tests1.test1",
            ],
        )

    def test_reorder_tests_reverse_with_duplicates(self):
        """

        Reorders test cases to ensure consistent execution order across test suites.

        This function takes a list of test cases, optionally grouped by class, and returns 
        a reordered list to maintain a consistent order of test case execution. The 
        reordering considers test case dependencies and provides the option to reverse the 
        order of test case execution. It also handles test suites with duplicate test cases.

        Two modes of reordering are supported: normal and reverse. In normal mode, test 
        cases are ordered based on their natural sequence. In reverse mode, test cases are 
        executed in reverse order, allowing for testing scenarios where test case 
        dependencies require a specific order of execution.

        The function returns a list of reordered test cases.

        """
        class Tests1(unittest.TestCase):
            def test1(self):
                pass

        class Tests2(unittest.TestCase):
            def test2(self):
                pass

            def test3(self):
                pass

        suite = self.build_test_suite((Tests1, Tests2))
        subsuite = list(suite)[0]
        suite.addTest(subsuite)
        tests = list(iter_test_cases(suite))
        self.assertTestNames(
            tests,
            expected=[
                "Tests1.test1",
                "Tests2.test2",
                "Tests2.test3",
                "Tests1.test1",
            ],
        )
        reordered_tests = reorder_tests(tests, classes=[])
        self.assertTestNames(
            reordered_tests,
            expected=[
                "Tests1.test1",
                "Tests2.test2",
                "Tests2.test3",
            ],
        )
        reordered_tests = reorder_tests(tests, classes=[], reverse=True)
        self.assertTestNames(
            reordered_tests,
            expected=[
                "Tests2.test3",
                "Tests2.test2",
                "Tests1.test1",
            ],
        )


class DependencyOrderingTests(unittest.TestCase):
    def test_simple_dependencies(self):
        raw = [
            ("s1", ("s1_db", ["alpha"])),
            ("s2", ("s2_db", ["bravo"])),
            ("s3", ("s3_db", ["charlie"])),
        ]
        dependencies = {
            "alpha": ["charlie"],
            "bravo": ["charlie"],
        }

        ordered = dependency_ordered(raw, dependencies=dependencies)
        ordered_sigs = [sig for sig, value in ordered]

        self.assertIn("s1", ordered_sigs)
        self.assertIn("s2", ordered_sigs)
        self.assertIn("s3", ordered_sigs)
        self.assertLess(ordered_sigs.index("s3"), ordered_sigs.index("s1"))
        self.assertLess(ordered_sigs.index("s3"), ordered_sigs.index("s2"))

    def test_chained_dependencies(self):
        """
        Tests the functionality of ordering signatures with complex dependencies.
        This test case covers the scenario where there are multiple signatures ('s1', 's2', 's3') 
        that depend on each other through their 'alpha', 'bravo', and 'charlie' dependencies.
        The test asserts that the function `dependency_ordered` correctly orders these signatures 
        based on their dependencies, ensuring that a signature is ordered after all its dependencies.
        """
        raw = [
            ("s1", ("s1_db", ["alpha"])),
            ("s2", ("s2_db", ["bravo"])),
            ("s3", ("s3_db", ["charlie"])),
        ]
        dependencies = {
            "alpha": ["bravo"],
            "bravo": ["charlie"],
        }

        ordered = dependency_ordered(raw, dependencies=dependencies)
        ordered_sigs = [sig for sig, value in ordered]

        self.assertIn("s1", ordered_sigs)
        self.assertIn("s2", ordered_sigs)
        self.assertIn("s3", ordered_sigs)

        # Explicit dependencies
        self.assertLess(ordered_sigs.index("s2"), ordered_sigs.index("s1"))
        self.assertLess(ordered_sigs.index("s3"), ordered_sigs.index("s2"))

        # Implied dependencies
        self.assertLess(ordered_sigs.index("s3"), ordered_sigs.index("s1"))

    def test_multiple_dependencies(self):
        raw = [
            ("s1", ("s1_db", ["alpha"])),
            ("s2", ("s2_db", ["bravo"])),
            ("s3", ("s3_db", ["charlie"])),
            ("s4", ("s4_db", ["delta"])),
        ]
        dependencies = {
            "alpha": ["bravo", "delta"],
            "bravo": ["charlie"],
            "delta": ["charlie"],
        }

        ordered = dependency_ordered(raw, dependencies=dependencies)
        ordered_sigs = [sig for sig, aliases in ordered]

        self.assertIn("s1", ordered_sigs)
        self.assertIn("s2", ordered_sigs)
        self.assertIn("s3", ordered_sigs)
        self.assertIn("s4", ordered_sigs)

        # Explicit dependencies
        self.assertLess(ordered_sigs.index("s2"), ordered_sigs.index("s1"))
        self.assertLess(ordered_sigs.index("s4"), ordered_sigs.index("s1"))
        self.assertLess(ordered_sigs.index("s3"), ordered_sigs.index("s2"))
        self.assertLess(ordered_sigs.index("s3"), ordered_sigs.index("s4"))

        # Implicit dependencies
        self.assertLess(ordered_sigs.index("s3"), ordered_sigs.index("s1"))

    def test_circular_dependencies(self):
        """
        Raises an exception when attempting to order dependencies with a circular dependency.

        This test case checks that the function correctly identifies and handles circular dependencies between components.
        It verifies that an ImproperlyConfigured exception is raised when a circular dependency is detected, preventing 
        infinite loops or unexpected behavior. The test setup includes a list of raw components and their corresponding 
        dependencies, which intentionally contain a circular reference to trigger the exception.
        """
        raw = [
            ("s1", ("s1_db", ["alpha"])),
            ("s2", ("s2_db", ["bravo"])),
        ]
        dependencies = {
            "bravo": ["alpha"],
            "alpha": ["bravo"],
        }

        with self.assertRaises(ImproperlyConfigured):
            dependency_ordered(raw, dependencies=dependencies)

    def test_own_alias_dependency(self):
        raw = [("s1", ("s1_db", ["alpha", "bravo"]))]
        dependencies = {"alpha": ["bravo"]}

        with self.assertRaises(ImproperlyConfigured):
            dependency_ordered(raw, dependencies=dependencies)

        # reordering aliases shouldn't matter
        raw = [("s1", ("s1_db", ["bravo", "alpha"]))]

        with self.assertRaises(ImproperlyConfigured):
            dependency_ordered(raw, dependencies=dependencies)


class MockTestRunner:
    def __init__(self, *args, **kwargs):
        if parallel := kwargs.get("parallel"):
            sys.stderr.write(f"parallel={parallel}")
        if durations := kwargs.get("durations"):
            sys.stderr.write(f"durations={durations}")


MockTestRunner.run_tests = mock.Mock(return_value=[])


class ManageCommandTests(unittest.TestCase):
    def test_custom_test_runner(self):
        """
        Tests the usage of a custom test runner by invoking the test command with a specified test runner and verifying its execution.

        This test confirms that the custom test runner is properly called with the correct arguments when the test command is executed.

        :raises AssertionError: If the custom test runner is not called as expected
        """
        call_command("test", "sites", testrunner="test_runner.tests.MockTestRunner")
        MockTestRunner.run_tests.assert_called_with(("sites",))

    def test_bad_test_runner(self):
        """
        Tests the behavior of the test command when a non-existent test runner is specified.

        This test case checks that an AttributeError is raised when attempting to use a test runner that does not exist.

        :param none:
        :raises AttributeError: If the specified test runner is not a valid module or class.
        :returns: None
        """
        with self.assertRaises(AttributeError):
            call_command("test", "sites", testrunner="test_runner.NonexistentRunner")

    def test_time_recorded(self):
        """
        Tests that the --timing option correctly records and outputs the total execution time of a test run.

        This test case verifies that the timing information is properly displayed when running the test command with the --timing option.

        """
        with captured_stderr() as stderr:
            call_command(
                "test",
                "--timing",
                "sites",
                testrunner="test_runner.tests.MockTestRunner",
            )
        self.assertIn("Total run took", stderr.getvalue())

    @unittest.skipUnless(PY312, "unittest --durations option requires Python 3.12")
    def test_durations(self):
        with captured_stderr() as stderr:
            call_command(
                "test",
                "--durations=10",
                "sites",
                testrunner="test_runner.tests.MockTestRunner",
            )
        self.assertIn("durations=10", stderr.getvalue())

    @unittest.skipIf(PY312, "unittest --durations option requires Python 3.12")
    def test_durations_lt_py312(self):
        msg = "Error: unrecognized arguments: --durations=10"
        with self.assertRaises(CommandError, msg=msg):
            call_command(
                "test",
                "--durations=10",
                "sites",
                testrunner="test_runner.tests.MockTestRunner",
            )


# Isolate from the real environment.
@mock.patch.dict(os.environ, {}, clear=True)
@mock.patch.object(multiprocessing, "cpu_count", return_value=12)
class ManageCommandParallelTests(SimpleTestCase):
    def test_parallel_default(self, *mocked_objects):
        """

        Tests the default behavior of running tests in parallel.

        Verifies that when the '--parallel' option is used with the 'test' command,
        the test runner uses the default number of parallel processes.

        :param mocked_objects: Variable number of mock objects to be used during the test.

        """
        with captured_stderr() as stderr:
            call_command(
                "test",
                "--parallel",
                testrunner="test_runner.tests.MockTestRunner",
            )
        self.assertIn("parallel=12", stderr.getvalue())

    def test_parallel_auto(self, *mocked_objects):
        with captured_stderr() as stderr:
            call_command(
                "test",
                "--parallel=auto",
                testrunner="test_runner.tests.MockTestRunner",
            )
        self.assertIn("parallel=12", stderr.getvalue())

    def test_no_parallel(self, *mocked_objects):
        """
        Tests that running tests without parallelization does not produce any errors.

        This test case invokes the test command with a mock test runner and checks that
        the standard error output is empty, indicating successful test execution without
        any issues related to parallelization.

        :raises AssertionError: If the standard error output is not empty after running
            the test command.

        """
        with captured_stderr() as stderr:
            call_command("test", testrunner="test_runner.tests.MockTestRunner")
        # Parallel is disabled by default.
        self.assertEqual(stderr.getvalue(), "")

    @mock.patch.object(multiprocessing, "get_start_method", return_value="spawn")
    def test_parallel_spawn(self, *mocked_objects):
        """

        Tests the test runner command with parallel execution set to auto, 
        verifying that it defaults to a single process when the spawn start method is used.

        """
        with captured_stderr() as stderr:
            call_command(
                "test",
                "--parallel=auto",
                testrunner="test_runner.tests.MockTestRunner",
            )
        self.assertIn("parallel=1", stderr.getvalue())

    @mock.patch.object(multiprocessing, "get_start_method", return_value="spawn")
    def test_no_parallel_spawn(self, *mocked_objects):
        with captured_stderr() as stderr:
            call_command(
                "test",
                testrunner="test_runner.tests.MockTestRunner",
            )
        self.assertEqual(stderr.getvalue(), "")

    @mock.patch.dict(os.environ, {"DJANGO_TEST_PROCESSES": "7"})
    def test_no_parallel_django_test_processes_env(self, *mocked_objects):
        with captured_stderr() as stderr:
            call_command("test", testrunner="test_runner.tests.MockTestRunner")
        self.assertEqual(stderr.getvalue(), "")

    @mock.patch.dict(os.environ, {"DJANGO_TEST_PROCESSES": "invalid"})
    def test_django_test_processes_env_non_int(self, *mocked_objects):
        """

        Tests that setting the DJANGO_TEST_PROCESSES environment variable to a non-integer value raises a ValueError when running the test command with the --parallel option.

        Verifies that the test command properly handles invalid input for the number of test processes, ensuring robust error handling in this scenario.

        """
        with self.assertRaises(ValueError):
            call_command(
                "test",
                "--parallel",
                testrunner="test_runner.tests.MockTestRunner",
            )

    @mock.patch.dict(os.environ, {"DJANGO_TEST_PROCESSES": "7"})
    def test_django_test_processes_parallel_default(self, *mocked_objects):
        """
        Tests the functionality of setting parallel test processes in Django.

        This test case checks the behavior of the 'test' command when run with the '--parallel' option.
        It verifies that the number of parallel processes defaults to the value specified in the DJANGO_TEST_PROCESSES environment variable.

        The test covers two scenarios: running the 'test' command with the '--parallel' option and with the '--parallel=auto' option.
        In both cases, it ensures that the correct number of parallel processes is used, as indicated by the output on the standard error stream.
        """
        for parallel in ["--parallel", "--parallel=auto"]:
            with self.subTest(parallel=parallel):
                with captured_stderr() as stderr:
                    call_command(
                        "test",
                        parallel,
                        testrunner="test_runner.tests.MockTestRunner",
                    )
                self.assertIn("parallel=7", stderr.getvalue())


class CustomTestRunnerOptionsSettingsTests(AdminScriptTestCase):
    """
    Custom runners can add command line arguments. The runner is specified
    through a settings file.
    """

    def setUp(self):
        """
        Sets up the test environment by calling the parent class's setUp method and configuring custom test runner settings.

        This method is responsible for initializing the test setup and overriding the default test runner with a custom test runner, 'CustomOptionsTestRunner', defined in 'test_runner.runner'. The custom test runner settings are written to a 'settings.py' file.

        Returns:
            None
        """
        super().setUp()
        settings = {
            "TEST_RUNNER": "'test_runner.runner.CustomOptionsTestRunner'",
        }
        self.write_settings("settings.py", sdict=settings)

    def test_default_options(self):
        args = ["test", "--settings=test_project.settings"]
        out, err = self.run_django_admin(args)
        self.assertNoOutput(err)
        self.assertOutput(out, "1:2:3")

    def test_default_and_given_options(self):
        """

        Tests Django admin command with default and given options.

        This test case verifies that the command runs successfully and produces the expected output
        when provided with a combination of default and specified options.
        The test specifically checks that the output matches the expected format, 
        indicating that the command has correctly processed the provided options.

        """
        args = ["test", "--settings=test_project.settings", "--option_b=foo"]
        out, err = self.run_django_admin(args)
        self.assertNoOutput(err)
        self.assertOutput(out, "1:foo:3")

    def test_option_name_and_value_separated(self):
        args = ["test", "--settings=test_project.settings", "--option_b", "foo"]
        out, err = self.run_django_admin(args)
        self.assertNoOutput(err)
        self.assertOutput(out, "1:foo:3")

    def test_all_options_given(self):
        args = [
            "test",
            "--settings=test_project.settings",
            "--option_a=bar",
            "--option_b=foo",
            "--option_c=31337",
        ]
        out, err = self.run_django_admin(args)
        self.assertNoOutput(err)
        self.assertOutput(out, "bar:foo:31337")


class CustomTestRunnerOptionsCmdlineTests(AdminScriptTestCase):
    """
    Custom runners can add command line arguments when the runner is specified
    using --testrunner.
    """

    def setUp(self):
        """
        def setUp(self):
            \"\"\"
            Initializes the test setup by calling the superclass's setup method and 
            configuring settings by writing them to a settings file named 'settings.py'.

            This method is used to prepare the test environment and ensure that the 
            required settings are in place before executing tests.

        """
        super().setUp()
        self.write_settings("settings.py")

    def test_testrunner_option(self):
        args = [
            "test",
            "--testrunner",
            "test_runner.runner.CustomOptionsTestRunner",
            "--option_a=bar",
            "--option_b=foo",
            "--option_c=31337",
        ]
        out, err = self.run_django_admin(args, "test_project.settings")
        self.assertNoOutput(err)
        self.assertOutput(out, "bar:foo:31337")

    def test_testrunner_equals(self):
        """

        Tests the test runner's ability to handle custom options.

        Verifies that the test runner correctly parses and utilizes custom command line options.

        This test confirms that the CustomOptionsTestRunner class properly processes and outputs 
        the provided options (option_a, option_b, option_c) when invoked via the Django admin interface.

        """
        args = [
            "test",
            "--testrunner=test_runner.runner.CustomOptionsTestRunner",
            "--option_a=bar",
            "--option_b=foo",
            "--option_c=31337",
        ]
        out, err = self.run_django_admin(args, "test_project.settings")
        self.assertNoOutput(err)
        self.assertOutput(out, "bar:foo:31337")

    def test_no_testrunner(self):
        """
        Tests that running the Django admin test command with the --testrunner option 
           does not execute any tests and instead displays usage information.

           Verifies that the command does not produce any output, does not encounter any 
           errors, and provides usage instructions in the error message as expected.

        """
        args = ["test", "--testrunner"]
        out, err = self.run_django_admin(args, "test_project.settings")
        self.assertIn("usage", err)
        self.assertNotIn("Traceback", err)
        self.assertNoOutput(out)


class NoInitializeSuiteTestRunnerTests(SimpleTestCase):
    @mock.patch.object(multiprocessing, "get_start_method", return_value="spawn")
    @mock.patch(
        "django.test.runner.ParallelTestSuite.initialize_suite",
        side_effect=Exception("initialize_suite() is called."),
    )
    def test_no_initialize_suite_test_runner(self, *mocked_objects):
        """
        The test suite's initialize_suite() method must always be called when
        using spawn. It cannot rely on a test runner implementation.
        """

        class NoInitializeSuiteTestRunner(DiscoverRunner):
            def setup_test_environment(self, **kwargs):
                return

            def setup_databases(self, **kwargs):
                return

            def run_checks(self, databases):
                return

            def teardown_databases(self, old_config, **kwargs):
                return

            def teardown_test_environment(self, **kwargs):
                return

            def run_suite(self, suite, **kwargs):
                """
                Runs a test suite using the configured test runner.

                Parameters
                ----------
                suite : object
                    The test suite to be executed.
                **kwargs : dict
                    Additional keyword arguments (currently ignored, using default test runner kwargs instead).

                Returns
                -------
                result : object
                    The result of the test suite execution.

                Notes
                -----
                This method is responsible for executing a test suite. It utilizes the test runner 
                configured for this instance, passing in the necessary keyword arguments to the 
                runner. The result of the test suite execution is then returned, allowing for 
                further processing or analysis.

                """
                kwargs = self.get_test_runner_kwargs()
                runner = self.test_runner(**kwargs)
                return runner.run(suite)

        with self.assertRaisesMessage(Exception, "initialize_suite() is called."):
            runner = NoInitializeSuiteTestRunner(
                verbosity=0, interactive=False, parallel=2
            )
            runner.run_tests(
                [
                    "test_runner_apps.sample.tests_sample.TestDjangoTestCase",
                    "test_runner_apps.simple.tests",
                ]
            )


class TestRunnerInitializerTests(SimpleTestCase):
    # Raise an exception to don't actually run tests.
    @mock.patch.object(
        multiprocessing, "Pool", side_effect=Exception("multiprocessing.Pool()")
    )
    def test_no_initialize_suite_test_runner(self, mocked_pool):
        """
        Tests the suite test runner when multiprocessing.Pool initialization fails.

        This test ensures that the test runner correctly handles the exception raised when
        multiprocessing Pool cannot be initialized. It verifies that the initializer and
        arguments passed to the Pool are correct, and that the exception is properly propagated.

        The test case uses a stubbed test runner and patches the multiprocessing Pool to
        simulate the failure. It checks that the test runner raises the expected exception
        with the correct message, and that the mocked Pool is called with the correct arguments.

        """
        class StubTestRunner(DiscoverRunner):
            def setup_test_environment(self, **kwargs):
                return

            def setup_databases(self, **kwargs):
                return

            def run_checks(self, databases):
                return

            def teardown_databases(self, old_config, **kwargs):
                return

            def teardown_test_environment(self, **kwargs):
                return

            def run_suite(self, suite, **kwargs):
                kwargs = self.get_test_runner_kwargs()
                runner = self.test_runner(**kwargs)
                return runner.run(suite)

        runner = StubTestRunner(
            verbosity=0, interactive=False, parallel=2, debug_mode=True
        )
        with self.assertRaisesMessage(Exception, "multiprocessing.Pool()"):
            runner.run_tests(
                [
                    "test_runner_apps.sample.tests_sample.TestDjangoTestCase",
                    "test_runner_apps.simple.tests",
                ]
            )
        # Initializer must be a function.
        self.assertIs(mocked_pool.call_args.kwargs["initializer"], _init_worker)
        initargs = mocked_pool.call_args.kwargs["initargs"]
        self.assertEqual(len(initargs), 7)
        self.assertEqual(initargs[5], True)  # debug_mode
        self.assertEqual(initargs[6], {db.DEFAULT_DB_ALIAS})  # Used database aliases.


class Ticket17477RegressionTests(AdminScriptTestCase):
    def setUp(self):
        super().setUp()
        self.write_settings("settings.py")

    def test_ticket_17477(self):
        """'manage.py help test' works after r16352."""
        args = ["help", "test"]
        out, err = self.run_manage(args)
        self.assertNoOutput(err)


class SQLiteInMemoryTestDbs(TransactionTestCase):
    available_apps = ["test_runner"]
    databases = {"default", "other"}

    @unittest.skipUnless(
        all(db.connections[conn].vendor == "sqlite" for conn in db.connections),
        "This is an sqlite-specific issue",
    )
    def test_transaction_support(self):
        # Assert connections mocking is appropriately applied by preventing
        # any attempts at calling create_test_db on the global connection
        # objects.
        """
        Tests that transaction support detection is not interfered with by setting the 'NAME' or 'TEST' options in the DATABASES setting to sqlite3's ':memory:' value.

            The test covers the cases where the 'NAME' or 'TEST' options are set to ':memory:' for sqlite3 databases and verifies that transaction support is correctly detected for the 'other' database connection.

            The test uses a mock patch to prevent the global connection object from being manipulated and sets up test databases with the specified options. It then checks that transaction support is enabled for the 'other' connection and that the connections support transactions.

            This test is specific to sqlite databases and is skipped if any non-sqlite databases are being tested.
        """
        for connection in db.connections.all():
            create_test_db = mock.patch.object(
                connection.creation,
                "create_test_db",
                side_effect=AssertionError(
                    "Global connection object shouldn't be manipulated."
                ),
            )
            create_test_db.start()
            self.addCleanup(create_test_db.stop)
        for option_key, option_value in (
            ("NAME", ":memory:"),
            ("TEST", {"NAME": ":memory:"}),
        ):
            tested_connections = db.ConnectionHandler(
                {
                    "default": {
                        "ENGINE": "django.db.backends.sqlite3",
                        option_key: option_value,
                    },
                    "other": {
                        "ENGINE": "django.db.backends.sqlite3",
                        option_key: option_value,
                    },
                }
            )
            with mock.patch("django.test.utils.connections", new=tested_connections):
                other = tested_connections["other"]
                try:
                    new_test_connections = DiscoverRunner(verbosity=0).setup_databases()
                    msg = (
                        f"DATABASES setting '{option_key}' option set to sqlite3's "
                        "':memory:' value shouldn't interfere with transaction support "
                        "detection."
                    )
                    # Transaction support is properly initialized for the
                    # 'other' DB.
                    self.assertTrue(other.features.supports_transactions, msg)
                    # And all the DBs report that they support transactions.
                    self.assertTrue(connections_support_transactions(), msg)
                finally:
                    for test_connection, _, _ in new_test_connections:
                        test_connection._close()


class DummyBackendTest(unittest.TestCase):
    def test_setup_databases(self):
        """
        setup_databases() doesn't fail with dummy database backend.
        """
        tested_connections = db.ConnectionHandler({})
        with mock.patch("django.test.utils.connections", new=tested_connections):
            runner_instance = DiscoverRunner(verbosity=0)
            old_config = runner_instance.setup_databases()
            runner_instance.teardown_databases(old_config)


class AliasedDefaultTestSetupTest(unittest.TestCase):
    def test_setup_aliased_default_database(self):
        """
        setup_databases() doesn't fail when 'default' is aliased
        """
        tested_connections = db.ConnectionHandler(
            {"default": {"NAME": "dummy"}, "aliased": {"NAME": "dummy"}}
        )
        with mock.patch("django.test.utils.connections", new=tested_connections):
            runner_instance = DiscoverRunner(verbosity=0)
            old_config = runner_instance.setup_databases()
            runner_instance.teardown_databases(old_config)


class SetupDatabasesTests(unittest.TestCase):
    def setUp(self):
        self.runner_instance = DiscoverRunner(verbosity=0)

    def test_setup_aliased_databases(self):
        tested_connections = db.ConnectionHandler(
            {
                "default": {
                    "ENGINE": "django.db.backends.dummy",
                    "NAME": "dbname",
                },
                "other": {
                    "ENGINE": "django.db.backends.dummy",
                    "NAME": "dbname",
                },
            }
        )

        with mock.patch(
            "django.db.backends.dummy.base.DatabaseWrapper.creation_class"
        ) as mocked_db_creation:
            with mock.patch("django.test.utils.connections", new=tested_connections):
                old_config = self.runner_instance.setup_databases()
                self.runner_instance.teardown_databases(old_config)
        mocked_db_creation.return_value.destroy_test_db.assert_called_once_with(
            "dbname", 0, False
        )

    def test_setup_test_database_aliases(self):
        """
        The default database must be the first because data migrations
        use the default alias by default.
        """
        tested_connections = db.ConnectionHandler(
            {
                "other": {
                    "ENGINE": "django.db.backends.dummy",
                    "NAME": "dbname",
                },
                "default": {
                    "ENGINE": "django.db.backends.dummy",
                    "NAME": "dbname",
                },
            }
        )
        with mock.patch("django.test.utils.connections", new=tested_connections):
            test_databases, _ = get_unique_databases_and_mirrors()
            self.assertEqual(
                test_databases,
                {
                    ("", "", "django.db.backends.dummy", "test_dbname"): (
                        "dbname",
                        ["default", "other"],
                    ),
                },
            )

    def test_destroy_test_db_restores_db_name(self):
        """

        Tests that the destroy_test_db method correctly restores the original database name.

        Verifies that after creating a test database with a modified name, calling destroy_test_db
        restores the original database name. This ensures that the database is left in its original
        state after the test is completed.

        """
        tested_connections = db.ConnectionHandler(
            {
                "default": {
                    "ENGINE": settings.DATABASES[db.DEFAULT_DB_ALIAS]["ENGINE"],
                    "NAME": "xxx_test_database",
                },
            }
        )
        # Using the real current name as old_name to not mess with the test suite.
        old_name = settings.DATABASES[db.DEFAULT_DB_ALIAS]["NAME"]
        with mock.patch("django.db.connections", new=tested_connections):
            tested_connections["default"].creation.destroy_test_db(
                old_name, verbosity=0, keepdb=True
            )
            self.assertEqual(
                tested_connections["default"].settings_dict["NAME"], old_name
            )

    def test_serialization(self):
        tested_connections = db.ConnectionHandler(
            {
                "default": {
                    "ENGINE": "django.db.backends.dummy",
                },
            }
        )
        with mock.patch(
            "django.db.backends.dummy.base.DatabaseWrapper.creation_class"
        ) as mocked_db_creation:
            with mock.patch("django.test.utils.connections", new=tested_connections):
                self.runner_instance.setup_databases()
        mocked_db_creation.return_value.create_test_db.assert_called_once_with(
            verbosity=0, autoclobber=False, serialize=True, keepdb=False
        )


@skipUnlessDBFeature("supports_sequence_reset")
class AutoIncrementResetTest(TransactionTestCase):
    """
    Creating the same models in different test methods receive the same PK
    values since the sequences are reset before each test method.
    """

    available_apps = ["test_runner"]

    reset_sequences = True

    def _test(self):
        # Regular model
        p = Person.objects.create(first_name="Jack", last_name="Smith")
        self.assertEqual(p.pk, 1)
        # Auto-created many-to-many through model
        p.friends.add(Person.objects.create(first_name="Jacky", last_name="Smith"))
        self.assertEqual(p.friends.through.objects.first().pk, 1)
        # Many-to-many through model
        b = B.objects.create()
        t = Through.objects.create(person=p, b=b)
        self.assertEqual(t.pk, 1)

    def test_autoincrement_reset1(self):
        self._test()

    def test_autoincrement_reset2(self):
        self._test()


class EmptyDefaultDatabaseTest(unittest.TestCase):
    def test_empty_default_database(self):
        """
        An empty default database in settings does not raise an ImproperlyConfigured
        error when running a unit test that does not use a database.
        """
        tested_connections = db.ConnectionHandler({"default": {}})
        with mock.patch("django.db.connections", new=tested_connections):
            connection = tested_connections[db.utils.DEFAULT_DB_ALIAS]
            self.assertEqual(
                connection.settings_dict["ENGINE"], "django.db.backends.dummy"
            )
            connections_support_transactions()


class RunTestsExceptionHandlingTests(unittest.TestCase):
    def test_run_checks_raises(self):
        """
        Teardown functions are run when run_checks() raises SystemCheckError.
        """
        with (
            mock.patch("django.test.runner.DiscoverRunner.setup_test_environment"),
            mock.patch("django.test.runner.DiscoverRunner.setup_databases"),
            mock.patch("django.test.runner.DiscoverRunner.build_suite"),
            mock.patch(
                "django.test.runner.DiscoverRunner.run_checks",
                side_effect=SystemCheckError,
            ),
            mock.patch(
                "django.test.runner.DiscoverRunner.teardown_databases"
            ) as teardown_databases,
            mock.patch(
                "django.test.runner.DiscoverRunner.teardown_test_environment"
            ) as teardown_test_environment,
        ):
            runner = DiscoverRunner(verbosity=0, interactive=False)
            with self.assertRaises(SystemCheckError):
                runner.run_tests(
                    ["test_runner_apps.sample.tests_sample.TestDjangoTestCase"]
                )
            self.assertTrue(teardown_databases.called)
            self.assertTrue(teardown_test_environment.called)

    def test_run_checks_raises_and_teardown_raises(self):
        """
        SystemCheckError is surfaced when run_checks() raises SystemCheckError
        and teardown databases() raises ValueError.
        """
        with (
            mock.patch("django.test.runner.DiscoverRunner.setup_test_environment"),
            mock.patch("django.test.runner.DiscoverRunner.setup_databases"),
            mock.patch("django.test.runner.DiscoverRunner.build_suite"),
            mock.patch(
                "django.test.runner.DiscoverRunner.run_checks",
                side_effect=SystemCheckError,
            ),
            mock.patch(
                "django.test.runner.DiscoverRunner.teardown_databases",
                side_effect=ValueError,
            ) as teardown_databases,
            mock.patch(
                "django.test.runner.DiscoverRunner.teardown_test_environment"
            ) as teardown_test_environment,
        ):
            runner = DiscoverRunner(verbosity=0, interactive=False)
            with self.assertRaises(SystemCheckError):
                runner.run_tests(
                    ["test_runner_apps.sample.tests_sample.TestDjangoTestCase"]
                )
            self.assertTrue(teardown_databases.called)
            self.assertFalse(teardown_test_environment.called)

    def test_run_checks_passes_and_teardown_raises(self):
        """
        Exceptions on teardown are surfaced if no exceptions happen during
        run_checks().
        """
        with (
            mock.patch("django.test.runner.DiscoverRunner.setup_test_environment"),
            mock.patch("django.test.runner.DiscoverRunner.setup_databases"),
            mock.patch("django.test.runner.DiscoverRunner.build_suite"),
            mock.patch("django.test.runner.DiscoverRunner.run_checks"),
            mock.patch(
                "django.test.runner.DiscoverRunner.teardown_databases",
                side_effect=ValueError,
            ) as teardown_databases,
            mock.patch(
                "django.test.runner.DiscoverRunner.teardown_test_environment"
            ) as teardown_test_environment,
        ):
            runner = DiscoverRunner(verbosity=0, interactive=False)
            with self.assertRaises(ValueError):
                # Suppress the output when running TestDjangoTestCase.
                with mock.patch("sys.stderr"):
                    runner.run_tests(
                        ["test_runner_apps.sample.tests_sample.TestDjangoTestCase"]
                    )
            self.assertTrue(teardown_databases.called)
            self.assertFalse(teardown_test_environment.called)
