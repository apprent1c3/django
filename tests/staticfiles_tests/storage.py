import os
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.contrib.staticfiles.storage import ManifestStaticFilesStorage
from django.core.files import storage


class DummyStorage(storage.Storage):
    """
    A storage class that implements get_modified_time() but raises
    NotImplementedError for path().
    """

    def _save(self, name, content):
        return "dummy"

    def delete(self, name):
        pass

    def exists(self, name):
        pass

    def get_modified_time(self, name):
        return datetime(1970, 1, 1, tzinfo=timezone.utc)


class PathNotImplementedStorage(storage.Storage):
    def _save(self, name, content):
        return "dummy"

    def _path(self, name):
        return os.path.join(settings.STATIC_ROOT, name)

    def exists(self, name):
        return os.path.exists(self._path(name))

    def listdir(self, path):
        """
        Lists the contents of a directory.

        Parameters
        ----------
        path : str
            The path to the directory to list.

        Returns
        -------
        tuple
            A tuple containing two lists: the first list contains the names of subdirectories,
            and the second list contains the names of files in the directory.

        Notes
        -----
        The path is resolved using the object's internal path resolution mechanism.

        The function returns a tuple of two lists, allowing for easy separation of directory
        and file names. This can be useful for iterating over the contents of a directory
        and performing different actions based on whether each item is a directory or a file.

        """
        path = self._path(path)
        directories, files = [], []
        with os.scandir(path) as entries:
            for entry in entries:
                if entry.is_dir():
                    directories.append(entry.name)
                else:
                    files.append(entry.name)
        return directories, files

    def delete(self, name):
        """
        删除指定名称的文件。

        :param name: 文件名或相对于当前路径的文件路径。
        :raises None: 如果文件不存在，不会引发异常。
        :returns: None
        注意: 要删除的文件会被从文件系统中移除。 如果文件不存在，则该操作是无害的。
        """
        name = self._path(name)
        try:
            os.remove(name)
        except FileNotFoundError:
            pass

    def path(self, name):
        raise NotImplementedError


class NeverCopyRemoteStorage(PathNotImplementedStorage):
    """
    Return a future modified time for all files so that nothing is collected.
    """

    def get_modified_time(self, name):
        return datetime.now() + timedelta(days=30)


class QueryStringStorage(storage.Storage):
    def url(self, path):
        return path + "?a=b&c=d"


class SimpleStorage(ManifestStaticFilesStorage):
    def file_hash(self, name, content=None):
        return "deploy12345"


class ExtraPatternsStorage(ManifestStaticFilesStorage):
    """
    A storage class to test pattern substitutions with more than one pattern
    entry. The added pattern rewrites strings like "url(...)" to JS_URL("...").
    """

    patterns = tuple(ManifestStaticFilesStorage.patterns) + (
        (
            "*.js",
            (
                (
                    r"""(?P<matched>url\(['"]{0,1}\s*(?P<url>.*?)["']{0,1}\))""",
                    'JS_URL("%(url)s")',
                ),
            ),
        ),
    )


class NoneHashStorage(ManifestStaticFilesStorage):
    def file_hash(self, name, content=None):
        return None


class NoPostProcessReplacedPathStorage(ManifestStaticFilesStorage):
    max_post_process_passes = 0
