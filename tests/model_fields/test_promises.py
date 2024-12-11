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
        lazy_func = lazy(lambda: 1, int)
        self.assertIsInstance(
            AutoField(primary_key=True).get_prep_value(lazy_func()), int
        )

    def test_BinaryField(self):
        """
        Tests the BinaryField class to ensure it properly handles binary data.

        Checks that the get_prep_value method of BinaryField returns a bytes object when 
        given a lazy function that evaluates to a bytes object, verifying correct 
        preparation of binary data for storage or processing.

        Note: This test is part of a larger suite to validate the functionality of 
        BinaryField in handling binary data. If the test passes, it confirms that 
        BinaryField behaves as expected with lazy-loaded binary data.
        """
        lazy_func = lazy(lambda: b"", bytes)
        self.assertIsInstance(BinaryField().get_prep_value(lazy_func()), bytes)

    def test_BooleanField(self):
        lazy_func = lazy(lambda: True, bool)
        self.assertIsInstance(BooleanField().get_prep_value(lazy_func()), bool)

    def test_CharField(self):
        """
        Tests that the CharField's get_prep_value method correctly prepares values for database storage.

        This method is essential for ensuring that values are properly converted to strings, 
        regardless of their original data type, to prevent potential database errors.

        It verifies that both string and non-string values are handled correctly, 
        resulting in a string output that can be safely stored in the database.
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
        Tests the DateTimeField's get_prep_value method to verify it returns a datetime object when given a lazy function that evaluates to the current datetime.
        """
        lazy_func = lazy(lambda: datetime.datetime.now(), datetime.datetime)
        self.assertIsInstance(
            DateTimeField().get_prep_value(lazy_func()), datetime.datetime
        )

    def test_DecimalField(self):
        """
        Tests the get_prep_value method of the DecimalField class.

        Verifies that the get_prep_value method correctly prepares a lazy decimal value for use.
        The test checks that the method returns an instance of the Decimal class when given a lazy function that loads a decimal value.

        This ensures that DecimalField properly handles lazy decimal values and returns the expected data type.
        """
        lazy_func = lazy(lambda: Decimal("1.2"), Decimal)
        self.assertIsInstance(DecimalField().get_prep_value(lazy_func()), Decimal)

    def test_EmailField(self):
        """

        Tests the EmailField's get_prep_value method to ensure it correctly handles lazy evaluation.

        This test checks that when a lazy function is passed to the get_prep_value method,
        it returns a string value as expected, verifying the compatibility of EmailField with lazy objects.

        """
        lazy_func = lazy(lambda: "mailbox@domain.com", str)
        self.assertIsInstance(EmailField().get_prep_value(lazy_func()), str)

    def test_FileField(self):
        lazy_func = lazy(lambda: "filename.ext", str)
        self.assertIsInstance(FileField().get_prep_value(lazy_func()), str)
        lazy_func = lazy(lambda: 0, int)
        self.assertIsInstance(FileField().get_prep_value(lazy_func()), str)

    def test_FilePathField(self):
        """
        Tests the FilePathField by verifying its get_prep_value method.

        The FilePathField is expected to return a string value regardless of the input type.
        This test checks the get_prep_value method with lazy functions that evaluate to a
        string and an integer, ensuring that the output is always a string.

        The test covers two main scenarios:
        1. When the input is a string, the get_prep_value method should return the same string.
        2. When the input is a non-string type (e.g., integer), the get_prep_value method should
           still return a string, effectively handling type conversions.

        By verifying these cases, this test ensures the FilePathField behaves as expected and
        can handle various input types, providing a robust way to work with file paths in the application.
        """
        lazy_func = lazy(lambda: "tests.py", str)
        self.assertIsInstance(FilePathField().get_prep_value(lazy_func()), str)
        lazy_func = lazy(lambda: 0, int)
        self.assertIsInstance(FilePathField().get_prep_value(lazy_func()), str)

    def test_FloatField(self):
        lazy_func = lazy(lambda: 1.2, float)
        self.assertIsInstance(FloatField().get_prep_value(lazy_func()), float)

    def test_ImageField(self):
        """
        Tests the ImageField's get_prep_value method with a lazy function.

        Verifies that when a lazy function is passed to get_prep_value, it returns a string 
        value, ensuring that the field's value is properly prepared for database storage.

        The test checks the instance type of the returned value, confirming that it is a 
        string as expected. This gives confidence that the ImageField handles lazy 
        functions correctly, facilitating the use of dynamic or delayed evaluation of 
        image file names or paths.
        """
        lazy_func = lazy(lambda: "filename.ext", str)
        self.assertIsInstance(ImageField().get_prep_value(lazy_func()), str)

    def test_IntegerField(self):
        """

         Tests that the IntegerField correctly prepares a lazy integer value.

         Verifies that the get_prep_value method of an IntegerField instance 
         returns an integer when given a lazy function that evaluates to an integer.

        """
        lazy_func = lazy(lambda: 1, int)
        self.assertIsInstance(IntegerField().get_prep_value(lazy_func()), int)

    def test_IPAddressField(self):
        lazy_func = lazy(lambda: "127.0.0.1", str)
        self.assertIsInstance(IPAddressField().get_prep_value(lazy_func()), str)
        lazy_func = lazy(lambda: 0, int)
        self.assertIsInstance(IPAddressField().get_prep_value(lazy_func()), str)

    def test_GenericIPAddressField(self):
        lazy_func = lazy(lambda: "127.0.0.1", str)
        self.assertIsInstance(GenericIPAddressField().get_prep_value(lazy_func()), str)
        lazy_func = lazy(lambda: 0, int)
        self.assertIsInstance(GenericIPAddressField().get_prep_value(lazy_func()), str)

    def test_PositiveIntegerField(self):
        """
        Tests the functionality of PositiveIntegerField to ensure it correctly handles lazy integer values.

            Verifies that the get_prep_value method of PositiveIntegerField returns an integer value when given a lazy function
            that evaluates to a positive integer. This test case is crucial for ensuring data integrity and correct type handling
            in database interactions involving PositiveIntegerField instances.
        """
        lazy_func = lazy(lambda: 1, int)
        self.assertIsInstance(PositiveIntegerField().get_prep_value(lazy_func()), int)

    def test_PositiveSmallIntegerField(self):
        """

        Tests the PositiveSmallIntegerField class to ensure it correctly prepares a value for database storage.

        The test verifies that a lazy function returning a small positive integer value is properly converted to an integer type when passed through the get_prep_value method.

        This ensures that the field handles lazy loaded values correctly and returns the expected data type.

        """
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
        Tests the SlugField's get_prep_value method to ensure it correctly converts input values to strings, 
        regardless of whether the input is a string, integer or a callable that returns a string or integer. 
        The test verifies that the output is always a string, as expected by the SlugField.
        """
        lazy_func = lazy(lambda: "slug", str)
        self.assertIsInstance(SlugField().get_prep_value(lazy_func()), str)
        lazy_func = lazy(lambda: 0, int)
        self.assertIsInstance(SlugField().get_prep_value(lazy_func()), str)

    def test_SmallIntegerField(self):
        """

        Tests the preparation of a SmallIntegerField value.

        Verifies that the get_prep_value method of a SmallIntegerField instance correctly
        prepares a lazily evaluated integer value, returning an integer.

        """
        lazy_func = lazy(lambda: 1, int)
        self.assertIsInstance(SmallIntegerField().get_prep_value(lazy_func()), int)

    def test_TextField(self):
        lazy_func = lazy(lambda: "Abc", str)
        self.assertIsInstance(TextField().get_prep_value(lazy_func()), str)
        lazy_func = lazy(lambda: 0, int)
        self.assertIsInstance(TextField().get_prep_value(lazy_func()), str)

    def test_TimeField(self):
        """
        Tests the functionality of the TimeField class to ensure it properly prepares a time value by verifying that the get_prep_value method returns a datetime.time object when given a lazy time value.
        """
        lazy_func = lazy(lambda: datetime.datetime.now().time(), datetime.time)
        self.assertIsInstance(TimeField().get_prep_value(lazy_func()), datetime.time)

    def test_URLField(self):
        """

        Tests the URLField's get_prep_value method to ensure it correctly prepares a URL value for storage.

        The test checks that when a lazy function returning a URL string is passed to get_prep_value,
        the method returns a string instance, indicating successful preparation of the URL for storage.

        """
        lazy_func = lazy(lambda: "http://domain.com", str)
        self.assertIsInstance(URLField().get_prep_value(lazy_func()), str)
