import json
import warnings

from django.conf import settings
from django.contrib.admin.utils import quote
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.deprecation import RemovedInDjango60Warning
from django.utils.text import get_text_list
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

ADDITION = 1
CHANGE = 2
DELETION = 3

ACTION_FLAG_CHOICES = [
    (ADDITION, _("Addition")),
    (CHANGE, _("Change")),
    (DELETION, _("Deletion")),
]


class LogEntryManager(models.Manager):
    use_in_migrations = True

    def log_action(
        self,
        user_id,
        content_type_id,
        object_id,
        object_repr,
        action_flag,
        change_message="",
    ):
        """

        Logs an action performed by a user on an object.

        This method records a log entry for the specified action, including information about the user, object, and any changes made.
        It stores details such as the user who performed the action, the type and ID of the object, a short representation of the object, 
        and a flag indicating the type of action (e.g., creation, update, deletion). Additionally, it can store a message describing the changes made.

        Note: This method is deprecated since Django 3.x and will be removed in Django 6.0. It is recommended to use :meth:`log_actions()` instead.

        Parameters
        ----------
        user_id : int
            The ID of the user who performed the action.
        content_type_id : int
            The ID of the content type of the object.
        object_id : str
            The ID of the object.
        object_repr : str
            A short representation of the object.
        action_flag : int
            A flag indicating the type of action (e.g., creation, update, deletion).
        change_message : str
            A message describing the changes made.

        Returns
        -------
        LogEntry
            The newly created log entry instance.

        """
        warnings.warn(
            "LogEntryManager.log_action() is deprecated. Use log_actions() instead.",
            RemovedInDjango60Warning,
            stacklevel=2,
        )
        if isinstance(change_message, list):
            change_message = json.dumps(change_message)
        return self.model.objects.create(
            user_id=user_id,
            content_type_id=content_type_id,
            object_id=str(object_id),
            object_repr=object_repr[:200],
            action_flag=action_flag,
            change_message=change_message,
        )

    def log_actions(
        self, user_id, queryset, action_flag, change_message="", *, single_object=False
    ):
        # RemovedInDjango60Warning.
        """
        Logs actions performed by a user on a queryset of objects.

        :param user_id: The ID of the user performing the action.
        :param queryset: A queryset of objects that the action was performed on.
        :param action_flag: A flag indicating the type of action performed.
        :param change_message: An optional message describing the changes made.
        :param single_object: If True, log a single action for the entire queryset.

        :returns: The logged action instance if single_object is True, otherwise the result of bulk creating the log entries.

        :note: This method is not compatible with the deprecated log_action() method. If log_action() is used, a warning will be raised and the method will fall back to the deprecated behavior.

        Logs actions in bulk, allowing for efficient storage of user interactions with the system. The logged actions can be used for auditing, monitoring, or other purposes. If single_object is True, only one log entry will be created for the entire queryset, otherwise a log entry will be created for each object in the queryset.
        """
        if type(self).log_action != LogEntryManager.log_action:
            warnings.warn(
                "The usage of log_action() is deprecated. Implement log_actions() "
                "instead.",
                RemovedInDjango60Warning,
                stacklevel=2,
            )
            return [
                self.log_action(
                    user_id=user_id,
                    content_type_id=ContentType.objects.get_for_model(
                        obj, for_concrete_model=False
                    ).id,
                    object_id=obj.pk,
                    object_repr=str(obj),
                    action_flag=action_flag,
                    change_message=change_message,
                )
                for obj in queryset
            ]

        if isinstance(change_message, list):
            change_message = json.dumps(change_message)

        log_entry_list = [
            self.model(
                user_id=user_id,
                content_type_id=ContentType.objects.get_for_model(
                    obj, for_concrete_model=False
                ).id,
                object_id=obj.pk,
                object_repr=str(obj)[:200],
                action_flag=action_flag,
                change_message=change_message,
            )
            for obj in queryset
        ]

        if single_object and log_entry_list:
            instance = log_entry_list[0]
            instance.save()
            return instance

        return self.model.objects.bulk_create(log_entry_list)


