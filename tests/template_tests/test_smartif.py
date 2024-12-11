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

        Tests the logical 'not' operator in the IfParser.

        Verifies that the 'not' operator is correctly parsed and evaluated.
        The test covers the cases where the operand is both True and False,
        ensuring the 'not' operator correctly inverts the boolean value.

        The test checks the following conditions:
        - The 'not' operator is correctly represented in the parsed expression.
        - The 'not' operator correctly evaluates to True when the operand is False.
        - The 'not' operator correctly evaluates to False when the operand is True.

        """
        var = IfParser(["not", False]).parse()
        self.assertEqual("(not (literal False))", repr(var))
        self.assertTrue(var.eval({}))

        self.assertFalse(IfParser(["not", True]).parse().eval({}))

    def test_or(self):
        """

        Checks the functionality of 'or' operator parsing.

        This test case verifies that the IfParser correctly interprets the 'or' operator 
        and the evaluated result is as expected. It ensures that the parsed expression 
        is represented as a logical 'or' operation and the evaluation of the expression 
        returns True when only one of the operands is True.

        """
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

        Tests the precedence of logical operators in conditional expressions.

        This function verifies that the order of operations is correctly applied when 
        evaluating expressions containing 'and', 'or', and comparison operators. It 
        also checks that the parser correctly handles the precedence of these operators 
        and generates the expected abstract syntax tree representation.

        The test cases cover various scenarios, including the use of 'and' and 'or' 
        operators with boolean values, as well as the interaction between comparison 
        operators and logical operators. The parser's output is checked against the 
        expected string representation of the parsed expression.

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
