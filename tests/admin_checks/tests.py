from django import forms
from django.contrib import admin
from django.contrib.admin import AdminSite
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.middleware import AuthenticationMiddleware
from django.contrib.contenttypes.admin import GenericStackedInline
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.core import checks
from django.test import SimpleTestCase, override_settings

from .models import Album, Author, Book, City, Influence, Song, State, TwoAlbumFKAndAnE


class SongForm(forms.ModelForm):
    pass


class ValidFields(admin.ModelAdmin):
    form = SongForm
    fields = ["title"]


class ValidFormFieldsets(admin.ModelAdmin):
    def get_form(self, request, obj=None, **kwargs):
        """
        This is a comment
        """
        class ExtraFieldForm(SongForm):
            name = forms.CharField(max_length=50)

        return ExtraFieldForm

    fieldsets = (
        (
            None,
            {
                "fields": ("name",),
            },
        ),
    )


class MyAdmin(admin.ModelAdmin):
    def check(self, **kwargs):
        """
        This is a comment
        """
        return ["error!"]


class AuthenticationMiddlewareSubclass(AuthenticationMiddleware):
    pass


class MessageMiddlewareSubclass(MessageMiddleware):
    pass


class ModelBackendSubclass(ModelBackend):
    pass


class SessionMiddlewareSubclass(SessionMiddleware):
    pass


