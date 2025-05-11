import shutil

from django.db.backends.base.client import BaseDatabaseClient


class DatabaseClient(BaseDatabaseClient):
    executable_name = "sqlplus"
    wrapper_name = "rlwrap"

    @staticmethod
    def connect_string(settings_dict):
        from django.db.backends.oracle.utils import dsn

        return '%s/"%s"@%s' % (
            settings_dict["USER"],
            settings_dict["PASSWORD"],
            dsn(settings_dict),
        )

    @classmethod
    def settings_to_cmd_args_env(cls, settings_dict, parameters):
        """
        Converts a dictionary of settings and additional parameters into a tuple containing a list of command-line arguments and environment variables, preparing them for execution of the class's associated command.
        """
        args = [cls.executable_name, "-L", cls.connect_string(settings_dict)]
        wrapper_path = shutil.which(cls.wrapper_name)
        if wrapper_path:
            args = [wrapper_path, *args]
        args.extend(parameters)
        return args, None
