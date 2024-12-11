from django.db import models
from django.test import SimpleTestCase

from .models import AutoModel, BigAutoModel, SmallAutoModel
from .test_integerfield import (
    BigIntegerFieldTests,
    IntegerFieldTests,
    SmallIntegerFieldTests,
)


class AutoFieldTests(IntegerFieldTests):
    model = AutoModel
    rel_db_type_class = models.IntegerField


class BigAutoFieldTests(BigIntegerFieldTests):
    model = BigAutoModel
    rel_db_type_class = models.BigIntegerField


class SmallAutoFieldTests(SmallIntegerFieldTests):
    model = SmallAutoModel
    rel_db_type_class = models.SmallIntegerField


class AutoFieldInheritanceTests(SimpleTestCase):
    def test_isinstance_of_autofield(self):
        for field in (models.BigAutoField, models.SmallAutoField):
            with self.subTest(field.__name__):
                self.assertIsInstance(field(), models.AutoField)

    def test_issubclass_of_autofield(self):
        """
        Tests if various auto field classes are subclasses of the base :class:`models.AutoField` class.

        The function checks the inheritance relationship of different auto field classes, 
        including custom classes that inherit from :class:`models.BigAutoField` and :class:`models.SmallAutoField`, 
        as well as the base :class:`models.BigAutoField` and :class:`models.SmallAutoField` classes themselves.

        It verifies that all these classes are indeed subclasses of :class:`models.AutoField`, 
        ensuring the expected class hierarchy is maintained.
        """
        class MyBigAutoField(models.BigAutoField):
            pass

        class MySmallAutoField(models.SmallAutoField):
            pass

        tests = [
            MyBigAutoField,
            MySmallAutoField,
            models.BigAutoField,
            models.SmallAutoField,
        ]
        for field in tests:
            with self.subTest(field.__name__):
                self.assertTrue(issubclass(field, models.AutoField))
