from django.db.models import Q
from django.test import TestCase

from .models import Issue, StringReferenceModel, User


class RelatedObjectTests(TestCase):
    def test_related_objects_have_name_attribute(self):
        for field_name in ("test_issue_client", "test_issue_cc"):
            obj = User._meta.get_field(field_name)
            self.assertEqual(field_name, obj.field.related_query_name())

    def test_m2m_and_m2o(self):
        """
        Tests the many-to-many (m2m) and many-to-one (m2o) relationships in the Issue model.

        This test case creates several users and issues, setting up various relationships between them. It then verifies that the Issue model's manager correctly filters issues based on their client and cc (carbon copy) relationships.

        The test covers several scenarios, including:

        * Retrieving issues for a specific client
        * Retrieving issues where a user is cc'd
        * Retrieving issues where a user is either the client or cc'd, using both bitwise OR operators and Django's Q objects.

        It ensures that the model's relationships are correctly established and that the manager returns the expected results. The test is designed to verify the correct behavior of the Issue model's relationships and querying capabilities.
        """
        r = User.objects.create(username="russell")
        g = User.objects.create(username="gustav")

        i1 = Issue(num=1)
        i1.client = r
        i1.save()

        i2 = Issue(num=2)
        i2.client = r
        i2.save()
        i2.cc.add(r)

        i3 = Issue(num=3)
        i3.client = g
        i3.save()
        i3.cc.add(r)

        self.assertQuerySetEqual(
            Issue.objects.filter(client=r.id),
            [
                1,
                2,
            ],
            lambda i: i.num,
        )
        self.assertQuerySetEqual(
            Issue.objects.filter(client=g.id),
            [
                3,
            ],
            lambda i: i.num,
        )
        self.assertQuerySetEqual(Issue.objects.filter(cc__id__exact=g.id), [])
        self.assertQuerySetEqual(
            Issue.objects.filter(cc__id__exact=r.id),
            [
                2,
                3,
            ],
            lambda i: i.num,
        )

        # These queries combine results from the m2m and the m2o relationships.
        # They're three ways of saying the same thing.
        self.assertQuerySetEqual(
            Issue.objects.filter(Q(cc__id__exact=r.id) | Q(client=r.id)),
            [
                1,
                2,
                3,
            ],
            lambda i: i.num,
        )
        self.assertQuerySetEqual(
            Issue.objects.filter(cc__id__exact=r.id)
            | Issue.objects.filter(client=r.id),
            [
                1,
                2,
                3,
            ],
            lambda i: i.num,
        )
        self.assertQuerySetEqual(
            Issue.objects.filter(Q(client=r.id) | Q(cc__id__exact=r.id)),
            [
                1,
                2,
                3,
            ],
            lambda i: i.num,
        )


class RelatedObjectUnicodeTests(TestCase):
    def test_m2m_with_unicode_reference(self):
        """
        Regression test for #6045: references to other models can be
        strings, providing they are directly convertible to ASCII.
        """
        m1 = StringReferenceModel.objects.create()
        m2 = StringReferenceModel.objects.create()
        m2.others.add(m1)  # used to cause an error (see ticket #6045)
        m2.save()
        list(m2.others.all())  # Force retrieval.
