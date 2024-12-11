import os

from django.core.management import call_command
from django.test import TestCase, TransactionTestCase
from django.test.utils import extend_sys_path

from .models import (
    ConcreteModel,
    ConcreteModelSubclass,
    ConcreteModelSubclassProxy,
    ProxyModel,
)


class ProxyModelInheritanceTests(TransactionTestCase):
    """
    Proxy model inheritance across apps can result in migrate not creating the table
    for the proxied model (as described in #12286).  This test creates two dummy
    apps and calls migrate, then verifies that the table has been created.
    """

    available_apps = []

    def test_table_exists(self):
        """

        Verify the existence and initial state of database tables for the ProxyModel and NiceModel.

        This test case checks that the tables for ProxyModel and NiceModel are correctly created 
        and contain no initial data after running database migrations.

        :raises AssertionError: If the table existence or initial data count is not as expected.

        """
        with extend_sys_path(os.path.dirname(os.path.abspath(__file__))):
            with self.modify_settings(INSTALLED_APPS={"append": ["app1", "app2"]}):
                call_command("migrate", verbosity=0, run_syncdb=True)
                from app1.models import ProxyModel
                from app2.models import NiceModel

                self.assertEqual(NiceModel.objects.count(), 0)
                self.assertEqual(ProxyModel.objects.count(), 0)


class MultiTableInheritanceProxyTest(TestCase):
    def test_model_subclass_proxy(self):
        """
        Deleting an instance of a model proxying a multi-table inherited
        subclass should cascade delete down the whole inheritance chain (see
        #18083).
        """
        instance = ConcreteModelSubclassProxy.objects.create()
        instance.delete()
        self.assertEqual(0, ConcreteModelSubclassProxy.objects.count())
        self.assertEqual(0, ConcreteModelSubclass.objects.count())
        self.assertEqual(0, ConcreteModel.objects.count())

    def test_deletion_through_intermediate_proxy(self):
        """

        Test that deletion of an object through an intermediate proxy correctly 
        removes the object and all related instances from the database.

        This test case verifies that when an object is deleted via a proxy model, 
        both the object itself and its subclasses are properly removed.

        """
        child = ConcreteModelSubclass.objects.create()
        proxy = ProxyModel.objects.get(pk=child.pk)
        proxy.delete()
        self.assertFalse(ConcreteModel.objects.exists())
        self.assertFalse(ConcreteModelSubclass.objects.exists())
