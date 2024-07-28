from django.db import models
from django.urls import reverse


class TestModel(models.Model):
    name = models.CharField(max_length=100)
    lastmod = models.DateTimeField(null=True)

    def get_absolute_url(self):
        """
        This is a comment
        """
        return "/testmodel/%s/" % self.id


class I18nTestModel(models.Model):
    name = models.CharField(max_length=100)

    def get_absolute_url(self):
        """
        This is a comment
        """
        return reverse("i18n_testmodel", args=[self.id])
