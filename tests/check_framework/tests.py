import multiprocessing
import sys
from io import StringIO
from unittest import skipIf

from django.apps import apps
from django.core import checks
from django.core.checks import Error, Warning
from django.core.checks.messages import CheckMessage
from django.core.checks.registry import CheckRegistry
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import models
from django.test import SimpleTestCase
from django.test.utils import isolate_apps, override_settings, override_system_checks

from .models import SimpleModel, my_check


class DummyObj:
    def __repr__(self):
        return "obj"


class SystemCheckFrameworkTests(SimpleTestCase):
    def test_register_and_run_checks(self):
        """

        Tests the registration and execution of checks in the CheckRegistry.

        This function verifies that checks can be successfully registered and run,
        producing the expected output. It tests the registration process using two
        different methods: decorator-based and explicit registration. The function
        then runs the registered checks with various filtering options, including tags
        and deployment checks, to ensure the correct checks are executed and the 
        expected errors are reported.

        """
        def f(**kwargs):
            calls[0] += 1
            return [1, 2, 3]

        def f2(**kwargs):
            return [4]

        def f3(**kwargs):
            return [5]

        calls = [0]

        # test register as decorator
        registry = CheckRegistry()
        registry.register()(f)
        registry.register("tag1", "tag2")(f2)
        registry.register("tag2", deploy=True)(f3)

        # test register as function
        registry2 = CheckRegistry()
        registry2.register(f)
        registry2.register(f2, "tag1", "tag2")
        registry2.register(f3, "tag2", deploy=True)

        # check results
        errors = registry.run_checks()
        errors2 = registry2.run_checks()
        self.assertEqual(errors, errors2)
        self.assertEqual(sorted(errors), [1, 2, 3, 4])
        self.assertEqual(calls[0], 2)

        errors = registry.run_checks(tags=["tag1"])
        errors2 = registry2.run_checks(tags=["tag1"])
        self.assertEqual(errors, errors2)
        self.assertEqual(sorted(errors), [4])

        errors = registry.run_checks(
            tags=["tag1", "tag2"], include_deployment_checks=True
        )
        errors2 = registry2.run_checks(
            tags=["tag1", "tag2"], include_deployment_checks=True
        )
        self.assertEqual(errors, errors2)
        self.assertEqual(sorted(errors), [4, 5])

    def test_register_no_kwargs_error(self):
        registry = CheckRegistry()
        msg = "Check functions must accept keyword arguments (**kwargs)."
        with self.assertRaisesMessage(TypeError, msg):

            @registry.register
            def no_kwargs(app_configs, databases):
                pass

    def test_register_run_checks_non_iterable(self):
        registry = CheckRegistry()

        @registry.register
        def return_non_iterable(**kwargs):
            return Error("Message")

        msg = (
            "The function %r did not return a list. All functions registered "
            "with the checks registry must return a list." % return_non_iterable
        )
        with self.assertRaisesMessage(TypeError, msg):
            registry.run_checks()


