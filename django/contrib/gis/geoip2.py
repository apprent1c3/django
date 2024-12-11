"""
This module houses the GeoIP2 object, a wrapper for the MaxMind GeoIP2(R)
Python API (https://geoip2.readthedocs.io/). This is an alternative to the
Python GeoIP2 interface provided by MaxMind.

GeoIP(R) is a registered trademark of MaxMind, Inc.

For IP-based geolocation, this module requires the GeoLite2 Country and City
datasets, in binary format (CSV will not work!). The datasets may be
downloaded from MaxMind at https://dev.maxmind.com/geoip/geoip2/geolite2/.
Grab GeoLite2-Country.mmdb.gz and GeoLite2-City.mmdb.gz, and unzip them in the
directory corresponding to settings.GEOIP_PATH.
"""

import ipaddress
import socket
import warnings

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_ipv46_address
from django.utils._os import to_path
from django.utils.deprecation import RemovedInDjango60Warning
from django.utils.functional import cached_property

__all__ = ["HAS_GEOIP2"]

try:
    import geoip2.database
except ImportError:  # pragma: no cover
    HAS_GEOIP2 = False
else:
    HAS_GEOIP2 = True
    __all__ += ["GeoIP2", "GeoIP2Exception"]


class GeoIP2Exception(Exception):
    pass


