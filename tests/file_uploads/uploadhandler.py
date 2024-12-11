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
        """
        Initializes the class instance, optionally setting the request attribute and initializing the total upload counter to zero. 
        :param request: The request to be associated with this instance
        :rtype: None
        """
        super().__init__(request)
        self.total_upload = 0

    def receive_data_chunk(self, raw_data, start):
        """

        Receives a chunk of raw data and processes it for upload.

        This method updates the total upload size and checks if the quota has been exceeded. 
        If the quota has been exceeded, it raises a StopUpload exception to halt the upload process.

        :param raw_data: The chunk of data being uploaded
        :param start: The starting point of the data chunk (not utilized in this implementation)
        :raises StopUpload: If the total upload size exceeds the quota
        :return: The received raw data chunk

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
        """

        Initializes the instance, optionally with a request object.

        This constructor sets up the object with a reference to the parent class
        through a call to :meth:`super().__init__()`. It also defines the directory
        where uploads will be stored, using the value from :data:`UPLOAD_TO`.

        :param request: Optional request object to be associated with the instance

        """
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

        Parameters
        ----------
        field_name : str
            The name of the field associated with the uploaded file.
        file_name : str
            The name of the uploaded file.
        content_type : str
            The MIME type of the uploaded file.
        content_length : int
            The size of the uploaded file in bytes.
        charset : str, optional
            The character encoding of the uploaded file (default is None).
        content_type_extra : str, optional
            Additional information about the content type (default is None).

        Returns
        -------
        None

        Notes
        -----
        The created file is stored in a temporary location on disk and has a '.upload' suffix.
        This method should be used to initialize the upload process. The actual file contents are not handled in this method.

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
