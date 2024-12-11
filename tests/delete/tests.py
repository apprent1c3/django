from math import ceil

from django.db import connection, models
from django.db.models import ProtectedError, Q, RestrictedError
from django.db.models.deletion import Collector
from django.db.models.sql.constants import GET_ITERATOR_CHUNK_SIZE
from django.test import TestCase, skipIfDBFeature, skipUnlessDBFeature

from .models import (
    B1,
    B2,
    B3,
    MR,
    A,
    Avatar,
    B,
    Base,
    Child,
    DeleteBottom,
    DeleteTop,
    GenericB1,
    GenericB2,
    GenericDeleteBottom,
    HiddenUser,
    HiddenUserProfile,
    M,
    M2MFrom,
    M2MTo,
    MRNull,
    Origin,
    P,
    Parent,
    R,
    RChild,
    RChildChild,
    Referrer,
    S,
    T,
    User,
    create_a,
    get_default_r,
)


class OnDeleteTests(TestCase):
    def setUp(self):
        self.DEFAULT = get_default_r()

    def test_auto(self):
        """

        Tests the auto-deletion of an object.

        This test case verifies that an object created with the name 'auto' is successfully deleted,
        resulting in its absence from the database. The existence of the object is checked before and
        after deletion to ensure the operation was successful.

        """
        a = create_a("auto")
        a.auto.delete()
        self.assertFalse(A.objects.filter(name="auto").exists())

    def test_non_callable(self):
        msg = "on_delete must be callable."
        with self.assertRaisesMessage(TypeError, msg):
            models.ForeignKey("self", on_delete=None)
        with self.assertRaisesMessage(TypeError, msg):
            models.OneToOneField("self", on_delete=None)

    def test_auto_nullable(self):
        a = create_a("auto_nullable")
        a.auto_nullable.delete()
        self.assertFalse(A.objects.filter(name="auto_nullable").exists())

    def test_setvalue(self):
        a = create_a("setvalue")
        a.setvalue.delete()
        a = A.objects.get(pk=a.pk)
        self.assertEqual(self.DEFAULT, a.setvalue.pk)

    def test_setnull(self):
        a = create_a("setnull")
        a.setnull.delete()
        a = A.objects.get(pk=a.pk)
        self.assertIsNone(a.setnull)

    def test_setdefault(self):
        """
        Tests that the setdefault attribute is properly restored to its default value after deletion.

        The test case verifies that when the setdefault attribute is deleted, it is automatically reset to its default value when the object is re-retrieved from the database. This ensures data consistency and integrity in scenarios where the setdefault attribute is expected to have a default value.

        :raises AssertionError: If the setdefault attribute is not restored to its default value after deletion
        """
        a = create_a("setdefault")
        a.setdefault.delete()
        a = A.objects.get(pk=a.pk)
        self.assertEqual(self.DEFAULT, a.setdefault.pk)

    def test_setdefault_none(self):
        """

        Tests that the setdefault_none attribute is correctly set to None after deletion.

        This test case verifies that when the setdefault_none attribute is deleted, 
        subsequent database requests return the attribute as None, ensuring data consistency.

        """
        a = create_a("setdefault_none")
        a.setdefault_none.delete()
        a = A.objects.get(pk=a.pk)
        self.assertIsNone(a.setdefault_none)

    def test_cascade(self):
        """

        Tests the cascade deletion behavior.

        This function verifies that when a parent object is deleted, its associated child objects
        are also deleted due to the cascade effect. It creates an instance of 'A' with the name 'cascade',
        deletes the associated cascade object, and then checks that the instance of 'A' with the name 'cascade'
        no longer exists in the database.

        """
        a = create_a("cascade")
        a.cascade.delete()
        self.assertFalse(A.objects.filter(name="cascade").exists())

    def test_cascade_nullable(self):
        """
        Tests the cascade nullable behavior when deleting an object.

        Verifies that when an object with a cascade nullable relationship is deleted, 
        the related object is also removed from the database. In this case, 
        it checks that the object 'cascade_nullable' is successfully deleted and 
        no longer exists in the database after deletion of its related object.
        """
        a = create_a("cascade_nullable")
        a.cascade_nullable.delete()
        self.assertFalse(A.objects.filter(name="cascade_nullable").exists())

    def test_protect(self):
        """
        Tests the protection of a model instance from deletion when referenced by a protected foreign key.

        Verifies that attempting to delete an instance that is protected due to a foreign key relationship raises a ProtectedError with the expected message and identifies the protected object.

        This test ensures the functionality of the protection mechanism in preventing unintended deletion of related instances.
        """
        a = create_a("protect")
        msg = (
            "Cannot delete some instances of model 'R' because they are "
            "referenced through protected foreign keys: 'A.protect'."
        )
        with self.assertRaisesMessage(ProtectedError, msg) as cm:
            a.protect.delete()
        self.assertEqual(cm.exception.protected_objects, {a})

    def test_protect_multiple(self):
        """

        Tests that deleting an instance with multiple protected foreign keys raises a ProtectedError.

        This test verifies that attempting to delete an object that has foreign keys
        protecting it from deletion in multiple related models will correctly raise an
        exception. The exception message will include information about the models and
        fields that are preventing the deletion.

        The test checks both that the correct exception is raised, and that the
        exception includes the correct set of protected objects.

        """
        a = create_a("protect")
        b = B.objects.create(protect=a.protect)
        msg = (
            "Cannot delete some instances of model 'R' because they are "
            "referenced through protected foreign keys: 'A.protect', "
            "'B.protect'."
        )
        with self.assertRaisesMessage(ProtectedError, msg) as cm:
            a.protect.delete()
        self.assertEqual(cm.exception.protected_objects, {a, b})

    def test_protect_path(self):
        """

        Tests the protection of a path from deletion due to a foreign key reference.

        Verifies that an instance of model 'P' cannot be deleted if it is referenced
        by another instance through a protected foreign key. This ensures data integrity
        by preventing the deletion of objects that are still being referenced by other parts
        of the system.

        Raises a ProtectedError with a descriptive message if the deletion is attempted,
        and checks that the exception contains the correct set of protected objects.

        """
        a = create_a("protect")
        a.protect.p = P.objects.create()
        a.protect.save()
        msg = (
            "Cannot delete some instances of model 'P' because they are "
            "referenced through protected foreign keys: 'R.p'."
        )
        with self.assertRaisesMessage(ProtectedError, msg) as cm:
            a.protect.p.delete()
        self.assertEqual(cm.exception.protected_objects, {a})

    def test_do_nothing(self):
        # Testing DO_NOTHING is a bit harder: It would raise IntegrityError for
        # a normal model, so we connect to pre_delete and set the fk to a known
        # value.
        """

        Tests that the 'do nothing' functionality triggers correctly when an object is deleted.

        This function checks if replacing an object with a new one before deleting it works as expected.
        It verifies that after deletion, the replacement object is correctly assigned to the related field.

        The test case involves creating a replacement object, setting up a signal handler to replace the object,
        deleting the original object, and then asserting that the replacement object is correctly assigned.

        """
        replacement_r = R.objects.create()

        def check_do_nothing(sender, **kwargs):
            obj = kwargs["instance"]
            obj.donothing_set.update(donothing=replacement_r)

        models.signals.pre_delete.connect(check_do_nothing)
        a = create_a("do_nothing")
        a.donothing.delete()
        a = A.objects.get(pk=a.pk)
        self.assertEqual(replacement_r, a.donothing)
        models.signals.pre_delete.disconnect(check_do_nothing)

    def test_do_nothing_qscount(self):
        """
        A models.DO_NOTHING relation doesn't trigger a query.
        """
        b = Base.objects.create()
        with self.assertNumQueries(1):
            # RelToBase should not be queried.
            b.delete()
        self.assertEqual(Base.objects.count(), 0)

    def test_inheritance_cascade_up(self):
        child = RChild.objects.create()
        child.delete()
        self.assertFalse(R.objects.filter(pk=child.pk).exists())

    def test_inheritance_cascade_down(self):
        child = RChild.objects.create()
        parent = child.r_ptr
        parent.delete()
        self.assertFalse(RChild.objects.filter(pk=child.pk).exists())

    def test_cascade_from_child(self):
        a = create_a("child")
        a.child.delete()
        self.assertFalse(A.objects.filter(name="child").exists())
        self.assertFalse(R.objects.filter(pk=a.child_id).exists())

    def test_cascade_from_parent(self):
        a = create_a("child")
        R.objects.get(pk=a.child_id).delete()
        self.assertFalse(A.objects.filter(name="child").exists())
        self.assertFalse(RChild.objects.filter(pk=a.child_id).exists())

    def test_setnull_from_child(self):
        """
        Tests the removal of a related object by deleting the child object and verifies that the parent object's reference to it is set to null.

        This test case ensures that when a child object is deleted, the parent object's foreign key reference to it is correctly updated to null, maintaining data consistency and preventing stale references.

        The test verifies this behavior by:

        * Creating a parent object with a child object
        * Deleting the child object
        * Checking that the child object is no longer present in the database
        * Retrieving the parent object and verifying that its reference to the child object is set to null
        """
        a = create_a("child_setnull")
        a.child_setnull.delete()
        self.assertFalse(R.objects.filter(pk=a.child_setnull_id).exists())

        a = A.objects.get(pk=a.pk)
        self.assertIsNone(a.child_setnull)

    def test_setnull_from_parent(self):
        """

        Tests that setting a parent object to null via deletion correctly updates the related child object's foreign key reference.

        Checks that after deleting a parent object, the corresponding child object's foreign key is set to null, ensuring data integrity and consistency.

        """
        a = create_a("child_setnull")
        R.objects.get(pk=a.child_setnull_id).delete()
        self.assertFalse(RChild.objects.filter(pk=a.child_setnull_id).exists())

        a = A.objects.get(pk=a.pk)
        self.assertIsNone(a.child_setnull)

    def test_o2o_setnull(self):
        """

        Tests the behavior of a one-to-one relationship when the related object is set to null.

        Verifies that after deleting the object at the other end of a one-to-one relationship,
        the relationship on the original object is updated to reflect the change, specifically
        by being set to None. 

        This test ensures data consistency and proper handling of one-to-one relationships
        in the case of related object deletion.

        """
        a = create_a("o2o_setnull")
        a.o2o_setnull.delete()
        a = A.objects.get(pk=a.pk)
        self.assertIsNone(a.o2o_setnull)

    def test_restrict(self):
        """

        Tests whether deletion of an instance is properly restricted when referenced through a restricted foreign key.

        This test case verifies that attempting to delete an instance of model 'A' raises a :class:`RestrictedError` when the instance is 
        referenced by another model through a restricted foreign key. The error is expected to contain a message explaining the reason 
        for the restriction and to identify the object that cannot be deleted due to the restriction.

        """
        a = create_a("restrict")
        msg = (
            "Cannot delete some instances of model 'R' because they are "
            "referenced through restricted foreign keys: 'A.restrict'."
        )
        with self.assertRaisesMessage(RestrictedError, msg) as cm:
            a.restrict.delete()
        self.assertEqual(cm.exception.restricted_objects, {a})

    def test_restrict_multiple(self):
        """

        Tests the restriction of deleting instances of a model when they are referenced 
        through restricted foreign keys by multiple other models.

        Verifies that a RestrictedError is raised with a correct error message when 
        attempting to delete such an instance and checks that the exception contains 
        the set of objects that prevent the deletion due to the restrictions.

        """
        a = create_a("restrict")
        b3 = B3.objects.create(restrict=a.restrict)
        msg = (
            "Cannot delete some instances of model 'R' because they are "
            "referenced through restricted foreign keys: 'A.restrict', "
            "'B3.restrict'."
        )
        with self.assertRaisesMessage(RestrictedError, msg) as cm:
            a.restrict.delete()
        self.assertEqual(cm.exception.restricted_objects, {a, b3})

    def test_restrict_path_cascade_indirect(self):
        """

        Tests the behavior of restricted foreign keys when a cascading delete is involved.

        This test verifies that:

        * A RestrictError is raised when attempting to delete an instance that is referenced through a restricted foreign key.
        * When an instance is deleted, all instances that reference it through a restricted foreign key are also deleted due to the cascade.

        The test covers indirect restriction through a foreign key relationship to ensure that the system behaves as expected when dealing with complex object relationships.

        """
        a = create_a("restrict")
        a.restrict.p = P.objects.create()
        a.restrict.save()
        msg = (
            "Cannot delete some instances of model 'P' because they are "
            "referenced through restricted foreign keys: 'A.restrict'."
        )
        with self.assertRaisesMessage(RestrictedError, msg) as cm:
            a.restrict.p.delete()
        self.assertEqual(cm.exception.restricted_objects, {a})
        # Object referenced also with CASCADE relationship can be deleted.
        a.cascade.p = a.restrict.p
        a.cascade.save()
        a.restrict.p.delete()
        self.assertFalse(A.objects.filter(name="restrict").exists())
        self.assertFalse(R.objects.filter(pk=a.restrict_id).exists())

    def test_restrict_path_cascade_direct(self):
        """

        Tests the cascade deletion functionality when restricting a path.

        Verifies that when an object is restricted and then deleted, the objects 
        that have a cascading relationship with it are also deleted. In this case, 
        when a 'p' object is deleted, its corresponding 'a' object with a 
        'restrict' relationship and the 'restrict' object itself should also be 
        deleted. The test confirms that both the 'a' and 'restrict' objects are 
        properly removed from the database after the 'p' object is deleted.

        """
        a = create_a("restrict")
        a.restrict.p = P.objects.create()
        a.restrict.save()
        a.cascade_p = a.restrict.p
        a.save()
        a.restrict.p.delete()
        self.assertFalse(A.objects.filter(name="restrict").exists())
        self.assertFalse(R.objects.filter(pk=a.restrict_id).exists())

    def test_restrict_path_cascade_indirect_diamond(self):
        """

        Tests that restricting the deletion of a model through a cascading indirect diamond foreign key structure correctly prevents the deletion of the model instance.

        The test case checks for the following conditions:
        - Deletion of an instance of the model 'B1' fails with a RestrictedError
        - The error message includes the correct restricted model 'DeleteBottom'
        - The delete cascade works correctly when the top-level instance 'DeleteTop' is deleted
        - The deletion of 'DeleteTop' results in the removal of all related instances

        """
        delete_top = DeleteTop.objects.create()
        b1 = B1.objects.create(delete_top=delete_top)
        b2 = B2.objects.create(delete_top=delete_top)
        delete_bottom = DeleteBottom.objects.create(b1=b1, b2=b2)
        msg = (
            "Cannot delete some instances of model 'B1' because they are "
            "referenced through restricted foreign keys: 'DeleteBottom.b1'."
        )
        with self.assertRaisesMessage(RestrictedError, msg) as cm:
            b1.delete()
        self.assertEqual(cm.exception.restricted_objects, {delete_bottom})
        self.assertTrue(DeleteTop.objects.exists())
        self.assertTrue(B1.objects.exists())
        self.assertTrue(B2.objects.exists())
        self.assertTrue(DeleteBottom.objects.exists())
        # Object referenced also with CASCADE relationship can be deleted.
        delete_top.delete()
        self.assertFalse(DeleteTop.objects.exists())
        self.assertFalse(B1.objects.exists())
        self.assertFalse(B2.objects.exists())
        self.assertFalse(DeleteBottom.objects.exists())

    def test_restrict_gfk_no_fast_delete(self):
        """

        Tests the restriction on deleting an instance of GenericB1 when it is referenced through a restricted foreign key.

        This test verifies that attempting to delete an instance of GenericB1 raises a RestrictedError, and that the error is propagated correctly. It also checks that the related instances of GenericDeleteBottom are properly restricted from being deleted, and that all related instances are ultimately deleted when the top-level instance (GenericDeleteTop) is deleted.

        The test covers the following scenarios:

        * Attempting to delete an instance of GenericB1 that is referenced through a restricted foreign key raises a RestrictedError.
        * The RestrictedError includes information about the restricted objects.
        * Deleting the top-level instance (GenericDeleteTop) cascades the deletion to all related instances.

        """
        delete_top = DeleteTop.objects.create()
        generic_b1 = GenericB1.objects.create(generic_delete_top=delete_top)
        generic_b2 = GenericB2.objects.create(generic_delete_top=delete_top)
        generic_delete_bottom = GenericDeleteBottom.objects.create(
            generic_b1=generic_b1,
            generic_b2=generic_b2,
        )
        msg = (
            "Cannot delete some instances of model 'GenericB1' because they "
            "are referenced through restricted foreign keys: "
            "'GenericDeleteBottom.generic_b1'."
        )
        with self.assertRaisesMessage(RestrictedError, msg) as cm:
            generic_b1.delete()
        self.assertEqual(cm.exception.restricted_objects, {generic_delete_bottom})
        self.assertTrue(DeleteTop.objects.exists())
        self.assertTrue(GenericB1.objects.exists())
        self.assertTrue(GenericB2.objects.exists())
        self.assertTrue(GenericDeleteBottom.objects.exists())
        # Object referenced also with CASCADE relationship can be deleted.
        delete_top.delete()
        self.assertFalse(DeleteTop.objects.exists())
        self.assertFalse(GenericB1.objects.exists())
        self.assertFalse(GenericB2.objects.exists())
        self.assertFalse(GenericDeleteBottom.objects.exists())


