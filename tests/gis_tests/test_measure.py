"""
Distance and Area objects to allow for sensible and convenient calculation
and conversions. Here are some tests.
"""

import unittest

from django.contrib.gis.measure import A, Area, D, Distance
from django.test import SimpleTestCase


class DistanceTest(SimpleTestCase):
    "Testing the Distance object"

    def test_init(self):
        """
        Tests the initialization of the Distance class with different units to ensure correct conversion to base units.
        """
        d = Distance(m=100)
        self.assertEqual(d.m, 100)

        d1, d2, d3 = D(m=100), D(meter=100), D(metre=100)
        for d in (d1, d2, d3):
            self.assertEqual(d.m, 100)

        d = D(nm=100)
        self.assertEqual(d.m, 185200)

        y1, y2, y3 = D(yd=100), D(yard=100), D(Yard=100)
        for d in (y1, y2, y3):
            self.assertEqual(d.yd, 100)

        mm1, mm2 = D(millimeter=1000), D(MiLLiMeTeR=1000)
        for d in (mm1, mm2):
            self.assertEqual(d.m, 1.0)
            self.assertEqual(d.mm, 1000.0)

    def test_init_invalid(self):
        "Testing initialization from invalid units"
        with self.assertRaises(AttributeError):
            D(banana=100)

    def test_init_invalid_area_only_units(self):
        with self.assertRaises(AttributeError):
            D(ha=100)

    def test_access(self):
        "Testing access in different units"
        d = D(m=100)
        self.assertEqual(d.km, 0.1)
        self.assertAlmostEqual(d.ft, 328.084, 3)

    def test_access_invalid(self):
        "Testing access in invalid units"
        d = D(m=100)
        self.assertFalse(hasattr(d, "banana"))

    def test_addition(self):
        """
        Tests the addition and subtraction operations of the D class, verifying that they produce the expected results and raise TypeErrors when attempting to operate with incompatible types.
        """
        d1 = D(m=100)
        d2 = D(m=200)

        d3 = d1 + d2
        self.assertEqual(d3.m, 300)
        d3 += d1
        self.assertEqual(d3.m, 400)

        d4 = d1 - d2
        self.assertEqual(d4.m, -100)
        d4 -= d1
        self.assertEqual(d4.m, -200)

        with self.assertRaises(TypeError):
            d1 + 1

        with self.assertRaises(TypeError):
            d1 - 1

        with self.assertRaises(TypeError):
            d1 += 1

        with self.assertRaises(TypeError):
            d1 -= 1

    def test_multiplication(self):
        """
        Tests the multiplication and division operations of the Distance class, 
        including scalar multiplication, division by scalar, and division by another Distance object.
        """
        d1 = D(m=100)

        d3 = d1 * 2
        self.assertEqual(d3.m, 200)
        d3 = 2 * d1
        self.assertEqual(d3.m, 200)
        d3 *= 5
        self.assertEqual(d3.m, 1000)

        d4 = d1 / 2
        self.assertEqual(d4.m, 50)
        d4 /= 5
        self.assertEqual(d4.m, 10)
        d5 = d1 / D(m=2)
        self.assertEqual(d5, 50)

        a5 = d1 * D(m=10)
        self.assertIsInstance(a5, Area)
        self.assertEqual(a5.sq_m, 100 * 10)

        with self.assertRaises(TypeError):
            d1 *= D(m=1)

        with self.assertRaises(TypeError):
            d1 /= D(m=1)

    def test_unit_conversions(self):
        """
        Tests that unit conversions work as expected during mathematical operations, 
        ensuring the result has the correct default unit when combining distances with different units.
        """
        d1 = D(m=100)
        d2 = D(km=1)

        d3 = d1 + d2
        self.assertEqual(d3._default_unit, "m")
        d4 = d2 + d1
        self.assertEqual(d4._default_unit, "km")
        d5 = d1 * 2
        self.assertEqual(d5._default_unit, "m")
        d6 = d1 / 2
        self.assertEqual(d6._default_unit, "m")

    def test_comparisons(self):
        """

        Verifies the correctness of comparison operations between distance objects.

        This test ensures that distances are properly compared in terms of their magnitude,
        covering cases such as equality, greater than, and less than, as well as testing
        for falsy distances.

        """
        d1 = D(m=100)
        d2 = D(km=1)
        d3 = D(km=0)

        self.assertGreater(d2, d1)
        self.assertEqual(d1, d1)
        self.assertLess(d1, d2)
        self.assertFalse(d3)

    def test_units_str(self):
        """
        Tests the conversion of distance objects to string representations, verifying both human-readable string format and formal representation.
        """
        d1 = D(m=100)
        d2 = D(km=3.5)

        self.assertEqual(str(d1), "100.0 m")
        self.assertEqual(str(d2), "3.5 km")
        self.assertEqual(repr(d1), "Distance(m=100.0)")
        self.assertEqual(repr(d2), "Distance(km=3.5)")

    def test_furlong(self):
        d = D(m=201.168)
        self.assertEqual(d.furlong, 1)

    def test_unit_att_name(self):
        """
        Verifies the correctness of unit attribute names returned by the unit_attname class method for a variety of units.
        """
        unit_tuple = [
            ("Yard", "yd"),
            ("Nautical Mile", "nm"),
            ("German legal metre", "german_m"),
            ("Indian yard", "indian_yd"),
            ("Chain (Sears)", "chain_sears"),
            ("Chain", "chain"),
            ("Furrow Long", "furlong"),
        ]
        for nm, att in unit_tuple:
            with self.subTest(nm=nm):
                self.assertEqual(att, D.unit_attname(nm))

    def test_unit_att_name_invalid(self):
        """
        Tests that an AttributeError is raised with a specific message when an invalid unit name is passed to the unit_attname method of classes D and A.
        """
        msg = "Unknown unit type: invalid-unit-name"
        with self.assertRaisesMessage(AttributeError, msg):
            D.unit_attname("invalid-unit-name")
        with self.assertRaisesMessage(AttributeError, msg):
            A.unit_attname("invalid-unit-name")

    def test_hash(self):
        """
        Tests the hash function of the D class to ensure that objects with equivalent values have the same hash, and objects with different values have different hashes.
        """
        d1 = D(m=99)
        d2 = D(m=100)
        d3 = D(km=0.1)
        self.assertEqual(hash(d2), hash(d3))
        self.assertNotEqual(hash(d1), hash(d2))
        self.assertNotEqual(hash(d1), hash(d3))


