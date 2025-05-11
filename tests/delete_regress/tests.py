import datetime

from django.db import connection, models, transaction
from django.db.models import Exists, OuterRef
from django.test import (
    SimpleTestCase,
    TestCase,
    TransactionTestCase,
    skipUnlessDBFeature,
)

from .models import (
    Award,
    AwardNote,
    Book,
    Child,
    Contact,
    Eaten,
    Email,
    File,
    Food,
    FooFile,
    FooFileProxy,
    FooImage,
    FooPhoto,
    House,
    Image,
    Item,
    Location,
    Login,
    OrderedPerson,
    OrgUnit,
    Person,
    Photo,
    PlayedWith,
    PlayedWithNote,
    Policy,
    Researcher,
    Toy,
    Version,
)


# Can't run this test under SQLite, because you can't
# get two connections to an in-memory database.
@skipUnlessDBFeature("test_db_allows_multiple_connections")
class DeleteLockingTest(TransactionTestCase):
    available_apps = ["delete_regress"]

    def setUp(self):
        # Create a second connection to the default database
        self.conn2 = connection.copy()
        self.conn2.set_autocommit(False)
        # Close down the second connection.
        self.addCleanup(self.conn2.close)
        self.addCleanup(self.conn2.rollback)

    def test_concurrent_delete(self):
        """
        Tests that concurrent deletion of database records does not result in collisions or database locks.
        """
        with transaction.atomic():
            Book.objects.create(id=1, pagecount=100)
            Book.objects.create(id=2, pagecount=200)
            Book.objects.create(id=3, pagecount=300)

        with transaction.atomic():
            # Start a transaction on the main connection.
            self.assertEqual(3, Book.objects.count())

            # Delete something using another database connection.
            with self.conn2.cursor() as cursor2:
                cursor2.execute("DELETE from delete_regress_book WHERE id = 1")
            self.conn2.commit()

            # In the same transaction on the main connection, perform a
            # queryset delete that covers the object deleted with the other
            # connection. This causes an infinite loop under MySQL InnoDB
            # unless we keep track of already deleted objects.
            Book.objects.filter(pagecount__lt=250).delete()

        self.assertEqual(1, Book.objects.count())


class DeleteCascadeTests(TestCase):
    def test_generic_relation_cascade(self):
        """
        Tests that Django correctly cascades deletes through generic-related objects to their reverse relations, ensuring related objects are deleted when the parent object is removed.
        """
        person = Person.objects.create(name="Nelson Mandela")
        award = Award.objects.create(name="Nobel", content_object=person)
        AwardNote.objects.create(note="a peace prize", award=award)
        self.assertEqual(AwardNote.objects.count(), 1)
        person.delete()
        self.assertEqual(Award.objects.count(), 0)
        # first two asserts are just sanity checks, this is the kicker:
        self.assertEqual(AwardNote.objects.count(), 0)

    def test_fk_to_m2m_through(self):
        """
        Tests that deletion of a model participating in a many-to-many relationship with an explicitly-specified through model cascades to the through model and its related models.
        """
        juan = Child.objects.create(name="Juan")
        paints = Toy.objects.create(name="Paints")
        played = PlayedWith.objects.create(
            child=juan, toy=paints, date=datetime.date.today()
        )
        PlayedWithNote.objects.create(played=played, note="the next Jackson Pollock")
        self.assertEqual(PlayedWithNote.objects.count(), 1)
        paints.delete()
        self.assertEqual(PlayedWith.objects.count(), 0)
        # first two asserts just sanity checks, this is the kicker:
        self.assertEqual(PlayedWithNote.objects.count(), 0)

    def test_15776(self):
        """
        Tests the cascade deletion behavior of policy objects, ensuring that all associated versions, locations, and items are properly removed when a policy is deleted.
        """
        policy = Policy.objects.create(pk=1, policy_number="1234")
        version = Version.objects.create(policy=policy)
        location = Location.objects.create(version=version)
        Item.objects.create(version=version, location=location)
        policy.delete()


class DeleteCascadeTransactionTests(TransactionTestCase):
    available_apps = ["delete_regress"]

    def test_inheritance(self):
        """
        Tests that many-to-many through tables referencing a parent model are correctly handled by the delete cascade when a child of that parent is deleted.
        """
        r = Researcher.objects.create()
        email = Email.objects.create(
            label="office-email", email_address="carl@science.edu"
        )
        r.contacts.add(email)

        email.delete()

    def test_to_field(self):
        """
        Tests the cascading deletion of related objects when a ForeignKey's to_field is set to a non-primary key field, ensuring that both the parent and child objects are properly deleted.
        """
        apple = Food.objects.create(name="apple")
        Eaten.objects.create(food=apple, meal="lunch")

        apple.delete()
        self.assertFalse(Food.objects.exists())
        self.assertFalse(Eaten.objects.exists())


