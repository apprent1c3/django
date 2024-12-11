import datetime
import decimal
import enum
import functools
import math
import os
import pathlib
import re
import sys
import time
import uuid
import zoneinfo
from types import NoneType
from unittest import mock

import custom_migration_operations.more_operations
import custom_migration_operations.operations

from django import get_version
from django.conf import SettingsReference, settings
from django.core.validators import EmailValidator, RegexValidator
from django.db import migrations, models
from django.db.migrations.serializer import BaseSerializer
from django.db.migrations.writer import MigrationWriter, OperationWriter
from django.test import SimpleTestCase
from django.utils.deconstruct import deconstructible
from django.utils.functional import SimpleLazyObject
from django.utils.timezone import get_default_timezone, get_fixed_timezone
from django.utils.translation import gettext_lazy as _

from .models import FoodManager, FoodQuerySet


def get_choices():
    return [(i, str(i)) for i in range(3)]


class DeconstructibleInstances:
    def deconstruct(self):
        return ("DeconstructibleInstances", [], {})


class Money(decimal.Decimal):
    def deconstruct(self):
        return (
            "%s.%s" % (self.__class__.__module__, self.__class__.__name__),
            [str(self)],
            {},
        )


class TestModel1:
    def upload_to(self):
        return "/somewhere/dynamic/"

    thing = models.FileField(upload_to=upload_to)


class TextEnum(enum.Enum):
    A = "a-value"
    B = "value-b"


class TextTranslatedEnum(enum.Enum):
    A = _("a-value")
    B = _("value-b")


class BinaryEnum(enum.Enum):
    A = b"a-value"
    B = b"value-b"


class IntEnum(enum.IntEnum):
    A = 1
    B = 2


class IntFlagEnum(enum.IntFlag):
    A = 1
    B = 2


def decorator(f):
    @functools.wraps(f)
    """
    A decorator function that preserves the original function's metadata.

    This decorator does not modify the behavior of the original function but allows
    for additional functionality to be added in the future. It ensures that the
    original function's name, docstring, and other attributes are retained in the
    decorated function.

    Use this decorator to create a base for other decorators, or when you need to
    preserve the original function's identity while still allowing for further
    customization.

    Args:
        f (callable): The function to be decorated.

    Returns:
        callable: The decorated function.

    """
    def wrapper(*args, **kwargs):
        return f(*args, **kwargs)

    return wrapper


@decorator
def function_with_decorator():
    pass


@functools.cache
def function_with_cache():
    pass


@functools.lru_cache(maxsize=10)
def function_with_lru_cache():
    pass


class OperationWriterTests(SimpleTestCase):
    def test_empty_signature(self):
        operation = custom_migration_operations.operations.TestOperation()
        buff, imports = OperationWriter(operation, indentation=0).serialize()
        self.assertEqual(imports, {"import custom_migration_operations.operations"})
        self.assertEqual(
            buff,
            "custom_migration_operations.operations.TestOperation(\n),",
        )

    def test_args_signature(self):
        """

        Tests the ArgsOperation signature serialization.

        Verifies that the ArgsOperation is correctly serialized into a string, including proper indentation and import statement.
        The test case checks for the expected output string format and the required import statements.

        """
        operation = custom_migration_operations.operations.ArgsOperation(1, 2)
        buff, imports = OperationWriter(operation, indentation=0).serialize()
        self.assertEqual(imports, {"import custom_migration_operations.operations"})
        self.assertEqual(
            buff,
            "custom_migration_operations.operations.ArgsOperation(\n"
            "    arg1=1,\n"
            "    arg2=2,\n"
            "),",
        )

    def test_kwargs_signature(self):
        operation = custom_migration_operations.operations.KwargsOperation(kwarg1=1)
        buff, imports = OperationWriter(operation, indentation=0).serialize()
        self.assertEqual(imports, {"import custom_migration_operations.operations"})
        self.assertEqual(
            buff,
            "custom_migration_operations.operations.KwargsOperation(\n"
            "    kwarg1=1,\n"
            "),",
        )

    def test_args_kwargs_signature(self):
        """
        Tests the ArgsKwargsOperation function's signature.

        This test case verifies that ArgsKwargsOperation with positional and keyword arguments 
        is correctly serialized into a string representation. The serialized form should include 
        the operation's name, argument values, and import statement.

        The test checks for the following:
        - Correct import statement generation.
        - Accurate representation of operation's arguments in the serialized string.

        It ensures the ArgsKwargsOperation can be properly represented as a string, 
        which is crucial for writing and applying custom migration operations.
        """
        operation = custom_migration_operations.operations.ArgsKwargsOperation(
            1, 2, kwarg2=4
        )
        buff, imports = OperationWriter(operation, indentation=0).serialize()
        self.assertEqual(imports, {"import custom_migration_operations.operations"})
        self.assertEqual(
            buff,
            "custom_migration_operations.operations.ArgsKwargsOperation(\n"
            "    arg1=1,\n"
            "    arg2=2,\n"
            "    kwarg2=4,\n"
            "),",
        )

    def test_keyword_only_args_signature(self):
        """

        Tests the serialization of a function signature that includes both positional and keyword-only arguments.

        The function verifies that the operation is correctly serialized into a string representation 
        and that the necessary imports are properly generated. The test case covers the ArgsAndKeywordOnlyArgsOperation 
        from custom_migration_operations, ensuring that all arguments (both positional and keyword) are correctly 
        represented in the generated string.

        This test helps to ensure that the OperationWriter correctly handles function signatures with various 
        argument types, providing accurate and complete documentation of the operation.

        """
        operation = (
            custom_migration_operations.operations.ArgsAndKeywordOnlyArgsOperation(
                1, 2, kwarg1=3, kwarg2=4
            )
        )
        buff, imports = OperationWriter(operation, indentation=0).serialize()
        self.assertEqual(imports, {"import custom_migration_operations.operations"})
        self.assertEqual(
            buff,
            "custom_migration_operations.operations.ArgsAndKeywordOnlyArgsOperation(\n"
            "    arg1=1,\n"
            "    arg2=2,\n"
            "    kwarg1=3,\n"
            "    kwarg2=4,\n"
            "),",
        )

    def test_nested_args_signature(self):
        """

        Tests the serialization of a nested ArgsOperation.

        This test case verifies that the ArgsOperation is correctly serialized when it contains another ArgsOperation and a KwargsOperation as its arguments. It checks the generated buffer and import statements to ensure they match the expected output.

        The test covers the following scenarios:

        * Nested ArgsOperation is properly serialized with correct indentation and formatting.
        * KwargsOperation is correctly serialized as an argument to the outer ArgsOperation.
        * Import statements are generated correctly for the operations used in the test case.

        The test asserts that the generated buffer and import statements match the expected output, ensuring that the serialization of nested ArgsOperation is working as expected.

        """
        operation = custom_migration_operations.operations.ArgsOperation(
            custom_migration_operations.operations.ArgsOperation(1, 2),
            custom_migration_operations.operations.KwargsOperation(kwarg1=3, kwarg2=4),
        )
        buff, imports = OperationWriter(operation, indentation=0).serialize()
        self.assertEqual(imports, {"import custom_migration_operations.operations"})
        self.assertEqual(
            buff,
            "custom_migration_operations.operations.ArgsOperation(\n"
            "    arg1=custom_migration_operations.operations.ArgsOperation(\n"
            "        arg1=1,\n"
            "        arg2=2,\n"
            "    ),\n"
            "    arg2=custom_migration_operations.operations.KwargsOperation(\n"
            "        kwarg1=3,\n"
            "        kwarg2=4,\n"
            "    ),\n"
            "),",
        )

    def test_multiline_args_signature(self):
        operation = custom_migration_operations.operations.ArgsOperation(
            "test\n    arg1", "test\narg2"
        )
        buff, imports = OperationWriter(operation, indentation=0).serialize()
        self.assertEqual(imports, {"import custom_migration_operations.operations"})
        self.assertEqual(
            buff,
            "custom_migration_operations.operations.ArgsOperation(\n"
            "    arg1='test\\n    arg1',\n"
            "    arg2='test\\narg2',\n"
            "),",
        )

    def test_expand_args_signature(self):
        operation = custom_migration_operations.operations.ExpandArgsOperation([1, 2])
        buff, imports = OperationWriter(operation, indentation=0).serialize()
        self.assertEqual(imports, {"import custom_migration_operations.operations"})
        self.assertEqual(
            buff,
            "custom_migration_operations.operations.ExpandArgsOperation(\n"
            "    arg=[\n"
            "        1,\n"
            "        2,\n"
            "    ],\n"
            "),",
        )

    def test_nested_operation_expand_args_signature(self):
        """

        Tests the ExpandArgsOperation with a nested operation, specifically an instance of KwargsOperation.

        This test verifies that the ExpandArgsOperation is correctly serialized into the expected code string and import statement.
        The test checks that the nested KwargsOperation is properly handled and that the resulting serialized code matches the expected output.

        The purpose of this test is to ensure that the ExpandArgsOperation can be correctly used with more complex arguments, such as other operations, and that the output is correctly formatted.

        """
        operation = custom_migration_operations.operations.ExpandArgsOperation(
            arg=[
                custom_migration_operations.operations.KwargsOperation(
                    kwarg1=1,
                    kwarg2=2,
                ),
            ]
        )
        buff, imports = OperationWriter(operation, indentation=0).serialize()
        self.assertEqual(imports, {"import custom_migration_operations.operations"})
        self.assertEqual(
            buff,
            "custom_migration_operations.operations.ExpandArgsOperation(\n"
            "    arg=[\n"
            "        custom_migration_operations.operations.KwargsOperation(\n"
            "            kwarg1=1,\n"
            "            kwarg2=2,\n"
            "        ),\n"
            "    ],\n"
            "),",
        )


