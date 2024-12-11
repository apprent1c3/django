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
        """
        Tests the template_changed function to verify its behavior when a template file is modified.

        This test checks if the function correctly detects changes to a template and triggers an autoreload response by calling the reset_loaders function.

        Args:
            None

        Returns:
            None

        Notes:
            Verifies that the template_changed function returns True when a template is changed and that the reset_loaders function is called once to initiate the autoreload process.
        """
        template_path = Path(__file__).parent / "templates" / "index.html"
        self.assertTrue(autoreload.template_changed(None, template_path))
        mock_reset.assert_called_once()

    @mock.patch("django.template.autoreload.reset_loaders")
    def test_non_template_changed(self, mock_reset):
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
        Tests that a file changed within a template directory does not trigger a template autoreload if it is not a template file.

        Verifies the behavior of the template_changed function when given a non-template file path within a template directory.
        The function is expected to return None and not trigger a reload of the template loaders, indicating that the changed file does not affect the template rendering process.
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
        Tests that the template_changed function correctly detects template changes and triggers a reset.

        This test case verifies that when a template is changed, the template_changed function returns True and 
        the reset method of the template loader is called once to reload the updated template.

        :param mock_loader_reset: Mocked reset method of the template loader
        :returns: None
        """
        template_path = Path(__file__).parent / "templates" / "index.html"
        self.assertIs(autoreload.template_changed(None, template_path), True)
        mock_loader_reset.assert_called_once()

    @override_settings(FORM_RENDERER="django.forms.renderers.TemplatesSetting")
    @mock.patch("django.template.loaders.cached.Loader.reset")
    def test_form_template_reset_template_change_no_djangotemplates(
        self, mock_loader_reset
    ):
        template_path = Path(__file__).parent / "templates" / "index.html"
        self.assertIs(autoreload.template_changed(None, template_path), True)
        mock_loader_reset.assert_not_called()

    @mock.patch("django.forms.renderers.get_default_renderer")
    def test_form_template_reset_non_template_change(self, mock_renderer):
        self.assertIsNone(autoreload.template_changed(None, Path(__file__)))
        mock_renderer.assert_not_called()

    def test_watch_for_template_changes(self):
        """
        Tests the functionality of watching for template changes by verifying that the correct directories are being monitored. Specifically, it checks that the 'templates' and 'templates_extra' directories are being watched for any changes to files or subdirectories within them, ensuring that updates to templates trigger the autoreload mechanism.
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
        """
        Tests that autoreload.reset_loaders resets all template loaders by verifying the reset method is called on each loader.
        """
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
        Tests the functionality of watching for template changes.

        Verifies that the watch_for_template_changes function correctly sets up a watcher to monitor the templates directory for any changes, including all subdirectories and files. 

        The test checks if the expected directories are being watched as intended, ensuring that any modifications to the templates will trigger the specified reload functionality.

        This test case is integral to ensuring proper autoreload functionality in the context of template changes.
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
        """

        Tests that the reset_loaders function in autoreload does not reset all Django template loaders.

        This test checks the behavior of the reset_loaders function when it is expected not to 
        invoke the reset method on all template loaders, verifying its correct functionality 
        in specific scenarios.

        """
        autoreload.reset_loaders()
        self.assertEqual(mock_reset.call_count, 0)
