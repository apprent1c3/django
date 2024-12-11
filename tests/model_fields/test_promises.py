import datetime
from decimal import Decimal

from django.db.models import (
    AutoField,
    BinaryField,
    BooleanField,
    CharField,
    DateField,
    DateTimeField,
    DecimalField,
    EmailField,
    FileField,
    FilePathField,
    FloatField,
    GenericIPAddressField,
    ImageField,
    IntegerField,
    IPAddressField,
    PositiveBigIntegerField,
    PositiveIntegerField,
    PositiveSmallIntegerField,
    SlugField,
    SmallIntegerField,
    TextField,
    TimeField,
    URLField,
)
from django.test import SimpleTestCase
from django.utils.functional import lazy


class PromiseTest(SimpleTestCase):
    def test_AutoField(self):
        """
        Tests the AutoField class to ensure it correctly handles lazy-loaded values.

        When an AutoField instance is created with primary_key=True, this test verifies
        that it can properly prepare its value for database storage by calling get_prep_value()
        on a lazy-loaded integer. The expected result is that the prepared value is an integer.

        This test case covers the interaction between AutoField and lazy-loaded values,
        ensuring that the AutoField can handle and process them as expected.
        """
        lazy_func = lazy(lambda: 1, int)
        self.assertIsInstance(
            AutoField(primary_key=True).get_prep_value(lazy_func()), int
        )

    def test_BinaryField(self):
        lazy_func = lazy(lambda: b"", bytes)
        self.assertIsInstance(BinaryField().get_prep_value(lazy_func()), bytes)

    def test_BooleanField(self):
        """
        Tests the behavior of the BooleanField when preparing a value for storage.

        The function verifies that the get_prep_value method of a BooleanField instance correctly
        handles a lazy boolean value and returns a boolean value as expected.

        This test ensures that the BooleanField behaves as expected when dealing with
        boolean values that are lazily evaluated, helping to prevent potential type errors
        in the application.
        """
        lazy_func = lazy(lambda: True, bool)
        self.assertIsInstance(BooleanField().get_prep_value(lazy_func()), bool)

    def test_CharField(self):
        """

        Tests the behavior of CharField's get_prep_value method when given lazy functions.

        This test ensures that when a CharField receives a lazy function as input, 
        it correctly prepares the value by evaluating the lazy function and returning 
        its result as a string, regardless of the original type of the value returned 
        by the lazy function.

        """
        lazy_func = lazy(lambda: "", str)
        self.assertIsInstance(CharField().get_prep_value(lazy_func()), str)
        lazy_func = lazy(lambda: 0, int)
        self.assertIsInstance(CharField().get_prep_value(lazy_func()), str)

    def test_DateField(self):
        lazy_func = lazy(lambda: datetime.date.today(), datetime.date)
        self.assertIsInstance(DateField().get_prep_value(lazy_func()), datetime.date)

    def test_DateTimeField(self):
        """
        Tests that DateTimeField correctly processes a lazy function returning the current date and time, 
        verifying the field's get_prep_value method returns an instance of datetime.datetime.
        """
        lazy_func = lazy(lambda: datetime.datetime.now(), datetime.datetime)
        self.assertIsInstance(
            DateTimeField().get_prep_value(lazy_func()), datetime.datetime
        )

    def test_DecimalField(self):
        """

        Tests the DecimalField to ensure it properly prepares a lazy decimal value.

        Verifies that a lazy function returning a decimal value is correctly prepared
        and returns an instance of the Decimal class.

        """
        lazy_func = lazy(lambda: Decimal("1.2"), Decimal)
        self.assertIsInstance(DecimalField().get_prep_value(lazy_func()), Decimal)

    def test_EmailField(self):
        """
        Tests the EmailField's get_prep_value method to ensure it correctly prepares an email address for storage.

            This test verifies that when a lazy function returning an email address is passed to get_prep_value, the method returns a string representation of the email address.

        """
        lazy_func = lazy(lambda: "mailbox@domain.com", str)
        self.assertIsInstance(EmailField().get_prep_value(lazy_func()), str)

    def test_FileField(self):
        """

        Tests the behavior of the FileField class's get_prep_value method.

        This test case verifies that the get_prep_value method correctly handles lazy functions 
        that return both string and integer values, ensuring that the output is always a string.

        The test covers two scenarios: 
        - When the lazy function returns a string value, 
        - When the lazy function returns an integer value.

        In both cases, the test checks if the result of get_prep_value is an instance of the string type. 

        """
        lazy_func = lazy(lambda: "filename.ext", str)
        self.assertIsInstance(FileField().get_prep_value(lazy_func()), str)
        lazy_func = lazy(lambda: 0, int)
        self.assertIsInstance(FileField().get_prep_value(lazy_func()), str)

    def test_FilePathField(self):
        lazy_func = lazy(lambda: "tests.py", str)
        self.assertIsInstance(FilePathField().get_prep_value(lazy_func()), str)
        lazy_func = lazy(lambda: 0, int)
        self.assertIsInstance(FilePathField().get_prep_value(lazy_func()), str)

    def test_FloatField(self):
        lazy_func = lazy(lambda: 1.2, float)
        self.assertIsInstance(FloatField().get_prep_value(lazy_func()), float)

    def test_ImageField(self):
        lazy_func = lazy(lambda: "filename.ext", str)
        self.assertIsInstance(ImageField().get_prep_value(lazy_func()), str)

    def test_IntegerField(self):
        """

        Tests the IntegerField to ensure it correctly prepares and returns an integer value.

        Verifies that the get_prep_value method of IntegerField can handle lazy values and 
        returns an instance of int, as expected.

        This test is crucial for validating the data type consistency and integrity of integer fields 
        in the application, ensuring they behave as expected when working with lazy evaluations.

        """
        lazy_func = lazy(lambda: 1, int)
        self.assertIsInstance(IntegerField().get_prep_value(lazy_func()), int)

    def test_IPAddressField(self):
        """
        Tests the IPAddressField by verifying its get_prep_value method returns a string 
        for both string and integer input values. This ensures that the IPAddressField 
        consistently processes input data and outputs it in a string format, 
        regardless of the original data type.
        """
        lazy_func = lazy(lambda: "127.0.0.1", str)
        self.assertIsInstance(IPAddressField().get_prep_value(lazy_func()), str)
        lazy_func = lazy(lambda: 0, int)
        self.assertIsInstance(IPAddressField().get_prep_value(lazy_func()), str)

    def test_GenericIPAddressField(self):
        """
        Tests the GenericIPAddressField to ensure it correctly prepares IP address values.

        The test verifies that the get_prep_value method of the GenericIPAddressField returns a string
        representation of the IP address, regardless of the input type. It checks the functionality with
        both string and integer inputs, ensuring the output is consistently a string.

        This test case is crucial to guarantee the robustness and type consistency of the GenericIPAddressField,
        which is essential for reliable network address handling in various applications.
        """
        lazy_func = lazy(lambda: "127.0.0.1", str)
        self.assertIsInstance(GenericIPAddressField().get_prep_value(lazy_func()), str)
        lazy_func = lazy(lambda: 0, int)
        self.assertIsInstance(GenericIPAddressField().get_prep_value(lazy_func()), str)

    def test_PositiveIntegerField(self):
        """
        Tests the PositiveIntegerField class to ensure it correctly prepares a lazy integer value for database storage.

        Checks that the get_prep_value method returns an integer value when given a lazy function that evaluates to a positive integer.

        The purpose of this test is to verify the field's ability to handle lazy values and ensure they are properly converted to the expected data type before being stored in the database.
        """
        lazy_func = lazy(lambda: 1, int)
        self.assertIsInstance(PositiveIntegerField().get_prep_value(lazy_func()), int)

    def test_PositiveSmallIntegerField(self):
        lazy_func = lazy(lambda: 1, int)
        self.assertIsInstance(
            PositiveSmallIntegerField().get_prep_value(lazy_func()), int
        )

    def test_PositiveBigIntegerField(self):
        """
        Tests the PositiveBigIntegerField to ensure it correctly prepares a lazy integer function for storage by verifying the output is an integer. 

        This method checks the functionality of the PositiveBigIntegerField's get_prep_value method when given a lazy function that returns an integer value, confirming that the result is of the expected integer type.
        """
        lazy_func = lazy(lambda: 1, int)
        self.assertIsInstance(
            PositiveBigIntegerField().get_prep_value(lazy_func()), int
        )

    def test_SlugField(self):
        lazy_func = lazy(lambda: "slug", str)
        self.assertIsInstance(SlugField().get_prep_value(lazy_func()), str)
        lazy_func = lazy(lambda: 0, int)
        self.assertIsInstance(SlugField().get_prep_value(lazy_func()), str)

    def test_SmallIntegerField(self):
        """
        Tests the SmallIntegerField's get_prep_value method with a lazily evaluated integer value.

        This test case checks if the SmallIntegerField is able to correctly process a value 
        that is evaluated lazily and returns it as an integer. This ensures that the field 
        can handle values generated by lazy functions and processes them as expected.
        """
        lazy_func = lazy(lambda: 1, int)
        self.assertIsInstance(SmallIntegerField().get_prep_value(lazy_func()), int)

    def test_TextField(self):
        """

        Test the TextField class's get_prep_value method.

        This method tests that the TextField class correctly prepares values for storage.
        It checks that the get_prep_value method returns a string object regardless of the input type.
        The test uses lazy functions to provide values of different types to the get_prep_value method.

        """
        lazy_func = lazy(lambda: "Abc", str)
        self.assertIsInstance(TextField().get_prep_value(lazy_func()), str)
        lazy_func = lazy(lambda: 0, int)
        self.assertIsInstance(TextField().get_prep_value(lazy_func()), str)

    def test_TimeField(self):
        lazy_func = lazy(lambda: datetime.datetime.now().time(), datetime.time)
        self.assertIsInstance(TimeField().get_prep_value(lazy_func()), datetime.time)

    def test_URLField(self):
        lazy_func = lazy(lambda: "http://domain.com", str)
        self.assertIsInstance(URLField().get_prep_value(lazy_func()), str)
