from django import forms
from django.conf import settings
from django.contrib.flatpages.models import FlatPage
from django.core.exceptions import ValidationError
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _


class FlatpageForm(forms.ModelForm):
    url = forms.RegexField(
        label=_("URL"),
        max_length=100,
        regex=r"^[-\w/.~]+$",
        help_text=_(
            "Example: “/about/contact/”. Make sure to have leading and trailing "
            "slashes."
        ),
        error_messages={
            "invalid": _(
                "This value must contain only letters, numbers, dots, "
                "underscores, dashes, slashes or tildes."
            ),
        },
    )

    class Meta:
        model = FlatPage
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        """
        Initializes the class instance, inheriting attributes from its parent class and optionally updates the 'url' field's help text based on the trailing slash requirement. The help text will be modified to include guidance on proper URL formatting, such as including a leading slash, if a trailing slash is not necessary.
        """
        super().__init__(*args, **kwargs)
        if not self._trailing_slash_required():
            self.fields["url"].help_text = _(
                "Example: “/about/contact”. Make sure to have a leading slash."
            )

    def _trailing_slash_required(self):
        return (
            settings.APPEND_SLASH
            and "django.middleware.common.CommonMiddleware" in settings.MIDDLEWARE
        )

    def clean_url(self):
        url = self.cleaned_data["url"]
        if not url.startswith("/"):
            raise ValidationError(
                gettext("URL is missing a leading slash."),
                code="missing_leading_slash",
            )
        if self._trailing_slash_required() and not url.endswith("/"):
            raise ValidationError(
                gettext("URL is missing a trailing slash."),
                code="missing_trailing_slash",
            )
        return url

    def clean(self):
        """

        Verifies that a flat page does not have a duplicate URL on any of the selected sites.

        Checks for the existence of a flat page with the same URL on any of the specified sites.
        If a duplicate is found, raises a ValidationError to prevent the creation or update of the flat page.
        This validation ensures data consistency and prevents potential conflicts between flat pages.

        """
        url = self.cleaned_data.get("url")
        sites = self.cleaned_data.get("sites")

        same_url = FlatPage.objects.filter(url=url)
        if self.instance.pk:
            same_url = same_url.exclude(pk=self.instance.pk)

        if sites and same_url.filter(sites__in=sites).exists():
            for site in sites:
                if same_url.filter(sites=site).exists():
                    raise ValidationError(
                        _("Flatpage with url %(url)s already exists for site %(site)s"),
                        code="duplicate_url",
                        params={"url": url, "site": site},
                    )

        return super().clean()
