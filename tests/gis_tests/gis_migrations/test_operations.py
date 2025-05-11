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
        if connection.ops.mysql:
            with connection.cursor() as cursor:
                return connection.introspection.supports_spatial_index(
                    cursor, "gis_neighborhood"
                )
        return True

    def get_table_description(self, table):
        with connection.cursor() as cursor:
            return connection.introspection.get_table_description(cursor, table)

    def assertColumnExists(self, table, column):
        self.assertIn(column, [c.name for c in self.get_table_description(table)])

    def assertColumnNotExists(self, table, column):
        self.assertNotIn(column, [c.name for c in self.get_table_description(table)])

    def apply_operations(self, app_label, project_state, operations):
        migration = Migration("name", app_label)
        migration.operations = operations
        with connection.schema_editor() as editor:
            return migration.apply(project_state, editor)

    def set_up_test_model(self, force_raster_creation=False):
        """
        Sets up a test model for geographic information system (GIS) operations, optionally including a raster field if the database supports it or if forced. The model includes fields for a unique identifier, name, and geometry, and the raster field if applicable.
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

        Verifies that a spatial index exists on the specified column of a given table.

        If raster is True, checks for a convex hull constraint; otherwise, checks for a standard spatial index.

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
        """
        Alter a Geographic Information System (GIS) model by applying the specified migration operation.

        :param migration_class: The class of the migration operation to apply
        :param model_name: The name of the model to alter
        :param field_name: The name of the field to alter
        :param field_class: The class of the new field (optional)
        :param field_class_kwargs: Keyword arguments for the new field class (optional)
        """
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
        super().setUp()
        self.set_up_test_model()

    def test_add_geom_field(self):
        """
        Tests the addition of a geometry field to a model, verifying the field's existence and spatial index creation.
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
        Tests the removal of a nullable geometry field with an index on a MySQL database, verifying that the column is removed without generating a spatial index creation query.
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

            Tests adding a raster field to a model using the AddField migration operation.

            Verifies that the operation successfully adds the field to the model and creates
            the necessary spatial index if supported by the database.

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
        Tests the ability to add a GeometryField with blank=True to a model, verifying that the column and geometry columns exist, and a spatial index is created if applicable.
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
        Tests the ability to add a RasterField to a GIS model with the blank attribute set to True, verifying the field's existence and spatial index creation if supported.
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
        Tests the removal of a geometry field from a model using the RemoveField operation, verifying the column is deleted and geometry columns are updated accordingly.
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
        Tests the creation of a spatial index on the 'gis_neighborhood' model, verifying its existence for both geometry and raster fields, if supported by the database connection.
        """
        if not self.has_spatial_indexes:
            self.skipTest("No support for Spatial indexes")

        self.assertSpatialIndexExists("gis_neighborhood", "geom")

        if connection.features.supports_raster:
            self.assertSpatialIndexExists("gis_neighborhood", "rast", raster=True)

    @skipUnlessDBFeature("supports_3d_storage")
    def test_add_3d_field_opclass(self):
        """
        Tests the addition of a 3D field with the correct opclass in a PostGIS-enabled database, verifying both the column and spatial index existence, as well as the opclass specified on the index.
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
        Verifies that the dimension of a geometry field can be altered and that it correctly reflects in the geometry data stored in the database.

        Tests transitioning between 2D and 3D geometry storage and checks for the presence or absence of Z coordinates in the geometry data after each alteration.
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
        """
        Tests the addition of a check constraint to a model, verifying that the constraint can be successfully applied and introspected from the database.
        """
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
        msg = "Raster fields require backends with raster support."
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            self.set_up_test_model(force_raster_creation=True)

    def test_add_raster_field_on_db_without_raster_support(self):
        msg = "Raster fields require backends with raster support."
        with self.assertRaisesMessage(ImproperlyConfigured, msg):
            self.set_up_test_model()
            self.alter_gis_model(
                migrations.AddField, "Neighborhood", "heatmap", fields.RasterField
            )
