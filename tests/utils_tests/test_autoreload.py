import contextlib
import os
import py_compile
import shutil
import sys
import tempfile
import threading
import time
import types
import weakref
import zipfile
import zoneinfo
from importlib import import_module
from pathlib import Path
from subprocess import CompletedProcess
from unittest import mock, skip, skipIf

import django.__main__
from django.apps.registry import Apps
from django.test import SimpleTestCase
from django.test.utils import extend_sys_path
from django.utils import autoreload
from django.utils.autoreload import WatchmanUnavailable

from .test_module import __main__ as test_main
from .test_module import main_module as test_main_module
from .utils import on_macos_with_hfs


class TestIterModulesAndFiles(SimpleTestCase):
    def import_and_cleanup(self, name):
        """
        Imports a module by its given name and schedules cleanup operations to maintain a clean state after the import.

        This function dynamically imports a module based on the provided name, allowing for flexible loading of modules.
        After the import, it sets up two cleanup actions to ensure the environment remains consistent:
        - Clears the system's path importer cache to prevent stale references.
        - Removes the imported module from the system's modules dictionary to avoid pollution.

        OE (Note that cleanup operations are not performed immediately but are scheduled to run after the function has completed its execution.)
        """
        import_module(name)
        self.addCleanup(lambda: sys.path_importer_cache.clear())
        self.addCleanup(lambda: sys.modules.pop(name, None))

    def clear_autoreload_caches(self):
        autoreload.iter_modules_and_files.cache_clear()

    def assertFileFound(self, filename):
        # Some temp directories are symlinks. Python resolves these fully while
        # importing.
        """
        Verifies that a specific Python file is found and properly cached by the autoreload system.

        This assertion checks that the given filename is resolvable and exists within the set of all Python module files tracked by autoreload.
        It also ensures that the autoreload cache is correctly populated and that subsequent lookups of the same file will return a cached result.

        :param filename: The file to be checked for existence and caching.

        """
        resolved_filename = filename.resolve(strict=True)
        self.clear_autoreload_caches()
        # Test uncached access
        self.assertIn(
            resolved_filename, list(autoreload.iter_all_python_module_files())
        )
        # Test cached access
        self.assertIn(
            resolved_filename, list(autoreload.iter_all_python_module_files())
        )
        self.assertEqual(autoreload.iter_modules_and_files.cache_info().hits, 1)

    def assertFileNotFound(self, filename):
        """
        Asserts that a given file does not exist in the current Python module search path.

        This function first resolves the provided filename to its absolute path. It then checks 
        that the resolved filename is not present in the list of all Python module files. 
        Additionally, it verifies that the autoreload cache has not been consulted more than once, 
        indicating that the file was not found. 

        Parameters
        ----------
        filename : path-like object
            The filename to check for existence.

        Raises
        ------
        AssertionError
            If the file is found in the list of Python module files or the autoreload cache is hit 
            more than once.

        """
        resolved_filename = filename.resolve(strict=True)
        self.clear_autoreload_caches()
        # Test uncached access
        self.assertNotIn(
            resolved_filename, list(autoreload.iter_all_python_module_files())
        )
        # Test cached access
        self.assertNotIn(
            resolved_filename, list(autoreload.iter_all_python_module_files())
        )
        self.assertEqual(autoreload.iter_modules_and_files.cache_info().hits, 1)

    def temporary_file(self, filename):
        dirname = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, dirname)
        return Path(dirname) / filename

    def test_paths_are_pathlib_instances(self):
        for filename in autoreload.iter_all_python_module_files():
            self.assertIsInstance(filename, Path)

    def test_file_added(self):
        """
        When a file is added, it's returned by iter_all_python_module_files().
        """
        filename = self.temporary_file("test_deleted_removed_module.py")
        filename.touch()

        with extend_sys_path(str(filename.parent)):
            self.import_and_cleanup("test_deleted_removed_module")

        self.assertFileFound(filename.absolute())

    def test_check_errors(self):
        """
        When a file containing an error is imported in a function wrapped by
        check_errors(), gen_filenames() returns it.
        """
        filename = self.temporary_file("test_syntax_error.py")
        filename.write_text("Ceci n'est pas du Python.")

        with extend_sys_path(str(filename.parent)):
            try:
                with self.assertRaises(SyntaxError):
                    autoreload.check_errors(import_module)("test_syntax_error")
            finally:
                autoreload._exception = None
        self.assertFileFound(filename)

    def test_check_errors_catches_all_exceptions(self):
        """
        Since Python may raise arbitrary exceptions when importing code,
        check_errors() must catch Exception, not just some subclasses.
        """
        filename = self.temporary_file("test_exception.py")
        filename.write_text("raise Exception")
        with extend_sys_path(str(filename.parent)):
            try:
                with self.assertRaises(Exception):
                    autoreload.check_errors(import_module)("test_exception")
            finally:
                autoreload._exception = None
        self.assertFileFound(filename)

    def test_zip_reload(self):
        """
        Modules imported from zipped files have their archive location included
        in the result.
        """
        zip_file = self.temporary_file("zip_import.zip")
        with zipfile.ZipFile(str(zip_file), "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.writestr("test_zipped_file.py", "")

        with extend_sys_path(str(zip_file)):
            self.import_and_cleanup("test_zipped_file")
        self.assertFileFound(zip_file)

    def test_bytecode_conversion_to_source(self):
        """.pyc and .pyo files are included in the files list."""
        filename = self.temporary_file("test_compiled.py")
        filename.touch()
        compiled_file = Path(
            py_compile.compile(str(filename), str(filename.with_suffix(".pyc")))
        )
        filename.unlink()
        with extend_sys_path(str(compiled_file.parent)):
            self.import_and_cleanup("test_compiled")
        self.assertFileFound(compiled_file)

    def test_weakref_in_sys_module(self):
        """iter_all_python_module_file() ignores weakref modules."""
        time_proxy = weakref.proxy(time)
        sys.modules["time_proxy"] = time_proxy
        self.addCleanup(lambda: sys.modules.pop("time_proxy", None))
        list(autoreload.iter_all_python_module_files())  # No crash.

    def test_module_without_spec(self):
        """
        Tests that a module without a specification is correctly handled by the autoreload module iteration function.

        The function verifies that when a module is missing its specification (i.e., its `__spec__` attribute has been deleted), 
        the autoreload function `iter_modules_and_files` returns an empty set of modules and files, 
        as expected for a module that cannot be properly reloaded.
        """
        module = types.ModuleType("test_module")
        del module.__spec__
        self.assertEqual(
            autoreload.iter_modules_and_files((module,), frozenset()), frozenset()
        )

    def test_main_module_is_resolved(self):
        main_module = sys.modules["__main__"]
        self.assertFileFound(Path(main_module.__file__))

    def test_main_module_without_file_is_not_resolved(self):
        """
        Tests that the main module is not resolved when no files are provided to the autoreload module iterator. 

        This ensures that autoreload correctly handles cases where only a module is given, without any associated files, and verifies that no modules or files are returned in such a scenario.
        """
        fake_main = types.ModuleType("__main__")
        self.assertEqual(
            autoreload.iter_modules_and_files((fake_main,), frozenset()), frozenset()
        )

    def test_path_with_embedded_null_bytes(self):
        """

        Tests if autoreload correctly handles file system paths containing embedded null bytes.

        This function checks that the autoreload functionality ignores files and directories
        with names containing null bytes, as these are invalid in most operating systems.
        It verifies this behavior by attempting to iterate over modules and files in a set
        of paths containing embedded null bytes and asserting that an empty set is returned.

        """
        for path in (
            "embedded_null_byte\x00.py",
            "di\x00rectory/embedded_null_byte.py",
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    autoreload.iter_modules_and_files((), frozenset([path])),
                    frozenset(),
                )


class TestChildArguments(SimpleTestCase):
    @mock.patch.dict(sys.modules, {"__main__": django.__main__})
    @mock.patch("sys.argv", [django.__main__.__file__, "runserver"])
    @mock.patch("sys.warnoptions", [])
    @mock.patch("sys._xoptions", {})
    def test_run_as_module(self):
        self.assertEqual(
            autoreload.get_child_arguments(),
            [sys.executable, "-m", "django", "runserver"],
        )

    @mock.patch.dict(sys.modules, {"__main__": test_main})
    @mock.patch("sys.argv", [test_main.__file__, "runserver"])
    @mock.patch("sys.warnoptions", [])
    @mock.patch("sys._xoptions", {})
    def test_run_as_non_django_module(self):
        self.assertEqual(
            autoreload.get_child_arguments(),
            [sys.executable, "-m", "utils_tests.test_module", "runserver"],
        )

    @mock.patch.dict(sys.modules, {"__main__": test_main_module})
    @mock.patch("sys.argv", [test_main.__file__, "runserver"])
    @mock.patch("sys.warnoptions", [])
    @mock.patch("sys._xoptions", {})
    def test_run_as_non_django_module_non_package(self):
        self.assertEqual(
            autoreload.get_child_arguments(),
            [sys.executable, "-m", "utils_tests.test_module.main_module", "runserver"],
        )

    @mock.patch("__main__.__spec__", None)
    @mock.patch("sys.argv", [__file__, "runserver"])
    @mock.patch("sys.warnoptions", ["error"])
    @mock.patch("sys._xoptions", {})
    def test_warnoptions(self):
        self.assertEqual(
            autoreload.get_child_arguments(),
            [sys.executable, "-Werror", __file__, "runserver"],
        )

    @mock.patch("sys.argv", [__file__, "runserver"])
    @mock.patch("sys.warnoptions", [])
    @mock.patch("sys._xoptions", {"utf8": True, "a": "b"})
    def test_xoptions(self):
        self.assertEqual(
            autoreload.get_child_arguments(),
            [sys.executable, "-Xutf8", "-Xa=b", __file__, "runserver"],
        )

    @mock.patch("__main__.__spec__", None)
    @mock.patch("sys.warnoptions", [])
    def test_exe_fallback(self):
        """

        Tests the fallback behavior of the autoreload module when determining the executable path.

        This test case simulates a Windows environment by creating a temporary directory with an executable file 'django-admin.exe'.
        It then verifies that the autoreload module correctly identifies the executable path and returns the expected child arguments.

        The expected output is a list containing the executable path and the 'runserver' command, demonstrating that the autoreload module
        can correctly handle the fallback scenario when determining the executable path.

        """
        with tempfile.TemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir) / "django-admin.exe"
            exe_path.touch()
            with mock.patch("sys.argv", [exe_path.with_suffix(""), "runserver"]):
                self.assertEqual(
                    autoreload.get_child_arguments(), [exe_path, "runserver"]
                )

    @mock.patch("sys.warnoptions", [])
    @mock.patch.dict(sys.modules, {"__main__": django.__main__})
    def test_use_exe_when_main_spec(self):
        """
        Tests the use of an executable when running Django as the main module.

        This test case verifies the logic for determining the child arguments for the 
        autoreloader when an executable is present. It simulates a scenario where 
        Django is run from an executable file (e.g., `django-admin.exe`) and checks 
        that the correct arguments are passed to the autoreloader.

        The test creates a temporary executable file, sets up a mock environment to 
        simulate running Django as the main module, and then checks the output of the 
        `get_child_arguments` function. The expected result is a list containing the 
        path to the executable and the `runserver` command.

        This test ensures that the autoreloader behaves correctly when running Django 
        from an executable file, which is an important use case for Django development.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            exe_path = Path(tmpdir) / "django-admin.exe"
            exe_path.touch()
            with mock.patch("sys.argv", [exe_path.with_suffix(""), "runserver"]):
                self.assertEqual(
                    autoreload.get_child_arguments(), [exe_path, "runserver"]
                )

    @mock.patch("__main__.__spec__", None)
    @mock.patch("sys.warnoptions", [])
    @mock.patch("sys._xoptions", {})
    def test_entrypoint_fallback(self):
        """

        Tests the entrypoint fallback mechanism for the autoreload module.

        This test ensures that when the entrypoint is not properly specified, the 
        autoreload module correctly identifies the script to be executed and its 
        arguments. It simulates a temporary directory with a script and verifies 
        that the get_child_arguments function returns the correct executable, 
        script path, and command-line arguments.

        The test covers a scenario where the entrypoint falls back to using the 
        script path and command-line arguments from sys.argv, and checks that 
        the autoreload module behaves as expected in this case.

        """
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "django-admin-script.py"
            script_path.touch()
            with mock.patch(
                "sys.argv", [script_path.with_name("django-admin"), "runserver"]
            ):
                self.assertEqual(
                    autoreload.get_child_arguments(),
                    [sys.executable, script_path, "runserver"],
                )

    @mock.patch("__main__.__spec__", None)
    @mock.patch("sys.argv", ["does-not-exist", "runserver"])
    @mock.patch("sys.warnoptions", [])
    def test_raises_runtimeerror(self):
        """
        Tests that autoreload.get_child_arguments raises a RuntimeError when the script does not exist.

        The function is expected to throw an error when it encounters a non-existent script, indicating that the child arguments cannot be retrieved.

        :raises RuntimeError: If the script specified in sys.argv does not exist.
        :note: This test validates the error handling behavior of autoreload.get_child_arguments in the presence of an invalid script.

        """
        msg = "Script does-not-exist does not exist."
        with self.assertRaisesMessage(RuntimeError, msg):
            autoreload.get_child_arguments()

    @mock.patch("sys.argv", [__file__, "runserver"])
    @mock.patch("sys.warnoptions", [])
    @mock.patch("sys._xoptions", {})
    def test_module_no_spec(self):
        """

        Tests the autoreload.get_child_arguments function in the context of a module with no specification.

        This test case simulates the execution of a module with missing specification,
        and verifies that get_child_arguments correctly returns the expected arguments.

        The test sets up a mock environment by patching sys.argv, sys.warnoptions, and sys._xoptions,
        and creates a mock module without a specification. It then tests the get_child_arguments function
        by asserting that it returns the expected list of child arguments, which includes the Python executable,
        the current file, and the 'runserver' command.

        """
        module = types.ModuleType("test_module")
        del module.__spec__
        with mock.patch.dict(sys.modules, {"__main__": module}):
            self.assertEqual(
                autoreload.get_child_arguments(),
                [sys.executable, __file__, "runserver"],
            )


class TestUtilities(SimpleTestCase):
    def test_is_django_module(self):
        for module, expected in ((zoneinfo, False), (sys, False), (autoreload, True)):
            with self.subTest(module=module):
                self.assertIs(autoreload.is_django_module(module), expected)

    def test_is_django_path(self):
        """
        Tests the is_django_path function to determine if a given module path originates from Django.

        Verifies the function's behavior on various module paths, including those from standard library and Django-specific modules, ensuring correct identification of Django paths.

         module: The Python module file path being evaluated
         expected: A boolean indicating whether the module path is expected to be identified as a Django path

        The test coverage includes modules from the standard library and Django-specific modules to ensure the is_django_path function behaves as expected in different scenarios.
        """
        for module, expected in (
            (zoneinfo.__file__, False),
            (contextlib.__file__, False),
            (autoreload.__file__, True),
        ):
            with self.subTest(module=module):
                self.assertIs(autoreload.is_django_path(module), expected)


class TestCommonRoots(SimpleTestCase):
    def test_common_roots(self):
        """
        Tests that the common_roots function correctly identifies the most common root paths among a given set of paths.

        This test ensures that the function can handle both full and partial path matches, as well as distinguish between paths with distinct roots. The expected output includes the most common root paths that appear across the input set.

        Parameters: None
        Returns: None
        """
        paths = (
            Path("/first/second"),
            Path("/first/second/third"),
            Path("/first/"),
            Path("/root/first/"),
        )
        results = autoreload.common_roots(paths)
        self.assertCountEqual(results, [Path("/first/"), Path("/root/first/")])


class TestSysPathDirectories(SimpleTestCase):
    def setUp(self):
        """

        Set up a temporary test environment.

        Creates a temporary directory and file for use in testing, ensuring proper cleanup
        after the test is completed. The temporary directory and file are stored as instance
        attributes for use in subsequent test methods.

        """
        _directory = tempfile.TemporaryDirectory()
        self.addCleanup(_directory.cleanup)
        self.directory = Path(_directory.name).resolve(strict=True).absolute()
        self.file = self.directory / "test"
        self.file.touch()

    def test_sys_paths_with_directories(self):
        with extend_sys_path(str(self.file)):
            paths = list(autoreload.sys_path_directories())
        self.assertIn(self.file.parent, paths)

    def test_sys_paths_non_existing(self):
        nonexistent_file = Path(self.directory.name) / "does_not_exist"
        with extend_sys_path(str(nonexistent_file)):
            paths = list(autoreload.sys_path_directories())
        self.assertNotIn(nonexistent_file, paths)
        self.assertNotIn(nonexistent_file.parent, paths)

    def test_sys_paths_absolute(self):
        """
        Test that all system paths returned by sys_path_directories are absolute.

        This test case verifies that the function sys_path_directories() from the autoreload module 
        returns a list of directories where all paths are absolute, i.e., they specify the full path 
        from the root directory to the file or directory.

        """
        paths = list(autoreload.sys_path_directories())
        self.assertTrue(all(p.is_absolute() for p in paths))

    def test_sys_paths_directories(self):
        """

        Checks that a specified directory is included in the system paths after 
        modifying the sys.path using the extend_sys_path context manager.

        Verifies that the provided directory is correctly added to the list of 
        system path directories, ensuring it is discoverable by the autoreload 
        mechanism.

        The test case exercises the extend_sys_path functionality to temporarily 
        modify the sys.path and checks the updated list of sys_path_directories 
        to ensure the specified directory is included.

        """
        with extend_sys_path(str(self.directory)):
            paths = list(autoreload.sys_path_directories())
        self.assertIn(self.directory, paths)


class GetReloaderTests(SimpleTestCase):
    @mock.patch("django.utils.autoreload.WatchmanReloader")
    def test_watchman_unavailable(self, mocked_watchman):
        """

        Tests the fallback behavior of the autoreload system when Watchman is unavailable.

        Verifies that when Watchman cannot be used, the autoreload system defaults to
        using the StatReloader instead.

        Note:
            This test ensures that the autoreload system remains functional even when
            the preferred Watchman reloader is not available.

        """
        mocked_watchman.check_availability.side_effect = WatchmanUnavailable
        self.assertIsInstance(autoreload.get_reloader(), autoreload.StatReloader)

    @mock.patch.object(autoreload.WatchmanReloader, "check_availability")
    def test_watchman_available(self, mocked_available):
        # If WatchmanUnavailable isn't raised, Watchman will be chosen.
        mocked_available.return_value = None
        result = autoreload.get_reloader()
        self.assertIsInstance(result, autoreload.WatchmanReloader)


class RunWithReloaderTests(SimpleTestCase):
    @mock.patch.dict(os.environ, {autoreload.DJANGO_AUTORELOAD_ENV: "true"})
    @mock.patch("django.utils.autoreload.get_reloader")
    def test_swallows_keyboard_interrupt(self, mocked_get_reloader):
        """

        Tests the behavior of the run_with_reloader function when a KeyboardInterrupt exception occurs.

        This test case verifies that the run_with_reloader function properly handles and swallows a KeyboardInterrupt exception, ensuring that the application remains stable and functional even when such an interrupt is encountered.

        The test scenario involves mocking the get_reloader function to raise a KeyboardInterrupt exception and then executing the run_with_reloader function with a no-op callback. The test passes if the exception is successfully caught and handled without terminating the application.

        Parameters
        ----------
        mocked_get_reloader : mock.Mock
            A mock object representing the get_reloader function, configured to raise a KeyboardInterrupt exception when called.

        """
        mocked_get_reloader.side_effect = KeyboardInterrupt()
        autoreload.run_with_reloader(lambda: None)  # No exception

    @mock.patch.dict(os.environ, {autoreload.DJANGO_AUTORELOAD_ENV: "false"})
    @mock.patch("django.utils.autoreload.restart_with_reloader")
    def test_calls_sys_exit(self, mocked_restart_reloader):
        mocked_restart_reloader.return_value = 1
        with self.assertRaises(SystemExit) as exc:
            autoreload.run_with_reloader(lambda: None)
        self.assertEqual(exc.exception.code, 1)

    @mock.patch.dict(os.environ, {autoreload.DJANGO_AUTORELOAD_ENV: "true"})
    @mock.patch("django.utils.autoreload.start_django")
    @mock.patch("django.utils.autoreload.get_reloader")
    def test_calls_start_django(self, mocked_reloader, mocked_start_django):
        """
        Tests the functionality of running a Django application with a reloader.

        The test case verifies that the `start_django` function is called once when the `run_with_reloader` function is invoked. 
        It also checks that the `start_django` function is called with the correct reloader and method arguments. 
        This ensures that the autoreload mechanism is properly integrated with the Django application.
        """
        mocked_reloader.return_value = mock.sentinel.RELOADER
        autoreload.run_with_reloader(mock.sentinel.METHOD)
        self.assertEqual(mocked_start_django.call_count, 1)
        self.assertSequenceEqual(
            mocked_start_django.call_args[0],
            [mock.sentinel.RELOADER, mock.sentinel.METHOD],
        )


class StartDjangoTests(SimpleTestCase):
    @mock.patch("django.utils.autoreload.ensure_echo_on")
    def test_echo_on_called(self, mocked_echo):
        fake_reloader = mock.MagicMock()
        autoreload.start_django(fake_reloader, lambda: None)
        self.assertEqual(mocked_echo.call_count, 1)

    @mock.patch("django.utils.autoreload.check_errors")
    def test_check_errors_called(self, mocked_check_errors):
        fake_method = mock.MagicMock(return_value=None)
        fake_reloader = mock.MagicMock()
        autoreload.start_django(fake_reloader, fake_method)
        self.assertCountEqual(mocked_check_errors.call_args[0], [fake_method])

    @mock.patch("threading.Thread")
    @mock.patch("django.utils.autoreload.check_errors")
    def test_starts_thread_with_args(self, mocked_check_errors, mocked_thread):
        fake_reloader = mock.MagicMock()
        fake_main_func = mock.MagicMock()
        fake_thread = mock.MagicMock()
        mocked_check_errors.return_value = fake_main_func
        mocked_thread.return_value = fake_thread
        autoreload.start_django(fake_reloader, fake_main_func, 123, abc=123)
        self.assertEqual(mocked_thread.call_count, 1)
        self.assertEqual(
            mocked_thread.call_args[1],
            {
                "target": fake_main_func,
                "args": (123,),
                "kwargs": {"abc": 123},
                "name": "django-main-thread",
            },
        )
        self.assertIs(fake_thread.daemon, True)
        self.assertTrue(fake_thread.start.called)


class TestCheckErrors(SimpleTestCase):
    def test_mutates_error_files(self):
        fake_method = mock.MagicMock(side_effect=RuntimeError())
        wrapped = autoreload.check_errors(fake_method)
        with mock.patch.object(autoreload, "_error_files") as mocked_error_files:
            try:
                with self.assertRaises(RuntimeError):
                    wrapped()
            finally:
                autoreload._exception = None
        self.assertEqual(mocked_error_files.append.call_count, 1)


class TestRaiseLastException(SimpleTestCase):
    @mock.patch("django.utils.autoreload._exception", None)
    def test_no_exception(self):
        # Should raise no exception if _exception is None
        autoreload.raise_last_exception()

    def test_raises_exception(self):
        """
        Tests that raise_last_exception correctly raises an exception with the expected message.

        This test case verifies that the function raise_last_exception raises an instance of MyException
        with the specified 'Test Message' when the simulated exception information is provided.

        The test covers the exception handling mechanism and ensures that the function behaves as expected
        when an exception needs to be re-raised. It validates the type of the exception and its associated message,
        providing confidence in the function's ability to handle and propagate exceptions correctly.
        """
        class MyException(Exception):
            pass

        # Create an exception
        try:
            raise MyException("Test Message")
        except MyException:
            exc_info = sys.exc_info()

        with mock.patch("django.utils.autoreload._exception", exc_info):
            with self.assertRaisesMessage(MyException, "Test Message"):
                autoreload.raise_last_exception()

    def test_raises_custom_exception(self):
        """
        Tests whether the custom exception is raised as expected by the autoreload module.

        This test case checks if the autoreload	raise_last_exception function correctly raises a custom exception, 
        MyException, with a specific error message and additional context. The test verifies that the 
        exception is raised with the expected message, ensuring that the custom exception is handled 
        properly by the autoreload module. 

        The test uses a mock patch to simulate the exception being raised and then asserts that the 
        expected exception is raised when autoreload.raise_last_exception is called. 

        The successful execution of this test ensures the custom exception is correctly propagated 
        and handled in the autoreload module, providing a robust and informative error reporting 
        mechanism for users of the module.
        """
        class MyException(Exception):
            def __init__(self, msg, extra_context):
                """
                Initializes the class instance with a message and additional contextual information.

                Parameters
                ----------
                msg : str
                    The primary message to be stored or used by the instance.
                extra_context : dict
                    A dictionary containing extra information to provide more context to the message.

                Notes
                -----
                This initialization also calls the parent class's constructor to set up the primary message.
                The extra context is stored as an instance attribute for later use.
                """
                super().__init__(msg)
                self.extra_context = extra_context

        # Create an exception.
        try:
            raise MyException("Test Message", "extra context")
        except MyException:
            exc_info = sys.exc_info()

        with mock.patch("django.utils.autoreload._exception", exc_info):
            with self.assertRaisesMessage(MyException, "Test Message"):
                autoreload.raise_last_exception()

    def test_raises_exception_with_context(self):
        """

        Tests that the raise_last_exception function correctly raises an exception 
        with the original exception context.

        Verifies that when the original exception is raised, and a new exception 
        is raised with the original exception as its cause, the 
        raise_last_exception function propagates the correct exception information. 

        Specifically, it checks that the raised exception has the correct arguments 
        and cause, ensuring that the original exception context is preserved.

        """
        try:
            raise Exception(2)
        except Exception as e:
            try:
                raise Exception(1) from e
            except Exception:
                exc_info = sys.exc_info()

        with mock.patch("django.utils.autoreload._exception", exc_info):
            with self.assertRaises(Exception) as cm:
                autoreload.raise_last_exception()
            self.assertEqual(cm.exception.args[0], 1)
            self.assertEqual(cm.exception.__cause__.args[0], 2)


class RestartWithReloaderTests(SimpleTestCase):
    executable = "/usr/bin/python"

    def patch_autoreload(self, argv):
        """
        Patches the autoreload functionality in Django to simulate a successful subprocess call.

        This function sets up mock patches for various system attributes and functions to mimic the behavior of the autoreload mechanism. It allows for the specification of the command line arguments (argv) that would be passed to the subprocess.

        The patches are applied to the following attributes and functions:
            - sys.argv
            - sys.executable
            - sys.warnoptions
            - sys._xoptions
            - subprocess.run (in django.utils.autoreload)

        The function returns the mock object for the patched subprocess.run call, which can be used to inspect the interactions with this function.

        After the test is completed, all patches are automatically stopped to restore the original behavior.

        :param argv: The command line arguments to be passed to the subprocess.
        :return: The mock object for the patched subprocess.run call.
        """
        patch_call = mock.patch(
            "django.utils.autoreload.subprocess.run",
            return_value=CompletedProcess(argv, 0),
        )
        patches = [
            mock.patch("django.utils.autoreload.sys.argv", argv),
            mock.patch("django.utils.autoreload.sys.executable", self.executable),
            mock.patch("django.utils.autoreload.sys.warnoptions", ["all"]),
            mock.patch("django.utils.autoreload.sys._xoptions", {}),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        mock_call = patch_call.start()
        self.addCleanup(patch_call.stop)
        return mock_call

    def test_manage_py(self):
        """
        Tests the manage.py script by simulating a runserver command with autoreload enabled.

        This test creates a temporary manage.py script and exercises the autoreload functionality by 
        patching the autoreload call and restarting with a reloader. It verifies that the autoreload 
        call is made once and that the correct command-line arguments are passed.

        The test covers the integration of the manage.py script with the autoreload mechanism, 
        ensuring that the server can be restarted correctly when changes are detected in the codebase.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            script = Path(temp_dir) / "manage.py"
            script.touch()
            argv = [str(script), "runserver"]
            mock_call = self.patch_autoreload(argv)
            with mock.patch("__main__.__spec__", None):
                autoreload.restart_with_reloader()
            self.assertEqual(mock_call.call_count, 1)
            self.assertEqual(
                mock_call.call_args[0][0],
                [self.executable, "-Wall"] + argv,
            )

    def test_python_m_django(self):
        """
        Tests the Django framework's autoreload functionality when running the development server.

        This test case simulates the execution of the Django development server by running the 
        :mod:`django.__main__` module and checks if the autoreload mechanism is triggered correctly.

        The test verifies that the autoreload restarts the server with the correct arguments and 
        that the restart is performed only once.
        """
        main = "/usr/lib/pythonX.Y/site-packages/django/__main__.py"
        argv = [main, "runserver"]
        mock_call = self.patch_autoreload(argv)
        with mock.patch("django.__main__.__file__", main):
            with mock.patch.dict(sys.modules, {"__main__": django.__main__}):
                autoreload.restart_with_reloader()
            self.assertEqual(mock_call.call_count, 1)
            self.assertEqual(
                mock_call.call_args[0][0],
                [self.executable, "-Wall", "-m", "django"] + argv[1:],
            )


