import datetime

from django import forms
from django.test import TestCase

from .models import Article


class FormsTests(TestCase):
    # ForeignObjects should not have any form fields, currently the user needs
    # to manually deal with the foreignobject relation.
    class ArticleForm(forms.ModelForm):
        class Meta:
            model = Article
            fields = "__all__"

    def test_foreign_object_form(self):
        # A very crude test checking that the non-concrete fields do not get
        # form fields.
        """
        Tests the functionality of the ArticleForm.

        This test case checks the following scenarios:
            - The form includes the 'id_pub_date' field.
            - The 'active_translation' field is not included in the form.
            - A new form instance can be successfully validated and saved with a 'pub_date' field set to the current date.
            - An existing article instance can be updated with a new 'pub_date' and the changes are persisted correctly.

        """
        form = FormsTests.ArticleForm()
        self.assertIn("id_pub_date", form.as_table())
        self.assertNotIn("active_translation", form.as_table())
        form = FormsTests.ArticleForm(data={"pub_date": str(datetime.date.today())})
        self.assertTrue(form.is_valid())
        a = form.save()
        self.assertEqual(a.pub_date, datetime.date.today())
        form = FormsTests.ArticleForm(instance=a, data={"pub_date": "2013-01-01"})
        a2 = form.save()
        self.assertEqual(a.pk, a2.pk)
        self.assertEqual(a2.pub_date, datetime.date(2013, 1, 1))
