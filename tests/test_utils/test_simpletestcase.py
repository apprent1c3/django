import unittest
from io import StringIO
from unittest import mock
from unittest.suite import _DebugResult

from django.test import SimpleTestCase


class ErrorTestCase(SimpleTestCase):
    def raising_test(self):
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
        test_suite._tearDownPreviousClass(None, result)
        test_suite._handleModuleTearDown(result)

    def test_run_cleanup(self, _pre_setup, _post_teardown):
        """
        Verifies the test run process, ensuring that errors are caught and cleanup is executed as expected, even when exceptions occur during test execution.
        """
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

        Tests that an error raised during a test's pre-setup phase is properly handled.

        Verifies that the error is reported in the test result, and that the post-teardown
        method is not called when pre-setup fails.

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
        Tests that an exception in the post-teardown method is properly reported as a test error.
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
        """
        Tests that a skipped test does not trigger pre-setup or post-teardown when run.
        """
        test_suite = unittest.TestSuite()
        test_suite.addTest(ErrorTestCase("skipped_test"))
        try:
            test_suite.run(self.get_runner()._makeResult())
        except unittest.SkipTest:
            self.fail("SkipTest should not be raised at this stage.")
        self.assertFalse(_post_teardown.called)
        self.assertFalse(_pre_setup.called)

    def test_debug_cleanup(self, _pre_setup, _post_teardown):
        """
        Runs a simple debug test to verify error-free execution and checks that setup and teardown methods are called correctly.
        """
        test_suite = unittest.TestSuite()
        test_suite.addTest(ErrorTestCase("simple_test"))
        test_suite.debug()
        _pre_setup.assert_called_once_with()
        _post_teardown.assert_called_once_with()

    def test_debug_bubbles_error(self, _pre_setup, _post_teardown):
        """
        Tests if debug() correctly propagates exceptions before executing cleanup actions, ensuring test suite interruptions are properly handled.
        """
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
        """
        Tests that debug mode properly propagates exceptions occurring during pre-setup, ensuring they are visible and no teardown is attempted.
        """
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
        """
        Tests that debug mode correctly propagates exceptions raised during test teardown.
        """
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
        Tests that a debug skipped test doesn't trigger setup or teardown hooks.

        Checks that when a test is skipped in debug mode, the pre-setup and post-teardown
        hooks are not called, and cleans up after the test run.
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
