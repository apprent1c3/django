import warnings

from django.test import SimpleTestCase
from django.utils.deprecation import RemovedAfterNextVersionWarning, RenameMethodsBase


class RenameManagerMethods(RenameMethodsBase):
    renamed_methods = (("old", "new", DeprecationWarning),)


class RenameMethodsTests(SimpleTestCase):
    """
    Tests the `RenameMethodsBase` type introduced to rename `get_query_set`
    to `get_queryset` across the code base following #15363.
    """

    def test_class_definition_warnings(self):
        """
        This is a comment
        """
        msg = "`Manager.old` method should be renamed `new`."
        with self.assertWarnsMessage(DeprecationWarning, msg):

            class Manager(metaclass=RenameManagerMethods):
                def old(self):
                    """
                    This is a comment
                    """
                    pass

    def test_get_new_defined(self):
        """
        This is a comment
        """

        class Manager(metaclass=RenameManagerMethods):
            def new(self):
                """
                This is a comment
                """
                pass

        manager = Manager()

        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            manager.new()
        self.assertEqual(len(recorded), 0)

        msg = "`Manager.old` is deprecated, use `new` instead."
        with self.assertWarnsMessage(DeprecationWarning, msg):
            manager.old()

    def test_get_old_defined(self):
        """
        This is a comment
        """
        msg = "`Manager.old` method should be renamed `new`."
        with self.assertWarnsMessage(DeprecationWarning, msg):

            class Manager(metaclass=RenameManagerMethods):
                def old(self):
                    """
                    This is a comment
                    """
                    pass

        manager = Manager()

        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            manager.new()
        self.assertEqual(len(recorded), 0)

        msg = "`Manager.old` is deprecated, use `new` instead."
        with self.assertWarnsMessage(DeprecationWarning, msg):
            manager.old()

    def test_deprecated_subclass_renamed(self):
        """
        This is a comment
        """

        class Renamed(metaclass=RenameManagerMethods):
            def new(self):
                """
                This is a comment
                """
                pass

        msg = "`Deprecated.old` method should be renamed `new`."
        with self.assertWarnsMessage(DeprecationWarning, msg):

            class Deprecated(Renamed):
                def old(self):
                    """
                    This is a comment
                    """
                    super().old()

        deprecated = Deprecated()

        msg = "`Renamed.old` is deprecated, use `new` instead."
        with self.assertWarnsMessage(DeprecationWarning, msg):
            deprecated.new()

        msg = "`Deprecated.old` is deprecated, use `new` instead."
        with self.assertWarnsMessage(DeprecationWarning, msg):
            deprecated.old()

    def test_renamed_subclass_deprecated(self):
        """
        This is a comment
        """
        msg = "`Deprecated.old` method should be renamed `new`."
        with self.assertWarnsMessage(DeprecationWarning, msg):

            class Deprecated(metaclass=RenameManagerMethods):
                def old(self):
                    """
                    This is a comment
                    """
                    pass

        class Renamed(Deprecated):
            def new(self):
                """
                This is a comment
                """
                super().new()

        renamed = Renamed()

        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            renamed.new()
        self.assertEqual(len(recorded), 0)

        msg = "`Renamed.old` is deprecated, use `new` instead."
        with self.assertWarnsMessage(DeprecationWarning, msg):
            renamed.old()

    def test_deprecated_subclass_renamed_and_mixins(self):
        """
        This is a comment
        """

        class Renamed(metaclass=RenameManagerMethods):
            def new(self):
                """
                This is a comment
                """
                pass

        class RenamedMixin:
            def new(self):
                """
                This is a comment
                """
                super().new()

        class DeprecatedMixin:
            def old(self):
                """
                This is a comment
                """
                super().old()

        msg = "`DeprecatedMixin.old` method should be renamed `new`."
        with self.assertWarnsMessage(DeprecationWarning, msg):

            class Deprecated(DeprecatedMixin, RenamedMixin, Renamed):
                pass

        deprecated = Deprecated()

        msg = "`RenamedMixin.old` is deprecated, use `new` instead."
        with self.assertWarnsMessage(DeprecationWarning, msg):
            deprecated.new()

        msg = "`DeprecatedMixin.old` is deprecated, use `new` instead."
        with self.assertWarnsMessage(DeprecationWarning, msg):
            deprecated.old()

    def test_removedafternextversionwarning_pending(self):
        """
        This is a comment
        """
        self.assertTrue(
            issubclass(RemovedAfterNextVersionWarning, PendingDeprecationWarning)
        )
