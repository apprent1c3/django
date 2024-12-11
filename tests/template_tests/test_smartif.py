import unittest

from django.template.smartif import IfParser


class SmartIfTests(unittest.TestCase):
    def assertCalcEqual(self, expected, tokens):
        self.assertEqual(expected, IfParser(tokens).parse().eval({}))

    # We only test things here that are difficult to test elsewhere
    # Many other tests are found in the main tests for builtin template tags
    # Test parsing via the printed parse tree
    def test_not(self):
        """
        Tests the logical NOT operation in conditional statements.

        Verifies that the 'not' keyword correctly inverts a boolean value.
        The function checks that the parsed expression is correctly represented as a string,
        and that it evaluates to the expected boolean value when given an empty context.

        It tests both the negation of a False value (expected to be True) and the negation of a True value (expected to be False).
        """
        var = IfParser(["not", False]).parse()
        self.assertEqual("(not (literal False))", repr(var))
        self.assertTrue(var.eval({}))

        self.assertFalse(IfParser(["not", True]).parse().eval({}))

    def test_or(self):
        var = IfParser([True, "or", False]).parse()
        self.assertEqual("(or (literal True) (literal False))", repr(var))
        self.assertTrue(var.eval({}))

    def test_in(self):
        list_ = [1, 2, 3]
        self.assertCalcEqual(True, [1, "in", list_])
        self.assertCalcEqual(False, [1, "in", None])
        self.assertCalcEqual(False, [None, "in", list_])

    def test_not_in(self):
        list_ = [1, 2, 3]
        self.assertCalcEqual(False, [1, "not", "in", list_])
        self.assertCalcEqual(True, [4, "not", "in", list_])
        self.assertCalcEqual(False, [1, "not", "in", None])
        self.assertCalcEqual(True, [None, "not", "in", list_])

    def test_precedence(self):
        # (False and False) or True == True   <- we want this one, like Python
        # False and (False or True) == False
        """

        Tests the precedence of operators in the expression parser.

        Verifies that the parser correctly interprets the order of operations for logical 
        operators such as 'and' and 'or', and comparison operators like '=='.

        Checks various scenarios to ensure the parser evaluates expressions as expected, 
        including cases with multiple operators and nested expressions.

        Ensures the parser correctly builds an abstract syntax tree representation of the 
        expression, which can be converted to a string representation.

        """
        self.assertCalcEqual(True, [False, "and", False, "or", True])

        # True or (False and False) == True   <- we want this one, like Python
        # (True or False) and False == False
        self.assertCalcEqual(True, [True, "or", False, "and", False])

        # (1 or 1) == 2  -> False
        # 1 or (1 == 2)  -> True   <- we want this one
        self.assertCalcEqual(True, [1, "or", 1, "==", 2])

        self.assertCalcEqual(True, [True, "==", True, "or", True, "==", False])

        self.assertEqual(
            "(or (and (== (literal 1) (literal 2)) (literal 3)) (literal 4))",
            repr(IfParser([1, "==", 2, "and", 3, "or", 4]).parse()),
        )
