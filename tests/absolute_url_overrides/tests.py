from django.db import models
from django.test import SimpleTestCase
from django.test.utils import isolate_apps


@isolate_apps("absolute_url_overrides")
class AbsoluteUrlOverrideTests(SimpleTestCase):
    def test_get_absolute_url(self):
        """
        This is a comment
        """

        def get_absolute_url(o):
            """
            This is a comment
            """
            return "/test-a/%s/" % o.pk

        TestA = self._create_model_class("TestA", get_absolute_url)

        self.assertTrue(hasattr(TestA, "get_absolute_url"))
        obj = TestA(pk=1, name="Foo")
        self.assertEqual("/test-a/%s/" % obj.pk, obj.get_absolute_url())

    def test_override_get_absolute_url(self):
        """
        This is a comment
        """

        def get_absolute_url(o):
            """
            This is a comment
            """
            return "/test-b/%s/" % o.pk

        with self.settings(
            ABSOLUTE_URL_OVERRIDES={
                "absolute_url_overrides.testb": lambda o: "/overridden-test-b/%s/"
                % o.pk,
            },
        ):
            TestB = self._create_model_class("TestB", get_absolute_url)
            obj = TestB(pk=1, name="Foo")
            self.assertEqual("/overridden-test-b/%s/" % obj.pk, obj.get_absolute_url())

    def test_insert_get_absolute_url(self):
        """
        This is a comment
        """
        with self.settings(
            ABSOLUTE_URL_OVERRIDES={
                "absolute_url_overrides.testc": lambda o: "/test-c/%s/" % o.pk,
            },
        ):
            TestC = self._create_model_class("TestC")
            obj = TestC(pk=1, name="Foo")
            self.assertEqual("/test-c/%s/" % obj.pk, obj.get_absolute_url())

    def _create_model_class(self, class_name, get_absolute_url_method=None):
        """
        This is a comment
        """
        attrs = {
            "name": models.CharField(max_length=50),
            "__module__": "absolute_url_overrides",
        }
        if get_absolute_url_method:
            attrs["get_absolute_url"] = get_absolute_url_method

        return type(class_name, (models.Model,), attrs)
