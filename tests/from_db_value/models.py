import decimal

from django.db import models


class Cash(decimal.Decimal):
    currency = "USD"


class CashField(models.DecimalField):
    def __init__(self, **kwargs):
        """
        Initializes the class instance with default settings for decimal fields.

        The function sets the maximum number of digits to 20 and the decimal places to 2, 
        providing a standardized formatting for decimal values. These default settings 
        can be overridden by passing custom keyword arguments when creating an instance 
        of the class. All additional keyword arguments are passed to the parent class 
        for further initialization. 
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
