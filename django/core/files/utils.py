import os
import pathlib

from django.core.exceptions import SuspiciousFileOperation


def validate_file_name(name, allow_relative_path=False):
    # Remove potentially dangerous names
    """
    Validate a file name to prevent suspicious file operations.

    This function checks if a given file name is valid and does not contain any attempts to traverse the file system or include path elements.
    It can optionally allow relative paths, while still preventing absolute paths and path traversal attempts.
    If the file name is invalid, it raises a SuspiciousFileOperation exception; otherwise, it returns the validated file name.
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
        Indicates whether the associated file object is readable.

        Returns True if the file object is readable, False otherwise. The check is
        skipped if the resource is already closed, in which case False is returned.
        """
        if self.closed:
            return False
        if hasattr(self.file, "readable"):
            return self.file.readable()
        return True

    def writable(self):
        """
        Indicates whether the file object is writable, returning False if the file is closed, and otherwise checking the file's mode or 'writable' attribute.
        """
        if self.closed:
            return False
        if hasattr(self.file, "writable"):
            return self.file.writable()
        return "w" in getattr(self.file, "mode", "")

    def seekable(self):
        """
        Determines whether the file object is seekable, meaning it supports random access and can jump to any position. The determination is based on the underlying file object, defaulting to True if its seekability cannot be directly determined.
        """
        if self.closed:
            return False
        if hasattr(self.file, "seekable"):
            return self.file.seekable()
        return True

    def __iter__(self):
        return iter(self.file)
