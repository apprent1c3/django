import pathlib
import sys

from django.test import SimpleTestCase


def last_n_parts(path, n):
    return "/".join(path.parts[-n:])


# The import must happen at the end of setUpClass, so it can't be imported at
# the top of the file.
github_links = None


class GitHubLinkTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        # The file implementing the code under test is in the docs folder and
        # is not part of the Django package. This means it cannot be imported
        # through standard means. Include its parent in the pythonpath for the
        # duration of the tests to allow the code to be imported.
        cls.ext_path = str((pathlib.Path(__file__).parents[2] / "docs/_ext").resolve())
        sys.path.insert(0, cls.ext_path)
        cls.addClassCleanup(sys.path.remove, cls.ext_path)
        cls.addClassCleanup(sys.modules.pop, "github_links", None)
        # Linters/IDEs may not be able to detect this as a valid import.
        import github_links as _github_links

        global github_links
        github_links = _github_links

    def test_code_locator(self):
        locator = github_links.CodeLocator.from_code(
            """
from a import b, c
from .d import e, f as g

def h():
    pass

class I:
    def j(self):
        pass"""
        )

        self.assertEqual(locator.node_line_numbers, {"h": 5, "I": 8, "I.j": 9})
        self.assertEqual(locator.import_locations, {"b": "a", "c": "a", "e": ".d"})

    def test_module_name_to_file_path_package(self):
        path = github_links.module_name_to_file_path("django")

        self.assertEqual(last_n_parts(path, 2), "django/__init__.py")

    def test_module_name_to_file_path_module(self):
        path = github_links.module_name_to_file_path("django.shortcuts")

        self.assertEqual(last_n_parts(path, 2), "django/shortcuts.py")

    def test_get_path_and_line_class(self):
        path, line = github_links.get_path_and_line(
            module="tests.sphinx.testdata.package.module", fullname="MyClass"
        )

        self.assertEqual(
            last_n_parts(path, 5), "tests/sphinx/testdata/package/module.py"
        )
        self.assertEqual(line, 12)

    def test_get_path_and_line_func(self):
        """

        Return the file path and line number for a given module and function name.

        The function takes a module name and a full function name as input, and returns a tuple containing the file path where the function is defined and the line number where the function is located.

        Parameters
        ----------
        module : str
            The name of the module where the function is defined.
        fullname : str
            The full name of the function.

        Returns
        -------
        tuple
            A tuple containing the file path and line number of the function.

        """
        path, line = github_links.get_path_and_line(
            module="tests.sphinx.testdata.package.module", fullname="my_function"
        )

        self.assertEqual(
            last_n_parts(path, 5), "tests/sphinx/testdata/package/module.py"
        )
        self.assertEqual(line, 24)

    def test_get_path_and_line_method(self):
        path, line = github_links.get_path_and_line(
            module="tests.sphinx.testdata.package.module", fullname="MyClass.my_method"
        )

        self.assertEqual(
            last_n_parts(path, 5), "tests/sphinx/testdata/package/module.py"
        )
        self.assertEqual(line, 16)

    def test_get_path_and_line_cached_property(self):
        path, line = github_links.get_path_and_line(
            module="tests.sphinx.testdata.package.module",
            fullname="MyClass.my_cached_property",
        )

        self.assertEqual(
            last_n_parts(path, 5), "tests/sphinx/testdata/package/module.py"
        )
        self.assertEqual(line, 20)

    def test_get_path_and_line_forwarded_import(self):
        path, line = github_links.get_path_and_line(
            module="tests.sphinx.testdata.package.module", fullname="MyOtherClass"
        )

        self.assertEqual(
            last_n_parts(path, 5), "tests/sphinx/testdata/package/other_module.py"
        )
        self.assertEqual(line, 1)

    def test_get_path_and_line_wildcard_import(self):
        path, line = github_links.get_path_and_line(
            module="tests.sphinx.testdata.package.module", fullname="WildcardClass"
        )

        self.assertEqual(
            last_n_parts(path, 5),
            "tests/sphinx/testdata/package/wildcard_module.py",
        )
        self.assertEqual(line, 4)

        path, line = github_links.get_path_and_line(
            module="tests.sphinx.testdata.package.module",
            fullname="WildcardMixin",
        )
        self.assertEqual(
            last_n_parts(path, 5),
            "tests/sphinx/testdata/package/wildcard_base.py",
        )
        self.assertEqual(line, 1)

    def test_get_path_and_line_forwarded_import_module(self):
        path, line = github_links.get_path_and_line(
            module="tests.sphinx.testdata.package.module",
            fullname="other_module.MyOtherClass",
        )

        self.assertEqual(
            last_n_parts(path, 5), "tests/sphinx/testdata/package/other_module.py"
        )
        self.assertEqual(line, 1)

    def test_get_branch_stable(self):
        branch = github_links.get_branch(version="2.2", next_version="3.2")
        self.assertEqual(branch, "stable/2.2.x")

    def test_get_branch_latest(self):
        branch = github_links.get_branch(version="3.2", next_version="3.2")
        self.assertEqual(branch, "main")

    def test_github_linkcode_resolve_unspecified_domain(self):
        """

        Resolves the GitHub link code for an unspecified domain.

        This function tests whether the github_linkcode_resolve function returns None when 
        given an unspecified domain, indicating that no specific GitHub link code 
        resolution is possible for this domain.

        :param domain: the domain to be resolved (set to 'unspecified' in this test)
        :param info: additional information used for resolution (empty in this test)
        :param version: the current version (set to '3.2' in this test)
        :param next_version: the next version (set to '3.2' in this test)

        :return: None if the domain is unspecified, indicating no resolution is possible.

        """
        domain = "unspecified"
        info = {}
        self.assertIsNone(
            github_links.github_linkcode_resolve(
                domain, info, version="3.2", next_version="3.2"
            )
        )

    def test_github_linkcode_resolve_unspecified_info(self):
        """

        Test the github_linkcode_resolve function when given unspecified information.

        This test case examines the resolver's behavior when no module or fullname is provided.
        It verifies that the function correctly handles this absence of information and returns None as expected.
        The test is performed for the Python domain with version '3.2' and next_version '3.2'.

        """
        domain = "py"
        info = {"module": None, "fullname": None}
        self.assertIsNone(
            github_links.github_linkcode_resolve(
                domain, info, version="3.2", next_version="3.2"
            )
        )

    def test_github_linkcode_resolve_not_found(self):
        """

        Tests the resolution of GitHub link codes when the referenced module does not exist.

        This test case checks that the github_linkcode_resolve function returns None when 
        it encounters a module that is not found. It simulates this scenario by providing 
        a fictional module name and verifying that the function behaves as expected in 
        this case. The test covers the function's behavior for Python link codes, 
        using a specific version and next version of the module.

        """
        info = {
            "module": "foo.bar.baz.hopefully_non_existant_module",
            "fullname": "MyClass",
        }
        self.assertIsNone(
            github_links.github_linkcode_resolve(
                "py", info, version="3.2", next_version="3.2"
            )
        )

    def test_github_linkcode_resolve_link_to_object(self):
        info = {
            "module": "tests.sphinx.testdata.package.module",
            "fullname": "MyClass",
        }
        self.assertEqual(
            github_links.github_linkcode_resolve(
                "py", info, version="3.2", next_version="3.2"
            ),
            "https://github.com/django/django/blob/main/tests/sphinx/"
            "testdata/package/module.py#L12",
        )

    def test_github_linkcode_resolve_link_to_class_older_version(self):
        info = {
            "module": "tests.sphinx.testdata.package.module",
            "fullname": "MyClass",
        }
        self.assertEqual(
            github_links.github_linkcode_resolve(
                "py", info, version="2.2", next_version="3.2"
            ),
            "https://github.com/django/django/blob/stable/2.2.x/tests/sphinx/"
            "testdata/package/module.py#L12",
        )

    def test_import_error(self):
        msg = "Could not import '.....test' in 'tests.sphinx.testdata.package'."
        with self.assertRaisesMessage(ImportError, msg):
            github_links.get_path_and_line(
                module="tests.sphinx.testdata.package.import_error", fullname="Test"
            )
