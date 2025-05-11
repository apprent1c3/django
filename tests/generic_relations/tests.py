from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.prefetch import GenericPrefetch
from django.core.exceptions import FieldError
from django.db.models import Q, prefetch_related_objects
from django.test import SimpleTestCase, TestCase, skipUnlessDBFeature

from .models import (
    AllowsNullGFK,
    Animal,
    Carrot,
    Comparison,
    ConcreteRelatedModel,
    ForConcreteModelModel,
    ForProxyModelModel,
    Gecko,
    ManualPK,
    Mineral,
    ProxyRelatedModel,
    Rock,
    TaggedItem,
    ValuableRock,
    ValuableTaggedItem,
    Vegetable,
)


class GenericRelationsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for classes to use during testing, creating instances of animals, vegetables, minerals, and their associated tags.
        """
        cls.lion = Animal.objects.create(common_name="Lion", latin_name="Panthera leo")
        cls.platypus = Animal.objects.create(
            common_name="Platypus",
            latin_name="Ornithorhynchus anatinus",
        )
        Vegetable.objects.create(name="Eggplant", is_yucky=True)
        cls.bacon = Vegetable.objects.create(name="Bacon", is_yucky=False)
        cls.quartz = Mineral.objects.create(name="Quartz", hardness=7)

        # Tagging stuff.
        cls.fatty = cls.bacon.tags.create(tag="fatty")
        cls.salty = cls.bacon.tags.create(tag="salty")
        cls.yellow = cls.lion.tags.create(tag="yellow")
        cls.hairy = cls.lion.tags.create(tag="hairy")

    def comp_func(self, obj):
        # Original list of tags:
        return obj.tag, obj.content_type.model_class(), obj.object_id

    async def test_generic_async_acreate(self):
        await self.bacon.tags.acreate(tag="orange")
        self.assertEqual(await self.bacon.tags.acount(), 3)

    def test_generic_update_or_create_when_created(self):
        """
        Tests that the update_or_create method of a generic related manager can successfully create a new tag instance when one does not already exist.
        """
        count = self.bacon.tags.count()
        tag, created = self.bacon.tags.update_or_create(tag="stinky")
        self.assertTrue(created)
        self.assertEqual(count + 1, self.bacon.tags.count())

    def test_generic_update_or_create_when_created_with_create_defaults(self):
        """
        Tests that update_or_create method creates a new instance when it doesn't exist, using the provided create defaults and returns the created instance and a flag indicating creation occurred.
        """
        count = self.bacon.tags.count()
        tag, created = self.bacon.tags.update_or_create(
            # Since, the "stinky" tag doesn't exist create
            # a "juicy" tag.
            create_defaults={"tag": "juicy"},
            defaults={"tag": "uncured"},
            tag="stinky",
        )
        self.assertEqual(tag.tag, "juicy")
        self.assertIs(created, True)
        self.assertEqual(count + 1, self.bacon.tags.count())

    def test_generic_update_or_create_when_updated(self):
        """
        Tests the ability to update an existing tag using the update_or_create method from a generic related manager, ensuring that the tag is updated correctly without creating a new instance.
        """
        count = self.bacon.tags.count()
        tag = self.bacon.tags.create(tag="stinky")
        self.assertEqual(count + 1, self.bacon.tags.count())
        tag, created = self.bacon.tags.update_or_create(
            defaults={"tag": "juicy"}, id=tag.id
        )
        self.assertFalse(created)
        self.assertEqual(count + 1, self.bacon.tags.count())
        self.assertEqual(tag.tag, "juicy")

    def test_generic_update_or_create_when_updated_with_defaults(self):
        """
        Tests the update_or_create method on a model's related object manager when updating an existing object with default values.

        Ensures that the method successfully updates the object without creating a new one and returns the updated object and False to indicate no creation occurred.
        """
        count = self.bacon.tags.count()
        tag = self.bacon.tags.create(tag="stinky")
        self.assertEqual(count + 1, self.bacon.tags.count())
        tag, created = self.bacon.tags.update_or_create(
            create_defaults={"tag": "uncured"}, defaults={"tag": "juicy"}, id=tag.id
        )
        self.assertIs(created, False)
        self.assertEqual(count + 1, self.bacon.tags.count())
        self.assertEqual(tag.tag, "juicy")

    async def test_generic_async_aupdate_or_create(self):
        """
        Tests the asynchronous update or creation of a tag, ensuring that existing tags are updated and new tags are created with the correct values, while also verifying the overall count of tags.
        """
        tag, created = await self.bacon.tags.aupdate_or_create(
            id=self.fatty.id, defaults={"tag": "orange"}
        )
        self.assertIs(created, False)
        self.assertEqual(tag.tag, "orange")
        self.assertEqual(await self.bacon.tags.acount(), 2)
        tag, created = await self.bacon.tags.aupdate_or_create(tag="pink")
        self.assertIs(created, True)
        self.assertEqual(await self.bacon.tags.acount(), 3)
        self.assertEqual(tag.tag, "pink")

    async def test_generic_async_aupdate_or_create_with_create_defaults(self):
        """
        Tests the asynchronous update or creation of a tag, covering both the update of an existing tag and the creation of a new one with default values. Verifies the correctness of the created or updated tag and the overall count of tags.
        """
        tag, created = await self.bacon.tags.aupdate_or_create(
            id=self.fatty.id,
            create_defaults={"tag": "pink"},
            defaults={"tag": "orange"},
        )
        self.assertIs(created, False)
        self.assertEqual(tag.tag, "orange")
        self.assertEqual(await self.bacon.tags.acount(), 2)
        tag, created = await self.bacon.tags.aupdate_or_create(
            tag="pink", create_defaults={"tag": "brown"}
        )
        self.assertIs(created, True)
        self.assertEqual(await self.bacon.tags.acount(), 3)
        self.assertEqual(tag.tag, "brown")

    def test_generic_get_or_create_when_created(self):
        """
        Tests the successful creation of a tag using the get_or_create method from the generic related manager.
        """
        count = self.bacon.tags.count()
        tag, created = self.bacon.tags.get_or_create(tag="stinky")
        self.assertTrue(created)
        self.assertEqual(count + 1, self.bacon.tags.count())

    def test_generic_get_or_create_when_exists(self):
        """
        Tests the functionality of the get_or_create method on a generic related manager, 
        verifying it correctly retrieves an existing object without creating a new one.
        """
        count = self.bacon.tags.count()
        tag = self.bacon.tags.create(tag="stinky")
        self.assertEqual(count + 1, self.bacon.tags.count())
        tag, created = self.bacon.tags.get_or_create(
            id=tag.id, defaults={"tag": "juicy"}
        )
        self.assertFalse(created)
        self.assertEqual(count + 1, self.bacon.tags.count())
        # shouldn't had changed the tag
        self.assertEqual(tag.tag, "stinky")

    async def test_generic_async_aget_or_create(self):
        """
        Tests the asynchronous get or create functionality for tags, verifying that it correctly handles existing and non-existing tags, and updates the tag count accordingly.
        """
        tag, created = await self.bacon.tags.aget_or_create(
            id=self.fatty.id, defaults={"tag": "orange"}
        )
        self.assertIs(created, False)
        self.assertEqual(tag.tag, "fatty")
        self.assertEqual(await self.bacon.tags.acount(), 2)
        tag, created = await self.bacon.tags.aget_or_create(tag="orange")
        self.assertIs(created, True)
        self.assertEqual(await self.bacon.tags.acount(), 3)
        self.assertEqual(tag.tag, "orange")

    def test_generic_relations_m2m_mimic(self):
        """
        Objects with declared GenericRelations can be tagged directly -- the
        API mimics the many-to-many API.
        """
        self.assertSequenceEqual(self.lion.tags.all(), [self.hairy, self.yellow])
        self.assertSequenceEqual(self.bacon.tags.all(), [self.fatty, self.salty])

    def test_access_content_object(self):
        """
        Test accessing the content object like a foreign key.
        """
        tagged_item = TaggedItem.objects.get(tag="salty")
        self.assertEqual(tagged_item.content_object, self.bacon)

    def test_query_content_object(self):
        """

         Tests the ability to query TaggedItem objects by their content objects, 
        ensuring correct filtering and ordering by animal common name and tag. 
        Also verifies that the query can combine filtering by different content objects.

        """
        qs = TaggedItem.objects.filter(animal__isnull=False).order_by(
            "animal__common_name", "tag"
        )
        self.assertSequenceEqual(qs, [self.hairy, self.yellow])

        mpk = ManualPK.objects.create(id=1)
        mpk.tags.create(tag="mpk")
        qs = TaggedItem.objects.filter(
            Q(animal__isnull=False) | Q(manualpk__id=1)
        ).order_by("tag")
        self.assertQuerySetEqual(qs, ["hairy", "mpk", "yellow"], lambda x: x.tag)

    def test_exclude_generic_relations(self):
        """
        .Tests the retrieval of TaggedItem objects associated with a specific content object, 
        excluding those that involve generic relations, to ensure correct lookup functionality.
        """
        # Recall that the Mineral class doesn't have an explicit GenericRelation
        # defined. That's OK, because you can create TaggedItems explicitly.
        # However, excluding GenericRelations means your lookups have to be a
        # bit more explicit.
        shiny = TaggedItem.objects.create(content_object=self.quartz, tag="shiny")
        clearish = TaggedItem.objects.create(content_object=self.quartz, tag="clearish")

        ctype = ContentType.objects.get_for_model(self.quartz)
        q = TaggedItem.objects.filter(
            content_type__pk=ctype.id, object_id=self.quartz.id
        )
        self.assertSequenceEqual(q, [clearish, shiny])

    def test_access_via_content_type(self):
        """
        Checks that objects can be correctly retrieved using their content type in conjunction with applied tags.
        """
        self.lion.delete()
        self.platypus.tags.create(tag="fatty")

        ctype = ContentType.objects.get_for_model(self.platypus)

        self.assertSequenceEqual(
            Animal.objects.filter(tags__content_type=ctype),
            [self.platypus],
        )

    def test_set_foreign_key(self):
        """
        Tests the ability to set a foreign key on a generic relation, specifically verifying that reassigning a tagged item to a different content object updates the tags accordingly.
        """
        tag1 = TaggedItem.objects.create(content_object=self.quartz, tag="shiny")
        tag1.content_object = self.platypus
        tag1.save()

        self.assertSequenceEqual(self.platypus.tags.all(), [tag1])

    def test_queries_across_generic_relations(self):
        """
        Queries across generic relations respect the content types. Even though
        there are two TaggedItems with a tag of "fatty", this query only pulls
        out the one with the content type related to Animals.
        """
        self.assertSequenceEqual(
            Animal.objects.order_by("common_name"),
            [self.lion, self.platypus],
        )

    def test_queries_content_type_restriction(self):
        """
        Tests that content type restriction is applied correctly in queries involving tagged instances.\"\"\"
        ```
        """
        mpk = ManualPK.objects.create(id=self.lion.pk)
        mpk.tags.create(tag="fatty")
        self.platypus.tags.create(tag="fatty")

        self.assertSequenceEqual(
            Animal.objects.filter(tags__tag="fatty"),
            [self.platypus],
        )
        self.assertSequenceEqual(
            Animal.objects.exclude(tags__tag="fatty"),
            [self.lion],
        )

    def test_object_deletion_with_generic_relation(self):
        """
        If you delete an object with an explicit Generic relation, the related
        objects are deleted when the source object is deleted.
        """
        self.assertQuerySetEqual(
            TaggedItem.objects.all(),
            [
                ("fatty", Vegetable, self.bacon.pk),
                ("hairy", Animal, self.lion.pk),
                ("salty", Vegetable, self.bacon.pk),
                ("yellow", Animal, self.lion.pk),
            ],
            self.comp_func,
        )
        self.lion.delete()

        self.assertQuerySetEqual(
            TaggedItem.objects.all(),
            [
                ("fatty", Vegetable, self.bacon.pk),
                ("salty", Vegetable, self.bacon.pk),
            ],
            self.comp_func,
        )

    def test_object_deletion_without_generic_relation(self):
        """
        Tests the behavior of object deletion when a generic relation is not explicitly defined, ensuring related objects remain after the source object is deleted.
        """
        TaggedItem.objects.create(content_object=self.quartz, tag="clearish")
        quartz_pk = self.quartz.pk
        self.quartz.delete()
        self.assertQuerySetEqual(
            TaggedItem.objects.all(),
            [
                ("clearish", Mineral, quartz_pk),
                ("fatty", Vegetable, self.bacon.pk),
                ("hairy", Animal, self.lion.pk),
                ("salty", Vegetable, self.bacon.pk),
                ("yellow", Animal, self.lion.pk),
            ],
            self.comp_func,
        )

    def test_tag_deletion_related_objects_unaffected(self):
        """
        Verifies that deleting a tag does not affect the objects that were tagged, except for the removal of the tag itself.
        """
        ctype = ContentType.objects.get_for_model(self.lion)
        tag = TaggedItem.objects.get(
            content_type__pk=ctype.id, object_id=self.lion.id, tag="hairy"
        )
        tag.delete()

        self.assertSequenceEqual(self.lion.tags.all(), [self.yellow])
        self.assertQuerySetEqual(
            TaggedItem.objects.all(),
            [
                ("fatty", Vegetable, self.bacon.pk),
                ("salty", Vegetable, self.bacon.pk),
                ("yellow", Animal, self.lion.pk),
            ],
            self.comp_func,
        )

    def test_add_bulk(self):
        """

        Tests adding multiple tags to a vegetable in bulk.

        Verifies that the operation is performed efficiently in a single database query
        and that the tags are correctly associated with the vegetable.

        """
        bacon = Vegetable.objects.create(name="Bacon", is_yucky=False)
        t1 = TaggedItem.objects.create(content_object=self.quartz, tag="shiny")
        t2 = TaggedItem.objects.create(content_object=self.quartz, tag="clearish")
        # One update() query.
        with self.assertNumQueries(1):
            bacon.tags.add(t1, t2)
        self.assertEqual(t1.content_object, bacon)
        self.assertEqual(t2.content_object, bacon)

    def test_add_bulk_false(self):
        """
        Tests adding multiple tags to an object with bulk=False, verifying the tags are correctly assigned and the database queries are optimized.
        """
        bacon = Vegetable.objects.create(name="Bacon", is_yucky=False)
        t1 = TaggedItem.objects.create(content_object=self.quartz, tag="shiny")
        t2 = TaggedItem.objects.create(content_object=self.quartz, tag="clearish")
        # One save() for each object.
        with self.assertNumQueries(2):
            bacon.tags.add(t1, t2, bulk=False)
        self.assertEqual(t1.content_object, bacon)
        self.assertEqual(t2.content_object, bacon)

    def test_add_rejects_unsaved_objects(self):
        t1 = TaggedItem(content_object=self.quartz, tag="shiny")
        msg = (
            "<TaggedItem: shiny> instance isn't saved. Use bulk=False or save the "
            "object first."
        )
        with self.assertRaisesMessage(ValueError, msg):
            self.bacon.tags.add(t1)

    def test_add_rejects_wrong_instances(self):
        msg = "'TaggedItem' instance expected, got <Animal: Lion>"
        with self.assertRaisesMessage(TypeError, msg):
            self.bacon.tags.add(self.lion)

    async def test_aadd(self):
        """
         Tests adding tags to an object using the aadd method. Verifies that the tags are successfully associated and the count of tags is accurate. 
        """
        bacon = await Vegetable.objects.acreate(name="Bacon", is_yucky=False)
        t1 = await TaggedItem.objects.acreate(content_object=self.quartz, tag="shiny")
        t2 = await TaggedItem.objects.acreate(content_object=self.quartz, tag="fatty")
        await bacon.tags.aadd(t1, t2, bulk=False)
        self.assertEqual(await bacon.tags.acount(), 2)

    def test_set(self):
        """
        Tests the set method of a Vegetable's tags, ensuring it correctly replaces existing tags with the provided list, in both bulk and non-bulk modes.
        """
        bacon = Vegetable.objects.create(name="Bacon", is_yucky=False)
        fatty = bacon.tags.create(tag="fatty")
        salty = bacon.tags.create(tag="salty")

        bacon.tags.set([fatty, salty])
        self.assertSequenceEqual(bacon.tags.all(), [fatty, salty])

        bacon.tags.set([fatty])
        self.assertSequenceEqual(bacon.tags.all(), [fatty])

        bacon.tags.set([])
        self.assertSequenceEqual(bacon.tags.all(), [])

        bacon.tags.set([fatty, salty], bulk=False, clear=True)
        self.assertSequenceEqual(bacon.tags.all(), [fatty, salty])

        bacon.tags.set([fatty], bulk=False, clear=True)
        self.assertSequenceEqual(bacon.tags.all(), [fatty])

        bacon.tags.set([], clear=True)
        self.assertSequenceEqual(bacon.tags.all(), [])

    async def test_aset(self):
        """
        Tests the functionality of the aset method, which is used to set or replace the tags associated with a Vegetable object.

         Verifies that the aset method correctly updates the tags, handles bulk operations, and clears existing tags when necessary.
        """
        bacon = await Vegetable.objects.acreate(name="Bacon", is_yucky=False)
        fatty = await bacon.tags.acreate(tag="fatty")
        await bacon.tags.aset([fatty])
        self.assertEqual(await bacon.tags.acount(), 1)
        await bacon.tags.aset([])
        self.assertEqual(await bacon.tags.acount(), 0)
        await bacon.tags.aset([fatty], bulk=False, clear=True)
        self.assertEqual(await bacon.tags.acount(), 1)

    def test_assign(self):
        """

        Tests the assignment of tags to a vegetable object.

        Verifies that tags can be added, removed, and updated correctly.

        """
        bacon = Vegetable.objects.create(name="Bacon", is_yucky=False)
        fatty = bacon.tags.create(tag="fatty")
        salty = bacon.tags.create(tag="salty")

        bacon.tags.set([fatty, salty])
        self.assertSequenceEqual(bacon.tags.all(), [fatty, salty])

        bacon.tags.set([fatty])
        self.assertSequenceEqual(bacon.tags.all(), [fatty])

        bacon.tags.set([])
        self.assertSequenceEqual(bacon.tags.all(), [])

    def test_assign_with_queryset(self):
        # Querysets used in reverse GFK assignments are pre-evaluated so their
        # value isn't affected by the clearing operation
        # in ManyRelatedManager.set() (#19816).
        """

        Tests that assigning a queryset to an object's many-to-many field replaces the existing related objects.

        Verifies that the resulting set contains only the objects from the assigned queryset.

        """
        bacon = Vegetable.objects.create(name="Bacon", is_yucky=False)
        bacon.tags.create(tag="fatty")
        bacon.tags.create(tag="salty")
        self.assertEqual(2, bacon.tags.count())

        qs = bacon.tags.filter(tag="fatty")
        bacon.tags.set(qs)

        self.assertEqual(1, bacon.tags.count())
        self.assertEqual(1, qs.count())

    def test_clear(self):
        self.assertSequenceEqual(
            TaggedItem.objects.order_by("tag"),
            [self.fatty, self.hairy, self.salty, self.yellow],
        )
        self.bacon.tags.clear()
        self.assertSequenceEqual(self.bacon.tags.all(), [])
        self.assertSequenceEqual(
            TaggedItem.objects.order_by("tag"),
            [self.hairy, self.yellow],
        )

    async def test_aclear(self):
        await self.bacon.tags.aclear()
        self.assertEqual(await self.bacon.tags.acount(), 0)

    def test_remove(self):
        self.assertSequenceEqual(
            TaggedItem.objects.order_by("tag"),
            [self.fatty, self.hairy, self.salty, self.yellow],
        )
        self.bacon.tags.remove(self.fatty)
        self.assertSequenceEqual(self.bacon.tags.all(), [self.salty])
        self.assertSequenceEqual(
            TaggedItem.objects.order_by("tag"),
            [self.hairy, self.salty, self.yellow],
        )

    async def test_aremove(self):
        await self.bacon.tags.aremove(self.fatty)
        self.assertEqual(await self.bacon.tags.acount(), 1)
        await self.bacon.tags.aremove(self.salty)
        self.assertEqual(await self.bacon.tags.acount(), 0)

    def test_generic_relation_related_name_default(self):
        # GenericRelation isn't usable from the reverse side by default.
        msg = (
            "Cannot resolve keyword 'vegetable' into field. Choices are: "
            "animal, content_object, content_type, content_type_id, id, "
            "manualpk, object_id, tag, valuabletaggeditem"
        )
        with self.assertRaisesMessage(FieldError, msg):
            TaggedItem.objects.filter(vegetable__isnull=True)

    def test_multiple_gfk(self):
        # Simple tests for multiple GenericForeignKeys
        # only uses one model, since the above tests should be sufficient.
        """
        Tests the creation and management of multiple generic foreign key comparisons between Animal objects, including filtering, deletion, and cascading effects on related comparisons.
        """
        tiger = Animal.objects.create(common_name="tiger")
        cheetah = Animal.objects.create(common_name="cheetah")
        bear = Animal.objects.create(common_name="bear")

        # Create directly
        c1 = Comparison.objects.create(
            first_obj=cheetah, other_obj=tiger, comparative="faster"
        )
        c2 = Comparison.objects.create(
            first_obj=tiger, other_obj=cheetah, comparative="cooler"
        )

        # Create using GenericRelation
        c3 = tiger.comparisons.create(other_obj=bear, comparative="cooler")
        c4 = tiger.comparisons.create(other_obj=cheetah, comparative="stronger")
        self.assertSequenceEqual(cheetah.comparisons.all(), [c1])

        # Filtering works
        self.assertCountEqual(
            tiger.comparisons.filter(comparative="cooler"),
            [c2, c3],
        )

        # Filtering and deleting works
        subjective = ["cooler"]
        tiger.comparisons.filter(comparative__in=subjective).delete()
        self.assertCountEqual(Comparison.objects.all(), [c1, c4])

        # If we delete cheetah, Comparisons with cheetah as 'first_obj' will be
        # deleted since Animal has an explicit GenericRelation to Comparison
        # through first_obj. Comparisons with cheetah as 'other_obj' will not
        # be deleted.
        cheetah.delete()
        self.assertSequenceEqual(Comparison.objects.all(), [c4])

    def test_gfk_subclasses(self):
        # GenericForeignKey should work with subclasses (see #8309)
        quartz = Mineral.objects.create(name="Quartz", hardness=7)
        valuedtag = ValuableTaggedItem.objects.create(
            content_object=quartz, tag="shiny", value=10
        )
        self.assertEqual(valuedtag.content_object, quartz)

    def test_generic_relation_to_inherited_child(self):
        # GenericRelations to models that use multi-table inheritance work.
        """
        Tests the generic relationship between a model and its tagged items, 
        particularly when the model is an inherited child, verifying tag filtering and object deletion cascade.
        """
        granite = ValuableRock.objects.create(name="granite", hardness=5)
        ValuableTaggedItem.objects.create(
            content_object=granite, tag="countertop", value=1
        )
        self.assertEqual(ValuableRock.objects.filter(tags__value=1).count(), 1)
        # We're generating a slightly inefficient query for tags__tag - we
        # first join ValuableRock -> TaggedItem -> ValuableTaggedItem, and then
        # we fetch tag by joining TaggedItem from ValuableTaggedItem. The last
        # join isn't necessary, as TaggedItem <-> ValuableTaggedItem is a
        # one-to-one join.
        self.assertEqual(ValuableRock.objects.filter(tags__tag="countertop").count(), 1)
        granite.delete()  # deleting the rock should delete the related tag.
        self.assertEqual(ValuableTaggedItem.objects.count(), 0)

    def test_gfk_manager(self):
        # GenericForeignKey should not use the default manager (which may
        # filter objects).
        tailless = Gecko.objects.create(has_tail=False)
        tag = TaggedItem.objects.create(content_object=tailless, tag="lizard")
        self.assertEqual(tag.content_object, tailless)

    def test_subclasses_with_gen_rel(self):
        """
        Concrete model subclasses with generic relations work
        correctly (ticket 11263).
        """
        granite = Rock.objects.create(name="granite", hardness=5)
        TaggedItem.objects.create(content_object=granite, tag="countertop")
        self.assertEqual(Rock.objects.get(tags__tag="countertop"), granite)

    def test_subclasses_with_parent_gen_rel(self):
        """
        Generic relations on a base class (Vegetable) work correctly in
        subclasses (Carrot).
        """
        bear = Carrot.objects.create(name="carrot")
        TaggedItem.objects.create(content_object=bear, tag="orange")
        self.assertEqual(Carrot.objects.get(tags__tag="orange"), bear)

    def test_get_or_create(self):
        # get_or_create should work with virtual fields (content_object)
        """
        Tests the get_or_create functionality of TaggedItem, ensuring a new tag is created when the specified tag does not exist and attached to a content object.
        """
        quartz = Mineral.objects.create(name="Quartz", hardness=7)
        tag, created = TaggedItem.objects.get_or_create(
            tag="shiny", defaults={"content_object": quartz}
        )
        self.assertTrue(created)
        self.assertEqual(tag.tag, "shiny")
        self.assertEqual(tag.content_object.id, quartz.id)

    def test_update_or_create_defaults(self):
        # update_or_create should work with virtual fields (content_object)
        """
        Tests the update_or_create functionality for TaggedItem objects.

        Verifies that updating or creating TaggedItem instances with the same tag value 
        works as expected, including setting default values and determining whether a 
        new object was created.
        """
        quartz = Mineral.objects.create(name="Quartz", hardness=7)
        diamond = Mineral.objects.create(name="Diamond", hardness=7)
        tag, created = TaggedItem.objects.update_or_create(
            tag="shiny", defaults={"content_object": quartz}
        )
        self.assertTrue(created)
        self.assertEqual(tag.content_object.id, quartz.id)

        tag, created = TaggedItem.objects.update_or_create(
            tag="shiny", defaults={"content_object": diamond}
        )
        self.assertFalse(created)
        self.assertEqual(tag.content_object.id, diamond.id)

    def test_update_or_create_defaults_with_create_defaults(self):
        # update_or_create() should work with virtual fields (content_object).
        """
        Update or create a TaggedItem instance with the given tag, utilizing the provided defaults if the item does not exist; the create_defaults dictionary takes precedence over defaults when creating a new instance.
        """
        quartz = Mineral.objects.create(name="Quartz", hardness=7)
        diamond = Mineral.objects.create(name="Diamond", hardness=7)
        tag, created = TaggedItem.objects.update_or_create(
            tag="shiny",
            create_defaults={"content_object": quartz},
            defaults={"content_object": diamond},
        )
        self.assertIs(created, True)
        self.assertEqual(tag.content_object.id, quartz.id)

        tag, created = TaggedItem.objects.update_or_create(
            tag="shiny",
            create_defaults={"content_object": quartz},
            defaults={"content_object": diamond},
        )
        self.assertIs(created, False)
        self.assertEqual(tag.content_object.id, diamond.id)

    def test_query_content_type(self):
        msg = "Field 'content_object' does not generate an automatic reverse relation"
        with self.assertRaisesMessage(FieldError, msg):
            TaggedItem.objects.get(content_object="")

    def test_unsaved_generic_foreign_key_parent_save(self):
        """
        Tests that saving an instance with an unsaved generic foreign key parent raises a ValueError to prevent data loss.
        """
        quartz = Mineral(name="Quartz", hardness=7)
        tagged_item = TaggedItem(tag="shiny", content_object=quartz)
        msg = (
            "save() prohibited to prevent data loss due to unsaved related object "
            "'content_object'."
        )
        with self.assertRaisesMessage(ValueError, msg):
            tagged_item.save()

    @skipUnlessDBFeature("has_bulk_insert")
    def test_unsaved_generic_foreign_key_parent_bulk_create(self):
        """
        Tests the prohibition of bulk creation for unsaved generic foreign key parent objects, ensuring data integrity by preventing potential data loss due to unsaved related objects.
        """
        quartz = Mineral(name="Quartz", hardness=7)
        tagged_item = TaggedItem(tag="shiny", content_object=quartz)
        msg = (
            "bulk_create() prohibited to prevent data loss due to unsaved related "
            "object 'content_object'."
        )
        with self.assertRaisesMessage(ValueError, msg):
            TaggedItem.objects.bulk_create([tagged_item])

    def test_cache_invalidation_for_content_type_id(self):
        # Create a Vegetable and Mineral with the same id.
        """
        Tests cache invalidation when content type ID is changed for a tagged item.

        Ensures that when the content type ID of a tagged item is updated, the cached
        content object is correctly updated to reflect the new content type.
        """
        new_id = (
            max(
                Vegetable.objects.order_by("-id")[0].id,
                Mineral.objects.order_by("-id")[0].id,
            )
            + 1
        )
        broccoli = Vegetable.objects.create(id=new_id, name="Broccoli")
        diamond = Mineral.objects.create(id=new_id, name="Diamond", hardness=7)
        tag = TaggedItem.objects.create(content_object=broccoli, tag="yummy")
        tag.content_type = ContentType.objects.get_for_model(diamond)
        self.assertEqual(tag.content_object, diamond)

    def test_cache_invalidation_for_object_id(self):
        """

        Tests that the cache for a TaggedItem is invalidated when the object_id is updated.

        Verifies that changing the object_id of a TaggedItem correctly updates the associated content object.

        """
        broccoli = Vegetable.objects.create(name="Broccoli")
        cauliflower = Vegetable.objects.create(name="Cauliflower")
        tag = TaggedItem.objects.create(content_object=broccoli, tag="yummy")
        tag.object_id = cauliflower.id
        self.assertEqual(tag.content_object, cauliflower)

    def test_assign_content_object_in_init(self):
        spinach = Vegetable(name="spinach")
        tag = TaggedItem(content_object=spinach)
        self.assertEqual(tag.content_object, spinach)

    def test_create_after_prefetch(self):
        platypus = Animal.objects.prefetch_related("tags").get(pk=self.platypus.pk)
        self.assertSequenceEqual(platypus.tags.all(), [])
        weird_tag = platypus.tags.create(tag="weird")
        self.assertSequenceEqual(platypus.tags.all(), [weird_tag])

    def test_add_after_prefetch(self):
        """
        Tests adding a tag to an object after it has been prefetched, ensuring that the new tag is correctly associated with the object and included in the prefetched related objects.
        """
        platypus = Animal.objects.prefetch_related("tags").get(pk=self.platypus.pk)
        self.assertSequenceEqual(platypus.tags.all(), [])
        weird_tag = TaggedItem.objects.create(tag="weird", content_object=platypus)
        platypus.tags.add(weird_tag)
        self.assertSequenceEqual(platypus.tags.all(), [weird_tag])

    def test_remove_after_prefetch(self):
        """
        Tests the removal of tags from an Animal instance after prefetching related tags.
        """
        weird_tag = self.platypus.tags.create(tag="weird")
        platypus = Animal.objects.prefetch_related("tags").get(pk=self.platypus.pk)
        self.assertSequenceEqual(platypus.tags.all(), [weird_tag])
        platypus.tags.remove(weird_tag)
        self.assertSequenceEqual(platypus.tags.all(), [])

    def test_clear_after_prefetch(self):
        """
        Tests that the clear method removes all tags from an Animal instance after prefetching the tags.
        """
        weird_tag = self.platypus.tags.create(tag="weird")
        platypus = Animal.objects.prefetch_related("tags").get(pk=self.platypus.pk)
        self.assertSequenceEqual(platypus.tags.all(), [weird_tag])
        platypus.tags.clear()
        self.assertSequenceEqual(platypus.tags.all(), [])

    def test_set_after_prefetch(self):
        """
        Tests that the prefetching of related objects does not interfere with setting new relationships for a model instance.
        """
        platypus = Animal.objects.prefetch_related("tags").get(pk=self.platypus.pk)
        self.assertSequenceEqual(platypus.tags.all(), [])
        furry_tag = TaggedItem.objects.create(tag="furry", content_object=platypus)
        platypus.tags.set([furry_tag])
        self.assertSequenceEqual(platypus.tags.all(), [furry_tag])
        weird_tag = TaggedItem.objects.create(tag="weird", content_object=platypus)
        platypus.tags.set([weird_tag])
        self.assertSequenceEqual(platypus.tags.all(), [weird_tag])

    def test_add_then_remove_after_prefetch(self):
        """

        Tests adding and then removing a tag from an animal instance after prefetching its tags.

        Verifies that tags are correctly added and removed from the prefetched collection.

        """
        furry_tag = self.platypus.tags.create(tag="furry")
        platypus = Animal.objects.prefetch_related("tags").get(pk=self.platypus.pk)
        self.assertSequenceEqual(platypus.tags.all(), [furry_tag])
        weird_tag = self.platypus.tags.create(tag="weird")
        platypus.tags.add(weird_tag)
        self.assertSequenceEqual(platypus.tags.all(), [furry_tag, weird_tag])
        platypus.tags.remove(weird_tag)
        self.assertSequenceEqual(platypus.tags.all(), [furry_tag])

    def test_prefetch_related_different_content_types(self):
        """
        Tests the correctness of prefetching related objects for TaggedItem instances with different content types, ensuring that the related objects and their tags are fetched efficiently in a minimal number of database queries.
        """
        TaggedItem.objects.create(content_object=self.platypus, tag="prefetch_tag_1")
        TaggedItem.objects.create(
            content_object=Vegetable.objects.create(name="Broccoli"),
            tag="prefetch_tag_2",
        )
        TaggedItem.objects.create(
            content_object=Animal.objects.create(common_name="Bear"),
            tag="prefetch_tag_3",
        )
        qs = TaggedItem.objects.filter(
            tag__startswith="prefetch_tag_",
        ).prefetch_related("content_object", "content_object__tags")
        with self.assertNumQueries(4):
            tags = list(qs)
        for tag in tags:
            self.assertSequenceEqual(tag.content_object.tags.all(), [tag])

    def test_prefetch_related_custom_object_id(self):
        """

        Tests that prefetching a custom related object id for a Comparison model works correctly.
        Verifies that the related comparisons for the 'first_obj' are properly prefetched and retrieved.

        """
        tiger = Animal.objects.create(common_name="tiger")
        cheetah = Animal.objects.create(common_name="cheetah")
        Comparison.objects.create(
            first_obj=cheetah,
            other_obj=tiger,
            comparative="faster",
        )
        Comparison.objects.create(
            first_obj=tiger,
            other_obj=cheetah,
            comparative="cooler",
        )
        qs = Comparison.objects.prefetch_related("first_obj__comparisons")
        for comparison in qs:
            self.assertSequenceEqual(
                comparison.first_obj.comparisons.all(), [comparison]
            )

    def test_generic_prefetch(self):
        """
        Tests the functionality of generic prefetching for TaggedItem objects.

        Ensures that related objects can be prefetched efficiently, reducing the number of database queries.

        The test verifies that generic prefetching works correctly for different types of related objects (Vegetable and Animal) and that it only fetches the required fields (e.g., 'common_name' for Animal objects).

        It also checks that subsequent database queries are eliminated when accessing prefetched related objects and their attributes.
        """
        tagged_vegetable = TaggedItem.objects.create(
            tag="great", content_object=self.bacon
        )
        tagged_animal = TaggedItem.objects.create(
            tag="awesome", content_object=self.platypus
        )
        # Getting the instances again so that content object is deferred.
        tagged_vegetable = TaggedItem.objects.get(pk=tagged_vegetable.pk)
        tagged_animal = TaggedItem.objects.get(pk=tagged_animal.pk)

        with self.assertNumQueries(2):
            prefetch_related_objects(
                [tagged_vegetable, tagged_animal],
                GenericPrefetch(
                    "content_object",
                    [Vegetable.objects.all(), Animal.objects.only("common_name")],
                ),
            )
        with self.assertNumQueries(0):
            self.assertEqual(tagged_vegetable.content_object.name, self.bacon.name)
        with self.assertNumQueries(0):
            self.assertEqual(
                tagged_animal.content_object.common_name,
                self.platypus.common_name,
            )
        with self.assertNumQueries(1):
            self.assertEqual(
                tagged_animal.content_object.latin_name,
                self.platypus.latin_name,
            )


class ProxyRelatedModelTest(TestCase):
    def test_default_behavior(self):
        """
        Tests that the default behavior of ForConcreteModelModel is to set for_concrete_model to True, ensuring that a related object is correctly associated with its concrete instance after saving and retrieving from the database.
        """
        base = ForConcreteModelModel()
        base.obj = rel = ProxyRelatedModel.objects.create()
        base.save()

        base = ForConcreteModelModel.objects.get(pk=base.pk)
        rel = ConcreteRelatedModel.objects.get(pk=rel.pk)
        self.assertEqual(base.obj, rel)

    def test_works_normally(self):
        """

        Verifies that the model functions correctly when not used for concrete models, 
        by testing the ability to retrieve an instance of the concrete class.

        """
        base = ForProxyModelModel()
        base.obj = rel = ConcreteRelatedModel.objects.create()
        base.save()

        base = ForProxyModelModel.objects.get(pk=base.pk)
        self.assertEqual(base.obj, rel)

    def test_proxy_is_returned(self):
        """
        Tests whether a proxy instance is returned when querying the model with for_concrete_model set to False.
        """
        base = ForProxyModelModel()
        base.obj = ProxyRelatedModel.objects.create()
        base.save()

        base = ForProxyModelModel.objects.get(pk=base.pk)
        self.assertIsInstance(base.obj, ProxyRelatedModel)

    def test_query(self):
        base = ForProxyModelModel()
        base.obj = rel = ConcreteRelatedModel.objects.create()
        base.save()

        self.assertEqual(rel, ConcreteRelatedModel.objects.get(bases__id=base.id))

    def test_query_proxy(self):
        base = ForProxyModelModel()
        base.obj = rel = ProxyRelatedModel.objects.create()
        base.save()

        self.assertEqual(rel, ProxyRelatedModel.objects.get(bases__id=base.id))

    def test_generic_relation(self):
        """
        Tests the generic relation between ForProxyModelModel and ProxyRelatedModel instances to ensure they are correctly established and retrieved.
        """
        base = ForProxyModelModel()
        base.obj = ProxyRelatedModel.objects.create()
        base.save()

        base = ForProxyModelModel.objects.get(pk=base.pk)
        rel = ProxyRelatedModel.objects.get(pk=base.obj.pk)
        self.assertEqual(base, rel.bases.get())

    def test_generic_relation_set(self):
        """
        Tests the establishment of a generic relation set between a base object and related objects, verifying that the relationship is correctly established and retrievable.
        """
        base = ForProxyModelModel()
        base.obj = ConcreteRelatedModel.objects.create()
        base.save()
        newrel = ConcreteRelatedModel.objects.create()

        newrel.bases.set([base])
        newrel = ConcreteRelatedModel.objects.get(pk=newrel.pk)
        self.assertEqual(base, newrel.bases.get())


class TestInitWithNoneArgument(SimpleTestCase):
    def test_none_allowed(self):
        # AllowsNullGFK doesn't require a content_type, so None argument should
        # also be allowed.
        AllowsNullGFK(content_object=None)
        # TaggedItem requires a content_type but initializing with None should
        # be allowed.
        TaggedItem(content_object=None)
