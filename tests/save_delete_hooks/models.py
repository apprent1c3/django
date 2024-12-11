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
        Initializes the object, setting up its internal state.

        This constructor method is called when an object of the class is instantiated.
        It takes in any number of positional and keyword arguments, which are passed to the parent class's constructor.
        Additionally, it initializes an empty list, `data`, which can be used to store information within the object.

        :param args: Variable number of positional arguments
        :param kwargs: Variable number of keyword arguments
        """
        super().__init__(*args, **kwargs)
        self.data = []

    def __str__(self):
        return "%s %s" % (self.first_name, self.last_name)

    def save(self, *args, **kwargs):
        self.data.append("Before save")
        # Call the "real" save() method
        super().save(*args, **kwargs)
        self.data.append("After save")

    def delete(self):
        self.data.append("Before deletion")
        # Call the "real" delete() method
        super().delete()
        self.data.append("After deletion")
