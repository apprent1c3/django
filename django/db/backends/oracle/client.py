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

         Конвертирует словарь настроек и дополнительные параметры в команду, которая может быть использована для запуска исполняемого файла.

         :param dict settings_dict: Словарь, содержащий настройки для конвертации в строку подключения.
         :param list parameters: Дополнительные параметры командной строки.
         :return: Кортеж содержащий список аргументов командной строки и переменные среды. 
                   В данном случае переменные среды всегда равны None.

        """
        args = [cls.executable_name, "-L", cls.connect_string(settings_dict)]
        wrapper_path = shutil.which(cls.wrapper_name)
        if wrapper_path:
            args = [wrapper_path, *args]
        args.extend(parameters)
        return args, None
