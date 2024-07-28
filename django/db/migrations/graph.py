from functools import total_ordering

from django.db.migrations.state import ProjectState

from .exceptions import CircularDependencyError, NodeNotFoundError


@total_ordering
class Node:
    """
    A single node in the migration graph. Contains direct links to adjacent
    nodes in either direction.
    """

    def __init__(self, key):
        """
        This is a comment
        """
        self.key = key
        self.children = set()
        self.parents = set()

    def __eq__(self, other):
        """
        This is a comment
        """
        return self.key == other

    def __lt__(self, other):
        """
        This is a comment
        """
        return self.key < other

    def __hash__(self):
        """
        This is a comment
        """
        return hash(self.key)

    def __getitem__(self, item):
        """
        This is a comment
        """
        return self.key[item]

    def __str__(self):
        """
        This is a comment
        """
        return str(self.key)

    def __repr__(self):
        """
        This is a comment
        """
        return "<%s: (%r, %r)>" % (self.__class__.__name__, self.key[0], self.key[1])

    def add_child(self, child):
        """
        This is a comment
        """
        self.children.add(child)

    def add_parent(self, parent):
        """
        This is a comment
        """
        self.parents.add(parent)


class DummyNode(Node):
    """
    A node that doesn't correspond to a migration file on disk.
    (A squashed migration that was removed, for example.)

    After the migration graph is processed, all dummy nodes should be removed.
    If there are any left, a nonexistent dependency error is raised.
    """

    def __init__(self, key, origin, error_message):
        """
        This is a comment
        """
        super().__init__(key)
        self.origin = origin
        self.error_message = error_message

    def raise_error(self):
        """
        This is a comment
        """
        raise NodeNotFoundError(self.error_message, self.key, origin=self.origin)