class ReloaderTests(SimpleTestCase):
    RELOADER_CLS = None

    def setUp(self):
        """
        Set up the test environment by creating a temporary directory and initializing test files and a reloader.

        This method creates a temporary directory and sets up test files, including an existing file and a nonexistent file.
        It also instantiates a reloader and schedules cleanup tasks to stop the reloader and remove the temporary directory after the test is completed.

        The resulting test environment is used to test the functionality of the class in a isolated and controlled setting.

        Attributes set by this method:
            tempdir (Path): The absolute path to the temporary directory.
            existing_file (Path): The path to an existing test file.
            nonexistent_file (Path): The path to a nonexistent test file.
            reloader: An instance of the reloader class.

        """
        _tempdir = tempfile.TemporaryDirectory()
        self.tempdir = Path(_tempdir.name).resolve(strict=True).absolute()
        self.existing_file = self.ensure_file(self.tempdir / "test.py")
        self.nonexistent_file = (self.tempdir / "does_not_exist.py").absolute()
        self.reloader = self.RELOADER_CLS()
        self.addCleanup(self.reloader.stop)
        self.addCleanup(_tempdir.cleanup)

    def ensure_file(self, path):
        """
        Ensures the existence of a file at the specified path, creating any necessary parent directories and the file itself if they do not already exist.

        The file's last modified time is then updated to the current time.

        Returns the absolute path of the file.
        """
        path.parent.mkdir(exist_ok=True, parents=True)
        path.touch()
        # On Linux and Windows updating the mtime of a file using touch() will
        # set a timestamp value that is in the past, as the time value for the
        # last kernel tick is used rather than getting the correct absolute
        # time.
        # To make testing simpler set the mtime to be the observed time when
        # this function is called.
        self.set_mtime(path, time.time())
        return path.absolute()

    def set_mtime(self, fp, value):
        os.utime(str(fp), (value, value))

    def increment_mtime(self, fp, by=1):
        """
        Increment the last modification time (mtime) of a file.

        Increase the last modification time of the file at the given file path by a specified amount. 

        :param fp: The path to the file.
        :param by: The number of seconds to increment the mtime by (default is 1).

        """
        current_time = time.time()
        self.set_mtime(fp, current_time + by)

    @contextlib.contextmanager
    def tick_twice(self):
        ticker = self.reloader.tick()
        next(ticker)
        yield
        next(ticker)


