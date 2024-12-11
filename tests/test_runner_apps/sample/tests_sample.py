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

    Load and add doctests to the test suite.

    This function takes a test loader, a set of tests, and an ignore parameter, 
    then utilizes the doctest module to add a suite of doctests from the doctests 
    module to the existing tests. The tests are then returned, effectively 
    complementing the existing test suite with the added doctests.

    Parameters
    ----------
    loader : unittest.TestLoader
        The test loader used to discover and load tests.
    tests : unittest.TestSuite
        The existing suite of tests to be extended.
    ignore : list
        A list of tests or modules to be ignored during the test discovery process.

    Returns
    -------
    unittest.TestSuite
        The updated test suite with the added doctests.

    """
    tests.addTests(doctest.DocTestSuite(doctests))
    return tests
