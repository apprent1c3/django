from datetime import datetime

from django.test import TestCase

from .models import Article, Reporter, Writer


class M2MIntermediaryTests(TestCase):
    def test_intermediary(self):
        """

        Tests the intermediary table in a many-to-many relationship between Reporters and Articles.

        Verifies that the writer_set on an Article instance returns a QuerySet of Writers
        in the correct order, and that the Writer instances have the correct Reporter and Article references.

        Also checks that the writer_set on a Reporter instance returns a QuerySet of Writers
        associated with that Reporter.

        """
        r1 = Reporter.objects.create(first_name="John", last_name="Smith")
        r2 = Reporter.objects.create(first_name="Jane", last_name="Doe")

        a = Article.objects.create(
            headline="This is a test", pub_date=datetime(2005, 7, 27)
        )

        w1 = Writer.objects.create(reporter=r1, article=a, position="Main writer")
        w2 = Writer.objects.create(reporter=r2, article=a, position="Contributor")

        self.assertQuerySetEqual(
            a.writer_set.select_related().order_by("-position"),
            [
                ("John Smith", "Main writer"),
                ("Jane Doe", "Contributor"),
            ],
            lambda w: (str(w.reporter), w.position),
        )
        self.assertEqual(w1.reporter, r1)
        self.assertEqual(w2.reporter, r2)

        self.assertEqual(w1.article, a)
        self.assertEqual(w2.article, a)

        self.assertQuerySetEqual(
            r1.writer_set.all(),
            [("John Smith", "Main writer")],
            lambda w: (str(w.reporter), w.position),
        )
