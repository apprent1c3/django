import copy
import unittest

from django.db.models.sql import AND, OR
from django.utils.tree import Node


class NodeTests(unittest.TestCase):
    def setUp(self):
        """
        Sets up the test environment by initializing two nodes.

        The first node is created with a predefined list of children, while the second node is created empty.
        This setup is used as a foundation for subsequent tests to ensure a consistent starting point.

        Attributes:
            node1 (Node): A node with children, used for testing with predefined data.
            node2 (Node): An empty node, used for testing with a clean slate.
            node1_children (list): A list of tuples representing the children of the first node, used for initialization.
        """
        self.node1_children = [("a", 1), ("b", 2)]
        self.node1 = Node(self.node1_children)
        self.node2 = Node()

    def test_str(self):
        """
        Tests the string representation of nodes.

        Verifies that the string representation of nodes matches the expected format,
        including the default label and the contents of the node.

        This test case checks two scenarios: a node with key-value pairs and an empty node.
        The expected output for the string representation is a tuple-like format,
        displaying the default label followed by the node's contents in parentheses.

        """
        self.assertEqual(str(self.node1), "(DEFAULT: ('a', 1), ('b', 2))")
        self.assertEqual(str(self.node2), "(DEFAULT: )")

    def test_repr(self):
        """

        Tests the string representation of Node objects.

        Verifies that the repr function returns the expected string format for Node instances,
        including the node's attributes and default values.

        """
        self.assertEqual(repr(self.node1), "<Node: (DEFAULT: ('a', 1), ('b', 2))>")
        self.assertEqual(repr(self.node2), "<Node: (DEFAULT: )>")

    def test_hash(self):
        node3 = Node(self.node1_children, negated=True)
        node4 = Node(self.node1_children, connector="OTHER")
        node5 = Node(self.node1_children)
        node6 = Node([["a", 1], ["b", 2]])
        node7 = Node([("a", [1, 2])])
        node8 = Node([("a", (1, 2))])
        self.assertNotEqual(hash(self.node1), hash(self.node2))
        self.assertNotEqual(hash(self.node1), hash(node3))
        self.assertNotEqual(hash(self.node1), hash(node4))
        self.assertEqual(hash(self.node1), hash(node5))
        self.assertEqual(hash(self.node1), hash(node6))
        self.assertEqual(hash(self.node2), hash(Node()))
        self.assertEqual(hash(node7), hash(node8))

    def test_len(self):
        """
        Verifies the length of nodes in the data structure.

        Checks if the length of the first node (node1) is correctly reported as 2 and 
        the length of the second node (node2) is correctly reported as 0. This test 
        ensures that the implementation of the __len__ method accurately represents 
        the size of the nodes in the data structure.
        """
        self.assertEqual(len(self.node1), 2)
        self.assertEqual(len(self.node2), 0)

    def test_bool(self):
        """
        Tests the boolean representation of nodes.

        This test case verifies that nodes can be evaluated as boolean values.
        It checks that node1 evaluates to True and node2 evaluates to False, 
        indicating their expected truthiness in a boolean context.
        """
        self.assertTrue(self.node1)
        self.assertFalse(self.node2)

    def test_contains(self):
        self.assertIn(("a", 1), self.node1)
        self.assertNotIn(("a", 1), self.node2)

    def test_add(self):
        # start with the same children of node1 then add an item
        """

        Tests the addition of a new child node to an existing node.

        Verifies that the add method correctly appends a child node with the specified value and returns the added child.
        Also checks that the length of the node's children list is incremented by one after adding a new child.
        Lastly, it ensures the string representation of the node reflects the addition of the new child in the correct order.

        """
        node3 = Node(self.node1_children)
        node3_added_child = ("c", 3)
        # add() returns the added data
        self.assertEqual(node3.add(node3_added_child, Node.default), node3_added_child)
        # we added exactly one item, len() should reflect that
        self.assertEqual(len(self.node1) + 1, len(node3))
        self.assertEqual(str(node3), "(DEFAULT: ('a', 1), ('b', 2), ('c', 3))")

    def test_add_eq_child_mixed_connector(self):
        node = Node(["a", "b"], OR)
        self.assertEqual(node.add("a", AND), "a")
        self.assertEqual(node, Node([Node(["a", "b"], OR), "a"], AND))

    def test_negate(self):
        # negated is False by default
        """
        Tests the negation functionality of a node.

        Verifies that the node's negation state can be toggled successfully, ensuring that
        the negate method correctly sets and unsets the node's negated attribute.

        Checks the initial state of the node, then tests the negation and subsequent 
        re-negation to confirm the expected behavior.
        """
        self.assertFalse(self.node1.negated)
        self.node1.negate()
        self.assertTrue(self.node1.negated)
        self.node1.negate()
        self.assertFalse(self.node1.negated)

    def test_create(self):
        SubNode = type("SubNode", (Node,), {})

        a = SubNode([SubNode(["a", "b"], OR), "c"], AND)
        b = SubNode.create(a.children, a.connector, a.negated)
        self.assertEqual(a, b)
        # Children lists are the same object, but equal.
        self.assertIsNot(a.children, b.children)
        self.assertEqual(a.children, b.children)
        # Child Node objects are the same objects.
        for a_child, b_child in zip(a.children, b.children):
            if isinstance(a_child, Node):
                self.assertIs(a_child, b_child)
            self.assertEqual(a_child, b_child)

    def test_copy(self):
        """
        Tests the shallow copying of a Node object.

        Verifies that a copied Node object has the same attributes and content as the original,
        and that both objects reference the same child objects.

        This test ensures that the Node object's `__eq__` method works correctly and that the 
        copying process does not create unnecessary new objects for the child nodes.

        It covers the following specific scenarios:
        - Equality between the original and copied Node objects
        - Shared references between the child objects of the original and copied Node objects
        """
        a = Node([Node(["a", "b"], OR), "c"], AND)
        b = copy.copy(a)
        self.assertEqual(a, b)
        # Children lists are the same object.
        self.assertIs(a.children, b.children)
        # Child Node objects are the same objects.
        for a_child, b_child in zip(a.children, b.children):
            if isinstance(a_child, Node):
                self.assertIs(a_child, b_child)
            self.assertEqual(a_child, b_child)

    def test_deepcopy(self):
        """
        Tests the behavior of creating a deep copy of a Node instance.

        Verifies that the copied node has the same value and structure as the original,
        but that the resulting object is a distinct instance with its own child nodes.
        This ensures that modifications made to the copied node do not affect the original.
        The test checks for equality and identity of both the nodes and their children,
        to verify that the copying process is correct and complete.
        """
        a = Node([Node(["a", "b"], OR), "c"], AND)
        b = copy.deepcopy(a)
        self.assertEqual(a, b)
        # Children lists are not be the same object, but equal.
        self.assertIsNot(a.children, b.children)
        self.assertEqual(a.children, b.children)
        # Child Node objects are not be the same objects.
        for a_child, b_child in zip(a.children, b.children):
            if isinstance(a_child, Node):
                self.assertIsNot(a_child, b_child)
            self.assertEqual(a_child, b_child)

    def test_eq_children(self):
        node = Node(self.node1_children)
        self.assertEqual(node, self.node1)
        self.assertNotEqual(node, self.node2)

    def test_eq_connector(self):
        new_node = Node(connector="NEW")
        default_node = Node(connector="DEFAULT")
        self.assertEqual(default_node, self.node2)
        self.assertNotEqual(default_node, new_node)

    def test_eq_negated(self):
        """
        Tests that two Node instances with different negation states are not considered equal.

        Verifies that a Node with negated set to False is not equal to a Node with negated set to True.

        """
        node = Node(negated=False)
        negated = Node(negated=True)
        self.assertNotEqual(negated, node)
