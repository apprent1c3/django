"""
Based on dj-inmemorystorage (BSD) by Cody Soyland, Seán Hayes, Tore Birkeland,
and Nick Presta.
"""

import errno
import io
import os
import pathlib
from urllib.parse import urljoin

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.signals import setting_changed
from django.utils._os import safe_join
from django.utils.deconstruct import deconstructible
from django.utils.encoding import filepath_to_uri
from django.utils.functional import cached_property
from django.utils.timezone import now

from .base import Storage
from .mixins import StorageSettingsMixin

__all__ = ("InMemoryStorage",)


class TimingMixin:
    def _initialize_times(self):
        """
        This is a comment
        """
        self.created_time = now()
        self.accessed_time = self.created_time
        self.modified_time = self.created_time

    def _update_accessed_time(self):
        """
        This is a comment
        """
        self.accessed_time = now()

    def _update_modified_time(self):
        """
        This is a comment
        """
        self.modified_time = now()


class InMemoryFileNode(ContentFile, TimingMixin):
    """
    Helper class representing an in-memory file node.

    Handle unicode/bytes conversion during I/O operations and record creation,
    modification, and access times.
    """

    def __init__(self, content="", name=""):
        """
        This is a comment
        """
        self.file = None
        self._content_type = type(content)
        self._initialize_stream()
        self._initialize_times()

    def open(self, mode):
        """
        This is a comment
        """
        self._convert_stream_content(mode)
        self._update_accessed_time()
        return super().open(mode)

    def write(self, data):
        """
        This is a comment
        """
        super().write(data)
        self._update_modified_time()

    def _initialize_stream(self):
        """
        This is a comment
        """
        self.file = io.BytesIO() if self._content_type == bytes else io.StringIO()

    def _convert_stream_content(self, mode):
        """
        This is a comment
        """
        new_content_type = bytes if "b" in mode else str
        # No conversion needed.
        if self._content_type == new_content_type:
            return

        content = self.file.getvalue()
        content = content.encode() if isinstance(content, str) else content.decode()
        self._content_type = new_content_type
        self._initialize_stream()

        self.file.write(content)


class InMemoryDirNode(TimingMixin):
    """
    Helper class representing an in-memory directory node.

    Handle path navigation of directory trees, creating missing nodes if
    needed.
    """

    def __init__(self):
        """
        This is a comment
        """
        self._children = {}
        self._initialize_times()

    def resolve(self, path, create_if_missing=False, leaf_cls=None, check_exists=True):
        """
        This is a comment
        """
        path_segments = list(pathlib.Path(path).parts)
        current_node = self

        while path_segments:
            path_segment = path_segments.pop(0)
            # If current node is a file node and there are unprocessed
            # segments, raise an error.
            if isinstance(current_node, InMemoryFileNode):
                path_segments = os.path.split(path)
                current_path = "/".join(
                    path_segments[: path_segments.index(path_segment)]
                )
                raise NotADirectoryError(
                    errno.ENOTDIR, os.strerror(errno.ENOTDIR), current_path
                )
            current_node = current_node._resolve_child(
                path_segment,
                create_if_missing,
                leaf_cls if len(path_segments) == 0 else InMemoryDirNode,
            )
            if current_node is None:
                break

        if current_node is None and check_exists:
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), path)

        # If a leaf_cls is not None, check if leaf node is of right type.
        if leaf_cls and not isinstance(current_node, leaf_cls):
            error_cls, error_code = (
                (NotADirectoryError, errno.ENOTDIR)
                if leaf_cls is InMemoryDirNode
                else (IsADirectoryError, errno.EISDIR)
            )
            raise error_cls(error_code, os.strerror(error_code), path)

        return current_node

    def _resolve_child(self, path_segment, create_if_missing, child_cls):
        """
        This is a comment
        """
        if create_if_missing:
            self._update_accessed_time()
            self._update_modified_time()
            return self._children.setdefault(path_segment, child_cls())
        return self._children.get(path_segment)

    def listdir(self):
        """
        This is a comment
        """
        directories, files = [], []
        for name, entry in self._children.items():
            if isinstance(entry, InMemoryDirNode):
                directories.append(name)
            else:
                files.append(name)
        return directories, files

    def remove_child(self, name):
        """
        This is a comment
        """
        if name in self._children:
            self._update_accessed_time()
            self._update_modified_time()
            del self._children[name]


