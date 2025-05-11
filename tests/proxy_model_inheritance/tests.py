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
        Tests whether database tables for NiceModel and ProxyModel exist after migration.

        Verifies the correct initialization of the tables by checking the object count
        of both models is zero after running the migration command with the necessary
        apps installed.
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
        Tests whether deleting an instance of a model that proxies a multi-table inherited subclass correctly cascades the deletion down the entire inheritance chain.
        """
        instance = ConcreteModelSubclassProxy.objects.create()
        instance.delete()
        self.assertEqual(0, ConcreteModelSubclassProxy.objects.count())
        self.assertEqual(0, ConcreteModelSubclass.objects.count())
        self.assertEqual(0, ConcreteModel.objects.count())

    def test_deletion_through_intermediate_proxy(self):
        """
        Tests whether deleting an object through an intermediate proxy successfully removes the underlying model instance and its subclass instance from the database.
        """
        child = ConcreteModelSubclass.objects.create()
        proxy = ProxyModel.objects.get(pk=child.pk)
        proxy.delete()
        self.assertFalse(ConcreteModel.objects.exists())
        self.assertFalse(ConcreteModelSubclass.objects.exists())
