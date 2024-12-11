from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import AutocompleteSelect
from django.forms import ModelChoiceField
from django.test import TestCase, override_settings
from django.utils import translation

from .models import Album, Band, ReleaseEvent, VideoStream


class AlbumForm(forms.ModelForm):
    class Meta:
        model = Album
        fields = ["band", "featuring"]
        widgets = {
            "band": AutocompleteSelect(
                Album._meta.get_field("band"),
                admin.site,
                attrs={"class": "my-class"},
            ),
            "featuring": AutocompleteSelect(
                Album._meta.get_field("featuring"),
                admin.site,
            ),
        }


class NotRequiredBandForm(forms.Form):
    band = ModelChoiceField(
        queryset=Album.objects.all(),
        widget=AutocompleteSelect(
            Album._meta.get_field("band").remote_field, admin.site
        ),
        required=False,
    )


class RequiredBandForm(forms.Form):
    band = ModelChoiceField(
        queryset=Album.objects.all(),
        widget=AutocompleteSelect(
            Album._meta.get_field("band").remote_field, admin.site
        ),
        required=True,
    )


class VideoStreamForm(forms.ModelForm):
    class Meta:
        model = VideoStream
        fields = ["release_event"]
        widgets = {
            "release_event": AutocompleteSelect(
                VideoStream._meta.get_field("release_event"),
                admin.site,
            ),
        }


