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
        """
        Tests the CodeLocator class to correctly identify and locate code elements.

        This function verifies that the CodeLocator can accurately find and map the line numbers of
        functions and classes, as well as the locations of imported modules and variables.

        The expected output includes a dictionary mapping code elements to their respective line numbers,
        and another dictionary mapping imported variables to their import locations. 

        The test case covers both absolute and relative imports, as well as function and class definitions.
        It ensures that the CodeLocator can handle a variety of code structures and correctly identify the 
        locations of different code elements. 
        """
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
        """

        Tests the module_name_to_file_path function when resolving a package module name.

        This function checks if the given module name is correctly resolved to its corresponding file path.
        In the context of a package, this function should return a path that ends with the package's __init__.py file.
        The test verifies that the resolved path matches the expected pattern.

        Args:
            None

        Returns:
            None

        Raises:
            AssertionError: If the resolved path does not match the expected pattern.

        """
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
        Returns the filesystem path and line number for a given Python module and fullname.

        The function takes a Python module name and a fullname (function or class name) as input, 
        and returns a tuple containing the path to the file where the fullname is defined, 
        and the line number where the definition is located.

        This is typically used to determine the location of a specific function or class 
        within a larger codebase, and can be useful for generating links to source code 
        or reporting errors.
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
        """
        Returns the file path and line number of a given object that is imported from another module.

        This function is useful for locating the original definition of an object, even if it has been imported from a different module.

        Parameters
        ----------
        module : str
            The name of the module where the object is imported
        fullname : str
            The fully qualified name of the object

        Returns
        -------
        tuple
            A tuple containing the path to the file where the object is defined and the line number where it is defined
        """
        path, line = github_links.get_path_and_line(
            module="tests.sphinx.testdata.package.module", fullname="MyOtherClass"
        )

        self.assertEqual(
            last_n_parts(path, 5), "tests/sphinx/testdata/package/other_module.py"
        )
        self.assertEqual(line, 1)

    def test_get_path_and_line_wildcard_import(self):
        """
        Retrieve the file path and line number of a class or object within a Python module.

        Given a module name and the full name of a class or object, this function returns the path to the file where the class or object is defined and the line number where its definition begins.

        The function is useful for generating links to specific parts of a GitHub repository, such as the definition of a class or mixin. It can handle wildcard imports and returns the actual file path and line number where the class or object is defined.

        Args:
            module (str): The name of the Python module to search.
            fullname (str): The full name of the class or object to find.

        Returns:
            tuple: A tuple containing the file path (str) and line number (int) where the class or object is defined.

        """
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
        domain = "unspecified"
        info = {}
        self.assertIsNone(
            github_links.github_linkcode_resolve(
                domain, info, version="3.2", next_version="3.2"
            )
        )

    def test_github_linkcode_resolve_unspecified_info(self):
        domain = "py"
        info = {"module": None, "fullname": None}
        self.assertIsNone(
            github_links.github_linkcode_resolve(
                domain, info, version="3.2", next_version="3.2"
            )
        )

    def test_github_linkcode_resolve_not_found(self):
        """
        Tests that github_linkcode_resolve returns None when it cannot find a GitHub link for a given module and fullname.

        This test case simulates a scenario where the module and fullname do not correspond to a real GitHub repository or file. It verifies that the function correctly handles this situation and returns None instead of raising an error or providing incorrect information.

        Parameters are specified for a Python ('py') language, a specific module and fullname, and versions '3.2' and '3.2' respectively, but the key aspect of this test is the non-existent module, which should lead to a None result.
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
        """
        Raised when the module is not properly importable, tests that the github_links.get_path_and_line function correctly handles an ImportError.

        When the function is called with a module that cannot be imported, it checks that an ImportError is raised with the expected error message, ensuring proper error handling and reporting for import issues.
        """
        msg = "Could not import '.....test' in 'tests.sphinx.testdata.package'."
        with self.assertRaisesMessage(ImportError, msg):
            github_links.get_path_and_line(
                module="tests.sphinx.testdata.package.import_error", fullname="Test"
            )
