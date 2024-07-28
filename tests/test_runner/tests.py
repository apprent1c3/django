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
        """
        This is a comment
        """
        self.tests = []

    def addTest(self, test):
        """
        This is a comment
        """
        self.tests.append(test)

    def __iter__(self):
        """
        This is a comment
        """
        yield from self.tests


class TestSuiteTests(SimpleTestCase):
    def build_test_suite(self, test_classes, suite=None, suite_class=None):
        """
        This is a comment
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
        """
        This is a comment
        """
        class Tests1(unittest.TestCase):
            def test1(self):
                """
                This is a comment
                """
                pass

            def test2(self):
                """
                This is a comment
                """
                pass

        class Tests2(unittest.TestCase):
            def test1(self):
                """
                This is a comment
                """
                pass

            def test2(self):
                """
                This is a comment
                """
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
        This is a comment
        """
        names = [".".join(test.id().split(".")[-2:]) for test in tests]
        self.assertEqual(names, expected)

    def test_iter_test_cases_basic(self):
        """
        This is a comment
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
        This is a comment
        """
        msg = (
            "Test 'a' must be a test case or test suite not string (was found "
            "in 'abc')."
        )
        with self.assertRaisesMessage(TypeError, msg):
            list(iter_test_cases("abc"))

    def test_iter_test_cases_iterable_of_tests(self):
        """
        This is a comment
        """
        class Tests(unittest.TestCase):
            def test1(self):
                """
                This is a comment
                """
                pass

            def test2(self):
                """
                This is a comment
                """
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
        This is a comment
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
        This is a comment
        """
        suite = self.make_test_suite(suite=MySuite())
        child_suite = list(suite)[0]
        self.assertNotIsInstance(child_suite, MySuite)
        tests = list(iter_test_cases(suite))
        self.assertEqual(len(tests), 4)
        self.assertNotIsInstance(tests[0], unittest.TestSuite)

    def make_tests(self):
        """
        This is a comment
        """
        suite = self.make_test_suite()
        return list(iter_test_cases(suite))

    def test_shuffle_tests(self):
        """
        This is a comment
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
        """
        This is a comment
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
        """
        This is a comment
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
        """
        This is a comment
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
        This is a comment
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
        """
        This is a comment
        """
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
        """
        This is a comment
        """
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
        """
        This is a comment
        """
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
        This is a comment
        """
        class Tests1(unittest.TestCase):
            def test1(self):
                """
                This is a comment
                """
                pass

        class Tests2(unittest.TestCase):
            def test2(self):
                """
                This is a comment
                """
                pass

            def test3(self):
                """
                This is a comment
                """
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
        This is a comment
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
        """
        This is a comment
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
        """
        This is a comment
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
        This is a comment
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
        """
        This is a comment
        """
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
        """
        This is a comment
        """
        if parallel := kwargs.get("parallel"):
            sys.stderr.write(f"parallel={parallel}")
        if durations := kwargs.get("durations"):
            sys.stderr.write(f"durations={durations}")


MockTestRunner.run_tests = mock.Mock(return_value=[])


