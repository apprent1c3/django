from pathlib import Path
from unittest import mock

from django.template import autoreload
from django.test import SimpleTestCase, override_settings
from django.test.utils import require_jinja2

ROOT = Path(__file__).parent.absolute()
EXTRA_TEMPLATES_DIR = ROOT / "templates_extra"


@override_settings(
    INSTALLED_APPS=["template_tests"],
    TEMPLATES=[
        {
            "BACKEND": "django.template.backends.dummy.TemplateStrings",
            "APP_DIRS": True,
        },
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "DIRS": [EXTRA_TEMPLATES_DIR],
            "OPTIONS": {
                "context_processors": [
                    "django.template.context_processors.request",
                ],
                "loaders": [
                    "django.template.loaders.filesystem.Loader",
                    "django.template.loaders.app_directories.Loader",
                ],
            },
        },
    ],
)
class TemplateReloadTests(SimpleTestCase):
    @mock.patch("django.template.autoreload.reset_loaders")
    def test_template_changed(self, mock_reset):
        template_path = Path(__file__).parent / "templates" / "index.html"
        self.assertTrue(autoreload.template_changed(None, template_path))
        mock_reset.assert_called_once()

    @mock.patch("django.template.autoreload.reset_loaders")
    def test_non_template_changed(self, mock_reset):
        """

        Test that the template_changed function behaves correctly when given a non-template file path.

        This test verifies that the function returns None and does not trigger a reset of the loaders 
        when a file path that is not a template is provided. 

        :param self: The test instance.
        :param mock_reset: A mock object for the reset_loaders function.
        :returns: None

        """
        self.assertIsNone(autoreload.template_changed(None, Path(__file__)))
        mock_reset.assert_not_called()

    @override_settings(
        TEMPLATES=[
            {
                "DIRS": [ROOT],
                "BACKEND": "django.template.backends.django.DjangoTemplates",
            }
        ]
    )
    @mock.patch("django.template.autoreload.reset_loaders")
    def test_non_template_changed_in_template_directory(self, mock_reset):
        """
        Test that a non-template file change in a template directory does not trigger autoreload.

        This test checks the behavior of the autoreload mechanism when a file change occurs
        in a directory that contains templates, but the changed file is not a template itself.
        The test verifies that the autoreload function correctly identifies the file as not
        being a template and does not trigger a reset of the template loaders.

        Args:
            None

        Returns:
            None

        Asserts:
            The autoreload function returns None and does not call the template loader reset function.

        """
        self.assertIsNone(autoreload.template_changed(None, Path(__file__)))
        mock_reset.assert_not_called()

    @mock.patch("django.forms.renderers.get_default_renderer")
    def test_form_template_reset_template_change(self, mock_renderer):
        template_path = Path(__file__).parent / "templates" / "index.html"
        self.assertIs(autoreload.template_changed(None, template_path), True)
        mock_renderer.assert_called_once()

    @mock.patch("django.template.loaders.cached.Loader.reset")
    def test_form_template_reset_template_change_reset_call(self, mock_loader_reset):
        """

        Tests that the autoreload.template_changed function resets the template when a change is detected.

        This function checks if the autoreload.template_changed function correctly identifies when a template 
        has been modified and subsequently calls the reset method on the Django template loader.

        Args:
            None

        Returns:
            bool: True if the template has changed, False otherwise.

        Notes:
            This function is used to verify the functionality of the autoreload.template_changed function 
            in the context of automatic template reloading in Django.

        """
        template_path = Path(__file__).parent / "templates" / "index.html"
        self.assertIs(autoreload.template_changed(None, template_path), True)
        mock_loader_reset.assert_called_once()

    @override_settings(FORM_RENDERER="django.forms.renderers.TemplatesSetting")
    @mock.patch("django.template.loaders.cached.Loader.reset")
    def test_form_template_reset_template_change_no_djangotemplates(
        self, mock_loader_reset
    ):
        """
        Tests the autoreload template changed function when a template change occurs but does not involve a django template.

        Verifies that the function correctly identifies a template change and returns True, and also checks that the 
        template loader reset is not triggered in this scenario, ensuring that only relevant template changes cause 
        a reset of the loader.
        """
        template_path = Path(__file__).parent / "templates" / "index.html"
        self.assertIs(autoreload.template_changed(None, template_path), True)
        mock_loader_reset.assert_not_called()

    @mock.patch("django.forms.renderers.get_default_renderer")
    def test_form_template_reset_non_template_change(self, mock_renderer):
        self.assertIsNone(autoreload.template_changed(None, Path(__file__)))
        mock_renderer.assert_not_called()

    def test_watch_for_template_changes(self):
        """
        Tests that the watch_for_template_changes function correctly watches for changes in the template directories.

        This test case verifies that the function establishes watches for changes in both the primary and extra template directories. 

        :raises AssertionError: If the watch directories do not match the expected template directories.
        :return: None
        """
        mock_reloader = mock.MagicMock()
        autoreload.watch_for_template_changes(mock_reloader)
        self.assertSequenceEqual(
            sorted(mock_reloader.watch_dir.call_args_list),
            [
                mock.call(ROOT / "templates", "**/*"),
                mock.call(ROOT / "templates_extra", "**/*"),
            ],
        )

    def test_get_template_directories(self):
        self.assertSetEqual(
            autoreload.get_template_directories(),
            {
                ROOT / "templates_extra",
                ROOT / "templates",
            },
        )

    @mock.patch("django.template.loaders.base.Loader.reset")
    def test_reset_all_loaders(self, mock_reset):
        autoreload.reset_loaders()
        self.assertEqual(mock_reset.call_count, 2)

    @override_settings(
        TEMPLATES=[
            {
                "DIRS": [""],
                "BACKEND": "django.template.backends.django.DjangoTemplates",
            }
        ]
    )
    def test_template_dirs_ignore_empty_path(self):
        self.assertEqual(autoreload.get_template_directories(), set())

    @override_settings(
        TEMPLATES=[
            {
                "DIRS": [
                    str(ROOT) + "/absolute_str",
                    "template_tests/relative_str",
                    Path("template_tests/relative_path"),
                ],
                "BACKEND": "django.template.backends.django.DjangoTemplates",
            }
        ]
    )
    def test_template_dirs_normalized_to_paths(self):
        self.assertSetEqual(
            autoreload.get_template_directories(),
            {
                ROOT / "absolute_str",
                Path.cwd() / "template_tests/relative_str",
                Path.cwd() / "template_tests/relative_path",
            },
        )


@require_jinja2
@override_settings(INSTALLED_APPS=["template_tests"])
class Jinja2TemplateReloadTests(SimpleTestCase):
    def test_watch_for_template_changes(self):
        """

        Tests the watch_for_template_changes function to ensure it correctly sets up a watch for changes to template files.

        The function is expected to watch for any changes to files within the 'templates' directory and its subdirectories.

        """
        mock_reloader = mock.MagicMock()
        autoreload.watch_for_template_changes(mock_reloader)
        self.assertSequenceEqual(
            sorted(mock_reloader.watch_dir.call_args_list),
            [
                mock.call(ROOT / "templates", "**/*"),
            ],
        )

    def test_get_template_directories(self):
        self.assertSetEqual(
            autoreload.get_template_directories(),
            {
                ROOT / "templates",
            },
        )

    @mock.patch("django.template.loaders.base.Loader.reset")
    def test_reset_all_loaders(self, mock_reset):
        autoreload.reset_loaders()
        self.assertEqual(mock_reset.call_count, 0)
