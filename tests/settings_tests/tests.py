import os
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest import mock

from django.conf import ENVIRONMENT_VARIABLE, LazySettings, Settings, settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from django.test import (
    SimpleTestCase,
    TestCase,
    TransactionTestCase,
    modify_settings,
    override_settings,
    signals,
)
from django.test.utils import requires_tz_support
from django.urls import clear_script_prefix, set_script_prefix


@modify_settings(ITEMS={"prepend": ["b"], "append": ["d"], "remove": ["a", "e"]})
@override_settings(
    ITEMS=["a", "c", "e"], ITEMS_OUTER=[1, 2, 3], TEST="override", TEST_OUTER="outer"
)
class FullyDecoratedTranTestCase(TransactionTestCase):
    available_apps = []

    def test_override(self):
        """
        Tests that specific setting overrides have been successfully applied. 

        This test case verifies the correctness of ITEMs, ITEMS_OUTER, TEST, and TEST_OUTER settings by comparing their values to the expected ones, ensuring that the override functionality works as expected.
        """
        self.assertEqual(settings.ITEMS, ["b", "c", "d"])
        self.assertEqual(settings.ITEMS_OUTER, [1, 2, 3])
        self.assertEqual(settings.TEST, "override")
        self.assertEqual(settings.TEST_OUTER, "outer")

    @modify_settings(
        ITEMS={
            "append": ["e", "f"],
            "prepend": ["a"],
            "remove": ["d", "c"],
        }
    )
    def test_method_list_override(self):
        """
        Tests the modification of settings by overriding the ITEMS list.

        Verifies that the ITEMS list can be modified by appending, prepending, and removing elements.
        The test checks that the modified list is correctly updated, while other settings remain unchanged.

        The expected outcome is that the ITEMS list is updated to include the new elements 'a', 'b', 'e', 'f',
        and that the ITEMS_OUTER list remains unchanged as [1, 2, 3].

        """
        self.assertEqual(settings.ITEMS, ["a", "b", "e", "f"])
        self.assertEqual(settings.ITEMS_OUTER, [1, 2, 3])

    @modify_settings(
        ITEMS={
            "append": ["b"],
            "prepend": ["d"],
            "remove": ["a", "c", "e"],
        }
    )
    def test_method_list_override_no_ops(self):
        self.assertEqual(settings.ITEMS, ["b", "d"])

    @modify_settings(
        ITEMS={
            "append": "e",
            "prepend": "a",
            "remove": "c",
        }
    )
    def test_method_list_override_strings(self):
        self.assertEqual(settings.ITEMS, ["a", "b", "d", "e"])

    @modify_settings(ITEMS={"remove": ["b", "d"]})
    @modify_settings(ITEMS={"append": ["b"], "prepend": ["d"]})
    def test_method_list_override_nested_order(self):
        self.assertEqual(settings.ITEMS, ["d", "c", "b"])

    @override_settings(TEST="override2")
    def test_method_override(self):
        """

        Tests that the override_settings decorator correctly overrides test settings.

        Verifies that the specified settings are overridden to the provided values, while
        leaving other settings unchanged. This ensures that test settings can be isolated
        and modified without affecting the entire application configuration.

        The test checks the override of both the directly modified setting and an outer
        setting to confirm the decorator's functionality.

        """
        self.assertEqual(settings.TEST, "override2")
        self.assertEqual(settings.TEST_OUTER, "outer")

    def test_decorated_testcase_name(self):
        self.assertEqual(
            FullyDecoratedTranTestCase.__name__, "FullyDecoratedTranTestCase"
        )

    def test_decorated_testcase_module(self):
        self.assertEqual(FullyDecoratedTranTestCase.__module__, __name__)


