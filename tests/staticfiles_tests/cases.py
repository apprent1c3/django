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
        """
        Asserts that attempting to retrieve a file at the specified filepath results in an OSError, indicating that the file does not exist.

        :param filepath: The path to the file to check for existence
        :raises AssertionError: If the file is found or no OSError is raised
        """
        with self.assertRaises(OSError):
            self._get_file(filepath)

    def render_template(self, template, **kwargs):
        """
        _RENDER_TEMPLATE_
        Renders a template string with given keyword arguments.

        :param template: A template string or a Template object to be rendered.
        :keyword kwargs: Keyword arguments to be replaced in the template.
        :return: A rendered template string with replaced keyword arguments, stripped of leading and trailing whitespace.
        """
        if isinstance(template, str):
            template = Template(template)
        return template.render(Context(**kwargs)).strip()

    def static_template_snippet(self, path, asvar=False):
        """
        Generates a template snippet for loading static files.

        :param path: The path to the static file.
        :param asvar: If True, returns a snippet that assigns the static file to a variable, otherwise returns a snippet that directly includes the static file.
        :returns: A Django template snippet as a string.
        :description: The generated snippet can be used in a Django template to load static files, either by directly including them or by assigning them to a variable for further use.
        """
        if asvar:
            return (
                "{%% load static from static %%}{%% static '%s' as var %%}{{ var }}"
                % path
            )
        return "{%% load static from static %%}{%% static '%s' %%}" % path

    def assertStaticRenders(self, path, result, asvar=False, **kwargs):
        """

        Asserts that a static rendered template matches the expected result.

        :arg path: The path to the template to render.
        :arg result: The expected rendered result of the template.
        :arg asvar: Optional boolean indicating whether to render the template as a variable.
        :arg kwargs: Additional keyword arguments to pass to the render_template method.

        This function verifies that the rendered template at the specified path matches the provided result, 
        optionally rendered as a variable, allowing for flexible testing of static template rendering scenarios.

        """
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

        Sets up a temporary environment for testing by creating a temporary directory,
        configuring static file settings, and optionally running the collectstatic command.

        Creates a temporary directory to serve as the static root and enables a patched
        version of the settings. If `run_collectstatic_in_setUp` is True, the collectstatic
        command is executed to populate the static directory. Cleanup hooks are added to
        remove the temporary directory and disable the patched settings after the test is
        complete.

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
