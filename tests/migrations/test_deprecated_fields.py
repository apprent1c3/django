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
        Tests the migration process for the IPAddressField model, verifying that the corresponding database table is created and deleted as expected during migration and rollback operations. 

         This test case consists of four main steps: 
         1. Verifying that the 'migrations_ipaddressfield' table does not initially exist.
         2. Running a migration command to create the table.
         3. Confirming that the table now exists after migration.
         4. Reverting the migration and checking that the table is removed as a result. 

         Overall, this test ensures that the migration process correctly handles the creation and deletion of the IPAddressField table.
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
