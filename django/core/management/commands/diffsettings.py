from django.core.management.base import BaseCommand


def module_to_dict(module, omittable=lambda k: k.startswith("_") or not k.isupper()):
    """Convert a module namespace to a Python dictionary."""
    return {k: repr(getattr(module, k)) for k in dir(module) if not omittable(k)}


class Command(BaseCommand):
    help = """Displays differences between the current settings.py and Django's
    default settings."""

    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help=(
                'Display all settings, regardless of their value. In "hash" '
                'mode, default values are prefixed by "###".'
            ),
        )
        parser.add_argument(
            "--default",
            metavar="MODULE",
            help=(
                "The settings module to compare the current settings against. Leave "
                "empty to compare against Django's default settings."
            ),
        )
        parser.add_argument(
            "--output",
            default="hash",
            choices=("hash", "unified"),
            help=(
                "Selects the output format. 'hash' mode displays each changed "
                "setting, with the settings that don't appear in the defaults "
                "followed by ###. 'unified' mode prefixes the default setting "
                "with a minus sign, followed by the changed setting prefixed "
                "with a plus sign."
            ),
        )

    def handle(self, **options):
        """

        Generates formatted output comparing the given Django project settings to a default configuration.

        The comparison is output in the specified format, either 'hash' or 'unified', and includes the differences between the project's settings and the default settings.

        :param options: A dictionary containing the comparison options, including 'default' and 'output'.
        :returns: A string representing the formatted comparison of the project settings to the default settings.

        """
        from django.conf import Settings, global_settings, settings

        # Because settings are imported lazily, we need to explicitly load them.
        if not settings.configured:
            settings._setup()

        user_settings = module_to_dict(settings._wrapped)
        default = options["default"]
        default_settings = module_to_dict(
            Settings(default) if default else global_settings
        )
        output_func = {
            "hash": self.output_hash,
            "unified": self.output_unified,
        }[options["output"]]
        return "\n".join(output_func(user_settings, default_settings, **options))

    def output_hash(self, user_settings, default_settings, **options):
        # Inspired by Postfix's "postconf -n".
        """
        Produces a list of key-value pairs where user settings differ from default settings.

        Parameters
        ----------
        user_settings : dict
            User-defined settings.
        default_settings : dict
            Default settings.
        **options
            Additional options, including 'all' to include unchanged settings marked as comments.

        Returns
        -------
        list
            List of settings with differences or all settings if 'all' option is specified.
        """
        output = []
        for key in sorted(user_settings):
            if key not in default_settings:
                output.append("%s = %s  ###" % (key, user_settings[key]))
            elif user_settings[key] != default_settings[key]:
                output.append("%s = %s" % (key, user_settings[key]))
            elif options["all"]:
                output.append("### %s = %s" % (key, user_settings[key]))
        return output

    def output_unified(self, user_settings, default_settings, **options):
        """
        Returns a formatted list comparing user settings with default settings.

        The output highlights differences between the two settings, including values
        that exist only in user settings and settings with different values. The
        'all' option can be used to include all settings, even if they match the
        default settings.
        """
        output = []
        for key in sorted(user_settings):
            if key not in default_settings:
                output.append(
                    self.style.SUCCESS("+ %s = %s" % (key, user_settings[key]))
                )
            elif user_settings[key] != default_settings[key]:
                output.append(
                    self.style.ERROR("- %s = %s" % (key, default_settings[key]))
                )
                output.append(
                    self.style.SUCCESS("+ %s = %s" % (key, user_settings[key]))
                )
            elif options["all"]:
                output.append("  %s = %s" % (key, user_settings[key]))
        return output