@override_settings(ROOT_URLCONF="admin_widgets.urls")
class AutocompleteMixinTests(TestCase):
    empty_option = '<option value=""></option>'
    maxDiff = 1000

    def test_build_attrs(self):
        """
        Tests that the build attributes for the 'band' field in the AlbumForm are correctly generated.

        The test verifies that the attributes added to the field widget match the expected set of attributes, 
        including class names, data attributes for autocomplete functionality, and other relevant settings.

        """
        form = AlbumForm()
        attrs = form["band"].field.widget.get_context(
            name="my_field", value=None, attrs={}
        )["widget"]["attrs"]
        self.assertEqual(
            attrs,
            {
                "class": "my-class admin-autocomplete",
                "data-ajax--cache": "true",
                "data-ajax--delay": 250,
                "data-ajax--type": "GET",
                "data-ajax--url": "/autocomplete/",
                "data-theme": "admin-autocomplete",
                "data-allow-clear": "false",
                "data-app-label": "admin_widgets",
                "data-field-name": "band",
                "data-model-name": "album",
                "data-placeholder": "",
                "lang": "en",
            },
        )

    def test_build_attrs_no_custom_class(self):
        form = AlbumForm()
        attrs = form["featuring"].field.widget.get_context(
            name="name", value=None, attrs={}
        )["widget"]["attrs"]
        self.assertEqual(attrs["class"], "admin-autocomplete")

    def test_build_attrs_not_required_field(self):
        """
        Test that the 'band' field widget in the NotRequiredBandForm builds attributes correctly for a non-required field.

        Checks that the 'data-allow-clear' attribute is set to True, indicating that the field allows its value to be cleared.
        """
        form = NotRequiredBandForm()
        attrs = form["band"].field.widget.build_attrs({})
        self.assertJSONEqual(attrs["data-allow-clear"], True)

    def test_build_attrs_required_field(self):
        """

        Checks that a required field in the RequiredBandForm does not allow clearing its value.

        Verifies that the 'data-allow-clear' attribute of the 'band' field's widget is set to False,
        indicating that the field must always contain a value and cannot be cleared by the user.

        """
        form = RequiredBandForm()
        attrs = form["band"].field.widget.build_attrs({})
        self.assertJSONEqual(attrs["data-allow-clear"], False)

    def test_get_url(self):
        """
        Tests the retrieval of the URL used by the AutocompleteSelect widget.

        Verifies that the get_url method returns the correct URL for the autocomplete
        feature, which is used to provide suggestions for selecting related objects.

        Checks that the returned URL matches the expected path for the autocomplete
        endpoint, ensuring proper functioning of the AutocompleteSelect widget in the
        admin interface.
        """
        rel = Album._meta.get_field("band")
        w = AutocompleteSelect(rel, admin.site)
        url = w.get_url()
        self.assertEqual(url, "/autocomplete/")

    def test_render_options(self):
        beatles = Band.objects.create(name="The Beatles", style="rock")
        who = Band.objects.create(name="The Who", style="rock")
        # With 'band', a ForeignKey.
        form = AlbumForm(initial={"band": beatles.uuid})
        output = form.as_table()
        selected_option = (
            '<option value="%s" selected>The Beatles</option>' % beatles.uuid
        )
        option = '<option value="%s">The Who</option>' % who.uuid
        self.assertIn(selected_option, output)
        self.assertNotIn(option, output)
        # With 'featuring', a ManyToManyField.
        form = AlbumForm(initial={"featuring": [beatles.pk, who.pk]})
        output = form.as_table()
        selected_option = (
            '<option value="%s" selected>The Beatles</option>' % beatles.pk
        )
        option = '<option value="%s" selected>The Who</option>' % who.pk
        self.assertIn(selected_option, output)
        self.assertIn(option, output)

    def test_render_options_required_field(self):
        """Empty option is present if the field isn't required."""
        form = NotRequiredBandForm()
        output = form.as_table()
        self.assertIn(self.empty_option, output)

    def test_render_options_not_required_field(self):
        """Empty option isn't present if the field isn't required."""
        form = RequiredBandForm()
        output = form.as_table()
        self.assertNotIn(self.empty_option, output)

    def test_render_options_fk_as_pk(self):
        """
        Tests that the foreign key field in VideoStreamForm is properly rendered as a primary key.

        The test creates a release event and an instance of VideoStreamForm, initializing the form with the event's primary key.
        It then checks that the form's HTML representation includes the expected selected option for the release event, 
        verifying that the foreign key is correctly rendered as the primary key in the form's dropdown menu.
        """
        beatles = Band.objects.create(name="The Beatles", style="rock")
        rubber_soul = Album.objects.create(name="Rubber Soul", band=beatles)
        release_event = ReleaseEvent.objects.create(
            name="Test Target", album=rubber_soul
        )
        form = VideoStreamForm(initial={"release_event": release_event.pk})
        output = form.as_table()
        selected_option = (
            '<option value="%s" selected>Test Target</option>' % release_event.pk
        )
        self.assertIn(selected_option, output)

    def test_media(self):
        """

        Tests the media files returned by AutocompleteSelect for the \"band\" field of the Album model.
        This test covers various language locales to ensure the correct language-specific JavaScript files are included.
        It verifies that the expected JavaScript files are returned for each locale.

        """
        rel = Album._meta.get_field("band").remote_field
        base_files = (
            "admin/js/vendor/jquery/jquery.min.js",
            "admin/js/vendor/select2/select2.full.min.js",
            # Language file is inserted here.
            "admin/js/jquery.init.js",
            "admin/js/autocomplete.js",
        )
        languages = (
            ("de", "de"),
            # Subsequent language codes are used when the language code is not
            # supported.
            ("de-at", "de"),
            ("de-ch-1901", "de"),
            ("en-latn-us", "en"),
            ("nl-nl-x-informal", "nl"),
            ("zh-hans-HK", "zh-CN"),
            # Language with code 00 does not exist.
            ("00", None),
            # Language files are case sensitive.
            ("sr-cyrl", "sr-Cyrl"),
            ("zh-hans", "zh-CN"),
            ("zh-hant", "zh-TW"),
            (None, None),
        )
        for lang, select_lang in languages:
            with self.subTest(lang=lang):
                if select_lang:
                    expected_files = (
                        base_files[:2]
                        + (("admin/js/vendor/select2/i18n/%s.js" % select_lang),)
                        + base_files[2:]
                    )
                else:
                    expected_files = base_files
                with translation.override(lang):
                    self.assertEqual(
                        AutocompleteSelect(rel, admin.site).media._js,
                        list(expected_files),
                    )