class GeoIP2:
    # The flags for GeoIP memory caching.
    # Try MODE_MMAP_EXT, MODE_MMAP, MODE_FILE in that order.
    MODE_AUTO = 0
    # Use the C extension with memory map.
    MODE_MMAP_EXT = 1
    # Read from memory map. Pure Python.
    MODE_MMAP = 2
    # Read database as standard file. Pure Python.
    MODE_FILE = 4
    # Load database into memory. Pure Python.
    MODE_MEMORY = 8
    cache_options = frozenset(
        (MODE_AUTO, MODE_MMAP_EXT, MODE_MMAP, MODE_FILE, MODE_MEMORY)
    )

    _path = None
    _reader = None

    def __init__(self, path=None, cache=0, country=None, city=None):
        """
        Initialize the GeoIP object. No parameters are required to use default
        settings. Keyword arguments may be passed in to customize the locations
        of the GeoIP datasets.

        * path: Base directory to where GeoIP data is located or the full path
            to where the city or country data files (*.mmdb) are located.
            Assumes that both the city and country data sets are located in
            this directory; overrides the GEOIP_PATH setting.

        * cache: The cache settings when opening up the GeoIP datasets. May be
            an integer in (0, 1, 2, 4, 8) corresponding to the MODE_AUTO,
            MODE_MMAP_EXT, MODE_MMAP, MODE_FILE, and MODE_MEMORY,
            `GeoIPOptions` C API settings,  respectively. Defaults to 0,
            meaning MODE_AUTO.

        * country: The name of the GeoIP country data file. Defaults to
            'GeoLite2-Country.mmdb'; overrides the GEOIP_COUNTRY setting.

        * city: The name of the GeoIP city data file. Defaults to
            'GeoLite2-City.mmdb'; overrides the GEOIP_CITY setting.
        """
        if cache not in self.cache_options:
            raise GeoIP2Exception("Invalid GeoIP caching option: %s" % cache)

        path = path or getattr(settings, "GEOIP_PATH", None)
        city = city or getattr(settings, "GEOIP_CITY", "GeoLite2-City.mmdb")
        country = country or getattr(settings, "GEOIP_COUNTRY", "GeoLite2-Country.mmdb")

        if not path:
            raise GeoIP2Exception(
                "GeoIP path must be provided via parameter or the GEOIP_PATH setting."
            )

        path = to_path(path)

        # Try the path first in case it is the full path to a database.
        for path in (path, path / city, path / country):
            if path.is_file():
                self._path = path
                self._reader = geoip2.database.Reader(path, mode=cache)
                break
        else:
            raise GeoIP2Exception(
                "Path must be a valid database or directory containing databases."
            )

        database_type = self._metadata.database_type
        if not database_type.endswith(("City", "Country")):
            raise GeoIP2Exception(f"Unable to handle database edition: {database_type}")

    def __del__(self):
        # Cleanup any GeoIP file handles lying around.
        if self._reader:
            self._reader.close()

    def __repr__(self):
        m = self._metadata
        version = f"v{m.binary_format_major_version}.{m.binary_format_minor_version}"
        return f"<{self.__class__.__name__} [{version}] _path='{self._path}'>"

    @cached_property
    def _metadata(self):
        return self._reader.metadata()

    def _query(self, query, *, require_city=False):
        """

        Perform a GeoIP query to retrieve geographic information.

        Parameters
        ----------
        query : str or ipaddress.IPv4Address or ipaddress.IPv6Address
            The query to perform, which can be a string (e.g., hostname, IP address), an IPv4Address, or an IPv6Address.
        require_city : bool, optional
            If True, the query requires city-level data. If the database does not contain city-level data, a GeoIP2Exception is raised.

        Returns
        -------
        The result of the query, which can be either city or country-level data, depending on the database type.

        Raises
        ------
        TypeError
            If the query is not a string or an instance of IPv4Address or IPv6Address.
        GeoIP2Exception
            If city-level data is required but the database does not contain it.

        """
        if not isinstance(query, (str, ipaddress.IPv4Address, ipaddress.IPv6Address)):
            raise TypeError(
                "GeoIP query must be a string or instance of IPv4Address or "
                "IPv6Address, not type %s" % type(query).__name__,
            )

        is_city = self._metadata.database_type.endswith("City")

        if require_city and not is_city:
            raise GeoIP2Exception(f"Invalid GeoIP city data file: {self._path}")

        try:
            validate_ipv46_address(query)
        except ValidationError:
            # GeoIP2 only takes IP addresses, so try to resolve a hostname.
            query = socket.gethostbyname(query)

        function = self._reader.city if is_city else self._reader.country
        return function(query)

    def city(self, query):
        """
        Return a dictionary of city information for the given IP address or
        Fully Qualified Domain Name (FQDN). Some information in the dictionary
        may be undefined (None).
        """
        response = self._query(query, require_city=True)
        region = response.subdivisions[0] if response.subdivisions else None
        return {
            "accuracy_radius": response.location.accuracy_radius,
            "city": response.city.name,
            "continent_code": response.continent.code,
            "continent_name": response.continent.name,
            "country_code": response.country.iso_code,
            "country_name": response.country.name,
            "is_in_european_union": response.country.is_in_european_union,
            "latitude": response.location.latitude,
            "longitude": response.location.longitude,
            "metro_code": response.location.metro_code,
            "postal_code": response.postal.code,
            "region_code": region.iso_code if region else None,
            "region_name": region.name if region else None,
            "time_zone": response.location.time_zone,
            # Kept for backward compatibility.
            "dma_code": response.location.metro_code,
            "region": region.iso_code if region else None,
        }

    def country_code(self, query):
        "Return the country code for the given IP Address or FQDN."
        return self.country(query)["country_code"]

    def country_name(self, query):
        "Return the country name for the given IP Address or FQDN."
        return self.country(query)["country_name"]

    def country(self, query):
        """
        Return a dictionary with the country code and name when given an
        IP address or a Fully Qualified Domain Name (FQDN). For example, both
        '24.124.1.80' and 'djangoproject.com' are valid parameters.
        """
        response = self._query(query, require_city=False)
        return {
            "continent_code": response.continent.code,
            "continent_name": response.continent.name,
            "country_code": response.country.iso_code,
            "country_name": response.country.name,
            "is_in_european_union": response.country.is_in_european_union,
        }

    def coords(self, query, ordering=("longitude", "latitude")):
        """

        Retrieve the coordinates for a query from the GeoIP2 database.

        This method takes a query and returns a tuple of the longitude and latitude in the specified order. 
        By default, the order is (longitude, latitude), but this can be customized by passing a tuple of 'longitude' and 'latitude' in the desired order.

        Note:
            This method is deprecated and will be removed in Django 6.0. It is recommended to use the `GeoIP2.lon_lat()` method instead.

        :param query: The query to search for in the GeoIP2 database.
        :param ordering: A tuple specifying the order of the coordinates. Defaults to ('longitude', 'latitude').
        :return: A tuple of the coordinates in the specified order.
        :rtype: tuple

        """
        warnings.warn(
            "GeoIP2.coords() is deprecated. Use GeoIP2.lon_lat() instead.",
            RemovedInDjango60Warning,
            stacklevel=2,
        )
        data = self.city(query)
        return tuple(data[o] for o in ordering)

    def lon_lat(self, query):
        "Return a tuple of the (longitude, latitude) for the given query."
        data = self.city(query)
        return data["longitude"], data["latitude"]

    def lat_lon(self, query):
        "Return a tuple of the (latitude, longitude) for the given query."
        data = self.city(query)
        return data["latitude"], data["longitude"]

    def geos(self, query):
        "Return a GEOS Point object for the given query."
        # Allows importing and using GeoIP2() when GEOS is not installed.
        from django.contrib.gis.geos import Point

        return Point(self.lon_lat(query), srid=4326)

    @classmethod
    def open(cls, full_path, cache):
        warnings.warn(
            "GeoIP2.open() is deprecated. Use GeoIP2() instead.",
            RemovedInDjango60Warning,
            stacklevel=2,
        )
        return GeoIP2(full_path, cache)
