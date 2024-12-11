import os
import shutil
import tempfile

from django.conf import settings
from django.core.management import call_command
from django.template import Context, Template
from django.test import SimpleTestCase, override_settings

from .settings import TEST_SETTINGS


class BaseStaticFilesMixin:
    """
    Test case with a couple utility assertions.
    """

    def assertFileContains(self, filepath, text):
        self.assertIn(
            text,
            self._get_file(filepath),
            "'%s' not in '%s'" % (text, filepath),
        )

    def assertFileNotFound(self, filepath):
        with self.assertRaises(OSError):
            self._get_file(filepath)

    def render_template(self, template, **kwargs):
        if isinstance(template, str):
            template = Template(template)
        return template.render(Context(**kwargs)).strip()

    def static_template_snippet(self, path, asvar=False):
        """

        Generates a template snippet for loading a static file.

        The snippet can be used directly in a Django template to include a static file.
        It handles loading the static file system and rendering the static URL.

        If :attr:`asvar` is True, the snippet assigns the static URL to a template variable
        instead of directly rendering it. This allows for further manipulation of the URL within the template.

        :param path: The path to the static file.
        :param asvar: Whether to assign the static URL to a template variable (default: False).
        :returns: A template snippet as a string.

        """
        if asvar:
            return (
                "{%% load static from static %%}{%% static '%s' as var %%}{{ var }}"
                % path
            )
        return "{%% load static from static %%}{%% static '%s' %%}" % path

    def assertStaticRenders(self, path, result, asvar=False, **kwargs):
        template = self.static_template_snippet(path, asvar)
        self.assertEqual(self.render_template(template, **kwargs), result)

    def assertStaticRaises(self, exc, path, result, asvar=False, **kwargs):
        with self.assertRaises(exc):
            self.assertStaticRenders(path, result, **kwargs)


@override_settings(**TEST_SETTINGS)
class StaticFilesTestCase(BaseStaticFilesMixin, SimpleTestCase):
    pass


@override_settings(**TEST_SETTINGS)
class CollectionTestCase(BaseStaticFilesMixin, SimpleTestCase):
    """
    Tests shared by all file finding features (collectstatic,
    findstatic, and static serve view).

    This relies on the asserts defined in BaseStaticFilesTestCase, but
    is separated because some test cases need those asserts without
    all these tests.
    """

    run_collectstatic_in_setUp = True

    def setUp(self):
        """
        Sets up the environment for testing by creating a temporary directory for static files,
        overriding the STATIC_ROOT setting, and optionally running collectstatic.
        The temporary directory and patched settings are cleaned up automatically after the test finishes.

        Note:
            The temporary directory is removed and the original settings are restored after the test, regardless of the test outcome.

        """
        super().setUp()
        temp_dir = self.mkdtemp()
        # Override the STATIC_ROOT for all tests from setUp to tearDown
        # rather than as a context manager
        patched_settings = self.settings(STATIC_ROOT=temp_dir)
        patched_settings.enable()
        if self.run_collectstatic_in_setUp:
            self.run_collectstatic()
        # Same comment as in runtests.teardown.
        self.addCleanup(shutil.rmtree, temp_dir)
        self.addCleanup(patched_settings.disable)

    def mkdtemp(self):
        return tempfile.mkdtemp()

    def run_collectstatic(self, *, verbosity=0, **kwargs):
        call_command(
            "collectstatic",
            interactive=False,
            verbosity=verbosity,
            ignore_patterns=["*.ignoreme"],
            **kwargs,
        )

    def _get_file(self, filepath):
        """
        Retrieves the contents of a file from the static root directory.

        This method takes a filepath as input, joins it with the static root directory,
        and returns the contents of the file as a string. The file is assumed to be
        encoded in UTF-8.

        :param filepath: The path to the file relative to the static root directory
        :returns: The contents of the file as a string
        :raises AssertionError: If the filepath is empty
        """
        assert filepath, "filepath is empty."
        filepath = os.path.join(settings.STATIC_ROOT, filepath)
        with open(filepath, encoding="utf-8") as f:
            return f.read()


class TestDefaults:
    """
    A few standard test cases.
    """

    def test_staticfiles_dirs(self):
        """
        Can find a file in a STATICFILES_DIRS directory.
        """
        self.assertFileContains("test.txt", "Can we find")
        self.assertFileContains(os.path.join("prefix", "test.txt"), "Prefix")

    def test_staticfiles_dirs_subdir(self):
        """
        Can find a file in a subdirectory of a STATICFILES_DIRS
        directory.
        """
        self.assertFileContains("subdir/test.txt", "Can we find")

    def test_staticfiles_dirs_priority(self):
        """
        File in STATICFILES_DIRS has priority over file in app.
        """
        self.assertFileContains("test/file.txt", "STATICFILES_DIRS")

    def test_app_files(self):
        """
        Can find a file in an app static/ directory.
        """
        self.assertFileContains("test/file1.txt", "file1 in the app dir")

    def test_nonascii_filenames(self):
        """
        Can find a file with non-ASCII character in an app static/ directory.
        """
        self.assertFileContains("test/⊗.txt", "⊗ in the app dir")

    def test_camelcase_filenames(self):
        """
        Can find a file with capital letters.
        """
        self.assertFileContains("test/camelCase.txt", "camelCase")

    def test_filename_with_percent_sign(self):
        self.assertFileContains("test/%2F.txt", "%2F content")
