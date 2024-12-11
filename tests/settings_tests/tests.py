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

        Tests that certain setting values have been overridden correctly.

        This test case verifies that the settings ITEMs, ITEMS_OUTER, TEST, and TEST_OUTER
        have been overridden with the expected values. The test passes if the actual values
        of these settings match the expected ones, which are 'b', 'c', 'd' for ITEMs, 
        1, 2, 3 for ITEMS_OUTER, 'override' for TEST, and 'outer' for TEST_OUTER.

        The purpose of this test is to ensure that the override mechanism is working as
        expected, and that the settings are being updated correctly.

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

        Override the ITEMS setting to test its modification.

        This function tests that the ITEMS setting can be successfully modified by appending, prepending, and removing items.
        It verifies that the resulting ITEMS list contains the expected elements after modification.
        The test also confirms that the modification does not affect other unrelated settings, such as ITEMS_OUTER.

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

        Tests that settings are correctly overridden using the @override_settings decorator.

        This test checks if the TEST setting is overridden with the value 'override2' and 
        verifies that other settings, like TEST_OUTER, remain unchanged.

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
        Tests if default settings values have been correctly overridden.

        Checks if the ITEMS list and the TEST value in the settings module have been 
        successfully overridden with the expected values, ensuring that the default 
        settings have been modified as intended.

        This test verifies that the settings module is properly configured and 
        that the overridden values are accessible and correct, which is essential 
        for ensuring the correct behavior of the application in different environments.

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
        """

        Tests the override of settings in the application.

        This method verifies that settings can be successfully modified and overridden. 
        It checks that the 'ITEMS' setting has been correctly updated by appending, 
        prepending, and removing items, resulting in a list containing ['a', 'b', 'd', 'e']. 
        Additionally, it confirms that the 'TEST' setting has been overridden to 'override2'.

        """
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
        """
        Sets up the class-level state for testing purposes.

        This method is called once for the entire test class, and is responsible for
        initializing class-level attributes. Specifically, it retrieves the 'TEST'
        setting from the application settings, defaulting to 'BUG' if the setting is
        not found, and assigns it to the class attribute 'foo'.

        This setup is performed after calling the parent class's setup method to ensure
        proper inheritance of setup functionality. The resulting 'foo' attribute can be
        used throughout the test class to customize test behavior or provide default
        values. 
        """
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
        Tests that the override settings are correctly inherited.

        Verifies that the ITEMS setting is set to its expected value and that the TEST setting
        is overridden with the 'override-child' value, demonstrating the correct inheritance
        of settings from parent configurations.

        This test ensures that the settings are properly configured and that the override
        mechanism is functioning as expected, allowing for customization of settings in
        child configurations while still inheriting base settings from parent configurations.
        """
        self.assertEqual(settings.ITEMS, ["father", "mother", "child"])
        self.assertEqual(settings.TEST, "override-child")


class SettingsTests(SimpleTestCase):
    def setUp(self):
        """

        Sets up the test environment by initializing test values and connecting a callback to the setting changed signal.
        The callback is automatically disconnected after the test is completed to ensure a clean test setup.

        """
        self.testvalue = None
        signals.setting_changed.connect(self.signal_callback)
        self.addCleanup(signals.setting_changed.disconnect, self.signal_callback)

    def signal_callback(self, sender, setting, value, **kwargs):
        """
        Handles a signal emitted by a sender when a setting is changed.

        This callback function is invoked whenever a setting is modified, passing the
        sender, setting name, new value, and any additional keyword arguments. It
        currently listens for changes to the 'TEST' setting and updates the internal
        test value accordingly.

        :param sender: The object emitting the signal.
        :param setting: The name of the setting that has been changed.
        :param value: The new value of the setting.
        :param kwargs: Any additional keyword arguments passed with the signal.

        """
        if setting == "TEST":
            self.testvalue = value

    def test_override(self):
        """

        Tests that settings can be overridden within a specific context.

        Verifies that the TEST setting can be overridden temporarily using the settings context manager,
        and that the original value is restored after the context is exited.

        The test follows this sequence:

        * Set the initial value of the TEST setting to 'test'
        * Override the TEST setting to 'override' within a context manager
        * Verify that the value of TEST is restored to 'test' after the context manager is exited
        * Clean up by deleting the TEST setting

        This test ensures that settings can be safely overridden without affecting the global state.

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
        Verifies that overriding a setting does not persist after the override context is exited.

        This test checks that settings can be temporarily overridden without leaking into other parts of the application.
        It ensures that attempting to access a non-existent setting raises an AttributeError, and that overriding a setting
        only affects the current context. Once the override context is exited, the original setting behavior is restored,
        and attempting to access the overridden setting again raises an AttributeError.

        The test also confirms that manually setting a setting within an override context does not persist after the context
        is exited, ensuring the isolation of the override context.

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

        Tests the proper functionality of the context manager used to override settings.

        The test case checks that an AttributeError is raised when attempting to access a setting that does not exist.
        It then creates an instance of the override settings context manager, testing that the setting remains inaccessible 
        until the context is enabled. Once enabled, the test verifies that the overridden setting value is correctly applied.
        Finally, the test checks that the setting reverts to its original inaccessible state after the context is disabled.

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
        """

        Test the functionality of the class decorator for overriding settings.

        This test case verifies that the decorator correctly modifies a subclass of 
        Django's SimpleTestCase, ensuring it remains a subclass after decoration. It 
        also checks that an error is raised when attempting to decorate a subclass of 
        Python's unittest.TestCase, as this is not a supported use case.

        The test covers the following scenarios:
        - Successful decoration of a SimpleTestCase subclass
        - Validation that the decorated class remains a subclass of SimpleTestCase
        - Error handling when decorating an unsupported subclass of unittest.TestCase

        """
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
        Tests the behavior of the signal callback context manager.

        This test verifies that the context manager correctly overrides the 'TEST' setting in the settings module and reverts back to its original state after exiting the context.

        The test first checks that the 'TEST' attribute does not exist in the settings module by default, then overrides it with the value 'override' within a context and checks that the override is reflected in the test value. Finally, it verifies that the value is reset to None after exiting the context, ensuring the original state is restored.
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
        """
        Tests that deleting a setting from the settings object correctly removes the attribute, raising an AttributeError when attempting to access the deleted attribute. 

         Args:
            None

         Returns:
            None

         Raises:
            AssertionError: If the test setting is not successfully deleted or the expected AttributeError is not raised.
        """
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
        """
        Tests that attempting to access the SECRET_KEY setting when it is empty raises an ImproperlyConfigured exception with a descriptive message, ensuring that a valid secret key is configured for the application.
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
        """
        Tests that a RuntimeError is raised when attempting to configure settings 
        that have already been configured.

        Verifies the expected error message 'Settings already configured.' is 
        displayed when the configure method is called on previously configured settings.

        Raises:
            RuntimeError: If settings configuration has already been applied.

        """
        with self.assertRaisesMessage(RuntimeError, "Settings already configured."):
            settings.configure()

    def test_nonupper_settings_prohibited_in_configure(self):
        """

        Tests that settings names with non-uppercase characters are prohibited when configuring the application.

        This test checks that a TypeError is raised when attempting to configure the application with a setting name that does not follow the standard naming convention of using uppercase characters.

        The test verifies that the error message correctly identifies the problematic setting name and provides a clear indication of the expected naming convention.

        """
        s = LazySettings()
        with self.assertRaisesMessage(TypeError, "Setting 'foo' must be uppercase."):
            s.configure(foo="bar")

    def test_nonupper_settings_ignored_in_default_settings(self):
        """
        Tests whether non-upper case settings are ignored in the default settings configuration.

        This test verifies that only upper case settings are recognized and accessible 
        in the default settings, while non-upper case settings are handled as not 
        configured. It checks that attempting to access a non-upper case setting 
        will result in an AttributeError being raised.
        """
        s = LazySettings()
        s.configure(SimpleNamespace(foo="bar"))
        with self.assertRaises(AttributeError):
            getattr(s, "foo")

    @requires_tz_support
    @mock.patch("django.conf.global_settings.TIME_ZONE", "test")
    def test_incorrect_timezone(self):
        """
        :param self: Test instance
        :raises: ValueError
        :raisessetMessage: \"Incorrect timezone setting: test\"

        Tests that a ValueError is raised when an invalid timezone setting is provided. This checks the handling of incorrect timezone configurations, ensuring that the application properly handles and reports such errors. The test utilizes a mock timezone setting to simulate an invalid configuration, verifying that the correct error message is generated.
        """
        with self.assertRaisesMessage(ValueError, "Incorrect timezone setting: test"):
            settings._setup()


class TestComplexSettingOverride(SimpleTestCase):
    def setUp(self):
        self.old_warn_override_settings = signals.COMPLEX_OVERRIDE_SETTINGS.copy()
        signals.COMPLEX_OVERRIDE_SETTINGS.add("TEST_WARN")

    def tearDown(self):
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
        req = HttpRequest()
        self.assertIs(req.is_secure(), False)

    @override_settings(SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"))
    def test_set_with_xheader_wrong(self):
        """
        Tests the request's is_secure method when the SECURE_PROXY_SSL_HEADER setting is enabled and the 'HTTP_X_FORWARDED_PROTO' header has an incorrect value.

        Verifies that the request is correctly identified as insecure when the 'HTTP_X_FORWARDED_PROTO' header contains an unexpected value, rather than the expected 'https' or 'http' value.

        This ensures the security of the request is properly evaluated when behind a proxy server, and the 'HTTP_X_FORWARDED_PROTO' header is being used to determine the security of the request.
        """
        req = HttpRequest()
        req.META["HTTP_X_FORWARDED_PROTO"] = "wrongvalue"
        self.assertIs(req.is_secure(), False)

    @override_settings(SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"))
    def test_set_with_xheader_right(self):
        """

        Tests that a request is correctly identified as secure when the 'X-Forwarded-Proto' header is set to 'https'.

        This test case verifies the functionality of the :meth:`HttpRequest.is_secure` method when the request is made behind a proxy server.
        It checks that the request is marked as secure when the 'HTTP_X_FORWARDED_PROTO' header is present and set to 'https', as per the configured SECURE_PROXY_SSL_HEADER setting.

        """
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
        """

        Tests the creation and behavior of the Settings class.

        This test case verifies that the Settings class correctly identifies overridden
        settings by checking the presence of specific settings in a simulated module.
        It ensures that the 'is_overridden' method returns True for settings that are
        defined in the module and False for settings that are not defined.

        The test scenario involves setting up a fake settings module with a SECRET_KEY
        and verifying that this setting is detected as overridden. Additionally, it
        checks that a non-existent setting (ALLOWED_HOSTS) is correctly identified as
        not overridden.

        The test setup and teardown involve creating and removing the fake settings
        module from the system modules to prevent any interference with other tests.

        """
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
        """

        Tests whether the override_settings context manager correctly overrides the ALLOWED_HOSTS setting.

        This test case verifies that the setting is not initially overridden, then checks that the override_settings context manager successfully overrides it, and finally ensures that the setting is defaulted back after exiting the context manager.

        The purpose of this test is to ensure that the override_settings functionality works as expected, allowing for safe and temporary modification of settings during testing.

        """
        self.assertFalse(settings.is_overridden("ALLOWED_HOSTS"))
        with override_settings(ALLOWED_HOSTS=[]):
            self.assertTrue(settings.is_overridden("ALLOWED_HOSTS"))

    def test_unevaluated_lazysettings_repr(self):
        """
        Tests that the representation of a LazySettings instance that has not been evaluated is correctly formatted.

        Checks that the string representation of an unevaluated LazySettings object matches the expected format, 
        indicating its unevaluated state.
        """
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
        lazy_settings = LazySettings()
        lazy_settings.configure(APPEND_SLASH=False)
        expected = "<UserSettingsHolder>"
        self.assertEqual(repr(lazy_settings._wrapped), expected)

    def test_settings_repr(self):
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

        Tests that tuple settings are correctly validated.

        This test checks that settings which are expected to be lists or tuples raise an
        ImproperlyConfigured exception when they are not. It iterates over a list of
        settings which should be lists or tuples, sets each one to a non-list or tuple
        value, and attempts to create a Settings object with the invalid setting.

        The test verifies that the expected error message is raised, including the name
        of the invalid setting. After each test, the fake settings module is cleaned
        up to avoid interfering with other tests.

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
        """
        Sets up the test environment by connecting the receiver and spy receiver functions to the setting_changed signal, 
        ensuring they are properly disconnected after the test is completed to prevent interference with other tests. 
        This allows for the monitoring and verification of the setting_changed signal during the test execution.
        """
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
