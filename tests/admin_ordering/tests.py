from django.contrib import admin
from django.contrib.admin.options import ModelAdmin
from django.contrib.auth.models import User
from django.db.models import F
from django.test import RequestFactory, TestCase

from .models import (
    Band,
    DynOrderingBandAdmin,
    Song,
    SongInlineDefaultOrdering,
    SongInlineNewOrdering,
)


class MockRequest:
    pass


class MockSuperUser:
    def has_perm(self, perm, obj=None):
        return True

    def has_module_perms(self, module):
        return True


request = MockRequest()
request.user = MockSuperUser()

site = admin.AdminSite()


class TestAdminOrdering(TestCase):
    """
    Let's make sure that ModelAdmin.get_queryset uses the ordering we define
    in ModelAdmin rather that ordering defined in the model's inner Meta
    class.
    """

    request_factory = RequestFactory()

    @classmethod
    def setUpTestData(cls):
        Band.objects.bulk_create(
            [
                Band(name="Aerosmith", bio="", rank=3),
                Band(name="Radiohead", bio="", rank=1),
                Band(name="Van Halen", bio="", rank=2),
            ]
        )

    def test_default_ordering(self):
        """
        The default ordering should be by name, as specified in the inner Meta
        class.
        """
        ma = ModelAdmin(Band, site)
        names = [b.name for b in ma.get_queryset(request)]
        self.assertEqual(["Aerosmith", "Radiohead", "Van Halen"], names)

    def test_specified_ordering(self):
        """
        Let's use a custom ModelAdmin that changes the ordering, and make sure
        it actually changes.
        """

        class BandAdmin(ModelAdmin):
            ordering = ("rank",)  # default ordering is ('name',)

        ma = BandAdmin(Band, site)
        names = [b.name for b in ma.get_queryset(request)]
        self.assertEqual(["Radiohead", "Van Halen", "Aerosmith"], names)

    def test_specified_ordering_by_f_expression(self):
        """

        Tests that the BandAdmin class correctly orders bands in descending order by rank, 
        with null values placed last, and verifies that the resulting queryset returns the 
        expected band names in the specified order.

        """
        class BandAdmin(ModelAdmin):
            ordering = (F("rank").desc(nulls_last=True),)

        band_admin = BandAdmin(Band, site)
        names = [b.name for b in band_admin.get_queryset(request)]
        self.assertEqual(["Aerosmith", "Van Halen", "Radiohead"], names)

    def test_dynamic_ordering(self):
        """
        Let's use a custom ModelAdmin that changes the ordering dynamically.
        """
        super_user = User.objects.create(username="admin", is_superuser=True)
        other_user = User.objects.create(username="other")
        request = self.request_factory.get("/")
        request.user = super_user
        ma = DynOrderingBandAdmin(Band, site)
        names = [b.name for b in ma.get_queryset(request)]
        self.assertEqual(["Radiohead", "Van Halen", "Aerosmith"], names)
        request.user = other_user
        names = [b.name for b in ma.get_queryset(request)]
        self.assertEqual(["Aerosmith", "Radiohead", "Van Halen"], names)


class TestInlineModelAdminOrdering(TestCase):
    """
    Let's make sure that InlineModelAdmin.get_queryset uses the ordering we
    define in InlineModelAdmin.
    """

    @classmethod
    def setUpTestData(cls):
        cls.band = Band.objects.create(name="Aerosmith", bio="", rank=3)
        Song.objects.bulk_create(
            [
                Song(band=cls.band, name="Pink", duration=235),
                Song(band=cls.band, name="Dude (Looks Like a Lady)", duration=264),
                Song(band=cls.band, name="Jaded", duration=214),
            ]
        )

    def test_default_ordering(self):
        """
        The default ordering should be by name, as specified in the inner Meta
        class.
        """
        inline = SongInlineDefaultOrdering(self.band, site)
        names = [s.name for s in inline.get_queryset(request)]
        self.assertEqual(["Dude (Looks Like a Lady)", "Jaded", "Pink"], names)

    def test_specified_ordering(self):
        """
        Let's check with ordering set to something different than the default.
        """
        inline = SongInlineNewOrdering(self.band, site)
        names = [s.name for s in inline.get_queryset(request)]
        self.assertEqual(["Jaded", "Pink", "Dude (Looks Like a Lady)"], names)