class AreaTest(unittest.TestCase):
    "Testing the Area object"

    def test_init(self):
        """
        Verifies the correct initialization of the Area class from various valid units, ensuring that conversions are accurately performed.
        """
        a = Area(sq_m=100)
        self.assertEqual(a.sq_m, 100)

        a = A(sq_m=100)
        self.assertEqual(a.sq_m, 100)

        a = A(sq_mi=100)
        self.assertEqual(a.sq_m, 258998811.0336)

    def test_init_invalid_a(self):
        "Testing initialization from invalid units"
        with self.assertRaises(AttributeError):
            A(banana=100)

    def test_access(self):
        "Testing access in different units"
        a = A(sq_m=100)
        self.assertEqual(a.sq_km, 0.0001)
        self.assertAlmostEqual(a.sq_ft, 1076.391, 3)

    def test_access_invalid_a(self):
        "Testing access in invalid units"
        a = A(sq_m=100)
        self.assertFalse(hasattr(a, "banana"))

    def test_addition(self):
        """
        Tests the implementation of addition and subtraction operations for objects of class A, ensuring correct results and handling of invalid operands.
        """
        a1 = A(sq_m=100)
        a2 = A(sq_m=200)

        a3 = a1 + a2
        self.assertEqual(a3.sq_m, 300)
        a3 += a1
        self.assertEqual(a3.sq_m, 400)

        a4 = a1 - a2
        self.assertEqual(a4.sq_m, -100)
        a4 -= a1
        self.assertEqual(a4.sq_m, -200)

        with self.assertRaises(TypeError):
            a1 + 1

        with self.assertRaises(TypeError):
            a1 - 1

        with self.assertRaises(TypeError):
            a1 += 1

        with self.assertRaises(TypeError):
            a1 -= 1

    def test_multiplication(self):
        """
        Verifies the correctness of multiplication and division operations on instances of class A, including scalar multiplication, commutativity, and in-place modification, while also checking for invalid operand types.
        """
        a1 = A(sq_m=100)

        a3 = a1 * 2
        self.assertEqual(a3.sq_m, 200)
        a3 = 2 * a1
        self.assertEqual(a3.sq_m, 200)
        a3 *= 5
        self.assertEqual(a3.sq_m, 1000)

        a4 = a1 / 2
        self.assertEqual(a4.sq_m, 50)
        a4 /= 5
        self.assertEqual(a4.sq_m, 10)

        with self.assertRaises(TypeError):
            a1 * A(sq_m=1)

        with self.assertRaises(TypeError):
            a1 *= A(sq_m=1)

        with self.assertRaises(TypeError):
            a1 / A(sq_m=1)

        with self.assertRaises(TypeError):
            a1 /= A(sq_m=1)

    def test_unit_conversions(self):
        """
        Tests the conversion of units during mathematical operations in the A class, ensuring that the default unit is correctly preserved when performing addition and multiplication.
        """
        a1 = A(sq_m=100)
        a2 = A(sq_km=1)

        a3 = a1 + a2
        self.assertEqual(a3._default_unit, "sq_m")
        a4 = a2 + a1
        self.assertEqual(a4._default_unit, "sq_km")
        a5 = a1 * 2
        self.assertEqual(a5._default_unit, "sq_m")
        a6 = a1 / 2
        self.assertEqual(a6._default_unit, "sq_m")

    def test_comparisons(self):
        """
        Tests the comparison functionality of the A class, ensuring that instances can be correctly ordered and compared based on their areas.
        """
        a1 = A(sq_m=100)
        a2 = A(sq_km=1)
        a3 = A(sq_km=0)

        self.assertGreater(a2, a1)
        self.assertEqual(a1, a1)
        self.assertLess(a1, a2)
        self.assertFalse(a3)

    def test_units_str(self):
        """
        Tests the conversion of area objects to string representations, verifying both string and repr formats are correctly generated for different unit types.
        """
        a1 = A(sq_m=100)
        a2 = A(sq_km=3.5)

        self.assertEqual(str(a1), "100.0 sq_m")
        self.assertEqual(str(a2), "3.5 sq_km")
        self.assertEqual(repr(a1), "Area(sq_m=100.0)")
        self.assertEqual(repr(a2), "Area(sq_km=3.5)")

    def test_hectare(self):
        a = A(sq_m=10000)
        self.assertEqual(a.ha, 1)

    def test_hectare_unit_att_name(self):
        self.assertEqual(A.unit_attname("Hectare"), "ha")

    def test_hash(self):
        """
        Tests the hash functionality of class A, ensuring equal instances have the same hash and unequal instances have different hashes, based on their area properties.
        """
        a1 = A(sq_m=100)
        a2 = A(sq_m=1000000)
        a3 = A(sq_km=1)
        self.assertEqual(hash(a2), hash(a3))
        self.assertNotEqual(hash(a1), hash(a2))
        self.assertNotEqual(hash(a1), hash(a3))
