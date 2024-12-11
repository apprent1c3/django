import decimal

from django.db import models


class Cash(decimal.Decimal):
    currency = "USD"


class CashField(models.DecimalField):
    def __init__(self, **kwargs):
        """
        Initializes a numeric field with specific settings for decimal precision.

        This constructor sets default configurations for a numeric field, including 
        a maximum of 20 digits and 2 decimal places, and then passes any additional 
        keyword arguments to the parent class's initializer.
        """
        kwargs["max_digits"] = 20
        kwargs["decimal_places"] = 2
        super().__init__(**kwargs)

    def from_db_value(self, value, expression, connection):
        cash = Cash(value)
        cash.vendor = connection.vendor
        return cash


class CashModel(models.Model):
    cash = CashField()
