from operator import attrgetter

from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Count
from django.test import TestCase

from .models import (
    Base,
    Child,
    Derived,
    Feature,
    Item,
    ItemAndSimpleItem,
    Leaf,
    Location,
    OneToOneItem,
    Proxy,
    ProxyRelated,
    RelatedItem,
    Request,
    ResolveThis,
    SimpleItem,
    SpecialFeature,
)


class DeferRegressionTest(TestCase):
    def test_basic(self):
        # Deferred fields should really be deferred and not accidentally use
        # the field's default value just because they aren't passed to __init__

        """
        Test basic ORM functionality, including query optimization, deferred and only loading, 
        select related, annotations, and content type caching. Verifies that queries are executed 
        as expected and that results are correctly retrieved and loaded from the database.
        """
        Item.objects.create(name="first", value=42)
        obj = Item.objects.only("name", "other_value").get(name="first")
        # Accessing "name" doesn't trigger a new database query. Accessing
        # "value" or "text" should.
        with self.assertNumQueries(0):
            self.assertEqual(obj.name, "first")
            self.assertEqual(obj.other_value, 0)

        with self.assertNumQueries(1):
            self.assertEqual(obj.value, 42)

        with self.assertNumQueries(1):
            self.assertEqual(obj.text, "xyzzy")

        with self.assertNumQueries(0):
            self.assertEqual(obj.text, "xyzzy")

        # Regression test for #10695. Make sure different instances don't
        # inadvertently share data in the deferred descriptor objects.
        i = Item.objects.create(name="no I'm first", value=37)
        items = Item.objects.only("value").order_by("-value")
        self.assertEqual(items[0].name, "first")
        self.assertEqual(items[1].name, "no I'm first")

        RelatedItem.objects.create(item=i)
        r = RelatedItem.objects.defer("item").get()
        self.assertEqual(r.item_id, i.id)
        self.assertEqual(r.item, i)

        # Some further checks for select_related() and inherited model
        # behavior (regression for #10710).
        c1 = Child.objects.create(name="c1", value=42)
        c2 = Child.objects.create(name="c2", value=37)
        Leaf.objects.create(name="l1", child=c1, second_child=c2)

        obj = Leaf.objects.only("name", "child").select_related()[0]
        self.assertEqual(obj.child.name, "c1")

        self.assertQuerySetEqual(
            Leaf.objects.select_related().only("child__name", "second_child__name"),
            [
                "l1",
            ],
            attrgetter("name"),
        )

        # Models instances with deferred fields should still return the same
        # content types as their non-deferred versions (bug #10738).
        ctype = ContentType.objects.get_for_model
        c1 = ctype(Item.objects.all()[0])
        c2 = ctype(Item.objects.defer("name")[0])
        c3 = ctype(Item.objects.only("name")[0])
        self.assertTrue(c1 is c2 is c3)

        # Regression for #10733 - only() can be used on a model with two
        # foreign keys.
        results = Leaf.objects.only("name", "child", "second_child").select_related()
        self.assertEqual(results[0].child.name, "c1")
        self.assertEqual(results[0].second_child.name, "c2")

        results = Leaf.objects.only(
            "name", "child", "second_child", "child__name", "second_child__name"
        ).select_related()
        self.assertEqual(results[0].child.name, "c1")
        self.assertEqual(results[0].second_child.name, "c2")

        # Regression for #16409 - make sure defer() and only() work with annotate()
        self.assertIsInstance(
            list(SimpleItem.objects.annotate(Count("feature")).defer("name")), list
        )
        self.assertIsInstance(
            list(SimpleItem.objects.annotate(Count("feature")).only("name")), list
        )

    def test_ticket_16409(self):
        # Regression for #16409 - make sure defer() and only() work with annotate()
        self.assertIsInstance(
            list(SimpleItem.objects.annotate(Count("feature")).defer("name")), list
        )
        self.assertIsInstance(
            list(SimpleItem.objects.annotate(Count("feature")).only("name")), list
        )

    def test_ticket_23270(self):
        """

        Tests the lazy loading and deferred fields functionality for a derived model
        in a select_related query, ensuring only one database query is executed and
        that the desired fields are loaded and deferred as expected.

        """
        d = Derived.objects.create(text="foo", other_text="bar")
        with self.assertNumQueries(1):
            obj = Base.objects.select_related("derived").defer("text")[0]
            self.assertIsInstance(obj.derived, Derived)
            self.assertEqual("bar", obj.derived.other_text)
            self.assertNotIn("text", obj.__dict__)
            self.assertEqual(d.pk, obj.derived.base_ptr_id)

    def test_only_and_defer_usage_on_proxy_models(self):
        # Regression for #15790 - only() broken for proxy models
        """
        Tests the usage of :meth:`~django.db.models.query.QuerySet.only` and :meth:`~django.db.models.query.QuerySet.defer` methods on proxy models, ensuring that they return the correct results.
        """
        proxy = Proxy.objects.create(name="proxy", value=42)

        msg = "QuerySet.only() return bogus results with proxy models"
        dp = Proxy.objects.only("other_value").get(pk=proxy.pk)
        self.assertEqual(dp.name, proxy.name, msg=msg)
        self.assertEqual(dp.value, proxy.value, msg=msg)

        # also test things with .defer()
        msg = "QuerySet.defer() return bogus results with proxy models"
        dp = Proxy.objects.defer("name", "text", "value").get(pk=proxy.pk)
        self.assertEqual(dp.name, proxy.name, msg=msg)
        self.assertEqual(dp.value, proxy.value, msg=msg)

    def test_resolve_columns(self):
        ResolveThis.objects.create(num=5.0, name="Foobar")
        qs = ResolveThis.objects.defer("num")
        self.assertEqual(1, qs.count())
        self.assertEqual("Foobar", qs[0].name)

    def test_reverse_one_to_one_relations(self):
        # Refs #14694. Test reverse relations which are known unique (reverse
        # side has o2ofield or unique FK) - the o2o case
        """
        Tests the behavior of Django ORM's select_related, defer, and only methods when working with one-to-one relationships, ensuring they fetch related objects correctly and optimize database queries.
        """
        item = Item.objects.create(name="first", value=42)
        o2o = OneToOneItem.objects.create(item=item, name="second")
        self.assertEqual(len(Item.objects.defer("one_to_one_item__name")), 1)
        self.assertEqual(len(Item.objects.select_related("one_to_one_item")), 1)
        self.assertEqual(
            len(
                Item.objects.select_related("one_to_one_item").defer(
                    "one_to_one_item__name"
                )
            ),
            1,
        )
        self.assertEqual(
            len(Item.objects.select_related("one_to_one_item").defer("value")), 1
        )
        # Make sure that `only()` doesn't break when we pass in a unique relation,
        # rather than a field on the relation.
        self.assertEqual(len(Item.objects.only("one_to_one_item")), 1)
        with self.assertNumQueries(1):
            i = Item.objects.select_related("one_to_one_item")[0]
            self.assertEqual(i.one_to_one_item.pk, o2o.pk)
            self.assertEqual(i.one_to_one_item.name, "second")
        with self.assertNumQueries(1):
            i = Item.objects.select_related("one_to_one_item").defer(
                "value", "one_to_one_item__name"
            )[0]
            self.assertEqual(i.one_to_one_item.pk, o2o.pk)
            self.assertEqual(i.name, "first")
        with self.assertNumQueries(1):
            self.assertEqual(i.one_to_one_item.name, "second")
        with self.assertNumQueries(1):
            self.assertEqual(i.value, 42)
        with self.assertNumQueries(1):
            i = Item.objects.select_related("one_to_one_item").only(
                "name", "one_to_one_item__item"
            )[0]
            self.assertEqual(i.one_to_one_item.pk, o2o.pk)
            self.assertEqual(i.name, "first")
        with self.assertNumQueries(1):
            self.assertEqual(i.one_to_one_item.name, "second")
        with self.assertNumQueries(1):
            self.assertEqual(i.value, 42)

    def test_defer_with_select_related(self):
        """
        Provide a test case for deferred fields in conjunction with select_related to ensure correct behavior when retrieving and updating related objects.
        """
        item1 = Item.objects.create(name="first", value=47)
        item2 = Item.objects.create(name="second", value=42)
        simple = SimpleItem.objects.create(name="simple", value="23")
        ItemAndSimpleItem.objects.create(item=item1, simple=simple)

        obj = ItemAndSimpleItem.objects.defer("item").select_related("simple").get()
        self.assertEqual(obj.item, item1)
        self.assertEqual(obj.item_id, item1.id)

        obj.item = item2
        obj.save()

        obj = ItemAndSimpleItem.objects.defer("item").select_related("simple").get()
        self.assertEqual(obj.item, item2)
        self.assertEqual(obj.item_id, item2.id)

    def test_proxy_model_defer_with_select_related(self):
        # Regression for #22050
        """
        Tests that a proxy model with select_related defer loads the related model fields correctly.
        """
        item = Item.objects.create(name="first", value=47)
        RelatedItem.objects.create(item=item)
        # Defer fields with only()
        obj = ProxyRelated.objects.select_related().only("item__name")[0]
        with self.assertNumQueries(0):
            self.assertEqual(obj.item.name, "first")
        with self.assertNumQueries(1):
            self.assertEqual(obj.item.value, 47)

    def test_only_with_select_related(self):
        # Test for #17485.
        """
        Verifies that the only() and select_related() query methods can be used together to fetch specific fields from related models, while also ensuring related objects are prefetched to prevent additional database queries.
        """
        item = SimpleItem.objects.create(name="first", value=47)
        feature = Feature.objects.create(item=item)
        SpecialFeature.objects.create(feature=feature)

        qs = Feature.objects.only("item__name").select_related("item")
        self.assertEqual(len(qs), 1)

        qs = SpecialFeature.objects.only("feature__item__name").select_related(
            "feature__item"
        )
        self.assertEqual(len(qs), 1)

    def test_defer_annotate_select_related(self):
        """
        Tests that the `annotate`, `select_related`, `only`, and `defer` methods work correctly together on the Request model's QuerySet, ensuring they return instances as expected and allowing for efficient querying with aggregated annotations and selective field retrieval.
        """
        location = Location.objects.create()
        Request.objects.create(location=location)
        self.assertIsInstance(
            list(
                Request.objects.annotate(Count("items"))
                .select_related("profile", "location")
                .only("profile", "location")
            ),
            list,
        )
        self.assertIsInstance(
            list(
                Request.objects.annotate(Count("items"))
                .select_related("profile", "location")
                .only("profile__profile1", "location__location1")
            ),
            list,
        )
        self.assertIsInstance(
            list(
                Request.objects.annotate(Count("items"))
                .select_related("profile", "location")
                .defer("request1", "request2", "request3", "request4")
            ),
            list,
        )

    def test_common_model_different_mask(self):
        """
        Tests that using select_related and defer together can load related models with some fields deferred, 
        verifying that deferred fields are loaded when accessed and only one query is made for loading the related models 
        and additional queries are made when accessing the deferred fields.
        """
        child = Child.objects.create(name="Child", value=42)
        second_child = Child.objects.create(name="Second", value=64)
        Leaf.objects.create(child=child, second_child=second_child)
        with self.assertNumQueries(1):
            leaf = (
                Leaf.objects.select_related("child", "second_child")
                .defer("child__name", "second_child__value")
                .get()
            )
            self.assertEqual(leaf.child, child)
            self.assertEqual(leaf.second_child, second_child)
        self.assertEqual(leaf.child.get_deferred_fields(), {"name"})
        self.assertEqual(leaf.second_child.get_deferred_fields(), {"value"})
        with self.assertNumQueries(0):
            self.assertEqual(leaf.child.value, 42)
            self.assertEqual(leaf.second_child.name, "Second")
        with self.assertNumQueries(1):
            self.assertEqual(leaf.child.name, "Child")
        with self.assertNumQueries(1):
            self.assertEqual(leaf.second_child.value, 64)

    def test_defer_many_to_many_ignored(self):
        location = Location.objects.create()
        request = Request.objects.create(location=location)
        with self.assertNumQueries(1):
            self.assertEqual(Request.objects.defer("items").get(), request)

    def test_only_many_to_many_ignored(self):
        location = Location.objects.create()
        request = Request.objects.create(location=location)
        with self.assertNumQueries(1):
            self.assertEqual(Request.objects.only("items").get(), request)

    def test_defer_reverse_many_to_many_ignored(self):
        """
        Tests that deferring the 'request' field on an Item object with a many-to-many relationship does not cause additional database queries when retrieving the item.
        """
        location = Location.objects.create()
        request = Request.objects.create(location=location)
        item = Item.objects.create(value=1)
        request.items.add(item)
        with self.assertNumQueries(1):
            self.assertEqual(Item.objects.defer("request").get(), item)

    def test_only_reverse_many_to_many_ignored(self):
        """
        Tests that the 'only' method ignores many-to-many fields when retrieving an object, 
        ensuring a single database query is performed.\"\"\"
        ```
        """
        location = Location.objects.create()
        request = Request.objects.create(location=location)
        item = Item.objects.create(value=1)
        request.items.add(item)
        with self.assertNumQueries(1):
            self.assertEqual(Item.objects.only("request").get(), item)

    def test_self_referential_one_to_one(self):
        """
        Tests a self-referential one-to-one relationship between items, 
        ensuring efficient database queries when accessing related attributes.
        """
        first = Item.objects.create(name="first", value=1)
        second = Item.objects.create(name="second", value=2, source=first)
        with self.assertNumQueries(1):
            deferred_first, deferred_second = (
                Item.objects.select_related("source", "destination")
                .only("name", "source__name", "destination__value")
                .order_by("pk")
            )
        with self.assertNumQueries(0):
            self.assertEqual(deferred_first.name, first.name)
            self.assertEqual(deferred_second.name, second.name)
            self.assertEqual(deferred_second.source.name, first.name)
            self.assertEqual(deferred_first.destination.value, second.value)
        with self.assertNumQueries(1):
            self.assertEqual(deferred_first.value, first.value)
        with self.assertNumQueries(1):
            self.assertEqual(deferred_second.source.value, first.value)
        with self.assertNumQueries(1):
            self.assertEqual(deferred_first.destination.name, second.name)