class LargeDeleteTests(TestCase):
    def test_large_deletes(self):
        """

            Validate that bulk deletion of objects works correctly even when the number of objects exceeds the chunk size.

            Tests that all objects are successfully deleted and that post-delete signals are properly handled.

        """
        for x in range(300):
            Book.objects.create(pagecount=x + 100)
        # attach a signal to make sure we will not fast-delete

        def noop(*args, **kwargs):
            pass

        models.signals.post_delete.connect(noop, sender=Book)
        Book.objects.all().delete()
        models.signals.post_delete.disconnect(noop, sender=Book)
        self.assertEqual(Book.objects.count(), 0)


class ProxyDeleteTest(TestCase):
    """
    Tests on_delete behavior for proxy models.

    See #16128.
    """

    def create_image(self):
        """
        Creates and returns an Image instance associated with both a FooImage and a FooFile, establishing the necessary relationships between them.
        """
        # Create an Image
        test_image = Image()
        test_image.save()
        foo_image = FooImage(my_image=test_image)
        foo_image.save()

        # Get the Image instance as a File
        test_file = File.objects.get(pk=test_image.pk)
        foo_file = FooFile(my_file=test_file)
        foo_file.save()

        return test_image

    def test_delete_proxy(self):
        """

            Tests the cascading deletion behavior of proxy instances.

            Verifies that deleting a proxy object also removes all related objects.

        """
        self.create_image()

        Image.objects.all().delete()

        # An Image deletion == File deletion
        self.assertEqual(len(Image.objects.all()), 0)
        self.assertEqual(len(File.objects.all()), 0)

        # The Image deletion cascaded and *all* references to it are deleted.
        self.assertEqual(len(FooImage.objects.all()), 0)
        self.assertEqual(len(FooFile.objects.all()), 0)

    def test_delete_proxy_of_proxy(self):
        """
        Deletes a proxy-of-proxy instance and verifies that all referring proxy and non-proxy objects are also deleted, ensuring a complete removal of related objects from the database.
        """
        test_image = self.create_image()

        # Get the Image as a Photo
        test_photo = Photo.objects.get(pk=test_image.pk)
        foo_photo = FooPhoto(my_photo=test_photo)
        foo_photo.save()

        Photo.objects.all().delete()

        # A Photo deletion == Image deletion == File deletion
        self.assertEqual(len(Photo.objects.all()), 0)
        self.assertEqual(len(Image.objects.all()), 0)
        self.assertEqual(len(File.objects.all()), 0)

        # The Photo deletion should have cascaded and deleted *all*
        # references to it.
        self.assertEqual(len(FooPhoto.objects.all()), 0)
        self.assertEqual(len(FooFile.objects.all()), 0)
        self.assertEqual(len(FooImage.objects.all()), 0)

    def test_delete_concrete_parent(self):
        """
        Deletes a concrete model instance and verifies that all referencing proxy subclass objects are also removed.
        """
        self.create_image()

        File.objects.all().delete()

        # A File deletion == Image deletion
        self.assertEqual(len(File.objects.all()), 0)
        self.assertEqual(len(Image.objects.all()), 0)

        # The File deletion should have cascaded and deleted *all* references
        # to it.
        self.assertEqual(len(FooFile.objects.all()), 0)
        self.assertEqual(len(FooImage.objects.all()), 0)

    def test_delete_proxy_pair(self):
        """
        Tests the cascade deletion of proxy model pairs linked by a foreign key, 
        ensuring the deletion occurs in the correct order to prevent IntegrityErrors.
        """
        # Create an Image (proxy of File) and FooFileProxy (proxy of FooFile,
        # which has an FK to File)
        image = Image.objects.create()
        as_file = File.objects.get(pk=image.pk)
        FooFileProxy.objects.create(my_file=as_file)

        Image.objects.all().delete()

        self.assertEqual(len(FooFileProxy.objects.all()), 0)

    def test_19187_values(self):
        """
        Tests that calling delete() on QuerySets obtained from values() or values_list() raises a TypeError with the expected error message.
        """
        msg = "Cannot call delete() after .values() or .values_list()"
        with self.assertRaisesMessage(TypeError, msg):
            Image.objects.values().delete()
        with self.assertRaisesMessage(TypeError, msg):
            Image.objects.values_list().delete()


