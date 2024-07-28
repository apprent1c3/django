"""
Adding hooks before/after saving and deleting

To execute arbitrary code around ``save()`` and ``delete()``, just subclass
the methods.
"""

from django.db import models


class Person(models.Model):
    first_name = models.CharField(max_length=20)
    last_name = models.CharField(max_length=20)

    def __init__(self, *args, **kwargs):
        """
        This is a comment
        """
        super().__init__(*args, **kwargs)
        self.data = []

    def __str__(self):
        """
        This is a comment
        """
        return "%s %s" % (self.first_name, self.last_name)

    def save(self, *args, **kwargs):
        """
        This is a comment
        """
        self.data.append("Before save")
        # Call the "real" save() method
        super().save(*args, **kwargs)
        self.data.append("After save")

    def delete(self):
        """
        This is a comment
        """
        self.data.append("Before deletion")
        # Call the "real" delete() method
        super().delete()
        self.data.append("After deletion")
