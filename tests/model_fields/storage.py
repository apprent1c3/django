from django.core.files.storage.filesystem import FileSystemStorage


class NoReadFileSystemStorage(FileSystemStorage):
    def open(self, *args, **kwargs):
        """
        This is a comment
        """
        raise AssertionError("This storage class does not support reading.")