class DeletionTests(TestCase):
    def test_sliced_queryset(self):
        """

        Tests that attempting to delete a sliced queryset raises a TypeError.

        The test case verifies that using 'delete()' on a sliced queryset, which is created by using list slicing on a queryset (e.g., `M.objects.all()[0:5]`), results in a TypeError. This is because slicing a queryset before deletion can lead to unpredictable behavior, as the database may not support deletion with offset and limit. The expected error message is \"Cannot use 'limit' or 'offset' with delete().\".

        This test ensures that the ORM correctly handles and prevents such operations, providing a clear and informative error message instead of proceeding with a potentially harmful action.

        """
        msg = "Cannot use 'limit' or 'offset' with delete()."
        with self.assertRaisesMessage(TypeError, msg):
            M.objects.all()[0:5].delete()

    def test_pk_none(self):
        m = M()
        msg = "M object can't be deleted because its id attribute is set to None."
        with self.assertRaisesMessage(ValueError, msg):
            m.delete()

    def test_m2m(self):
        """
        .. method:: test_m2m

            Tests the behavior of many-to-many fields when instances are created, deleted, and associated through the relationship.

            Verifies that when an instance is deleted from either side of the many-to-many relationship, the intermediate relationship instance is also deleted, thus maintaining data consistency.

            Additionally, the test covers scenarios where null values are allowed in the relationship table, ensuring that expected behavior is followed in such cases. The overall goal of this test is to guarantee that many-to-many relationships are correctly established and removed in the database, providing a robust foundation for applications relying on these relationships.
        """
        m = M.objects.create()
        r = R.objects.create()
        MR.objects.create(m=m, r=r)
        r.delete()
        self.assertFalse(MR.objects.exists())

        r = R.objects.create()
        MR.objects.create(m=m, r=r)
        m.delete()
        self.assertFalse(MR.objects.exists())

        m = M.objects.create()
        r = R.objects.create()
        m.m2m.add(r)
        r.delete()
        through = M._meta.get_field("m2m").remote_field.through
        self.assertFalse(through.objects.exists())

        r = R.objects.create()
        m.m2m.add(r)
        m.delete()
        self.assertFalse(through.objects.exists())

        m = M.objects.create()
        r = R.objects.create()
        MRNull.objects.create(m=m, r=r)
        r.delete()
        self.assertFalse(not MRNull.objects.exists())
        self.assertFalse(m.m2m_through_null.exists())

    def test_bulk(self):
        s = S.objects.create(r=R.objects.create())
        for i in range(2 * GET_ITERATOR_CHUNK_SIZE):
            T.objects.create(s=s)
        #   1 (select related `T` instances)
        # + 1 (select related `U` instances)
        # + 2 (delete `T` instances in batches)
        # + 1 (delete `s`)
        self.assertNumQueries(5, s.delete)
        self.assertFalse(S.objects.exists())

    def test_instance_update(self):
        """
        Tests the instance update behavior when associated objects are deleted.

        This function verifies that the primary key of deleted objects is set to None
        and that the related objects have their foreign keys set to None when the
        'delete' action is 'SET_NULL'. The test covers both 'SET_NULL' and 'CASCADE'
        delete actions to ensure the instance update behavior is correct in both cases.

        The function creates test objects, deletes them, and then checks the state of
        the deleted objects and their associated objects to ensure they have been
        updated correctly. The test uses Django's pre-delete signal to track the
        deleted objects and their associated objects, allowing for a detailed
        verification of the instance update behavior.

        The function validates the following:
        - The primary key of deleted objects is set to None.
        - The foreign key of related objects is set to None when the 'delete' action
          is 'SET_NULL'.

        """
        deleted = []
        related_setnull_sets = []

        def pre_delete(sender, **kwargs):
            """

            Pre-deletion signal handler.

            Called before an object is deleted, this function captures the object being deleted
            and tracks its related objects that will have their foreign keys set to null.
            The object is added to a list of deleted objects, and if it is of type R, its related
            objects that will have their foreign keys set to null are also tracked for later reference.

            Args:
                sender: The model class that sent the signal.
                **kwargs: Additional keyword arguments, including 'instance' which is the object being deleted.

            Note:
                This function modifies external lists 'deleted' and 'related_setnull_sets' to track deleted objects and their effects.

            """
            obj = kwargs["instance"]
            deleted.append(obj)
            if isinstance(obj, R):
                related_setnull_sets.append([a.pk for a in obj.setnull_set.all()])

        models.signals.pre_delete.connect(pre_delete)
        a = create_a("update_setnull")
        a.setnull.delete()

        a = create_a("update_cascade")
        a.cascade.delete()

        for obj in deleted:
            self.assertIsNone(obj.pk)

        for pk_list in related_setnull_sets:
            for a in A.objects.filter(id__in=pk_list):
                self.assertIsNone(a.setnull)

        models.signals.pre_delete.disconnect(pre_delete)

    def test_deletion_order(self):
        pre_delete_order = []
        post_delete_order = []

        def log_post_delete(sender, **kwargs):
            pre_delete_order.append((sender, kwargs["instance"].pk))

        def log_pre_delete(sender, **kwargs):
            post_delete_order.append((sender, kwargs["instance"].pk))

        models.signals.post_delete.connect(log_post_delete)
        models.signals.pre_delete.connect(log_pre_delete)

        r = R.objects.create()
        s1 = S.objects.create(r=r)
        s2 = S.objects.create(r=r)
        t1 = T.objects.create(s=s1)
        t2 = T.objects.create(s=s2)
        rchild = RChild.objects.create(r_ptr=r)
        r_pk = r.pk
        r.delete()
        self.assertEqual(
            pre_delete_order,
            [
                (T, t2.pk),
                (T, t1.pk),
                (RChild, rchild.pk),
                (S, s2.pk),
                (S, s1.pk),
                (R, r_pk),
            ],
        )
        self.assertEqual(
            post_delete_order,
            [
                (T, t1.pk),
                (T, t2.pk),
                (RChild, rchild.pk),
                (S, s1.pk),
                (S, s2.pk),
                (R, r_pk),
            ],
        )

        models.signals.post_delete.disconnect(log_post_delete)
        models.signals.pre_delete.disconnect(log_pre_delete)

    def test_relational_post_delete_signals_happen_before_parent_object(self):
        """
        Tests that post_delete signals are sent to child objects before the parent object is deleted.

        This test case verifies the order of operations during a cascading deletion, 
        ensuring that the post_delete signal is sent to the child object after it has been 
        deleted but before the parent object is deleted. The test also checks that the 
        signal is sent only once for the child object and that the instance being 
        deleted is of the correct type.

        The test creates a parent and child object, connects a signal handler to the 
        post_delete signal of the child model, deletes the parent object, and then checks 
        that the signal handler was called as expected. The signal handler is 
        disconnected after the deletion to prevent interference with other tests. 

        The expected behavior is that the post_delete signal is sent to the child object 
        before the parent object is deleted, and that the signal is sent only once for 
        the child object. 

        :raises AssertionError: if the test fails, indicating that the post_delete 
        signal was not sent as expected
        """
        deletions = []

        def log_post_delete(instance, **kwargs):
            self.assertTrue(R.objects.filter(pk=instance.r_id))
            self.assertIs(type(instance), S)
            deletions.append(instance.id)

        r = R.objects.create()
        s = S.objects.create(r=r)
        s_id = s.pk
        models.signals.post_delete.connect(log_post_delete, sender=S)

        try:
            r.delete()
        finally:
            models.signals.post_delete.disconnect(log_post_delete)

        self.assertEqual(len(deletions), 1)
        self.assertEqual(deletions[0], s_id)

    @skipUnlessDBFeature("can_defer_constraint_checks")
    def test_can_defer_constraint_checks(self):
        """

        Tests the database's ability to defer constraint checks.

        This test case creates a User instance with an associated Avatar, then deletes the Avatar,
        verifying that both the User and Avatar are successfully deleted from the database.
        It also checks that the necessary database queries are executed and that post-delete signals are sent as expected.

        """
        u = User.objects.create(avatar=Avatar.objects.create())
        a = Avatar.objects.get(pk=u.avatar_id)
        # 1 query to find the users for the avatar.
        # 1 query to delete the user
        # 1 query to delete the avatar
        # The important thing is that when we can defer constraint checks there
        # is no need to do an UPDATE on User.avatar to null it out.

        # Attach a signal to make sure we will not do fast_deletes.
        calls = []

        def noop(*args, **kwargs):
            calls.append("")

        models.signals.post_delete.connect(noop, sender=User)

        self.assertNumQueries(3, a.delete)
        self.assertFalse(User.objects.exists())
        self.assertFalse(Avatar.objects.exists())
        self.assertEqual(len(calls), 1)
        models.signals.post_delete.disconnect(noop, sender=User)

    @skipIfDBFeature("can_defer_constraint_checks")
    def test_cannot_defer_constraint_checks(self):
        """
        Tests that constraint checks cannot be deferred when deleting objects.

        This test creates a user object with an associated avatar, then deletes the avatar and checks that the user object is also deleted.
        It verifies that the post_delete signal is called once and that both User and Avatar objects are removed from the database.

        The test is skipped if the database backend supports deferring constraint checks, as this functionality is not relevant in such cases.
        """
        u = User.objects.create(avatar=Avatar.objects.create())
        # Attach a signal to make sure we will not do fast_deletes.
        calls = []

        def noop(*args, **kwargs):
            calls.append("")

        models.signals.post_delete.connect(noop, sender=User)

        a = Avatar.objects.get(pk=u.avatar_id)
        # The below doesn't make sense... Why do we need to null out
        # user.avatar if we are going to delete the user immediately after it,
        # and there are no more cascades.
        # 1 query to find the users for the avatar.
        # 1 query to delete the user
        # 1 query to null out user.avatar, because we can't defer the constraint
        # 1 query to delete the avatar
        self.assertNumQueries(4, a.delete)
        self.assertFalse(User.objects.exists())
        self.assertFalse(Avatar.objects.exists())
        self.assertEqual(len(calls), 1)
        models.signals.post_delete.disconnect(noop, sender=User)

    def test_hidden_related(self):
        """

        Tests the deletion behavior of HiddenUserProfile instances related to a deleted R object.
        Verifies that when an R object is deleted, its associated HiddenUserProfile is also removed,
        ensuring that there are no orphaned HiddenUserProfile records in the database.

        """
        r = R.objects.create()
        h = HiddenUser.objects.create(r=r)
        HiddenUserProfile.objects.create(user=h)

        r.delete()
        self.assertEqual(HiddenUserProfile.objects.count(), 0)

    def test_large_delete(self):
        """

        Tests the deletion of a large number of objects in the database.

        This test creates a large number of Avatar objects, adds them to the database in batches,
        and then deletes all of them. It verifies that the deletion operation is executed within
        the expected number of database queries, ensuring efficient bulk deletion.

        The test covers scenarios where the number of objects exceeds the bulk batch size,
        requiring multiple batches to be processed. It also takes into account the chunk size
        used by the database iterator, which affects the number of queries issued during the deletion process.

        """
        TEST_SIZE = 2000
        objs = [Avatar() for i in range(0, TEST_SIZE)]
        Avatar.objects.bulk_create(objs)
        # Calculate the number of queries needed.
        batch_size = connection.ops.bulk_batch_size(["pk"], objs)
        # The related fetches are done in batches.
        batches = ceil(len(objs) / batch_size)
        # One query for Avatar.objects.all() and then one related fast delete for
        # each batch.
        fetches_to_mem = 1 + batches
        # The Avatar objects are going to be deleted in batches of
        # GET_ITERATOR_CHUNK_SIZE.
        queries = fetches_to_mem + TEST_SIZE // GET_ITERATOR_CHUNK_SIZE
        self.assertNumQueries(queries, Avatar.objects.all().delete)
        self.assertFalse(Avatar.objects.exists())

    def test_large_delete_related(self):
        TEST_SIZE = 2000
        s = S.objects.create(r=R.objects.create())
        for i in range(TEST_SIZE):
            T.objects.create(s=s)

        batch_size = max(connection.ops.bulk_batch_size(["pk"], range(TEST_SIZE)), 1)

        # TEST_SIZE / batch_size (select related `T` instances)
        # + 1 (select related `U` instances)
        # + TEST_SIZE / GET_ITERATOR_CHUNK_SIZE (delete `T` instances in batches)
        # + 1 (delete `s`)
        expected_num_queries = ceil(TEST_SIZE / batch_size)
        expected_num_queries += ceil(TEST_SIZE / GET_ITERATOR_CHUNK_SIZE) + 2

        self.assertNumQueries(expected_num_queries, s.delete)
        self.assertFalse(S.objects.exists())
        self.assertFalse(T.objects.exists())

    def test_delete_with_keeping_parents(self):
        child = RChild.objects.create()
        parent_id = child.r_ptr_id
        child.delete(keep_parents=True)
        self.assertFalse(RChild.objects.filter(id=child.id).exists())
        self.assertTrue(R.objects.filter(id=parent_id).exists())

    def test_delete_with_keeping_parents_relationships(self):
        child = RChild.objects.create()
        parent_id = child.r_ptr_id
        parent_referent_id = S.objects.create(r=child.r_ptr).pk
        child.delete(keep_parents=True)
        self.assertFalse(RChild.objects.filter(id=child.id).exists())
        self.assertTrue(R.objects.filter(id=parent_id).exists())
        self.assertTrue(S.objects.filter(pk=parent_referent_id).exists())

        childchild = RChildChild.objects.create()
        parent_id = childchild.rchild_ptr.r_ptr_id
        child_id = childchild.rchild_ptr_id
        parent_referent_id = S.objects.create(r=childchild.rchild_ptr.r_ptr).pk
        childchild.delete(keep_parents=True)
        self.assertFalse(RChildChild.objects.filter(id=childchild.id).exists())
        self.assertTrue(RChild.objects.filter(id=child_id).exists())
        self.assertTrue(R.objects.filter(id=parent_id).exists())
        self.assertTrue(S.objects.filter(pk=parent_referent_id).exists())

    def test_queryset_delete_returns_num_rows(self):
        """
        QuerySet.delete() should return the number of deleted rows and a
        dictionary with the number of deletions for each object type.
        """
        Avatar.objects.bulk_create(
            [Avatar(desc="a"), Avatar(desc="b"), Avatar(desc="c")]
        )
        avatars_count = Avatar.objects.count()
        deleted, rows_count = Avatar.objects.all().delete()
        self.assertEqual(deleted, avatars_count)

        # more complex example with multiple object types
        r = R.objects.create()
        h1 = HiddenUser.objects.create(r=r)
        HiddenUser.objects.create(r=r)
        HiddenUserProfile.objects.create(user=h1)
        existed_objs = {
            R._meta.label: R.objects.count(),
            HiddenUser._meta.label: HiddenUser.objects.count(),
            HiddenUserProfile._meta.label: HiddenUserProfile.objects.count(),
        }
        deleted, deleted_objs = R.objects.all().delete()
        self.assertCountEqual(deleted_objs.keys(), existed_objs.keys())
        for k, v in existed_objs.items():
            self.assertEqual(deleted_objs[k], v)

    def test_model_delete_returns_num_rows(self):
        """
        Model.delete() should return the number of deleted rows and a
        dictionary with the number of deletions for each object type.
        """
        r = R.objects.create()
        h1 = HiddenUser.objects.create(r=r)
        h2 = HiddenUser.objects.create(r=r)
        HiddenUser.objects.create(r=r)
        HiddenUserProfile.objects.create(user=h1)
        HiddenUserProfile.objects.create(user=h2)
        m1 = M.objects.create()
        m2 = M.objects.create()
        MR.objects.create(r=r, m=m1)
        r.m_set.add(m1)
        r.m_set.add(m2)
        r.save()
        existed_objs = {
            R._meta.label: R.objects.count(),
            HiddenUser._meta.label: HiddenUser.objects.count(),
            MR._meta.label: MR.objects.count(),
            HiddenUserProfile._meta.label: HiddenUserProfile.objects.count(),
            M.m2m.through._meta.label: M.m2m.through.objects.count(),
        }
        deleted, deleted_objs = r.delete()
        self.assertEqual(deleted, sum(existed_objs.values()))
        self.assertCountEqual(deleted_objs.keys(), existed_objs.keys())
        for k, v in existed_objs.items():
            self.assertEqual(deleted_objs[k], v)

    def test_proxied_model_duplicate_queries(self):
        """
        #25685 - Deleting instances of a model with existing proxy
        classes should not issue multiple queries during cascade
        deletion of referring models.
        """
        avatar = Avatar.objects.create()
        # One query for the Avatar table and a second for the User one.
        with self.assertNumQueries(2):
            avatar.delete()

    def test_only_referenced_fields_selected(self):
        """
        Only referenced fields are selected during cascade deletion SELECT
        unless deletion signals are connected.
        """
        origin = Origin.objects.create()
        expected_sql = str(
            Referrer.objects.only(
                # Both fields are referenced by SecondReferrer.
                "id",
                "unique_field",
            )
            .filter(origin__in=[origin])
            .query
        )
        with self.assertNumQueries(2) as ctx:
            origin.delete()
        self.assertEqual(ctx.captured_queries[0]["sql"], expected_sql)

        def receiver(instance, **kwargs):
            pass

        # All fields are selected if deletion signals are connected.
        for signal_name in ("pre_delete", "post_delete"):
            with self.subTest(signal=signal_name):
                origin = Origin.objects.create()
                signal = getattr(models.signals, signal_name)
                signal.connect(receiver, sender=Referrer)
                with self.assertNumQueries(2) as ctx:
                    origin.delete()
                self.assertIn(
                    connection.ops.quote_name("large_field"),
                    ctx.captured_queries[0]["sql"],
                )
                signal.disconnect(receiver, sender=Referrer)


