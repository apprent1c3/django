from django.db import connection, models
from django.db.backends.utils import truncate_name
from django.test import TestCase

from .models.article import Article, Site
from .models.publication import Publication


class Advertisement(models.Model):
    customer = models.CharField(max_length=100)
    publications = models.ManyToManyField("model_package.Publication", blank=True)


class ModelPackageTests(TestCase):
    def test_m2m_tables_in_subpackage_models(self):
        """
        This is a comment
        """
        p = Publication.objects.create(title="FooBar")

        site = Site.objects.create(name="example.com")

        a = Article.objects.create(headline="a foo headline")
        a.publications.add(p)
        a.sites.add(site)

        a = Article.objects.get(id=a.pk)
        self.assertEqual(a.id, a.pk)
        self.assertEqual(a.sites.count(), 1)

    def test_models_in_the_test_package(self):
        """
        This is a comment
        """
        p = Publication.objects.create(title="FooBar")
        ad = Advertisement.objects.create(customer="Lawrence Journal-World")
        ad.publications.add(p)

        ad = Advertisement.objects.get(id=ad.pk)
        self.assertEqual(ad.publications.count(), 1)

    def test_automatic_m2m_column_names(self):
        """
        This is a comment
        """
        self.assertEqual(Article.publications.through._meta.fields[1].name, "article")
        self.assertEqual(
            Article.publications.through._meta.fields[1].get_attname_column(),
            ("article_id", "article_id"),
        )
        self.assertEqual(
            Article.publications.through._meta.fields[2].name, "publication"
        )
        self.assertEqual(
            Article.publications.through._meta.fields[2].get_attname_column(),
            ("publication_id", "publication_id"),
        )

        self.assertEqual(
            Article._meta.get_field("publications").m2m_db_table(),
            truncate_name(
                "model_package_article_publications", connection.ops.max_name_length()
            ),
        )

        self.assertEqual(
            Article._meta.get_field("publications").m2m_column_name(), "article_id"
        )
        self.assertEqual(
            Article._meta.get_field("publications").m2m_reverse_name(), "publication_id"
        )
