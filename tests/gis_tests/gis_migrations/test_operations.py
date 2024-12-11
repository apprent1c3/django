from unittest import skipUnless

from django.contrib.gis.db.models import fields
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.exceptions import ImproperlyConfigured
from django.db import connection, migrations, models
from django.db.migrations.migration import Migration
from django.db.migrations.state import ProjectState
from django.test import TransactionTestCase, skipIfDBFeature, skipUnlessDBFeature

try:
    GeometryColumns = connection.ops.geometry_columns()
    HAS_GEOMETRY_COLUMNS = True
except NotImplementedError:
    HAS_GEOMETRY_COLUMNS = False


class OperationTestCase(TransactionTestCase):
    available_apps = ["gis_tests.gis_migrations"]
    get_opclass_query = """
        SELECT opcname, c.relname FROM pg_opclass AS oc
        JOIN pg_index as i on oc.oid = ANY(i.indclass)
        JOIN pg_class as c on c.oid = i.indexrelid
        WHERE c.relname = %s
    """

    def tearDown(self):
        # Delete table after testing
        if hasattr(self, "current_state"):
            self.apply_operations(
                "gis", self.current_state, [migrations.DeleteModel("Neighborhood")]
            )
        super().tearDown()

    @property
    def has_spatial_indexes(self):
        """
        Indicates whether spatial indexes are supported by the database connection.

        Returns True if spatial indexes are available, and False otherwise. The check is
        specifically tailored for MySQL databases, where it verifies support for spatial
        indexes on a table named 'gis_neighborhood'. For non-MySQL databases, spatial
        index support is assumed to be available.

        :rtype: bool
        """
        if connection.ops.mysql:
            with connection.cursor() as cursor:
                return connection.introspection.supports_spatial_index(
                    cursor, "gis_neighborhood"
                )
        return True

    def get_table_description(self, table):
        """

        Retrieves a description of the specified database table.

        This method queries the database to retrieve column information and other metadata about the given table.
        The retrieved table description includes details such as column names, data types, and other relevant properties.
        The returned description can be used for various purposes, including data validation, schema inspection, or generating documentation.

        :param table: The name of the database table to retrieve the description for.
        :return: A description of the specified table, including column metadata.

        """
        with connection.cursor() as cursor:
            return connection.introspection.get_table_description(cursor, table)

    def assertColumnExists(self, table, column):
        self.assertIn(column, [c.name for c in self.get_table_description(table)])

    def assertColumnNotExists(self, table, column):
        self.assertNotIn(column, [c.name for c in self.get_table_description(table)])

    def apply_operations(self, app_label, project_state, operations):
        """

        Applies a series of migration operations to a project's state.

        :param app_label: The label of the application to which the operations belong.
        :param project_state: The current state of the project.
        :param operations: A list of operations to be applied to the project state.
        :return: The result of applying the migration operations.

        This method creates a migration instance with the given application label and operations, 
        and then applies it to the project state using the database schema editor.

        """
        migration = Migration("name", app_label)
        migration.operations = operations
        with connection.schema_editor() as editor:
            return migration.apply(project_state, editor)

    def set_up_test_model(self, force_raster_creation=False):
        """

        Sets up a test model for the Neighborhood entity.

        This function creates a model with the required fields, including an id, name, and geometry (MultiPolygonField).
        If the database connection supports raster data or if forced, it also includes a raster field.

        The model is then applied to the current project state, updating the database schema accordingly.

        :param force_raster_creation: Forces the creation of the raster field, even if the database connection does not support it.
        :returns: The updated project state.

        """
        test_fields = [
            ("id", models.AutoField(primary_key=True)),
            ("name", models.CharField(max_length=100, unique=True)),
            ("geom", fields.MultiPolygonField(srid=4326)),
        ]
        if connection.features.supports_raster or force_raster_creation:
            test_fields += [("rast", fields.RasterField(srid=4326, null=True))]
        operations = [migrations.CreateModel("Neighborhood", test_fields)]
        self.current_state = self.apply_operations("gis", ProjectState(), operations)

    def assertGeometryColumnsCount(self, expected_count):
        self.assertEqual(
            GeometryColumns.objects.filter(
                **{
                    "%s__iexact" % GeometryColumns.table_name_col(): "gis_neighborhood",
                }
            ).count(),
            expected_count,
        )

    def assertSpatialIndexExists(self, table, column, raster=False):
        """

        Asserts the existence of a spatial index on a specified table and column.

        Args:
            table (str): Name of the table to check.
            column (str): Name of the column to check.
            raster (bool): Whether the column is a raster type. Defaults to False.

        Notes:
            For non-raster columns, this function checks that the column is included in the spatial index.
            For raster columns, this function checks that the spatial index is defined using the st_convexhull function.

        """
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, table)
        if raster:
            self.assertTrue(
                any(
                    "st_convexhull(%s)" % column in c["definition"]
                    for c in constraints.values()
                    if c["definition"] is not None
                )
            )
        else:
            self.assertIn([column], [c["columns"] for c in constraints.values()])

    def alter_gis_model(
        self,
        migration_class,
        model_name,
        field_name,
        field_class=None,
        field_class_kwargs=None,
    ):
        args = [model_name, field_name]
        if field_class:
            field_class_kwargs = field_class_kwargs or {}
            args.append(field_class(**field_class_kwargs))
        operation = migration_class(*args)
        old_state = self.current_state.clone()
        operation.state_forwards("gis", self.current_state)
        with connection.schema_editor() as editor:
            operation.database_forwards("gis", editor, old_state, self.current_state)


