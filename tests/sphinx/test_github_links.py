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
        """
        Tests the conversion of a module name to its corresponding file path within a package, ensuring it correctly resolves to the package's initialization file.
        """
        path = github_links.module_name_to_file_path("django")

        self.assertEqual(last_n_parts(path, 2), "django/__init__.py")

    def test_module_name_to_file_path_module(self):
        """
        Tests the module_name_to_file_path function to ensure it correctly converts a Python module name to its corresponding file path.

        The function should transform a module name, such as 'django.shortcuts', into a file path like 'django/shortcuts.py', which represents the location of the module file in a standard Python package structure.

        This test case verifies that the last two parts of the generated path match the expected module file path, providing confidence in the function's ability to accurately map module names to their file locations.
        """
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
        """
        Gets the file path and line number of a cached property within a specific module.

        The path is returned as a string and the line number is returned as an integer. 
        The function is designed to work with cached properties, and it relies on the module name and the full name of the cached property to determine its location. 
        The module name should be specified as a string, including the package and module names, and the full name of the cached property should include the class name and the property name, separated by a dot. 
        The function returns the path to the file where the cached property is defined, and the line number where it is defined.
        """
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

        Retrieves the file path and line number of a forwarded import.

        Given a module name and a fullname of an object (e.g. class, function), 
        this function determines the path to the file where the object is defined 
        and the line number where the definition starts. 

        The path is determined relative to the module, so it can handle cases 
        where the object is defined in a different file from where it is imported.

        The returned path is a string representing the file location, and the 
        line number is an integer indicating the line where the object's definition 
        begins. 

        This function is useful for resolving the original location of objects 
        that have been imported or forwarded from other modules.

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

        Return the file path and line number for a given class or object.

        This function takes a module name and the fullname of a class or object within that module,
        and returns the file path where the class or object is defined, along with its line number.

        The path is the file location relative to the module, and the line number is the line where the class or object is defined.

        The function supports the resolution of classes and objects defined within wildcard imports,
        allowing for the accurate identification of their source locations.

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
        """
        Retrieve the file path and line number of a forwarded import module.

        This function locates the definition of a class or module that is imported 
        using a 'from... import' statement and returns its file path and the line number 
        where it is defined, given the module name and the full qualified name of the 
        class or module. The returned path is the location of the file where the class 
        or module is actually defined, rather than where it is imported.

        The function takes into account Python's import mechanics, including 
        forwarded imports, where a module imports and re-exports another module 
        or class under a different name. It will follow these imports to find the 
        actual location of the class or module.

        The result can be used for tasks like generating documentation links or 
        resolving the actual location of imported classes or modules.

        """
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
        """
        Tests the retrieval of the latest branch for a given version.

        This test case verifies that the function correctly returns the expected branch name 
        for a specific version. In this scenario, it checks that the latest branch for version 
        '3.2' is 'main', ensuring that the function behaves as expected when the version 
        and next version are the same.

        :param None
        :returns: None
        :raises: AssertionError if the function does not return the expected branch name
        """
        branch = github_links.get_branch(version="3.2", next_version="3.2")
        self.assertEqual(branch, "main")

    def test_github_linkcode_resolve_unspecified_domain(self):
        """

        Tests the resolution of a GitHub link code when the domain is unspecified.

        This test case checks the behavior of the github_linkcode_resolve function when 
        it encounters an unspecified domain. It verifies that the function returns None 
        as expected. The test uses a specific version and next version, but the focus 
        is on the domain resolution rather than version handling. 

        Parameters are not explicitly specified here, as they are assumed to be 
        handled by the github_linkcode_resolve function; for details on parameters, 
        refer to that function's documentation.

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
        Tests the github_linkcode_resolve function when the module and fullname information are unspecified.

        This test case verifies that the function returns None when the domain is 'py' and the info dictionary contains no module or fullname specifications.

        Parameters are set to default values with '3.2' as the current and next version.

        The expected result is that the github_linkcode_resolve function should return None when the necessary information for resolving the link is not provided.
        """
        domain = "py"
        info = {"module": None, "fullname": None}
        self.assertIsNone(
            github_links.github_linkcode_resolve(
                domain, info, version="3.2", next_version="3.2"
            )
        )

    def test_github_linkcode_resolve_not_found(self):
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