class IntegrationTests:
    @mock.patch("django.utils.autoreload.BaseReloader.notify_file_changed")
    @mock.patch(
        "django.utils.autoreload.iter_all_python_module_files", return_value=frozenset()
    )
    def test_glob(self, mocked_modules, notify_mock):
        """

        Test that the reloader only notifies of changes to Python files.

        This test ensures that the reloader correctly watches a directory for changes to
        Python files and ignores non-Python files. It checks that when a non-Python file
        and a Python file are modified, the reloader only notifies of the change to the
        Python file.

        """
        non_py_file = self.ensure_file(self.tempdir / "non_py_file")
        self.reloader.watch_dir(self.tempdir, "*.py")
        with self.tick_twice():
            self.increment_mtime(non_py_file)
            self.increment_mtime(self.existing_file)
        self.assertEqual(notify_mock.call_count, 1)
        self.assertCountEqual(notify_mock.call_args[0], [self.existing_file])

    @mock.patch("django.utils.autoreload.BaseReloader.notify_file_changed")
    @mock.patch(
        "django.utils.autoreload.iter_all_python_module_files", return_value=frozenset()
    )
    def test_multiple_globs(self, mocked_modules, notify_mock):
        """
        ```python
        def test_multiple_globs(self, mocked_modules, notify_mock):
            \"\"\"
            Tests the reloader's ability to watch multiple file patterns in a directory.

            Verifies that the reloader correctly identifies and notifies about file changes 
            when watching multiple glob patterns, such as Python files and test files, 
            in a specified directory.

            The test case ensures that the reloader only notifies about changes to files 
            that match the specified patterns and does not trigger false notifications.
            \"\"\"
        ```
        """
        self.ensure_file(self.tempdir / "x.test")
        self.reloader.watch_dir(self.tempdir, "*.py")
        self.reloader.watch_dir(self.tempdir, "*.test")
        with self.tick_twice():
            self.increment_mtime(self.existing_file)
        self.assertEqual(notify_mock.call_count, 1)
        self.assertCountEqual(notify_mock.call_args[0], [self.existing_file])

    @mock.patch("django.utils.autoreload.BaseReloader.notify_file_changed")
    @mock.patch(
        "django.utils.autoreload.iter_all_python_module_files", return_value=frozenset()
    )
    def test_overlapping_globs(self, mocked_modules, notify_mock):
        """

        Tests the behavior of the file reloader when watching for file changes with overlapping glob patterns.

        This test case ensures that when multiple glob patterns overlap for a given file,
        the reloader will only notify of changes to that file once, preventing duplicate notifications.

        The test scenario involves watching a directory for Python files using two different glob patterns,
        then simulating a file modification and verifying that the notification callback is called correctly.

        """
        self.reloader.watch_dir(self.tempdir, "*.py")
        self.reloader.watch_dir(self.tempdir, "*.p*")
        with self.tick_twice():
            self.increment_mtime(self.existing_file)
        self.assertEqual(notify_mock.call_count, 1)
        self.assertCountEqual(notify_mock.call_args[0], [self.existing_file])

    @mock.patch("django.utils.autoreload.BaseReloader.notify_file_changed")
    @mock.patch(
        "django.utils.autoreload.iter_all_python_module_files", return_value=frozenset()
    )
    def test_glob_recursive(self, mocked_modules, notify_mock):
        non_py_file = self.ensure_file(self.tempdir / "dir" / "non_py_file")
        py_file = self.ensure_file(self.tempdir / "dir" / "file.py")
        self.reloader.watch_dir(self.tempdir, "**/*.py")
        with self.tick_twice():
            self.increment_mtime(non_py_file)
            self.increment_mtime(py_file)
        self.assertEqual(notify_mock.call_count, 1)
        self.assertCountEqual(notify_mock.call_args[0], [py_file])

    @mock.patch("django.utils.autoreload.BaseReloader.notify_file_changed")
    @mock.patch(
        "django.utils.autoreload.iter_all_python_module_files", return_value=frozenset()
    )
    def test_multiple_recursive_globs(self, mocked_modules, notify_mock):
        """
        Test that the autoreloader correctly notifies on changes to files matching multiple recursive glob patterns.

        This test verifies that the reloader watches for changes to files matching the specified patterns and notifies the system when modifications occur.
        It checks that both Python and non-Python files are handled correctly, and that notifications are sent in the correct order.
        The test uses mock patches to isolate the dependencies and ensure the test is deterministic and efficient.
        """
        non_py_file = self.ensure_file(self.tempdir / "dir" / "test.txt")
        py_file = self.ensure_file(self.tempdir / "dir" / "file.py")
        self.reloader.watch_dir(self.tempdir, "**/*.txt")
        self.reloader.watch_dir(self.tempdir, "**/*.py")
        with self.tick_twice():
            self.increment_mtime(non_py_file)
            self.increment_mtime(py_file)
        self.assertEqual(notify_mock.call_count, 2)
        self.assertCountEqual(
            notify_mock.call_args_list, [mock.call(py_file), mock.call(non_py_file)]
        )

    @mock.patch("django.utils.autoreload.BaseReloader.notify_file_changed")
    @mock.patch(
        "django.utils.autoreload.iter_all_python_module_files", return_value=frozenset()
    )
    def test_nested_glob_recursive(self, mocked_modules, notify_mock):
        """
        Tests the reloader's functionality when watching directories recursively with nested glob patterns.

        Verifies that a change to a Python file within a watched directory triggers a notification, 
        even if the directory is watched recursively from multiple levels. The test ensures that 
        the reloader correctly handles recursive watching and notifies about changed files as expected.

        Checks the following:

        * Watching a directory and its subdirectories with a recursive glob pattern.
        * Notifications are triggered when a watched file's modification time is updated.
        * Correct handling of nested directories and files within the watched directories.

        """
        inner_py_file = self.ensure_file(self.tempdir / "dir" / "file.py")
        self.reloader.watch_dir(self.tempdir, "**/*.py")
        self.reloader.watch_dir(inner_py_file.parent, "**/*.py")
        with self.tick_twice():
            self.increment_mtime(inner_py_file)
        self.assertEqual(notify_mock.call_count, 1)
        self.assertCountEqual(notify_mock.call_args[0], [inner_py_file])

    @mock.patch("django.utils.autoreload.BaseReloader.notify_file_changed")
    @mock.patch(
        "django.utils.autoreload.iter_all_python_module_files", return_value=frozenset()
    )
    def test_overlapping_glob_recursive(self, mocked_modules, notify_mock):
        py_file = self.ensure_file(self.tempdir / "dir" / "file.py")
        self.reloader.watch_dir(self.tempdir, "**/*.p*")
        self.reloader.watch_dir(self.tempdir, "**/*.py*")
        with self.tick_twice():
            self.increment_mtime(py_file)
        self.assertEqual(notify_mock.call_count, 1)
        self.assertCountEqual(notify_mock.call_args[0], [py_file])


