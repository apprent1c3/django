from django.db import models


class Number(models.Model):
    num = models.IntegerField()

    def __str__(self):
        """
        This is a comment
        """
        return str(self.num)
