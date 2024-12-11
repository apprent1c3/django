import unittest
from io import StringIO
from unittest import mock
from unittest.suite import _DebugResult

from django.test import SimpleTestCase


class ErrorTestCase(SimpleTestCase):
    def raising_test(self):
        """
        Tests the behavior of raising an exception during the execution of a process.

        This function verifies that the pre-setup method has been called exactly once, 
        then intentionally raises an exception to test whether it is properly propagated 
        and handled by the surrounding code, specifically checking if cleanup is performed 
        after the exception is thrown. This ensures that the debug process correctly 
        bubbles up exceptions before any cleanup actions are taken.
        """
        self._pre_setup.assert_called_once_with()
        raise Exception("debug() bubbles up exceptions before cleanup.")

    def simple_test(self):
        self._pre_setup.assert_called_once_with()

    @unittest.skip("Skip condition.")
    def skipped_test(self):
        pass


@mock.patch.object(ErrorTestCase, "_post_teardown")
@mock.patch.object(ErrorTestCase, "_pre_setup")
class DebugInvocationTests(SimpleTestCase):
    def get_runner(self):
        return unittest.TextTestRunner(stream=StringIO())

    def isolate_debug_test(self, test_suite, result):
        # Suite teardown needs to be manually called to isolate failures.
        """

        Isolate a test suite run from previous test executions.

        This method prepares the test suite environment for a new test run by 
        performing necessary teardown operations for the previous class and 
        module. It ensures that any potential side effects from previous tests 
        are cleaned up, allowing for a clean and isolated execution of the 
        current test suite.

        :param test_suite: The test suite to be isolated.
        :param result: The result object to store the outcome of the test suite run.

        """
        test_suite._tearDownPreviousClass(None, result)
        test_suite._handleModuleTearDown(result)

    def test_run_cleanup(self, _pre_setup, _post_teardown):
        """Simple test run: catches errors and runs cleanup."""
        test_suite = unittest.TestSuite()
        test_suite.addTest(ErrorTestCase("raising_test"))
        result = self.get_runner()._makeResult()
        self.assertEqual(result.errors, [])
        test_suite.run(result)
        self.assertEqual(len(result.errors), 1)
        _, traceback = result.errors[0]
        self.assertIn(
            "Exception: debug() bubbles up exceptions before cleanup.", traceback
        )
        _pre_setup.assert_called_once_with()
        _post_teardown.assert_called_once_with()

    def test_run_pre_setup_error(self, _pre_setup, _post_teardown):
        _pre_setup.side_effect = Exception("Exception in _pre_setup.")
        test_suite = unittest.TestSuite()
        test_suite.addTest(ErrorTestCase("simple_test"))
        result = self.get_runner()._makeResult()
        self.assertEqual(result.errors, [])
        test_suite.run(result)
        self.assertEqual(len(result.errors), 1)
        _, traceback = result.errors[0]
        self.assertIn("Exception: Exception in _pre_setup.", traceback)
        # pre-setup is called but not post-teardown.
        _pre_setup.assert_called_once_with()
        self.assertFalse(_post_teardown.called)

    def test_run_post_teardown_error(self, _pre_setup, _post_teardown):
        """

        Tests the test suite's behavior when an error occurs during the post-teardown step.
        Verifies that the test suite correctly captures and reports the exception,
        and that the pre-setup and post-teardown methods are called as expected.

        The test sets up a test suite with a single test case, simulates a failure during the
        post-teardown step by raising an exception, and then runs the test suite.
        It validates that the test result contains the expected error information,
        including the exception message and traceback, and confirms that the setup and teardown
        methods are invoked correctly.

        """
        _post_teardown.side_effect = Exception("Exception in _post_teardown.")
        test_suite = unittest.TestSuite()
        test_suite.addTest(ErrorTestCase("simple_test"))
        result = self.get_runner()._makeResult()
        self.assertEqual(result.errors, [])
        test_suite.run(result)
        self.assertEqual(len(result.errors), 1)
        _, traceback = result.errors[0]
        self.assertIn("Exception: Exception in _post_teardown.", traceback)
        # pre-setup and post-teardwn are called.
        _pre_setup.assert_called_once_with()
        _post_teardown.assert_called_once_with()

    def test_run_skipped_test_no_cleanup(self, _pre_setup, _post_teardown):
        test_suite = unittest.TestSuite()
        test_suite.addTest(ErrorTestCase("skipped_test"))
        try:
            test_suite.run(self.get_runner()._makeResult())
        except unittest.SkipTest:
            self.fail("SkipTest should not be raised at this stage.")
        self.assertFalse(_post_teardown.called)
        self.assertFalse(_pre_setup.called)

    def test_debug_cleanup(self, _pre_setup, _post_teardown):
        """Simple debug run without errors."""
        test_suite = unittest.TestSuite()
        test_suite.addTest(ErrorTestCase("simple_test"))
        test_suite.debug()
        _pre_setup.assert_called_once_with()
        _post_teardown.assert_called_once_with()

    def test_debug_bubbles_error(self, _pre_setup, _post_teardown):
        """debug() bubbles up exceptions before cleanup."""
        test_suite = unittest.TestSuite()
        test_suite.addTest(ErrorTestCase("raising_test"))
        msg = "debug() bubbles up exceptions before cleanup."
        with self.assertRaisesMessage(Exception, msg):
            # This is the same as test_suite.debug().
            result = _DebugResult()
            test_suite.run(result, debug=True)
        # pre-setup is called but not post-teardown.
        _pre_setup.assert_called_once_with()
        self.assertFalse(_post_teardown.called)
        self.isolate_debug_test(test_suite, result)

    def test_debug_bubbles_pre_setup_error(self, _pre_setup, _post_teardown):
        """debug() bubbles up exceptions during _pre_setup."""
        msg = "Exception in _pre_setup."
        _pre_setup.side_effect = Exception(msg)
        test_suite = unittest.TestSuite()
        test_suite.addTest(ErrorTestCase("simple_test"))
        with self.assertRaisesMessage(Exception, msg):
            # This is the same as test_suite.debug().
            result = _DebugResult()
            test_suite.run(result, debug=True)
        # pre-setup is called but not post-teardown.
        _pre_setup.assert_called_once_with()
        self.assertFalse(_post_teardown.called)
        self.isolate_debug_test(test_suite, result)

    def test_debug_bubbles_post_teardown_error(self, _pre_setup, _post_teardown):
        """debug() bubbles up exceptions during _post_teardown."""
        msg = "Exception in _post_teardown."
        _post_teardown.side_effect = Exception(msg)
        test_suite = unittest.TestSuite()
        test_suite.addTest(ErrorTestCase("simple_test"))
        with self.assertRaisesMessage(Exception, msg):
            # This is the same as test_suite.debug().
            result = _DebugResult()
            test_suite.run(result, debug=True)
        # pre-setup and post-teardwn are called.
        _pre_setup.assert_called_once_with()
        _post_teardown.assert_called_once_with()
        self.isolate_debug_test(test_suite, result)

    def test_debug_skipped_test_no_cleanup(self, _pre_setup, _post_teardown):
        test_suite = unittest.TestSuite()
        test_suite.addTest(ErrorTestCase("skipped_test"))
        with self.assertRaisesMessage(unittest.SkipTest, "Skip condition."):
            # This is the same as test_suite.debug().
            result = _DebugResult()
            test_suite.run(result, debug=True)
        self.assertFalse(_post_teardown.called)
        self.assertFalse(_pre_setup.called)
        self.isolate_debug_test(test_suite, result)