class MessageTests(SimpleTestCase):
    def test_printing(self):
        """

        Tests the string representation of the Error class to ensure it correctly formats the error message, object, and hint.

        The test checks that the error message is printed on the first line, followed by the hint indented on the next line, prefixed with 'HINT: '.

        """
        e = Error("Message", hint="Hint", obj=DummyObj())
        expected = "obj: Message\n\tHINT: Hint"
        self.assertEqual(str(e), expected)

    def test_printing_no_hint(self):
        e = Error("Message", obj=DummyObj())
        expected = "obj: Message"
        self.assertEqual(str(e), expected)

    def test_printing_no_object(self):
        e = Error("Message", hint="Hint")
        expected = "?: Message\n\tHINT: Hint"
        self.assertEqual(str(e), expected)

    def test_printing_with_given_id(self):
        """

        Tests the string representation of an Error object when an ID is provided.

        Verifies that the error message, hint, and object ID are correctly formatted
        in the expected output string.

        The output string should include the object ID, the error message, and the hint,
        with proper indentation and formatting.

        """
        e = Error("Message", hint="Hint", obj=DummyObj(), id="ID")
        expected = "obj: (ID) Message\n\tHINT: Hint"
        self.assertEqual(str(e), expected)

    def test_printing_field_error(self):
        field = SimpleModel._meta.get_field("field")
        e = Error("Error", obj=field)
        expected = "check_framework.SimpleModel.field: Error"
        self.assertEqual(str(e), expected)

    def test_printing_model_error(self):
        e = Error("Error", obj=SimpleModel)
        expected = "check_framework.SimpleModel: Error"
        self.assertEqual(str(e), expected)

    def test_printing_manager_error(self):
        manager = SimpleModel.manager
        e = Error("Error", obj=manager)
        expected = "check_framework.SimpleModel.manager: Error"
        self.assertEqual(str(e), expected)

    def test_equal_to_self(self):
        """
        Tests that an Error instance is equal to itself.

        This ensures that the equality operator (==) correctly handles instances of the Error class, 
        returning True when comparing an instance to itself. This is a fundamental property for 
        objects and is necessary for various use cases such as storing and comparing errors in 
        collections or data structures.
        """
        e = Error("Error", obj=SimpleModel)
        self.assertEqual(e, e)

    def test_equal_to_same_constructed_check(self):
        """
        Checks that two Error instances constructed with the same parameters are considered equal.

        Verifies that errors with the same error message and associated object are treated as identical, 
        regardless of being separate instances. This ensures that equality checks work as expected 
        for Error instances with the same construction parameters.
        """
        e1 = Error("Error", obj=SimpleModel)
        e2 = Error("Error", obj=SimpleModel)
        self.assertEqual(e1, e2)

    def test_not_equal_to_different_constructed_check(self):
        e1 = Error("Error", obj=SimpleModel)
        e2 = Error("Error2", obj=SimpleModel)
        self.assertNotEqual(e1, e2)

    def test_not_equal_to_non_check(self):
        """
        Tests that an Error object is not equal to a string.

        This test case verifies that the equality comparison between an Error object and 
        a string returns False, as expected. It ensures that the Error object's unique 
        attributes are not inadvertently treated as equal to a string, which could lead 
        to unexpected behavior in the application.

        The test uses a dummy object as the source of the error to isolate the test 
        from specific error details, focusing solely on the equality comparison aspect.
        """
        e = Error("Error", obj=DummyObj())
        self.assertNotEqual(e, "a string")

    def test_invalid_level(self):
        """
        Tests that a TypeError is raised when an invalid level is provided to CheckMessage.

        Verifies that the error message correctly indicates the expected type of the first argument, 
        which should represent the log level of the message. This ensures that the function correctly 
        validates its input parameters and provides informative error messages in case of invalid input.
        """
        msg = "The first argument should be level."
        with self.assertRaisesMessage(TypeError, msg):
            CheckMessage("ERROR", "Message")


def simple_system_check(**kwargs):
    simple_system_check.kwargs = kwargs
    return []


def tagged_system_check(**kwargs):
    tagged_system_check.kwargs = kwargs
    return [checks.Warning("System Check")]


tagged_system_check.tags = ["simpletag"]


def deployment_system_check(**kwargs):
    """
    Performs a deployment system check, triggering a warning for deployment verification.

     :param kwargs: Keyword arguments to customize the check (implementation details vary).
     :return: A list containing a Warning object indicating the deployment check.

     This function facilitates the examination of a deployment system, returning an alert to signal 
     the performance of a deployment verification check. The input keyword arguments are stored 
     for potential use during the check process. The function returns a list with a single Warning 
     object, designated as 'Deployment Check'. The specifics of the verification process depend 
     on the system being checked and the provided keyword arguments. 
    """
    deployment_system_check.kwargs = kwargs
    return [checks.Warning("Deployment Check")]


deployment_system_check.tags = ["deploymenttag"]


