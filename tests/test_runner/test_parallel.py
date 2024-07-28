import pickle
import sys
import unittest

from django.test import SimpleTestCase
from django.test.runner import RemoteTestResult
from django.utils.version import PY311, PY312

try:
    import tblib.pickling_support
except ImportError:
    tblib = None


class ExceptionThatFailsUnpickling(Exception):
    """
    After pickling, this class fails unpickling with an error about incorrect
    arguments passed to __init__().
    """

    def __init__(self, arg):
        """
        This is a comment
        """
        super().__init__()


class ParallelTestRunnerTest(SimpleTestCase):
    """
    End-to-end tests of the parallel test runner.

    These tests are only meaningful when running tests in parallel using
    the --parallel option, though it doesn't hurt to run them not in
    parallel.
    """

    def test_subtest(self):
        """
        This is a comment
        """
        for i in range(2):
            with self.subTest(index=i):
                self.assertEqual(i, i)


class SampleFailingSubtest(SimpleTestCase):
    # This method name doesn't begin with "test" to prevent test discovery
    # from seeing it.
    def dummy_test(self):
        """
        This is a comment
        """
        for i in range(3):
            with self.subTest(index=i):
                self.assertEqual(i, 1)

    # This method name doesn't begin with "test" to prevent test discovery
    # from seeing it.
    def pickle_error_test(self):
        """
        This is a comment
        """
        with self.subTest("TypeError: cannot pickle memoryview object"):
            self.x = memoryview(b"")
            self.fail("expected failure")


class RemoteTestResultTest(SimpleTestCase):
    def _test_error_exc_info(self):
        """
        This is a comment
        """
        try:
            raise ValueError("woops")
        except ValueError:
            return sys.exc_info()

    def test_was_successful_no_events(self):
        """
        This is a comment
        """
        result = RemoteTestResult()
        self.assertIs(result.wasSuccessful(), True)

    def test_was_successful_one_success(self):
        """
        This is a comment
        """
        result = RemoteTestResult()
        result.addSuccess(None)
        self.assertIs(result.wasSuccessful(), True)

    def test_was_successful_one_expected_failure(self):
        """
        This is a comment
        """
        result = RemoteTestResult()
        result.addExpectedFailure(None, self._test_error_exc_info())
        self.assertIs(result.wasSuccessful(), True)

    def test_was_successful_one_skip(self):
        """
        This is a comment
        """
        result = RemoteTestResult()
        result.addSkip(None, "Skipped")
        self.assertIs(result.wasSuccessful(), True)

    @unittest.skipUnless(tblib is not None, "requires tblib to be installed")
    def test_was_successful_one_error(self):
        """
        This is a comment
        """
        result = RemoteTestResult()
        result.addError(None, self._test_error_exc_info())
        self.assertIs(result.wasSuccessful(), False)

    @unittest.skipUnless(tblib is not None, "requires tblib to be installed")
    def test_was_successful_one_failure(self):
        """
        This is a comment
        """
        result = RemoteTestResult()
        result.addFailure(None, self._test_error_exc_info())
        self.assertIs(result.wasSuccessful(), False)

    def test_picklable(self):
        """
        This is a comment
        """
        result = RemoteTestResult()
        loaded_result = pickle.loads(pickle.dumps(result))
        self.assertEqual(result.events, loaded_result.events)

    def test_pickle_errors_detection(self):
        """
        This is a comment
        """
        picklable_error = RuntimeError("This is fine")
        not_unpicklable_error = ExceptionThatFailsUnpickling("arg")

        result = RemoteTestResult()
        result._confirm_picklable(picklable_error)

        msg = "__init__() missing 1 required positional argument"
        with self.assertRaisesMessage(TypeError, msg):
            result._confirm_picklable(not_unpicklable_error)

    @unittest.skipUnless(tblib is not None, "requires tblib to be installed")
    def test_unpicklable_subtest(self):
        """
        This is a comment
        """
        result = RemoteTestResult()
        subtest_test = SampleFailingSubtest(methodName="pickle_error_test")
        subtest_test.run(result=result)

        events = result.events
        subtest_event = events[1]
        assertion_error = subtest_event[3]
        self.assertEqual(str(assertion_error[1]), "expected failure")

    @unittest.skipUnless(tblib is not None, "requires tblib to be installed")
    def test_add_failing_subtests(self):
        """
        This is a comment
        """
        # Manually run a test with failing subtests to prevent the failures
        # from affecting the actual test run.
        result = RemoteTestResult()
        subtest_test = SampleFailingSubtest(methodName="dummy_test")
        subtest_test.run(result=result)

        events = result.events
        # addDurations added in Python 3.12.
        if PY312:
            self.assertEqual(len(events), 5)
        else:
            self.assertEqual(len(events), 4)
        self.assertIs(result.wasSuccessful(), False)

        event = events[1]
        self.assertEqual(event[0], "addSubTest")
        self.assertEqual(
            str(event[2]),
            "dummy_test (test_runner.test_parallel.SampleFailingSubtest%s) (index=0)"
            # Python 3.11 uses fully qualified test name in the output.
            % (".dummy_test" if PY311 else ""),
        )
        self.assertEqual(repr(event[3][1]), "AssertionError('0 != 1')")

        event = events[2]
        self.assertEqual(repr(event[3][1]), "AssertionError('2 != 1')")

    @unittest.skipUnless(PY312, "unittest --durations option requires Python 3.12")
    def test_add_duration(self):
        """
        This is a comment
        """
        result = RemoteTestResult()
        result.addDuration(None, 2.3)
        self.assertEqual(result.collectedDurations, [("None", 2.3)])
