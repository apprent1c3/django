import os
import re
import shutil
import tempfile

source_code_dir = os.path.dirname(__file__)


def copytree(src, dst):
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))


class POFileAssertionMixin:
    def _assertPoKeyword(self, keyword, expected_value, haystack, use_quotes=True):
        """

        Asserts that a specific PO keyword is present in a given haystack string.

        The assertion checks if the keyword followed by the expected value is found at the
        beginning of a line in the haystack. The expected value can be optionally wrapped
        in quotes.

        Parameters
        ----------
        keyword : str
            The PO keyword to search for.
        expected_value : str
            The expected value following the keyword.
        haystack : str
            The string to search in.
        use_quotes : bool, optional
            Whether to wrap the expected value in quotes (default is True).

        Returns
        -------
        bool
            True if the keyword with the expected value is found, False otherwise.

        """
        q = '"'
        if use_quotes:
            expected_value = '"%s"' % expected_value
            q = "'"
        needle = "%s %s" % (keyword, expected_value)
        expected_value = re.escape(expected_value)
        return self.assertTrue(
            re.search("^%s %s" % (keyword, expected_value), haystack, re.MULTILINE),
            "Could not find %(q)s%(n)s%(q)s in generated PO file"
            % {"n": needle, "q": q},
        )

    def assertMsgId(self, msgid, haystack, use_quotes=True):
        return self._assertPoKeyword("msgid", msgid, haystack, use_quotes=use_quotes)


class RunInTmpDirMixin:
    """
    Allow i18n tests that need to generate .po/.mo files to run in an isolated
    temporary filesystem tree created by tempfile.mkdtemp() that contains a
    clean copy of the relevant test code.

    Test classes using this mixin need to define a `work_subdir` attribute
    which designates the subdir under `tests/i18n/` that will be copied to the
    temporary tree from which its test cases will run.

    The setUp() method sets the current working dir to the temporary tree.
    It'll be removed when cleaning up.
    """

    def setUp(self):
        """
        Set up the test environment by creating a temporary working directory.

        This method creates a temporary directory, copies the necessary test files into it, and changes the current working directory to the test directory.
        The original current working directory is saved to be restored after the test is completed.
        Any files and directories created during the test will be automatically removed after the test finishes.

        The test directory is set up to mimic the structure of the source code directory, allowing for realistic testing of functionality without affecting the original codebase.
        The method also ensures that the test environment is properly cleaned up after use, regardless of the test outcome.
        """
        self._cwd = os.getcwd()
        self.work_dir = tempfile.mkdtemp(prefix="i18n_")
        # Resolve symlinks, if any, in test directory paths.
        self.test_dir = os.path.realpath(os.path.join(self.work_dir, self.work_subdir))
        copytree(os.path.join(source_code_dir, self.work_subdir), self.test_dir)
        # Step out of the temporary working tree before removing it to avoid
        # deletion problems on Windows. Cleanup actions registered with
        # addCleanup() are called in reverse so preserve this ordering.
        self.addCleanup(self._rmrf, self.test_dir)
        self.addCleanup(os.chdir, self._cwd)
        os.chdir(self.test_dir)

    def _rmrf(self, dname):
        if (
            os.path.commonprefix([self.test_dir, os.path.abspath(dname)])
            != self.test_dir
        ):
            return
        shutil.rmtree(dname)
