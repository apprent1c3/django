from django.contrib.gis.geos.geometry import GEOSGeometry, hex_regex, wkt_regex


def fromfile(file_h):
    """

    Load a GEOSGeometry from a file.

    The file can contain WKB, WKT, or HEX data. This function reads the file's contents
    and returns a GEOSGeometry object, attempting to decode the data if necessary.

    :param file_h: file name (as a string) or a file-like object
    :return: a GEOSGeometry object

    """
    # If given a file name, get a real handle.
    if isinstance(file_h, str):
        with open(file_h, "rb") as file_h:
            buf = file_h.read()
    else:
        buf = file_h.read()

    # If we get WKB need to wrap in memoryview(), so run through regexes.
    if isinstance(buf, bytes):
        try:
            decoded = buf.decode()
        except UnicodeDecodeError:
            pass
        else:
            if wkt_regex.match(decoded) or hex_regex.match(decoded):
                return GEOSGeometry(decoded)
    else:
        return GEOSGeometry(buf)

    return GEOSGeometry(memoryview(buf))


def fromstr(string, **kwargs):
    "Given a string value, return a GEOSGeometry object."
    return GEOSGeometry(string, **kwargs)
