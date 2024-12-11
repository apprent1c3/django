import logging
import multiprocessing
import os
import unittest.loader
from argparse import ArgumentParser
from contextlib import contextmanager
from importlib import import_module
from unittest import TestSuite, TextTestRunner, defaultTestLoader, mock

from django.db import connections
from django.test import SimpleTestCase
from django.test.runner import DiscoverRunner, get_max_test_processes
from django.test.utils import (
    NullTimeKeeper,
    TimeKeeper,
    captured_stderr,
    captured_stdout,
)
from django.utils.version import PY312


@contextmanager
def change_cwd(directory):
    current_dir = os.path.abspath(os.path.dirname(__file__))
    new_dir = os.path.join(current_dir, directory)
    old_cwd = os.getcwd()
    os.chdir(new_dir)
    try:
        yield
    finally:
        os.chdir(old_cwd)


@contextmanager
def change_loader_patterns(patterns):
    original_patterns = DiscoverRunner.test_loader.testNamePatterns
    DiscoverRunner.test_loader.testNamePatterns = patterns
    try:
        yield
    finally:
        DiscoverRunner.test_loader.testNamePatterns = original_patterns


# Isolate from the real environment.
@mock.patch.dict(os.environ, {}, clear=True)
@mock.patch.object(multiprocessing, "cpu_count", return_value=12)
# Python 3.8 on macOS defaults to 'spawn' mode.
@mock.patch.object(multiprocessing, "get_start_method", return_value="fork")
class DiscoverRunnerParallelArgumentTests(SimpleTestCase):
    def get_parser(self):
        parser = ArgumentParser()
        DiscoverRunner.add_arguments(parser)
        return parser

    def test_parallel_default(self, *mocked_objects):
        """
        Tests that the 'parallel' argument defaults to 0 when not provided.

        Verifies that the parser correctly sets the 'parallel' attribute to its default value 
        when no parallel argument is passed to the command line interface. This ensures that 
        the application behaves as expected in the absence of explicit parallelization settings.
        """
        result = self.get_parser().parse_args([])
        self.assertEqual(result.parallel, 0)

    def test_parallel_flag(self, *mocked_objects):
        """
        Tests the '--parallel' command line flag to ensure it is parsed correctly.

        When the '--parallel' flag is provided, this test verifies that the 'parallel' attribute
        is set to 'auto', indicating that parallel processing should be enabled with automatic
        configuration. This test case covers the basic functionality of parsing command line
        arguments related to parallel processing and ensures the expected behavior is achieved.
        """
        result = self.get_parser().parse_args(["--parallel"])
        self.assertEqual(result.parallel, "auto")

    def test_parallel_auto(self, *mocked_objects):
        """
        Test that the '--parallel auto' command line argument is correctly parsed.

        This test case verifies that when the '--parallel auto' option is provided,
        the result of the parsing operation sets the 'parallel' attribute to 'auto',
        indicating that the system should automatically determine the level of parallelism.
        """
        result = self.get_parser().parse_args(["--parallel", "auto"])
        self.assertEqual(result.parallel, "auto")

    def test_parallel_count(self, *mocked_objects):
        result = self.get_parser().parse_args(["--parallel", "17"])
        self.assertEqual(result.parallel, 17)

    def test_parallel_invalid(self, *mocked_objects):
        """

        Tests the parser's handling of invalid parallel argument values.

        Verifies that when an invalid value (neither an integer nor the string 'auto') 
        is provided for the --parallel option, a SystemExit exception is raised with 
        an error message indicating that the value is not acceptable.

        """
        with self.assertRaises(SystemExit), captured_stderr() as stderr:
            self.get_parser().parse_args(["--parallel", "unaccepted"])
        msg = "argument --parallel: 'unaccepted' is not an integer or the string 'auto'"
        self.assertIn(msg, stderr.getvalue())

    def test_get_max_test_processes(self, *mocked_objects):
        self.assertEqual(get_max_test_processes(), 12)

    @mock.patch.dict(os.environ, {"DJANGO_TEST_PROCESSES": "7"})
    def test_get_max_test_processes_env_var(self, *mocked_objects):
        self.assertEqual(get_max_test_processes(), 7)

    def test_get_max_test_processes_spawn(
        self,
        mocked_get_start_method,
        mocked_cpu_count,
    ):
        """

        Tests the get_max_test_processes function to determine the maximum number of test processes.

        This function tests the logic for determining the maximum number of test processes to spawn.
        It covers the default case where the maximum number of test processes is returned as well as
        the scenario where the DJANGO_TEST_PROCESSES environment variable is set, allowing for
        customization of the maximum number of test processes.

        The test verifies that the function returns the correct maximum number of test processes
        based on the system's current configuration and environment settings.

        """
        mocked_get_start_method.return_value = "spawn"
        self.assertEqual(get_max_test_processes(), 12)
        with mock.patch.dict(os.environ, {"DJANGO_TEST_PROCESSES": "7"}):
            self.assertEqual(get_max_test_processes(), 7)

    def test_get_max_test_processes_forkserver(
        self,
        mocked_get_start_method,
        mocked_cpu_count,
    ):
        mocked_get_start_method.return_value = "forkserver"
        self.assertEqual(get_max_test_processes(), 1)
        with mock.patch.dict(os.environ, {"DJANGO_TEST_PROCESSES": "7"}):
            self.assertEqual(get_max_test_processes(), 1)


