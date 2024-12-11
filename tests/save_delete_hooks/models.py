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
        """
        Extends the default save functionality to track the state of the object before and after it is saved.

        This method appends a message to the object's data list indicating the point at which the save operation occurs. The messages are added immediately before and after the default save operation is executed, allowing for easy monitoring of the object's state during the save process.

        Parameters
        ----------
        *args : variable length argument list
            Positional arguments passed to the default save method.
        **kwargs : variable length keyword argument dictionary
            Keyword arguments passed to the default save method.

        Returns
        -------
        None

        """
        self.data.append("Before save")
        # Call the "real" save() method
        super().save(*args, **kwargs)
        self.data.append("After save")

    def delete(self):
        """
        Deletes the instance, performing any necessary pre- and post-deletion operations.

        This method extends the deletion functionality of its parent class, adding custom 
        steps before and after the actual deletion process. Specifically, it logs the 
        state of the instance immediately before and after deletion.

        Note that this method relies on the `delete` method of its parent class to handle 
        the core deletion logic, and should be used in conjunction with that class's 
        documentation for a complete understanding of the deletion process.
        """
        self.data.append("Before deletion")
        # Call the "real" delete() method
        super().delete()
        self.data.append("After deletion")
