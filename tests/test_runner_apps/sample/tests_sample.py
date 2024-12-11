import doctest
from unittest import TestCase

from django.test import SimpleTestCase
from django.test import TestCase as DjangoTestCase

from . import doctests


class TestVanillaUnittest(TestCase):
    def test_sample(self):
        self.assertEqual(1, 1)


class TestDjangoTestCase(DjangoTestCase):
    def test_sample(self):
        self.assertEqual(1, 1)


class TestZimpleTestCase(SimpleTestCase):
    # Z is used to trick this test case to appear after Vanilla in default suite

    def test_sample(self):
        self.assertEqual(1, 1)


class EmptyTestCase(TestCase):
    pass


def load_tests(loader, tests, ignore):
    """
    Loads and adds doctests to the test suite.

    This function is used to integrate doctests into the testing framework. It takes a test loader, a test suite, and an ignore parameter, 
    and returns the updated test suite with the doctests added.

    The doctests are loaded from a specific module, 'doctests', which contains the test cases.
    The function uses the doctest module to discover and add these test cases to the test suite.

    Parameters
    ----------
    loader : unittest.TestLoader
        The test loader used to discover and load tests.
    tests : unittest.TestSuite
        The test suite to which the doctests are added.
    ignore : list
        A list of tests to ignore.

    Returns
    -------
    unittest.TestSuite
        The updated test suite with the doctests added.

    """
    tests.addTests(doctest.DocTestSuite(doctests))
    return tests