class DiscoverRunnerTests(SimpleTestCase):
    @staticmethod
    def get_test_methods_names(suite):
        return [t.__class__.__name__ + "." + t._testMethodName for t in suite._tests]

    def test_init_debug_mode(self):
        runner = DiscoverRunner()
        self.assertFalse(runner.debug_mode)

    def test_add_arguments_shuffle(self):
        """

        Tests the addition of the '--shuffle' argument to the command line parser.

        Verifies that the '--shuffle' option is correctly parsed and its value is set 
        accordingly. The default value for '--shuffle' is False when the option is not 
        specified. When '--shuffle' is provided without a value, it is considered as 
        active with no seed specified. When '--shuffle' is provided with an integer 
        value, it is used as the seed for shuffling.

        """
        parser = ArgumentParser()
        DiscoverRunner.add_arguments(parser)
        ns = parser.parse_args([])
        self.assertIs(ns.shuffle, False)
        ns = parser.parse_args(["--shuffle"])
        self.assertIsNone(ns.shuffle)
        ns = parser.parse_args(["--shuffle", "5"])
        self.assertEqual(ns.shuffle, 5)

    def test_add_arguments_debug_mode(self):
        """
        Tests the addition of command line arguments, specifically the --debug-mode flag.

        Verifies that the debug mode is disabled by default when no flags are provided, 
        and enabled when the --debug-mode flag is explicitly passed to the parser. 

        Ensures the correct functionality of the debug mode argument parsing mechanism.
        """
        parser = ArgumentParser()
        DiscoverRunner.add_arguments(parser)

        ns = parser.parse_args([])
        self.assertFalse(ns.debug_mode)
        ns = parser.parse_args(["--debug-mode"])
        self.assertTrue(ns.debug_mode)

    def test_setup_shuffler_no_shuffle_argument(self):
        """
        Tests the setup of the shuffler when no shuffle argument is provided.

        Verifies that the shuffler is initially disabled and that the shuffle seed is
        not set after calling the setup function. This ensures that tests are run in
        a predictable order when shuffling is not explicitly enabled.
        """
        runner = DiscoverRunner()
        self.assertIs(runner.shuffle, False)
        runner.setup_shuffler()
        self.assertIsNone(runner.shuffle_seed)

    def test_setup_shuffler_shuffle_none(self):
        """
        Tests the setup of a shuffler with no seed value provided.

        This test case verifies that the shuffler setup process correctly handles the
        case when no seed value is specified, and that a seed value is automatically
        generated. It checks that the generated seed value is correctly assigned to
        the shuffler and that a corresponding message is printed to the console.

        The test covers the following scenarios:
        - The initial seed value is None
        - The generated seed value is correctly assigned to the runner
        - The correct message is printed to the console with the generated seed value
        """
        runner = DiscoverRunner(shuffle=None)
        self.assertIsNone(runner.shuffle)
        with mock.patch("random.randint", return_value=1):
            with captured_stdout() as stdout:
                runner.setup_shuffler()
        self.assertEqual(stdout.getvalue(), "Using shuffle seed: 1 (generated)\n")
        self.assertEqual(runner.shuffle_seed, 1)

    def test_setup_shuffler_shuffle_int(self):
        runner = DiscoverRunner(shuffle=2)
        self.assertEqual(runner.shuffle, 2)
        with captured_stdout() as stdout:
            runner.setup_shuffler()
        expected_out = "Using shuffle seed: 2 (given)\n"
        self.assertEqual(stdout.getvalue(), expected_out)
        self.assertEqual(runner.shuffle_seed, 2)

    def test_load_tests_for_label_file_path(self):
        """

        Tests that loading tests for a label specified as a file path raises a RuntimeError.

        The function verifies that attempting to load tests using a file path as the label
        will result in an error, as only dotted module names or paths to directories are supported.
        It checks that the expected error message is raised when trying to load tests
        using a file path, ensuring that the test discovery process behaves as expected.

        """
        with change_cwd("."):
            msg = (
                "One of the test labels is a path to a file: "
                "'test_discover_runner.py', which is not supported. Use a "
                "dotted module name or path to a directory instead."
            )
            with self.assertRaisesMessage(RuntimeError, msg):
                DiscoverRunner().load_tests_for_label("test_discover_runner.py", {})

    def test_dotted_test_module(self):
        """
        Tests the discovery of test cases in a module with a dotted path.

        Verifies that the test runner is able to correctly count the number of test cases
        in a module with a dotted path, such as 'test_runner_apps.sample.tests_sample'.
        The test asserts that the expected number of test cases is returned, ensuring
        that the test discovery mechanism is functioning as expected.

        This test case ensures the test runner's ability to discover and count test cases
        in modules that are nested within packages, which is essential for large-scale
        testing frameworks. 

        :raises AssertionError: If the actual test case count does not match the expected count of 4.
        """
        count = (
            DiscoverRunner(verbosity=0)
            .build_suite(
                ["test_runner_apps.sample.tests_sample"],
            )
            .countTestCases()
        )

        self.assertEqual(count, 4)

    def test_dotted_test_class_vanilla_unittest(self):
        count = (
            DiscoverRunner(verbosity=0)
            .build_suite(
                ["test_runner_apps.sample.tests_sample.TestVanillaUnittest"],
            )
            .countTestCases()
        )

        self.assertEqual(count, 1)

    def test_dotted_test_class_django_testcase(self):
        count = (
            DiscoverRunner(verbosity=0)
            .build_suite(
                ["test_runner_apps.sample.tests_sample.TestDjangoTestCase"],
            )
            .countTestCases()
        )

        self.assertEqual(count, 1)

    def test_dotted_test_method_django_testcase(self):
        count = (
            DiscoverRunner(verbosity=0)
            .build_suite(
                ["test_runner_apps.sample.tests_sample.TestDjangoTestCase.test_sample"],
            )
            .countTestCases()
        )

        self.assertEqual(count, 1)

    def test_pattern(self):
        """

        Tests that the test pattern for discovering test cases is correctly implemented.

        This test verifies that the test runner can discover and count test cases based on a given pattern.
        The pattern used is '*_tests.py', which means it will look for files ending with '_tests.py' in the test path.
        The test case count is then compared to an expected value to ensure the pattern is working as expected.

        """
        count = (
            DiscoverRunner(
                pattern="*_tests.py",
                verbosity=0,
            )
            .build_suite(["test_runner_apps.sample"])
            .countTestCases()
        )

        self.assertEqual(count, 1)

    def test_name_patterns(self):
        """
        Tests the test name pattern matching functionality.

        This test case checks that the test name patterns are correctly applied to discover and filter tests.
        It uses various patterns, including exact matches, wildcards, and multiple patterns, to verify that the
        expected tests are included or excluded from the test suite.

        The test covers different scenarios, such as matching tests by name, class, or a combination of both,
        and ensures that the results are as expected.

        Parameters:
            None

        Returns:
            None\"\"\"

        However, looking more closely at the function, it appears to be a test function itself. So a more accurate description would be:

        \"\"\"Tests the DiscoverRunner's test_name_patterns parameter.

        Verifies that the test_name_patterns parameter correctly filters tests based on the provided patterns.
        The test checks various scenarios, including exact matches, wildcards, and multiple patterns, and
        ensures that the resulting test suite includes the expected tests.

        Parameters:
            None

        Returns:
            None
        """
        all_test_1 = [
            "DjangoCase1.test_1",
            "DjangoCase2.test_1",
            "SimpleCase1.test_1",
            "SimpleCase2.test_1",
            "UnittestCase1.test_1",
            "UnittestCase2.test_1",
        ]
        all_test_2 = [
            "DjangoCase1.test_2",
            "DjangoCase2.test_2",
            "SimpleCase1.test_2",
            "SimpleCase2.test_2",
            "UnittestCase1.test_2",
            "UnittestCase2.test_2",
        ]
        all_tests = sorted([*all_test_1, *all_test_2, "UnittestCase2.test_3_test"])
        for pattern, expected in [
            [["test_1"], all_test_1],
            [["UnittestCase1"], ["UnittestCase1.test_1", "UnittestCase1.test_2"]],
            [["*test"], ["UnittestCase2.test_3_test"]],
            [["test*"], all_tests],
            [["test"], all_tests],
            [["test_1", "test_2"], sorted([*all_test_1, *all_test_2])],
            [["test*1"], all_test_1],
        ]:
            with self.subTest(pattern):
                suite = DiscoverRunner(
                    test_name_patterns=pattern,
                    verbosity=0,
                ).build_suite(["test_runner_apps.simple"])
                self.assertEqual(expected, self.get_test_methods_names(suite))

    def test_loader_patterns_not_mutated(self):
        runner = DiscoverRunner(test_name_patterns=["test_sample"], verbosity=0)
        tests = [
            ("test_runner_apps.sample.tests", 1),
            ("test_runner_apps.sample.tests.Test.test_sample", 1),
            ("test_runner_apps.sample.empty", 0),
            ("test_runner_apps.sample.tests_sample.EmptyTestCase", 0),
        ]
        for test_labels, tests_count in tests:
            with self.subTest(test_labels=test_labels):
                with change_loader_patterns(["UnittestCase1"]):
                    count = runner.build_suite([test_labels]).countTestCases()
                    self.assertEqual(count, tests_count)
                    self.assertEqual(
                        runner.test_loader.testNamePatterns, ["UnittestCase1"]
                    )

    def test_loader_patterns_not_mutated_when_test_label_is_file_path(self):
        """

        Tests that the test loader patterns remain unchanged when a test label is provided as a file path.

        This test case verifies that the discovery runner does not modify the test loader patterns 
        even when a test file is explicitly specified for discovery.

        The test ensures that the initial test loader pattern is maintained throughout the discovery process.

        """
        runner = DiscoverRunner(test_name_patterns=["test_sample"], verbosity=0)
        with change_cwd("."), change_loader_patterns(["UnittestCase1"]):
            with self.assertRaises(RuntimeError):
                runner.build_suite(["test_discover_runner.py"])
            self.assertEqual(runner.test_loader.testNamePatterns, ["UnittestCase1"])

    def test_file_path(self):
        """
        Verifies the test file path by counting test cases.

        This test method checks if the correct number of test cases can be discovered 
        in the sample application directory, ensuring the test file path is valid.

        The test counts the total number of test cases found and asserts that the 
        count matches the expected value of 5, confirming the integrity of the test 
        file path and the test discovery process.
        """
        with change_cwd(".."):
            count = (
                DiscoverRunner(verbosity=0)
                .build_suite(
                    ["test_runner_apps/sample/"],
                )
                .countTestCases()
            )

        self.assertEqual(count, 5)

    def test_empty_label(self):
        """
        If the test label is empty, discovery should happen on the current
        working directory.
        """
        with change_cwd("."):
            suite = DiscoverRunner(verbosity=0).build_suite([])
            self.assertEqual(
                suite._tests[0].id().split(".")[0],
                os.path.basename(os.getcwd()),
            )

    def test_empty_test_case(self):
        """
        Tests that a test case with no test methods is correctly reported as having zero test cases. 

        ноп 
        This function utilizes the test discovery mechanism to load a test suite containing a single empty test case, then asserts that the total count of test cases is zero, confirming the test case is properly handled as empty.
        """
        count = (
            DiscoverRunner(verbosity=0)
            .build_suite(
                ["test_runner_apps.sample.tests_sample.EmptyTestCase"],
            )
            .countTestCases()
        )

        self.assertEqual(count, 0)

    def test_discovery_on_package(self):
        """

        Tests the discovery of test cases in a package.

        This test verifies that the test discovery mechanism is able to find and count test cases within a specific package.
        It checks that the correct number of test cases is returned, ensuring that the discovery process is working as expected.

        :return: None

        """
        count = (
            DiscoverRunner(verbosity=0)
            .build_suite(
                ["test_runner_apps.sample.tests"],
            )
            .countTestCases()
        )

        self.assertEqual(count, 1)

    def test_ignore_adjacent(self):
        """
        When given a dotted path to a module, unittest discovery searches
        not just the module, but also the directory containing the module.

        This results in tests from adjacent modules being run when they
        should not. The discover runner avoids this behavior.
        """
        count = (
            DiscoverRunner(verbosity=0)
            .build_suite(
                ["test_runner_apps.sample.empty"],
            )
            .countTestCases()
        )

        self.assertEqual(count, 0)

    def test_testcase_ordering(self):
        """
        Tests the ordering of test cases.

        This test ensures that test cases are ordered correctly when discovered using the DiscoverRunner.
        It checks that TestDjangoTestCase is the first test case, followed by TestZimpleTestCase, 
        and that DocTestCase is also included in the test suite.

        Validates the test discovery and ordering process to guarantee the correct execution of tests.

        """
        with change_cwd(".."):
            suite = DiscoverRunner(verbosity=0).build_suite(
                ["test_runner_apps/sample/"]
            )
            self.assertEqual(
                suite._tests[0].__class__.__name__,
                "TestDjangoTestCase",
                msg="TestDjangoTestCase should be the first test case",
            )
            self.assertEqual(
                suite._tests[1].__class__.__name__,
                "TestZimpleTestCase",
                msg="TestZimpleTestCase should be the second test case",
            )
            # All others can follow in unspecified order, including doctests
            self.assertIn(
                "DocTestCase", [t.__class__.__name__ for t in suite._tests[2:]]
            )

    def test_duplicates_ignored(self):
        """
        Tests shouldn't be discovered twice when discovering on overlapping paths.
        """
        base_app = "forms_tests"
        sub_app = "forms_tests.field_tests"
        runner = DiscoverRunner(verbosity=0)
        with self.modify_settings(INSTALLED_APPS={"append": sub_app}):
            single = runner.build_suite([base_app]).countTestCases()
            dups = runner.build_suite([base_app, sub_app]).countTestCases()
        self.assertEqual(single, dups)

    def test_reverse(self):
        """
        Reverse should reorder tests while maintaining the grouping specified
        by ``DiscoverRunner.reorder_by``.
        """
        runner = DiscoverRunner(reverse=True, verbosity=0)
        suite = runner.build_suite(
            test_labels=("test_runner_apps.sample", "test_runner_apps.simple")
        )
        self.assertIn(
            "test_runner_apps.simple",
            next(iter(suite)).id(),
            msg="Test labels should be reversed.",
        )
        suite = runner.build_suite(test_labels=("test_runner_apps.simple",))
        suite = tuple(suite)
        self.assertIn(
            "DjangoCase", suite[0].id(), msg="Test groups should not be reversed."
        )
        self.assertIn(
            "SimpleCase", suite[4].id(), msg="Test groups order should be preserved."
        )
        self.assertIn(
            "DjangoCase2", suite[0].id(), msg="Django test cases should be reversed."
        )
        self.assertIn(
            "SimpleCase2", suite[4].id(), msg="Simple test cases should be reversed."
        )
        self.assertIn(
            "UnittestCase2",
            suite[8].id(),
            msg="Unittest test cases should be reversed.",
        )
        self.assertIn(
            "test_2", suite[0].id(), msg="Methods of Django cases should be reversed."
        )
        self.assertIn(
            "test_2", suite[4].id(), msg="Methods of simple cases should be reversed."
        )
        self.assertIn(
            "test_2", suite[9].id(), msg="Methods of unittest cases should be reversed."
        )

    def test_build_suite_failed_tests_first(self):
        # The "doesnotexist" label results in a _FailedTest instance.
        """

        Test that the test suite is built with failed tests first.

        This test ensures that when building a test suite with a mix of valid and invalid test labels,
        the invalid tests (i.e., tests that cannot be loaded) are placed at the beginning of the suite.
        The test suite is constructed using the DiscoverRunner with the specified test labels,
        and then validated to confirm that the first test in the suite is a failed test and the last test is not.

        """
        suite = DiscoverRunner(verbosity=0).build_suite(
            test_labels=["test_runner_apps.sample", "doesnotexist"],
        )
        tests = list(suite)
        self.assertIsInstance(tests[0], unittest.loader._FailedTest)
        self.assertNotIsInstance(tests[-1], unittest.loader._FailedTest)

    def test_build_suite_shuffling(self):
        # These will result in unittest.loader._FailedTest instances rather
        # than TestCase objects, but they are sufficient for testing.
        labels = ["label1", "label2", "label3", "label4"]
        cases = [
            ({}, ["label1", "label2", "label3", "label4"]),
            ({"reverse": True}, ["label4", "label3", "label2", "label1"]),
            ({"shuffle": 8}, ["label4", "label1", "label3", "label2"]),
            ({"shuffle": 8, "reverse": True}, ["label2", "label3", "label1", "label4"]),
        ]
        for kwargs, expected in cases:
            with self.subTest(kwargs=kwargs):
                # Prevent writing the seed to stdout.
                runner = DiscoverRunner(**kwargs, verbosity=0)
                tests = runner.build_suite(test_labels=labels)
                # The ids have the form "unittest.loader._FailedTest.label1".
                names = [test.id().split(".")[-1] for test in tests]
                self.assertEqual(names, expected)

    def test_overridable_get_test_runner_kwargs(self):
        self.assertIsInstance(DiscoverRunner().get_test_runner_kwargs(), dict)

    def test_overridable_test_suite(self):
        self.assertEqual(DiscoverRunner().test_suite, TestSuite)

    def test_overridable_test_runner(self):
        self.assertEqual(DiscoverRunner().test_runner, TextTestRunner)

    def test_overridable_test_loader(self):
        self.assertEqual(DiscoverRunner().test_loader, defaultTestLoader)

    def test_tags(self):
        """
        Tests the functionality of test tags.

        This function verifies that the test discovery runner correctly identifies
        and runs tests based on their assigned tags. It checks the number of test cases
        returned for specific tags ('core', 'fast', 'slow') to ensure that the runner
        applies the tags as expected.

        The test covers the scenario where tests are filtered by different tags,
        confirming that the test suite is built accordingly and the correct number of
        test cases is included in each case.
        """
        runner = DiscoverRunner(tags=["core"], verbosity=0)
        self.assertEqual(
            runner.build_suite(["test_runner_apps.tagged.tests"]).countTestCases(), 1
        )
        runner = DiscoverRunner(tags=["fast"], verbosity=0)
        self.assertEqual(
            runner.build_suite(["test_runner_apps.tagged.tests"]).countTestCases(), 2
        )
        runner = DiscoverRunner(tags=["slow"], verbosity=0)
        self.assertEqual(
            runner.build_suite(["test_runner_apps.tagged.tests"]).countTestCases(), 2
        )

    def test_exclude_tags(self):
        runner = DiscoverRunner(tags=["fast"], exclude_tags=["core"], verbosity=0)
        self.assertEqual(
            runner.build_suite(["test_runner_apps.tagged.tests"]).countTestCases(), 1
        )
        runner = DiscoverRunner(tags=["fast"], exclude_tags=["slow"], verbosity=0)
        self.assertEqual(
            runner.build_suite(["test_runner_apps.tagged.tests"]).countTestCases(), 0
        )
        runner = DiscoverRunner(exclude_tags=["slow"], verbosity=0)
        self.assertEqual(
            runner.build_suite(["test_runner_apps.tagged.tests"]).countTestCases(), 0
        )

    def test_tag_inheritance(self):
        """

        Test the inheritance of tags in test cases.

        This test case ensures that the tagging system correctly handles the inheritance
        of tags from parent classes to child classes. It verifies that tests are correctly
        included or excluded based on the tags and excluded tags provided.

        The test checks the following scenarios:

        * Tag inheritance: Tests that a test case with a tag set on a parent class
          is correctly counted when the tag is specified.
        * Exclusion: Verifies that tests are excluded when an excluded tag is specified.
        * Combination: Checks that tests are correctly included or excluded when multiple
          tags and excluded tags are provided.

        """
        def count_tests(**kwargs):
            kwargs.setdefault("verbosity", 0)
            suite = DiscoverRunner(**kwargs).build_suite(
                ["test_runner_apps.tagged.tests_inheritance"]
            )
            return suite.countTestCases()

        self.assertEqual(count_tests(tags=["foo"]), 4)
        self.assertEqual(count_tests(tags=["bar"]), 2)
        self.assertEqual(count_tests(tags=["baz"]), 2)
        self.assertEqual(count_tests(tags=["foo"], exclude_tags=["bar"]), 2)
        self.assertEqual(count_tests(tags=["foo"], exclude_tags=["bar", "baz"]), 1)
        self.assertEqual(count_tests(exclude_tags=["foo"]), 0)

    def test_tag_fail_to_load(self):
        """
        Verifies that the test runner correctly handles tags when a module fails to load due to a syntax error.

        Tests are run with a tag of 'syntax_error' and the verbosity set to 0. The test suite is then built using a non-existent test module and a module with a known syntax error.

        The test checks that the resulting test suite contains the expected failed tests, indicating that the test runner is correctly handling the syntax error and non-existent test module.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the test suite does not contain the expected failed tests.

        """
        with self.assertRaises(SyntaxError):
            import_module("test_runner_apps.tagged.tests_syntax_error")
        runner = DiscoverRunner(tags=["syntax_error"], verbosity=0)
        # A label that doesn't exist or cannot be loaded due to syntax errors
        # is always considered matching.
        suite = runner.build_suite(["doesnotexist", "test_runner_apps.tagged"])
        self.assertEqual(
            [test.id() for test in suite],
            [
                "unittest.loader._FailedTest.doesnotexist",
                "unittest.loader._FailedTest.test_runner_apps.tagged."
                "tests_syntax_error",
            ],
        )

    def test_included_tags_displayed(self):
        """

        Tests that included tags are displayed correctly during test suite discovery.

        This test verifies that when running a test suite with specific tags, the test runner
        correctly displays the included tags. It checks that the tags are listed in the output,
        indicating that they have been successfully included in the test run.

        Checks the output for a message indicating that the specified tags are being included.

        """
        runner = DiscoverRunner(tags=["foo", "bar"], verbosity=2)
        with captured_stdout() as stdout:
            runner.build_suite(["test_runner_apps.tagged.tests"])
            self.assertIn("Including test tag(s): bar, foo.\n", stdout.getvalue())

    def test_excluded_tags_displayed(self):
        """

        Tests that excluded tags are correctly displayed during test suite construction.

        This test case verifies that when excluded tags are specified, a message indicating
        the excluded tags is printed to the console. It checks that the message includes
        the names of the excluded tags, ensuring that the test runner correctly handles
        and reports tag exclusions.

        """
        runner = DiscoverRunner(exclude_tags=["foo", "bar"], verbosity=3)
        with captured_stdout() as stdout:
            runner.build_suite(["test_runner_apps.tagged.tests"])
            self.assertIn("Excluding test tag(s): bar, foo.\n", stdout.getvalue())

    def test_number_of_tests_found_displayed(self):
        runner = DiscoverRunner()
        with captured_stdout() as stdout:
            runner.build_suite(
                [
                    "test_runner_apps.sample.tests_sample.TestDjangoTestCase",
                    "test_runner_apps.simple",
                ]
            )
            self.assertIn("Found 14 test(s).\n", stdout.getvalue())

    def test_pdb_with_parallel(self):
        msg = "You cannot use --pdb with parallel tests; pass --parallel=1 to use it."
        with self.assertRaisesMessage(ValueError, msg):
            DiscoverRunner(pdb=True, parallel=2)

    def test_number_of_parallel_workers(self):
        """Number of processes doesn't exceed the number of TestCases."""
        runner = DiscoverRunner(parallel=5, verbosity=0)
        suite = runner.build_suite(["test_runner_apps.tagged"])
        self.assertEqual(suite.processes, len(suite.subsuites))

    def test_number_of_databases_parallel_test_suite(self):
        """
        Number of databases doesn't exceed the number of TestCases with
        parallel tests.
        """
        runner = DiscoverRunner(parallel=8, verbosity=0)
        suite = runner.build_suite(["test_runner_apps.tagged"])
        self.assertEqual(suite.processes, len(suite.subsuites))
        self.assertEqual(runner.parallel, suite.processes)

    def test_number_of_databases_no_parallel_test_suite(self):
        """
        Number of databases doesn't exceed the number of TestCases with
        non-parallel tests.
        """
        runner = DiscoverRunner(parallel=8, verbosity=0)
        suite = runner.build_suite(["test_runner_apps.simple.tests.DjangoCase1"])
        self.assertEqual(runner.parallel, 1)
        self.assertIsInstance(suite, TestSuite)

    def test_buffer_mode_test_pass(self):
        runner = DiscoverRunner(buffer=True, verbosity=0)
        with captured_stdout() as stdout, captured_stderr() as stderr:
            suite = runner.build_suite(
                [
                    "test_runner_apps.buffer.tests_buffer.WriteToStdoutStderrTestCase."
                    "test_pass",
                ]
            )
            runner.run_suite(suite)
        self.assertNotIn("Write to stderr.", stderr.getvalue())
        self.assertNotIn("Write to stdout.", stdout.getvalue())

    def test_buffer_mode_test_fail(self):
        """
        Tests the buffer mode of the test runner when a test fails.

        This test case runs a single test that writes to both stdout and stderr, then 
        verifies that the output is correctly captured and buffered. It ensures that 
        the test runner correctly handles test failures while running in buffer mode.

        The test checks for the presence of specific messages in the stdout and stderr 
        outputs, confirming that the test runner's buffering is functioning as expected.

        Use this test to ensure the test runner's buffer mode is working correctly and 
        handling test failures as anticipated.
        """
        runner = DiscoverRunner(buffer=True, verbosity=0)
        with captured_stdout() as stdout, captured_stderr() as stderr:
            suite = runner.build_suite(
                [
                    "test_runner_apps.buffer.tests_buffer.WriteToStdoutStderrTestCase."
                    "test_fail",
                ]
            )
            runner.run_suite(suite)
        self.assertIn("Write to stderr.", stderr.getvalue())
        self.assertIn("Write to stdout.", stdout.getvalue())

    def run_suite_with_runner(self, runner_class, **kwargs):
        """

        Run a test suite using a custom test runner class.

        This function utilizes a custom test runner class, which is provided as an argument, 
        to execute a test suite. It sets up a shuffler, runs the suite, and captures both 
        the result and output of the test run.

        The function accepts a test runner class and additional keyword arguments, which 
        are used to configure the test runner. It returns a tuple containing the result of 
        the test run and the captured output.

        Parameters
        ----------
        runner_class : class
            The custom test runner class to use for running the test suite.
        **kwargs
            Additional keyword arguments to pass to the test runner.

        Returns
        -------
        tuple
            A tuple containing the result of the test run and the captured output.

        """
        class MyRunner(DiscoverRunner):
            def test_runner(self, *args, **kwargs):
                return runner_class()

        runner = MyRunner(**kwargs)
        # Suppress logging "Using shuffle seed" to the console.
        with captured_stdout():
            runner.setup_shuffler()
        with captured_stdout() as stdout:
            try:
                result = runner.run_suite(None)
            except RuntimeError as exc:
                result = str(exc)
        output = stdout.getvalue()
        return result, output

    def test_run_suite_logs_seed(self):
        """
        ویPIX
                    Tests the functionality of running a test suite with logging of shuffle seed.

                    Verifies that:
                    - the shuffle seed is not logged when no shuffle seed is provided
                    - the shuffle seed is logged correctly when a shuffle seed is provided
                    - the result of running the test suite is as expected

                    The test uses a fake test runner that returns a predefined result, allowing the test to focus on the logging behavior.
        """
        class TestRunner:
            def run(self, suite):
                return "<fake-result>"

        expected_prefix = "Used shuffle seed"
        # Test with and without shuffling enabled.
        result, output = self.run_suite_with_runner(TestRunner)
        self.assertEqual(result, "<fake-result>")
        self.assertNotIn(expected_prefix, output)

        result, output = self.run_suite_with_runner(TestRunner, shuffle=2)
        self.assertEqual(result, "<fake-result>")
        expected_output = f"{expected_prefix}: 2 (given)\n"
        self.assertEqual(output, expected_output)

    def test_run_suite_logs_seed_exception(self):
        """
        run_suite() logs the seed when TestRunner.run() raises an exception.
        """

        class TestRunner:
            def run(self, suite):
                raise RuntimeError("my exception")

        result, output = self.run_suite_with_runner(TestRunner, shuffle=2)
        self.assertEqual(result, "my exception")
        expected_output = "Used shuffle seed: 2 (given)\n"
        self.assertEqual(output, expected_output)

    @mock.patch("faulthandler.enable")
    def test_faulthandler_enabled(self, mocked_enable):
        """

        Tests that the faulthandler is enabled when running the DiscoverRunner with the enable_faulthandler option set to True.

        The test case verifies that the faulthandler.enable function is called when the DiscoverRunner is initialized with faulthandler enabled, 
        even if the faulthandler is initially disabled.

        This ensures that the DiscoverRunner correctly enables the faulthandler when requested.

        """
        with mock.patch("faulthandler.is_enabled", return_value=False):
            DiscoverRunner(enable_faulthandler=True)
            mocked_enable.assert_called()

    @mock.patch("faulthandler.enable")
    def test_faulthandler_already_enabled(self, mocked_enable):
        with mock.patch("faulthandler.is_enabled", return_value=True):
            DiscoverRunner(enable_faulthandler=True)
            mocked_enable.assert_not_called()

    @mock.patch("faulthandler.enable")
    def test_faulthandler_enabled_fileno(self, mocked_enable):
        # sys.stderr that is not an actual file.
        with (
            mock.patch("faulthandler.is_enabled", return_value=False),
            captured_stderr(),
        ):
            DiscoverRunner(enable_faulthandler=True)
            mocked_enable.assert_called()

    @mock.patch("faulthandler.enable")
    def test_faulthandler_disabled(self, mocked_enable):
        with mock.patch("faulthandler.is_enabled", return_value=False):
            DiscoverRunner(enable_faulthandler=False)
            mocked_enable.assert_not_called()

    def test_timings_not_captured(self):
        runner = DiscoverRunner(timing=False)
        with captured_stderr() as stderr:
            with runner.time_keeper.timed("test"):
                pass
            runner.time_keeper.print_results()
        self.assertIsInstance(runner.time_keeper, NullTimeKeeper)
        self.assertNotIn("test", stderr.getvalue())

    def test_timings_captured(self):
        """
        Tests that timings are correctly captured and reported.

        This test case verifies that the TimeKeeper class is able to track and display 
        execution times for a given test. It confirms that the TimeKeeper instance is 
        properly initialized and that the timing results are printed as expected, 
        including the name of the test being timed. 

        The test also checks the type of the time_keeper attribute to ensure it is an 
        instance of TimeKeeper, and that the test name appears in the output, 
        demonstrating that the timing information is correctly captured and reported.
        """
        runner = DiscoverRunner(timing=True)
        with captured_stderr() as stderr:
            with runner.time_keeper.timed("test"):
                pass
            runner.time_keeper.print_results()
        self.assertIsInstance(runner.time_keeper, TimeKeeper)
        self.assertIn("test", stderr.getvalue())

    def test_log(self):
        custom_low_level = 5
        custom_high_level = 45
        msg = "logging message"
        cases = [
            (0, None, False),
            (0, custom_low_level, False),
            (0, logging.DEBUG, False),
            (0, logging.INFO, False),
            (0, logging.WARNING, False),
            (0, custom_high_level, False),
            (1, None, True),
            (1, custom_low_level, False),
            (1, logging.DEBUG, False),
            (1, logging.INFO, True),
            (1, logging.WARNING, True),
            (1, custom_high_level, True),
            (2, None, True),
            (2, custom_low_level, True),
            (2, logging.DEBUG, True),
            (2, logging.INFO, True),
            (2, logging.WARNING, True),
            (2, custom_high_level, True),
            (3, None, True),
            (3, custom_low_level, True),
            (3, logging.DEBUG, True),
            (3, logging.INFO, True),
            (3, logging.WARNING, True),
            (3, custom_high_level, True),
        ]
        for verbosity, level, output in cases:
            with self.subTest(verbosity=verbosity, level=level):
                with captured_stdout() as stdout:
                    runner = DiscoverRunner(verbosity=verbosity)
                    runner.log(msg, level)
                    self.assertEqual(stdout.getvalue(), f"{msg}\n" if output else "")

    def test_log_logger(self):
        """

        Tests the logging functionality of the logger.

        This test case exercises the logger with various logging levels, ensuring that
        the output matches the expected format for each level. The logging levels tested
        include the built-in levels (e.g., DEBUG, INFO, WARNING) as well as custom levels.

        The test verifies that the logger correctly handles levels specified as integers
        or logging module constants, and that the output contains the expected log level
        name, logger name, and log message.

        The test cases cover the following scenarios:

        * Logging with no level specified (default level)
        * Logging with custom level (integer value)
        * Logging with built-in levels (e.g., DEBUG, INFO, WARNING)

        """
        logger = logging.getLogger("test.logging")
        cases = [
            (None, "INFO:test.logging:log message"),
            # Test a low custom logging level.
            (5, "Level 5:test.logging:log message"),
            (logging.DEBUG, "DEBUG:test.logging:log message"),
            (logging.INFO, "INFO:test.logging:log message"),
            (logging.WARNING, "WARNING:test.logging:log message"),
            # Test a high custom logging level.
            (45, "Level 45:test.logging:log message"),
        ]
        for level, expected in cases:
            with self.subTest(level=level):
                runner = DiscoverRunner(logger=logger)
                # Pass a logging level smaller than the smallest level in cases
                # in order to capture all messages.
                with self.assertLogs("test.logging", level=1) as cm:
                    runner.log("log message", level)
                self.assertEqual(cm.output, [expected])

    def test_suite_result_with_failure(self):
        cases = [
            (1, "FailureTestCase"),
            (1, "ErrorTestCase"),
            (0, "ExpectedFailureTestCase"),
            (1, "UnexpectedSuccessTestCase"),
        ]
        runner = DiscoverRunner(verbosity=0)
        for expected_failures, testcase in cases:
            with self.subTest(testcase=testcase):
                suite = runner.build_suite(
                    [
                        f"test_runner_apps.failures.tests_failures.{testcase}",
                    ]
                )
                with captured_stderr():
                    result = runner.run_suite(suite)
                failures = runner.suite_result(suite, result)
                self.assertEqual(failures, expected_failures)

    @unittest.skipUnless(PY312, "unittest --durations option requires Python 3.12")
    def test_durations(self):
        """

        Tests the functionality of displaying test durations using the DiscoverRunner.

        This test case ensures that the test runner correctly reports the durations of tests 
        when the --durations option is used. It verifies that the output includes the slowest 
        test durations, indicating that the test runner is working as expected with this option.

        The test is skipped unless the Python version is 3.12 or higher, as the --durations 
        option is only available in this version.

        """
        with captured_stderr() as stderr, captured_stdout():
            runner = DiscoverRunner(durations=10)
            suite = runner.build_suite(["test_runner_apps.simple.tests.SimpleCase1"])
            runner.run_suite(suite)
        self.assertIn("Slowest test durations", stderr.getvalue())

    @unittest.skipUnless(PY312, "unittest --durations option requires Python 3.12")
    def test_durations_debug_sql(self):
        """
        Test that the DiscoverRunner properly reports test durations with debug SQL.

        This test case ensures that the DiscoverRunner correctly outputs the slowest test
        durations when the --durations option is used in conjunction with debug SQL.
        It verifies that the runner produces the expected output, including a header
        indicating the slowest test durations, when run with a specified test suite.

        The test also validates that the debug SQL option is correctly enabled, allowing
        for detailed SQL logging during the test execution.

        The output of this test includes the slowest test durations, which can be useful
        for identifying performance bottlenecks in the test suite.

        Requires Python 3.12 or later due to dependency on the unittest --durations option.
        """
        with captured_stderr() as stderr, captured_stdout():
            runner = DiscoverRunner(durations=10, debug_sql=True)
            suite = runner.build_suite(["test_runner_apps.simple.SimpleCase1"])
            runner.run_suite(suite)
        self.assertIn("Slowest test durations", stderr.getvalue())


