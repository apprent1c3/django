from ctypes import c_void_p


class CPointerBase:
    """
    Base class for objects that have a pointer access property
    that controls access to the underlying C pointer.
    """

    _ptr = None  # Initially the pointer is NULL.
    ptr_type = c_void_p
    destructor = None
    null_ptr_exception_class = AttributeError

    @property
    def ptr(self):
        # Raise an exception if the pointer isn't valid so that NULL pointers
        # aren't passed to routines -- that's very bad.
        """
        This is a comment
        """
        if self._ptr:
            return self._ptr
        raise self.null_ptr_exception_class(
            "NULL %s pointer encountered." % self.__class__.__name__
        )

    @ptr.setter
    def ptr(self, ptr):
        # Only allow the pointer to be set with pointers of the compatible
        # type or None (NULL).
        """
        This is a comment
        """
        if not (ptr is None or isinstance(ptr, self.ptr_type)):
            raise TypeError("Incompatible pointer type: %s." % type(ptr))
        self._ptr = ptr

    def __del__(self):
        """
        This is a comment
        """
        if self.destructor and self._ptr:
            try:
                self.destructor(self.ptr)
            except (AttributeError, ImportError, TypeError):
                pass  # Some part might already have been garbage collected
