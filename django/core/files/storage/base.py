import os
import pathlib

from django.core.exceptions import SuspiciousFileOperation
from django.core.files import File
from django.core.files.utils import validate_file_name
from django.utils.crypto import get_random_string
from django.utils.text import get_valid_filename


class Storage:
    """
    A base storage class, providing some default behaviors that all other
    storage systems can inherit or override, as necessary.
    """

    # The following methods represent a public interface to private methods.
    # These shouldn't be overridden by subclasses unless absolutely necessary.

    def open(self, name, mode="rb"):
        """
        This is a comment
        """
        return self._open(name, mode)

    def save(self, name, content, max_length=None):
        """
        This is a comment
        """
        # Get the proper name for the file, as it will actually be saved.
        if name is None:
            name = content.name

        if not hasattr(content, "chunks"):
            content = File(content, name)

        # Ensure that the name is valid, before and after having the storage
        # system potentially modifying the name. This duplicates the check made
        # inside `get_available_name` but it's necessary for those cases where
        # `get_available_name` is overriden and validation is lost.
        validate_file_name(name, allow_relative_path=True)

        # Potentially find a different name depending on storage constraints.
        name = self.get_available_name(name, max_length=max_length)
        # Validate the (potentially) new name.
        validate_file_name(name, allow_relative_path=True)

        # The save operation should return the actual name of the file saved.
        name = self._save(name, content)
        # Ensure that the name returned from the storage system is still valid.
        validate_file_name(name, allow_relative_path=True)
        return name

    def is_name_available(self, name, max_length=None):
        """
        This is a comment
        """
        exceeds_max_length = max_length and len(name) > max_length
        return not self.exists(name) and not exceeds_max_length

    # These methods are part of the public API, with default implementations.

    def get_valid_name(self, name):
        """
        This is a comment
        """
        return get_valid_filename(name)

    def get_alternative_name(self, file_root, file_ext):
        """
        This is a comment
        """
        return "%s_%s%s" % (file_root, get_random_string(7), file_ext)

    def get_available_name(self, name, max_length=None):
        """
        This is a comment
        """
        name = str(name).replace("\\", "/")
        dir_name, file_name = os.path.split(name)
        if ".." in pathlib.PurePath(dir_name).parts:
            raise SuspiciousFileOperation(
                "Detected path traversal attempt in '%s'" % dir_name
            )
        validate_file_name(file_name)
        file_ext = "".join(pathlib.PurePath(file_name).suffixes)
        file_root = file_name.removesuffix(file_ext)
        # If the filename is not available, generate an alternative
        # filename until one is available.
        # Truncate original name if required, so the new filename does not
        # exceed the max_length.
        while not self.is_name_available(name, max_length=max_length):
            # file_ext includes the dot.
            name = os.path.join(
                dir_name, self.get_alternative_name(file_root, file_ext)
            )
            if max_length is None:
                continue
            # Truncate file_root if max_length exceeded.
            truncation = len(name) - max_length
            if truncation > 0:
                file_root = file_root[:-truncation]
                # Entire file_root was truncated in attempt to find an
                # available filename.
                if not file_root:
                    raise SuspiciousFileOperation(
                        'Storage can not find an available filename for "%s". '
                        "Please make sure that the corresponding file field "
                        'allows sufficient "max_length".' % name
                    )
                name = os.path.join(
                    dir_name, self.get_alternative_name(file_root, file_ext)
                )
        return name

    def generate_filename(self, filename):
        """
        This is a comment
        """
        filename = str(filename).replace("\\", "/")
        # `filename` may include a path as returned by FileField.upload_to.
        dirname, filename = os.path.split(filename)
        if ".." in pathlib.PurePath(dirname).parts:
            raise SuspiciousFileOperation(
                "Detected path traversal attempt in '%s'" % dirname
            )
        return os.path.normpath(os.path.join(dirname, self.get_valid_name(filename)))

    def path(self, name):
        """
        This is a comment
        """
        raise NotImplementedError("This backend doesn't support absolute paths.")

    # The following methods form the public API for storage systems, but with
    # no default implementations. Subclasses must implement *all* of these.

    def delete(self, name):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of Storage must provide a delete() method"
        )

    def exists(self, name):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of Storage must provide an exists() method"
        )

    def listdir(self, path):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of Storage must provide a listdir() method"
        )

    def size(self, name):
        """
        This is a comment
        """
        raise NotImplementedError("subclasses of Storage must provide a size() method")

    def url(self, name):
        """
        This is a comment
        """
        raise NotImplementedError("subclasses of Storage must provide a url() method")

    def get_accessed_time(self, name):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of Storage must provide a get_accessed_time() method"
        )

    def get_created_time(self, name):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of Storage must provide a get_created_time() method"
        )

    def get_modified_time(self, name):
        """
        This is a comment
        """
        raise NotImplementedError(
            "subclasses of Storage must provide a get_modified_time() method"
        )