class FastDeleteTests(TestCase):
    def test_fast_delete_all(self):
        """
        Tests that deleting all User objects results in a single database query.

        This test case verifies that the deletion operation is performed efficiently, without 
        retrieving the objects to be deleted. It checks the generated SQL query to ensure it does 
        not include a SELECT statement, thus confirming a fast deletion process.

        """
        with self.assertNumQueries(1) as ctx:
            User.objects.all().delete()
        sql = ctx.captured_queries[0]["sql"]
        # No subqueries is used when performing a full delete.
        self.assertNotIn("SELECT", sql)

    def test_fast_delete_fk(self):
        """

        Tests the fast deletion of a foreign key relationship.

        This test case verifies that deleting an Avatar object also deletes the associated User object,
        ensuring that there are no orphaned records. It checks the number of database queries executed
        during the deletion process and confirms that both the User and Avatar tables are left empty
        after the deletion.

        """
        u = User.objects.create(avatar=Avatar.objects.create())
        a = Avatar.objects.get(pk=u.avatar_id)
        # 1 query to fast-delete the user
        # 1 query to delete the avatar
        self.assertNumQueries(2, a.delete)
        self.assertFalse(User.objects.exists())
        self.assertFalse(Avatar.objects.exists())

    def test_fast_delete_m2m(self):
        t = M2MTo.objects.create()
        f = M2MFrom.objects.create()
        f.m2m.add(t)
        # 1 to delete f, 1 to fast-delete m2m for f
        self.assertNumQueries(2, f.delete)

    def test_fast_delete_revm2m(self):
        """

        Tests the efficiency of deleting an instance of M2MFrom with many-to-many relationship.

        Checks if the deletion of the instance triggers the expected number of database queries,
        specifically two queries, when the instance has an existing many-to-many relationship with M2MTo.
        This ensures that the deletion process is optimized and does not result in excessive database queries.

        """
        t = M2MTo.objects.create()
        f = M2MFrom.objects.create()
        f.m2m.add(t)
        # 1 to delete t, 1 to fast-delete t's m_set
        self.assertNumQueries(2, f.delete)

    def test_fast_delete_qs(self):
        """

        Tests the efficiency of deleting a queryset in a single database query.

        This test case verifies that deleting a queryset with a filter condition 
        only generates a single database query. It creates two users, 
        deletes one of them using a queryset, and then checks that 
        the deletion operation was executed efficiently and correctly, 
        leaving the other user intact. 

        """
        u1 = User.objects.create()
        u2 = User.objects.create()
        self.assertNumQueries(1, User.objects.filter(pk=u1.pk).delete)
        self.assertEqual(User.objects.count(), 1)
        self.assertTrue(User.objects.filter(pk=u2.pk).exists())

    def test_fast_delete_instance_set_pk_none(self):
        """

        Tests the fast deletion of a model instance and verifies that its primary key is set to None afterwards.

        This test case checks the Collector's ability to quickly delete an instance and ensures that the instance's primary key is properly updated after deletion.

        """
        u = User.objects.create()
        # User can be fast-deleted.
        collector = Collector(using="default")
        self.assertTrue(collector.can_fast_delete(u))
        u.delete()
        self.assertIsNone(u.pk)

    def test_fast_delete_joined_qs(self):
        a = Avatar.objects.create(desc="a")
        User.objects.create(avatar=a)
        u2 = User.objects.create()
        self.assertNumQueries(1, User.objects.filter(avatar__desc="a").delete)
        self.assertEqual(User.objects.count(), 1)
        self.assertTrue(User.objects.filter(pk=u2.pk).exists())

    def test_fast_delete_inheritance(self):
        """

        Test the efficiency of deleting objects with inheritance.

        This test case verifies that deleting objects in an inherited model hierarchy
        results in the expected number of database queries and that the objects are
        properly removed. It creates objects of the Child and Parent classes, deletes
        them, and checks that the objects no longer exist in the database.

        The test covers both direct deletion of Child and Parent objects, as well as
        deletion of a Parent object through its Child instance (using the parent_ptr
        attribute), ensuring that the deletion process works correctly in all cases.

        The expected outcome is that deleting an object will result in two database
        queries and that both Child and Parent objects are properly removed from the
        database after deletion.

        """
        c = Child.objects.create()
        p = Parent.objects.create()
        # 1 for self, 1 for parent
        self.assertNumQueries(2, c.delete)
        self.assertFalse(Child.objects.exists())
        self.assertEqual(Parent.objects.count(), 1)
        self.assertEqual(Parent.objects.filter(pk=p.pk).count(), 1)
        # 1 for self delete, 1 for fast delete of empty "child" qs.
        self.assertNumQueries(2, p.delete)
        self.assertFalse(Parent.objects.exists())
        # 1 for self delete, 1 for fast delete of empty "child" qs.
        c = Child.objects.create()
        p = c.parent_ptr
        self.assertNumQueries(2, p.delete)
        self.assertFalse(Parent.objects.exists())
        self.assertFalse(Child.objects.exists())

    def test_fast_delete_large_batch(self):
        """

        Tests the performance of deleting large batches of objects in the database.

        This test case evaluates the efficiency of deleting multiple objects at once,
        covering scenarios where objects are deleted with and without associated dependencies.
        It verifies that the deletion process is optimized, minimizing the number of database queries.

        """
        User.objects.bulk_create(User() for i in range(0, 2000))
        # No problems here - we aren't going to cascade, so we will fast
        # delete the objects in a single query.
        self.assertNumQueries(1, User.objects.all().delete)
        a = Avatar.objects.create(desc="a")
        User.objects.bulk_create(User(avatar=a) for i in range(0, 2000))
        # We don't hit parameter amount limits for a, so just one query for
        # that + fast delete of the related objs.
        self.assertNumQueries(2, a.delete)
        self.assertEqual(User.objects.count(), 0)

    def test_fast_delete_empty_no_update_can_self_select(self):
        """
        Fast deleting when DatabaseFeatures.update_can_self_select = False
        works even if the specified filter doesn't match any row (#25932).
        """
        with self.assertNumQueries(1):
            self.assertEqual(
                User.objects.filter(avatar__desc="missing").delete(),
                (0, {}),
            )

    def test_fast_delete_combined_relationships(self):
        # The cascading fast-delete of SecondReferrer should be combined
        # in a single DELETE WHERE referrer_id OR unique_field.
        """
        Tests the fast deletion of combined relationships in a single query.

        Ensures that when a Referrer object is deleted, the related Origin object is 
        also handled efficiently, with minimal database queries. This test case 
        verifies that the deletion process only requires two database queries, 
        indicating a optimized deletion process for the combined relationships.
        """
        origin = Origin.objects.create()
        referer = Referrer.objects.create(origin=origin, unique_field=42)
        with self.assertNumQueries(2):
            referer.delete()

    def test_fast_delete_aggregation(self):
        # Fast-deleting when filtering against an aggregation result in
        # a single query containing a subquery.
        """
        Deletes an object from the database using a fast aggregation method, verifying the deletion process and its side effects.

        This function tests the efficient removal of objects with no related instances, confirming that 
        the database query is executed within the expected number of database operations and 
        successfully removes the specified object, leaving the table empty.
        """
        Base.objects.create()
        with self.assertNumQueries(1):
            self.assertEqual(
                Base.objects.annotate(
                    rels_count=models.Count("rels"),
                )
                .filter(rels_count=0)
                .delete(),
                (1, {"delete.Base": 1}),
            )
        self.assertIs(Base.objects.exists(), False)

    def test_fast_delete_full_match(self):
        """
        Tests the optimization of deleting objects in a single database query.

        This test case verifies that when filtering on a non-existent condition, 
        combined with an existent condition using an 'or' operator, all objects 
        are deleted with a single query. The test ensures that the database query 
        is optimized to delete objects efficiently, without requiring multiple 
        queries.

        The test scenario includes creating an avatar and a user object, then 
        deleting the user object using a query that matches all objects, 
        resulting in a single database query being executed.

        It checks if the deletion is successful by asserting that no user objects 
        exist after the deletion operation.
        """
        avatar = Avatar.objects.create(desc="bar")
        User.objects.create(avatar=avatar)
        with self.assertNumQueries(1):
            User.objects.filter(~Q(pk__in=[]) | Q(avatar__desc="foo")).delete()
        self.assertFalse(User.objects.exists())
