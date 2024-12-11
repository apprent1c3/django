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
    Adds doctests to the test suite.

    This function is used to load and integrate doctests into the existing test suite. 
    It utilizes the doctest module to discover and execute doctests defined in the 
    doctests module, effectively allowing test cases to be embedded within 
    documentation strings.

    The function takes in a test loader, a collection of tests, and an ignore 
    parameter, and returns an updated test suite that includes the doctests.

    :param loader: The test loader used to load tests.
    :param tests: The collection of tests to which doctests will be added.
    :param ignore: An ignore parameter, typically used to exclude certain tests.
    :returns: The updated test suite containing the doctests.

    """
    tests.addTests(doctest.DocTestSuite(doctests))
    return tests
