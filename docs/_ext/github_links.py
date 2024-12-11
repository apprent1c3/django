import ast
import functools
import importlib.util
import pathlib


class CodeLocator(ast.NodeVisitor):
    def __init__(self):
        super().__init__()
        self.current_path = []
        self.node_line_numbers = {}
        self.import_locations = {}

    @classmethod
    def from_code(cls, code):
        """
        Creates an instance of the locator class from a given Python code string.

        This method parses the provided code into an abstract syntax tree (AST) and then
        traverses the tree to initialize the locator instance. The resulting locator
        instance contains information extracted from the code.

        :param code: A string of valid Python code.
        :returns: An instance of the locator class initialized with the extracted information.

        """
        tree = ast.parse(code)
        locator = cls()
        locator.visit(tree)
        return locator

    def visit_node(self, node):
        self.current_path.append(node.name)
        self.node_line_numbers[".".join(self.current_path)] = node.lineno
        self.generic_visit(node)
        self.current_path.pop()

    def visit_FunctionDef(self, node):
        self.visit_node(node)

    def visit_ClassDef(self, node):
        self.visit_node(node)

    def visit_ImportFrom(self, node):
        """
        ..: 
            Visit an ImportFrom node to track imported module locations.

            This method iterates over alias names in the import statement, handling wildcard imports and named imports separately.
            For wildcard imports, it reads the imported module's file contents and extracts import locations using a CodeLocator.
            Named imports are directly tracked with their corresponding module path.

            :param node: The ImportFrom node to visit
            :return: None
        """
        for alias in node.names:
            if alias.asname:
                # Exclude linking aliases (`import x as y`) to avoid confusion
                # when clicking a source link to a differently named entity.
                continue
            if alias.name == "*":
                # Resolve wildcard imports.
                file = module_name_to_file_path(node.module)
                file_contents = file.read_text(encoding="utf-8")
                locator = CodeLocator.from_code(file_contents)
                self.import_locations.update(locator.import_locations)
                self.import_locations.update(
                    {n: node.module for n in locator.node_line_numbers if "." not in n}
                )
            else:
                self.import_locations[alias.name] = ("." * node.level) + (
                    node.module or ""
                )


@functools.lru_cache(maxsize=1024)
def get_locator(file):
    file_contents = file.read_text(encoding="utf-8")
    return CodeLocator.from_code(file_contents)


class CodeNotFound(Exception):
    pass


def module_name_to_file_path(module_name):
    # Avoid importlib machinery as locating a module involves importing its
    # parent, which would trigger import side effects.

    for suffix in [".py", "/__init__.py"]:
        file_path = pathlib.Path(__file__).parents[2] / (
            module_name.replace(".", "/") + suffix
        )
        if file_path.exists():
            return file_path

    raise CodeNotFound


def get_path_and_line(module, fullname):
    """
    Get the file path and line number of a given object in a module.

    :param module: The module to search in.
    :param fullname: The full name of the object, including any namespaces or classes.

    :raise CodeNotFound: If the object is not found in the module or any of its imports.
    :raise ImportError: If an import fails while trying to locate the object.

    :return: A tuple containing the file path and line number of the object, or raises an exception if not found.

    :note: This function recursively searches for the object in the module's imports if it is not found directly.
    """
    path = module_name_to_file_path(module_name=module)

    locator = get_locator(path)

    lineno = locator.node_line_numbers.get(fullname)

    if lineno is not None:
        return path, lineno

    imported_object = fullname.split(".", maxsplit=1)[0]
    try:
        imported_path = locator.import_locations[imported_object]
    except KeyError:
        raise CodeNotFound

    # From a statement such as:
    # from . import y.z
    # - either y.z might be an object in the parent module
    # - or y might be a module, and z be an object in y
    # also:
    # - either the current file is x/__init__.py, and z would be in x.y
    # - or the current file is x/a.py, and z would be in x.a.y
    if path.name != "__init__.py":
        # Look in parent module
        module = module.rsplit(".", maxsplit=1)[0]
    try:
        imported_module = importlib.util.resolve_name(
            name=imported_path, package=module
        )
    except ImportError as error:
        raise ImportError(
            f"Could not import '{imported_path}' in '{module}'."
        ) from error
    try:
        return get_path_and_line(module=imported_module, fullname=fullname)
    except CodeNotFound:
        if "." not in fullname:
            raise

        first_element, remainder = fullname.rsplit(".", maxsplit=1)
        # Retrying, assuming the first element of the fullname is a module.
        return get_path_and_line(
            module=f"{imported_module}.{first_element}", fullname=remainder
        )


def get_branch(version, next_version):
    if version == next_version:
        return "main"
    else:
        return f"stable/{version}.x"


def github_linkcode_resolve(domain, info, *, version, next_version):
    if domain != "py":
        return None

    if not (module := info["module"]):
        return None

    try:
        path, lineno = get_path_and_line(module=module, fullname=info["fullname"])
    except CodeNotFound:
        return None

    branch = get_branch(version=version, next_version=next_version)
    relative_path = path.relative_to(pathlib.Path(__file__).parents[2])
    # Use "/" explicitly to join the path parts since str(file), on Windows,
    # uses the Windows path separator which is incorrect for URLs.
    url_path = "/".join(relative_path.parts)
    return f"https://github.com/django/django/blob/{branch}/{url_path}#L{lineno}"