class WriterTests(SimpleTestCase):
    """
    Tests the migration writer (makes migration files from Migration instances)
    """

    class NestedEnum(enum.IntEnum):
        A = 1
        B = 2

    class NestedChoices(models.TextChoices):
        X = "X", "X value"
        Y = "Y", "Y value"

        @classmethod
        def method(cls):
            return cls.X

    def safe_exec(self, string, value=None):
        d = {}
        try:
            exec(string, globals(), d)
        except Exception as e:
            if value:
                self.fail(
                    "Could not exec %r (from value %r): %s" % (string.strip(), value, e)
                )
            else:
                self.fail("Could not exec %r: %s" % (string.strip(), e))
        return d

    def serialize_round_trip(self, value):
        """

        Serializes an object and performs a round trip test to verify its integrity.

        This method takes an input value, serializes it into a string representation, 
        and then executes the serialized string in a safe environment to reconstruct 
        the original object. If the serialization and reconstruction process is successful, 
        the reconstructed object is returned. 

        The purpose of this function is to ensure that the serialization process preserves 
        the original object's properties and behavior, which is crucial for reliable data 
        migration and storage. 

        :param value: The object to be serialized and tested.
        :return: The reconstructed object after a successful round trip.

        """
        string, imports = MigrationWriter.serialize(value)
        return self.safe_exec(
            "%s\ntest_value_result = %s" % ("\n".join(imports), string), value
        )["test_value_result"]

    def assertSerializedEqual(self, value):
        self.assertEqual(self.serialize_round_trip(value), value)

    def assertSerializedResultEqual(self, value, target):
        self.assertEqual(MigrationWriter.serialize(value), target)

    def assertSerializedFieldEqual(self, value):
        new_value = self.serialize_round_trip(value)
        self.assertEqual(value.__class__, new_value.__class__)
        self.assertEqual(value.max_length, new_value.max_length)
        self.assertEqual(value.null, new_value.null)
        self.assertEqual(value.unique, new_value.unique)

    def test_serialize_numbers(self):
        self.assertSerializedEqual(1)
        self.assertSerializedEqual(1.2)
        self.assertTrue(math.isinf(self.serialize_round_trip(float("inf"))))
        self.assertTrue(math.isinf(self.serialize_round_trip(float("-inf"))))
        self.assertTrue(math.isnan(self.serialize_round_trip(float("nan"))))

        self.assertSerializedEqual(decimal.Decimal("1.3"))
        self.assertSerializedResultEqual(
            decimal.Decimal("1.3"), ("Decimal('1.3')", {"from decimal import Decimal"})
        )

        self.assertSerializedEqual(Money("1.3"))
        self.assertSerializedResultEqual(
            Money("1.3"),
            ("migrations.test_writer.Money('1.3')", {"import migrations.test_writer"}),
        )

    def test_serialize_constants(self):
        """
        Tests the serialization of constant values.

        Verifies that the serialization process correctly handles and preserves the
        values of None, True, and False when converting them to their serialized form.

        This test ensures that these fundamental constants are accurately represented
        after serialization, which is crucial for maintaining data integrity and
        consistency in various applications and use cases.
        """
        self.assertSerializedEqual(None)
        self.assertSerializedEqual(True)
        self.assertSerializedEqual(False)

    def test_serialize_strings(self):
        self.assertSerializedEqual(b"foobar")
        string, imports = MigrationWriter.serialize(b"foobar")
        self.assertEqual(string, "b'foobar'")
        self.assertSerializedEqual("föobár")
        string, imports = MigrationWriter.serialize("foobar")
        self.assertEqual(string, "'foobar'")

    def test_serialize_multiline_strings(self):
        """
        Tests the serialization of multiline strings.

        This test case checks that multiline strings can be properly serialized and 
        deserialized. It covers both byte strings and Unicode strings containing 
        non-ASCII characters and newline characters, ensuring that they are correctly 
        escaped and represented as Python literals.

        The test verifies that the resulting serialized string is a valid Python 
        representation of the original multiline string, with newline characters 
        correctly escaped. It also checks that the serialization process works 
        correctly for both byte and Unicode strings, handling any necessary imports 
        and encoding conversions.

        The expected output is a serialized string that can be safely used in a 
        Python migration script, with the original multiline string accurately 
        represented and newline characters properly escaped.
        """
        self.assertSerializedEqual(b"foo\nbar")
        string, imports = MigrationWriter.serialize(b"foo\nbar")
        self.assertEqual(string, "b'foo\\nbar'")
        self.assertSerializedEqual("föo\nbár")
        string, imports = MigrationWriter.serialize("foo\nbar")
        self.assertEqual(string, "'foo\\nbar'")

    def test_serialize_collections(self):
        """
        Test serialization of various collection types to ensure correct output.

        This test case covers serialization of dictionaries, lists, sets, and nested collections, 
        as well as translatable strings, verifying that the output matches the expected result.
        """
        self.assertSerializedEqual({1: 2})
        self.assertSerializedEqual(["a", 2, True, None])
        self.assertSerializedEqual({2, 3, "eighty"})
        self.assertSerializedEqual({"lalalala": ["yeah", "no", "maybe"]})
        self.assertSerializedEqual(_("Hello"))

    def test_serialize_builtin_types(self):
        """

        Verify the serialization of built-in Python types.

        This test case checks that the following types can be correctly serialized and deserialized:
        - Lists
        - Tuples
        - Dictionaries
        - Sets
        - Frozen sets

        It ensures that the serialized output is as expected and that the deserialized result matches the original data.

        """
        self.assertSerializedEqual([list, tuple, dict, set, frozenset])
        self.assertSerializedResultEqual(
            [list, tuple, dict, set, frozenset],
            ("[list, tuple, dict, set, frozenset]", set()),
        )

    def test_serialize_lazy_objects(self):
        pattern = re.compile(r"^foo$")
        lazy_pattern = SimpleLazyObject(lambda: pattern)
        self.assertEqual(self.serialize_round_trip(lazy_pattern), pattern)

    def test_serialize_enums(self):
        """
        Tests the serialization of various types of enum fields.

        Verifies that TextEnum, TextTranslatedEnum, BinaryEnum, and IntEnum can be properly
        serialized to string representations, including default values and choices.
        Additionally, tests the serialization of nested enums and field serialization
        in the context of Django models.

        """
        self.assertSerializedResultEqual(
            TextEnum.A,
            ("migrations.test_writer.TextEnum['A']", {"import migrations.test_writer"}),
        )
        self.assertSerializedResultEqual(
            TextTranslatedEnum.A,
            (
                "migrations.test_writer.TextTranslatedEnum['A']",
                {"import migrations.test_writer"},
            ),
        )
        self.assertSerializedResultEqual(
            BinaryEnum.A,
            (
                "migrations.test_writer.BinaryEnum['A']",
                {"import migrations.test_writer"},
            ),
        )
        self.assertSerializedResultEqual(
            IntEnum.B,
            ("migrations.test_writer.IntEnum['B']", {"import migrations.test_writer"}),
        )
        self.assertSerializedResultEqual(
            self.NestedEnum.A,
            (
                "migrations.test_writer.WriterTests.NestedEnum['A']",
                {"import migrations.test_writer"},
            ),
        )
        self.assertSerializedEqual(self.NestedEnum.A)

        field = models.CharField(
            default=TextEnum.B, choices=[(m.value, m) for m in TextEnum]
        )
        string = MigrationWriter.serialize(field)[0]
        self.assertEqual(
            string,
            "models.CharField(choices=["
            "('a-value', migrations.test_writer.TextEnum['A']), "
            "('value-b', migrations.test_writer.TextEnum['B'])], "
            "default=migrations.test_writer.TextEnum['B'])",
        )
        field = models.CharField(
            default=TextTranslatedEnum.A,
            choices=[(m.value, m) for m in TextTranslatedEnum],
        )
        string = MigrationWriter.serialize(field)[0]
        self.assertEqual(
            string,
            "models.CharField(choices=["
            "('a-value', migrations.test_writer.TextTranslatedEnum['A']), "
            "('value-b', migrations.test_writer.TextTranslatedEnum['B'])], "
            "default=migrations.test_writer.TextTranslatedEnum['A'])",
        )
        field = models.CharField(
            default=BinaryEnum.B, choices=[(m.value, m) for m in BinaryEnum]
        )
        string = MigrationWriter.serialize(field)[0]
        self.assertEqual(
            string,
            "models.CharField(choices=["
            "(b'a-value', migrations.test_writer.BinaryEnum['A']), "
            "(b'value-b', migrations.test_writer.BinaryEnum['B'])], "
            "default=migrations.test_writer.BinaryEnum['B'])",
        )
        field = models.IntegerField(
            default=IntEnum.A, choices=[(m.value, m) for m in IntEnum]
        )
        string = MigrationWriter.serialize(field)[0]
        self.assertEqual(
            string,
            "models.IntegerField(choices=["
            "(1, migrations.test_writer.IntEnum['A']), "
            "(2, migrations.test_writer.IntEnum['B'])], "
            "default=migrations.test_writer.IntEnum['A'])",
        )

    def test_serialize_enum_flags(self):
        """
        Tests the serialization of IntFlagEnum values and fields.

        Verifies that individual enum flags and their combinations can be correctly
        serialized and represented in a migration. Ensures that the default value and
        choices of an IntegerField using IntFlagEnum are properly serialized.

        Checks the following scenarios:

        * Serialization of individual enum flags
        * Serialization of combined enum flags
        * Serialization of an IntegerField with default value and choices defined using IntFlagEnum
        """
        self.assertSerializedResultEqual(
            IntFlagEnum.A,
            (
                "migrations.test_writer.IntFlagEnum['A']",
                {"import migrations.test_writer"},
            ),
        )
        self.assertSerializedResultEqual(
            IntFlagEnum.B,
            (
                "migrations.test_writer.IntFlagEnum['B']",
                {"import migrations.test_writer"},
            ),
        )
        field = models.IntegerField(
            default=IntFlagEnum.A, choices=[(m.value, m) for m in IntFlagEnum]
        )
        string = MigrationWriter.serialize(field)[0]
        self.assertEqual(
            string,
            "models.IntegerField(choices=["
            "(1, migrations.test_writer.IntFlagEnum['A']), "
            "(2, migrations.test_writer.IntFlagEnum['B'])], "
            "default=migrations.test_writer.IntFlagEnum['A'])",
        )
        self.assertSerializedResultEqual(
            IntFlagEnum.A | IntFlagEnum.B,
            (
                "migrations.test_writer.IntFlagEnum['A'] | "
                "migrations.test_writer.IntFlagEnum['B']",
                {"import migrations.test_writer"},
            ),
        )

    def test_serialize_choices(self):
        class TextChoices(models.TextChoices):
            A = "A", "A value"
            B = "B", "B value"

        class IntegerChoices(models.IntegerChoices):
            A = 1, "One"
            B = 2, "Two"

        class DateChoices(datetime.date, models.Choices):
            DATE_1 = 1969, 7, 20, "First date"
            DATE_2 = 1969, 11, 19, "Second date"

        self.assertSerializedResultEqual(TextChoices.A, ("'A'", set()))
        self.assertSerializedResultEqual(IntegerChoices.A, ("1", set()))
        self.assertSerializedResultEqual(
            DateChoices.DATE_1,
            ("datetime.date(1969, 7, 20)", {"import datetime"}),
        )
        field = models.CharField(default=TextChoices.B, choices=TextChoices)
        string = MigrationWriter.serialize(field)[0]
        self.assertEqual(
            string,
            "models.CharField(choices=[('A', 'A value'), ('B', 'B value')], "
            "default='B')",
        )
        field = models.IntegerField(default=IntegerChoices.B, choices=IntegerChoices)
        string = MigrationWriter.serialize(field)[0]
        self.assertEqual(
            string,
            "models.IntegerField(choices=[(1, 'One'), (2, 'Two')], default=2)",
        )
        field = models.DateField(default=DateChoices.DATE_2, choices=DateChoices)
        string = MigrationWriter.serialize(field)[0]
        self.assertEqual(
            string,
            "models.DateField(choices=["
            "(datetime.date(1969, 7, 20), 'First date'), "
            "(datetime.date(1969, 11, 19), 'Second date')], "
            "default=datetime.date(1969, 11, 19))",
        )

    def test_serialize_dictionary_choices(self):
        for choices in ({"Group": [(2, "2"), (1, "1")]}, {"Group": {2: "2", 1: "1"}}):
            with self.subTest(choices):
                field = models.IntegerField(choices=choices)
                string = MigrationWriter.serialize(field)[0]
                self.assertEqual(
                    string,
                    "models.IntegerField(choices=[('Group', [(2, '2'), (1, '1')])])",
                )

    def test_serialize_callable_choices(self):
        """

        Tests the serialization of a field with callable choices.

        This tests ensures that when a field has choices defined by a callable,
        the migration writer correctly serializes it to a string, including the
        fully qualified name of the callable.

        """
        field = models.IntegerField(choices=get_choices)
        string = MigrationWriter.serialize(field)[0]
        self.assertEqual(
            string,
            "models.IntegerField(choices=migrations.test_writer.get_choices)",
        )

    def test_serialize_nested_class(self):
        """

        Tests the serialization of nested classes.

        This test ensures that nested classes are properly serialized by checking the
        output against the expected result. It covers the serialization of both
        NestedEnum and NestedChoices classes.

        The test iterates over each nested class, asserting that the serialized result
        matches the expected output, which includes the fully qualified name of the
        class and the necessary import statement.

        """
        for nested_cls in [self.NestedEnum, self.NestedChoices]:
            cls_name = nested_cls.__name__
            with self.subTest(cls_name):
                self.assertSerializedResultEqual(
                    nested_cls,
                    (
                        "migrations.test_writer.WriterTests.%s" % cls_name,
                        {"import migrations.test_writer"},
                    ),
                )

    def test_serialize_nested_class_method(self):
        self.assertSerializedResultEqual(
            self.NestedChoices.method,
            (
                "migrations.test_writer.WriterTests.NestedChoices.method",
                {"import migrations.test_writer"},
            ),
        )

    def test_serialize_uuid(self):
        """
        Tests the serialization of UUID objects, including UUID1, UUID4, and specific predefined UUIDs.

        The test covers the serialization of UUIDs in various contexts, such as in isolation and as part of a database field with choices.

        It verifies that the serialized output matches the expected string representation of the UUIDs, including any required import statements.

        Additionally, the test checks the serialization of a UUIDField from a database model, ensuring that the choices and default value are correctly represented in the serialized output.
        """
        self.assertSerializedEqual(uuid.uuid1())
        self.assertSerializedEqual(uuid.uuid4())

        uuid_a = uuid.UUID("5c859437-d061-4847-b3f7-e6b78852f8c8")
        uuid_b = uuid.UUID("c7853ec1-2ea3-4359-b02d-b54e8f1bcee2")
        self.assertSerializedResultEqual(
            uuid_a,
            ("uuid.UUID('5c859437-d061-4847-b3f7-e6b78852f8c8')", {"import uuid"}),
        )
        self.assertSerializedResultEqual(
            uuid_b,
            ("uuid.UUID('c7853ec1-2ea3-4359-b02d-b54e8f1bcee2')", {"import uuid"}),
        )

        field = models.UUIDField(
            choices=((uuid_a, "UUID A"), (uuid_b, "UUID B")), default=uuid_a
        )
        string = MigrationWriter.serialize(field)[0]
        self.assertEqual(
            string,
            "models.UUIDField(choices=["
            "(uuid.UUID('5c859437-d061-4847-b3f7-e6b78852f8c8'), 'UUID A'), "
            "(uuid.UUID('c7853ec1-2ea3-4359-b02d-b54e8f1bcee2'), 'UUID B')], "
            "default=uuid.UUID('5c859437-d061-4847-b3f7-e6b78852f8c8'))",
        )

    def test_serialize_pathlib(self):
        # Pure path objects work in all platforms.
        """

        Tests the serialization of pathlib objects.

        This test case checks that PurePosixPath, PureWindowsPath, WindowsPath, and PosixPath objects can be properly serialized.
        It verifies that the serialized output matches the expected string representation of the path, and that the necessary imports are included.
        The test also covers both Unix and Windows paths, and checks that the serialization works correctly for both absolute and relative paths.
        Additionally, it tests the serialization of FilePathField objects that use pathlib objects as their path attribute.

        """
        self.assertSerializedEqual(pathlib.PurePosixPath())
        self.assertSerializedEqual(pathlib.PureWindowsPath())
        path = pathlib.PurePosixPath("/path/file.txt")
        expected = ("pathlib.PurePosixPath('/path/file.txt')", {"import pathlib"})
        self.assertSerializedResultEqual(path, expected)
        path = pathlib.PureWindowsPath("A:\\File.txt")
        expected = ("pathlib.PureWindowsPath('A:/File.txt')", {"import pathlib"})
        self.assertSerializedResultEqual(path, expected)
        # Concrete path objects work on supported platforms.
        if sys.platform == "win32":
            self.assertSerializedEqual(pathlib.WindowsPath.cwd())
            path = pathlib.WindowsPath("A:\\File.txt")
            expected = ("pathlib.PureWindowsPath('A:/File.txt')", {"import pathlib"})
            self.assertSerializedResultEqual(path, expected)
        else:
            self.assertSerializedEqual(pathlib.PosixPath.cwd())
            path = pathlib.PosixPath("/path/file.txt")
            expected = ("pathlib.PurePosixPath('/path/file.txt')", {"import pathlib"})
            self.assertSerializedResultEqual(path, expected)

        field = models.FilePathField(path=pathlib.PurePosixPath("/home/user"))
        string, imports = MigrationWriter.serialize(field)
        self.assertEqual(
            string,
            "models.FilePathField(path=pathlib.PurePosixPath('/home/user'))",
        )
        self.assertIn("import pathlib", imports)

    def test_serialize_path_like(self):
        """
        Tests the serialization of a path-like object.

        Verifies that a path-like object, such as one returned by os.scandir, can be correctly
        serialized and represented as a string. The test checks that the serialized result
        matches the expected representation of the path-like object, and that a FilePathField
        created with the path-like object is serialized to the correct string format.

        Ensures that the serialization process handles path-like objects as expected, providing
        a valid string representation that can be used in further processing or storage.
        """
        with os.scandir(os.path.dirname(__file__)) as entries:
            path_like = list(entries)[0]
        expected = (repr(path_like.path), {})
        self.assertSerializedResultEqual(path_like, expected)

        field = models.FilePathField(path=path_like)
        string = MigrationWriter.serialize(field)[0]
        self.assertEqual(string, "models.FilePathField(path=%r)" % path_like.path)

    def test_serialize_functions(self):
        """

        Tests the serialization functionality for functions.

        This test case checks that attempting to serialize a lambda function raises a ValueError,
        while serialization of built-in functions like SET_NULL and SET works correctly.
        It also verifies that the serialized form of SET can be correctly reconstructed
        and that it can be round-tripped without any loss of information.

        It ensures that the serialization process handles these functions as expected,
        providing a solid foundation for reliable data migration and transformation.

        """
        with self.assertRaisesMessage(ValueError, "Cannot serialize function: lambda"):
            self.assertSerializedEqual(lambda x: 42)
        self.assertSerializedEqual(models.SET_NULL)
        string, imports = MigrationWriter.serialize(models.SET(42))
        self.assertEqual(string, "models.SET(42)")
        self.serialize_round_trip(models.SET(42))

    def test_serialize_decorated_functions(self):
        """
        Tests the serialization of functions that have been decorated with various decorators.

        This test case verifies that functions with decorators, such as cache and LRU cache, 
        can be successfully serialized and retain their original behavior.

        The test checks the serialization of multiple decorated functions, 
        including those with custom and built-in decorators, 
        to ensure that the serialization process works correctly in different scenarios.
        """
        self.assertSerializedEqual(function_with_decorator)
        self.assertSerializedEqual(function_with_cache)
        self.assertSerializedEqual(function_with_lru_cache)

    def test_serialize_datetime(self):
        """
        Tests the serialization of various datetime-related objects.

        This test case covers the serialization of different datetime objects, including 
        datetime instances, date instances, time instances, and timezone-aware instances.
        It verifies that these objects are correctly serialized and deserialized, 
        including their import statements, to ensure compatibility and accuracy.

        The test includes various edge cases, such as datetime instances with different 
        timezones and date instances, to ensure the serialization process handles these 
        scenarios correctly.

        The test results are compared to the expected serialized output to ensure that 
        the serialization process produces the correct result, including the necessary 
        import statements for deserialization.
        """
        self.assertSerializedEqual(datetime.datetime.now())
        self.assertSerializedEqual(datetime.datetime.now)
        self.assertSerializedEqual(datetime.datetime.today())
        self.assertSerializedEqual(datetime.datetime.today)
        self.assertSerializedEqual(datetime.date.today())
        self.assertSerializedEqual(datetime.date.today)
        self.assertSerializedEqual(datetime.datetime.now().time())
        self.assertSerializedEqual(
            datetime.datetime(2014, 1, 1, 1, 1, tzinfo=get_default_timezone())
        )
        self.assertSerializedEqual(
            datetime.datetime(2013, 12, 31, 22, 1, tzinfo=get_fixed_timezone(180))
        )
        self.assertSerializedResultEqual(
            datetime.datetime(2014, 1, 1, 1, 1),
            ("datetime.datetime(2014, 1, 1, 1, 1)", {"import datetime"}),
        )
        self.assertSerializedResultEqual(
            datetime.datetime(2012, 1, 1, 1, 1, tzinfo=datetime.timezone.utc),
            (
                "datetime.datetime(2012, 1, 1, 1, 1, tzinfo=datetime.timezone.utc)",
                {"import datetime"},
            ),
        )
        self.assertSerializedResultEqual(
            datetime.datetime(
                2012, 1, 1, 2, 1, tzinfo=zoneinfo.ZoneInfo("Europe/Paris")
            ),
            (
                "datetime.datetime(2012, 1, 1, 1, 1, tzinfo=datetime.timezone.utc)",
                {"import datetime"},
            ),
        )

    def test_serialize_fields(self):
        self.assertSerializedFieldEqual(models.CharField(max_length=255))
        self.assertSerializedResultEqual(
            models.CharField(max_length=255),
            ("models.CharField(max_length=255)", {"from django.db import models"}),
        )
        self.assertSerializedFieldEqual(models.TextField(null=True, blank=True))
        self.assertSerializedResultEqual(
            models.TextField(null=True, blank=True),
            (
                "models.TextField(blank=True, null=True)",
                {"from django.db import models"},
            ),
        )

    def test_serialize_settings(self):
        """
        Tests the serialization of settings references.

        The function checks that settings references are correctly serialized, 
        ensuring that the reference to the auth user model is properly handled, 
        and that imports are generated as needed. This is done by comparing the 
        serialized output with the expected results.
        """
        self.assertSerializedEqual(
            SettingsReference(settings.AUTH_USER_MODEL, "AUTH_USER_MODEL")
        )
        self.assertSerializedResultEqual(
            SettingsReference("someapp.model", "AUTH_USER_MODEL"),
            ("settings.AUTH_USER_MODEL", {"from django.conf import settings"}),
        )

    def test_serialize_iterators(self):
        self.assertSerializedResultEqual(
            ((x, x * x) for x in range(3)), ("((0, 0), (1, 1), (2, 4))", set())
        )

    def test_serialize_compiled_regex(self):
        """
        Make sure compiled regex can be serialized.
        """
        regex = re.compile(r"^\w+$")
        self.assertSerializedEqual(regex)

    def test_serialize_class_based_validators(self):
        """
        Ticket #22943: Test serialization of class-based validators, including
        compiled regexes.
        """
        validator = RegexValidator(message="hello")
        string = MigrationWriter.serialize(validator)[0]
        self.assertEqual(
            string, "django.core.validators.RegexValidator(message='hello')"
        )
        self.serialize_round_trip(validator)

        # Test with a compiled regex.
        validator = RegexValidator(regex=re.compile(r"^\w+$"))
        string = MigrationWriter.serialize(validator)[0]
        self.assertEqual(
            string,
            "django.core.validators.RegexValidator(regex=re.compile('^\\\\w+$'))",
        )
        self.serialize_round_trip(validator)

        # Test a string regex with flag
        validator = RegexValidator(r"^[0-9]+$", flags=re.S)
        string = MigrationWriter.serialize(validator)[0]
        self.assertEqual(
            string,
            "django.core.validators.RegexValidator('^[0-9]+$', "
            "flags=re.RegexFlag['DOTALL'])",
        )
        self.serialize_round_trip(validator)

        # Test message and code
        validator = RegexValidator("^[-a-zA-Z0-9_]+$", "Invalid", "invalid")
        string = MigrationWriter.serialize(validator)[0]
        self.assertEqual(
            string,
            "django.core.validators.RegexValidator('^[-a-zA-Z0-9_]+$', 'Invalid', "
            "'invalid')",
        )
        self.serialize_round_trip(validator)

        # Test with a subclass.
        validator = EmailValidator(message="hello")
        string = MigrationWriter.serialize(validator)[0]
        self.assertEqual(
            string, "django.core.validators.EmailValidator(message='hello')"
        )
        self.serialize_round_trip(validator)

        validator = deconstructible(path="migrations.test_writer.EmailValidator")(
            EmailValidator
        )(message="hello")
        string = MigrationWriter.serialize(validator)[0]
        self.assertEqual(
            string, "migrations.test_writer.EmailValidator(message='hello')"
        )

        validator = deconstructible(path="custom.EmailValidator")(EmailValidator)(
            message="hello"
        )
        with self.assertRaisesMessage(ImportError, "No module named 'custom'"):
            MigrationWriter.serialize(validator)

        validator = deconstructible(path="django.core.validators.EmailValidator2")(
            EmailValidator
        )(message="hello")
        with self.assertRaisesMessage(
            ValueError,
            "Could not find object EmailValidator2 in django.core.validators.",
        ):
            MigrationWriter.serialize(validator)

    def test_serialize_complex_func_index(self):
        """

        Tests the serialization of a complex database index.

        The index is comprised of multiple components, including a function-based index,
        a conditional expression, an expression wrapper with a specific output field,
        and an ordering clause. This test ensures that the MigrationWriter can correctly
        serialize this complex index into a string representation, while also tracking
        the necessary imports.

        """
        index = models.Index(
            models.Func("rating", function="ABS"),
            models.Case(
                models.When(name="special", then=models.Value("X")),
                default=models.Value("other"),
            ),
            models.ExpressionWrapper(
                models.F("pages"),
                output_field=models.IntegerField(),
            ),
            models.OrderBy(models.F("name").desc()),
            name="complex_func_index",
        )
        string, imports = MigrationWriter.serialize(index)
        self.assertEqual(
            string,
            "models.Index(models.Func('rating', function='ABS'), "
            "models.Case(models.When(name='special', then=models.Value('X')), "
            "default=models.Value('other')), "
            "models.ExpressionWrapper("
            "models.F('pages'), output_field=models.IntegerField()), "
            "models.OrderBy(models.OrderBy(models.F('name'), descending=True)), "
            "name='complex_func_index')",
        )
        self.assertEqual(imports, {"from django.db import models"})

    def test_serialize_empty_nonempty_tuple(self):
        """
        Ticket #22679: makemigrations generates invalid code for (an empty
        tuple) default_permissions = ()
        """
        empty_tuple = ()
        one_item_tuple = ("a",)
        many_items_tuple = ("a", "b", "c")
        self.assertSerializedEqual(empty_tuple)
        self.assertSerializedEqual(one_item_tuple)
        self.assertSerializedEqual(many_items_tuple)

    def test_serialize_range(self):
        """
        Tests the serialization of a range object.

        Verifies that the :func:`MigrationWriter.serialize` function correctly converts a range object into a string representation and returns no imports.

        The serialization process is expected to preserve the original range's start and end values, resulting in a string that accurately represents the range.

        This test case ensures the proper functionality of the :func:`MigrationWriter.serialize` method when handling range objects, providing a foundation for reliable serialization of various data types.
        """
        string, imports = MigrationWriter.serialize(range(1, 5))
        self.assertEqual(string, "range(1, 5)")
        self.assertEqual(imports, set())

    def test_serialize_builtins(self):
        """

        Tests the serialization of built-in Python types.

        Verifies that the MigrationWriter can correctly serialize a built-in type, 
        in this case the range type, into its string representation and determines 
        if any additional imports are required for its representation.

        """
        string, imports = MigrationWriter.serialize(range)
        self.assertEqual(string, "range")
        self.assertEqual(imports, set())

    def test_serialize_unbound_method_reference(self):
        """An unbound method used within a class body can be serialized."""
        self.serialize_round_trip(TestModel1.thing)

    def test_serialize_local_function_reference(self):
        """A reference in a local scope can't be serialized."""

        class TestModel2:
            def upload_to(self):
                return "somewhere dynamic"

            thing = models.FileField(upload_to=upload_to)

        with self.assertRaisesMessage(
            ValueError, "Could not find function upload_to in migrations.test_writer"
        ):
            self.serialize_round_trip(TestModel2.thing)

    def test_serialize_managers(self):
        """

        Tests the serialization of various manager instances.

        This test case verifies that different types of managers, including the base Manager class,
        managers created from querysets, and custom managers with varying arguments, can be
        successfully serialized and deserialized to their original state.

        The test covers the serialization of managers in different scenarios, ensuring that the 
        serialization process captures all relevant information, including the manager's class 
        and any provided arguments.

        """
        self.assertSerializedEqual(models.Manager())
        self.assertSerializedResultEqual(
            FoodQuerySet.as_manager(),
            (
                "migrations.models.FoodQuerySet.as_manager()",
                {"import migrations.models"},
            ),
        )
        self.assertSerializedEqual(FoodManager("a", "b"))
        self.assertSerializedEqual(FoodManager("x", "y", c=3, d=4))

    def test_serialize_frozensets(self):
        """
        Tests serialization of frozensets.

        This test checks that empty and non-empty frozensets are correctly serialized.
        It also verifies that the serialized form of a frozenset is consistent, 
        regardless of the order of its elements, and matches the expected output format.
        The test covers various scenarios, including an empty frozenset, a frozenset with a string, 
        and a frozenset with characters in a specific order, to ensure robust serialization support.
        """
        self.assertSerializedEqual(frozenset())
        self.assertSerializedEqual(frozenset("let it go"))
        self.assertSerializedResultEqual(
            frozenset("cba"), ("frozenset(['a', 'b', 'c'])", set())
        )

    def test_serialize_set(self):
        self.assertSerializedEqual(set())
        self.assertSerializedResultEqual(set(), ("set()", set()))
        self.assertSerializedEqual({"a"})
        self.assertSerializedResultEqual({"a"}, ("{'a'}", set()))
        self.assertSerializedEqual({"c", "b", "a"})
        self.assertSerializedResultEqual({"c", "b", "a"}, ("{'a', 'b', 'c'}", set()))

    def test_serialize_timedelta(self):
        self.assertSerializedEqual(datetime.timedelta())
        self.assertSerializedEqual(datetime.timedelta(minutes=42))

    def test_serialize_functools_partial(self):
        """

        Tests the serialization of a functools.partial object.

        This test case verifies that a functools.partial object, created with a timedelta function,
        is correctly serialized and deserialized, preserving its original function, arguments, and keyword arguments.

        """
        value = functools.partial(datetime.timedelta, 1, seconds=2)
        result = self.serialize_round_trip(value)
        self.assertEqual(result.func, value.func)
        self.assertEqual(result.args, value.args)
        self.assertEqual(result.keywords, value.keywords)

    def test_serialize_functools_partialmethod(self):
        """
        Tests the serialization and deserialization of a functools.partialmethod object.

        Verifies that the serialization and round-trip deserialization process preserves the original functools.partialmethod object's attributes, including the wrapped function, positional arguments, and keyword arguments.

        This test ensures that the serialization mechanism correctly handles partialmethod objects and that the deserialized result is functionally equivalent to the original object.
        """
        value = functools.partialmethod(datetime.timedelta, 1, seconds=2)
        result = self.serialize_round_trip(value)
        self.assertIsInstance(result, functools.partialmethod)
        self.assertEqual(result.func, value.func)
        self.assertEqual(result.args, value.args)
        self.assertEqual(result.keywords, value.keywords)

    def test_serialize_type_none(self):
        self.assertSerializedEqual(NoneType)

    def test_serialize_type_model(self):
        """

        Tests the serialization of the Model type from Django.

        This test case verifies that the Model class from Django's db module can be correctly serialized.
        It checks that the serialized representation of the Model class matches the expected output and that the serialization process produces the correct imports and dependencies.

        The test covers the following aspects:
        - The Model class can be successfully serialized.
        - The serialized output includes the correct import statement for the Model class.
        - The serialization process correctly identifies and includes any dependencies required by the Model class.

        """
        self.assertSerializedEqual(models.Model)
        self.assertSerializedResultEqual(
            MigrationWriter.serialize(models.Model),
            ("('models.Model', {'from django.db import models'})", set()),
        )

    def test_simple_migration(self):
        """
        Tests serializing a simple migration.
        """
        fields = {
            "charfield": models.DateTimeField(default=datetime.datetime.now),
            "datetimefield": models.DateTimeField(default=datetime.datetime.now),
        }

        options = {
            "verbose_name": "My model",
            "verbose_name_plural": "My models",
        }

        migration = type(
            "Migration",
            (migrations.Migration,),
            {
                "operations": [
                    migrations.CreateModel(
                        "MyModel", tuple(fields.items()), options, (models.Model,)
                    ),
                    migrations.CreateModel(
                        "MyModel2", tuple(fields.items()), bases=(models.Model,)
                    ),
                    migrations.CreateModel(
                        name="MyModel3",
                        fields=tuple(fields.items()),
                        options=options,
                        bases=(models.Model,),
                    ),
                    migrations.DeleteModel("MyModel"),
                    migrations.AddField(
                        "OtherModel", "datetimefield", fields["datetimefield"]
                    ),
                ],
                "dependencies": [("testapp", "some_other_one")],
            },
        )
        writer = MigrationWriter(migration)
        output = writer.as_string()
        # We don't test the output formatting - that's too fragile.
        # Just make sure it runs for now, and that things look alright.
        result = self.safe_exec(output)
        self.assertIn("Migration", result)

    def test_migration_path(self):
        test_apps = [
            "migrations.migrations_test_apps.normal",
            "migrations.migrations_test_apps.with_package_model",
            "migrations.migrations_test_apps.without_init_file",
        ]

        base_dir = os.path.dirname(os.path.dirname(__file__))

        for app in test_apps:
            with self.modify_settings(INSTALLED_APPS={"append": app}):
                migration = migrations.Migration("0001_initial", app.split(".")[-1])
                expected_path = os.path.join(
                    base_dir, *(app.split(".") + ["migrations", "0001_initial.py"])
                )
                writer = MigrationWriter(migration)
                self.assertEqual(writer.path, expected_path)

    def test_custom_operation(self):
        """
        :param self: Test class instance
        :raises AssertionError: If the custom operation is not correctly generated or executed
        :return: None

        Tests a custom operation in a migration by creating a mock migration, 
        writing it to a string, executing the string, and verifying the result.
        The test checks that the custom operation is correctly generated and 
        executed, and that multiple operations with the same name are handled as expected.
        """
        migration = type(
            "Migration",
            (migrations.Migration,),
            {
                "operations": [
                    custom_migration_operations.operations.TestOperation(),
                    custom_migration_operations.operations.CreateModel(),
                    migrations.CreateModel("MyModel", (), {}, (models.Model,)),
                    custom_migration_operations.more_operations.TestOperation(),
                ],
                "dependencies": [],
            },
        )
        writer = MigrationWriter(migration)
        output = writer.as_string()
        result = self.safe_exec(output)
        self.assertIn("custom_migration_operations", result)
        self.assertNotEqual(
            result["custom_migration_operations"].operations.TestOperation,
            result["custom_migration_operations"].more_operations.TestOperation,
        )

    def test_sorted_dependencies(self):
        """

        Tests that migration dependencies are sorted correctly.

        This test case verifies that the dependencies of a migration are properly ordered
        in the generated migration file. It checks that the dependencies are sorted by
        app name and then by migration name, ensuring that the migration can be applied
        in the correct order.

        """
        migration = type(
            "Migration",
            (migrations.Migration,),
            {
                "operations": [
                    migrations.AddField("mymodel", "myfield", models.IntegerField()),
                ],
                "dependencies": [
                    ("testapp10", "0005_fifth"),
                    ("testapp02", "0005_third"),
                    ("testapp02", "0004_sixth"),
                    ("testapp01", "0001_initial"),
                ],
            },
        )
        output = MigrationWriter(migration, include_header=False).as_string()
        self.assertIn(
            "    dependencies = [\n"
            "        ('testapp01', '0001_initial'),\n"
            "        ('testapp02', '0004_sixth'),\n"
            "        ('testapp02', '0005_third'),\n"
            "        ('testapp10', '0005_fifth'),\n"
            "    ]",
            output,
        )

    def test_sorted_imports(self):
        """
        #24155 - Tests ordering of imports.
        """
        migration = type(
            "Migration",
            (migrations.Migration,),
            {
                "operations": [
                    migrations.AddField(
                        "mymodel",
                        "myfield",
                        models.DateTimeField(
                            default=datetime.datetime(
                                2012, 1, 1, 1, 1, tzinfo=datetime.timezone.utc
                            ),
                        ),
                    ),
                    migrations.AddField(
                        "mymodel",
                        "myfield2",
                        models.FloatField(default=time.time),
                    ),
                ]
            },
        )
        writer = MigrationWriter(migration)
        output = writer.as_string()
        self.assertIn(
            "import datetime\nimport time\nfrom django.db import migrations, models\n",
            output,
        )

    def test_migration_file_header_comments(self):
        """
        Test comments at top of file.
        """
        migration = type("Migration", (migrations.Migration,), {"operations": []})
        dt = datetime.datetime(2015, 7, 31, 4, 40, 0, 0, tzinfo=datetime.timezone.utc)
        with mock.patch("django.db.migrations.writer.now", lambda: dt):
            for include_header in (True, False):
                with self.subTest(include_header=include_header):
                    writer = MigrationWriter(migration, include_header)
                    output = writer.as_string()

                    self.assertEqual(
                        include_header,
                        output.startswith(
                            "# Generated by Django %s on 2015-07-31 04:40\n\n"
                            % get_version()
                        ),
                    )
                    if not include_header:
                        # Make sure the output starts with something that's not
                        # a comment or indentation or blank line
                        self.assertRegex(
                            output.splitlines(keepends=True)[0], r"^[^#\s]+"
                        )

    def test_models_import_omitted(self):
        """
        django.db.models shouldn't be imported if unused.
        """
        migration = type(
            "Migration",
            (migrations.Migration,),
            {
                "operations": [
                    migrations.AlterModelOptions(
                        name="model",
                        options={
                            "verbose_name": "model",
                            "verbose_name_plural": "models",
                        },
                    ),
                ]
            },
        )
        writer = MigrationWriter(migration)
        output = writer.as_string()
        self.assertIn("from django.db import migrations\n", output)

    def test_deconstruct_class_arguments(self):
        # Yes, it doesn't make sense to use a class as a default for a
        # CharField. It does make sense for custom fields though, for example
        # an enumfield that takes the enum class as an argument.
        """
        Tests whether the :meth:`MigrationWriter.serialize` method correctly deconstructs class arguments.

        This test case verifies that when serializing a :class:`CharField` model field with a default value set to an instance of :class:`DeconstructibleInstances`, the resulting string representation matches the expected output.

        The purpose of this test is to ensure that the :class:`MigrationWriter` can properly handle class instances as default values and reconstruct them correctly for migration purposes.
        """
        string = MigrationWriter.serialize(
            models.CharField(default=DeconstructibleInstances)
        )[0]
        self.assertEqual(
            string,
            "models.CharField(default=migrations.test_writer.DeconstructibleInstances)",
        )

    def test_register_serializer(self):
        class ComplexSerializer(BaseSerializer):
            def serialize(self):
                return "complex(%r)" % self.value, {}

        MigrationWriter.register_serializer(complex, ComplexSerializer)
        self.assertSerializedEqual(complex(1, 2))
        MigrationWriter.unregister_serializer(complex)
        with self.assertRaisesMessage(ValueError, "Cannot serialize: (1+2j)"):
            self.assertSerializedEqual(complex(1, 2))

    def test_register_non_serializer(self):
        """
        Tests the registration of a non-serializer class with the MigrationWriter.

        This test case verifies that attempting to register a class that does not inherit 
        from BaseSerializer raises a ValueError with an informative error message.

        The error is expected to occur when trying to register TestModel1, which is not 
        a valid serializer, with the MigrationWriter using the complex data type.

        Raises:
            ValueError: If the registered class does not inherit from BaseSerializer.

        """
        with self.assertRaisesMessage(
            ValueError, "'TestModel1' must inherit from 'BaseSerializer'."
        ):
            MigrationWriter.register_serializer(complex, TestModel1)
