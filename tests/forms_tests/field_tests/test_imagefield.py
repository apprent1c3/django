import os
import unittest

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile, TemporaryUploadedFile
from django.forms import ClearableFileInput, FileInput, ImageField, Widget
from django.test import SimpleTestCase

from . import FormFieldAssertionsMixin

try:
    from PIL import Image
except ImportError:
    Image = None


def get_img_path(path):
    return os.path.join(
        os.path.abspath(os.path.join(__file__, "..", "..")), "tests", path
    )


@unittest.skipUnless(Image, "Pillow is required to test ImageField")
class ImageFieldTest(FormFieldAssertionsMixin, SimpleTestCase):
    def test_imagefield_annotate_with_image_after_clean(self):
        f = ImageField()

        img_path = get_img_path("filepath_test_files/1x1.png")
        with open(img_path, "rb") as img_file:
            img_data = img_file.read()

        img_file = SimpleUploadedFile("1x1.png", img_data)
        img_file.content_type = "text/plain"

        uploaded_file = f.clean(img_file)

        self.assertEqual("PNG", uploaded_file.image.format)
        self.assertEqual("image/png", uploaded_file.content_type)

    def test_imagefield_annotate_with_bitmap_image_after_clean(self):
        """
        This also tests the situation when Pillow doesn't detect the MIME type
        of the image (#24948).
        """
        from PIL.BmpImagePlugin import BmpImageFile

        try:
            Image.register_mime(BmpImageFile.format, None)
            f = ImageField()
            img_path = get_img_path("filepath_test_files/1x1.bmp")
            with open(img_path, "rb") as img_file:
                img_data = img_file.read()

            img_file = SimpleUploadedFile("1x1.bmp", img_data)
            img_file.content_type = "text/plain"

            uploaded_file = f.clean(img_file)

            self.assertEqual("BMP", uploaded_file.image.format)
            self.assertIsNone(uploaded_file.content_type)
        finally:
            Image.register_mime(BmpImageFile.format, "image/bmp")

    def test_file_extension_validation(self):
        f = ImageField()
        img_path = get_img_path("filepath_test_files/1x1.png")
        with open(img_path, "rb") as img_file:
            img_data = img_file.read()
        img_file = SimpleUploadedFile("1x1.txt", img_data)
        with self.assertRaisesMessage(
            ValidationError, "File extension “txt” is not allowed."
        ):
            f.clean(img_file)

    def test_corrupted_image(self):
        """
        Tests the functionality of an ImageField when dealing with corrupted or invalid image files.

        Checks that attempting to clean an invalid image file (either a non-image file 
        or a corrupted image file) raises a ValidationError with a descriptive error message.

        The test covers both permanent and temporary uploaded files, ensuring that the 
        ImageField's validation behaves correctly in all scenarios.
        """
        f = ImageField()
        img_file = SimpleUploadedFile("not_an_image.jpg", b"not an image")
        msg = (
            "Upload a valid image. The file you uploaded was either not an "
            "image or a corrupted image."
        )
        with self.assertRaisesMessage(ValidationError, msg):
            f.clean(img_file)
        with TemporaryUploadedFile(
            "not_an_image_tmp.png", "text/plain", 1, "utf-8"
        ) as tmp_file:
            with self.assertRaisesMessage(ValidationError, msg):
                f.clean(tmp_file)

    def test_widget_attrs_default_accept(self):
        """

        Tests the default widget attributes for an ImageField.

        This test verifies that the ImageField returns the correct widget attributes for different types of widgets.
        It checks that the widget attributes are empty for a basic Widget, and that the 'accept' attribute is set to 'image/*' 
        for FileInput and ClearableFileInput widgets, which ensures that only image files can be selected.

        The test also verifies that the ImageField renders to the correct HTML input field with the 'accept' attribute.

        """
        f = ImageField()
        # Nothing added for non-FileInput widgets.
        self.assertEqual(f.widget_attrs(Widget()), {})
        self.assertEqual(f.widget_attrs(FileInput()), {"accept": "image/*"})
        self.assertEqual(f.widget_attrs(ClearableFileInput()), {"accept": "image/*"})
        self.assertWidgetRendersTo(
            f, '<input type="file" name="f" accept="image/*" required id="id_f" />'
        )

    def test_widget_attrs_accept_specified(self):
        """
        Tests that the widget_attrs method correctly handles specified attributes for a FileInput widget in an ImageField, 
        ensuring the 'accept' attribute is properly rendered in the HTML output when an ImageField is created with a 
        FileInput widget that has an 'accept' attribute specified. The test verifies the widget's attributes are correctly 
        applied, specifically for accepting a specific image file type (e.g., 'image/png'), without affecting other 
        attributes in the widget.
        """
        f = ImageField(widget=FileInput(attrs={"accept": "image/png"}))
        self.assertEqual(f.widget_attrs(f.widget), {})
        self.assertWidgetRendersTo(
            f, '<input type="file" name="f" accept="image/png" required id="id_f" />'
        )

    def test_widget_attrs_accept_false(self):
        """

        Verify that a FileInput widget correctly handles 'accept' attribute set to False.

        This test case checks that when the 'accept' attribute is explicitly set to False
        in the widget's attributes, the resulting widget attributes are empty and the
        widget is rendered without the 'accept' attribute.

        Checks the rendered HTML output of the FileInput widget to ensure it matches
        the expected format, excluding the 'accept' attribute.

        """
        f = ImageField(widget=FileInput(attrs={"accept": False}))
        self.assertEqual(f.widget_attrs(f.widget), {})
        self.assertWidgetRendersTo(
            f, '<input type="file" name="f" required id="id_f" />'
        )
