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
        Passing subtests work.
        """
        for i in range(2):
            with self.subTest(index=i):
                self.assertEqual(i, i)


class SampleFailingSubtest(SimpleTestCase):
    # This method name doesn't begin with "test" to prevent test discovery
    # from seeing it.
    def dummy_test(self):
        """
        A dummy test for testing subTest failures.
        """
        for i in range(3):
            with self.subTest(index=i):
                self.assertEqual(i, 1)

    # This method name doesn't begin with "test" to prevent test discovery
    # from seeing it.
    def pickle_error_test(self):
        with self.subTest("TypeError: cannot pickle memoryview object"):
            self.x = memoryview(b"")
            self.fail("expected failure")


class RemoteTestResultTest(SimpleTestCase):
    def _test_error_exc_info(self):
        """
        Returns exception information for a test ValueError exception.

        This method generates a ValueError exception, catches it, and returns the 
        associated exception information as a tuple. The returned tuple contains 
        the type, value, and traceback of the exception, which can be used for 
        further error handling or testing purposes.

        :rtype: tuple
        :returns: A tuple containing the type, value, and traceback of the exception

        """
        try:
            raise ValueError("woops")
        except ValueError:
            return sys.exc_info()

    def test_was_successful_no_events(self):
        """

        Checks if a test was successful when no events have occurred.

        Verifies that the :meth:`wasSuccessful` method of :class:`RemoteTestResult` returns True
        by default, indicating a successful test run, in the absence of any test events.

        """
        result = RemoteTestResult()
        self.assertIs(result.wasSuccessful(), True)

    def test_was_successful_one_success(self):
        """
        Tests that a remote test result is considered successful when at least one test passes.

        This test case verifies the functionality of the `wasSuccessful` method by adding a single successful test result and confirming that the method returns True, indicating that the test run was successful.
        """
        result = RemoteTestResult()
        result.addSuccess(None)
        self.assertIs(result.wasSuccessful(), True)

    def test_was_successful_one_expected_failure(self):
        """

        Tests that a test result is considered successful when there is one expected failure.

        This test case verifies the behavior of the `wasSuccessful` method of the `RemoteTestResult` class.
        It checks that when a single expected failure is recorded, the test result is still considered successful.

        """
        result = RemoteTestResult()
        result.addExpectedFailure(None, self._test_error_exc_info())
        self.assertIs(result.wasSuccessful(), True)

    def test_was_successful_one_skip(self):
        """

        Checks if a test is considered successful when it has only one skipped test case.

        This test case confirms that a test run is deemed successful if all test cases pass 
        or are skipped, and there are no failures or errors. The success of a test run is 
        determined by the presence of failures or errors, rather than the presence of 
        skipped test cases.

        The test verifies that the wasSuccessful method of the test result object returns 
        True when there is only one skipped test case, indicating that the test run as a 
        whole is considered successful.

        """
        result = RemoteTestResult()
        result.addSkip(None, "Skipped")
        self.assertIs(result.wasSuccessful(), True)

    @unittest.skipUnless(tblib is not None, "requires tblib to be installed")
    def test_was_successful_one_error(self):
        """

        Checks the RemoteTestResult wasSuccessful method behavior when a single error occurs.

        This test verifies that a RemoteTestResult instance returns False when an error is added to its result set.
        The test covers the scenario where only one error is reported, confirming that the wasSuccessful method
        accurately reflects the presence of errors in the test result.

        """
        result = RemoteTestResult()
        result.addError(None, self._test_error_exc_info())
        self.assertIs(result.wasSuccessful(), False)

    @unittest.skipUnless(tblib is not None, "requires tblib to be installed")
    def test_was_successful_one_failure(self):
        result = RemoteTestResult()
        result.addFailure(None, self._test_error_exc_info())
        self.assertIs(result.wasSuccessful(), False)

    def test_picklable(self):
        """

        Verifies that RemoteTestResult instances can be serialized and deserialized
        using the pickle module without losing any event data.

        This test ensures that the result object and its events remain intact after
        being pickled and unpickled, which is essential for durable and reliable
        test result storage and retrieval.

        """
        result = RemoteTestResult()
        loaded_result = pickle.loads(pickle.dumps(result))
        self.assertEqual(result.events, loaded_result.events)

    def test_pickle_errors_detection(self):
        """

        Tests the detection of pickling errors in exceptions.

        This test case verifies that the function correctly identifies and handles 
        unpicklable exceptions, raising a TypeError with a descriptive error message 
        when attempting to pickle an exception that fails to unpickle.

        The test covers two scenarios: a picklable exception (RuntimeError) and an 
        unpicklable exception (ExceptionThatFailsUnpickling), ensuring the function 
        behaves as expected in both cases.

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
        Tests the capability to unpickle a subtest that contains an assertion error.

        This test case exercises the RemoteTestResult functionality by running a sample
        subtest that intentionally fails due to a pickle error. The test then verifies
        that the expected failure message is correctly captured and reported in the
        resulting events. The purpose of this test is to ensure that the test framework
        can properly handle and propagate errors from unpicklable subtests, allowing for
        more robust and reliable test execution and reporting.
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
        Failing subtests are added correctly using addSubTest().
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
        Tests the addition of a duration to a RemoteTestResult object.

        This test case verifies that the addDuration method correctly stores the provided duration.
        It checks if the collectedDurations attribute of the result object is updated with the expected value.

        The test is skipped unless running on Python 3.12, as it relies on features not available in earlier versions.
        """
        result = RemoteTestResult()
        result.addDuration(None, 2.3)
        self.assertEqual(result.collectedDurations, [("None", 2.3)])