@override_settings(
    SILENCED_SYSTEM_CHECKS=["fields.W342"],  # ForeignKey(unique=True)
    INSTALLED_APPS=[
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.messages",
        "admin_checks",
    ],
)
class SystemChecksTestCase(SimpleTestCase):
    databases = "__all__"

    def test_checks_are_performed(self):
        """
        This is a comment
        """
        admin.site.register(Song, MyAdmin)
        try:
            errors = checks.run_checks()
            expected = ["error!"]
            self.assertEqual(errors, expected)
        finally:
            admin.site.unregister(Song)

    @override_settings(INSTALLED_APPS=["django.contrib.admin"])
    def test_apps_dependencies(self):
        """
        This is a comment
        """
        errors = admin.checks.check_dependencies()
        expected = [
            checks.Error(
                "'django.contrib.contenttypes' must be in "
                "INSTALLED_APPS in order to use the admin application.",
                id="admin.E401",
            ),
            checks.Error(
                "'django.contrib.auth' must be in INSTALLED_APPS in order "
                "to use the admin application.",
                id="admin.E405",
            ),
            checks.Error(
                "'django.contrib.messages' must be in INSTALLED_APPS in order "
                "to use the admin application.",
                id="admin.E406",
            ),
        ]
        self.assertEqual(errors, expected)

    @override_settings(TEMPLATES=[])
    def test_no_template_engines(self):
        """
        This is a comment
        """
        self.assertEqual(
            admin.checks.check_dependencies(),
            [
                checks.Error(
                    "A 'django.template.backends.django.DjangoTemplates' "
                    "instance must be configured in TEMPLATES in order to use "
                    "the admin application.",
                    id="admin.E403",
                )
            ],
        )

    @override_settings(
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [],
                "APP_DIRS": True,
                "OPTIONS": {
                    "context_processors": [],
                },
            }
        ],
    )
    def test_context_processor_dependencies(self):
        """
        This is a comment
        """
        expected = [
            checks.Error(
                "'django.contrib.auth.context_processors.auth' must be "
                "enabled in DjangoTemplates (TEMPLATES) if using the default "
                "auth backend in order to use the admin application.",
                id="admin.E402",
            ),
            checks.Error(
                "'django.contrib.messages.context_processors.messages' must "
                "be enabled in DjangoTemplates (TEMPLATES) in order to use "
                "the admin application.",
                id="admin.E404",
            ),
            checks.Warning(
                "'django.template.context_processors.request' must be enabled "
                "in DjangoTemplates (TEMPLATES) in order to use the admin "
                "navigation sidebar.",
                id="admin.W411",
            ),
        ]
        self.assertEqual(admin.checks.check_dependencies(), expected)
        # The first error doesn't happen if
        # 'django.contrib.auth.backends.ModelBackend' isn't in
        # AUTHENTICATION_BACKENDS.
        with self.settings(AUTHENTICATION_BACKENDS=[]):
            self.assertEqual(admin.checks.check_dependencies(), expected[1:])

    @override_settings(
        AUTHENTICATION_BACKENDS=["admin_checks.tests.ModelBackendSubclass"],
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [],
                "APP_DIRS": True,
                "OPTIONS": {
                    "context_processors": [
                        "django.template.context_processors.request",
                        "django.contrib.messages.context_processors.messages",
                    ],
                },
            }
        ],
    )
    def test_context_processor_dependencies_model_backend_subclass(self):
        """
        This is a comment
        """
        self.assertEqual(
            admin.checks.check_dependencies(),
            [
                checks.Error(
                    "'django.contrib.auth.context_processors.auth' must be "
                    "enabled in DjangoTemplates (TEMPLATES) if using the default "
                    "auth backend in order to use the admin application.",
                    id="admin.E402",
                ),
            ],
        )

    @override_settings(
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.dummy.TemplateStrings",
                "DIRS": [],
                "APP_DIRS": True,
            },
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [],
                "APP_DIRS": True,
                "OPTIONS": {
                    "context_processors": [
                        "django.template.context_processors.request",
                        "django.contrib.auth.context_processors.auth",
                        "django.contrib.messages.context_processors.messages",
                    ],
                },
            },
        ],
    )
    def test_several_templates_backends(self):
        """
        This is a comment
        """
        self.assertEqual(admin.checks.check_dependencies(), [])

    @override_settings(MIDDLEWARE=[])
    def test_middleware_dependencies(self):
        """
        This is a comment
        """
        errors = admin.checks.check_dependencies()
        expected = [
            checks.Error(
                "'django.contrib.auth.middleware.AuthenticationMiddleware' "
                "must be in MIDDLEWARE in order to use the admin application.",
                id="admin.E408",
            ),
            checks.Error(
                "'django.contrib.messages.middleware.MessageMiddleware' "
                "must be in MIDDLEWARE in order to use the admin application.",
                id="admin.E409",
            ),
            checks.Error(
                "'django.contrib.sessions.middleware.SessionMiddleware' "
                "must be in MIDDLEWARE in order to use the admin application.",
                hint=(
                    "Insert "
                    "'django.contrib.sessions.middleware.SessionMiddleware' "
                    "before "
                    "'django.contrib.auth.middleware.AuthenticationMiddleware'."
                ),
                id="admin.E410",
            ),
        ]
        self.assertEqual(errors, expected)

    @override_settings(
        MIDDLEWARE=[
            "admin_checks.tests.AuthenticationMiddlewareSubclass",
            "admin_checks.tests.MessageMiddlewareSubclass",
            "admin_checks.tests.SessionMiddlewareSubclass",
        ]
    )
    def test_middleware_subclasses(self):
        """
        This is a comment
        """
        self.assertEqual(admin.checks.check_dependencies(), [])

    @override_settings(
        MIDDLEWARE=[
            "django.contrib.does.not.Exist",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",
        ]
    )
    def test_admin_check_ignores_import_error_in_middleware(self):
        """
        This is a comment
        """
        self.assertEqual(admin.checks.check_dependencies(), [])

    def test_custom_adminsite(self):
        """
        This is a comment
        """
        class CustomAdminSite(admin.AdminSite):
            pass

        custom_site = CustomAdminSite()
        custom_site.register(Song, MyAdmin)
        try:
            errors = checks.run_checks()
            expected = ["error!"]
            self.assertEqual(errors, expected)
        finally:
            custom_site.unregister(Song)

    def test_allows_checks_relying_on_other_modeladmins(self):
        """
        This is a comment
        """
        class MyBookAdmin(admin.ModelAdmin):
            def check(self, **kwargs):
                """
                This is a comment
                """
                errors = super().check(**kwargs)
                if not self.admin_site.is_registered(Author):
                    errors.append("AuthorAdmin missing!")
                return errors

        class MyAuthorAdmin(admin.ModelAdmin):
            pass

        admin.site.register(Book, MyBookAdmin)
        admin.site.register(Author, MyAuthorAdmin)
        try:
            self.assertEqual(admin.site.check(None), [])
        finally:
            admin.site.unregister(Book)
            admin.site.unregister(Author)

    def test_field_name_not_in_list_display(self):
        """
        This is a comment
        """
        class SongAdmin(admin.ModelAdmin):
            list_editable = ["original_release"]

        errors = SongAdmin(Song, AdminSite()).check()
        expected = [
            checks.Error(
                "The value of 'list_editable[0]' refers to 'original_release', "
                "which is not contained in 'list_display'.",
                obj=SongAdmin,
                id="admin.E122",
            )
        ]
        self.assertEqual(errors, expected)

    def test_list_editable_not_a_list_or_tuple(self):
        """
        This is a comment
        """
        class SongAdmin(admin.ModelAdmin):
            list_editable = "test"

        self.assertEqual(
            SongAdmin(Song, AdminSite()).check(),
            [
                checks.Error(
                    "The value of 'list_editable' must be a list or tuple.",
                    obj=SongAdmin,
                    id="admin.E120",
                )
            ],
        )

    def test_list_editable_missing_field(self):
        """
        This is a comment
        """
        class SongAdmin(admin.ModelAdmin):
            list_editable = ("test",)

        self.assertEqual(
            SongAdmin(Song, AdminSite()).check(),
            [
                checks.Error(
                    "The value of 'list_editable[0]' refers to 'test', which is "
                    "not a field of 'admin_checks.Song'.",
                    obj=SongAdmin,
                    id="admin.E121",
                )
            ],
        )

    def test_readonly_and_editable(self):
        """
        This is a comment
        """
        class SongAdmin(admin.ModelAdmin):
            readonly_fields = ["original_release"]
            list_display = ["pk", "original_release"]
            list_editable = ["original_release"]
            fieldsets = [
                (
                    None,
                    {
                        "fields": ["title", "original_release"],
                    },
                ),
            ]

        errors = SongAdmin(Song, AdminSite()).check()
        expected = [
            checks.Error(
                "The value of 'list_editable[0]' refers to 'original_release', "
                "which is not editable through the admin.",
                obj=SongAdmin,
                id="admin.E125",
            )
        ]
        self.assertEqual(errors, expected)

    def test_pk_not_editable(self):
        # PKs cannot be edited in the list.
        """
        This is a comment
        """
        class SongAdmin(admin.ModelAdmin):
            list_display = ["title", "id"]
            list_editable = ["id"]

        errors = SongAdmin(Song, AdminSite()).check()
        expected = [
            checks.Error(
                "The value of 'list_editable[0]' refers to 'id', which is not editable "
                "through the admin.",
                obj=SongAdmin,
                id="admin.E125",
            )
        ]
        self.assertEqual(errors, expected)

    def test_editable(self):
        """
        This is a comment
        """
        class SongAdmin(admin.ModelAdmin):
            list_display = ["pk", "title"]
            list_editable = ["title"]
            fieldsets = [
                (
                    None,
                    {
                        "fields": ["title", "original_release"],
                    },
                ),
            ]

        errors = SongAdmin(Song, AdminSite()).check()
        self.assertEqual(errors, [])

    def test_custom_modelforms_with_fields_fieldsets(self):
        """
        This is a comment
        """
        errors = ValidFields(Song, AdminSite()).check()
        self.assertEqual(errors, [])

    def test_custom_get_form_with_fieldsets(self):
        """
        This is a comment
        """
        errors = ValidFormFieldsets(Song, AdminSite()).check()
        self.assertEqual(errors, [])

    def test_fieldsets_fields_non_tuple(self):
        """
        This is a comment
        """

        class NotATupleAdmin(admin.ModelAdmin):
            list_display = ["pk", "title"]
            list_editable = ["title"]
            fieldsets = [
                (None, {"fields": "title"}),  # not a tuple
            ]

        errors = NotATupleAdmin(Song, AdminSite()).check()
        expected = [
            checks.Error(
                "The value of 'fieldsets[0][1]['fields']' must be a list or tuple.",
                obj=NotATupleAdmin,
                id="admin.E008",
            )
        ]
        self.assertEqual(errors, expected)

    def test_nonfirst_fieldset(self):
        """
        This is a comment
        """

        class NotATupleAdmin(admin.ModelAdmin):
            fieldsets = [
                (None, {"fields": ("title",)}),
                ("foo", {"fields": "author"}),  # not a tuple
            ]

        errors = NotATupleAdmin(Song, AdminSite()).check()
        expected = [
            checks.Error(
                "The value of 'fieldsets[1][1]['fields']' must be a list or tuple.",
                obj=NotATupleAdmin,
                id="admin.E008",
            )
        ]
        self.assertEqual(errors, expected)

    def test_exclude_values(self):
        """
        This is a comment
        """

        class ExcludedFields1(admin.ModelAdmin):
            exclude = "foo"

        errors = ExcludedFields1(Book, AdminSite()).check()
        expected = [
            checks.Error(
                "The value of 'exclude' must be a list or tuple.",
                obj=ExcludedFields1,
                id="admin.E014",
            )
        ]
        self.assertEqual(errors, expected)

    def test_exclude_duplicate_values(self):
        """
        This is a comment
        """
        class ExcludedFields2(admin.ModelAdmin):
            exclude = ("name", "name")

        errors = ExcludedFields2(Book, AdminSite()).check()
        expected = [
            checks.Error(
                "The value of 'exclude' contains duplicate field(s).",
                obj=ExcludedFields2,
                id="admin.E015",
            )
        ]
        self.assertEqual(errors, expected)

    def test_exclude_in_inline(self):
        """
        This is a comment
        """
        class ExcludedFieldsInline(admin.TabularInline):
            model = Song
            exclude = "foo"

        class ExcludedFieldsAlbumAdmin(admin.ModelAdmin):
            model = Album
            inlines = [ExcludedFieldsInline]

        errors = ExcludedFieldsAlbumAdmin(Album, AdminSite()).check()
        expected = [
            checks.Error(
                "The value of 'exclude' must be a list or tuple.",
                obj=ExcludedFieldsInline,
                id="admin.E014",
            )
        ]
        self.assertEqual(errors, expected)

    def test_exclude_inline_model_admin(self):
        """
        This is a comment
        """

        class SongInline(admin.StackedInline):
            model = Song
            exclude = ["album"]

        class AlbumAdmin(admin.ModelAdmin):
            model = Album
            inlines = [SongInline]

        errors = AlbumAdmin(Album, AdminSite()).check()
        expected = [
            checks.Error(
                "Cannot exclude the field 'album', because it is the foreign key "
                "to the parent model 'admin_checks.Album'.",
                obj=SongInline,
                id="admin.E201",
            )
        ]
        self.assertEqual(errors, expected)

    def test_valid_generic_inline_model_admin(self):
        """
        This is a comment
        """

        class InfluenceInline(GenericStackedInline):
            model = Influence

        class SongAdmin(admin.ModelAdmin):
            inlines = [InfluenceInline]

        errors = SongAdmin(Song, AdminSite()).check()
        self.assertEqual(errors, [])

    def test_generic_inline_model_admin_non_generic_model(self):
        """
        This is a comment
        """

        class BookInline(GenericStackedInline):
            model = Book

        class SongAdmin(admin.ModelAdmin):
            inlines = [BookInline]

        errors = SongAdmin(Song, AdminSite()).check()
        expected = [
            checks.Error(
                "'admin_checks.Book' has no GenericForeignKey.",
                obj=BookInline,
                id="admin.E301",
            )
        ]
        self.assertEqual(errors, expected)

    def test_generic_inline_model_admin_bad_ct_field(self):
        """
        This is a comment
        """

        class InfluenceInline(GenericStackedInline):
            model = Influence
            ct_field = "nonexistent"

        class SongAdmin(admin.ModelAdmin):
            inlines = [InfluenceInline]

        errors = SongAdmin(Song, AdminSite()).check()
        expected = [
            checks.Error(
                "'ct_field' references 'nonexistent', which is not a field on "
                "'admin_checks.Influence'.",
                obj=InfluenceInline,
                id="admin.E302",
            )
        ]
        self.assertEqual(errors, expected)

    def test_generic_inline_model_admin_bad_fk_field(self):
        """
        This is a comment
        """

        class InfluenceInline(GenericStackedInline):
            model = Influence
            ct_fk_field = "nonexistent"

        class SongAdmin(admin.ModelAdmin):
            inlines = [InfluenceInline]

        errors = SongAdmin(Song, AdminSite()).check()
        expected = [
            checks.Error(
                "'ct_fk_field' references 'nonexistent', which is not a field on "
                "'admin_checks.Influence'.",
                obj=InfluenceInline,
                id="admin.E303",
            )
        ]
        self.assertEqual(errors, expected)

    def test_generic_inline_model_admin_non_gfk_ct_field(self):
        """
        This is a comment
        """

        class InfluenceInline(GenericStackedInline):
            model = Influence
            ct_field = "name"

        class SongAdmin(admin.ModelAdmin):
            inlines = [InfluenceInline]

        errors = SongAdmin(Song, AdminSite()).check()
        expected = [
            checks.Error(
                "'admin_checks.Influence' has no GenericForeignKey using "
                "content type field 'name' and object ID field 'object_id'.",
                obj=InfluenceInline,
                id="admin.E304",
            )
        ]
        self.assertEqual(errors, expected)

    def test_generic_inline_model_admin_non_gfk_fk_field(self):
        """
        This is a comment
        """

        class InfluenceInline(GenericStackedInline):
            model = Influence
            ct_fk_field = "name"

        class SongAdmin(admin.ModelAdmin):
            inlines = [InfluenceInline]

        errors = SongAdmin(Song, AdminSite()).check()
        expected = [
            checks.Error(
                "'admin_checks.Influence' has no GenericForeignKey using "
                "content type field 'content_type' and object ID field 'name'.",
                obj=InfluenceInline,
                id="admin.E304",
            )
        ]
        self.assertEqual(errors, expected)

    def test_app_label_in_admin_checks(self):
        """
        This is a comment
        """
        class RawIdNonexistentAdmin(admin.ModelAdmin):
            raw_id_fields = ("nonexistent",)

        errors = RawIdNonexistentAdmin(Album, AdminSite()).check()
        expected = [
            checks.Error(
                "The value of 'raw_id_fields[0]' refers to 'nonexistent', "
                "which is not a field of 'admin_checks.Album'.",
                obj=RawIdNonexistentAdmin,
                id="admin.E002",
            )
        ]
        self.assertEqual(errors, expected)

    def test_fk_exclusion(self):
        """
        This is a comment
        """

        class TwoAlbumFKAndAnEInline(admin.TabularInline):
            model = TwoAlbumFKAndAnE
            exclude = ("e",)
            fk_name = "album1"

        class MyAdmin(admin.ModelAdmin):
            inlines = [TwoAlbumFKAndAnEInline]

        errors = MyAdmin(Album, AdminSite()).check()
        self.assertEqual(errors, [])

    def test_inline_self_check(self):
        """
        This is a comment
        """
        class TwoAlbumFKAndAnEInline(admin.TabularInline):
            model = TwoAlbumFKAndAnE

        class MyAdmin(admin.ModelAdmin):
            inlines = [TwoAlbumFKAndAnEInline]

        errors = MyAdmin(Album, AdminSite()).check()
        expected = [
            checks.Error(
                "'admin_checks.TwoAlbumFKAndAnE' has more than one ForeignKey "
                "to 'admin_checks.Album'. You must specify a 'fk_name' "
                "attribute.",
                obj=TwoAlbumFKAndAnEInline,
                id="admin.E202",
            )
        ]
        self.assertEqual(errors, expected)

    def test_inline_with_specified(self):
        """
        This is a comment
        """
        class TwoAlbumFKAndAnEInline(admin.TabularInline):
            model = TwoAlbumFKAndAnE
            fk_name = "album1"

        class MyAdmin(admin.ModelAdmin):
            inlines = [TwoAlbumFKAndAnEInline]

        errors = MyAdmin(Album, AdminSite()).check()
        self.assertEqual(errors, [])

    def test_inlines_property(self):
        """
        This is a comment
        """
        class CitiesInline(admin.TabularInline):
            model = City

        class StateAdmin(admin.ModelAdmin):
            @property
            def inlines(self):
                """
                This is a comment
                """
                return [CitiesInline]

        errors = StateAdmin(State, AdminSite()).check()
        self.assertEqual(errors, [])

    def test_readonly(self):
        """
        This is a comment
        """
        class SongAdmin(admin.ModelAdmin):
            readonly_fields = ("title",)

        errors = SongAdmin(Song, AdminSite()).check()
        self.assertEqual(errors, [])

    def test_readonly_on_method(self):
        @admin.display
        """
        This is a comment
        """
        def my_function(obj):
            """
            This is a comment
            """
            pass

        class SongAdmin(admin.ModelAdmin):
            readonly_fields = (my_function,)

        errors = SongAdmin(Song, AdminSite()).check()
        self.assertEqual(errors, [])

    def test_readonly_on_modeladmin(self):
        """
        This is a comment
        """
        class SongAdmin(admin.ModelAdmin):
            readonly_fields = ("readonly_method_on_modeladmin",)

            @admin.display
            def readonly_method_on_modeladmin(self, obj):
                """
                This is a comment
                """
                pass

        errors = SongAdmin(Song, AdminSite()).check()
        self.assertEqual(errors, [])

    def test_readonly_dynamic_attribute_on_modeladmin(self):
        """
        This is a comment
        """
        class SongAdmin(admin.ModelAdmin):
            readonly_fields = ("dynamic_method",)

            def __getattr__(self, item):
                """
                This is a comment
                """
                if item == "dynamic_method":

                    @admin.display
                    def method(obj):
                        """
                        This is a comment
                        """
                        pass

                    return method
                raise AttributeError

        errors = SongAdmin(Song, AdminSite()).check()
        self.assertEqual(errors, [])

    def test_readonly_method_on_model(self):
        """
        This is a comment
        """
        class SongAdmin(admin.ModelAdmin):
            readonly_fields = ("readonly_method_on_model",)

        errors = SongAdmin(Song, AdminSite()).check()
        self.assertEqual(errors, [])

    def test_nonexistent_field(self):
        """
        This is a comment
        """
        class SongAdmin(admin.ModelAdmin):
            readonly_fields = ("title", "nonexistent")

        errors = SongAdmin(Song, AdminSite()).check()
        expected = [
            checks.Error(
                "The value of 'readonly_fields[1]' refers to 'nonexistent', which is "
                "not a callable, an attribute of 'SongAdmin', or an attribute of "
                "'admin_checks.Song'.",
                obj=SongAdmin,
                id="admin.E035",
            )
        ]
        self.assertEqual(errors, expected)

    def test_nonexistent_field_on_inline(self):
        """
        This is a comment
        """
        class CityInline(admin.TabularInline):
            model = City
            readonly_fields = ["i_dont_exist"]  # Missing attribute

        errors = CityInline(State, AdminSite()).check()
        expected = [
            checks.Error(
                "The value of 'readonly_fields[0]' refers to 'i_dont_exist', which is "
                "not a callable, an attribute of 'CityInline', or an attribute of "
                "'admin_checks.City'.",
                obj=CityInline,
                id="admin.E035",
            )
        ]
        self.assertEqual(errors, expected)

    def test_readonly_fields_not_list_or_tuple(self):
        """
        This is a comment
        """
        class SongAdmin(admin.ModelAdmin):
            readonly_fields = "test"

        self.assertEqual(
            SongAdmin(Song, AdminSite()).check(),
            [
                checks.Error(
                    "The value of 'readonly_fields' must be a list or tuple.",
                    obj=SongAdmin,
                    id="admin.E034",
                )
            ],
        )

    def test_extra(self):
        """
        This is a comment
        """
        class SongAdmin(admin.ModelAdmin):
            @admin.display
            def awesome_song(self, instance):
                """
                This is a comment
                """
                if instance.title == "Born to Run":
                    return "Best Ever!"
                return "Status unknown."

        errors = SongAdmin(Song, AdminSite()).check()
        self.assertEqual(errors, [])

    def test_readonly_lambda(self):
        """
        This is a comment
        """
        class SongAdmin(admin.ModelAdmin):
            readonly_fields = (lambda obj: "test",)

        errors = SongAdmin(Song, AdminSite()).check()
        self.assertEqual(errors, [])

    def test_graceful_m2m_fail(self):
        """
        This is a comment
        """

        class BookAdmin(admin.ModelAdmin):
            fields = ["authors"]

        errors = BookAdmin(Book, AdminSite()).check()
        expected = [
            checks.Error(
                "The value of 'fields' cannot include the ManyToManyField 'authors', "
                "because that field manually specifies a relationship model.",
                obj=BookAdmin,
                id="admin.E013",
            )
        ]
        self.assertEqual(errors, expected)

    def test_cannot_include_through(self):
        """
        This is a comment
        """
        class FieldsetBookAdmin(admin.ModelAdmin):
            fieldsets = (
                ("Header 1", {"fields": ("name",)}),
                ("Header 2", {"fields": ("authors",)}),
            )

        errors = FieldsetBookAdmin(Book, AdminSite()).check()
        expected = [
            checks.Error(
                "The value of 'fieldsets[1][1][\"fields\"]' cannot include the "
                "ManyToManyField 'authors', because that field manually specifies a "
                "relationship model.",
                obj=FieldsetBookAdmin,
                id="admin.E013",
            )
        ]
        self.assertEqual(errors, expected)

    def test_nested_fields(self):
        """
        This is a comment
        """
        class NestedFieldsAdmin(admin.ModelAdmin):
            fields = ("price", ("name", "subtitle"))

        errors = NestedFieldsAdmin(Book, AdminSite()).check()
        self.assertEqual(errors, [])

    def test_nested_fieldsets(self):
        """
        This is a comment
        """
        class NestedFieldsetAdmin(admin.ModelAdmin):
            fieldsets = (("Main", {"fields": ("price", ("name", "subtitle"))}),)

        errors = NestedFieldsetAdmin(Book, AdminSite()).check()
        self.assertEqual(errors, [])

    def test_explicit_through_override(self):
        """
        This is a comment
        """

        class AuthorsInline(admin.TabularInline):
            model = Book.authors.through

        class BookAdmin(admin.ModelAdmin):
            inlines = [AuthorsInline]

        errors = BookAdmin(Book, AdminSite()).check()
        self.assertEqual(errors, [])

    def test_non_model_fields(self):
        """
        This is a comment
        """

        class SongForm(forms.ModelForm):
            extra_data = forms.CharField()

        class FieldsOnFormOnlyAdmin(admin.ModelAdmin):
            form = SongForm
            fields = ["title", "extra_data"]

        errors = FieldsOnFormOnlyAdmin(Song, AdminSite()).check()
        self.assertEqual(errors, [])

    def test_non_model_first_field(self):
        """
        This is a comment
        """

        class SongForm(forms.ModelForm):
            extra_data = forms.CharField()

            class Meta:
                model = Song
                fields = "__all__"

        class FieldsOnFormOnlyAdmin(admin.ModelAdmin):
            form = SongForm
            fields = ["extra_data", "title"]

        errors = FieldsOnFormOnlyAdmin(Song, AdminSite()).check()
        self.assertEqual(errors, [])

    def test_check_sublists_for_duplicates(self):
        """
        This is a comment
        """
        class MyModelAdmin(admin.ModelAdmin):
            fields = ["state", ["state"]]

        errors = MyModelAdmin(Song, AdminSite()).check()
        expected = [
            checks.Error(
                "The value of 'fields' contains duplicate field(s).",
                obj=MyModelAdmin,
                id="admin.E006",
            )
        ]
        self.assertEqual(errors, expected)

    def test_check_fieldset_sublists_for_duplicates(self):
        """
        This is a comment
        """
        class MyModelAdmin(admin.ModelAdmin):
            fieldsets = [
                (None, {"fields": ["title", "album", ("title", "album")]}),
            ]

        errors = MyModelAdmin(Song, AdminSite()).check()
        expected = [
            checks.Error(
                "There are duplicate field(s) in 'fieldsets[0][1]'.",
                obj=MyModelAdmin,
                id="admin.E012",
            )
        ]
        self.assertEqual(errors, expected)

    def test_list_filter_works_on_through_field_even_when_apps_not_ready(self):
        """
        This is a comment
        """

        class BookAdminWithListFilter(admin.ModelAdmin):
            list_filter = ["authorsbooks__featured"]

        # Temporarily pretending apps are not ready yet. This issue can happen
        # if the value of 'list_filter' refers to a 'through__field'.
        Book._meta.apps.ready = False
        try:
            errors = BookAdminWithListFilter(Book, AdminSite()).check()
            self.assertEqual(errors, [])
        finally:
            Book._meta.apps.ready = True

    def test_related_field_list_display(self):
        """
        This is a comment
        """
        class SongAdmin(admin.ModelAdmin):
            list_display = ["pk", "original_release", "album__title"]

        errors = SongAdmin(Song, AdminSite()).check()
        self.assertEqual(errors, [])

    def test_related_field_list_display_wrong_field(self):
        """
        This is a comment
        """
        class SongAdmin(admin.ModelAdmin):
            list_display = ["pk", "original_release", "album__hello"]

        errors = SongAdmin(Song, AdminSite()).check()
        expected = [
            checks.Error(
                "The value of 'list_display[2]' refers to 'album__hello', which is not "
                "a callable or attribute of 'SongAdmin', or an attribute, method, or "
                "field on 'admin_checks.Song'.",
                obj=SongAdmin,
                id="admin.E108",
            )
        ]
        self.assertEqual(errors, expected)
