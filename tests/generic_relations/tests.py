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
        """

        Tests the asynchronous creation of a new tag.

        This test case verifies that the asynchronous creation operation
        successfully adds a new tag to the existing collection and updates
        the tag count accordingly.

        The test creates a new tag with the name 'orange' and then asserts
        that the total number of tags is incremented to 3.

        """
        await self.bacon.tags.acreate(tag="orange")
        self.assertEqual(await self.bacon.tags.acount(), 3)

    def test_generic_update_or_create_when_created(self):
        """
        Should be able to use update_or_create from the generic related manager
        to create a tag. Refs #23611.
        """
        count = self.bacon.tags.count()
        tag, created = self.bacon.tags.update_or_create(tag="stinky")
        self.assertTrue(created)
        self.assertEqual(count + 1, self.bacon.tags.count())

    def test_generic_update_or_create_when_created_with_create_defaults(self):
        """

        Tests the update_or_create method for a generic relationship when a new object is created.

        The test verifies that when update_or_create is called with create defaults, a new object is created with the specified default values.
        It also checks that the created flag is set to True and that the count of related objects is incremented by one.

        This test case covers the scenario where a new object is created with default values, ensuring that the update_or_create method behaves correctly in this situation.

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
        Should be able to use update_or_create from the generic related manager
        to update a tag. Refs #23611.
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

        Tests the update_or_create method on a generic relation when default values are provided.

        The test creates a new tag instance and then attempts to update it using the update_or_create method,
        providing default values for both create and update scenarios.

        It verifies that the update operation is successful by checking that the instance was not re-created,
        the total count of tags remains the same, and the tag's attribute has been updated with the new value.

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

        Tests the asynchronous update or create functionality for tags.

        This test case exercises the aupdate_or_create method by attempting to update an existing tag and then create a new one.
        It verifies that the correct tag is returned, that the creation flag is set accordingly, and that the tag count is updated as expected.

        The test checks the following scenarios:

        * Updating an existing tag with a given id, verifying that the tag's attributes are updated correctly and that the creation flag is set to False.
        * Creating a new tag, verifying that the creation flag is set to True and that the tag count is incremented correctly.

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
        Should be able to use get_or_create from the generic related manager
        to create a tag. Refs #23611.
        """
        count = self.bacon.tags.count()
        tag, created = self.bacon.tags.get_or_create(tag="stinky")
        self.assertTrue(created)
        self.assertEqual(count + 1, self.bacon.tags.count())

    def test_generic_get_or_create_when_exists(self):
        """
        Should be able to use get_or_create from the generic related manager
        to get a tag. Refs #23611.
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
        Test lookups over an object without GenericRelations.
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
        Test lookups through content type.
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
        You can set a generic foreign key in the way you'd expect.
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
        Create another fatty tagged instance with different PK to ensure there
        is a content type restriction in the generated queries below.
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
        If Generic Relation is not explicitly defined, any related objects
        remain after deletion of the source object.
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
        If you delete a tag, the objects using the tag are unaffected (other
        than losing a tag).
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

        Tests the addition of multiple tags to an object in bulk.

        Verifies that the tags are correctly associated with the object and 
        that the database operations are performed efficiently, 
        specifically within a single query.

        This test covers the scenario where multiple existing tags are 
        added to a newly created object, ensuring data consistency and 
        Database query optimization. 

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

        Tests the ability to add multiple tags to an object without using bulk operations.

        Verifies that when adding multiple tags to an object with `bulk=False`, the 
        operation correctly assigns the content object of each tag to the object being 
        tagged. This test also checks that the database queries required to perform the 
        operation are optimized, resulting in the expected number of queries.

        The test case creates a new vegetable object and two tags, then adds these tags 
        to the vegetable object with `bulk=False`, confirming the correct assignment 
        of the tags and the number of database queries executed.

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
        """
        Tests that adding an unsaved TaggedItem instance to a Taggable object's tags raises a ValueError.

        The function checks that attempting to add an instance of TaggedItem that has not been saved to the database results in the expected error message, which instructs the user to either save the object first or use bulk=False.

        This test ensures the integrity of the data by preventing unsaved objects from being added to the tags, thus maintaining consistency in the database.
        """
        t1 = TaggedItem(content_object=self.quartz, tag="shiny")
        msg = (
            "<TaggedItem: shiny> instance isn't saved. Use bulk=False or save the "
            "object first."
        )
        with self.assertRaisesMessage(ValueError, msg):
            self.bacon.tags.add(t1)

    def test_add_rejects_wrong_instances(self):
        """

        Tests that attempting to add an incorrect type of instance to a tag collection raises a TypeError.

        The function verifies that only instances of 'TaggedItem' can be added to a tag collection, 
        and that adding any other type of instance will result in an error with a specific message.

        """
        msg = "'TaggedItem' instance expected, got <Animal: Lion>"
        with self.assertRaisesMessage(TypeError, msg):
            self.bacon.tags.add(self.lion)

    async def test_aadd(self):
        bacon = await Vegetable.objects.acreate(name="Bacon", is_yucky=False)
        t1 = await TaggedItem.objects.acreate(content_object=self.quartz, tag="shiny")
        t2 = await TaggedItem.objects.acreate(content_object=self.quartz, tag="fatty")
        await bacon.tags.aadd(t1, t2, bulk=False)
        self.assertEqual(await bacon.tags.acount(), 2)

    def test_set(self):
        """
        Tests the functionality of setting tags for a Vegetable object.

        This test creates a Vegetable instance and several associated tags, then checks 
        that the set() method correctly updates the tags associated with the object. It 
        covers various scenarios, including setting multiple tags, a single tag, and an 
        empty list of tags, as well as using the bulk and clear parameters to control 
        how the tags are updated.

        The test verifies that the set() method behaves as expected in different cases, 
        such as replacing existing tags, adding new tags, and removing all tags. It 
        ensures that the tags are correctly updated and that the resulting set of tags 
        matches the expected outcome.
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

        Tests the functionality of setting a list of associated objects in bulk or individually.

        This test case covers the following scenarios:

        * Creating an object and its associated tags
        * Setting a list of associated tags for an object
        * Verifying the correct count of associated tags after setting
        * Clearing all associated tags for an object
        * Setting a single associated tag for an object with the bulk option disabled

        The test ensures that the `aset` method correctly manages the associated objects and handles bulk operations as expected. 

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

        Checks that tags can be correctly created and assigned to a vegetable,
        and that the vegetable's tag set can be updated, added to, or cleared.

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

        Tests the assignment of a queryset to a model's many-to-many field.

        This test case checks the functionality of replacing the existing many-to-many relationships 
        of a model instance with a new set of relationships specified by a queryset. It verifies that 
        the previously associated objects are correctly removed and the new objects are associated 
        as expected.

        The test creates a Vegetable instance with multiple tags, then replaces the tags with a 
        queryset containing only one of the existing tags, and asserts that the Vegetable instance 
        is correctly updated with the new set of tags.

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
        """
        Tests the clear method of the tags attribute on the Bacon object.

        Verifies that the tags are correctly removed from the Bacon object and 
        that the TaggedItem query is updated accordingly, ensuring that the 
        correct items are returned after clearing the tags.

        This test case ensures data consistency and correct behavior of the 
        tags attribute after clearing, covering both the object's tags and the 
        related TaggedItem objects. 
        """
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
        """

        Tests that the asynchronous clear operation removes all tags.

        This test case verifies that after calling the asynchronous clear operation,
        there are no tags left, ensuring the tags are properly cleared.

        """
        await self.bacon.tags.aclear()
        self.assertEqual(await self.bacon.tags.acount(), 0)

    def test_remove(self):
        """
        Tests the removal of a tag from a tagged item, verifying that the item's tag list is updated correctly and the overall tag ordering remains consistent.

        Checks that removing a tag from a tagged item results in the expected changes to the item's tags and the overall sequence of tagged items, ensuring data integrity and correct behavior of the tagging system.
        """
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
        """
        Tests the asynchronous removal of tags from an object.

        This test case verifies that removing tags one by one decreases the total tag count as expected.
        It covers the scenario where all tags are removed, ensuring the count reaches zero after the last tag is removed.
        The test provides a basic sanity check for the aremove functionality, ensuring it behaves correctly and updates the tag count accordingly.
        """
        await self.bacon.tags.aremove(self.fatty)
        self.assertEqual(await self.bacon.tags.acount(), 1)
        await self.bacon.tags.aremove(self.salty)
        self.assertEqual(await self.bacon.tags.acount(), 0)

    def test_generic_relation_related_name_default(self):
        # GenericRelation isn't usable from the reverse side by default.
        """
        ..: 
            Tests the default behavior of the related_name attribute for generic relations.

            Verifies that attempting to filter on a non-existent related name 'vegetable' 
            raises a FieldError with a message indicating the available choices for the 
            related field. This ensures that the default related_name for generic 
            relations is correctly set and enforced by the ORM.
        """
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
        Tests the functionality of creating and managing multiple Generalized Foreign Key (GFK) comparisons between animal objects.

        This test case covers the creation of comparisons between different animal objects, 
        filtering comparisons based on the comparative value, and deletion of comparisons and animal objects.
        It verifies that comparisons are correctly associated with the respective animal objects and 
        that they are properly removed when the associated objects are deleted or when comparisons are explicitly deleted.

        The test case also checks for the correct count and sequence of comparisons after various operations, 
        ensuring the integrity and consistency of the data in the Comparison model.
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
        Tests the generic relation to an inherited child model, ensuring that tags are properly assigned and deleted. 

        This test case creates a ValuableRock instance and assigns a tag to it. It then checks that the tagged instance can be filtered by both the tag's value and the tag itself. Finally, it verifies that when the related object is deleted, the tag is also removed, demonstrating the proper cleanup of related objects.
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

        Tests the update_or_create method for TaggedItem objects.

        This test function checks the behavior of the update_or_create method when creating
        or updating a TaggedItem object. It verifies that the method correctly creates 
        a new object when a matching tag does not exist, and updates the existing object 
        when a matching tag already exists.

        It specifically tests the scenario where two objects (Quartz and Diamond) are 
        associated with a tag 'shiny', ensuring that the correct object is returned and 
        updated accordingly.

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
        """
        Tests that querying a model instance with an invalid content object raises a FieldError.

        This test case verifies that attempting to retrieve a TaggedItem instance using a content object
        that does not generate an automatic reverse relation results in the expected error message.

        The assertion ensures that a FieldError is raised with a message indicating that the 'content_object'
        field does not generate an automatic reverse relation, providing a safeguard against incorrect usage.

        """
        msg = "Field 'content_object' does not generate an automatic reverse relation"
        with self.assertRaisesMessage(FieldError, msg):
            TaggedItem.objects.get(content_object="")

    def test_unsaved_generic_foreign_key_parent_save(self):
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
        Tests bulk creation of objects with unsaved generic foreign key parents to ensure it raises an error and prevents data loss. 

        This test checks that attempting to bulk create a :class:`TaggedItem` instance with an unsaved :class:`Mineral` instance as its content object raises a :class:`ValueError` with a descriptive error message, thus preventing potential data loss due to the unsaved related object.
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
        Tests cache invalidation when the content type ID of a tagged item is updated.

        This test case verifies that the cache is properly invalidated when the content type ID
        associated with a tagged item is changed, ensuring that the correct content object
        is retrieved after the update.

        It covers a scenario where a tagged item is initially associated with an instance of
        one model (e.g. Vegetable), and then its content type ID is updated to reference an
        instance of a different model (e.g. Mineral).
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
        ..: 
            Tests cache invalidation for object id in a tagged item.

            This test ensures that when an object id is updated in a tagged item,
            the cache is correctly invalidated and the new content object is returned.
            It verifies that the relationship between the tagged item and its content object
            is updated as expected after changing the object id.
        """
        broccoli = Vegetable.objects.create(name="Broccoli")
        cauliflower = Vegetable.objects.create(name="Cauliflower")
        tag = TaggedItem.objects.create(content_object=broccoli, tag="yummy")
        tag.object_id = cauliflower.id
        self.assertEqual(tag.content_object, cauliflower)

    def test_assign_content_object_in_init(self):
        """
        '''Test the assignment of a content object to a TaggedItem instance during initialization.

        Verify that the content object assigned to the TaggedItem instance is correctly stored
        and retrievable as an attribute. This test ensures that the content object, in this
        case a Vegetable instance, is properly linked to the TaggedItem instance when created.'''
        """
        spinach = Vegetable(name="spinach")
        tag = TaggedItem(content_object=spinach)
        self.assertEqual(tag.content_object, spinach)

    def test_create_after_prefetch(self):
        """
        Tests the create functionality of a model instance's related objects after prefetching.

        This function verifies that creating a new related object after prefetching the original object's relations
        works correctly. It checks that the new object is successfully added to the original object's relation set
        and that the updated relation set is correctly reflected.

        The test case covers the scenario where a new related object is created and added to a previously prefetched
        relation, ensuring data consistency and correct behavior of the ORM's relation management functionality.
        """
        platypus = Animal.objects.prefetch_related("tags").get(pk=self.platypus.pk)
        self.assertSequenceEqual(platypus.tags.all(), [])
        weird_tag = platypus.tags.create(tag="weird")
        self.assertSequenceEqual(platypus.tags.all(), [weird_tag])

    def test_add_after_prefetch(self):
        platypus = Animal.objects.prefetch_related("tags").get(pk=self.platypus.pk)
        self.assertSequenceEqual(platypus.tags.all(), [])
        weird_tag = TaggedItem.objects.create(tag="weird", content_object=platypus)
        platypus.tags.add(weird_tag)
        self.assertSequenceEqual(platypus.tags.all(), [weird_tag])

    def test_remove_after_prefetch(self):
        """

        Tests the removal of a tag from an Animal instance after prefetching its tags.

        This test case verifies that the removal of a tag is correctly reflected in the 
        prefetched tags of an Animal instance. It checks that the tag is initially 
        associated with the Animal instance, and then confirms that the tag is no longer 
        associated after removal.

        The test covers the following scenarios:
        - The initial association of a tag with an Animal instance
        - The prefetching of tags for an Animal instance
        - The removal of a tag from an Animal instance
        - The verification that the removed tag is no longer associated with the Animal instance

        """
        weird_tag = self.platypus.tags.create(tag="weird")
        platypus = Animal.objects.prefetch_related("tags").get(pk=self.platypus.pk)
        self.assertSequenceEqual(platypus.tags.all(), [weird_tag])
        platypus.tags.remove(weird_tag)
        self.assertSequenceEqual(platypus.tags.all(), [])

    def test_clear_after_prefetch(self):
        """

        Tests that clearing a set of prefetched many-to-many related objects effectively removes all objects from the set.

        This test verifies that after prefetching related objects, clearing the set of objects has the expected effect of removing all objects from the set.

        """
        weird_tag = self.platypus.tags.create(tag="weird")
        platypus = Animal.objects.prefetch_related("tags").get(pk=self.platypus.pk)
        self.assertSequenceEqual(platypus.tags.all(), [weird_tag])
        platypus.tags.clear()
        self.assertSequenceEqual(platypus.tags.all(), [])

    def test_set_after_prefetch(self):
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

        Test adding and removing a tag from a prefetched many-to-many relationship.

        This test validates the behavior of adding and removing tags to an `Animal` object
        after it has been prefetched. It ensures that the changes are properly reflected
        in the prefetched relationship.

        The test covers the following scenarios:

        * Adding a tag to a prefetched object and verifying the updated relationship.
        * Removing a tag from a prefetched object and verifying the updated relationship.

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

        Tests the GenericPrefetch functionality to prefetch related objects.

        This test creates two tagged items, one related to a vegetable and one to an animal,
        and then uses GenericPrefetch to fetch the related objects. It verifies that the
        related objects are prefetched correctly by checking the number of database queries
        made when accessing their attributes.

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
        The default for for_concrete_model should be True
        """
        base = ForConcreteModelModel()
        base.obj = rel = ProxyRelatedModel.objects.create()
        base.save()

        base = ForConcreteModelModel.objects.get(pk=base.pk)
        rel = ConcreteRelatedModel.objects.get(pk=rel.pk)
        self.assertEqual(base.obj, rel)

    def test_works_normally(self):
        """
        When for_concrete_model is False, we should still be able to get
        an instance of the concrete class.
        """
        base = ForProxyModelModel()
        base.obj = rel = ConcreteRelatedModel.objects.create()
        base.save()

        base = ForProxyModelModel.objects.get(pk=base.pk)
        self.assertEqual(base.obj, rel)

    def test_proxy_is_returned(self):
        """
        Instances of the proxy should be returned when
        for_concrete_model is False.
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
        """

        Test the query functionality of the proxy model.

        Checks that an instance of :class:`ProxyRelatedModel` is correctly associated 
        with an instance of :class:`ForProxyModelModel`, and that this association can 
        be queried. This ensures that the proxy model is correctly set up and can be 
        used to retrieve related objects.

        """
        base = ForProxyModelModel()
        base.obj = rel = ProxyRelatedModel.objects.create()
        base.save()

        self.assertEqual(rel, ProxyRelatedModel.objects.get(bases__id=base.id))

    def test_generic_relation(self):
        """
        Tests the generic relation between ForProxyModelModel and ProxyRelatedModel instances.

        Verifies that after creating a new ProxyRelatedModel instance and associating it with a ForProxyModelModel,
        the relationship is correctly established and can be queried in both directions.

        Ensures that a ForProxyModelModel instance can be retrieved through its related ProxyRelatedModel instance,
        confirming the integrity of the generic relation.
        """
        base = ForProxyModelModel()
        base.obj = ProxyRelatedModel.objects.create()
        base.save()

        base = ForProxyModelModel.objects.get(pk=base.pk)
        rel = ProxyRelatedModel.objects.get(pk=base.obj.pk)
        self.assertEqual(base, rel.bases.get())

    def test_generic_relation_set(self):
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
        """

        Test that None is allowed as a content object for generic foreign keys.

        This test case verifies that certain models, specifically those utilizing 
        generic foreign keys, can successfully handle a content object of None.
        It checks the behavior of these models when the content object is not provided.

        """
        AllowsNullGFK(content_object=None)
        # TaggedItem requires a content_type but initializing with None should
        # be allowed.
        TaggedItem(content_object=None)
