import os
import subprocess
import sys

from . import PostgreSQLSimpleTestCase


class PostgresIntegrationTests(PostgreSQLSimpleTestCase):
    def test_check(self):
        """

        Checks the Django project for any errors or warnings.

        This function sets up a test environment, removes any existing Django settings module,
        and then runs the Django check command using the integration settings module.
        It verifies that the command completes successfully with no errors or warnings.

        If the command fails, it asserts an error with the standard error output from the command.

        """
        test_environ = os.environ.copy()
        if "DJANGO_SETTINGS_MODULE" in test_environ:
            del test_environ["DJANGO_SETTINGS_MODULE"]
        test_environ["PYTHONPATH"] = os.path.join(os.path.dirname(__file__), "../../")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "django",
                "check",
                "--settings",
                "integration_settings",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(__file__),
            env=test_environ,
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