@modify_settings(ITEMS={"prepend": ["b"], "append": ["d"], "remove": ["a", "e"]})
@override_settings(ITEMS=["a", "c", "e"], TEST="override")
class FullyDecoratedTestCase(TestCase):
    def test_override(self):
        """
        Tests to ensure that settings have been successfully overridden.

        This test checks that the ITEMS setting has been updated to contain the expected list of items and that the TEST setting has been overridden to the expected value.

        The test verifies that the changes to the settings have taken effect, ensuring that the application is using the correct configurations.

        It covers two key settings:
            ITEMS: a list of items expected to have been updated to ['b', 'c', 'd']
            TEST: a string setting expected to have been overridden to 'override'

        By passing this test, it confirms that the override functionality is working as expected, allowing for customizable configurations in the application.
        """
        self.assertEqual(settings.ITEMS, ["b", "c", "d"])
        self.assertEqual(settings.TEST, "override")

    @modify_settings(
        ITEMS={
            "append": "e",
            "prepend": "a",
            "remove": "c",
        }
    )
    @override_settings(TEST="override2")
    def test_method_override(self):
        self.assertEqual(settings.ITEMS, ["a", "b", "d", "e"])
        self.assertEqual(settings.TEST, "override2")


class ClassDecoratedTestCaseSuper(TestCase):
    """
    Dummy class for testing max recursion error in child class call to
    super().  Refs #17011.
    """

    def test_max_recursion_error(self):
        pass


@override_settings(TEST="override")
class ClassDecoratedTestCase(ClassDecoratedTestCaseSuper):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.foo = getattr(settings, "TEST", "BUG")

    def test_override(self):
        self.assertEqual(settings.TEST, "override")

    def test_setupclass_override(self):
        """Settings are overridden within setUpClass (#21281)."""
        self.assertEqual(self.foo, "override")

    @override_settings(TEST="override2")
    def test_method_override(self):
        self.assertEqual(settings.TEST, "override2")

    def test_max_recursion_error(self):
        """
        Overriding a method on a super class and then calling that method on
        the super class should not trigger infinite recursion. See #17011.
        """
        super().test_max_recursion_error()


@modify_settings(ITEMS={"append": "mother"})
@override_settings(ITEMS=["father"], TEST="override-parent")
class ParentDecoratedTestCase(TestCase):
    pass


@modify_settings(ITEMS={"append": ["child"]})
@override_settings(TEST="override-child")
class ChildDecoratedTestCase(ParentDecoratedTestCase):
    def test_override_settings_inheritance(self):
        """

        Tests the inheritance and overriding of settings.

        This test case checks that the settings are correctly inherited from parent settings and 
        properly overridden by child settings. It verifies that the ITEMS setting is correctly 
        inherited and the TEST setting is overridden with the expected value.

        """
        self.assertEqual(settings.ITEMS, ["father", "mother", "child"])
        self.assertEqual(settings.TEST, "override-child")


