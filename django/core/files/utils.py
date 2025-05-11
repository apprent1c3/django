import os
import pathlib

from django.core.exceptions import SuspiciousFileOperation


def validate_file_name(name, allow_relative_path=False):
    # Remove potentially dangerous names
    """
    Validates a file name to prevent path traversal attacks and ensure the name is not empty or incomplete.

    :param name: The file name to be validated.
    :param allow_relative_path: Whether to allow relative paths in the file name (default: False).
    :raises SuspiciousFileOperation: If the file name is invalid or appears to be a path traversal attempt.
    :return: The validated file name if it is valid.
    """
    if os.path.basename(name) in {"", ".", ".."}:
        raise SuspiciousFileOperation("Could not derive file name from '%s'" % name)

    if allow_relative_path:
        # Ensure that name can be treated as a pure posix path, i.e. Unix
        # style (with forward slashes).
        path = pathlib.PurePosixPath(str(name).replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts:
            raise SuspiciousFileOperation(
                "Detected path traversal attempt in '%s'" % name
            )
    elif name != os.path.basename(name):
        raise SuspiciousFileOperation("File name '%s' includes path elements" % name)

    return name


class FileProxyMixin:
    """
    A mixin class used to forward file methods to an underlying file
    object.  The internal file object has to be called "file"::

        class FileProxy(FileProxyMixin):
            def __init__(self, file):
                self.file = file
    """

    encoding = property(lambda self: self.file.encoding)
    fileno = property(lambda self: self.file.fileno)
    flush = property(lambda self: self.file.flush)
    isatty = property(lambda self: self.file.isatty)
    newlines = property(lambda self: self.file.newlines)
    read = property(lambda self: self.file.read)
    readinto = property(lambda self: self.file.readinto)
    readline = property(lambda self: self.file.readline)
    readlines = property(lambda self: self.file.readlines)
    seek = property(lambda self: self.file.seek)
    tell = property(lambda self: self.file.tell)
    truncate = property(lambda self: self.file.truncate)
    write = property(lambda self: self.file.write)
    writelines = property(lambda self: self.file.writelines)

    @property
    def closed(self):
        return not self.file or self.file.closed

    def readable(self):
        """
        Indicates whether an object can be read from.

        Returns:
            bool: True if the object is readable, False otherwise.
        """
        if self.closed:
            return False
        if hasattr(self.file, "readable"):
            return self.file.readable()
        return True

    def writable(self):
        """
        Checks if the file object associated with this instance is currently writable.
        """
        if self.closed:
            return False
        if hasattr(self.file, "writable"):
            return self.file.writable()
        return "w" in getattr(self.file, "mode", "")

    def seekable(self):
        """
        Indicates whether the associated file object is seekable.

        Returns:
            bool: True if the file object allows seeking, False otherwise.
        """
        if self.closed:
            return False
        if hasattr(self.file, "seekable"):
            return self.file.seekable()
        return True

    def __iter__(self):
        return iter(self.file)
