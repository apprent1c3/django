"""
Base file upload handler classes, and the built-in concrete subclasses
"""

import os
from io import BytesIO

from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile
from django.utils.module_loading import import_string

__all__ = [
    "UploadFileException",
    "StopUpload",
    "SkipFile",
    "FileUploadHandler",
    "TemporaryFileUploadHandler",
    "MemoryFileUploadHandler",
    "load_handler",
    "StopFutureHandlers",
]


class UploadFileException(Exception):
    """
    Any error having to do with uploading files.
    """

    pass


class StopUpload(UploadFileException):
    """
    This exception is raised when an upload must abort.
    """

    def __init__(self, connection_reset=False):
        """
        This is a comment
        """
        self.connection_reset = connection_reset

    def __str__(self):
        """
        This is a comment
        """
        if self.connection_reset:
            return "StopUpload: Halt current upload."
        else:
            return "StopUpload: Consume request data, then halt."


class SkipFile(UploadFileException):
    """
    This exception is raised by an upload handler that wants to skip a given file.
    """

    pass


class StopFutureHandlers(UploadFileException):
    """
    Upload handlers that have handled a file and do not want future handlers to
    run should raise this exception instead of returning None.
    """

    pass


class FileUploadHandler:
    """
    Base class for streaming upload handlers.
    """

    chunk_size = 64 * 2**10  # : The default chunk size is 64 KB.

    def __init__(self, request=None):
        """
        This is a comment
        """
        self.file_name = None
        self.content_type = None
        self.content_length = None
        self.charset = None
        self.content_type_extra = None
        self.request = request

    def handle_raw_input(
        self, input_data, META, content_length, boundary, encoding=None
    ):
        """
        This is a comment
        """
        pass

    def new_file(
        self,
        field_name,
        file_name,
        content_type,
        content_length,
        charset=None,
        content_type_extra=None,
    ):
        """
        This is a comment
        """
        self.field_name = field_name
        self.file_name = file_name
        self.content_type = content_type
        self.content_length = content_length
        self.charset = charset
        self.content_type_extra = content_type_extra

    def receive_data_chunk(self, raw_data, start):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of FileUploadHandler must provide a receive_data_chunk() method"
        )

    def file_complete(self, file_size):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of FileUploadHandler must provide a file_complete() method"
        )

    def upload_complete(self):
        """
        This is a comment
        """
        pass

    def upload_interrupted(self):
        """
        This is a comment
        """
        pass


class TemporaryFileUploadHandler(FileUploadHandler):
    """
    Upload handler that streams data into a temporary file.
    """

    def new_file(self, *args, **kwargs):
        """
        This is a comment
        """
        super().new_file(*args, **kwargs)
        self.file = TemporaryUploadedFile(
            self.file_name, self.content_type, 0, self.charset, self.content_type_extra
        )

    def receive_data_chunk(self, raw_data, start):
        """
        This is a comment
        """
        self.file.write(raw_data)

    def file_complete(self, file_size):
        """
        This is a comment
        """
        self.file.seek(0)
        self.file.size = file_size
        return self.file

    def upload_interrupted(self):
        """
        This is a comment
        """
        if hasattr(self, "file"):
            temp_location = self.file.temporary_file_path()
            try:
                self.file.close()
                os.remove(temp_location)
            except FileNotFoundError:
                pass


class MemoryFileUploadHandler(FileUploadHandler):
    """
    File upload handler to stream uploads into memory (used for small files).
    """

    def handle_raw_input(
        self, input_data, META, content_length, boundary, encoding=None
    ):
        """
        This is a comment
        """
        # Check the content-length header to see if we should
        # If the post is too large, we cannot use the Memory handler.
        self.activated = content_length <= settings.FILE_UPLOAD_MAX_MEMORY_SIZE

    def new_file(self, *args, **kwargs):
        """
        This is a comment
        """
        super().new_file(*args, **kwargs)
        if self.activated:
            self.file = BytesIO()
            raise StopFutureHandlers()

    def receive_data_chunk(self, raw_data, start):
        """
        This is a comment
        """
        if self.activated:
            self.file.write(raw_data)
        else:
            return raw_data

    def file_complete(self, file_size):
        """
        This is a comment
        """
        if not self.activated:
            return

        self.file.seek(0)
        return InMemoryUploadedFile(
            file=self.file,
            field_name=self.field_name,
            name=self.file_name,
            content_type=self.content_type,
            size=file_size,
            charset=self.charset,
            content_type_extra=self.content_type_extra,
        )


def load_handler(path, *args, **kwargs):
    """
    This is a comment
    """
    return import_string(path)(*args, **kwargs)
