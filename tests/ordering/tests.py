from datetime import datetime
from operator import attrgetter

from django.core.exceptions import FieldError
from django.db.models import (
    CharField,
    Count,
    DateTimeField,
    F,
    Max,
    OrderBy,
    OuterRef,
    Subquery,
    Value,
)
from django.db.models.functions import Length, Upper
from django.test import TestCase

from .models import (
    Article,
    Author,
    ChildArticle,
    OrderedByExpression,
    OrderedByExpressionChild,
    OrderedByExpressionGrandChild,
    OrderedByFArticle,
    Reference,
)


class OrderingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a1 = Article.objects.create(
            headline="Article 1", pub_date=datetime(2005, 7, 26)
        )
        cls.a2 = Article.objects.create(
            headline="Article 2", pub_date=datetime(2005, 7, 27)
        )
        cls.a3 = Article.objects.create(
            headline="Article 3", pub_date=datetime(2005, 7, 27)
        )
        cls.a4 = Article.objects.create(
            headline="Article 4", pub_date=datetime(2005, 7, 28)
        )
        cls.author_1 = Author.objects.create(name="Name 1")
        cls.author_2 = Author.objects.create(name="Name 2")
        for i in range(2):
            Author.objects.create()

    def test_default_ordering(self):
        """
        By default, Article.objects.all() orders by pub_date descending, then
        headline ascending.
        """
        self.assertQuerySetEqual(
            Article.objects.all(),
            [
                "Article 4",
                "Article 2",
                "Article 3",
                "Article 1",
            ],
            attrgetter("headline"),
        )

        # Getting a single item should work too:
        self.assertEqual(Article.objects.all()[0], self.a4)

    def test_default_ordering_override(self):
        """
        Override ordering with order_by, which is in the same format as the
        ordering attribute in models.
        """
        self.assertQuerySetEqual(
            Article.objects.order_by("headline"),
            [
                "Article 1",
                "Article 2",
                "Article 3",
                "Article 4",
            ],
            attrgetter("headline"),
        )
        self.assertQuerySetEqual(
            Article.objects.order_by("pub_date", "-headline"),
            [
                "Article 1",
                "Article 3",
                "Article 2",
                "Article 4",
            ],
            attrgetter("headline"),
        )

    def test_default_ordering_override_unknown_field(self):
        """
        Attempts to override default ordering on related models with an unknown
        field should result in an error.
        """
        msg = (
            "Cannot resolve keyword 'unknown_field' into field. Choices are: "
            "article, author, editor, editor_id, id, name"
        )
        with self.assertRaisesMessage(FieldError, msg):
            list(Article.objects.order_by("author__unknown_field"))

    def test_order_by_override(self):
        """
        Only the last order_by has any effect (since they each override any
        previous ordering).
        """
        self.assertQuerySetEqual(
            Article.objects.order_by("id"),
            [
                "Article 1",
                "Article 2",
                "Article 3",
                "Article 4",
            ],
            attrgetter("headline"),
        )
        self.assertQuerySetEqual(
            Article.objects.order_by("id").order_by("-headline"),
            [
                "Article 4",
                "Article 3",
                "Article 2",
                "Article 1",
            ],
            attrgetter("headline"),
        )

    def test_order_by_nulls_first_and_last(self):
        msg = "nulls_first and nulls_last are mutually exclusive"
        with self.assertRaisesMessage(ValueError, msg):
            Article.objects.order_by(
                F("author").desc(nulls_last=True, nulls_first=True)
            )

    def assertQuerySetEqualReversible(self, queryset, sequence):
        self.assertSequenceEqual(queryset, sequence)
        self.assertSequenceEqual(queryset.reverse(), list(reversed(sequence)))

    def test_order_by_nulls_last(self):
        """

        Tests the behavior of ordering querysets with null values at the end.

        This function verifies that database records can be sorted by specified fields in
        both ascending and descending order, with null values appearing at the end of the
        result set. It checks this behavior for fields of type 'author' and 'author__name'
        (with case-insensitive comparison), ensuring that null values are correctly
        handled by the 'nulls_last=True' argument.

        Multiple test cases are covered, including different combinations of sorting fields
        and ordering directions, to guarantee the correct ordering of records with and
        without null values.

        """
        Article.objects.filter(headline="Article 3").update(author=self.author_1)
        Article.objects.filter(headline="Article 4").update(author=self.author_2)
        # asc and desc are chainable with nulls_last.
        self.assertQuerySetEqualReversible(
            Article.objects.order_by(F("author").desc(nulls_last=True), "headline"),
            [self.a4, self.a3, self.a1, self.a2],
        )
        self.assertQuerySetEqualReversible(
            Article.objects.order_by(F("author").asc(nulls_last=True), "headline"),
            [self.a3, self.a4, self.a1, self.a2],
        )
        self.assertQuerySetEqualReversible(
            Article.objects.order_by(
                Upper("author__name").desc(nulls_last=True), "headline"
            ),
            [self.a4, self.a3, self.a1, self.a2],
        )
        self.assertQuerySetEqualReversible(
            Article.objects.order_by(
                Upper("author__name").asc(nulls_last=True), "headline"
            ),
            [self.a3, self.a4, self.a1, self.a2],
        )
        self.assertQuerySetEqualReversible(
            Article.objects.annotate(upper_name=Upper("author__name")).order_by(
                F("upper_name").asc(nulls_last=True), "headline"
            ),
            [self.a3, self.a4, self.a1, self.a2],
        )

    def test_order_by_nulls_first(self):
        """
        Tests the behavior of ordering database query results by a field with null values first.

        This test case covers different scenarios for ordering query results in ascending and descending order, 
        including ordering by a field with null values and a secondary field for tie-breakers. 
        It verifies that null values are placed first in the order when specified. 
        The test also checks the ordering when using database functions, such as Upper, to modify the field being ordered on.
        """
        Article.objects.filter(headline="Article 3").update(author=self.author_1)
        Article.objects.filter(headline="Article 4").update(author=self.author_2)
        # asc and desc are chainable with nulls_first.
        self.assertQuerySetEqualReversible(
            Article.objects.order_by(F("author").asc(nulls_first=True), "headline"),
            [self.a1, self.a2, self.a3, self.a4],
        )
        self.assertQuerySetEqualReversible(
            Article.objects.order_by(F("author").desc(nulls_first=True), "headline"),
            [self.a1, self.a2, self.a4, self.a3],
        )
        self.assertQuerySetEqualReversible(
            Article.objects.order_by(
                Upper("author__name").asc(nulls_first=True), "headline"
            ),
            [self.a1, self.a2, self.a3, self.a4],
        )
        self.assertQuerySetEqualReversible(
            Article.objects.order_by(
                Upper("author__name").desc(nulls_first=True), "headline"
            ),
            [self.a1, self.a2, self.a4, self.a3],
        )
        self.assertQuerySetEqualReversible(
            Article.objects.annotate(upper_name=Upper("author__name")).order_by(
                F("upper_name").desc(nulls_first=True), "headline"
            ),
            [self.a1, self.a2, self.a4, self.a3],
        )

    def test_orders_nulls_first_on_filtered_subquery(self):
        """

        Tests that the orders with nulls first when filtering on subquery.

        This test checks if null values are correctly ordered when filtering on a subquery.
        It verifies that authors are ordered by their last article publication date, with null dates appearing first.
        The test covers the scenario where authors have articles with publication dates, and where authors have no articles.
        The expected result is a list of authors in ascending order of their last article publication date, with authors having no articles (and thus null dates) appearing first.

        """
        Article.objects.filter(headline="Article 1").update(author=self.author_1)
        Article.objects.filter(headline="Article 2").update(author=self.author_1)
        Article.objects.filter(headline="Article 4").update(author=self.author_2)
        Author.objects.filter(name__isnull=True).delete()
        author_3 = Author.objects.create(name="Name 3")
        article_subquery = (
            Article.objects.filter(
                author=OuterRef("pk"),
                headline__icontains="Article",
            )
            .order_by()
            .values("author")
            .annotate(
                last_date=Max("pub_date"),
            )
            .values("last_date")
        )
        self.assertQuerySetEqualReversible(
            Author.objects.annotate(
                last_date=Subquery(article_subquery, output_field=DateTimeField())
            )
            .order_by(F("last_date").asc(nulls_first=True))
            .distinct(),
            [author_3, self.author_1, self.author_2],
        )

    def test_stop_slicing(self):
        """
        Use the 'stop' part of slicing notation to limit the results.
        """
        self.assertQuerySetEqual(
            Article.objects.order_by("headline")[:2],
            [
                "Article 1",
                "Article 2",
            ],
            attrgetter("headline"),
        )

    def test_stop_start_slicing(self):
        """
        Use the 'stop' and 'start' parts of slicing notation to offset the
        result list.
        """
        self.assertQuerySetEqual(
            Article.objects.order_by("headline")[1:3],
            [
                "Article 2",
                "Article 3",
            ],
            attrgetter("headline"),
        )

    def test_random_ordering(self):
        """
        Use '?' to order randomly.
        """
        self.assertEqual(len(list(Article.objects.order_by("?"))), 4)

    def test_reversed_ordering(self):
        """
        Ordering can be reversed using the reverse() method on a queryset.
        This allows you to extract things like "the last two items" (reverse
        and then take the first two).
        """
        self.assertQuerySetEqual(
            Article.objects.reverse()[:2],
            [
                "Article 1",
                "Article 3",
            ],
            attrgetter("headline"),
        )

    def test_reverse_ordering_pure(self):
        qs1 = Article.objects.order_by(F("headline").asc())
        qs2 = qs1.reverse()
        self.assertQuerySetEqual(
            qs2,
            [
                "Article 4",
                "Article 3",
                "Article 2",
                "Article 1",
            ],
            attrgetter("headline"),
        )
        self.assertQuerySetEqual(
            qs1,
            [
                "Article 1",
                "Article 2",
                "Article 3",
                "Article 4",
            ],
            attrgetter("headline"),
        )

    def test_reverse_meta_ordering_pure(self):
        Article.objects.create(
            headline="Article 5",
            pub_date=datetime(2005, 7, 30),
            author=self.author_1,
            second_author=self.author_2,
        )
        Article.objects.create(
            headline="Article 5",
            pub_date=datetime(2005, 7, 30),
            author=self.author_2,
            second_author=self.author_1,
        )
        self.assertQuerySetEqual(
            Article.objects.filter(headline="Article 5").reverse(),
            ["Name 2", "Name 1"],
            attrgetter("author.name"),
        )
        self.assertQuerySetEqual(
            Article.objects.filter(headline="Article 5"),
            ["Name 1", "Name 2"],
            attrgetter("author.name"),
        )

    def test_no_reordering_after_slicing(self):
        msg = "Cannot reverse a query once a slice has been taken."
        qs = Article.objects.all()[0:2]
        with self.assertRaisesMessage(TypeError, msg):
            qs.reverse()
        with self.assertRaisesMessage(TypeError, msg):
            qs.last()

    def test_extra_ordering(self):
        """
        Ordering can be based on fields included from an 'extra' clause
        """
        self.assertQuerySetEqual(
            Article.objects.extra(
                select={"foo": "pub_date"}, order_by=["foo", "headline"]
            ),
            [
                "Article 1",
                "Article 2",
                "Article 3",
                "Article 4",
            ],
            attrgetter("headline"),
        )

    def test_extra_ordering_quoting(self):
        """
        If the extra clause uses an SQL keyword for a name, it will be
        protected by quoting.
        """
        self.assertQuerySetEqual(
            Article.objects.extra(
                select={"order": "pub_date"}, order_by=["order", "headline"]
            ),
            [
                "Article 1",
                "Article 2",
                "Article 3",
                "Article 4",
            ],
            attrgetter("headline"),
        )

    def test_extra_ordering_with_table_name(self):
        self.assertQuerySetEqual(
            Article.objects.extra(order_by=["ordering_article.headline"]),
            [
                "Article 1",
                "Article 2",
                "Article 3",
                "Article 4",
            ],
            attrgetter("headline"),
        )
        self.assertQuerySetEqual(
            Article.objects.extra(order_by=["-ordering_article.headline"]),
            [
                "Article 4",
                "Article 3",
                "Article 2",
                "Article 1",
            ],
            attrgetter("headline"),
        )

    def test_order_by_pk(self):
        """
        'pk' works as an ordering option in Meta.
        """
        self.assertEqual(
            [a.pk for a in Author.objects.all()],
            [a.pk for a in Author.objects.order_by("-pk")],
        )

    def test_order_by_fk_attname(self):
        """
        ordering by a foreign key by its attribute name prevents the query
        from inheriting its related model ordering option (#19195).
        """
        authors = list(Author.objects.order_by("id"))
        for i in range(1, 5):
            author = authors[i - 1]
            article = getattr(self, "a%d" % (5 - i))
            article.author = author
            article.save(update_fields={"author"})

        self.assertQuerySetEqual(
            Article.objects.order_by("author_id"),
            [
                "Article 4",
                "Article 3",
                "Article 2",
                "Article 1",
            ],
            attrgetter("headline"),
        )

    def test_order_by_self_referential_fk(self):
        self.a1.author = Author.objects.create(editor=self.author_1)
        self.a1.save()
        self.a2.author = Author.objects.create(editor=self.author_2)
        self.a2.save()
        self.assertQuerySetEqual(
            Article.objects.filter(author__isnull=False).order_by("author__editor"),
            ["Article 2", "Article 1"],
            attrgetter("headline"),
        )
        self.assertQuerySetEqual(
            Article.objects.filter(author__isnull=False).order_by("author__editor_id"),
            ["Article 1", "Article 2"],
            attrgetter("headline"),
        )

    def test_order_by_f_expression(self):
        """

        Tests the functionality of ordering QuerySets using F-expressions.

        This test case verifies that the `order_by` method can correctly sort
        QuerySets based on a given F-expression, which allows for dynamic
        ordering of database fields. The test covers three scenarios:
        - Ordering by an F-expression without specifying an order (defaults to ascending).
        - Ordering by an F-expression with an ascending order.
        - Ordering by an F-expression with a descending order.

        Each scenario is verified by comparing the resulting QuerySet to an
        expected list of article headlines, ensuring that the ordering is correct.

        """
        self.assertQuerySetEqual(
            Article.objects.order_by(F("headline")),
            [
                "Article 1",
                "Article 2",
                "Article 3",
                "Article 4",
            ],
            attrgetter("headline"),
        )
        self.assertQuerySetEqual(
            Article.objects.order_by(F("headline").asc()),
            [
                "Article 1",
                "Article 2",
                "Article 3",
                "Article 4",
            ],
            attrgetter("headline"),
        )
        self.assertQuerySetEqual(
            Article.objects.order_by(F("headline").desc()),
            [
                "Article 4",
                "Article 3",
                "Article 2",
                "Article 1",
            ],
            attrgetter("headline"),
        )

    def test_order_by_f_expression_duplicates(self):
        """
        A column may only be included once (the first occurrence) so we check
        to ensure there are no duplicates by inspecting the SQL.
        """
        qs = Article.objects.order_by(F("headline").asc(), F("headline").desc())
        sql = str(qs.query).upper()
        fragment = sql[sql.find("ORDER BY") :]
        self.assertEqual(fragment.count("HEADLINE"), 1)
        self.assertQuerySetEqual(
            qs,
            [
                "Article 1",
                "Article 2",
                "Article 3",
                "Article 4",
            ],
            attrgetter("headline"),
        )
        qs = Article.objects.order_by(F("headline").desc(), F("headline").asc())
        sql = str(qs.query).upper()
        fragment = sql[sql.find("ORDER BY") :]
        self.assertEqual(fragment.count("HEADLINE"), 1)
        self.assertQuerySetEqual(
            qs,
            [
                "Article 4",
                "Article 3",
                "Article 2",
                "Article 1",
            ],
            attrgetter("headline"),
        )

    def test_order_by_constant_value(self):
        # Order by annotated constant from selected columns.
        qs = Article.objects.annotate(
            constant=Value("1", output_field=CharField()),
        ).order_by("constant", "-headline")
        self.assertSequenceEqual(qs, [self.a4, self.a3, self.a2, self.a1])
        # Order by annotated constant which is out of selected columns.
        self.assertSequenceEqual(
            qs.values_list("headline", flat=True),
            [
                "Article 4",
                "Article 3",
                "Article 2",
                "Article 1",
            ],
        )
        # Order by constant.
        qs = Article.objects.order_by(Value("1", output_field=CharField()), "-headline")
        self.assertSequenceEqual(qs, [self.a4, self.a3, self.a2, self.a1])

    def test_related_ordering_duplicate_table_reference(self):
        """
        An ordering referencing a model with an ordering referencing a model
        multiple time no circular reference should be detected (#24654).
        """
        first_author = Author.objects.create()
        second_author = Author.objects.create()
        self.a1.author = first_author
        self.a1.second_author = second_author
        self.a1.save()
        self.a2.author = second_author
        self.a2.second_author = first_author
        self.a2.save()
        r1 = Reference.objects.create(article_id=self.a1.pk)
        r2 = Reference.objects.create(article_id=self.a2.pk)
        self.assertSequenceEqual(Reference.objects.all(), [r2, r1])

    def test_default_ordering_by_f_expression(self):
        """F expressions can be used in Meta.ordering."""
        articles = OrderedByFArticle.objects.all()
        articles.filter(headline="Article 2").update(author=self.author_2)
        articles.filter(headline="Article 3").update(author=self.author_1)
        self.assertQuerySetEqual(
            articles,
            ["Article 1", "Article 4", "Article 3", "Article 2"],
            attrgetter("headline"),
        )

    def test_order_by_ptr_field_with_default_ordering_by_expression(self):
        ca1 = ChildArticle.objects.create(
            headline="h2",
            pub_date=datetime(2005, 7, 27),
            author=self.author_2,
        )
        ca2 = ChildArticle.objects.create(
            headline="h2",
            pub_date=datetime(2005, 7, 27),
            author=self.author_1,
        )
        ca3 = ChildArticle.objects.create(
            headline="h3",
            pub_date=datetime(2005, 7, 27),
            author=self.author_1,
        )
        ca4 = ChildArticle.objects.create(headline="h1", pub_date=datetime(2005, 7, 28))
        articles = ChildArticle.objects.order_by("article_ptr")
        self.assertSequenceEqual(articles, [ca4, ca2, ca1, ca3])

    def test_default_ordering_does_not_affect_group_by(self):
        Article.objects.exclude(headline="Article 4").update(author=self.author_1)
        Article.objects.filter(headline="Article 4").update(author=self.author_2)
        articles = Article.objects.values("author").annotate(count=Count("author"))
        self.assertCountEqual(
            articles,
            [
                {"author": self.author_1.pk, "count": 3},
                {"author": self.author_2.pk, "count": 1},
            ],
        )

    def test_order_by_parent_fk_with_expression_in_default_ordering(self):
        p3 = OrderedByExpression.objects.create(name="oBJ 3")
        p2 = OrderedByExpression.objects.create(name="OBJ 2")
        p1 = OrderedByExpression.objects.create(name="obj 1")
        c3 = OrderedByExpressionChild.objects.create(parent=p3)
        c2 = OrderedByExpressionChild.objects.create(parent=p2)
        c1 = OrderedByExpressionChild.objects.create(parent=p1)
        self.assertSequenceEqual(
            OrderedByExpressionChild.objects.order_by("parent"),
            [c1, c2, c3],
        )

    def test_order_by_grandparent_fk_with_expression_in_default_ordering(self):
        """

        Tests the ordering of grandchild objects based on their grandparent's foreign key,
        to ensure they are ordered correctly by the default ordering expression.

        This test case verifies that the grandchild objects are ordered in the correct sequence,
        which is determined by the ordering of their parent objects. The test creates a set of
        parent, child, and grandchild objects with specific names, and then checks that the
        grandchild objects are returned in the expected order when ordered by their parent.

        """
        p3 = OrderedByExpression.objects.create(name="oBJ 3")
        p2 = OrderedByExpression.objects.create(name="OBJ 2")
        p1 = OrderedByExpression.objects.create(name="obj 1")
        c3 = OrderedByExpressionChild.objects.create(parent=p3)
        c2 = OrderedByExpressionChild.objects.create(parent=p2)
        c1 = OrderedByExpressionChild.objects.create(parent=p1)
        g3 = OrderedByExpressionGrandChild.objects.create(parent=c3)
        g2 = OrderedByExpressionGrandChild.objects.create(parent=c2)
        g1 = OrderedByExpressionGrandChild.objects.create(parent=c1)
        self.assertSequenceEqual(
            OrderedByExpressionGrandChild.objects.order_by("parent"),
            [g1, g2, g3],
        )

    def test_order_by_expression_ref(self):
        self.assertQuerySetEqual(
            Author.objects.annotate(upper_name=Upper("name")).order_by(
                Length("upper_name")
            ),
            Author.objects.order_by(Length(Upper("name"))),
        )

    def test_ordering_select_related_collision(self):
        self.assertEqual(
            Article.objects.select_related("author")
            .annotate(name=Upper("author__name"))
            .filter(pk=self.a1.pk)
            .order_by(OrderBy(F("name")))
            .first(),
            self.a1,
        )
        self.assertEqual(
            Article.objects.select_related("author")
            .annotate(name=Upper("author__name"))
            .filter(pk=self.a1.pk)
            .order_by("name")
            .first(),
            self.a1,
        )

    def test_order_by_expr_query_reuse(self):
        """

        Tests if a queryset ordered by an expression can be reused, specifically when 
        using the iterator method, by comparing the results with the original queryset.

        Verifies that the ordering of the results is preserved when iterating over the 
        queryset multiple times, ensuring that the database query is correctly reused 
        and the results are consistent. 

        The test case uses a queryset of authors annotated with the count of their 
        articles, ordered by the count in descending order and then by the author's primary key.

        """
        qs = Author.objects.annotate(num=Count("article")).order_by(
            F("num").desc(), "pk"
        )
        self.assertCountEqual(qs, qs.iterator())