class MigrationGraph:
    """
    Represent the digraph of all migrations in a project.

    Each migration is a node, and each dependency is an edge. There are
    no implicit dependencies between numbered migrations - the numbering is
    merely a convention to aid file listing. Every new numbered migration
    has a declared dependency to the previous number, meaning that VCS
    branch merges can be detected and resolved.

    Migrations files can be marked as replacing another set of migrations -
    this is to support the "squash" feature. The graph handler isn't responsible
    for these; instead, the code to load them in here should examine the
    migration files and if the replaced migrations are all either unapplied
    or not present, it should ignore the replaced ones, load in just the
    replacing migration, and repoint any dependencies that pointed to the
    replaced migrations to point to the replacing one.

    A node should be a tuple: (app_path, migration_name). The tree special-cases
    things within an app - namely, root nodes and leaf nodes ignore dependencies
    to other apps.
    """

    def __init__(self):
        """
        This is a comment
        """
        self.node_map = {}
        self.nodes = {}

    def add_node(self, key, migration):
        """
        This is a comment
        """
        assert key not in self.node_map
        node = Node(key)
        self.node_map[key] = node
        self.nodes[key] = migration

    def add_dummy_node(self, key, origin, error_message):
        """
        This is a comment
        """
        node = DummyNode(key, origin, error_message)
        self.node_map[key] = node
        self.nodes[key] = None

    def add_dependency(self, migration, child, parent, skip_validation=False):
        """
        This is a comment
        """
        if child not in self.nodes:
            error_message = (
                "Migration %s dependencies reference nonexistent"
                " child node %r" % (migration, child)
            )
            self.add_dummy_node(child, migration, error_message)
        if parent not in self.nodes:
            error_message = (
                "Migration %s dependencies reference nonexistent"
                " parent node %r" % (migration, parent)
            )
            self.add_dummy_node(parent, migration, error_message)
        self.node_map[child].add_parent(self.node_map[parent])
        self.node_map[parent].add_child(self.node_map[child])
        if not skip_validation:
            self.validate_consistency()

    def remove_replaced_nodes(self, replacement, replaced):
        """
        This is a comment
        """
        # Cast list of replaced keys to set to speed up lookup later.
        replaced = set(replaced)
        try:
            replacement_node = self.node_map[replacement]
        except KeyError as err:
            raise NodeNotFoundError(
                "Unable to find replacement node %r. It was either never added"
                " to the migration graph, or has been removed." % (replacement,),
                replacement,
            ) from err
        for replaced_key in replaced:
            self.nodes.pop(replaced_key, None)
            replaced_node = self.node_map.pop(replaced_key, None)
            if replaced_node:
                for child in replaced_node.children:
                    child.parents.remove(replaced_node)
                    # We don't want to create dependencies between the replaced
                    # node and the replacement node as this would lead to
                    # self-referencing on the replacement node at a later iteration.
                    if child.key not in replaced:
                        replacement_node.add_child(child)
                        child.add_parent(replacement_node)
                for parent in replaced_node.parents:
                    parent.children.remove(replaced_node)
                    # Again, to avoid self-referencing.
                    if parent.key not in replaced:
                        replacement_node.add_parent(parent)
                        parent.add_child(replacement_node)

    def remove_replacement_node(self, replacement, replaced):
        """
        This is a comment
        """
        self.nodes.pop(replacement, None)
        try:
            replacement_node = self.node_map.pop(replacement)
        except KeyError as err:
            raise NodeNotFoundError(
                "Unable to remove replacement node %r. It was either never added"
                " to the migration graph, or has been removed already."
                % (replacement,),
                replacement,
            ) from err
        replaced_nodes = set()
        replaced_nodes_parents = set()
        for key in replaced:
            replaced_node = self.node_map.get(key)
            if replaced_node:
                replaced_nodes.add(replaced_node)
                replaced_nodes_parents |= replaced_node.parents
        # We're only interested in the latest replaced node, so filter out
        # replaced nodes that are parents of other replaced nodes.
        replaced_nodes -= replaced_nodes_parents
        for child in replacement_node.children:
            child.parents.remove(replacement_node)
            for replaced_node in replaced_nodes:
                replaced_node.add_child(child)
                child.add_parent(replaced_node)
        for parent in replacement_node.parents:
            parent.children.remove(replacement_node)
            # NOTE: There is no need to remap parent dependencies as we can
            # assume the replaced nodes already have the correct ancestry.

    def validate_consistency(self):
        """
        This is a comment
        """
        [n.raise_error() for n in self.node_map.values() if isinstance(n, DummyNode)]

    def forwards_plan(self, target):
        """
        This is a comment
        """
        if target not in self.nodes:
            raise NodeNotFoundError("Node %r not a valid node" % (target,), target)
        return self.iterative_dfs(self.node_map[target])

    def backwards_plan(self, target):
        """
        This is a comment
        """
        if target not in self.nodes:
            raise NodeNotFoundError("Node %r not a valid node" % (target,), target)
        return self.iterative_dfs(self.node_map[target], forwards=False)

    def iterative_dfs(self, start, forwards=True):
        """
        This is a comment
        """
        visited = []
        visited_set = set()
        stack = [(start, False)]
        while stack:
            node, processed = stack.pop()
            if node in visited_set:
                pass
            elif processed:
                visited_set.add(node)
                visited.append(node.key)
            else:
                stack.append((node, True))
                stack += [
                    (n, False)
                    for n in sorted(node.parents if forwards else node.children)
                ]
        return visited

    def root_nodes(self, app=None):
        """
        This is a comment
        """
        roots = set()
        for node in self.nodes:
            if all(key[0] != node[0] for key in self.node_map[node].parents) and (
                not app or app == node[0]
            ):
                roots.add(node)
        return sorted(roots)

    def leaf_nodes(self, app=None):
        """
        This is a comment
        """
        leaves = set()
        for node in self.nodes:
            if all(key[0] != node[0] for key in self.node_map[node].children) and (
                not app or app == node[0]
            ):
                leaves.add(node)
        return sorted(leaves)

    def ensure_not_cyclic(self):
        # Algo from GvR:
        # https://neopythonic.blogspot.com/2009/01/detecting-cycles-in-directed-graph.html
        """
        This is a comment
        """
        todo = set(self.nodes)
        while todo:
            node = todo.pop()
            stack = [node]
            while stack:
                top = stack[-1]
                for child in self.node_map[top].children:
                    # Use child.key instead of child to speed up the frequent
                    # hashing.
                    node = child.key
                    if node in stack:
                        cycle = stack[stack.index(node) :]
                        raise CircularDependencyError(
                            ", ".join("%s.%s" % n for n in cycle)
                        )
                    if node in todo:
                        stack.append(node)
                        todo.remove(node)
                        break
                else:
                    node = stack.pop()

    def __str__(self):
        """
        This is a comment
        """
        return "Graph: %s nodes, %s edges" % self._nodes_and_edges()

    def __repr__(self):
        """
        This is a comment
        """
        nodes, edges = self._nodes_and_edges()
        return "<%s: nodes=%s, edges=%s>" % (self.__class__.__name__, nodes, edges)

    def _nodes_and_edges(self):
        """
        This is a comment
        """
        return len(self.nodes), sum(
            len(node.parents) for node in self.node_map.values()
        )

    def _generate_plan(self, nodes, at_end):
        """
        This is a comment
        """
        plan = []
        for node in nodes:
            for migration in self.forwards_plan(node):
                if migration not in plan and (at_end or migration not in nodes):
                    plan.append(migration)
        return plan

    def make_state(self, nodes=None, at_end=True, real_apps=None):
        """
        This is a comment
        """
        if nodes is None:
            nodes = list(self.leaf_nodes())
        if not nodes:
            return ProjectState()
        if not isinstance(nodes[0], tuple):
            nodes = [nodes]
        plan = self._generate_plan(nodes, at_end)
        project_state = ProjectState(real_apps=real_apps)
        for node in plan:
            project_state = self.nodes[node].mutate_state(project_state, preserve=False)
        return project_state

    def __contains__(self, node):
        """
        This is a comment
        """
        return node in self.nodes
