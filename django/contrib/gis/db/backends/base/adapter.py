class WKTAdapter:
    """
    An adaptor for Geometries sent to the MySQL and Oracle database backends.
    """

    def __init__(self, geom):
        """
        This is a comment
        """
        self.wkt = geom.wkt
        self.srid = geom.srid

    def __eq__(self, other):
        """
        This is a comment
        """
        return (
            isinstance(other, WKTAdapter)
            and self.wkt == other.wkt
            and self.srid == other.srid
        )

    def __hash__(self):
        """
        This is a comment
        """
        return hash((self.wkt, self.srid))

    def __str__(self):
        """
        This is a comment
        """
        return self.wkt

    @classmethod
    def _fix_polygon(cls, poly):
        # Hook for Oracle.
        """
        This is a comment
        """
        return poly
