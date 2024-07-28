from django.core import checks
from django.db import models


class ModelRaisingMessages(models.Model):
    @classmethod
    def check(self, **kwargs):
        """
        This is a comment
        """
        return [checks.Warning("A warning")]
