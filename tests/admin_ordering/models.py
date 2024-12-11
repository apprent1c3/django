from django.contrib import admin
from django.db import models


class Band(models.Model):
    name = models.CharField(max_length=100)
    bio = models.TextField()
    rank = models.IntegerField()

    class Meta:
        ordering = ("name",)


class Song(models.Model):
    band = models.ForeignKey(Band, models.CASCADE)
    name = models.CharField(max_length=100)
    duration = models.IntegerField()
    other_interpreters = models.ManyToManyField(Band, related_name="covers")

    class Meta:
        ordering = ("name",)


class SongInlineDefaultOrdering(admin.StackedInline):
    model = Song


class SongInlineNewOrdering(admin.StackedInline):
    model = Song
    ordering = ("duration",)


class DynOrderingBandAdmin(admin.ModelAdmin):
    def get_ordering(self, request):
        """
        Returns the ordering criteria for a given request.

        The function determines whether the requesting user is a superuser and returns
        the relevant ordering criteria. If the user is a superuser, the ordering is
        based on the 'rank' field, otherwise it is based on the 'name' field.

        :returns: A list of field names to use for ordering
        """
        if request.user.is_superuser:
            return ["rank"]
        else:
            return ["name"]
