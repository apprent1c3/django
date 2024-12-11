from django.db.migrations.serializer import BaseSerializer


class RangeSerializer(BaseSerializer):
    def serialize(self):
        """
        Serialize the object's value into a string representation, including the module name.

        The serialized value is returned as a tuple, where the first element is a string
        representation of the value, and the second element is a set of import statements
        required to reconstruct the value. This allows for the object to be recreated
        using the serialized string.

        Note that the module name is adjusted for compatibility with psycopg2's range
        types, which are stored in the `_range` module but should be imported from
        `extras` instead.
        """
        module = self.value.__class__.__module__
        # Ranges are implemented in psycopg2._range but the public import
        # location is psycopg2.extras.
        module = "psycopg2.extras" if module == "psycopg2._range" else module
        return "%s.%r" % (module, self.value), {"import %s" % module}
