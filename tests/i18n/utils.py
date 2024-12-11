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
        Asserts that a specific keyword with an expected value exists in a PO file haystack.

        This function searches for the presence of a keyword-value pair within the provided haystack.
        It optionally encloses the expected value in single quotes if use_quotes is False, otherwise it defaults to double quotes.
        The search is performed across multiple lines in the haystack.

        :arg keyword: The keyword to be searched in the haystack
        :arg expected_value: The expected value associated with the keyword
        :arg haystack: The PO file content to be searched
        :arg use_quotes: Optional flag to determine whether double or single quotes should be used. Defaults to True.
        :returns: True if the keyword with the expected value is found, False otherwise
        :raises AssertionError: If the keyword with the expected value is not found in the haystack
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

        Setup a temporary working directory for testing purposes.

        This function creates a temporary directory with a unique prefix, copies the contents of a specified work directory into it, and changes the current working directory to the newly created test directory.

        The temporary directory is set to be removed after the test is completed, along with a return to the original working directory. This ensures a clean and isolated test environment.

        :raises: No exceptions are explicitly raised, but any errors during directory creation or copying may propagate up.

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
        """

        Removes a directory and its contents if it is a subdirectory of the test directory.

        This function checks if the provided directory :param:`dname` is within the test directory.
        If it is, the function deletes the directory and all its contents.
        If the directory is not within the test directory, the function takes no action.

        """
        if (
            os.path.commonprefix([self.test_dir, os.path.abspath(dname)])
            != self.test_dir
        ):
            return
        shutil.rmtree(dname)
