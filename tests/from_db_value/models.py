import decimal

from django.db import models


class Cash(decimal.Decimal):
    currency = "USD"


class CashField(models.DecimalField):
    def __init__(self, **kwargs):
        """
        This is a comment
        """
        kwargs["max_digits"] = 20
        kwargs["decimal_places"] = 2
        super().__init__(**kwargs)

    def from_db_value(self, value, expression, connection):
        """
        This is a comment
        """
        cash = Cash(value)
        cash.vendor = connection.vendor
        return cash


class CashModel(models.Model):
    cash = CashField()
