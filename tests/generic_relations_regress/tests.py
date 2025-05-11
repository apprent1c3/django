from django.contrib.contenttypes.models import ContentType
from django.db.models import ProtectedError, Q, Sum
from django.forms.models import modelform_factory
from django.test import TestCase, skipIfDBFeature

from .models import (
    A,
    Address,
    B,
    Board,
    C,
    Cafe,
    CharLink,
    Company,
    Contact,
    Content,
    D,
    Guild,
    HasLinkThing,
    Link,
    Node,
    Note,
    OddRelation1,
    OddRelation2,
    Organization,
    Person,
    Place,
    Related,
    Restaurant,
    Tag,
    Team,
    TextLink,
)


class GenericRelationTests(TestCase):
    def test_inherited_models_content_type(self):
        """
        Checks that GenericRelations in inherited models correctly resolve content types for related objects, ensuring proper object retrieval and association.
        """
        p = Place.objects.create(name="South Park")
        r = Restaurant.objects.create(name="Chubby's")
        l1 = Link.objects.create(content_object=p)
        l2 = Link.objects.create(content_object=r)
        self.assertEqual(list(p.links.all()), [l1])
        self.assertEqual(list(r.links.all()), [l2])

    def test_reverse_relation_pk(self):
        """
        Tests the correct usage of primary key column names when querying through reverse relations, specifically verifying that the originating model's primary key is correctly referenced.
        """
        p = Person.objects.create(account=23, name="Chef")
        Address.objects.create(
            street="123 Anywhere Place",
            city="Conifer",
            state="CO",
            zipcode="80433",
            content_object=p,
        )

        qs = Person.objects.filter(addresses__zipcode="80433")
        self.assertEqual(1, qs.count())
        self.assertEqual("Chef", qs[0].name)

    def test_charlink_delete(self):
        oddrel = OddRelation1.objects.create(name="clink")
        CharLink.objects.create(content_object=oddrel)
        oddrel.delete()

    def test_textlink_delete(self):
        oddrel = OddRelation2.objects.create(name="tlink")
        TextLink.objects.create(content_object=oddrel)
        oddrel.delete()

    def test_charlink_filter(self):
        oddrel = OddRelation1.objects.create(name="clink")
        CharLink.objects.create(content_object=oddrel, value="value")
        self.assertSequenceEqual(
            OddRelation1.objects.filter(clinks__value="value"), [oddrel]
        )

    def test_textlink_filter(self):
        oddrel = OddRelation2.objects.create(name="clink")
        TextLink.objects.create(content_object=oddrel, value="value")
        self.assertSequenceEqual(
            OddRelation2.objects.filter(tlinks__value="value"), [oddrel]
        )

    def test_coerce_object_id_remote_field_cache_persistence(self):
        """

        Tests that the remote field cache for CharLink objects persists across database queries.

        This test case verifies that the content object associated with a CharLink instance
        is correctly cached and retrieved, even after new CharLink objects are created with
        different content objects.

        """
        restaurant = Restaurant.objects.create()
        CharLink.objects.create(content_object=restaurant)
        charlink = CharLink.objects.latest("pk")
        self.assertIs(charlink.content_object, charlink.content_object)
        # If the model (Cafe) uses more than one level of multi-table inheritance.
        cafe = Cafe.objects.create()
        CharLink.objects.create(content_object=cafe)
        charlink = CharLink.objects.latest("pk")
        self.assertIs(charlink.content_object, charlink.content_object)

    def test_q_object_or(self):
        """
        Tests that SQL query parameters for generic relations are correctly grouped when using the OR operator, ensuring consistent query results regardless of parameter order.
        """
        note_contact = Contact.objects.create()
        org_contact = Contact.objects.create()
        Note.objects.create(note="note", content_object=note_contact)
        org = Organization.objects.create(name="org name")
        org.contacts.add(org_contact)
        # search with a non-matching note and a matching org name
        qs = Contact.objects.filter(
            Q(notes__note__icontains=r"other note")
            | Q(organizations__name__icontains=r"org name")
        )
        self.assertIn(org_contact, qs)
        # search again, with the same query parameters, in reverse order
        qs = Contact.objects.filter(
            Q(organizations__name__icontains=r"org name")
            | Q(notes__note__icontains=r"other note")
        )
        self.assertIn(org_contact, qs)

    def test_join_reuse(self):
        qs = Person.objects.filter(addresses__street="foo").filter(
            addresses__street="bar"
        )
        self.assertEqual(str(qs.query).count("JOIN"), 2)

    def test_generic_relation_ordering(self):
        """
        Tests that ordering over a generic relation produces the expected results, 
        including all related rows and avoiding duplicates.
        """
        p1 = Place.objects.create(name="South Park")
        p2 = Place.objects.create(name="The City")
        c = Company.objects.create(name="Chubby's Intl.")
        Link.objects.create(content_object=p1)
        Link.objects.create(content_object=c)

        places = list(Place.objects.order_by("links__id"))

        def count_places(place):
            return len([p for p in places if p.id == place.id])

        self.assertEqual(len(places), 2)
        self.assertEqual(count_places(p1), 1)
        self.assertEqual(count_places(p2), 1)

    def test_target_model_len_zero(self):
        """
        Saving a model with a GenericForeignKey to a model instance whose
        __len__ method returns 0 (Team.__len__() here) shouldn't fail (#13085).
        """
        team1 = Team.objects.create(name="Backend devs")
        note = Note(note="Deserve a bonus", content_object=team1)
        note.save()

    def test_target_model_bool_false(self):
        """
        Saving a model with a GenericForeignKey to a model instance whose
        __bool__ method returns False (Guild.__bool__() here) shouldn't fail
        (#13085).
        """
        g1 = Guild.objects.create(name="First guild")
        note = Note(note="Note for guild", content_object=g1)
        note.save()

    @skipIfDBFeature("interprets_empty_strings_as_nulls")
    def test_gfk_to_model_with_empty_pk(self):
        """Test related to #13085"""
        # Saving model with GenericForeignKey to model instance with an
        # empty CharField PK
        b1 = Board.objects.create(name="")
        tag = Tag(label="VP", content_object=b1)
        tag.save()

    def test_ticket_20378(self):
        # Create a couple of extra HasLinkThing so that the autopk value
        # isn't the same for Link and HasLinkThing.
        """
        Tests filtering of HasLinkThing objects based on their associated links.
        """
        hs1 = HasLinkThing.objects.create()
        hs2 = HasLinkThing.objects.create()
        hs3 = HasLinkThing.objects.create()
        hs4 = HasLinkThing.objects.create()
        l1 = Link.objects.create(content_object=hs3)
        l2 = Link.objects.create(content_object=hs4)
        self.assertSequenceEqual(HasLinkThing.objects.filter(links=l1), [hs3])
        self.assertSequenceEqual(HasLinkThing.objects.filter(links=l2), [hs4])
        self.assertSequenceEqual(
            HasLinkThing.objects.exclude(links=l2), [hs1, hs2, hs3]
        )
        self.assertSequenceEqual(
            HasLinkThing.objects.exclude(links=l1), [hs1, hs2, hs4]
        )

    def test_ticket_20564(self):
        """

        Tests the query filtering functionality for default values (None) in related models.

        This test case ensures that filtering on a related model's attribute behaves correctly when the attribute is not explicitly set.

        """
        b1 = B.objects.create()
        b2 = B.objects.create()
        b3 = B.objects.create()
        c1 = C.objects.create(b=b1)
        c2 = C.objects.create(b=b2)
        c3 = C.objects.create(b=b3)
        A.objects.create(flag=None, content_object=b1)
        A.objects.create(flag=True, content_object=b2)
        self.assertSequenceEqual(C.objects.filter(b__a__flag=None), [c1, c3])
        self.assertSequenceEqual(C.objects.exclude(b__a__flag=None), [c2])

    def test_ticket_20564_nullable_fk(self):
        """
        Tests the behavior of nullable foreign keys in model queries, specifically the interaction between objects with and without associated instances through a generic foreign key.
        """
        b1 = B.objects.create()
        b2 = B.objects.create()
        b3 = B.objects.create()
        d1 = D.objects.create(b=b1)
        d2 = D.objects.create(b=b2)
        d3 = D.objects.create(b=b3)
        d4 = D.objects.create()
        A.objects.create(flag=None, content_object=b1)
        A.objects.create(flag=True, content_object=b1)
        A.objects.create(flag=True, content_object=b2)
        self.assertSequenceEqual(D.objects.exclude(b__a__flag=None), [d2])
        self.assertSequenceEqual(D.objects.filter(b__a__flag=None), [d1, d3, d4])
        self.assertSequenceEqual(B.objects.filter(a__flag=None), [b1, b3])
        self.assertSequenceEqual(B.objects.exclude(a__flag=None), [b2])

    def test_extra_join_condition(self):
        # A crude check that content_type_id is taken in account in the
        # join/subquery condition.
        self.assertIn(
            "content_type_id", str(B.objects.exclude(a__flag=None).query).lower()
        )
        # No need for any joins - the join from inner query can be trimmed in
        # this case (but not in the above case as no a objects at all for given
        # B would then fail).
        self.assertNotIn(" join ", str(B.objects.exclude(a__flag=True).query).lower())
        self.assertIn(
            "content_type_id", str(B.objects.exclude(a__flag=True).query).lower()
        )

    def test_annotate(self):
        """
        Tests the annotation of objects with summed link IDs, ensuring correct results when links exist and when they are deleted.
        """
        hs1 = HasLinkThing.objects.create()
        hs2 = HasLinkThing.objects.create()
        HasLinkThing.objects.create()
        b = Board.objects.create(name=str(hs1.pk))
        Link.objects.create(content_object=hs2)
        link = Link.objects.create(content_object=hs1)
        Link.objects.create(content_object=b)
        qs = HasLinkThing.objects.annotate(Sum("links")).filter(pk=hs1.pk)
        # If content_type restriction isn't in the query's join condition,
        # then wrong results are produced here as the link to b will also match
        # (b and hs1 have equal pks).
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs[0].links__sum, link.id)
        link.delete()
        # Now if we don't have proper left join, we will not produce any
        # results at all here.
        # clear cached results
        qs = qs.all()
        self.assertEqual(qs.count(), 1)
        # Note - 0 here would be a nicer result...
        self.assertIs(qs[0].links__sum, None)
        # Finally test that filtering works.
        self.assertEqual(qs.filter(links__sum__isnull=True).count(), 1)
        self.assertEqual(qs.filter(links__sum__isnull=False).count(), 0)

    def test_filter_targets_related_pk(self):
        # Use hardcoded PKs to ensure different PKs for "link" and "hs2"
        # objects.
        """
        Checks that filtering by link's pk correctly retrieves related objects. Verifies that object_id and pk are distinct values for the link, and that the filter returns the expected object.
        """
        HasLinkThing.objects.create(pk=1)
        hs2 = HasLinkThing.objects.create(pk=2)
        link = Link.objects.create(content_object=hs2, pk=1)
        self.assertNotEqual(link.object_id, link.pk)
        self.assertSequenceEqual(HasLinkThing.objects.filter(links=link.pk), [hs2])

    def test_editable_generic_rel(self):
        """
        Tests the behavior of a model form with a generic relation field, verifying that the field is correctly included in the form, accepts null input, and triggers the expected save behavior when the form is valid and saved.
        """
        GenericRelationForm = modelform_factory(HasLinkThing, fields="__all__")
        form = GenericRelationForm()
        self.assertIn("links", form.fields)
        form = GenericRelationForm({"links": None})
        self.assertTrue(form.is_valid())
        form.save()
        links = HasLinkThing._meta.get_field("links")
        self.assertEqual(links.save_form_data_calls, 1)

    def test_ticket_22998(self):
        """
        Tests the inability to delete a Related object when it is referenced by existing content, ensuring that ProtectedError is raised.
        """
        related = Related.objects.create()
        content = Content.objects.create(related_obj=related)
        Node.objects.create(content=content)

        # deleting the Related cascades to the Content cascades to the Node,
        # where the pre_delete signal should fire and prevent deletion.
        with self.assertRaises(ProtectedError):
            related.delete()

    def test_ticket_22982(self):
        place = Place.objects.create(name="My Place")
        self.assertIn("GenericRelatedObjectManager", str(place.links))

    def test_filter_on_related_proxy_model(self):
        place = Place.objects.create()
        Link.objects.create(content_object=place)
        self.assertEqual(Place.objects.get(link_proxy__object_id=place.id), place)

    def test_generic_reverse_relation_with_mti(self):
        """
        Tests the filtering of objects using a reverse generic relation that is defined through multi-table inheritance, ensuring that the correct objects are retrieved.
        """
        place = Place.objects.create(name="Test Place")
        link = Link.objects.create(content_object=place)
        result = Link.objects.filter(places=place)
        self.assertCountEqual(result, [link])

    def test_generic_reverse_relation_with_abc(self):
        """
        The reverse generic relation accessor (targets) is created if the
        GenericRelation comes from an abstract base model (HasLinks).
        """
        thing = HasLinkThing.objects.create()
        link = Link.objects.create(content_object=thing)
        self.assertCountEqual(link.targets.all(), [thing])

    def test_generic_reverse_relation_exclude_filter(self):
        """
        Tests that the exclude filter works correctly with generic reverse relations.

        Verifies that a query using the exclude filter with a generic reverse relation
        correctly filters out objects based on the related object's attributes.
        """
        place1 = Place.objects.create(name="Test Place 1")
        place2 = Place.objects.create(name="Test Place 2")
        Link.objects.create(content_object=place1)
        link2 = Link.objects.create(content_object=place2)
        qs = Link.objects.filter(~Q(places__name="Test Place 1"))
        self.assertSequenceEqual(qs, [link2])
        qs = Link.objects.exclude(places__name="Test Place 1")
        self.assertSequenceEqual(qs, [link2])

    def test_check_cached_value_pk_different_type(self):
        """
        Verifies that the primary key of a generic relation's content object is updated correctly when the content type is changed, without rechecking the primary key for compatibility.
        """
        board = Board.objects.create(name="some test")
        oddrel = OddRelation1.objects.create(name="clink")
        charlink = CharLink.objects.create(content_object=oddrel)
        charlink = CharLink.objects.get(pk=charlink.pk)
        self.assertEqual(charlink.content_object, oddrel)
        charlink.object_id = board.pk
        charlink.content_type_id = ContentType.objects.get_for_model(Board).id
        self.assertEqual(charlink.content_object, board)
