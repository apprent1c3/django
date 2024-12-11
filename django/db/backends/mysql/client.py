import signal

from django.db.backends.base.client import BaseDatabaseClient


class DatabaseClient(BaseDatabaseClient):
    executable_name = "mysql"

    @classmethod
    def settings_to_cmd_args_env(cls, settings_dict, parameters):
        args = [cls.executable_name]
        env = None
        database = settings_dict["OPTIONS"].get(
            "database",
            settings_dict["OPTIONS"].get("db", settings_dict["NAME"]),
        )
        user = settings_dict["OPTIONS"].get("user", settings_dict["USER"])
        password = settings_dict["OPTIONS"].get(
            "password",
            settings_dict["OPTIONS"].get("passwd", settings_dict["PASSWORD"]),
        )
        host = settings_dict["OPTIONS"].get("host", settings_dict["HOST"])
        port = settings_dict["OPTIONS"].get("port", settings_dict["PORT"])
        server_ca = settings_dict["OPTIONS"].get("ssl", {}).get("ca")
        client_cert = settings_dict["OPTIONS"].get("ssl", {}).get("cert")
        client_key = settings_dict["OPTIONS"].get("ssl", {}).get("key")
        defaults_file = settings_dict["OPTIONS"].get("read_default_file")
        charset = settings_dict["OPTIONS"].get("charset")
        # Seems to be no good way to set sql_mode with CLI.

        if defaults_file:
            args += ["--defaults-file=%s" % defaults_file]
        if user:
            args += ["--user=%s" % user]
        if password:
            # The MYSQL_PWD environment variable usage is discouraged per
            # MySQL's documentation due to the possibility of exposure through
            # `ps` on old Unix flavors but --password suffers from the same
            # flaw on even more systems. Usage of an environment variable also
            # prevents password exposure if the subprocess.run(check=True) call
            # raises a CalledProcessError since the string representation of
            # the latter includes all of the provided `args`.
            env = {"MYSQL_PWD": password}
        if host:
            if "/" in host:
                args += ["--socket=%s" % host]
            else:
                args += ["--host=%s" % host]
        if port:
            args += ["--port=%s" % port]
        if server_ca:
            args += ["--ssl-ca=%s" % server_ca]
        if client_cert:
            args += ["--ssl-cert=%s" % client_cert]
        if client_key:
            args += ["--ssl-key=%s" % client_key]
        if charset:
            args += ["--default-character-set=%s" % charset]
        if database:
            args += [database]
        args.extend(parameters)
        return args, env

    def runshell(self, parameters):
        """

        Runs a shell with the specified parameters, temporarily ignoring interrupt signals.

        This method executes a shell with the given parameters, while catching and ignoring any interrupt signals (SIGINT) that may be raised during execution. 
        After the shell operation is complete, the original signal handling behavior is restored, ensuring that the program's default interrupt handling is preserved.

        Parameters
        ----------
        parameters : 
            Parameters to be passed to the shell.

        Note
        ----
        This method modifies the signal handling behavior of the program during its execution, but reverts to the original behavior after completion. 

        """
        sigint_handler = signal.getsignal(signal.SIGINT)
        try:
            # Allow SIGINT to pass to mysql to abort queries.
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            super().runshell(parameters)
        finally:
            # Restore the original SIGINT handler.
            signal.signal(signal.SIGINT, sigint_handler)
