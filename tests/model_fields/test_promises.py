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
        lazy_func = lazy(lambda: b"", bytes)
        self.assertIsInstance(BinaryField().get_prep_value(lazy_func()), bytes)

    def test_BooleanField(self):
        lazy_func = lazy(lambda: True, bool)
        self.assertIsInstance(BooleanField().get_prep_value(lazy_func()), bool)

    def test_CharField(self):
        lazy_func = lazy(lambda: "", str)
        self.assertIsInstance(CharField().get_prep_value(lazy_func()), str)
        lazy_func = lazy(lambda: 0, int)
        self.assertIsInstance(CharField().get_prep_value(lazy_func()), str)

    def test_DateField(self):
        lazy_func = lazy(lambda: datetime.date.today(), datetime.date)
        self.assertIsInstance(DateField().get_prep_value(lazy_func()), datetime.date)

    def test_DateTimeField(self):
        lazy_func = lazy(lambda: datetime.datetime.now(), datetime.datetime)
        self.assertIsInstance(
            DateTimeField().get_prep_value(lazy_func()), datetime.datetime
        )

    def test_DecimalField(self):
        lazy_func = lazy(lambda: Decimal("1.2"), Decimal)
        self.assertIsInstance(DecimalField().get_prep_value(lazy_func()), Decimal)

    def test_EmailField(self):
        """

        Tests the functionality of the EmailField class.

        Verifies that the get_prep_value method of EmailField returns a string value 
        when given a lazy function that evaluates to an email address.

        The purpose of this test is to ensure that the EmailField class correctly 
        handles lazy functions and returns a string as expected.

        """
        lazy_func = lazy(lambda: "mailbox@domain.com", str)
        self.assertIsInstance(EmailField().get_prep_value(lazy_func()), str)

    def test_FileField(self):
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
        """
        Tests the ImageField class to ensure it correctly prepares a lazy function value for database storage.

        The test verifies that the get_prep_value method of ImageField returns a string when given a lazy function that evaluates to a filename.

        This test case ensures that ImageField handles lazy functions as expected, allowing for delayed evaluation of the filename until it is actually needed for database storage.
        """
        lazy_func = lazy(lambda: "filename.ext", str)
        self.assertIsInstance(ImageField().get_prep_value(lazy_func()), str)

    def test_IntegerField(self):
        """
        Tests the IntegerField's get_prep_value method with a lazy function.

        This test case verifies that the IntegerField can properly prepare the value 
        returned by a lazy function, which evaluates to an integer, for further processing.
        It checks that the prepared value is an instance of the int type, ensuring its 
        correctness for subsequent operations.
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
        lazy_func = lazy(lambda: "slug", str)
        self.assertIsInstance(SlugField().get_prep_value(lazy_func()), str)
        lazy_func = lazy(lambda: 0, int)
        self.assertIsInstance(SlugField().get_prep_value(lazy_func()), str)

    def test_SmallIntegerField(self):
        lazy_func = lazy(lambda: 1, int)
        self.assertIsInstance(SmallIntegerField().get_prep_value(lazy_func()), int)

    def test_TextField(self):
        """

        Tests the get_prep_value method of the TextField class.

        This method is used to prepare the value for storage. The test checks if the 
        get_prep_value method correctly converts lazy loaded values of different 
        data types (string and integer) into strings.

        The test uses a lazy function that returns a value when called, simulating 
        a lazy loaded value. It then asserts that the result of 
        get_prep_value is a string, regardless of the type of the lazy loaded value.

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
