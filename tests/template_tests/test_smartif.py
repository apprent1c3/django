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
        Tests the functionality of the 'not' operator in conditional expressions.

        Verifies that the 'not' operator correctly inverts boolean values.
        The test checks the parsing and evaluation of 'not' expressions, ensuring 
        the correct output for both false and true inputs. 

        It asserts that the 'not' operator is represented correctly and that 
        the evaluation of 'not' expressions returns the expected boolean results.

        """
        var = IfParser(["not", False]).parse()
        self.assertEqual("(not (literal False))", repr(var))
        self.assertTrue(var.eval({}))

        self.assertFalse(IfParser(["not", True]).parse().eval({}))

    def test_or(self):
        """

        Tests the 'or' logical operator functionality.

        This function verifies that the 'or' operator is correctly parsed and evaluated.
        It checks that the expression is properly converted into its abstract syntax representation
        and that its evaluation produces the expected boolean result.

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
        """
        Tests the \"not in\" operator functionality in the calculator.
        Checks that an element is correctly identified as not present or present in a list.
        Verifies the behavior when the list or the element is None.
        """
        list_ = [1, 2, 3]
        self.assertCalcEqual(False, [1, "not", "in", list_])
        self.assertCalcEqual(True, [4, "not", "in", list_])
        self.assertCalcEqual(False, [1, "not", "in", None])
        self.assertCalcEqual(True, [None, "not", "in", list_])

    def test_precedence(self):
        # (False and False) or True == True   <- we want this one, like Python
        # False and (False or True) == False
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
