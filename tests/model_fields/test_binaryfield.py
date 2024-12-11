from django.core.exceptions import ValidationError
from django.db import models
from django.test import TestCase

from .models import DataModel


class BinaryFieldTests(TestCase):
    binary_data = b"\x00\x46\xFE"

    def test_set_and_retrieve(self):
        """
        Tests the setting and retrieval of binary data through the DataModel.

        This test case checks that binary data can be successfully saved and loaded from the database,
        regardless of whether it's provided as bytes, bytearray, or memoryview. The test also verifies
        that data is correctly saved twice in succession and that a secondary data attribute, short_data,
        always contains the expected bytes value after data has been saved and loaded.
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
        Tests whether the editable property of a BinaryField is correctly set based on its initialization parameters. 

        The test covers different scenarios, including the default case where editable is not explicitly specified, and cases where editable is explicitly set to True or False, 
        verifying that the field's editable attribute reflects the expected value.
        """
        field = models.BinaryField()
        self.assertIs(field.editable, False)
        field = models.BinaryField(editable=True)
        self.assertIs(field.editable, True)
        field = models.BinaryField(editable=False)
        self.assertIs(field.editable, False)

    def test_filter(self):
        """

        Tests the filtering functionality of DataModel objects based on binary data.

        This test case verifies that the filter method correctly retrieves DataModel
        instances with matching binary data, while ignoring instances with
        different data, such as a byte order mark (BOM).

        """
        dm = DataModel.objects.create(data=self.binary_data)
        DataModel.objects.create(data=b"\xef\xbb\xbf")
        self.assertSequenceEqual(DataModel.objects.filter(data=self.binary_data), [dm])

    def test_filter_bytearray(self):
        """

        Tests that the filter method correctly matches byte arrays.

        This test case verifies that the DataModel filter method accurately
        identifies objects based on bytearray matches. It creates a DataModel
        instance with a given bytearray and another with a distinct bytearray,
        then checks that filtering by the original bytearray returns the
        expected instance.

        The test covers the case where a bytearray is used as the filter
        criterion, confirming that the method distinguishes between identical
        and disparate byte arrays.

        :returns: None

        """
        dm = DataModel.objects.create(data=self.binary_data)
        DataModel.objects.create(data=b"\xef\xbb\xbf")
        self.assertSequenceEqual(
            DataModel.objects.filter(data=bytearray(self.binary_data)), [dm]
        )

    def test_filter_memoryview(self):
        """

        Tests the filtering of DataModel instances based on binary data using a memory view.

        Verifies that a DataModel instance can be correctly filtered from the database
        when its binary data is matched with a memory view of the same data.

        """
        dm = DataModel.objects.create(data=self.binary_data)
        DataModel.objects.create(data=b"\xef\xbb\xbf")
        self.assertSequenceEqual(
            DataModel.objects.filter(data=memoryview(self.binary_data)), [dm]
        )