class SettingsTests(SimpleTestCase):
    def setUp(self):
        self.testvalue = None
        signals.setting_changed.connect(self.signal_callback)
        self.addCleanup(signals.setting_changed.disconnect, self.signal_callback)

    def signal_callback(self, sender, setting, value, **kwargs):
        if setting == "TEST":
            self.testvalue = value

    def test_override(self):
        """
        ..: Tests the override functionality of settings by checking if a setting can be temporarily changed and then reverted back to its original value after the override context is closed. 

            This test case covers the following scenarios:
                - sets a setting to a default test value
                - verifies the setting has been updated correctly
                - overrides the setting with a new value within a context
                - checks the new value is applied during the override
                - confirms the original value is restored after the override context is exited
                - deletes the setting after testing to clean up the environment.
        """
        settings.TEST = "test"
        self.assertEqual("test", settings.TEST)
        with self.settings(TEST="override"):
            self.assertEqual("override", settings.TEST)
        self.assertEqual("test", settings.TEST)
        del settings.TEST

    def test_override_change(self):
        settings.TEST = "test"
        self.assertEqual("test", settings.TEST)
        with self.settings(TEST="override"):
            self.assertEqual("override", settings.TEST)
            settings.TEST = "test2"
        self.assertEqual("test", settings.TEST)
        del settings.TEST

    def test_override_doesnt_leak(self):
        """
        Tests that overriding a setting does not persist after the override context is exited.

        Verifies that attempting to access a non-existent setting raises an AttributeError,
        and that a setting can be successfully overridden within a limited scope.
        Additionally, confirms that the original setting is restored after the override
        context has ended, and attempting to access the setting again raises an AttributeError.
        """
        with self.assertRaises(AttributeError):
            getattr(settings, "TEST")
        with self.settings(TEST="override"):
            self.assertEqual("override", settings.TEST)
            settings.TEST = "test"
        with self.assertRaises(AttributeError):
            getattr(settings, "TEST")

    @override_settings(TEST="override")
    def test_decorator(self):
        self.assertEqual("override", settings.TEST)

    def test_context_manager(self):
        with self.assertRaises(AttributeError):
            getattr(settings, "TEST")
        override = override_settings(TEST="override")
        with self.assertRaises(AttributeError):
            getattr(settings, "TEST")
        override.enable()
        self.assertEqual("override", settings.TEST)
        override.disable()
        with self.assertRaises(AttributeError):
            getattr(settings, "TEST")

    def test_class_decorator(self):
        # SimpleTestCase can be decorated by override_settings, but not ut.TestCase
        class SimpleTestCaseSubclass(SimpleTestCase):
            pass

        class UnittestTestCaseSubclass(unittest.TestCase):
            pass

        decorated = override_settings(TEST="override")(SimpleTestCaseSubclass)
        self.assertIsInstance(decorated, type)
        self.assertTrue(issubclass(decorated, SimpleTestCase))

        with self.assertRaisesMessage(
            Exception, "Only subclasses of Django SimpleTestCase"
        ):
            decorated = override_settings(TEST="override")(UnittestTestCaseSubclass)

    def test_signal_callback_context_manager(self):
        """
        Tests the use of a signal callback context manager to temporarily override settings.

        This test verifies that attempting to access a non-existent setting raises an AttributeError.
        It then checks that the setting can be successfully overridden within a context manager block,
        and that the original setting is restored after exiting the block.

        The test case also ensures that the overridden setting value is correctly reflected in the test object,
        and that it is reset to None after the override is removed.
        """
        with self.assertRaises(AttributeError):
            getattr(settings, "TEST")
        with self.settings(TEST="override"):
            self.assertEqual(self.testvalue, "override")
        self.assertIsNone(self.testvalue)

    @override_settings(TEST="override")
    def test_signal_callback_decorator(self):
        self.assertEqual(self.testvalue, "override")

    #
    # Regression tests for #10130: deleting settings.
    #

    def test_settings_delete(self):
        settings.TEST = "test"
        self.assertEqual("test", settings.TEST)
        del settings.TEST
        msg = "'Settings' object has no attribute 'TEST'"
        with self.assertRaisesMessage(AttributeError, msg):
            getattr(settings, "TEST")

    def test_settings_delete_wrapped(self):
        with self.assertRaisesMessage(TypeError, "can't delete _wrapped."):
            delattr(settings, "_wrapped")

    def test_override_settings_delete(self):
        """
        Allow deletion of a setting in an overridden settings set (#18824)
        """
        previous_i18n = settings.USE_I18N
        previous_tz = settings.USE_TZ
        with self.settings(USE_I18N=False):
            del settings.USE_I18N
            with self.assertRaises(AttributeError):
                getattr(settings, "USE_I18N")
            # Should also work for a non-overridden setting
            del settings.USE_TZ
            with self.assertRaises(AttributeError):
                getattr(settings, "USE_TZ")
            self.assertNotIn("USE_I18N", dir(settings))
            self.assertNotIn("USE_TZ", dir(settings))
        self.assertEqual(settings.USE_I18N, previous_i18n)
        self.assertEqual(settings.USE_TZ, previous_tz)

    def test_override_settings_nested(self):
        """
        override_settings uses the actual _wrapped attribute at
        runtime, not when it was instantiated.
        """

        with self.assertRaises(AttributeError):
            getattr(settings, "TEST")
        with self.assertRaises(AttributeError):
            getattr(settings, "TEST2")

        inner = override_settings(TEST2="override")
        with override_settings(TEST="override"):
            self.assertEqual("override", settings.TEST)
            with inner:
                self.assertEqual("override", settings.TEST)
                self.assertEqual("override", settings.TEST2)
            # inner's __exit__ should have restored the settings of the outer
            # context manager, not those when the class was instantiated
            self.assertEqual("override", settings.TEST)
            with self.assertRaises(AttributeError):
                getattr(settings, "TEST2")

        with self.assertRaises(AttributeError):
            getattr(settings, "TEST")
        with self.assertRaises(AttributeError):
            getattr(settings, "TEST2")

    @override_settings(SECRET_KEY="")
    def test_no_secret_key(self):
        msg = "The SECRET_KEY setting must not be empty."
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            settings.SECRET_KEY

    def test_no_settings_module(self):
        msg = (
            "Requested setting%s, but settings are not configured. You "
            "must either define the environment variable DJANGO_SETTINGS_MODULE "
            "or call settings.configure() before accessing settings."
        )
        orig_settings = os.environ[ENVIRONMENT_VARIABLE]
        os.environ[ENVIRONMENT_VARIABLE] = ""
        try:
            with self.assertRaisesMessage(ImproperlyConfigured, msg % "s"):
                settings._setup()
            with self.assertRaisesMessage(ImproperlyConfigured, msg % " TEST"):
                settings._setup("TEST")
        finally:
            os.environ[ENVIRONMENT_VARIABLE] = orig_settings

    def test_already_configured(self):
        with self.assertRaisesMessage(RuntimeError, "Settings already configured."):
            settings.configure()

    def test_nonupper_settings_prohibited_in_configure(self):
        s = LazySettings()
        with self.assertRaisesMessage(TypeError, "Setting 'foo' must be uppercase."):
            s.configure(foo="bar")

    def test_nonupper_settings_ignored_in_default_settings(self):
        s = LazySettings()
        s.configure(SimpleNamespace(foo="bar"))
        with self.assertRaises(AttributeError):
            getattr(s, "foo")

    @requires_tz_support
    @mock.patch("django.conf.global_settings.TIME_ZONE", "test")
    def test_incorrect_timezone(self):
        with self.assertRaisesMessage(ValueError, "Incorrect timezone setting: test"):
            settings._setup()


