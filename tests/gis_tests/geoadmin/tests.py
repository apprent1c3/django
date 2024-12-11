from django.contrib.gis.geos import Point
from django.test import SimpleTestCase, override_settings

from .models import City, site, site_gis, site_gis_custom


@override_settings(ROOT_URLCONF="django.contrib.gis.tests.geoadmin.urls")
class GeoAdminTest(SimpleTestCase):
    admin_site = site  # ModelAdmin

    def test_widget_empty_string(self):
        geoadmin = self.admin_site.get_model_admin(City)
        form = geoadmin.get_changelist_form(None)({"point": ""})
        with self.assertRaisesMessage(AssertionError, "no logs"):
            with self.assertLogs("django.contrib.gis", "ERROR"):
                output = str(form["point"])
        self.assertInHTML(
            '<textarea id="id_point" class="vSerializedField required" cols="150"'
            ' rows="10" name="point" hidden></textarea>',
            output,
        )

    def test_widget_invalid_string(self):
        """
        Tests the behavior of the widget when an invalid string is provided for a geometric field.

        This test case verifies that the widget correctly handles invalid input by logging an error and
        rendering the expected form field. The test checks the widget's output and the logged error messages
        to ensure they match the expected behavior.

        The test case specifically checks that the widget:

        * Logs an error when an invalid string is provided
        * Renders a textarea field with the correct attributes
        * Produces the expected number of error logs with the correct error messages
        """
        geoadmin = self.admin_site.get_model_admin(City)
        form = geoadmin.get_changelist_form(None)({"point": "INVALID()"})
        with self.assertLogs("django.contrib.gis", "ERROR") as cm:
            output = str(form["point"])
        self.assertInHTML(
            '<textarea id="id_point" class="vSerializedField required" cols="150"'
            ' rows="10" name="point" hidden></textarea>',
            output,
        )
        self.assertEqual(len(cm.records), 2)
        self.assertEqual(
            cm.records[0].getMessage(),
            "Error creating geometry from value 'INVALID()' (String input "
            "unrecognized as WKT EWKT, and HEXEWKB.)",
        )

    def test_widget_has_changed(self):
        """

        Tests the functionality of the 'has_changed' method in the form field for the 'point' attribute.
        This ensures the method correctly identifies changes to the geographical point, considering different scenarios:
        - When no initial data is provided
        - When the data is the same as the initial value
        - When the data is almost the same (with minor differences in decimal places)
        - When the data is significantly different from the initial value
        The test covers these cases to guarantee the method behaves as expected in various situations.

        """
        geoadmin = self.admin_site.get_model_admin(City)
        form = geoadmin.get_changelist_form(None)()
        has_changed = form.fields["point"].has_changed

        initial = Point(13.4197458572965953, 52.5194108501149799, srid=4326)
        data_same = "SRID=3857;POINT(1493879.2754093995 6894592.019687599)"
        data_almost_same = "SRID=3857;POINT(1493879.2754093990 6894592.019687590)"
        data_changed = "SRID=3857;POINT(1493884.0527237 6894593.8111804)"

        self.assertIs(has_changed(None, data_changed), True)
        self.assertIs(has_changed(initial, ""), True)
        self.assertIs(has_changed(None, ""), False)
        self.assertIs(has_changed(initial, data_same), False)
        self.assertIs(has_changed(initial, data_almost_same), False)
        self.assertIs(has_changed(initial, data_changed), True)


class GISAdminTests(GeoAdminTest):
    admin_site = site_gis  # GISModelAdmin

    def test_default_gis_widget_kwargs(self):
        """
        Tests the default keyword arguments for the GIS widget.

        This test case checks if the default latitude, longitude, and zoom level
        are correctly set for the GIS widget in the City model's changelist form.

        The expected values are:
            - default latitude: 47
            - default longitude: 5
            - default zoom: 12

        Verifies that these defaults are applied as widget attributes, ensuring
        proper initialization of the GIS widget in the changelist view.
        """
        geoadmin = self.admin_site.get_model_admin(City)
        form = geoadmin.get_changelist_form(None)()
        widget = form["point"].field.widget
        self.assertEqual(widget.attrs["default_lat"], 47)
        self.assertEqual(widget.attrs["default_lon"], 5)
        self.assertEqual(widget.attrs["default_zoom"], 12)

    def test_custom_gis_widget_kwargs(self):
        """

        Tests the custom GIS widget with specified keyword arguments.

        This test case verifies that the custom GIS widget used in the City model admin form
        has been properly configured with default location and zoom level.
        It checks the widget's attributes for the default latitude, longitude, and zoom level.

        """
        geoadmin = site_gis_custom.get_model_admin(City)
        form = geoadmin.get_changelist_form(None)()
        widget = form["point"].field.widget
        self.assertEqual(widget.attrs["default_lat"], 55)
        self.assertEqual(widget.attrs["default_lon"], 37)
        self.assertEqual(widget.attrs["default_zoom"], 12)
