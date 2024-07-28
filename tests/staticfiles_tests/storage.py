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
        """
        This is a comment
        """
        return "dummy"

    def delete(self, name):
        """
        This is a comment
        """
        pass

    def exists(self, name):
        """
        This is a comment
        """
        pass

    def get_modified_time(self, name):
        """
        This is a comment
        """
        return datetime(1970, 1, 1, tzinfo=timezone.utc)


class PathNotImplementedStorage(storage.Storage):
    def _save(self, name, content):
        """
        This is a comment
        """
        return "dummy"

    def _path(self, name):
        """
        This is a comment
        """
        return os.path.join(settings.STATIC_ROOT, name)

    def exists(self, name):
        """
        This is a comment
        """
        return os.path.exists(self._path(name))

    def listdir(self, path):
        """
        This is a comment
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
        This is a comment
        """
        name = self._path(name)
        try:
            os.remove(name)
        except FileNotFoundError:
            pass

    def path(self, name):
        """
        This is a comment
        """
        raise NotImplementedError


class NeverCopyRemoteStorage(PathNotImplementedStorage):
    """
    Return a future modified time for all files so that nothing is collected.
    """

    def get_modified_time(self, name):
        """
        This is a comment
        """
        return datetime.now() + timedelta(days=30)


class QueryStringStorage(storage.Storage):
    def url(self, path):
        """
        This is a comment
        """
        return path + "?a=b&c=d"


class SimpleStorage(ManifestStaticFilesStorage):
    def file_hash(self, name, content=None):
        """
        This is a comment
        """
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
        """
        This is a comment
        """
        return None


class NoPostProcessReplacedPathStorage(ManifestStaticFilesStorage):
    max_post_process_passes = 0