class DiscoverRunnerGetDatabasesTests(SimpleTestCase):
    runner = DiscoverRunner(verbosity=2)
    skip_msg = "Skipping setup of unused database(s): "

    def get_databases(self, test_labels):
        with captured_stdout() as stdout:
            suite = self.runner.build_suite(test_labels)
            databases = self.runner.get_databases(suite)
        return databases, stdout.getvalue()

    def assertSkippedDatabases(self, test_labels, expected_databases):
        """
        Asserts that the correct databases are skipped based on the provided test labels.

        This function checks that the expected databases are present in the output, and
        that any skipped databases are correctly identified and marked as skipped in the
        output. The function takes a list of test labels and a list of expected databases
        as input, and compares the actual databases returned by the get_databases method
        with the expected databases.

        If any databases are skipped, the function verifies that a skip message is
        present in the output, containing the names of the skipped databases. If no
        databases are skipped, the function checks that the skip message is not present
        in the output.

        Parameters
        ----------
        test_labels : list
            A list of labels for the tests being run.
        expected_databases : list
            A list of databases that are expected to be present.

        Raises
        ------
        AssertionError
            If the actual databases do not match the expected databases, or if the skip
            message is incorrect.

        """
        databases, output = self.get_databases(test_labels)
        self.assertEqual(databases, expected_databases)
        skipped_databases = set(connections) - set(expected_databases)
        if skipped_databases:
            self.assertIn(self.skip_msg + ", ".join(sorted(skipped_databases)), output)
        else:
            self.assertNotIn(self.skip_msg, output)

    def test_mixed(self):
        """

        Tests the configuration of mixed databases.

        Verifies that the function correctly returns a dictionary containing the 
        status of each database, and ensures that the output does not contain 
        a skip message. This test case covers the scenario where the 'default' 
        database is enabled and the 'other' database is disabled.

        """
        databases, output = self.get_databases(["test_runner_apps.databases.tests"])
        self.assertEqual(databases, {"default": True, "other": False})
        self.assertNotIn(self.skip_msg, output)

    def test_all(self):
        databases, output = self.get_databases(
            ["test_runner_apps.databases.tests.AllDatabasesTests"]
        )
        self.assertEqual(databases, {alias: False for alias in connections})
        self.assertNotIn(self.skip_msg, output)

    def test_default_and_other(self):
        self.assertSkippedDatabases(
            [
                "test_runner_apps.databases.tests.DefaultDatabaseTests",
                "test_runner_apps.databases.tests.OtherDatabaseTests",
            ],
            {"default": False, "other": False},
        )

    def test_default_only(self):
        self.assertSkippedDatabases(
            [
                "test_runner_apps.databases.tests.DefaultDatabaseTests",
            ],
            {"default": False},
        )

    def test_other_only(self):
        self.assertSkippedDatabases(
            ["test_runner_apps.databases.tests.OtherDatabaseTests"], {"other": False}
        )

    def test_no_databases_required(self):
        self.assertSkippedDatabases(
            ["test_runner_apps.databases.tests.NoDatabaseTests"], {}
        )

    def test_serialize(self):
        databases, _ = self.get_databases(
            ["test_runner_apps.databases.tests.DefaultDatabaseSerializedTests"]
        )
        self.assertEqual(databases, {"default": True})
