from django.db import models


class Account(models.Model):
    num = models.IntegerField()


class Person(models.Model):
    GENDER_CHOICES = (
        ("M", "Male"),
        ("F", "Female"),
    )
    name = models.CharField(max_length=20)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    pid = models.IntegerField(null=True, default=None)


class Employee(Person):
    employee_num = models.IntegerField(default=0)
    profile = models.ForeignKey(
        "Profile", models.SET_NULL, related_name="profiles", null=True
    )
    accounts = models.ManyToManyField("Account", related_name="employees", blank=True)


class NonConcreteField(models.IntegerField):
    def db_type(self, connection):
        return None

    def get_attname_column(self):
        """
        Returns the attribute name and column information.

        This method overrides the parent class's implementation to return a tuple
        containing the attribute name and a column value of None.

        :return: A tuple of (attribute name, column), where column is always None.
        :rtype: tuple
        """
        attname, _ = super().get_attname_column()
        return attname, None


class Profile(models.Model):
    name = models.CharField(max_length=200)
    salary = models.FloatField(default=1000.0)
    non_concrete = NonConcreteField()


class ProxyEmployee(Employee):
    class Meta:
        proxy = True