class CheckCommandTests(SimpleTestCase):
    def setUp(self):
        """

        Set up the test environment by resetting system check kwargs and redirecting standard output and error streams.

        This function is called before each test to ensure a clean setup. It resets the keyword arguments for simple and tagged system checks,
        and temporarily redirects the standard output and error streams to in-memory buffers, allowing for controlled output capture and verification.

        """
        simple_system_check.kwargs = None
        tagged_system_check.kwargs = None
        self.old_stdout, self.old_stderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = StringIO(), StringIO()

    def tearDown(self):
        sys.stdout, sys.stderr = self.old_stdout, self.old_stderr

    @override_system_checks([simple_system_check, tagged_system_check])
    def test_simple_call(self):
        call_command("check")
        self.assertEqual(
            simple_system_check.kwargs, {"app_configs": None, "databases": None}
        )
        self.assertEqual(
            tagged_system_check.kwargs, {"app_configs": None, "databases": None}
        )

    @override_system_checks([simple_system_check, tagged_system_check])
    def test_given_app(self):
        call_command("check", "auth", "admin")
        auth_config = apps.get_app_config("auth")
        admin_config = apps.get_app_config("admin")
        self.assertEqual(
            simple_system_check.kwargs,
            {"app_configs": [auth_config, admin_config], "databases": None},
        )
        self.assertEqual(
            tagged_system_check.kwargs,
            {"app_configs": [auth_config, admin_config], "databases": None},
        )

    @override_system_checks([simple_system_check, tagged_system_check])
    def test_given_tag(self):
        """
        Tests the behavior of the system when given a specific tag.

        This test case verifies that the correct system checks are executed when a tag is provided.
        It checks that the simple system check does not receive any keyword arguments and
        that the tagged system check receives the expected keyword arguments.

        The purpose of this test is to ensure that the system correctly handles tagged checks
        and that the checks are executed with the correct parameters.
        """
        call_command("check", tags=["simpletag"])
        self.assertIsNone(simple_system_check.kwargs)
        self.assertEqual(
            tagged_system_check.kwargs, {"app_configs": None, "databases": None}
        )

    @override_system_checks([simple_system_check, tagged_system_check])
    def test_invalid_tag(self):
        msg = 'There is no system check with the "missingtag" tag.'
        with self.assertRaisesMessage(CommandError, msg):
            call_command("check", tags=["missingtag"])

    @override_system_checks([simple_system_check])
    def test_list_tags_empty(self):
        """
        Tests that listing tags produces the expected output when there are no tags.

            Verifies that the command to list tags, when executed without any tags present, 
            returns an empty response as expected. This ensures the correctness of the 
            tag listing functionality in the absence of any tags.

            :return: None
        """
        call_command("check", list_tags=True)
        self.assertEqual("\n", sys.stdout.getvalue())

    @override_system_checks([tagged_system_check])
    def test_list_tags(self):
        call_command("check", list_tags=True)
        self.assertEqual("simpletag\n", sys.stdout.getvalue())

    @override_system_checks(
        [tagged_system_check], deployment_checks=[deployment_system_check]
    )
    def test_list_deployment_check_omitted(self):
        """

        Tests the listing of deployment checks when a system check is tagged and omitted from deployment checks.

        Verifies that the check command with list_tags option returns the expected tagged system checks, 
        while respecting the overridden system checks and deployment checks configuration.

        """
        call_command("check", list_tags=True)
        self.assertEqual("simpletag\n", sys.stdout.getvalue())

    @override_system_checks(
        [tagged_system_check], deployment_checks=[deployment_system_check]
    )
    def test_list_deployment_check_included(self):
        """
        Tests that the :func:`check` command correctly lists deployment checks when the --deploy and --list-tags options are provided.

        This test case verifies that the command outputs the expected deployment tags, including the 'deploymenttag' and 'simpletag' tags, when the relevant system checks are overridden. The test checks the standard output to ensure it matches the expected result.

        :returns: None
        :raises: AssertionError if the command output does not match the expected result
        """
        call_command("check", deploy=True, list_tags=True)
        self.assertEqual("deploymenttag\nsimpletag\n", sys.stdout.getvalue())

    @override_system_checks(
        [tagged_system_check], deployment_checks=[deployment_system_check]
    )
    def test_tags_deployment_check_omitted(self):
        """

        Tests that a CommandError is raised when the 'check' command is called with a 
        'deploymenttag' tag but no corresponding system check is found.

        The test asserts that an error message is displayed indicating the absence of 
        a system check tagged with 'deploymenttag'.

        This test case helps ensure that the system check framework correctly handles 
        situations where a requested tag does not have a corresponding system check.

        """
        msg = 'There is no system check with the "deploymenttag" tag.'
        with self.assertRaisesMessage(CommandError, msg):
            call_command("check", tags=["deploymenttag"])

    @override_system_checks(
        [tagged_system_check], deployment_checks=[deployment_system_check]
    )
    def test_tags_deployment_check_included(self):
        call_command("check", deploy=True, tags=["deploymenttag"])
        self.assertIn("Deployment Check", sys.stderr.getvalue())

    @override_system_checks([tagged_system_check])
    def test_fail_level(self):
        """

        Tests that the command fails when the fail level is set to warning.

        This test case checks the behavior of the system when running the check command
        with a fail level of 'WARNING'. It verifies that the command raises a CommandError
        as expected, ensuring that the system correctly handles warnings as failures.

        """
        with self.assertRaises(CommandError):
            call_command("check", fail_level="WARNING")


def custom_error_system_check(app_configs, **kwargs):
    return [Error("Error", id="myerrorcheck.E001")]


def custom_warning_system_check(app_configs, **kwargs):
    return [Warning("Warning", id="mywarningcheck.E001")]