class TestRelatedFieldsAdminOrdering(TestCase):
    @classmethod
    def setUpTestData(cls):
        """

        Sets up test data for the class.

        This class method creates two instances of Band objects in the database,
        representing \"Pink Floyd\" and \"Foo Fighters\", with initial ranking values.
        These instances are stored as class attributes, making them accessible throughout the test suite.

        The created bands serve as defaults for testing purposes, providing a basic setup
        for testing scenarios that require band data.

        """
        cls.b1 = Band.objects.create(name="Pink Floyd", bio="", rank=1)
        cls.b2 = Band.objects.create(name="Foo Fighters", bio="", rank=5)

    def setUp(self):
        # we need to register a custom ModelAdmin (instead of just using
        # ModelAdmin) because the field creator tries to find the ModelAdmin
        # for the related model
        class SongAdmin(admin.ModelAdmin):
            pass

        site.register(Song, SongAdmin)

    def tearDown(self):
        """

        Reverses any registrations made during testing to restore the site to its original state.

        This function unregisters the Song model, ensuring it is no longer recognized by the site.
        Additionally, it checks if the Band model is registered and unregisters it if necessary,
        preventing any potential conflicts or side effects in subsequent tests.

        """
        site.unregister(Song)
        if site.is_registered(Band):
            site.unregister(Band)

    def check_ordering_of_field_choices(self, correct_ordering):
        """
        Checks if the choices for foreign key and many-to-many fields are in the correct order.

        Parameters
        ----------
        correct_ordering : list
            The expected ordering of the field choices.

        Notes
        -----
        This method verifies that the available choices for the foreign key field 'band' and the many-to-many field 'other_interpreters' in the Song model are ordered as specified in `correct_ordering`. The check is performed by comparing the querysets of the form fields with the expected ordering.
        """
        fk_field = site.get_model_admin(Song).formfield_for_foreignkey(
            Song.band.field, request=None
        )
        m2m_field = site.get_model_admin(Song).formfield_for_manytomany(
            Song.other_interpreters.field, request=None
        )
        self.assertEqual(list(fk_field.queryset), correct_ordering)
        self.assertEqual(list(m2m_field.queryset), correct_ordering)

    def test_no_admin_fallback_to_model_ordering(self):
        # should be ordered by name (as defined by the model)
        self.check_ordering_of_field_choices([self.b2, self.b1])

    def test_admin_with_no_ordering_fallback_to_model_ordering(self):
        """
        Tests that the admin interface for a model with no explicit ordering defined 
        falls back to using the model's default ordering. 

        This test case verifies that the ordering of choices for a model in the admin 
        interface is correct when no custom ordering is specified in the admin class. 
        In this scenario, the model's metaclass ordering is used as a fallback. 

        The test checks the ordering of field choices to ensure that they match the 
        expected order, providing confidence that the admin interface behaves as 
        expected even when no explicit ordering is defined.
        """
        class NoOrderingBandAdmin(admin.ModelAdmin):
            pass

        site.register(Band, NoOrderingBandAdmin)

        # should be ordered by name (as defined by the model)
        self.check_ordering_of_field_choices([self.b2, self.b1])

    def test_admin_ordering_beats_model_ordering(self):
        """
        Tests that admin ordering takes precedence over model ordering when displaying field choices.

        This test case verifies that when a model has a default ordering and an admin interface is configured with a custom ordering, 
        the admin ordering is used instead of the model's ordering when presenting field choices. 

        The test checks the ordering of field choices for a specific model, ensuring that the admin ordering beats the model ordering.

        """
        class StaticOrderingBandAdmin(admin.ModelAdmin):
            ordering = ("rank",)

        site.register(Band, StaticOrderingBandAdmin)

        # should be ordered by rank (defined by the ModelAdmin)
        self.check_ordering_of_field_choices([self.b1, self.b2])

    def test_custom_queryset_still_wins(self):
        """Custom queryset has still precedence (#21405)"""

        class SongAdmin(admin.ModelAdmin):
            # Exclude one of the two Bands from the querysets
            def formfield_for_foreignkey(self, db_field, request, **kwargs):
                """
                (def formfield_for_foreignkey(self, db_field, request, **kwargs): 
                    Forms a widget for foreign key model fields for use in forms.

                    This method extends the default behavior by filtering foreign key choices 
                    for specific fields. For the 'band' field, it restricts the choices to bands 
                    with a rank greater than 2, allowing more fine-grained control over the 
                    available options. The filtered choices are then passed to the parent 
                    class's implementation for further processing and rendering.

                    :param db_field: The model field for which to generate the form field.
                    :param request: The current request object.
                    :param kwargs: Additional keyword arguments to customize the form field.
                    :return: The generated form field instance.)
                """
                if db_field.name == "band":
                    kwargs["queryset"] = Band.objects.filter(rank__gt=2)
                return super().formfield_for_foreignkey(db_field, request, **kwargs)

            def formfield_for_manytomany(self, db_field, request, **kwargs):
                if db_field.name == "other_interpreters":
                    kwargs["queryset"] = Band.objects.filter(rank__gt=2)
                return super().formfield_for_foreignkey(db_field, request, **kwargs)

        class StaticOrderingBandAdmin(admin.ModelAdmin):
            ordering = ("rank",)

        site.unregister(Song)
        site.register(Song, SongAdmin)
        site.register(Band, StaticOrderingBandAdmin)

        self.check_ordering_of_field_choices([self.b2])
