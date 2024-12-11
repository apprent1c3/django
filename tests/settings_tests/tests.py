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

        Tests the override of settings by verifying the correct values for various configuration items.

        This function checks that the following settings have been overridden correctly:
        - ITEMS: a list of string values
        - ITEMS_OUTER: a list of integer values
        - TEST: a string value indicating an override has occurred
        - TEST_OUTER: a string value indicating an outer setting

        The function uses assertions to ensure these settings match the expected values, providing a basic sanity check for the override mechanism.

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
        Tests the override functionality of the ITEMS setting by modifying its list.

        The test appends elements 'e' and 'f', prepends element 'a', and removes elements 'd' and 'c' from the ITEMS list.
        It then verifies that the modified ITEMS list is correctly updated and that the ITEMS_OUTER list remains unchanged.
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
        Tests that default settings have been overridden correctly.

        This test case verifies that the ITEMS setting has been updated to include the
        expected list of items ['b', 'c', 'd'] and that the TEST setting has been
        set to 'override', as specified in the overrides. The purpose of this test
        is to ensure that the default settings can be successfully overridden with
        custom values.
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
        self.assertEqual(settings.ITEMS, ["father", "mother", "child"])
        self.assertEqual(settings.TEST, "override-child")


class SettingsTests(SimpleTestCase):
    def setUp(self):
        """
        Sets up the test environment by initializing test variables and connecting to the setting_changed signal.

        This method is used to prepare the test setup before each test case, ensuring a clean start. It connects to the setting_changed signal, allowing the test to respond to changes in settings, and automatically disconnects from the signal when the test is cleaned up.

        :return: None
        """
        self.testvalue = None
        signals.setting_changed.connect(self.signal_callback)
        self.addCleanup(signals.setting_changed.disconnect, self.signal_callback)

    def signal_callback(self, sender, setting, value, **kwargs):
        """

        Handles signals emitted by the sender when a setting is changed.

        This callback function is triggered when a setting's value is updated. It checks if the changed setting is 'TEST' and, if so, updates the test value accordingly.

        Parameters
        ----------
        sender : object
            The object that emitted the signal.
        setting : str
            The name of the setting that was changed.
        value : any
            The new value of the setting.
        **kwargs
            Additional keyword arguments passed by the signal.

        Note
        ----
        The function currently only reacts to changes of the 'TEST' setting.

        """
        if setting == "TEST":
            self.testvalue = value

    def test_override(self):
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
        Tests that overriding a setting does not persist after the override is removed.

        Verifies that attempting to access a non-existent setting raises an AttributeError,
        that a setting can be successfully overridden, and that the override is properly
        cleared after the override context is exited, restoring the original behavior of
        raising an AttributeError for the non-existent setting.
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
        """

        Tests the context manager functionality of overriding settings.

        This function verifies that an AttributeError is raised when attempting to access a non-existent setting.
        It then ensures that the override functionality correctly sets the setting to a specified value, and
        that the setting reverts back to its original state after the override is disabled.

        The test covers three main scenarios:
        - The initial state, where the setting does not exist.
        - The overridden state, where the setting has a specified value.
        - The reverted state, where the setting no longer exists after the override is disabled.

        This test provides confidence that the context manager correctly manages setting overrides.

        """
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
        """
        Tests that attempting to delete the _wrapped attribute of the settings object raises a TypeError.

        This test case verifies that the _wrapped attribute is protected from deletion and that the expected error message is displayed when such an attempt is made. The test ensures the integrity of the settings object and its internal state by checking for the correct exception type and message. 
        """
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
        """
        Tests that an ImproperlyConfigured exception is raised when the SECRET_KEY setting is empty, ensuring a valid secret key is provided for the application's security.
        """
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
        """
        Test that Django's settings setup correctly raises an error when an invalid timezone is configured.

        :param self: Test case instance
        :raises ValueError: If the timezone setting is invalid
        :note: This test requires timezone support and temporarily overrides the TIME_ZONE setting to 'test' for the duration of the test.
        """
        with self.assertRaisesMessage(ValueError, "Incorrect timezone setting: test"):
            settings._setup()