class LogEntry(models.Model):
    action_time = models.DateTimeField(
        _("action time"),
        default=timezone.now,
        editable=False,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        models.CASCADE,
        verbose_name=_("user"),
    )
    content_type = models.ForeignKey(
        ContentType,
        models.SET_NULL,
        verbose_name=_("content type"),
        blank=True,
        null=True,
    )
    object_id = models.TextField(_("object id"), blank=True, null=True)
    # Translators: 'repr' means representation
    # (https://docs.python.org/library/functions.html#repr)
    object_repr = models.CharField(_("object repr"), max_length=200)
    action_flag = models.PositiveSmallIntegerField(
        _("action flag"), choices=ACTION_FLAG_CHOICES
    )
    # change_message is either a string or a JSON structure
    change_message = models.TextField(_("change message"), blank=True)

    objects = LogEntryManager()

    class Meta:
        verbose_name = _("log entry")
        verbose_name_plural = _("log entries")
        db_table = "django_admin_log"
        ordering = ["-action_time"]

    def __repr__(self):
        return str(self.action_time)

    def __str__(self):
        if self.is_addition():
            return gettext("Added “%(object)s”.") % {"object": self.object_repr}
        elif self.is_change():
            return gettext("Changed “%(object)s” — %(changes)s") % {
                "object": self.object_repr,
                "changes": self.get_change_message(),
            }
        elif self.is_deletion():
            return gettext("Deleted “%(object)s.”") % {"object": self.object_repr}

        return gettext("LogEntry Object")

    def is_addition(self):
        return self.action_flag == ADDITION

    def is_change(self):
        return self.action_flag == CHANGE

    def is_deletion(self):
        return self.action_flag == DELETION

    def get_change_message(self):
        """
        If self.change_message is a JSON structure, interpret it as a change
        string, properly translated.
        """
        if self.change_message and self.change_message[0] == "[":
            try:
                change_message = json.loads(self.change_message)
            except json.JSONDecodeError:
                return self.change_message
            messages = []
            for sub_message in change_message:
                if "added" in sub_message:
                    if sub_message["added"]:
                        sub_message["added"]["name"] = gettext(
                            sub_message["added"]["name"]
                        )
                        messages.append(
                            gettext("Added {name} “{object}”.").format(
                                **sub_message["added"]
                            )
                        )
                    else:
                        messages.append(gettext("Added."))

                elif "changed" in sub_message:
                    sub_message["changed"]["fields"] = get_text_list(
                        [
                            gettext(field_name)
                            for field_name in sub_message["changed"]["fields"]
                        ],
                        gettext("and"),
                    )
                    if "name" in sub_message["changed"]:
                        sub_message["changed"]["name"] = gettext(
                            sub_message["changed"]["name"]
                        )
                        messages.append(
                            gettext("Changed {fields} for {name} “{object}”.").format(
                                **sub_message["changed"]
                            )
                        )
                    else:
                        messages.append(
                            gettext("Changed {fields}.").format(
                                **sub_message["changed"]
                            )
                        )

                elif "deleted" in sub_message:
                    sub_message["deleted"]["name"] = gettext(
                        sub_message["deleted"]["name"]
                    )
                    messages.append(
                        gettext("Deleted {name} “{object}”.").format(
                            **sub_message["deleted"]
                        )
                    )

            change_message = " ".join(msg[0].upper() + msg[1:] for msg in messages)
            return change_message or gettext("No fields changed.")
        else:
            return self.change_message

    def get_edited_object(self):
        """Return the edited object represented by this log entry."""
        return self.content_type.get_object_for_this_type(pk=self.object_id)

    def get_admin_url(self):
        """
        Return the admin URL to edit the object represented by this log entry.
        """
        if self.content_type and self.object_id:
            url_name = "admin:%s_%s_change" % (
                self.content_type.app_label,
                self.content_type.model,
            )
            try:
                return reverse(url_name, args=(quote(self.object_id),))
            except NoReverseMatch:
                pass
        return None
