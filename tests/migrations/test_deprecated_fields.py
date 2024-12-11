from django.core.management import call_command
from django.test import override_settings

from .test_base import MigrationTestBase


class Tests(MigrationTestBase):
    """
    Deprecated model fields should still be usable in historic migrations.
    """

    @override_settings(
        MIGRATION_MODULES={"migrations": "migrations.deprecated_field_migrations"}
    )
    def test_migrate(self):
        # Make sure no tables are created
        """
        Tests migration of the IPAddressField model.

        This test case checks the migration process of the IPAddressField model by asserting its presence or absence in the database.
        It first verifies that the table does not exist before migration, then runs the migration command to create the table.
        After confirming the table's existence, it runs the migration command with the 'zero' option to delete the table and finally checks that the table is removed.
        The test ensures that the migration process correctly creates and deletes the IPAddressField model's table in the database.

        """
        self.assertTableNotExists("migrations_ipaddressfield")
        # Run migration
        call_command("migrate", verbosity=0)
        # Make sure the right tables exist
        self.assertTableExists("migrations_ipaddressfield")
        # Unmigrate everything
        call_command("migrate", "migrations", "zero", verbosity=0)
        # Make sure it's all gone
        self.assertTableNotExists("migrations_ipaddressfield")
