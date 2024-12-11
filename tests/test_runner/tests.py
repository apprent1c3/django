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
        """

        Builds a test suite from a list of test classes.

        The function constructs a test suite by loading tests from each test class and adding them to the suite.
        If a suite is not provided, it will be created using the specified suite class, defaulting to :class:`unittest.TestSuite`.
        The function returns the constructed test suite, which can then be used to run the tests.

        :param test_classes: A list of test classes to include in the suite.
        :param suite: The test suite to add the test classes to, or None to create a new suite.
        :param suite_class: The class to use when creating a new suite, defaulting to :class:`unittest.TestSuite`.
        :returns: The constructed test suite.

        """
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
        Asserts that the names of a list of tests match an expected list of names.

        This function is a helper method for validating the names of tests. It takes a list of tests and an expected list of names,
        and checks that the actual names of the tests match the expected names.

        Args:
            tests (list): A list of test objects.
            expected (list): A list of expected test names.

        Note:
            The test names are extracted from the test objects using the id() method, and are formatted as \"module.name\" strings.

        """
        names = [".".join(test.id().split(".")[-2:]) for test in tests]
        self.assertEqual(names, expected)

    def test_iter_test_cases_basic(self):
        """

        Tests the :func:`iter_test_cases` function to ensure it properly iterates over test cases in a test suite.

        The function verifies that the test cases are yielded in the correct order and that their names match the expected values.

        This test covers a basic scenario where the test suite contains multiple test cases and each test case has a unique name.

        """
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
        Tests that the :func:`iter_test_cases` function raises a :class:`TypeError` when given a string input.

        This test case verifies that the function correctly identifies and rejects string inputs, which are not valid test cases or suites. The expected error message is raised when attempting to iterate over the test cases, ensuring that the function behaves as expected in this scenario.
        """
        msg = (
            "Test 'a' must be a test case or test suite not string (was found "
            "in 'abc')."
        )
        with self.assertRaisesMessage(TypeError, msg):
            list(iter_test_cases("abc"))

    def test_iter_test_cases_iterable_of_tests(self):
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
        Tests the iteration of test cases within a custom test suite class.

        This test function validates that the test cases are correctly iterated 
        over when using a custom test suite class. It checks that all expected 
        test cases are yielded by the iterator, ensuring accurate test discovery 
        and execution in the custom test suite setup.

        The function focuses on verifying the correctness of test case iteration 
        process, specifically in scenarios where a non-standard test suite class 
        is utilized. It provides assurance that the test framework can effectively 
        handle custom test suite configurations, allowing for greater flexibility 
        in test organization and execution.

        :param None
        :returns: None, but validates expected test case names are yielded during iteration
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
        """

        Reorders test cases from test bins to ensure consistent test execution order.

        This function tests that the reorder_test_bin function correctly reorders test cases
        from test bins without providing any arguments. It verifies that the reordered tests
        are returned as an iterator and that the test names are ordered as expected.

        """
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
        """
        Reorders tests in test bin to ensure randomness in test execution.

        This function utilizes a shuffler with a predefined seed to reorder tests.
        It ensures the reordering is done consistently, which is helpful for debugging and regression testing.
        The function returns an iterator of tests in the reordered sequence.
        """
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

        Reorders test cases in a test bin in a randomized and reversed manner.

        This function tests the functionality of reordering test cases by shuffling them 
        using a provided seed, and then reversing their order. It verifies that the 
        resulting reordered test cases are returned as an iterator and that their names 
        match the expected order.

        The purpose of this test is to ensure that the reorder_test_bin function behaves 
        as expected when randomizing and reversing the test cases. The seed used for 
        shuffling is fixed to guarantee reproducibility of the test results.

        :param none:
        :returns: None
        :raises: AssertionError if the reordered test cases are not as expected.

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
        """

        Tests the dependency ordering function with simple dependencies.

        This test case covers the scenario where there are multiple items with different dependencies.
        It checks if the function correctly orders the items based on their dependencies, ensuring that
        an item with no dependencies is ordered after items it depends on.

        """
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
        """

        Test that multiple dependencies are handled correctly.

        This test case verifies that when multiple dependencies are present, 
        the dependency_ordered function returns them in the correct order.
        It checks that all dependencies are included in the result and 
        that their order reflects the specified dependencies.

        """
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
        .. method:: test_circular_dependencies(self)

            Tests whether the dependency ordering function correctly handles circular dependencies.

            This test case simulates a scenario where two services ('s1' and 's2') have dependencies on each other, causing a circular reference.
            It verifies that the :func:`dependency_ordered` function raises an :exc:`ImproperlyConfigured` exception when encountering such a situation, ensuring that the system does not enter an infinite loop or produce incorrect results.
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
        call_command("test", "sites", testrunner="test_runner.tests.MockTestRunner")
        MockTestRunner.run_tests.assert_called_with(("sites",))

    def test_bad_test_runner(self):
        with self.assertRaises(AttributeError):
            call_command("test", "sites", testrunner="test_runner.NonexistentRunner")

    def test_time_recorded(self):
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
        """

        Tests that the --durations option is not supported in Python versions less than 3.12.
        Verifies that calling the test command with the --durations option raises a CommandError
        when running on an unsupported Python version, ensuring backwards compatibility.

        """
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
        Tests that the default parallel value is used when running tests in parallel.

        This function verifies that when the 'test' command is run with the '--parallel' option,
        it uses a default number of parallel processes, which is 12 in this case. The function
        captures the standard error output to check for the expected parallel value.

        :param mocked_objects: variable number of mocked objects to be used in the test
        :raises AssertionError: if the default parallel value is not found in the standard error output
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
        with captured_stderr() as stderr:
            call_command("test", testrunner="test_runner.tests.MockTestRunner")
        # Parallel is disabled by default.
        self.assertEqual(stderr.getvalue(), "")

    @mock.patch.object(multiprocessing, "get_start_method", return_value="spawn")
    def test_parallel_spawn(self, *mocked_objects):
        """

        Tests the parallel spawn functionality of the test command.

        This test case checks that when the '--parallel=auto' option is specified and the 
        'spawn' start method is used, the command runs with a single process in parallel.

        It verifies this by capturing the standard error output and checking for the 
        'parallel=1' message, indicating that the test runner executed with a single 
        process in parallel mode.

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
        with self.assertRaises(ValueError):
            call_command(
                "test",
                "--parallel",
                testrunner="test_runner.tests.MockTestRunner",
            )

    @mock.patch.dict(os.environ, {"DJANGO_TEST_PROCESSES": "7"})
    def test_django_test_processes_parallel_default(self, *mocked_objects):
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
        super().setUp()
        settings = {
            "TEST_RUNNER": "'test_runner.runner.CustomOptionsTestRunner'",
        }
        self.write_settings("settings.py", sdict=settings)

    def test_default_options(self):
        """
        Tests the default options of the Django administration command.

        Verifies that running the Django admin command with the test project settings
        produces the expected output and does not raise any errors.

        The test checks for the absence of error messages and confirms that the output
        matches the predefined format '1:2:3', indicating successful execution with
        default options.

        """
        args = ["test", "--settings=test_project.settings"]
        out, err = self.run_django_admin(args)
        self.assertNoOutput(err)
        self.assertOutput(out, "1:2:3")

    def test_default_and_given_options(self):
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
        """
        Tests that the django admin command successfully executes when all options are provided.

        This test verifies that the command-line arguments are correctly parsed and 
        that the output matches the expected format when options A, B, and C are specified.
        The test also checks that no error messages are generated during command execution.

        The test case covers the following command-line arguments:
        - settings
        - option_a
        - option_b
        - option_c

        A successful test indicates that the command can handle all required options 
        and produce the expected output without any errors.
        """
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
        Sets up the test environment by calling the parent class's setup method and writing the settings to a 'settings.py' file.

        This method is used to prepare the test fixture before executing the test cases. It ensures that the required settings are in place and written to the correct file, allowing the tests to run with the desired configuration.

        Note: This method should be called before executing any test cases to ensure the test environment is properly set up.
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
        Tests the initialization of the test suite runner when using multiprocessing.

        The test verifies that the test suite runner correctly handles an exception
        when attempting to create a multiprocessing pool. Specifically, it checks
        that the correct exception message is raised and that the initializer
        function and initialization arguments are passed correctly to the
        multiprocessing pool.

        This test ensures that the test suite runner is properly configured to use
        multiprocessing and that the necessary setup and teardown methods are called
        correctly.

        The test case covers the following scenarios:

        *   The test suite runner is initialized with verbosity set to 0, interactive
            mode disabled, parallel testing enabled with 2 processes, and debug mode
            enabled.
        *   The test suite runner attempts to run a test suite using multiprocessing.
        *   An exception is raised when creating the multiprocessing pool.
        *   The test verifies that the correct exception message is raised and that
            the initializer function and initialization arguments are passed
            correctly to the multiprocessing pool.

        This test is designed to ensure that the test suite runner is robust and
        handles exceptions properly when using multiprocessing. It provides a
        high-level overview of the test suite runner's behavior and ensures that the
        necessary setup and teardown methods are called correctly. 

        Args:
            None

        Returns:
            None

        Raises:
            Exception: If the multiprocessing pool cannot be created.

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
                """

                Run a suite of tests using the configured test runner.

                This method takes a test suite as input and executes it using the test runner
                configured for this instance. It allows for additional keyword arguments to be
                passed to the test runner, which can be used to customize its behavior.

                The outcome of running the test suite is returned by this method.

                :param suite: The suite of tests to be executed.
                :param kwargs: Additional keyword arguments to be passed to the test runner.
                :return: The outcome of running the test suite.

                """
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
        """

        Tests the serialization process of creating a test database.

        This function verifies that the database creation process correctly calls the 
        serialization method when setting up the test databases. It checks that the 
        create_test_db method is called with the expected parameters, including 
        serialization enabled, keeping the database disabled, and default verbosity 
        and autoclobber settings.

        The test uses mocking to isolate the database creation process and simulate 
        the interaction with the Django database backend.

        """
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
        """
        Tests the creation of relationships between Person objects and other models.

        This test case covers the creation of a Person object, the establishment of friendships,
        and the creation of relationships with model B through the Through model. It verifies
        that the primary keys of the created objects are correctly set and that the relationships
        are properly established.

        The test exercises the following scenarios:
        - Creating a new Person object and checking its primary key
        - Adding a friend to a Person object and verifying the friendship relationship
        - Creating a Through object to establish a relationship between a Person and model B
        - Verifying the primary key of the created Through object
        """
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
