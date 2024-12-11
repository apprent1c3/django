from django.contrib import admin

from .models import (
    Advisor,
    Album,
    Band,
    Bee,
    Car,
    CarTire,
    Event,
    Inventory,
    Member,
    Profile,
    ReleaseEvent,
    School,
    Student,
    User,
    VideoStream,
)


class WidgetAdmin(admin.AdminSite):
    pass


class CarAdmin(admin.ModelAdmin):
    list_display = ["make", "model", "owner"]
    list_editable = ["owner"]


class CarTireAdmin(admin.ModelAdmin):
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        Returns a form field for a foreign key relationship, applying specific filtering when the foreign key field is named 'car'. 

        In this case, the function limits the available choices to cars owned by the current user, making it easier to select the correct car when creating or editing a related object. 

        For all other foreign key fields, it falls back to the default behavior, returning a form field without any custom filtering.
        """
        if db_field.name == "car":
            kwargs["queryset"] = Car.objects.filter(owner=request.user)
            return db_field.formfield(**kwargs)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class EventAdmin(admin.ModelAdmin):
    raw_id_fields = ["main_band", "supporting_bands"]


class AlbumAdmin(admin.ModelAdmin):
    fields = (
        "name",
        "cover_art",
    )
    readonly_fields = ("cover_art",)


class SchoolAdmin(admin.ModelAdmin):
    filter_vertical = ("students",)
    filter_horizontal = ("alumni",)


site = WidgetAdmin(name="widget-admin")

site.register(User)
site.register(Car, CarAdmin)
site.register(CarTire, CarTireAdmin)

site.register(Member)
site.register(Band)
site.register(Event, EventAdmin)
site.register(Album, AlbumAdmin)
site.register(ReleaseEvent, search_fields=["name"])
site.register(VideoStream, autocomplete_fields=["release_event"])

site.register(Inventory)

site.register(Bee)

site.register(Advisor)

site.register(School, SchoolAdmin)
site.register(Student)

site.register(Profile)
