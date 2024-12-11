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
    """
    Changes the current working directory to the specified directory within a context, ensuring the original directory is restored upon exit.

        :param directory: The path to the directory to change into, relative to the directory of the current file.
        :yield: A context manager that allows execution of code within the changed directory.
        :note: This context manager is used to temporarily change the working directory and then revert back to the original directory, which is useful for tasks that require changing the directory but need to ensure the original state is preserved afterwards.
    """
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
        result = self.get_parser().parse_args([])
        self.assertEqual(result.parallel, 0)

    def test_parallel_flag(self, *mocked_objects):
        result = self.get_parser().parse_args(["--parallel"])
        self.assertEqual(result.parallel, "auto")

    def test_parallel_auto(self, *mocked_objects):
        result = self.get_parser().parse_args(["--parallel", "auto"])
        self.assertEqual(result.parallel, "auto")

    def test_parallel_count(self, *mocked_objects):
        """

        Test the ability to specify the number of parallel processes.

        This test verifies that the command line interface correctly accepts and parses
        the --parallel option, resulting in the expected number of parallel processes
        being set.

        :raises AssertionError: If the parsed number of parallel processes does not match
            the expected value.

        """
        result = self.get_parser().parse_args(["--parallel", "17"])
        self.assertEqual(result.parallel, 17)

    def test_parallel_invalid(self, *mocked_objects):
        """

        Checks that an invalid value provided to the '--parallel' command line argument raises a SystemExit and displays an error message.

        The test verifies that passing a non-integer and non-'auto' string to '--parallel' results in an error, ensuring the argument is validated correctly.

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
        mocked_get_start_method.return_value = "spawn"
        self.assertEqual(get_max_test_processes(), 12)
        with mock.patch.dict(os.environ, {"DJANGO_TEST_PROCESSES": "7"}):
            self.assertEqual(get_max_test_processes(), 7)

    def test_get_max_test_processes_forkserver(
        self,
        mocked_get_start_method,
        mocked_cpu_count,
    ):
        """

        Tests the get_max_test_processes function when the start method is set to 'forkserver'.

        This test case verifies that the function returns the correct maximum number of test processes
        to run in parallel when the 'forkserver' start method is used. It checks the function's behavior
        with and without the DJANGO_TEST_PROCESSES environment variable set.

        The test ensures that the function adheres to the expected behavior of the 'forkserver' start method,
        which requires a single test process to be run at a time, regardless of the number of available CPUs
        or any override settings provided by the DJANGO_TEST_PROCESSES environment variable.

        """
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
        Subcommand to test the addition of arguments for shuffling to the ArgumentParser.

        This test case verifies the correct functionality of adding the shuffle argument to the parser.
        It checks the default value of the shuffle argument, as well as its value when the --shuffle flag is provided with and without a specified seed.
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
        parser = ArgumentParser()
        DiscoverRunner.add_arguments(parser)

        ns = parser.parse_args([])
        self.assertFalse(ns.debug_mode)
        ns = parser.parse_args(["--debug-mode"])
        self.assertTrue(ns.debug_mode)

    def test_setup_shuffler_no_shuffle_argument(self):
        runner = DiscoverRunner()
        self.assertIs(runner.shuffle, False)
        runner.setup_shuffler()
        self.assertIsNone(runner.shuffle_seed)

    def test_setup_shuffler_shuffle_none(self):
        """

        Tests the setup of a shuffler when no shuffle seed is provided.

        Verifies that when the shuffle parameter is set to None, the shuffler is
        initialized with a randomly generated seed. The test checks that the generated
        seed is used and communicated to the user, and that the shuffle seed attribute
        is correctly updated.

        The test also ensures that the output message indicating the use of a generated
        shuffle seed is correctly displayed.

        """
        runner = DiscoverRunner(shuffle=None)
        self.assertIsNone(runner.shuffle)
        with mock.patch("random.randint", return_value=1):
            with captured_stdout() as stdout:
                runner.setup_shuffler()
        self.assertEqual(stdout.getvalue(), "Using shuffle seed: 1 (generated)\n")
        self.assertEqual(runner.shuffle_seed, 1)

    def test_setup_shuffler_shuffle_int(self):
        """

        Tests the setup of a shuffler with a given integer shuffle seed.

        Verifies that the shuffle seed is correctly set and used, and that the 
        correct message is printed to the console indicating the shuffle seed in use.

        """
        runner = DiscoverRunner(shuffle=2)
        self.assertEqual(runner.shuffle, 2)
        with captured_stdout() as stdout:
            runner.setup_shuffler()
        expected_out = "Using shuffle seed: 2 (given)\n"
        self.assertEqual(stdout.getvalue(), expected_out)
        self.assertEqual(runner.shuffle_seed, 2)

    def test_load_tests_for_label_file_path(self):
        with change_cwd("."):
            msg = (
                "One of the test labels is a path to a file: "
                "'test_discover_runner.py', which is not supported. Use a "
                "dotted module name or path to a directory instead."
            )
            with self.assertRaisesMessage(RuntimeError, msg):
                DiscoverRunner().load_tests_for_label("test_discover_runner.py", {})

    def test_dotted_test_module(self):
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
        """
        Tests that a Django TestCase is discovered and counted correctly by the test runner.

        This test case ensures that the test discovery process can identify and include
        Django TestCases in the test suite, and that the count of test cases is accurate.

        Verifies that the test runner can build a suite containing a single Django TestCase
        and correctly reports the total number of test cases in the suite as 1.
        """
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
        Tests the pattern used to discover test cases.

        Verifies that exactly one test case is discovered when using the specified pattern,
        ensuring that the test suite is properly configured and test cases are correctly identified.

        Returns:
            None

        Note:
            This test is a sanity check to ensure that the test runner is correctly configured
            to discover and run test cases. It does not verify the actual execution or outcome
            of the test cases themselves.

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
        """
        Verifies that test loader patterns are not modified during test discovery.

        This test ensures that the test loader patterns are not mutated when discovering tests
        using the DiscoverRunner. It checks the count of test cases for different test labels
        with a custom test name pattern, and verifies that the test loader patterns remain
        unchanged after test discovery.

        The test covers various test labels, including test modules, test classes, and test
        methods, to ensure that the test loader patterns are not accidentally modified in
        different scenarios. This helps maintain the expected behavior of the test discovery
        process and prevents unintended test loading or execution. 
        """
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
        runner = DiscoverRunner(test_name_patterns=["test_sample"], verbosity=0)
        with change_cwd("."), change_loader_patterns(["UnittestCase1"]):
            with self.assertRaises(RuntimeError):
                runner.build_suite(["test_discover_runner.py"])
            self.assertEqual(runner.test_loader.testNamePatterns, ["UnittestCase1"])

    def test_file_path(self):
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
        count = (
            DiscoverRunner(verbosity=0)
            .build_suite(
                ["test_runner_apps.sample.tests_sample.EmptyTestCase"],
            )
            .countTestCases()
        )

        self.assertEqual(count, 0)

    def test_discovery_on_package(self):
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
        def count_tests(**kwargs):
            """

            Counts the number of test cases in the test suite.

            This function uses the DiscoverRunner to discover and build a test suite from the 'test_runner_apps.tagged.tests_inheritance' module.
            The suite is then used to count the total number of test cases.

            The function accepts keyword arguments that can be used to customize the discovery process, with 'verbosity' being a supported option.
            The 'verbosity' argument controls the level of detail in the output, with 0 being the default.

            :returns: The total number of test cases in the suite.

            """
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
        runner = DiscoverRunner(tags=["foo", "bar"], verbosity=2)
        with captured_stdout() as stdout:
            runner.build_suite(["test_runner_apps.tagged.tests"])
            self.assertIn("Including test tag(s): bar, foo.\n", stdout.getvalue())

    def test_excluded_tags_displayed(self):
        """

        Tests that the excluded tags are correctly displayed when running the test suite.

        This function verifies that when tags are excluded from the test run, a message is printed to the console indicating which tags are being excluded. The purpose of this test is to ensure that the user is informed about the excluded tags, providing transparency and clarity during the testing process.

        The test checks for the presence of a specific message in the console output, confirming that the excluded tags are properly processed and reported.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the expected message is not found in the console output.

        """
        runner = DiscoverRunner(exclude_tags=["foo", "bar"], verbosity=3)
        with captured_stdout() as stdout:
            runner.build_suite(["test_runner_apps.tagged.tests"])
            self.assertIn("Excluding test tag(s): bar, foo.\n", stdout.getvalue())

    def test_number_of_tests_found_displayed(self):
        """

        Tests that the correct number of tests found is displayed when building a test suite.

        Verifies that the test runner correctly counts and reports the total number of tests
        found in the specified test modules and apps. The test checks the output of the test
        runner for the expected message indicating the number of tests discovered.

        The test case ensures that the test runner's output accurately reflects the number
        of tests available for execution, which is crucial for users to understand the scope
        of testing and for test automation workflows.

        """
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
        """
        Test that using --pdb with parallel tests raises a ValueError.

        This test case checks that when attempting to run tests in parallel with the
        pdb flag enabled, a ValueError is raised with a message indicating that --pdb
        cannot be used with parallel tests, and suggesting a workaround by setting
        --parallel=1. This ensures that the test runner behaves correctly when
        encountering conflicting configuration options.

        :raises: ValueError if --pdb is used with parallel tests
        """
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
        """

        Tests that the buffer mode in the test runner correctly suppresses output to stdout and stderr.

        This test case verifies that when the test runner is run with buffer mode enabled,
        it prevents test cases from printing to the console, ensuring that the output
        remains clean and only displays the test results.

        """
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
        Tests the behavior of the test runner when running a test suite in buffer mode and a test fails.
        The purpose of this test is to verify that output written to both stdout and stderr by a failing test is properly captured and available for inspection.
        It checks that the test runner correctly buffers and provides access to the output of the test, even when the test fails.
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

        Tests the behavior of running a test suite with logging of shuffle seed.

        This function verifies that running a test suite without specifying a shuffle seed does not include the seed in the output.
        It also checks that running the suite with a specified shuffle seed correctly logs the seed used.

        The function uses a fake test runner to simulate the test suite execution and checks the result and output for the expected values.

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
        with mock.patch("faulthandler.is_enabled", return_value=False):
            DiscoverRunner(enable_faulthandler=True)
            mocked_enable.assert_called()

    @mock.patch("faulthandler.enable")
    def test_faulthandler_already_enabled(self, mocked_enable):
        """
        Tests that the faulthandler is not enabled when it is already active.

        This test case verifies the behavior of the DiscoverRunner class when the faulthandler is
        previously enabled. It checks that the faulthandler.enable function is not called in this
        scenario, ensuring that the DiscoverRunner class correctly handles the case where the
        faulthandler is already enabled.

        :raises: AssertionError if the faulthandler.enable function is called when it is already enabled
        """
        with mock.patch("faulthandler.is_enabled", return_value=True):
            DiscoverRunner(enable_faulthandler=True)
            mocked_enable.assert_not_called()

    @mock.patch("faulthandler.enable")
    def test_faulthandler_enabled_fileno(self, mocked_enable):
        # sys.stderr that is not an actual file.
        """
        Tests that faulthandler is enabled when DiscoverRunner is created with enable_faulthandler set to True.

        Verifies that the faulthandler.enable function is called when the runner is initialized,
        ensuring that faulthandler is properly set up to handle faults and errors during test execution.

        The test checks the correct behavior by mocking the faulthandler functions and verifying the call to enable faulthandler.
        """
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
        .. method:: test_timings_captured(self)
            Tests whether timings are captured and reported correctly by the test runner.

            This test case verifies that the :class:`DiscoverRunner` can accurately measure 
            and display the execution time of a test. It creates a test runner with timing 
            enabled, runs a timed test, and checks that the timing results are printed to 
            the standard error stream. Additionally, it ensures that the test runner's 
            time keeper is an instance of :class:`TimeKeeper` and that the test name is 
            included in the printed results.
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
        Tests the functionality of the logger within the DiscoverRunner class.

        This test case verifies that log messages are correctly logged at various levels, 
        including custom levels and standard logging levels such as DEBUG, INFO, and WARNING.
        It ensures that the log output matches the expected format for each log level.

        The test covers both valid and invalid log levels, providing comprehensive coverage 
        of the logging functionality.

        Parameters are implicitly checked through the cases array which ensures that different 
        log levels are tested.

        The test utilizes Python's built-in logging module and the assertLogs context manager 
        to capture and verify the log output.

        Each test case is run as a subtest, allowing for detailed reporting of test results 
        and easier identification of any issues that may arise during testing.
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
        with captured_stderr() as stderr, captured_stdout():
            runner = DiscoverRunner(durations=10)
            suite = runner.build_suite(["test_runner_apps.simple.tests.SimpleCase1"])
            runner.run_suite(suite)
        self.assertIn("Slowest test durations", stderr.getvalue())

    @unittest.skipUnless(PY312, "unittest --durations option requires Python 3.12")
    def test_durations_debug_sql(self):
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
        databases, output = self.get_databases(test_labels)
        self.assertEqual(databases, expected_databases)
        skipped_databases = set(connections) - set(expected_databases)
        if skipped_databases:
            self.assertIn(self.skip_msg + ", ".join(sorted(skipped_databases)), output)
        else:
            self.assertNotIn(self.skip_msg, output)

    def test_mixed(self):
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
        """

        Tests the serialization of databases.

        Verifies that the databases are correctly serialized by comparing the 
        resulting dictionary with the expected output. The expected output in 
        this case is a dictionary containing the 'default' key with a value of 
        True, indicating that the 'default' database is properly serialized.

        This test is specifically designed to validate the serialization 
        process for the 'test_runner_apps.databases.tests.DefaultDatabaseSerializedTests' 
        database configuration.

        """
        databases, _ = self.get_databases(
            ["test_runner_apps.databases.tests.DefaultDatabaseSerializedTests"]
        )
        self.assertEqual(databases, {"default": True})
