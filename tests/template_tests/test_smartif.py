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
        Tests the 'not' operator functionality in the IfParser.

        Verifies that the 'not' operator is correctly parsed and evaluated, 
        producing the expected boolean result.

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

        Tests the precedence of logical operators in the expression parser.

        The function checks that the parser correctly handles the order of operations for 'and' and 'or' operators,
        as well as their interaction with comparison operators like '=='. It also verifies that the parser produces
        the expected output for various input expressions.


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
