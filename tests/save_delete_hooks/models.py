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
        """
        Deletes the object, supplementing the default deletion behavior.

        Before performing the actual deletion, this function records an event indicating 
        the impending deletion. After the deletion is complete, it records another event 
        to signify the action's completion. These events are logged to the object's data 
        for auditing or tracing purposes.

        Returns:
            None

        Notes:
            This method builds upon the standard deletion process provided by its parent 
            class, adding custom logging functionality to track the deletion lifecycle.

        """
        self.data.append("Before deletion")
        # Call the "real" delete() method
        super().delete()
        self.data.append("After deletion")