class BaseReloaderTests(ReloaderTests):
    RELOADER_CLS = autoreload.BaseReloader

    def test_watch_dir_with_unresolvable_path(self):
        path = Path("unresolvable_directory")
        with mock.patch.object(Path, "absolute", side_effect=FileNotFoundError):
            self.reloader.watch_dir(path, "**/*.mo")
        self.assertEqual(list(self.reloader.directory_globs), [])

    def test_watch_with_glob(self):
        self.reloader.watch_dir(self.tempdir, "*.py")
        watched_files = list(self.reloader.watched_files())
        self.assertIn(self.existing_file, watched_files)

    def test_watch_files_with_recursive_glob(self):
        inner_file = self.ensure_file(self.tempdir / "test" / "test.py")
        self.reloader.watch_dir(self.tempdir, "**/*.py")
        watched_files = list(self.reloader.watched_files())
        self.assertIn(self.existing_file, watched_files)
        self.assertIn(inner_file, watched_files)

    def test_run_loop_catches_stopiteration(self):
        def mocked_tick():
            yield

        with mock.patch.object(self.reloader, "tick", side_effect=mocked_tick) as tick:
            self.reloader.run_loop()
        self.assertEqual(tick.call_count, 1)

    def test_run_loop_stop_and_return(self):
        def mocked_tick(*args):
            yield
            self.reloader.stop()
            return  # Raises StopIteration

        with mock.patch.object(self.reloader, "tick", side_effect=mocked_tick) as tick:
            self.reloader.run_loop()

        self.assertEqual(tick.call_count, 1)

    def test_wait_for_apps_ready_checks_for_exception(self):
        app_reg = Apps()
        app_reg.ready_event.set()
        # thread.is_alive() is False if it's not started.
        dead_thread = threading.Thread()
        self.assertFalse(self.reloader.wait_for_apps_ready(app_reg, dead_thread))

    def test_wait_for_apps_ready_without_exception(self):
        app_reg = Apps()
        app_reg.ready_event.set()
        thread = mock.MagicMock()
        thread.is_alive.return_value = True
        self.assertTrue(self.reloader.wait_for_apps_ready(app_reg, thread))