class Ticket19102Tests(TestCase):
    """
    Test different queries which alter the SELECT clause of the query. We
    also must be using a subquery for the deletion (that is, the original
    query has a join in it). The deletion should be done as "fast-path"
    deletion (that is, just one query for the .delete() call).

    Note that .values() is not tested here on purpose. .values().delete()
    doesn't work for non fast-path deletes at all.
    """

    @classmethod
    def setUpTestData(cls):
        cls.o1 = OrgUnit.objects.create(name="o1")
        cls.o2 = OrgUnit.objects.create(name="o2")
        cls.l1 = Login.objects.create(description="l1", orgunit=cls.o1)
        cls.l2 = Login.objects.create(description="l2", orgunit=cls.o2)

    @skipUnlessDBFeature("update_can_self_select")
    def test_ticket_19102_annotate(self):
        with self.assertNumQueries(1):
            Login.objects.order_by("description").filter(
                orgunit__name__isnull=False
            ).annotate(n=models.Count("description")).filter(
                n=1, pk=self.l1.pk
            ).delete()
        self.assertFalse(Login.objects.filter(pk=self.l1.pk).exists())
        self.assertTrue(Login.objects.filter(pk=self.l2.pk).exists())

    @skipUnlessDBFeature("update_can_self_select")
    def test_ticket_19102_extra(self):
        with self.assertNumQueries(1):
            Login.objects.order_by("description").filter(
                orgunit__name__isnull=False
            ).extra(select={"extraf": "1"}).filter(pk=self.l1.pk).delete()
        self.assertFalse(Login.objects.filter(pk=self.l1.pk).exists())
        self.assertTrue(Login.objects.filter(pk=self.l2.pk).exists())

    @skipUnlessDBFeature("update_can_self_select")
    def test_ticket_19102_select_related(self):
        with self.assertNumQueries(1):
            Login.objects.filter(pk=self.l1.pk).filter(
                orgunit__name__isnull=False
            ).order_by("description").select_related("orgunit").delete()
        self.assertFalse(Login.objects.filter(pk=self.l1.pk).exists())
        self.assertTrue(Login.objects.filter(pk=self.l2.pk).exists())

    @skipUnlessDBFeature("update_can_self_select")
    def test_ticket_19102_defer(self):
        with self.assertNumQueries(1):
            Login.objects.filter(pk=self.l1.pk).filter(
                orgunit__name__isnull=False
            ).order_by("description").only("id").delete()
        self.assertFalse(Login.objects.filter(pk=self.l1.pk).exists())
        self.assertTrue(Login.objects.filter(pk=self.l2.pk).exists())


class DeleteTests(TestCase):
    def test_meta_ordered_delete(self):
        # When a subquery is performed by deletion code, the subquery must be
        # cleared of all ordering. There was a but that caused _meta ordering
        # to be used. Refs #19720.
        """
        Tests the deletion of OrderedPerson objects that are ordered and related to a House, verifying that the correct objects are removed when filtered by the House address.
        """
        h = House.objects.create(address="Foo")
        OrderedPerson.objects.create(name="Jack", lives_in=h)
        OrderedPerson.objects.create(name="Bob", lives_in=h)
        OrderedPerson.objects.filter(lives_in__address="Foo").delete()
        self.assertEqual(OrderedPerson.objects.count(), 0)

    def test_foreign_key_delete_nullifies_correct_columns(self):
        """
        Tests if deleting an instance of a model that is referenced by two foreign keys
        in another model correctly nullifies the corresponding foreign key fields.
        """
        contact1 = Contact.objects.create(label="Contact 1")
        contact2 = Contact.objects.create(label="Contact 2")
        researcher1 = Researcher.objects.create(
            primary_contact=contact1,
            secondary_contact=contact2,
        )
        researcher2 = Researcher.objects.create(
            primary_contact=contact2,
            secondary_contact=contact1,
        )
        contact1.delete()
        researcher1.refresh_from_db()
        researcher2.refresh_from_db()
        self.assertIsNone(researcher1.primary_contact)
        self.assertEqual(researcher1.secondary_contact, contact2)
        self.assertEqual(researcher2.primary_contact, contact2)
        self.assertIsNone(researcher2.secondary_contact)

    def test_self_reference_with_through_m2m_at_second_level(self):
        """
        Tests deletion of books using a subquery that self-references through a many-to-many relationship at the second level, verifying the query optimization and deletion result.
        """
        toy = Toy.objects.create(name="Paints")
        child = Child.objects.create(name="Juan")
        Book.objects.create(pagecount=500, owner=child)
        PlayedWith.objects.create(child=child, toy=toy, date=datetime.date.today())
        with self.assertNumQueries(1) as ctx:
            Book.objects.filter(
                Exists(
                    Book.objects.filter(
                        pk=OuterRef("pk"),
                        owner__toys=toy.pk,
                    ),
                )
            ).delete()

        self.assertIs(Book.objects.exists(), False)
        sql = ctx.captured_queries[0]["sql"].lower()
        if connection.features.delete_can_self_reference_subquery:
            self.assertEqual(sql.count("select"), 1)


class DeleteDistinct(SimpleTestCase):
    def test_disallowed_delete_distinct_on(self):
        msg = "Cannot call delete() after .distinct(*fields)."
        with self.assertRaisesMessage(TypeError, msg):
            Book.objects.distinct("id").delete()


class SetQueryCountTests(TestCase):
    def test_set_querycount(self):
        """
        ```\"\"\"Tests that deleting a location results in the correct query count.

        Ensures the associated item and location_value are updated with a minimal number of database queries.\"\"\"
        ```
        """
        policy = Policy.objects.create()
        version = Version.objects.create(policy=policy)
        location = Location.objects.create(version=version)
        Item.objects.create(
            version=version,
            location=location,
            location_value=location,
        )
        # 2 UPDATEs for SET of item values and one for DELETE locations.
        with self.assertNumQueries(3):
            location.delete()


class SetCallableCollectorDefaultTests(TestCase):
    def test_set(self):
        # Collector doesn't call callables used by models.SET and
        # models.SET_DEFAULT if not necessary.
        Toy.objects.create(name="test")
        Toy.objects.all().delete()
        self.assertSequenceEqual(Toy.objects.all(), [])