class DeferDeletionSignalsTests(TestCase):
    senders = [Item, Proxy]

    @classmethod
    def setUpTestData(cls):
        cls.item_pk = Item.objects.create(value=1).pk

    def setUp(self):
        """

        Sets up event handlers for model deletion events.
        Connects pre_delete and post_delete signals to the respective receivers for all senders and schedules their disconnection after test completion.

        """
        self.pre_delete_senders = []
        self.post_delete_senders = []
        for sender in self.senders:
            models.signals.pre_delete.connect(self.pre_delete_receiver, sender)
            self.addCleanup(
                models.signals.pre_delete.disconnect, self.pre_delete_receiver, sender
            )
            models.signals.post_delete.connect(self.post_delete_receiver, sender)
            self.addCleanup(
                models.signals.post_delete.disconnect, self.post_delete_receiver, sender
            )

    def pre_delete_receiver(self, sender, **kwargs):
        self.pre_delete_senders.append(sender)

    def post_delete_receiver(self, sender, **kwargs):
        self.post_delete_senders.append(sender)

    def test_delete_defered_model(self):
        Item.objects.only("value").get(pk=self.item_pk).delete()
        self.assertEqual(self.pre_delete_senders, [Item])
        self.assertEqual(self.post_delete_senders, [Item])

    def test_delete_defered_proxy_model(self):
        Proxy.objects.only("value").get(pk=self.item_pk).delete()
        self.assertEqual(self.pre_delete_senders, [Proxy])
        self.assertEqual(self.post_delete_senders, [Proxy])