class SilencingCheckTests(SimpleTestCase):
    def setUp(self):
        """
        Set up the test environment by redirecting standard output and standard error streams.

        This function captures the original stdout and stderr, and replaces them with in-memory buffers for the duration of the test.
        The captured output can be used for assertions and verification of the test results.

        Note: This function is typically used as part of a test suite setup, and should be called before running tests that produce output to stdout or stderr.
        """
        self.old_stdout, self.old_stderr = sys.stdout, sys.stderr
        self.stdout, self.stderr = StringIO(), StringIO()
        sys.stdout, sys.stderr = self.stdout, self.stderr

    def tearDown(self):
        sys.stdout, sys.stderr = self.old_stdout, self.old_stderr

    @override_settings(SILENCED_SYSTEM_CHECKS=["myerrorcheck.E001"])
    @override_system_checks([custom_error_system_check])
    def test_silenced_error(self):
        """

        Tests that silenced system checks are correctly handled.

        This test case verifies that the system check command correctly identifies and reports
        silenced errors, and that the output accurately reflects the number of silenced issues.
        The test also ensures that no error messages are printed to the standard error stream.

        """
        out = StringIO()
        err = StringIO()
        call_command("check", stdout=out, stderr=err)
        self.assertEqual(
            out.getvalue(), "System check identified no issues (1 silenced).\n"
        )
        self.assertEqual(err.getvalue(), "")

    @override_settings(SILENCED_SYSTEM_CHECKS=["mywarningcheck.E001"])
    @override_system_checks([custom_warning_system_check])
    def test_silenced_warning(self):
        """

        Tests that system checks are accurately reporting silenced warnings.

        This test overrides the default system checks to include a custom warning check,
        and then simulates running the 'check' command. It verifies that the command output
        indicates no issues were found, but also notes that one warning was silenced.

        """
        out = StringIO()
        err = StringIO()
        call_command("check", stdout=out, stderr=err)
        self.assertEqual(
            out.getvalue(), "System check identified no issues (1 silenced).\n"
        )
        self.assertEqual(err.getvalue(), "")


class CheckFrameworkReservedNamesTests(SimpleTestCase):
    @isolate_apps("check_framework", kwarg_name="apps")
    @override_system_checks([checks.model_checks.check_all_models])
    def test_model_check_method_not_shadowed(self, apps):
        """
        Tests whether Django's model check method is not overridden by model attributes, fields, or descriptors.

        This test case covers four different scenarios where the `check` method is shadowed:
        - by a model attribute
        - by a model field
        - by a related manager
        - by a descriptor

        It verifies that running system checks on these models raises the expected errors, specifically the `models.E020` error which indicates that a model's `check` method is being overridden. The test ensures that the error messages are correctly generated and match the expected output.
        """
        class ModelWithAttributeCalledCheck(models.Model):
            check = 42

        class ModelWithFieldCalledCheck(models.Model):
            check = models.IntegerField()

        class ModelWithRelatedManagerCalledCheck(models.Model):
            pass

        class ModelWithDescriptorCalledCheck(models.Model):
            check = models.ForeignKey(
                ModelWithRelatedManagerCalledCheck, models.CASCADE
            )
            article = models.ForeignKey(
                ModelWithRelatedManagerCalledCheck,
                models.CASCADE,
                related_name="check",
            )

        errors = checks.run_checks(app_configs=apps.get_app_configs())
        expected = [
            Error(
                "The 'ModelWithAttributeCalledCheck.check()' class method is "
                "currently overridden by 42.",
                obj=ModelWithAttributeCalledCheck,
                id="models.E020",
            ),
            Error(
                "The 'ModelWithFieldCalledCheck.check()' class method is "
                "currently overridden by %r." % ModelWithFieldCalledCheck.check,
                obj=ModelWithFieldCalledCheck,
                id="models.E020",
            ),
            Error(
                "The 'ModelWithRelatedManagerCalledCheck.check()' class method is "
                "currently overridden by %r."
                % ModelWithRelatedManagerCalledCheck.check,
                obj=ModelWithRelatedManagerCalledCheck,
                id="models.E020",
            ),
            Error(
                "The 'ModelWithDescriptorCalledCheck.check()' class method is "
                "currently overridden by %r." % ModelWithDescriptorCalledCheck.check,
                obj=ModelWithDescriptorCalledCheck,
                id="models.E020",
            ),
        ]
        self.assertEqual(errors, expected)


@skipIf(
    multiprocessing.get_start_method() == "spawn",
    "Spawning reimports modules, overwriting my_check.did_run to False, making this "
    "test useless.",
)
class ChecksRunDuringTests(SimpleTestCase):
    databases = "__all__"

    def test_registered_check_did_run(self):
        self.assertTrue(my_check.did_run)
