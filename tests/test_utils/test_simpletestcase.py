import unittest
from io import StringIO
from unittest import mock
from unittest.suite import _DebugResult

from django.test import SimpleTestCase


class ErrorTestCase(SimpleTestCase):
    def raising_test(self):
        """
        Tests that exceptions are properly propagated during the debug process.

        This method verifies that the pre-setup routine has been executed once, and then
        raises an exception to ensure that it is correctly bubbled up before any cleanup
        operations are performed.

        Raises:
            Exception: An exception with a message indicating that the debug process
                should propagate the exception before cleanup.

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
        Isolate a test suite from previous test state to ensure accurate results.

        This function prepares a test suite for execution by cleaning up any inherited state from previous test classes.
        It handles tear-down operations for both the previous class and the module, allowing for a fresh start for the test suite.
        The function takes in a test suite and test result as input, modifying the test suite's state accordingly.
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
        """
        Test the behavior of the test runner when an error occurs during the pre-setup phase.

        This test case verifies that an exception raised in the pre-setup phase results in the
        test being marked as an error and provides the expected error message. It also checks
        that the post-teardown method is not called in the event of a pre-setup error.

        The test runner's error handling is examined by simulating an error in the pre-setup
        phase and then running a test suite with the affected test case. The resulting test
        outcome is verified to ensure that the error is properly reported and that the test
        runner behaves as expected in the presence of a pre-setup error.
        """
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
        Tests the behavior of the test runner when an exception occurs during the post-teardown phase.

        Verifies that the test result reports an error and that the expected functions are called in the correct order.

        Specifically, this test checks that the pre-setup function is called once, the post-teardown function is called once,
        and that the test result contains an error with a traceback indicating the exception that occurred during post-teardown.
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
        """

        Test that a test case marked as skipped does not trigger setup or teardown steps when run in debug mode.

        This test verifies that when a test is skipped, the corresponding setup and teardown methods are not called.
        It also checks that the test case is properly isolated in the debug testing environment.

        The test case creates a test suite with a single test that is expected to be skipped, then runs the test in debug mode.
        It checks that the expected SkipTest exception is raised and that the setup and teardown methods are not called.
        Finally, it ensures that the test case is properly isolated in the debug testing environment.

        """
        test_suite = unittest.TestSuite()
        test_suite.addTest(ErrorTestCase("skipped_test"))
        with self.assertRaisesMessage(unittest.SkipTest, "Skip condition."):
            # This is the same as test_suite.debug().
            result = _DebugResult()
            test_suite.run(result, debug=True)
        self.assertFalse(_post_teardown.called)
        self.assertFalse(_pre_setup.called)
        self.isolate_debug_test(test_suite, result)