class OperationTests(OperationTestCase):
    def setUp(self):
        """

        Sets up the test environment.

        This method is called before each test and is responsible for initializing the test setup.
        It first calls the parent class's setUp method to perform any necessary setup, and then
        calls the set_up_test_model method to configure the test model. This ensures that each
        test starts with a consistent and properly configured environment.

        """
        super().setUp()
        self.set_up_test_model()

    def test_add_geom_field(self):
        """
        Test the AddField operation with a geometry-enabled column.
        """
        self.alter_gis_model(
            migrations.AddField, "Neighborhood", "path", fields.LineStringField
        )
        self.assertColumnExists("gis_neighborhood", "path")

        # Test GeometryColumns when available
        if HAS_GEOMETRY_COLUMNS:
            self.assertGeometryColumnsCount(2)

        # Test spatial indices when available
        if self.has_spatial_indexes:
            self.assertSpatialIndexExists("gis_neighborhood", "path")

    @skipUnless(connection.vendor == "mysql", "MySQL specific test")
    def test_remove_geom_field_nullable_with_index(self):
        # MySQL doesn't support spatial indexes on NULL columns.
        """
        Tests the removal of a nullable geometry field with an index on a MySQL database.

        This test case verifies that the field is correctly removed from the model and the
        associated column is dropped from the database table. It also checks that no spatial
        index is created during the addition of the field and that no error is logged during
        the removal of the field.

        The test covers the following scenarios:

        * Adding a nullable geometry field to the model and verifying that the column is created
          in the database table without a spatial index.
        * Removing the geometry field from the model and verifying that the column is dropped
          from the database table without logging any errors.

        """
        with self.assertNumQueries(1) as ctx:
            self.alter_gis_model(
                migrations.AddField,
                "Neighborhood",
                "path",
                fields.LineStringField,
                field_class_kwargs={"null": True},
            )
        self.assertColumnExists("gis_neighborhood", "path")
        self.assertNotIn("CREATE SPATIAL INDEX", ctx.captured_queries[0]["sql"])

        with self.assertNumQueries(1), self.assertNoLogs("django.contrib.gis", "ERROR"):
            self.alter_gis_model(migrations.RemoveField, "Neighborhood", "path")
        self.assertColumnNotExists("gis_neighborhood", "path")

    @skipUnless(HAS_GEOMETRY_COLUMNS, "Backend doesn't support GeometryColumns.")
    def test_geom_col_name(self):
        self.assertEqual(
            GeometryColumns.geom_col_name(),
            "column_name" if connection.ops.oracle else "f_geometry_column",
        )

    @skipUnlessDBFeature("supports_raster")
    def test_add_raster_field(self):
        """
        Test the AddField operation with a raster-enabled column.
        """
        self.alter_gis_model(
            migrations.AddField, "Neighborhood", "heatmap", fields.RasterField
        )
        self.assertColumnExists("gis_neighborhood", "heatmap")

        # Test spatial indices when available
        if self.has_spatial_indexes:
            self.assertSpatialIndexExists("gis_neighborhood", "heatmap", raster=True)

    def test_add_blank_geom_field(self):
        """
        Should be able to add a GeometryField with blank=True.
        """
        self.alter_gis_model(
            migrations.AddField,
            "Neighborhood",
            "path",
            fields.LineStringField,
            field_class_kwargs={"blank": True},
        )
        self.assertColumnExists("gis_neighborhood", "path")

        # Test GeometryColumns when available
        if HAS_GEOMETRY_COLUMNS:
            self.assertGeometryColumnsCount(2)

        # Test spatial indices when available
        if self.has_spatial_indexes:
            self.assertSpatialIndexExists("gis_neighborhood", "path")

    @skipUnlessDBFeature("supports_raster")
    def test_add_blank_raster_field(self):
        """
        Should be able to add a RasterField with blank=True.
        """
        self.alter_gis_model(
            migrations.AddField,
            "Neighborhood",
            "heatmap",
            fields.RasterField,
            field_class_kwargs={"blank": True},
        )
        self.assertColumnExists("gis_neighborhood", "heatmap")

        # Test spatial indices when available
        if self.has_spatial_indexes:
            self.assertSpatialIndexExists("gis_neighborhood", "heatmap", raster=True)

    def test_remove_geom_field(self):
        """
        Test the RemoveField operation with a geometry-enabled column.
        """
        self.alter_gis_model(migrations.RemoveField, "Neighborhood", "geom")
        self.assertColumnNotExists("gis_neighborhood", "geom")

        # Test GeometryColumns when available
        if HAS_GEOMETRY_COLUMNS:
            self.assertGeometryColumnsCount(0)

    @skipUnlessDBFeature("supports_raster")
    def test_remove_raster_field(self):
        """
        Test the RemoveField operation with a raster-enabled column.
        """
        self.alter_gis_model(migrations.RemoveField, "Neighborhood", "rast")
        self.assertColumnNotExists("gis_neighborhood", "rast")

    def test_create_model_spatial_index(self):
        """

        Tests the successful creation of a spatial index for a model.

        Checks if the spatial indexes are supported and if so, verifies that a spatial index 
        exists for the 'geom' field in the 'gis_neighborhood' model. Additionally, if the 
        database connection supports raster data, it checks for a spatial index on the 'rast' 
        field in the same model.

        This test ensures that the spatial indexes are properly set up, which is essential 
        for efficient spatial queries and operations on the model's geographic data.

        """
        if not self.has_spatial_indexes:
            self.skipTest("No support for Spatial indexes")

        self.assertSpatialIndexExists("gis_neighborhood", "geom")

        if connection.features.supports_raster:
            self.assertSpatialIndexExists("gis_neighborhood", "rast", raster=True)

    @skipUnlessDBFeature("supports_3d_storage")
    def test_add_3d_field_opclass(self):
        """

        Tests the addition of a 3D field to a model using the AddField operation.

        Verifies that the column is created with the correct spatial index and 
        that the correct GiST index opclass is used for 3D geometry storage. 

        This test is specific to PostGIS and requires a database that supports 
        3D geometry storage.

        """
        if not connection.ops.postgis:
            self.skipTest("PostGIS-specific test.")

        self.alter_gis_model(
            migrations.AddField,
            "Neighborhood",
            "point3d",
            field_class=fields.PointField,
            field_class_kwargs={"dim": 3},
        )
        self.assertColumnExists("gis_neighborhood", "point3d")
        self.assertSpatialIndexExists("gis_neighborhood", "point3d")

        with connection.cursor() as cursor:
            index_name = "gis_neighborhood_point3d_113bc868_id"
            cursor.execute(self.get_opclass_query, [index_name])
            self.assertEqual(
                cursor.fetchall(),
                [("gist_geometry_ops_nd", index_name)],
            )

    @skipUnlessDBFeature("can_alter_geometry_field", "supports_3d_storage")
    def test_alter_geom_field_dim(self):
        """
        Tests the alteration of a geometry field's dimension.

        This test case creates an instance of a 'Neighborhood' model with a MultiPolygon
        geometry field, then alters the field to change its dimension from 2D to 3D and
        back to 2D, verifying that the dimension change is correctly applied to the
        geometry data.

        Requires the database backend to support altering geometry fields and 3D storage.
        """
        Neighborhood = self.current_state.apps.get_model("gis", "Neighborhood")
        p1 = Polygon(((0, 0), (0, 1), (1, 1), (1, 0), (0, 0)))
        Neighborhood.objects.create(name="TestDim", geom=MultiPolygon(p1, p1))
        # Add 3rd dimension.
        self.alter_gis_model(
            migrations.AlterField,
            "Neighborhood",
            "geom",
            fields.MultiPolygonField,
            field_class_kwargs={"dim": 3},
        )
        self.assertTrue(Neighborhood.objects.first().geom.hasz)
        # Rewind to 2 dimensions.
        self.alter_gis_model(
            migrations.AlterField,
            "Neighborhood",
            "geom",
            fields.MultiPolygonField,
            field_class_kwargs={"dim": 2},
        )
        self.assertFalse(Neighborhood.objects.first().geom.hasz)

    @skipUnlessDBFeature(
        "supports_column_check_constraints", "can_introspect_check_constraints"
    )
    def test_add_check_constraint(self):
        Neighborhood = self.current_state.apps.get_model("gis", "Neighborhood")
        poly = Polygon(((0, 0), (0, 1), (1, 1), (1, 0), (0, 0)))
        constraint = models.CheckConstraint(
            condition=models.Q(geom=poly),
            name="geom_within_constraint",
        )
        Neighborhood._meta.constraints = [constraint]
        with connection.schema_editor() as editor:
            editor.add_constraint(Neighborhood, constraint)
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(
                cursor,
                Neighborhood._meta.db_table,
            )
            self.assertIn("geom_within_constraint", constraints)


@skipIfDBFeature("supports_raster")
class NoRasterSupportTests(OperationTestCase):
    def test_create_raster_model_on_db_without_raster_support(self):
        """
        Tests the creation of a raster model on a database without raster support.

        This function verifies that an :class:`ImproperlyConfigured` exception is raised when attempting to create a raster model on a database that does not support raster fields, ensuring that the expected error message is returned.
        """
        msg = "Raster fields require backends with raster support."
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            self.set_up_test_model(force_raster_creation=True)

    def test_add_raster_field_on_db_without_raster_support(self):
        """

        Tests that attempting to add a raster field to a database without raster support raises an ImproperlyConfigured exception.

        The test checks that the expected error message is raised when trying to add a RasterField to a model, simulating a scenario where the database backend does not support raster data types.

        """
        msg = "Raster fields require backends with raster support."
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            self.set_up_test_model()
            self.alter_gis_model(
                migrations.AddField, "Neighborhood", "heatmap", fields.RasterField
            )
