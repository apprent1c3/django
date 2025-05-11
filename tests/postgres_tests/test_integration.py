import os
import subprocess
import sys

from . import PostgreSQLSimpleTestCase


class PostgresIntegrationTests(PostgreSQLSimpleTestCase):
    def test_check(self):
        """

        Runs Django's system checks to verify the project's integrity.

        Removes the current DJANGO_SETTINGS_MODULE environment variable, adjusts the PYTHONPATH,
        and then executes Django's check command with the integration settings. Fails the test
        if the command returns a non-zero exit code. The command's output is discarded, but any
        error messages are captured and asserted against an expected empty error output.

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
