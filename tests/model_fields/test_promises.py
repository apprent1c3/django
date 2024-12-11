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

        Test the AutoField class with a lazy function value.

        This test case verifies that an AutoField instance with primary_key set to True
        correctly prepares the lazy function value and returns an integer result.

        """
        lazy_func = lazy(lambda: 1, int)
        self.assertIsInstance(
            AutoField(primary_key=True).get_prep_value(lazy_func()), int
        )

    def test_BinaryField(self):
        """
        Tests that the BinaryField correctly prepares a binary value for storage.

        The test verifies that when a BinaryField instance is provided with a lazy function
        that returns empty bytes, the `get_prep_value` method returns a bytes object.
        This ensures that the BinaryField properly handles binary data and prepares it
        according to the expected format for storage.

        The test case covers the scenario where an empty bytes object is returned by the
        lazy function, ensuring that the BinaryField behaves as expected in this edge case.
        """
        lazy_func = lazy(lambda: b"", bytes)
        self.assertIsInstance(BinaryField().get_prep_value(lazy_func()), bytes)

    def test_BooleanField(self):
        """
        Tests the BooleanField's get_prep_value method with a lazy function.

        Checks that the method returns a boolean value when given a lazy function
        that evaluates to a boolean. This ensures proper handling of dynamically
        computed boolean values, validating that the output is of the correct data type.

        The purpose of this test is to verify the correct functionality of the BooleanField
        in retrieving and processing boolean values under different scenarios, including
        the use of lazy functions, thus ensuring robustness and reliability in data processing.
        """
        lazy_func = lazy(lambda: True, bool)
        self.assertIsInstance(BooleanField().get_prep_value(lazy_func()), bool)

    def test_CharField(self):
        lazy_func = lazy(lambda: "", str)
        self.assertIsInstance(CharField().get_prep_value(lazy_func()), str)
        lazy_func = lazy(lambda: 0, int)
        self.assertIsInstance(CharField().get_prep_value(lazy_func()), str)

    def test_DateField(self):
        """

        Tests the functionality of the DateField class with a lazy-loaded value.

        Verifies that when a lazy-loaded function returning the current date is passed to the 
        get_prep_value method, the returned value is an instance of datetime.date.

        """
        lazy_func = lazy(lambda: datetime.date.today(), datetime.date)
        self.assertIsInstance(DateField().get_prep_value(lazy_func()), datetime.date)

    def test_DateTimeField(self):
        """
        Tests the DateTimeField's get_prep_value method by checking if it correctly handles a lazily loaded datetime value, 
        verifying that the returned value is of the expected datetime.datetime type.
        """
        lazy_func = lazy(lambda: datetime.datetime.now(), datetime.datetime)
        self.assertIsInstance(
            DateTimeField().get_prep_value(lazy_func()), datetime.datetime
        )

    def test_DecimalField(self):
        """

        Tests the get_prep_value method of the DecimalField class.

        This test verifies that the get_prep_value method correctly prepares a lazy Decimal value for use in a database query.
        It checks that the prepared value is an instance of the Decimal class, ensuring that it can be properly handled by the database.

        """
        lazy_func = lazy(lambda: Decimal("1.2"), Decimal)
        self.assertIsInstance(DecimalField().get_prep_value(lazy_func()), Decimal)

    def test_EmailField(self):
        lazy_func = lazy(lambda: "mailbox@domain.com", str)
        self.assertIsInstance(EmailField().get_prep_value(lazy_func()), str)

    def test_FileField(self):
        """
        Tests the behavior of the FileField class, specifically its get_prep_value method.

        This method is expected to return a string value, regardless of the input type.
        It is tested with lazy functions that return a string and an integer, verifying
        that the output is always a string. This ensures the correct preparation of file
        field values for storage or further processing, handling different input types
        gracefully by consistently returning a string representation.
        """
        lazy_func = lazy(lambda: "filename.ext", str)
        self.assertIsInstance(FileField().get_prep_value(lazy_func()), str)
        lazy_func = lazy(lambda: 0, int)
        self.assertIsInstance(FileField().get_prep_value(lazy_func()), str)

    def test_FilePathField(self):
        """
        Tests the FilePathField's ability to handle lazy functions of different types by checking if the get_prep_value method returns a string. The test covers scenarios where the lazy function returns a string and an integer, verifying that the output is consistently a string in both cases.
        """
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

        Tests the IntegerField class to ensure it correctly prepares integer values.

        This test verifies that the get_prep_value method of an IntegerField instance
        returns an integer when given a lazy-loaded integer value. The purpose of this
        test is to guarantee that the IntegerField class properly handles lazy-loaded
        integer values, which is crucial for maintaining data integrity and preventing
        potential errors in the application.

        """
        lazy_func = lazy(lambda: 1, int)
        self.assertIsInstance(IntegerField().get_prep_value(lazy_func()), int)

    def test_IPAddressField(self):
        lazy_func = lazy(lambda: "127.0.0.1", str)
        self.assertIsInstance(IPAddressField().get_prep_value(lazy_func()), str)
        lazy_func = lazy(lambda: 0, int)
        self.assertIsInstance(IPAddressField().get_prep_value(lazy_func()), str)

    def test_GenericIPAddressField(self):
        """
        Tests the GenericIPAddressField's get_prep_value method with lazy functions.

        This test case verifies that the get_prep_value method of GenericIPAddressField returns a string 
        value when given a lazy function that evaluates to a string or an integer, as expected. The 
        function is tested with two different lazy functions: one that returns an IPv4 address as a string 
        and another that returns an integer value. 

        It ensures that the method correctly handles these inputs and returns the result in the desired 
        string format, which is essential for proper IP address processing and validation.
        """
        lazy_func = lazy(lambda: "127.0.0.1", str)
        self.assertIsInstance(GenericIPAddressField().get_prep_value(lazy_func()), str)
        lazy_func = lazy(lambda: 0, int)
        self.assertIsInstance(GenericIPAddressField().get_prep_value(lazy_func()), str)

    def test_PositiveIntegerField(self):
        """
        Tests the behavior of PositiveIntegerField when handling lazy functions.

        This test ensures that the get_prep_value method of PositiveIntegerField correctly
        evaluates a lazy function and returns the result as an integer.

        The test uses a lazy function that returns the integer value 1, and verifies
        that the result of get_prep_value is an instance of int, confirming the expected
        data type conversion.

        This test case is important to guarantee the proper interaction between
        PositiveIntegerField and lazy functions, which can be used to delay the evaluation
        of expressions until their values are actually needed.
        """
        lazy_func = lazy(lambda: 1, int)
        self.assertIsInstance(PositiveIntegerField().get_prep_value(lazy_func()), int)

    def test_PositiveSmallIntegerField(self):
        lazy_func = lazy(lambda: 1, int)
        self.assertIsInstance(
            PositiveSmallIntegerField().get_prep_value(lazy_func()), int
        )

    def test_PositiveBigIntegerField(self):
        lazy_func = lazy(lambda: 1, int)
        self.assertIsInstance(
            PositiveBigIntegerField().get_prep_value(lazy_func()), int
        )

    def test_SlugField(self):
        """
        Tests the SlugField's get_prep_value method to ensure it correctly handles lazy functions.

        The test verifies that the method returns a string value, regardless of the type of the input value.
        It checks the functionality with both string and integer inputs, to ensure robust handling of different data types.

        This test is crucial in validating the field's ability to prepare values for database storage, 
        in a way that is consistent and compatible with the expected string data type of a slug field.
        """
        lazy_func = lazy(lambda: "slug", str)
        self.assertIsInstance(SlugField().get_prep_value(lazy_func()), str)
        lazy_func = lazy(lambda: 0, int)
        self.assertIsInstance(SlugField().get_prep_value(lazy_func()), str)

    def test_SmallIntegerField(self):
        lazy_func = lazy(lambda: 1, int)
        self.assertIsInstance(SmallIntegerField().get_prep_value(lazy_func()), int)

    def test_TextField(self):
        lazy_func = lazy(lambda: "Abc", str)
        self.assertIsInstance(TextField().get_prep_value(lazy_func()), str)
        lazy_func = lazy(lambda: 0, int)
        self.assertIsInstance(TextField().get_prep_value(lazy_func()), str)

    def test_TimeField(self):
        """
        Tests the TimeField by verifying it correctly prepares a lazy datetime time value.

        The test uses a lazy function to generate the current time and checks if the get_prep_value method of the TimeField instance returns a datetime.time object.

        """
        lazy_func = lazy(lambda: datetime.datetime.now().time(), datetime.time)
        self.assertIsInstance(TimeField().get_prep_value(lazy_func()), datetime.time)

    def test_URLField(self):
        lazy_func = lazy(lambda: "http://domain.com", str)
        self.assertIsInstance(URLField().get_prep_value(lazy_func()), str)
