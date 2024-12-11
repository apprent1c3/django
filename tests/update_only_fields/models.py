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
        Returns the attribute name and column for the current object.

        This method extends the functionality of its parent class by returning
        the attribute name along with a default column value of None.

        The returned attribute name is retrieved from the parent class, while the
        column is explicitly set to None.

        :return: tuple containing the attribute name and column value
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
