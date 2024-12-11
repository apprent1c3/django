from django.core.exceptions import ValidationError
from django.db import models
from django.test import TestCase

from .models import DataModel


class BinaryFieldTests(TestCase):
    binary_data = b"\x00\x46\xFE"

    def test_set_and_retrieve(self):
        """
        Test that setting and retrieving binary data via the DataModel class works correctly.

        The test checks the functionality with different binary data types, including bytes, bytearray, and memoryview.

        It verifies that after saving and retrieving the data, the original and retrieved data match. This test is performed twice to ensure that the data remains consistent after multiple save operations. Additionally, it checks that the short_data attribute is correctly set to a specific byte value.
        """
        data_set = (
            self.binary_data,
            bytearray(self.binary_data),
            memoryview(self.binary_data),
        )
        for bdata in data_set:
            with self.subTest(data=repr(bdata)):
                dm = DataModel(data=bdata)
                dm.save()
                dm = DataModel.objects.get(pk=dm.pk)
                self.assertEqual(bytes(dm.data), bytes(bdata))
                # Resave (=update)
                dm.save()
                dm = DataModel.objects.get(pk=dm.pk)
                self.assertEqual(bytes(dm.data), bytes(bdata))
                # Test default value
                self.assertEqual(bytes(dm.short_data), b"\x08")

    def test_max_length(self):
        dm = DataModel(short_data=self.binary_data * 4)
        with self.assertRaises(ValidationError):
            dm.full_clean()

    def test_editable(self):
        """
        Tests the editable attribute of a BinaryField, verifying that it is correctly set to False by default and can be explicitly set to True or False through the editable parameter.
        """
        field = models.BinaryField()
        self.assertIs(field.editable, False)
        field = models.BinaryField(editable=True)
        self.assertIs(field.editable, True)
        field = models.BinaryField(editable=False)
        self.assertIs(field.editable, False)

    def test_filter(self):
        """
        Tests the filter functionality of the DataModel class.

        This test ensures that filtering by binary data yields the correct results,
        specifically that it returns the expected object when the data matches and
        ignores objects with different data. 

        The test creates a DataModel object with specific binary data, then creates
        another object with different data to verify that the filter does not return
        unintended results. It then asserts that filtering by the original binary data
        returns the correct object.

        :raises: AssertionError if the filter does not return the expected object
        """
        dm = DataModel.objects.create(data=self.binary_data)
        DataModel.objects.create(data=b"\xef\xbb\xbf")
        self.assertSequenceEqual(DataModel.objects.filter(data=self.binary_data), [dm])

    def test_filter_bytearray(self):
        """
        Tests filtering DataModel instances by bytearray data.

        Verifies that DataModel objects can be correctly filtered based on their bytearray data,
        ensuring that only objects with matching data are returned, and others are excluded.

        This test case covers the scenario where multiple DataModel objects exist with different data,
        and the filtering operation should return only the object with the specified bytearray data.
        """
        dm = DataModel.objects.create(data=self.binary_data)
        DataModel.objects.create(data=b"\xef\xbb\xbf")
        self.assertSequenceEqual(
            DataModel.objects.filter(data=bytearray(self.binary_data)), [dm]
        )

    def test_filter_memoryview(self):
        """
        Tests filtering of DataModel objects by memoryview of binary data.

        This test ensures that a DataModel object can be successfully retrieved from the database
        by filtering using a memoryview of its binary data. The test verifies that only the 
        corresponding object is returned, even when multiple objects exist in the database with 
        different binary data.

        The test case creates two DataModel objects, one with binary data and another with a 
        distinct binary value. It then asserts that filtering by a memoryview of the original 
        binary data returns only the original DataModel object.
        """
        dm = DataModel.objects.create(data=self.binary_data)
        DataModel.objects.create(data=b"\xef\xbb\xbf")
        self.assertSequenceEqual(
            DataModel.objects.filter(data=memoryview(self.binary_data)), [dm]
        )