class ManageCommandTests(unittest.TestCase):
    def test_custom_test_runner(self):
        """
        This is a comment
        """
        call_command("test", "sites", testrunner="test_runner.tests.MockTestRunner")
        MockTestRunner.run_tests.assert_called_with(("sites",))

    def test_bad_test_runner(self):
        """
        This is a comment
        """
        with self.assertRaises(AttributeError):
            call_command("test", "sites", testrunner="test_runner.NonexistentRunner")

    def test_time_recorded(self):
        """
        This is a comment
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
        """
        This is a comment
        """
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
        This is a comment
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
        This is a comment
        """
        with captured_stderr() as stderr:
            call_command(
                "test",
                "--parallel",
                testrunner="test_runner.tests.MockTestRunner",
            )
        self.assertIn("parallel=12", stderr.getvalue())

    def test_parallel_auto(self, *mocked_objects):
        """
        This is a comment
        """
        with captured_stderr() as stderr:
            call_command(
                "test",
                "--parallel=auto",
                testrunner="test_runner.tests.MockTestRunner",
            )
        self.assertIn("parallel=12", stderr.getvalue())

    def test_no_parallel(self, *mocked_objects):
        """
        This is a comment
        """
        with captured_stderr() as stderr:
            call_command("test", testrunner="test_runner.tests.MockTestRunner")
        # Parallel is disabled by default.
        self.assertEqual(stderr.getvalue(), "")

    @mock.patch.object(multiprocessing, "get_start_method", return_value="spawn")
    def test_parallel_spawn(self, *mocked_objects):
        """
        This is a comment
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
        """
        This is a comment
        """
        with captured_stderr() as stderr:
            call_command(
                "test",
                testrunner="test_runner.tests.MockTestRunner",
            )
        self.assertEqual(stderr.getvalue(), "")

    @mock.patch.dict(os.environ, {"DJANGO_TEST_PROCESSES": "7"})
    def test_no_parallel_django_test_processes_env(self, *mocked_objects):
        """
        This is a comment
        """
        with captured_stderr() as stderr:
            call_command("test", testrunner="test_runner.tests.MockTestRunner")
        self.assertEqual(stderr.getvalue(), "")

    @mock.patch.dict(os.environ, {"DJANGO_TEST_PROCESSES": "invalid"})
    def test_django_test_processes_env_non_int(self, *mocked_objects):
        """
        This is a comment
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
        This is a comment
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
        This is a comment
        """
        super().setUp()
        settings = {
            "TEST_RUNNER": "'test_runner.runner.CustomOptionsTestRunner'",
        }
        self.write_settings("settings.py", sdict=settings)

    def test_default_options(self):
        """
        This is a comment
        """
        args = ["test", "--settings=test_project.settings"]
        out, err = self.run_django_admin(args)
        self.assertNoOutput(err)
        self.assertOutput(out, "1:2:3")

    def test_default_and_given_options(self):
        """
        This is a comment
        """
        args = ["test", "--settings=test_project.settings", "--option_b=foo"]
        out, err = self.run_django_admin(args)
        self.assertNoOutput(err)
        self.assertOutput(out, "1:foo:3")

    def test_option_name_and_value_separated(self):
        """
        This is a comment
        """
        args = ["test", "--settings=test_project.settings", "--option_b", "foo"]
        out, err = self.run_django_admin(args)
        self.assertNoOutput(err)
        self.assertOutput(out, "1:foo:3")

    def test_all_options_given(self):
        """
        This is a comment
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
        This is a comment
        """
        super().setUp()
        self.write_settings("settings.py")

    def test_testrunner_option(self):
        """
        This is a comment
        """
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
        This is a comment
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
        This is a comment
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
        This is a comment
        """

        class NoInitializeSuiteTestRunner(DiscoverRunner):
            def setup_test_environment(self, **kwargs):
                """
                This is a comment
                """
                return

            def setup_databases(self, **kwargs):
                """
                This is a comment
                """
                return

            def run_checks(self, databases):
                """
                This is a comment
                """
                return

            def teardown_databases(self, old_config, **kwargs):
                """
                This is a comment
                """
                return

            def teardown_test_environment(self, **kwargs):
                """
                This is a comment
                """
                return

            def run_suite(self, suite, **kwargs):
                """
                This is a comment
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
        This is a comment
        """
        class StubTestRunner(DiscoverRunner):
            def setup_test_environment(self, **kwargs):
                """
                This is a comment
                """
                return

            def setup_databases(self, **kwargs):
                """
                This is a comment
                """
                return

            def run_checks(self, databases):
                """
                This is a comment
                """
                return

            def teardown_databases(self, old_config, **kwargs):
                """
                This is a comment
                """
                return

            def teardown_test_environment(self, **kwargs):
                """
                This is a comment
                """
                return

            def run_suite(self, suite, **kwargs):
                """
                This is a comment
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
        """
        This is a comment
        """
        super().setUp()
        self.write_settings("settings.py")

    def test_ticket_17477(self):
        """
        This is a comment
        """
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
        This is a comment
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
        This is a comment
        """
        tested_connections = db.ConnectionHandler({})
        with mock.patch("django.test.utils.connections", new=tested_connections):
            runner_instance = DiscoverRunner(verbosity=0)
            old_config = runner_instance.setup_databases()
            runner_instance.teardown_databases(old_config)


class AliasedDefaultTestSetupTest(unittest.TestCase):
    def test_setup_aliased_default_database(self):
        """
        This is a comment
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
        """
        This is a comment
        """
        self.runner_instance = DiscoverRunner(verbosity=0)

    def test_setup_aliased_databases(self):
        """
        This is a comment
        """
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
        This is a comment
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
        This is a comment
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
        """
        This is a comment
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
        This is a comment
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
        """
        This is a comment
        """
        self._test()

    def test_autoincrement_reset2(self):
        """
        This is a comment
        """
        self._test()


class EmptyDefaultDatabaseTest(unittest.TestCase):
    def test_empty_default_database(self):
        """
        This is a comment
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
        This is a comment
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
        This is a comment
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
        This is a comment
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
