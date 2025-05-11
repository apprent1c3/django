from django.contrib.gis.gdal import SpatialReference
from django.db import DEFAULT_DB_ALIAS, connections


def add_srs_entry(
    srs, auth_name="EPSG", auth_srid=None, ref_sys_name=None, database=None
):
    """
    Add a Spatial Reference System (SRS) to the spatial backend database, enabling database-level spatial transformations.

    This function takes a GDAL SpatialReference system and its associated metadata, 
    then adds this information to the `spatial_ref_sys` table of the spatial backend.

    Parameters:
        srs (int or SpatialReference): The SRID or SpatialReference system to add.
        auth_name (str, optional): The authority name. Defaults to 'EPSG'.
        auth_srid (int, optional): The authority SRID. Defaults to the SRID determined by GDAL.
        ref_sys_name (str, optional): The reference system name. Defaults to the name determined by GDAL.
        database (str, optional): The name of the database connection to use. Defaults to the default database alias.

    Raises:
        Exception: If the spatial backend is not supported or the SpatialReference system is invalid.
    """
    database = database or DEFAULT_DB_ALIAS
    connection = connections[database]

    if not hasattr(connection.ops, "spatial_version"):
        raise Exception("The `add_srs_entry` utility only works with spatial backends.")
    if not connection.features.supports_add_srs_entry:
        raise Exception("This utility does not support your database backend.")
    SpatialRefSys = connection.ops.spatial_ref_sys()

    # If argument is not a `SpatialReference` instance, use it as parameter
    # to construct a `SpatialReference` instance.
    if not isinstance(srs, SpatialReference):
        srs = SpatialReference(srs)

    if srs.srid is None:
        raise Exception(
            "Spatial reference requires an SRID to be "
            "compatible with the spatial backend."
        )

    # Initializing the keyword arguments dictionary for both PostGIS
    # and SpatiaLite.
    kwargs = {
        "srid": srs.srid,
        "auth_name": auth_name,
        "auth_srid": auth_srid or srs.srid,
        "proj4text": srs.proj4,
    }
    # Backend-specific fields for the SpatialRefSys model.
    srs_field_names = {f.name for f in SpatialRefSys._meta.get_fields()}
    if "srtext" in srs_field_names:
        kwargs["srtext"] = srs.wkt
    if "ref_sys_name" in srs_field_names:
        # SpatiaLite specific
        kwargs["ref_sys_name"] = ref_sys_name or srs.name

    # Creating the spatial_ref_sys model.
    try:
        # Try getting via SRID only, because using all kwargs may
        # differ from exact wkt/proj in database.
        SpatialRefSys.objects.using(database).get(srid=srs.srid)
    except SpatialRefSys.DoesNotExist:
        SpatialRefSys.objects.using(database).create(**kwargs)