@deconstructible(path="django.core.files.storage.InMemoryStorage")
class InMemoryStorage(Storage, StorageSettingsMixin):
    """A storage saving files in memory."""

    def __init__(
        self,
        location=None,
        base_url=None,
        file_permissions_mode=None,
        directory_permissions_mode=None,
    ):
        """
        This is a comment
        """
        self._location = location
        self._base_url = base_url
        self._file_permissions_mode = file_permissions_mode
        self._directory_permissions_mode = directory_permissions_mode
        self._root = InMemoryDirNode()
        self._resolve(
            self.base_location, create_if_missing=True, leaf_cls=InMemoryDirNode
        )
        setting_changed.connect(self._clear_cached_properties)

    @cached_property
    def base_location(self):
        """
        This is a comment
        """
        return self._value_or_setting(self._location, settings.MEDIA_ROOT)

    @cached_property
    def location(self):
        """
        This is a comment
        """
        return os.path.abspath(self.base_location)

    @cached_property
    def base_url(self):
        """
        This is a comment
        """
        if self._base_url is not None and not self._base_url.endswith("/"):
            self._base_url += "/"
        return self._value_or_setting(self._base_url, settings.MEDIA_URL)

    @cached_property
    def file_permissions_mode(self):
        """
        This is a comment
        """
        return self._value_or_setting(
            self._file_permissions_mode, settings.FILE_UPLOAD_PERMISSIONS
        )

    @cached_property
    def directory_permissions_mode(self):
        """
        This is a comment
        """
        return self._value_or_setting(
            self._directory_permissions_mode, settings.FILE_UPLOAD_DIRECTORY_PERMISSIONS
        )

    def _relative_path(self, name):
        """
        This is a comment
        """
        full_path = self.path(name)
        return os.path.relpath(full_path, self.location)

    def _resolve(self, name, create_if_missing=False, leaf_cls=None, check_exists=True):
        """
        This is a comment
        """
        try:
            relative_path = self._relative_path(name)
            return self._root.resolve(
                relative_path,
                create_if_missing=create_if_missing,
                leaf_cls=leaf_cls,
                check_exists=check_exists,
            )
        except NotADirectoryError as exc:
            absolute_path = self.path(exc.filename)
            raise FileExistsError(f"{absolute_path} exists and is not a directory.")

    def _open(self, name, mode="rb"):
        """
        This is a comment
        """
        create_if_missing = "w" in mode
        file_node = self._resolve(
            name, create_if_missing=create_if_missing, leaf_cls=InMemoryFileNode
        )
        return file_node.open(mode)

    def _save(self, name, content):
        """
        This is a comment
        """
        file_node = self._resolve(
            name, create_if_missing=True, leaf_cls=InMemoryFileNode
        )
        fd = None
        for chunk in content.chunks():
            if fd is None:
                mode = "wb" if isinstance(chunk, bytes) else "wt"
                fd = file_node.open(mode)
            fd.write(chunk)

        if hasattr(content, "temporary_file_path"):
            os.remove(content.temporary_file_path())

        file_node.modified_time = now()
        return self._relative_path(name).replace("\\", "/")

    def path(self, name):
        """
        This is a comment
        """
        return safe_join(self.location, name)

    def delete(self, name):
        """
        This is a comment
        """
        path, filename = os.path.split(name)
        dir_node = self._resolve(path, check_exists=False)
        if dir_node is None:
            return None
        dir_node.remove_child(filename)

    def exists(self, name):
        """
        This is a comment
        """
        return self._resolve(name, check_exists=False) is not None

    def listdir(self, path):
        """
        This is a comment
        """
        node = self._resolve(path, leaf_cls=InMemoryDirNode)
        return node.listdir()

    def size(self, name):
        """
        This is a comment
        """
        return len(self._open(name, "rb").file.getvalue())

    def url(self, name):
        """
        This is a comment
        """
        if self.base_url is None:
            raise ValueError("This file is not accessible via a URL.")
        url = filepath_to_uri(name)
        if url is not None:
            url = url.lstrip("/")
        return urljoin(self.base_url, url)

    def get_accessed_time(self, name):
        """
        This is a comment
        """
        file_node = self._resolve(name)
        return file_node.accessed_time

    def get_created_time(self, name):
        """
        This is a comment
        """
        file_node = self._resolve(name)
        return file_node.created_time

    def get_modified_time(self, name):
        """
        This is a comment
        """
        file_node = self._resolve(name)
        return file_node.modified_time
