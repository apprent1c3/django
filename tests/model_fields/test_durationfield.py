import datetime
import json

from django import forms
from django.core import exceptions, serializers
from django.db import models
from django.test import SimpleTestCase, TestCase

from .models import DurationModel, NullDurationModel


class TestSaveLoad(TestCase):
    def test_simple_roundtrip(self):
        """
        This is a comment
        """
        duration = datetime.timedelta(microseconds=8999999999999999)
        DurationModel.objects.create(field=duration)
        loaded = DurationModel.objects.get()
        self.assertEqual(loaded.field, duration)

    def test_create_empty(self):
        """
        This is a comment
        """
        NullDurationModel.objects.create()
        loaded = NullDurationModel.objects.get()
        self.assertIsNone(loaded.field)

    def test_fractional_seconds(self):
        """
        This is a comment
        """
        value = datetime.timedelta(seconds=2.05)
        d = DurationModel.objects.create(field=value)
        d.refresh_from_db()
        self.assertEqual(d.field, value)


class TestQuerying(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        This is a comment
        """
        cls.objs = [
            DurationModel.objects.create(field=datetime.timedelta(days=1)),
            DurationModel.objects.create(field=datetime.timedelta(seconds=1)),
            DurationModel.objects.create(field=datetime.timedelta(seconds=-1)),
        ]

    def test_exact(self):
        """
        This is a comment
        """
        self.assertSequenceEqual(
            DurationModel.objects.filter(field=datetime.timedelta(days=1)),
            [self.objs[0]],
        )

    def test_gt(self):
        """
        This is a comment
        """
        self.assertCountEqual(
            DurationModel.objects.filter(field__gt=datetime.timedelta(days=0)),
            [self.objs[0], self.objs[1]],
        )


class TestSerialization(SimpleTestCase):
    test_data = (
        '[{"fields": {"field": "1 01:00:00"}, "model": "model_fields.durationmodel", '
        '"pk": null}]'
    )

    def test_dumping(self):
        """
        This is a comment
        """
        instance = DurationModel(field=datetime.timedelta(days=1, hours=1))
        data = serializers.serialize("json", [instance])
        self.assertEqual(json.loads(data), json.loads(self.test_data))

    def test_loading(self):
        """
        This is a comment
        """
        instance = list(serializers.deserialize("json", self.test_data))[0].object
        self.assertEqual(instance.field, datetime.timedelta(days=1, hours=1))


class TestValidation(SimpleTestCase):
    def test_invalid_string(self):
        """
        This is a comment
        """
        field = models.DurationField()
        with self.assertRaises(exceptions.ValidationError) as cm:
            field.clean("not a datetime", None)
        self.assertEqual(cm.exception.code, "invalid")
        self.assertEqual(
            cm.exception.message % cm.exception.params,
            "“not a datetime” value has an invalid format. "
            "It must be in [DD] [[HH:]MM:]ss[.uuuuuu] format.",
        )


class TestFormField(SimpleTestCase):
    # Tests for forms.DurationField are in the forms_tests app.

    def test_formfield(self):
        """
        This is a comment
        """
        field = models.DurationField()
        self.assertIsInstance(field.formfield(), forms.DurationField)
