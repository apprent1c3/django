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
        """
        Validates and cleans the provided URL by checking for a leading slash and 
        optional trailing slash.

        Raises:
            ValidationError: If the URL is missing a leading slash or a trailing slash 
                             when required.

        Returns:
            str: The cleaned URL if validation is successful.

        Note:
            The trailing slash requirement is determined by the `_trailing_slash_required` 
            method, which is not described here. Refer to that method's documentation for 
            more information on when a trailing slash is required.
        """
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
        Validate the uniqueness of a flat page URL across multiple sites.

        This method checks if a flat page with the same URL already exists on any of the
        selected sites. If it does, a ValidationError is raised to prevent duplicate URLs.

        The validation takes into account the current instance being edited, if any, to
        allow updating an existing flat page without triggering a duplicate URL error.

        If the validation passes, the method calls the parent class's clean method to
        perform any additional validation as needed.

        Raises:
            ValidationError: If a flat page with the same URL already exists on any of the
                selected sites.

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