class TestComplexSettingOverride(SimpleTestCase):
    def setUp(self):
        self.old_warn_override_settings = signals.COMPLEX_OVERRIDE_SETTINGS.copy()
        signals.COMPLEX_OVERRIDE_SETTINGS.add("TEST_WARN")

    def tearDown(self):
        """
        Resets the COMPLEX_OVERRIDE_SETTINGS signal to its original value after a test.

        Restores the settings to what they were before the test began, and verifies
        that the 'TEST_WARN' setting is no longer present in the override settings.

        This method is used to clean up after a test and ensure that subsequent tests
        start with the default settings, preventing any side effects from the test
        that called this method.
        """
        signals.COMPLEX_OVERRIDE_SETTINGS = self.old_warn_override_settings
        self.assertNotIn("TEST_WARN", signals.COMPLEX_OVERRIDE_SETTINGS)

    def test_complex_override_warning(self):
        """Regression test for #19031"""
        msg = "Overriding setting TEST_WARN can lead to unexpected behavior."
        with self.assertWarnsMessage(UserWarning, msg) as cm:
            with override_settings(TEST_WARN="override"):
                self.assertEqual(settings.TEST_WARN, "override")
        self.assertEqual(cm.filename, __file__)


class SecureProxySslHeaderTest(SimpleTestCase):
    @override_settings(SECURE_PROXY_SSL_HEADER=None)
    def test_none(self):
        req = HttpRequest()
        self.assertIs(req.is_secure(), False)

    @override_settings(SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"))
    def test_set_without_xheader(self):
        """

        Tests the HttpRequest is_secure method when the SECURE_PROXY_SSL_HEADER setting is enabled
        but no HTTP_X_FORWARDED_PROTO header is present in the request.

        Verifies that the method returns False, indicating the request is not secure.

        """
        req = HttpRequest()
        self.assertIs(req.is_secure(), False)

    @override_settings(SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"))
    def test_set_with_xheader_wrong(self):
        """
        Tests that an HttpRequest is deemed insecure when a proxy's X-Forwarded-Proto header contains an incorrect value.

        This test ensures that the is_secure method correctly handles cases where the proxy's header does not match the expected secure protocol (https), indicating that the request was not transmitted securely.

        The test verifies that when the HTTP_X_FORWARDED_PROTO header holds an unexpected value, the is_secure method returns False, correctly identifying the request as insecure.
        """
        req = HttpRequest()
        req.META["HTTP_X_FORWARDED_PROTO"] = "wrongvalue"
        self.assertIs(req.is_secure(), False)

    @override_settings(SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"))
    def test_set_with_xheader_right(self):
        """

        Tests the functionality of determining if an HTTP request is secure based on the 'HTTP_X_FORWARDED_PROTO' header.

        This test case verifies that when the 'HTTP_X_FORWARDED_PROTO' header is set to 'https', the request is correctly identified as secure.

        """
        req = HttpRequest()
        req.META["HTTP_X_FORWARDED_PROTO"] = "https"
        self.assertIs(req.is_secure(), True)

    @override_settings(SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"))
    def test_set_with_xheader_leftmost_right(self):
        """

        Tests that an HttpRequest is marked as secure if the 'HTTP_X_FORWARDED_PROTO' 
        header contains 'https' in the leftmost position, even if it is followed by 
        other values.

        The test covers cases where 'https' is followed by other protocol values, 
        including cases where there are extra spaces between the values.

        """
        req = HttpRequest()
        req.META["HTTP_X_FORWARDED_PROTO"] = "https, http"
        self.assertIs(req.is_secure(), True)
        req.META["HTTP_X_FORWARDED_PROTO"] = "https  , http"
        self.assertIs(req.is_secure(), True)

    @override_settings(SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"))
    def test_set_with_xheader_leftmost_not_secure(self):
        req = HttpRequest()
        req.META["HTTP_X_FORWARDED_PROTO"] = "http, https"
        self.assertIs(req.is_secure(), False)

    @override_settings(SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"))
    def test_set_with_xheader_multiple_not_secure(self):
        """
        Tests that the HttpRequest is_secure method returns False when the HTTP_X_FORWARDED_PROTO header contains multiple values, none of which indicate a secure connection.

        This test case simulates a scenario where the proxy server sets the HTTP_X_FORWARDED_PROTO header with multiple values, including 'http' and an invalid value. It verifies that the HttpRequest object correctly determines the request is not secure in this case.

        The test is performed with the SECURE_PROXY_SSL_HEADER setting overridden to prioritize the 'HTTP_X_FORWARDED_PROTO' header for determining the request's security status.
        """
        req = HttpRequest()
        req.META["HTTP_X_FORWARDED_PROTO"] = "http ,wrongvalue,http,http"
        self.assertIs(req.is_secure(), False)

    @override_settings(SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"))
    def test_xheader_preferred_to_underlying_request(self):
        """
        Tests that the 'X-Forwarded-Proto' header is prioritized over the underlying request scheme when determining the security status of a proxy request.

        The test case verifies that even if a proxy request is made via HTTPS, if the 'X-Forwarded-Proto' header specifies 'http', the request is considered insecure. This ensures proper handling of requests proxied through an SSL termination point, allowing the application to accurately determine the security status of incoming requests.
        """
        class ProxyRequest(HttpRequest):
            def _get_scheme(self):
                """Proxy always connecting via HTTPS"""
                return "https"

        # Client connects via HTTP.
        req = ProxyRequest()
        req.META["HTTP_X_FORWARDED_PROTO"] = "http"
        self.assertIs(req.is_secure(), False)


class IsOverriddenTest(SimpleTestCase):
    def test_configure(self):
        s = LazySettings()
        s.configure(SECRET_KEY="foo")

        self.assertTrue(s.is_overridden("SECRET_KEY"))

    def test_module(self):
        settings_module = ModuleType("fake_settings_module")
        settings_module.SECRET_KEY = "foo"
        settings_module.USE_TZ = False
        sys.modules["fake_settings_module"] = settings_module
        try:
            s = Settings("fake_settings_module")

            self.assertTrue(s.is_overridden("SECRET_KEY"))
            self.assertFalse(s.is_overridden("ALLOWED_HOSTS"))
        finally:
            del sys.modules["fake_settings_module"]

    def test_override(self):
        self.assertFalse(settings.is_overridden("ALLOWED_HOSTS"))
        with override_settings(ALLOWED_HOSTS=[]):
            self.assertTrue(settings.is_overridden("ALLOWED_HOSTS"))

    def test_unevaluated_lazysettings_repr(self):
        lazy_settings = LazySettings()
        expected = "<LazySettings [Unevaluated]>"
        self.assertEqual(repr(lazy_settings), expected)

    def test_evaluated_lazysettings_repr(self):
        lazy_settings = LazySettings()
        module = os.environ.get(ENVIRONMENT_VARIABLE)
        expected = '<LazySettings "%s">' % module
        # Force evaluation of the lazy object.
        lazy_settings.APPEND_SLASH
        self.assertEqual(repr(lazy_settings), expected)

    def test_usersettingsholder_repr(self):
        """
        Tests the string representation of the UserSettingsHolder object.

        Verifies that the repr method of the _wrapped attribute of LazySettings returns 
        the expected string '<UserSettingsHolder>' after configuring the LazySettings 
        instance with the specified settings. This ensures that the object can be 
        meaningfully represented as a string for debugging and logging purposes.
        """
        lazy_settings = LazySettings()
        lazy_settings.configure(APPEND_SLASH=False)
        expected = "<UserSettingsHolder>"
        self.assertEqual(repr(lazy_settings._wrapped), expected)

    def test_settings_repr(self):
        """
        \\":\"\"\"
        Tests that the string representation of the Settings object is correctly formatted.

        The function verifies that the repr() method returns a string in the format
         `<Settings \"module_name\">`, where `module_name` is the name of the module specified
         by the environment variable. This test ensures that the Settings object can be
         properly represented as a string for logging or debugging purposes.

        """
        module = os.environ.get(ENVIRONMENT_VARIABLE)
        lazy_settings = Settings(module)
        expected = '<Settings "%s">' % module
        self.assertEqual(repr(lazy_settings), expected)


class TestListSettings(SimpleTestCase):
    """
    Make sure settings that should be lists or tuples throw
    ImproperlyConfigured if they are set to a string instead of a list or tuple.
    """

    list_or_tuple_settings = (
        "ALLOWED_HOSTS",
        "INSTALLED_APPS",
        "TEMPLATE_DIRS",
        "LOCALE_PATHS",
        "SECRET_KEY_FALLBACKS",
    )

    def test_tuple_settings(self):
        settings_module = ModuleType("fake_settings_module")
        settings_module.SECRET_KEY = "foo"
        msg = "The %s setting must be a list or a tuple."
        for setting in self.list_or_tuple_settings:
            setattr(settings_module, setting, ("non_list_or_tuple_value"))
            sys.modules["fake_settings_module"] = settings_module
            try:
                with self.assertRaisesMessage(ImproperlyConfigured, msg % setting):
                    Settings("fake_settings_module")
            finally:
                del sys.modules["fake_settings_module"]
                delattr(settings_module, setting)


class SettingChangeEnterException(Exception):
    pass


class SettingChangeExitException(Exception):
    pass


class OverrideSettingsIsolationOnExceptionTests(SimpleTestCase):
    """
    The override_settings context manager restore settings if one of the
    receivers of "setting_changed" signal fails. Check the three cases of
    receiver failure detailed in receiver(). In each case, ALL receivers are
    called when exiting the context manager.
    """

    def setUp(self):
        signals.setting_changed.connect(self.receiver)
        self.addCleanup(signals.setting_changed.disconnect, self.receiver)
        # Create a spy that's connected to the `setting_changed` signal and
        # executed AFTER `self.receiver`.
        self.spy_receiver = mock.Mock()
        signals.setting_changed.connect(self.spy_receiver)
        self.addCleanup(signals.setting_changed.disconnect, self.spy_receiver)

    def receiver(self, **kwargs):
        """
        A receiver that fails while certain settings are being changed.
        - SETTING_BOTH raises an error while receiving the signal
          on both entering and exiting the context manager.
        - SETTING_ENTER raises an error only on enter.
        - SETTING_EXIT raises an error only on exit.
        """
        setting = kwargs["setting"]
        enter = kwargs["enter"]
        if setting in ("SETTING_BOTH", "SETTING_ENTER") and enter:
            raise SettingChangeEnterException
        if setting in ("SETTING_BOTH", "SETTING_EXIT") and not enter:
            raise SettingChangeExitException

    def check_settings(self):
        """Assert that settings for these tests aren't present."""
        self.assertFalse(hasattr(settings, "SETTING_BOTH"))
        self.assertFalse(hasattr(settings, "SETTING_ENTER"))
        self.assertFalse(hasattr(settings, "SETTING_EXIT"))
        self.assertFalse(hasattr(settings, "SETTING_PASS"))

    def check_spy_receiver_exit_calls(self, call_count):
        """
        Assert that `self.spy_receiver` was called exactly `call_count` times
        with the ``enter=False`` keyword argument.
        """
        kwargs_with_exit = [
            kwargs
            for args, kwargs in self.spy_receiver.call_args_list
            if ("enter", False) in kwargs.items()
        ]
        self.assertEqual(len(kwargs_with_exit), call_count)

    def test_override_settings_both(self):
        """Receiver fails on both enter and exit."""
        with self.assertRaises(SettingChangeEnterException):
            with override_settings(SETTING_PASS="BOTH", SETTING_BOTH="BOTH"):
                pass

        self.check_settings()
        # Two settings were touched, so expect two calls of `spy_receiver`.
        self.check_spy_receiver_exit_calls(call_count=2)

    def test_override_settings_enter(self):
        """Receiver fails on enter only."""
        with self.assertRaises(SettingChangeEnterException):
            with override_settings(SETTING_PASS="ENTER", SETTING_ENTER="ENTER"):
                pass

        self.check_settings()
        # Two settings were touched, so expect two calls of `spy_receiver`.
        self.check_spy_receiver_exit_calls(call_count=2)

    def test_override_settings_exit(self):
        """Receiver fails on exit only."""
        with self.assertRaises(SettingChangeExitException):
            with override_settings(SETTING_PASS="EXIT", SETTING_EXIT="EXIT"):
                pass

        self.check_settings()
        # Two settings were touched, so expect two calls of `spy_receiver`.
        self.check_spy_receiver_exit_calls(call_count=2)

    def test_override_settings_reusable_on_enter(self):
        """
        Error is raised correctly when reusing the same override_settings
        instance.
        """

        @override_settings(SETTING_ENTER="ENTER")
        def decorated_function():
            pass

        with self.assertRaises(SettingChangeEnterException):
            decorated_function()
        signals.setting_changed.disconnect(self.receiver)
        # This call shouldn't raise any errors.
        decorated_function()


class MediaURLStaticURLPrefixTest(SimpleTestCase):
    def set_script_name(self, val):
        clear_script_prefix()
        if val is not None:
            set_script_prefix(val)

    def test_not_prefixed(self):
        # Don't add SCRIPT_NAME prefix to absolute paths, URLs, or None.
        tests = (
            "/path/",
            "http://myhost.com/path/",
            "http://myhost/path/",
            "https://myhost/path/",
            None,
        )
        for setting in ("MEDIA_URL", "STATIC_URL"):
            for path in tests:
                new_settings = {setting: path}
                with self.settings(**new_settings):
                    for script_name in ["/somesubpath", "/somesubpath/", "/", "", None]:
                        with self.subTest(script_name=script_name, **new_settings):
                            try:
                                self.set_script_name(script_name)
                                self.assertEqual(getattr(settings, setting), path)
                            finally:
                                clear_script_prefix()

    def test_add_script_name_prefix(self):
        """
        Tests the addition of a script name prefix to media and static URLs.

        This test exercises the logic for combining the `script_name` with `MEDIA_URL` and `STATIC_URL` settings.
        It checks various combinations of `script_name` and URL settings to ensure the resulting URLs are constructed correctly.

        The test covers different scenarios, including absolute and relative URLs, and URL paths with and without a trailing slash.
        It verifies that the resulting URL is correctly prefixed with the `script_name` in each case.
        """
        tests = (
            # Relative paths.
            ("/somesubpath", "path/", "/somesubpath/path/"),
            ("/somesubpath/", "path/", "/somesubpath/path/"),
            ("/", "path/", "/path/"),
            # Invalid URLs.
            (
                "/somesubpath/",
                "htp://myhost.com/path/",
                "/somesubpath/htp://myhost.com/path/",
            ),
            # Blank settings.
            ("/somesubpath/", "", "/somesubpath/"),
        )
        for setting in ("MEDIA_URL", "STATIC_URL"):
            for script_name, path, expected_path in tests:
                new_settings = {setting: path}
                with self.settings(**new_settings):
                    with self.subTest(script_name=script_name, **new_settings):
                        try:
                            self.set_script_name(script_name)
                            self.assertEqual(getattr(settings, setting), expected_path)
                        finally:
                            clear_script_prefix()
