import os
import subprocess
import sys

from . import PostgreSQLSimpleTestCase


class PostgresIntegrationTests(PostgreSQLSimpleTestCase):
    def test_check(self):
        """
        Checks the Django project for any errors or warnings by running the Django check command.

        This function simulates a clean environment by removing any existing Django settings
        module environment variables and updating the Python path to point to the project directory.
        It then executes the Django check command using the integration settings and verifies
        that the command runs successfully without any errors. If the command fails, it asserts
        that the return code is 0 and displays any error messages captured from the command's
        standard error output.
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
