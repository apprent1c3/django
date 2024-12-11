from django.conf import settings
from django.contrib.sites.managers import CurrentSiteManager
from django.contrib.sites.models import Site
from django.core import checks
from django.db import models
from django.test import SimpleTestCase, TestCase
from django.test.utils import isolate_apps

from .models import CustomArticle, ExclusiveArticle, SyndicatedArticle


class SitesFrameworkTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for the application, including the creation of sites.

        This method creates two sites in the database: the primary site with the id specified
        in the settings and a secondary site with an incremented id. The primary site has a
        domain and name of 'example.com', while the secondary site has a domain and name of
        'example2.com'. This data is used as a foundation for subsequent tests.
        """
        Site.objects.get_or_create(
            id=settings.SITE_ID, domain="example.com", name="example.com"
        )
        Site.objects.create(
            id=settings.SITE_ID + 1, domain="example2.com", name="example2.com"
        )

    def test_site_fk(self):
        article = ExclusiveArticle.objects.create(
            title="Breaking News!", site_id=settings.SITE_ID
        )
        self.assertEqual(ExclusiveArticle.on_site.get(), article)

    def test_sites_m2m(self):
        article = SyndicatedArticle.objects.create(title="Fresh News!")
        article.sites.add(Site.objects.get(id=settings.SITE_ID))
        article.sites.add(Site.objects.get(id=settings.SITE_ID + 1))
        article2 = SyndicatedArticle.objects.create(title="More News!")
        article2.sites.add(Site.objects.get(id=settings.SITE_ID + 1))
        self.assertEqual(SyndicatedArticle.on_site.get(), article)

    def test_custom_named_field(self):
        article = CustomArticle.objects.create(
            title="Tantalizing News!",
            places_this_article_should_appear_id=settings.SITE_ID,
        )
        self.assertEqual(CustomArticle.on_site.get(), article)


@isolate_apps("sites_framework")
class CurrentSiteManagerChecksTests(SimpleTestCase):
    def test_invalid_name(self):
        """
        Tests that an error is raised when the CurrentSiteManager is initialized with an invalid field name.

        Checks that the model validation correctly identifies and reports the error when the specified field does not exist on the model. The expected error message includes the missing field name and the model object that triggered the error.

        The test case verifies that the error message matches the expected output, ensuring that the validation mechanism is working correctly and providing informative error messages for invalid configurations.
        """
        class InvalidArticle(models.Model):
            on_site = CurrentSiteManager("places_this_article_should_appear")

        errors = InvalidArticle.check()
        expected = [
            checks.Error(
                "CurrentSiteManager could not find a field named "
                "'places_this_article_should_appear'.",
                obj=InvalidArticle.on_site,
                id="sites.E001",
            )
        ]
        self.assertEqual(errors, expected)

    def test_invalid_field_type(self):
        """
        Tests that CurrentSiteManager raises an error when used with a non-foreign-key or non-many-to-many field.

        This test case verifies that a model using CurrentSiteManager with an invalid field type (in this case, an IntegerField) correctly reports the error.
        The expected error message indicates that CurrentSiteManager cannot use the specified field because it does not represent a relationship between models.
        The test confirms that the check method of the model returns the expected error when the CurrentSiteManager is misconfigured in this way.
        """
        class ConfusedArticle(models.Model):
            site = models.IntegerField()
            on_site = CurrentSiteManager()

        errors = ConfusedArticle.check()
        expected = [
            checks.Error(
                "CurrentSiteManager cannot use 'ConfusedArticle.site' as it is "
                "not a foreign key or a many-to-many field.",
                obj=ConfusedArticle.on_site,
                id="sites.E002",
            )
        ]
        self.assertEqual(errors, expected)