class TestComplexSettingOverride(SimpleTestCase):
    def setUp(self):
        """

        Sets up the environment for testing by preserving the current complex override settings and adding 'TEST_WARN' to the settings.

        This method is used to ensure that the original settings are restored after the test, and provides a way to test the behavior of the system with the 'TEST_WARN' setting enabled.

        """
        self.old_warn_override_settings = signals.COMPLEX_OVERRIDE_SETTINGS.copy()
        signals.COMPLEX_OVERRIDE_SETTINGS.add("TEST_WARN")

    def tearDown(self):
        """

        Teardown method to restore the original warning override settings after a test.

        Restores :data:`signals.COMPLEX_OVERRIDE_SETTINGS` to its original value
         stored in :attr:`old_warn_override_settings` before the test, ensuring that
         any modifications made during the test do not affect subsequent tests.

        Additionally, it verifies that 'TEST_WARN' is not present in the restored
         :data:`signals.COMPLEX_OVERRIDE_SETTINGS`.

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

        Tests that an HttpRequest instance reports itself as insecure when the 
        'HTTP_X_FORWARDED_PROTO' header is not present.

        This test ensures the correct behavior of the is_secure() method in the 
        absence of the 'HTTP_X_FORWARDED_PROTO' header, which is typically used to 
        indicate that a request was made over a secure connection (e.g., HTTPS) 
        when the request is proxied through a load balancer or other intermediary.

        """
        req = HttpRequest()
        self.assertIs(req.is_secure(), False)

    @override_settings(SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"))
    def test_set_with_xheader_wrong(self):
        req = HttpRequest()
        req.META["HTTP_X_FORWARDED_PROTO"] = "wrongvalue"
        self.assertIs(req.is_secure(), False)

    @override_settings(SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"))
    def test_set_with_xheader_right(self):
        req = HttpRequest()
        req.META["HTTP_X_FORWARDED_PROTO"] = "https"
        self.assertIs(req.is_secure(), True)

    @override_settings(SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"))
    def test_set_with_xheader_leftmost_right(self):
        req = HttpRequest()
        req.META["HTTP_X_FORWARDED_PROTO"] = "https, http"
        self.assertIs(req.is_secure(), True)
        req.META["HTTP_X_FORWARDED_PROTO"] = "https  , http"
        self.assertIs(req.is_secure(), True)

    @override_settings(SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"))
    def test_set_with_xheader_leftmost_not_secure(self):
        """

        Tests the behavior of the HttpRequest is_secure method when the leftmost value in the 
        X-Forwarded-Proto header is not 'https'. 

        The test case simulates a scenario where the X-Forwarded-Proto header contains multiple 
        values, with 'http' as the leftmost value. It verifies that the is_secure method 
        correctly returns False in this case, indicating that the request is not secure.

        This test ensures that the is_secure method prioritizes the leftmost value in the 
        X-Forwarded-Proto header when determining the security of the request.

        """
        req = HttpRequest()
        req.META["HTTP_X_FORWARDED_PROTO"] = "http, https"
        self.assertIs(req.is_secure(), False)

    @override_settings(SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"))
    def test_set_with_xheader_multiple_not_secure(self):
        req = HttpRequest()
        req.META["HTTP_X_FORWARDED_PROTO"] = "http ,wrongvalue,http,http"
        self.assertIs(req.is_secure(), False)

    @override_settings(SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"))
    def test_xheader_preferred_to_underlying_request(self):
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
        """
        :test_evaluated_lazysettings_repr:
            Tests the representation of LazySettings after accessing one of its attributes.

            Verifies that the string representation of a LazySettings instance matches the expected
            format after an attribute has been accessed, specifically when the environment variable
            is set. This checks that the representation reflects the name of the settings module.
        """
        lazy_settings = LazySettings()
        module = os.environ.get(ENVIRONMENT_VARIABLE)
        expected = '<LazySettings "%s">' % module
        # Force evaluation of the lazy object.
        lazy_settings.APPEND_SLASH
        self.assertEqual(repr(lazy_settings), expected)

    def test_usersettingsholder_repr(self):
        """
        Tests the representation of a UserSettingsHolder instance.

        Verifies that the repr method returns the expected string, 
        '<UserSettingsHolder>', for a LazySettings instance after it has been configured.
        This ensures that the string representation of the UserSettingsHolder is 
        consistent and useful for debugging purposes.
        """
        lazy_settings = LazySettings()
        lazy_settings.configure(APPEND_SLASH=False)
        expected = "<UserSettingsHolder>"
        self.assertEqual(repr(lazy_settings._wrapped), expected)

    def test_settings_repr(self):
        """

        Checks that the repr of a Settings instance returns the expected string representation.

        The function tests if the Settings object is properly represented as a string,
        which includes the name of the module used to initialize the Settings instance.

        This test case ensures that the repr function of the Settings class is working correctly,
        making it easier to identify and debug instances of the class.

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
        """

        Verifies that specified settings must be defined as lists or tuples.

        This test checks each setting in :attr:`list_or_tuple_settings` to ensure it raises
        an :exc:`ImproperlyConfigured` exception when set to a non-list or non-tuple value.
        The test creates a fake settings module, sets the invalid value, and then attempts
        to instantiate a :class:`Settings` object, confirming the expected exception is raised.

        """
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
        """
        Sets the script name for the current context.

        This method updates the script name to the provided value. If the value is not None, it sets the script prefix accordingly. Otherwise, it clears any existing script prefix.

        :param val: The new script name to be set.

        """
        clear_script_prefix()
        if val is not None:
            set_script_prefix(val)

    def test_not_prefixed(self):
        # Don't add SCRIPT_NAME prefix to absolute paths, URLs, or None.
        """

        Tests that the :data:`MEDIA_URL` and :data:`STATIC_URL` settings are not modified by script prefix.

        This test checks various combinations of URLs and script names to ensure that the
        URL settings remain unchanged, even when a script prefix is applied.

        The test cases cover different URL formats, including absolute and relative URLs,
        as well as scenarios where the URL is not set (i.e., ``None``). Additionally, the
        test checks the behavior with different script names, including those with and
        without a trailing slash.

        By verifying that the URL settings are not prefixed, this test helps to ensure that
        static and media files are correctly served in various deployment scenarios.

        """
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
