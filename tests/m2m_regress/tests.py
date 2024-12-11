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

        Tests multiple many-to-many relationships between different models.

        Verifies that objects can be correctly added to and retrieved from many-to-many
        fields, including self-referential relationships and relationships between different
        models (e.g., entries and tags).

        The test checks that the relationships are properly established and that the objects
        are correctly retrieved in the expected order.

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
        msg = (
            "Choices are: id, name, references, related, selfreferchild, "
            "selfreferchildsibling"
        )
        with self.assertRaisesMessage(FieldError, msg):
            SelfRefer.objects.filter(porcupine="fred")

    def test_m2m_inheritance_symmetry(self):
        # Test to ensure that the relationship between two inherited models
        # with a self-referential m2m field maintains symmetry

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

        """
        Tests that a many-to-many relationship's primary key field type is correctly handled.

        This test case exercises the creation, saving, and deletion of a worksheet instance,
        verifying that the many-to-many field is properly managed throughout the process.\"\"\"

        However considering empty function body it might make more sense to write:

        \"\"\"Tests that a many-to-many relationship's primary key field type is correctly handled.

        This test case is intended to verify the correct handling of many-to-many field's primary key type
        when creating, saving and deleting a worksheet instance, but its implementation is currently missing.
        """
        w = Worksheet(id="abc")
        w.save()
        w.delete()

    def test_create_copy_with_m2m(self):
        """

        Tests the creation of a copy of an Entry instance with many-to-many relationships.

        This test ensures that when a new Entry is created as a copy of an existing one,
        its many-to-many relationships are preserved. In this case, the relationship is
        between an Entry and a Tag. The test verifies that the copied Entry retains the
        same topics as the original Entry.

        The test covers the following scenarios:
        - Creating a new Entry and assigning a Tag to it
        - Creating a copy of the Entry and saving it
        - Verifying that the copied Entry has the same topics as the original Entry

        """
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

        t1 = Tag.objects.create(name="t1")
        t2 = Tag.objects.create(name="t2")

        c1 = TagCollection.objects.create(name="c1")
        c1.tags.set([t1, t2])
        c1 = TagCollection.objects.get(name="c1")

        self.assertCountEqual(c1.tags.all(), [t1, t2])
        self.assertCountEqual(t1.tag_collections.all(), [c1])

    def test_manager_class_caching(self):
        """

        Tests the caching behavior of the Entry and Tag manager classes.

        This test verifies that the manager classes for Entry and Tag instances are 
        cached properly, ensuring that the same class is returned for multiple 
        instances of the same model. It checks the consistency of the manager classes 
        for both entry and tag objects, confirming that they are properly cached and 
        remain consistent across different instances.

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
        """
        Tests the many-to-many relationship abstraction with a split operation.

        This test method creates a RegressionModelSplit instance, assigns it a name, and saves it to verify the proper functioning of the many-to-many relationship abstraction in the context of model splits.

        Args:
            None

        Returns:
            None

        Raises:
            None

        Note:
            This test is part of a larger suite of tests for ensuring the correct operation of abstracted many-to-many relationships in the application's data model.
        """
        m1 = RegressionModelSplit(name="1")
        m1.save()

    def test_assigning_invalid_data_to_m2m_doesnt_clear_existing_relations(self):
        """

        Tests that assigning invalid data to a many-to-many relationship field does not clear existing relations.

        This test verifies that when attempting to set a many-to-many relationship field to a value that is not iterable (in this case, an integer),
        the operation raises a TypeError and leaves the existing relations intact.

        The test ensures that the original relations are preserved by checking the tags associated with the TagCollection instance after the
        attempted assignment, confirming that the existing tags remain unchanged.

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
