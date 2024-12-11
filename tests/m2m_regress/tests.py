from django.core.exceptions import FieldError
from django.test import TestCase

from .models import (
    Entry,
    Line,
    Post,
    RegressionModelSplit,
    SelfRefer,
    SelfReferChild,
    SelfReferChildSibling,
    Tag,
    TagCollection,
    Worksheet,
)


class M2MRegressionTests(TestCase):
    def test_multiple_m2m(self):
        # Multiple m2m references to model must be distinguished when
        # accessing the relations through an instance attribute.

        """

        Tests the functionality of multiple many-to-many relationships in different models.

        Verifies that entities can be correctly associated with each other through multiple
        many-to-many fields, including self-referential relationships and relationships
        between different models. Ensures that the relationships are established and
        retrieved correctly, and that the resulting sequences of related entities are as expected.

        """
        s1 = SelfRefer.objects.create(name="s1")
        s2 = SelfRefer.objects.create(name="s2")
        s3 = SelfRefer.objects.create(name="s3")
        s1.references.add(s2)
        s1.related.add(s3)

        e1 = Entry.objects.create(name="e1")
        t1 = Tag.objects.create(name="t1")
        t2 = Tag.objects.create(name="t2")

        e1.topics.add(t1)
        e1.related.add(t2)

        self.assertSequenceEqual(s1.references.all(), [s2])
        self.assertSequenceEqual(s1.related.all(), [s3])

        self.assertSequenceEqual(e1.topics.all(), [t1])
        self.assertSequenceEqual(e1.related.all(), [t2])

    def test_internal_related_name_not_in_error_msg(self):
        # The secret internal related names for self-referential many-to-many
        # fields shouldn't appear in the list when an error is made.
        """
        Tests that an internal, related field name is not included in the error message when a non-existent field is queried.

        Verifies that attempting to filter a SelfRefer object by a non-existent field named 'porcupine' raises a FieldError with a specific message, 
        indicating that the internal, related field name is properly hidden from the error output. 

        The expected error message includes a list of valid field choices, demonstrating that the error handling correctly reports available options without 
        exposing internal implementation details.
        """
        msg = (
            "Choices are: id, name, references, related, selfreferchild, "
            "selfreferchildsibling"
        )
        with self.assertRaisesMessage(FieldError, msg):
            SelfRefer.objects.filter(porcupine="fred")

    def test_m2m_inheritance_symmetry(self):
        # Test to ensure that the relationship between two inherited models
        # with a self-referential m2m field maintains symmetry

        """
        Tests the symmetry of many-to-many (m2m) relationships with inheritance in the SelfReferChild and SelfReferChildSibling models.

        Verifies that when a relationship is established between a SelfReferChild instance and a SelfReferChildSibling instance, the relationship is correctly reflected on both sides, i.e., both the child and the sibling can retrieve the related instances of each other.
        """
        sr_child = SelfReferChild(name="Hanna")
        sr_child.save()

        sr_sibling = SelfReferChildSibling(name="Beth")
        sr_sibling.save()
        sr_child.related.add(sr_sibling)

        self.assertSequenceEqual(sr_child.related.all(), [sr_sibling.selfrefer_ptr])
        self.assertSequenceEqual(sr_sibling.related.all(), [sr_child.selfrefer_ptr])

    def test_m2m_pk_field_type(self):
        # Regression for #11311 - The primary key for models in a m2m relation
        # doesn't have to be an AutoField

        w = Worksheet(id="abc")
        w.save()
        w.delete()

    def test_create_copy_with_m2m(self):
        t1 = Tag.objects.create(name="t1")
        Entry.objects.create(name="e1")
        entry = Entry.objects.first()
        entry.topics.set([t1])
        old_topics = entry.topics.all()
        entry.pk = None
        entry._state.adding = True
        entry.save()
        entry.topics.set(old_topics)
        entry = Entry.objects.get(pk=entry.pk)
        self.assertCountEqual(entry.topics.all(), old_topics)
        self.assertSequenceEqual(entry.topics.all(), [t1])

    def test_add_m2m_with_base_class(self):
        # Regression for #11956 -- You can add an object to a m2m with the
        # base class without causing integrity errors

        """

        Tests the addition of many-to-many relationships between Tag and TagCollection models.

        This test case verifies that tags can be successfully added to a tag collection and
        that the relationship is correctly established in both directions, i.e., a tag can
        be associated with multiple tag collections and a tag collection can have multiple
        tags. The test ensures that the tags and collections are properly linked and that
        the resulting sets of tags and collections can be accurately retrieved.

        """
        t1 = Tag.objects.create(name="t1")
        t2 = Tag.objects.create(name="t2")

        c1 = TagCollection.objects.create(name="c1")
        c1.tags.set([t1, t2])
        c1 = TagCollection.objects.get(name="c1")

        self.assertCountEqual(c1.tags.all(), [t1, t2])
        self.assertCountEqual(t1.tag_collections.all(), [c1])

    def test_manager_class_caching(self):
        """

        Tests the consistency of class caching for manager instances.

        This test case verifies that the class of manager instances is consistent 
        across different instances of models. Specifically, it checks that the 
        classes of the manager instances for 'entry_set' and 'topics' are the 
        same when accessed from different model instances.

        The purpose of this test is to ensure that the caching mechanism for 
        manager classes is working correctly, and that it does not introduce 
        any inconsistencies in the behavior of the models.

        """
        e1 = Entry.objects.create()
        e2 = Entry.objects.create()
        t1 = Tag.objects.create()
        t2 = Tag.objects.create()

        # Get same manager twice in a row:
        self.assertIs(t1.entry_set.__class__, t1.entry_set.__class__)
        self.assertIs(e1.topics.__class__, e1.topics.__class__)

        # Get same manager for different instances
        self.assertIs(e1.topics.__class__, e2.topics.__class__)
        self.assertIs(t1.entry_set.__class__, t2.entry_set.__class__)

    def test_m2m_abstract_split(self):
        # Regression for #19236 - an abstract class with a 'split' method
        # causes a TypeError in add_lazy_relation
        m1 = RegressionModelSplit(name="1")
        m1.save()

    def test_assigning_invalid_data_to_m2m_doesnt_clear_existing_relations(self):
        """

        Tests that assigning invalid data to a many-to-many field does not clear existing relations.

        When attempting to set a non-iterable value to a many-to-many field, the function should raise a TypeError.
        The existing relations should remain intact, and the initial state of the object should be preserved.

        This test ensures that the data integrity is maintained in such scenarios, preventing unintended data loss.

        """
        t1 = Tag.objects.create(name="t1")
        t2 = Tag.objects.create(name="t2")
        c1 = TagCollection.objects.create(name="c1")
        c1.tags.set([t1, t2])

        with self.assertRaisesMessage(TypeError, "'int' object is not iterable"):
            c1.tags.set(7)

        c1.refresh_from_db()
        self.assertSequenceEqual(c1.tags.order_by("name"), [t1, t2])

    def test_multiple_forwards_only_m2m(self):
        # Regression for #24505 - Multiple ManyToManyFields to same "to"
        # model with related_name set to '+'.
        foo = Line.objects.create(name="foo")
        bar = Line.objects.create(name="bar")
        post = Post.objects.create()
        post.primary_lines.add(foo)
        post.secondary_lines.add(bar)
        self.assertSequenceEqual(post.primary_lines.all(), [foo])
        self.assertSequenceEqual(post.secondary_lines.all(), [bar])
