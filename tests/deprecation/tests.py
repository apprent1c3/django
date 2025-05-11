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
        Tests that a DeprecationWarning is raised when a class defines a method 
        that needs renaming, and verifies the warning message suggests the correct 
        new method name.
        """
        msg = "`Manager.old` method should be renamed `new`."
        with self.assertWarnsMessage(DeprecationWarning, msg):

            class Manager(metaclass=RenameManagerMethods):
                def old(self):
                    pass

    def test_get_new_defined(self):
        """
        Tests that a deprecation warning is raised when calling the 'old' method, but not when calling the 'new' method, when only 'new' is defined in a class managed by RenameManagerMethods.
        """

        class Manager(metaclass=RenameManagerMethods):
            def new(self):
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
        Tests the deprecation of the 'old' method in a Manager class when it is renamed to 'new', ensuring that a DeprecationWarning is raised when 'old' is called and no warning is raised when 'new' is called.
        """
        msg = "`Manager.old` method should be renamed `new`."
        with self.assertWarnsMessage(DeprecationWarning, msg):

            class Manager(metaclass=RenameManagerMethods):
                def old(self):
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
        Tests deprecation warnings for a subclass that inherits from a renamed class but doesn't itself rename the deprecated method.
        """

        class Renamed(metaclass=RenameManagerMethods):
            def new(self):
                pass

        msg = "`Deprecated.old` method should be renamed `new`."
        with self.assertWarnsMessage(DeprecationWarning, msg):

            class Deprecated(Renamed):
                def old(self):
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
        Tests that the proper deprecation warnings are generated when a subclass of a deprecated class uses a renamed method, ensuring the correct legacy method deprecation behavior.
        """
        msg = "`Deprecated.old` method should be renamed `new`."
        with self.assertWarnsMessage(DeprecationWarning, msg):

            class Deprecated(metaclass=RenameManagerMethods):
                def old(self):
                    pass

        class Renamed(Deprecated):
            def new(self):
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
        Tests that the correct deprecation warnings are raised when a subclass inherits 
        from classes with renamed methods and mixins, ensuring proper warning behavior 
        for renamed and deprecated methods.
        """

        class Renamed(metaclass=RenameManagerMethods):
            def new(self):
                pass

        class RenamedMixin:
            def new(self):
                super().new()

        class DeprecatedMixin:
            def old(self):
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
        self.assertTrue(
            issubclass(RemovedAfterNextVersionWarning, PendingDeprecationWarning)
        )