def skip_unless_watchman_available():
    """

    Skips a test or function unless Watchman is available.

    This decorator checks if Watchman, a file system watching service, is running and
    available for use. If Watchman is not available, it skips the decorated function
    instead of executing it. This can be useful for tests or functions that rely on
    Watchman for their operation.

    Returns:
        The original function if Watchman is available, or a skip function if it is not.

    """
    try:
        autoreload.WatchmanReloader.check_availability()
    except WatchmanUnavailable as e:
        return skip("Watchman unavailable: %s" % e)
    return lambda func: func


@skip_unless_watchman_available()
class WatchmanReloaderTests(ReloaderTests, IntegrationTests):
    RELOADER_CLS = autoreload.WatchmanReloader

    def setUp(self):
        super().setUp()
        # Shorten the timeout to speed up tests.
        self.reloader.client_timeout = int(os.environ.get("DJANGO_WATCHMAN_TIMEOUT", 2))

    def test_watch_glob_ignores_non_existing_directories_two_levels(self):
        """

        Tests that the reloader's glob watching functionality ignores non-existing directories two levels deep.

        Verifies that the _subscribe method is not called when a glob pattern is provided for a non-existent directory.

        """
        with mock.patch.object(self.reloader, "_subscribe") as mocked_subscribe:
            self.reloader._watch_glob(self.tempdir / "does_not_exist" / "more", ["*"])
        self.assertFalse(mocked_subscribe.called)

    def test_watch_glob_uses_existing_parent_directories(self):
        """
        Tests that the _watch_glob method utilizes existing parent directories when watching for files.

        This test case verifies that the _watch_glob method of the reloader correctly handles
        the case where the parent directory of the glob pattern does not exist. It checks that
        the _subscribe method is called with the correct arguments, which include the existing
        parent directory and a glob pattern that matches the specified directory.

        The test ensures that the reloader's behavior is correct even when the parent directory
        does not exist, and that it uses the correct path and glob pattern to watch for files.\"\"\"
         Args are implicitly included in the text as they are passed to the function and are being tested, there is no need to list them given that was what was being tested.
        """
        with mock.patch.object(self.reloader, "_subscribe") as mocked_subscribe:
            self.reloader._watch_glob(self.tempdir / "does_not_exist", ["*"])
        self.assertSequenceEqual(
            mocked_subscribe.call_args[0],
            [
                self.tempdir,
                "glob-parent-does_not_exist:%s" % self.tempdir,
                ["anyof", ["match", "does_not_exist/*", "wholename"]],
            ],
        )

    def test_watch_glob_multiple_patterns(self):
        with mock.patch.object(self.reloader, "_subscribe") as mocked_subscribe:
            self.reloader._watch_glob(self.tempdir, ["*", "*.py"])
        self.assertSequenceEqual(
            mocked_subscribe.call_args[0],
            [
                self.tempdir,
                "glob:%s" % self.tempdir,
                ["anyof", ["match", "*", "wholename"], ["match", "*.py", "wholename"]],
            ],
        )

    def test_watched_roots_contains_files(self):
        """
        Checks if the watched roots returned by the reloader contain the directory of an existing file.

        Parameters
        ----------
        None

        Returns
        -------
        None

        Notes
        -----
        This test ensures that the reloader's watched roots include the parent directory of a given file, 
        verifying that the reloader is monitoring the correct locations for file changes.
        """
        paths = self.reloader.watched_roots([self.existing_file])
        self.assertIn(self.existing_file.parent, paths)

    def test_watched_roots_contains_directory_globs(self):
        """
        Tests that a watched directory with a glob pattern is included in the watched roots.

        Verifies that when a directory is added to the watcher with a file pattern,
        the directory itself is correctly identified as one of the watched roots.

        This ensures that changes to the directory or its contents are properly detected
        and handled by the reloader.
        """
        self.reloader.watch_dir(self.tempdir, "*.py")
        paths = self.reloader.watched_roots([])
        self.assertIn(self.tempdir, paths)

    def test_watched_roots_contains_sys_path(self):
        with extend_sys_path(str(self.tempdir)):
            paths = self.reloader.watched_roots([])
        self.assertIn(self.tempdir, paths)

    def test_check_server_status(self):
        self.assertTrue(self.reloader.check_server_status())

    def test_check_server_status_raises_error(self):
        with mock.patch.object(self.reloader.client, "query") as mocked_query:
            mocked_query.side_effect = Exception()
            with self.assertRaises(autoreload.WatchmanUnavailable):
                self.reloader.check_server_status()

    @mock.patch("pywatchman.client")
    def test_check_availability(self, mocked_client):
        """

        Tests the check_availability method of the RELOADER_CLS class.

        This test case checks that the check_availability method correctly raises a WatchmanUnavailable exception when the watchman client's capabilityCheck method fails, indicating that the watchman service is not available.

        The test verifies that the exception is raised with a meaningful error message, 'Cannot connect to the watchman service', which provides useful feedback in case of a connection failure.

        The purpose of this test is to ensure that the RELOADER_CLS class handles watchman service availability issues correctly and provides a clear error message when the service is not available.

        """
        mocked_client().capabilityCheck.side_effect = Exception()
        with self.assertRaisesMessage(
            WatchmanUnavailable, "Cannot connect to the watchman service"
        ):
            self.RELOADER_CLS.check_availability()

    @mock.patch("pywatchman.client")
    def test_check_availability_lower_version(self, mocked_client):
        """
        Tests that check_availability raises WatchmanUnavailable when the Watchman client version is lower than 4.9.

        This test verifies the check_availability method's behavior when the available Watchman client version does not meet the minimum required version. It confirms that the function correctly identifies the version and raises an exception with a user-friendly error message.

        Args:
            None

        Raises:
            WatchmanUnavailable: If the Watchman client version is lower than 4.9.

        Notes:
            This test uses mocking to simulate a Watchman client with a specific version, allowing for isolation of the check_avability method's behavior.
        """
        mocked_client().capabilityCheck.return_value = {"version": "4.8.10"}
        with self.assertRaisesMessage(
            WatchmanUnavailable, "Watchman 4.9 or later is required."
        ):
            self.RELOADER_CLS.check_availability()

    def test_pywatchman_not_available(self):
        """

        Tests the behavior of the autoreloader when pywatchman is not available.

        This test case simulates the absence of pywatchman by mocking its presence and
        then checking if the correct exception is raised when attempting to check its
        availability. The test verifies that the WatchmanUnavailable exception is
        raised with the expected error message, indicating that pywatchman is not
        installed.

        """
        with mock.patch.object(autoreload, "pywatchman") as mocked:
            mocked.__bool__.return_value = False
            with self.assertRaisesMessage(
                WatchmanUnavailable, "pywatchman not installed."
            ):
                self.RELOADER_CLS.check_availability()

    def test_update_watches_raises_exceptions(self):
        """
        Tests that the update_watches method raises an exception when _update_watches fails.

        This test case verifies that the update_watches method properly handles exceptions
        raised by the _update_watches method. It checks that the exception is propagated
        up the call stack and that the check_server_status method is called with the
        raised exception.

        The test validates the interaction between update_watches, _update_watches, and
        check_server_status, ensuring that exceptions are correctly handled and passed
        to the server status check. This test helps ensure the reliability and robustness
        of the reloader's watch update functionality. 
        """
        class TestException(Exception):
            pass

        with mock.patch.object(self.reloader, "_update_watches") as mocked_watches:
            with mock.patch.object(
                self.reloader, "check_server_status"
            ) as mocked_server_status:
                mocked_watches.side_effect = TestException()
                mocked_server_status.return_value = True
                with self.assertRaises(TestException):
                    self.reloader.update_watches()
                self.assertIsInstance(
                    mocked_server_status.call_args[0][0], TestException
                )

    @mock.patch.dict(os.environ, {"DJANGO_WATCHMAN_TIMEOUT": "10"})
    def test_setting_timeout_from_environment_variable(self):
        self.assertEqual(self.RELOADER_CLS().client_timeout, 10)


