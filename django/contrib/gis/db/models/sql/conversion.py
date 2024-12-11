"""
This module holds simple classes to convert geospatial values from the
database.
"""

from decimal import Decimal

from django.contrib.gis.measure import Area, Distance
from django.db import models


class AreaField(models.FloatField):
    "Wrapper for Area values."

    def __init__(self, geo_field):
        super().__init__()
        self.geo_field = geo_field

    def get_prep_value(self, value):
        if not isinstance(value, Area):
            raise ValueError("AreaField only accepts Area measurement objects.")
        return value

    def get_db_prep_value(self, value, connection, prepared=False):
        """
        Returns the prepared value of a geographic field for database storage.

        Parameters
        ----------
        value : object
            The geographic value to be prepared for database storage.
        connection : object
            The database connection object.
        prepared : bool, optional
            A flag indicating whether the value is already prepared (default is False).

        Returns
        -------
        object
            The prepared geographic value, or None if the input value is None.

        The preparation process involves retrieving the area attribute for the
        geographic field from the database connection operations and using it
        to get the corresponding attribute from the value object. If no area
        attribute is found, the original value is returned.
        """
        if value is None:
            return
        area_att = connection.ops.get_area_att_for_field(self.geo_field)
        return getattr(value, area_att) if area_att else value

    def from_db_value(self, value, expression, connection):
        if value is None:
            return
        # If the database returns a Decimal, convert it to a float as expected
        # by the Python geometric objects.
        if isinstance(value, Decimal):
            value = float(value)
        # If the units are known, convert value into area measure.
        area_att = connection.ops.get_area_att_for_field(self.geo_field)
        return Area(**{area_att: value}) if area_att else value

    def get_internal_type(self):
        return "AreaField"


class DistanceField(models.FloatField):
    "Wrapper for Distance values."

    def __init__(self, geo_field):
        """
        Initializes the object, setting up the geographic field attribute.

        :param geo_field: The geographic field to be associated with this object
        :type geo_field: 
        :raises: 
        :note: This method is called when an instance of the class is created and is used to establish the geographic context for subsequent operations.
        """
        super().__init__()
        self.geo_field = geo_field

    def get_prep_value(self, value):
        if isinstance(value, Distance):
            return value
        return super().get_prep_value(value)

    def get_db_prep_value(self, value, connection, prepared=False):
        if not isinstance(value, Distance):
            return value
        distance_att = connection.ops.get_distance_att_for_field(self.geo_field)
        if not distance_att:
            raise ValueError(
                "Distance measure is supplied, but units are unknown for result."
            )
        return getattr(value, distance_att)

    def from_db_value(self, value, expression, connection):
        if value is None:
            return
        distance_att = connection.ops.get_distance_att_for_field(self.geo_field)
        return Distance(**{distance_att: value}) if distance_att else value

    def get_internal_type(self):
        return "DistanceField"
