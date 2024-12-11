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
        """

        Tests that an ImageField correctly annotates an uploaded image after cleaning.

        This test verifies that when a non-image content type is provided for an uploaded image,
        the ImageField still correctly identifies and annotates the image format and content type.
        The test specifically checks that the image format and content type are properly updated
        after the cleaning process, ensuring that the image is handled correctly despite the mismatched content type.

        """
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

        Tests that the ImageField instance returns the correct widget attributes.

        Verifies that when using the default widget, an empty dictionary is returned.
        For FileInput and ClearableFileInput widgets, checks that the 'accept' attribute
        is set to 'image/*', which specifies that only image files should be accepted.
        Also ensures that the rendered HTML widget includes the 'accept' attribute and
        other expected properties.

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
        f = ImageField(widget=FileInput(attrs={"accept": "image/png"}))
        self.assertEqual(f.widget_attrs(f.widget), {})
        self.assertWidgetRendersTo(
            f, '<input type="file" name="f" accept="image/png" required id="id_f" />'
        )

    def test_widget_attrs_accept_false(self):
        """
        Tests that the 'accept' attribute is not included in the widget attributes when set to False.

        The purpose of this test is to ensure that the widget attributes for a file input field
        are correctly generated when the 'accept' attribute is explicitly set to False.
        It verifies that no 'accept' attribute is present in the rendered HTML.
        """
        f = ImageField(widget=FileInput(attrs={"accept": False}))
        self.assertEqual(f.widget_attrs(f.widget), {})
        self.assertWidgetRendersTo(
            f, '<input type="file" name="f" required id="id_f" />'
        )
