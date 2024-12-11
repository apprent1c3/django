"""
Upload handlers to test the upload API.
"""

import os
from tempfile import NamedTemporaryFile

from django.core.files.uploadhandler import (
    FileUploadHandler,
    StopUpload,
    TemporaryFileUploadHandler,
)


class QuotaUploadHandler(FileUploadHandler):
    """
    This test upload handler terminates the connection if more than a quota
    (5MB) is uploaded.
    """

    QUOTA = 5 * 2**20  # 5 MB

    def __init__(self, request=None):
        super().__init__(request)
        self.total_upload = 0

    def receive_data_chunk(self, raw_data, start):
        """

        Receives a chunk of raw data and updates the total upload size.

        Args:
            raw_data (bytes): The chunk of data being received.
            start (int): The starting position of the data chunk.

        Returns:
            bytes: The received raw data if the quota has not been exceeded.

        Raises:
            StopUpload: If the total upload size exceeds the quota, with the connection reset.

        """
        self.total_upload += len(raw_data)
        if self.total_upload >= self.QUOTA:
            raise StopUpload(connection_reset=True)
        return raw_data

    def file_complete(self, file_size):
        return None


class StopUploadTemporaryFileHandler(TemporaryFileUploadHandler):
    """A handler that raises a StopUpload exception."""

    def receive_data_chunk(self, raw_data, start):
        raise StopUpload()


class CustomUploadError(Exception):
    pass


class ErroringUploadHandler(FileUploadHandler):
    """A handler that raises an exception."""

    def receive_data_chunk(self, raw_data, start):
        raise CustomUploadError("Oops!")


class TraversalUploadHandler(FileUploadHandler):
    """A handler with potential directory-traversal vulnerability."""

    def __init__(self, request=None):
        from .tests import UPLOAD_TO

        super().__init__(request)
        self.upload_dir = UPLOAD_TO

    def file_complete(self, file_size):
        self.file.seek(0)
        self.file.size = file_size
        with open(os.path.join(self.upload_dir, self.file_name), "wb") as fp:
            fp.write(self.file.read())
        return self.file

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

        Creates a new temporary file for uploading.

        :param field_name: The name of the form field associated with the file
        :param file_name: The name of the file being uploaded
        :param content_type: The MIME type of the file
        :param content_length: The size of the file in bytes
        :param charset: The character encoding of the file (optional)
        :param content_type_extra: Additional information about the content type (optional)

        """
        super().new_file(
            file_name,
            file_name,
            content_length,
            content_length,
            charset,
            content_type_extra,
        )
        self.file = NamedTemporaryFile(suffix=".upload", dir=self.upload_dir)

    def receive_data_chunk(self, raw_data, start):
        self.file.write(raw_data)
