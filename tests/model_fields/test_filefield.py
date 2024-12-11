import os
import pickle
import sys
import tempfile
import unittest
from pathlib import Path

from django.core.exceptions import FieldError, SuspiciousFileOperation
from django.core.files import File, temp
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.db import IntegrityError, models
from django.test import TestCase, override_settings
from django.test.utils import isolate_apps
from django.utils.version import PY311

from .models import Document


class FileFieldTests(TestCase):
    def test_clearable(self):
        """
        FileField.save_form_data() will clear its instance attribute value if
        passed False.
        """
        d = Document(myfile="something.txt")
        self.assertEqual(d.myfile, "something.txt")
        field = d._meta.get_field("myfile")
        field.save_form_data(d, False)
        self.assertEqual(d.myfile, "")

    def test_unchanged(self):
        """
        FileField.save_form_data() considers None to mean "no change" rather
        than "clear".
        """
        d = Document(myfile="something.txt")
        self.assertEqual(d.myfile, "something.txt")
        field = d._meta.get_field("myfile")
        field.save_form_data(d, None)
        self.assertEqual(d.myfile, "something.txt")

    def test_changed(self):
        """
        FileField.save_form_data(), if passed a truthy value, updates its
        instance attribute.
        """
        d = Document(myfile="something.txt")
        self.assertEqual(d.myfile, "something.txt")
        field = d._meta.get_field("myfile")
        field.save_form_data(d, "else.txt")
        self.assertEqual(d.myfile, "else.txt")

    def test_delete_when_file_unset(self):
        """
        Calling delete on an unset FileField should not call the file deletion
        process, but fail silently (#20660).
        """
        d = Document()
        d.myfile.delete()

    def test_refresh_from_db(self):
        d = Document.objects.create(myfile="something.txt")
        d.refresh_from_db()
        self.assertIs(d.myfile.instance, d)

    @unittest.skipIf(sys.platform == "win32", "Crashes with OSError on Windows.")
    def test_save_without_name(self):
        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp:
            document = Document.objects.create(myfile="something.txt")
            document.myfile = File(tmp)
            msg = f"Detected path traversal attempt in '{tmp.name}'"
            with self.assertRaisesMessage(SuspiciousFileOperation, msg):
                document.save()

    def test_save_content_file_without_name(self):
        """

        Tests that saving a Document instance fails when its ContentFile does not have a specified name.

        This test verifies that attempting to save a Document with a ContentFile lacking a 'name' attribute raises a FieldError.
        The expected error message indicates that a 'name' argument must be provided to ContentFile for the file to be saved.

        """
        d = Document()
        d.myfile = ContentFile(b"")
        msg = "File for myfile must have the name attribute specified to be saved."
        with self.assertRaisesMessage(FieldError, msg) as cm:
            d.save()

        if PY311:
            self.assertEqual(
                cm.exception.__notes__, ["Pass a 'name' argument to ContentFile."]
            )

    def test_delete_content_file(self):
        """
        Tests that deleting a content file associated with a document results in the 'myfile' attribute being set to None and attempting to access the file raises a ValueError.

        Checks the following conditions:

        * The file is properly deleted from the document.
        * The 'myfile' attribute is set to None after deletion.
        * Accessing the file after deletion raises a ValueError with the expected error message.

        Verifies the correct behavior of the document model when a content file is deleted, ensuring data consistency and preventing unexpected errors.
        """
        file = ContentFile(b"", name="foo")
        d = Document.objects.create(myfile=file)
        d.myfile.delete()
        self.assertIsNone(d.myfile.name)
        msg = "The 'myfile' attribute has no file associated with it."
        with self.assertRaisesMessage(ValueError, msg):
            getattr(d.myfile, "file")

    def test_defer(self):
        Document.objects.create(myfile="something.txt")
        self.assertEqual(Document.objects.defer("myfile")[0].myfile, "something.txt")

    def test_unique_when_same_filename(self):
        """
        A FileField with unique=True shouldn't allow two instances with the
        same name to be saved.
        """
        Document.objects.create(myfile="something.txt")
        with self.assertRaises(IntegrityError):
            Document.objects.create(myfile="something.txt")

    @unittest.skipIf(
        sys.platform == "win32", "Windows doesn't support moving open files."
    )
    # The file's source and destination must be on the same filesystem.
    @override_settings(MEDIA_ROOT=temp.gettempdir())
    def test_move_temporary_file(self):
        """
        The temporary uploaded file is moved rather than copied to the
        destination.
        """
        with TemporaryUploadedFile(
            "something.txt", "text/plain", 0, "UTF-8"
        ) as tmp_file:
            tmp_file_path = tmp_file.temporary_file_path()
            Document.objects.create(myfile=tmp_file)
            self.assertFalse(
                os.path.exists(tmp_file_path), "Temporary file still exists"
            )

    def test_open_returns_self(self):
        """
        FieldField.open() returns self so it can be used as a context manager.
        """
        d = Document.objects.create(myfile="something.txt")
        # Replace the FileField's file with an in-memory ContentFile, so that
        # open() doesn't write to disk.
        d.myfile.file = ContentFile(b"", name="bla")
        self.assertEqual(d.myfile, d.myfile.open())

    def test_media_root_pathlib(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with override_settings(MEDIA_ROOT=Path(tmp_dir)):
                with TemporaryUploadedFile(
                    "foo.txt", "text/plain", 1, "utf-8"
                ) as tmp_file:
                    document = Document.objects.create(myfile=tmp_file)
                    self.assertIs(
                        document.myfile.storage.exists(
                            os.path.join("unused", "foo.txt")
                        ),
                        True,
                    )

    def test_pickle(self):
        """

        Tests the pickling of Document instances and their associated File objects.

        This test ensures that the key attributes of a Document, specifically its file, 
        are preserved when the Document is pickled and then unpickled. It also verifies 
        that the same attributes are preserved when the File object itself is pickled 
        and unpickled.

        The test covers the following aspects:
        - The Document instance can be successfully pickled and unpickled.
        - The file associated with the Document is correctly pickled and unpickled.
        - The key attributes of the file (url, storage, instance, field) are preserved 
          through the pickling and unpickling process, both for the Document and its file.

        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            with override_settings(MEDIA_ROOT=Path(tmp_dir)):
                with open(__file__, "rb") as fp:
                    file1 = File(fp, name="test_file.py")
                    document = Document(myfile="test_file.py")
                    document.myfile.save("test_file.py", file1)
                    try:
                        dump = pickle.dumps(document)
                        loaded_document = pickle.loads(dump)
                        self.assertEqual(document.myfile, loaded_document.myfile)
                        self.assertEqual(
                            document.myfile.url,
                            loaded_document.myfile.url,
                        )
                        self.assertEqual(
                            document.myfile.storage,
                            loaded_document.myfile.storage,
                        )
                        self.assertEqual(
                            document.myfile.instance,
                            loaded_document.myfile.instance,
                        )
                        self.assertEqual(
                            document.myfile.field,
                            loaded_document.myfile.field,
                        )
                        myfile_dump = pickle.dumps(document.myfile)
                        loaded_myfile = pickle.loads(myfile_dump)
                        self.assertEqual(document.myfile, loaded_myfile)
                        self.assertEqual(document.myfile.url, loaded_myfile.url)
                        self.assertEqual(
                            document.myfile.storage,
                            loaded_myfile.storage,
                        )
                        self.assertEqual(
                            document.myfile.instance,
                            loaded_myfile.instance,
                        )
                        self.assertEqual(document.myfile.field, loaded_myfile.field)
                    finally:
                        document.myfile.delete()

    @isolate_apps("model_fields")
    def test_abstract_filefield_model(self):
        """
        FileField.model returns the concrete model for fields defined in an
        abstract model.
        """

        class AbstractMyDocument(models.Model):
            myfile = models.FileField(upload_to="unused")

            class Meta:
                abstract = True

        class MyDocument(AbstractMyDocument):
            pass

        document = MyDocument(myfile="test_file.py")
        self.assertEqual(document.myfile.field.model, MyDocument)