@skipIf(on_macos_with_hfs(), "These tests do not work with HFS+ as a filesystem")
class StatReloaderTests(ReloaderTests, IntegrationTests):
    RELOADER_CLS = autoreload.StatReloader

    def setUp(self):
        super().setUp()
        # Shorten the sleep time to speed up tests.
        self.reloader.SLEEP_TIME = 0.01

    @mock.patch("django.utils.autoreload.StatReloader.notify_file_changed")
    def test_tick_does_not_trigger_twice(self, mock_notify_file_changed):
        """

        Tests that the reloader's tick functionality does not trigger file change notifications more than once.

        This test case verifies that when a file's modification time is updated after the reloader has already 
        started watching it, the reloader will only send a single notification about the file change. 

        It ensures that the reloader correctly handles file system events and avoids duplicate notifications.

        """
        with mock.patch.object(
            self.reloader, "watched_files", return_value=[self.existing_file]
        ):
            ticker = self.reloader.tick()
            next(ticker)
            self.increment_mtime(self.existing_file)
            next(ticker)
            next(ticker)
            self.assertEqual(mock_notify_file_changed.call_count, 1)

    def test_snapshot_files_ignores_missing_files(self):
        with mock.patch.object(
            self.reloader, "watched_files", return_value=[self.nonexistent_file]
        ):
            self.assertEqual(dict(self.reloader.snapshot_files()), {})

    def test_snapshot_files_updates(self):
        """
        Tests that the snapshot_files method correctly updates when a watched file's modification time changes.

        The test checks that the snapshot includes the file when it first appears, and that the snapshot is updated when the file's modification time is incremented.
        """
        with mock.patch.object(
            self.reloader, "watched_files", return_value=[self.existing_file]
        ):
            snapshot1 = dict(self.reloader.snapshot_files())
            self.assertIn(self.existing_file, snapshot1)
            self.increment_mtime(self.existing_file)
            snapshot2 = dict(self.reloader.snapshot_files())
            self.assertNotEqual(
                snapshot1[self.existing_file], snapshot2[self.existing_file]
            )

    def test_snapshot_files_with_duplicates(self):
        """
        Tests that snapshot_files correctly handles duplicate files.

        Verifies that when the reloader's watched_files contains duplicate entries,
        the snapshot_files function returns a list containing each unique file only once.

        The test case checks that the resulting snapshot list has the correct length 
        and that the existing file is properly included in the snapshot.
        """
        with mock.patch.object(
            self.reloader,
            "watched_files",
            return_value=[self.existing_file, self.existing_file],
        ):
            snapshot = list(self.reloader.snapshot_files())
            self.assertEqual(len(snapshot), 1)
            self.assertEqual(snapshot[0][0], self.existing_file)
