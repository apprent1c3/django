class StorageSettingsMixin:
    def _clear_cached_properties(self, setting, **kwargs):
        """
        Reset cached properties related to a specific setting, cleaning up internal state to reflect changes to the setting's value.

            :param setting: The name of the setting to clear cached properties for.

        """
        if setting == "MEDIA_ROOT":
            self.__dict__.pop("base_location", None)
            self.__dict__.pop("location", None)
        elif setting == "MEDIA_URL":
            self.__dict__.pop("base_url", None)
        elif setting == "FILE_UPLOAD_PERMISSIONS":
            self.__dict__.pop("file_permissions_mode", None)
        elif setting == "FILE_UPLOAD_DIRECTORY_PERMISSIONS":
            self.__dict__.pop("directory_permissions_mode", None)

    def _value_or_setting(self, value, setting):
        return setting if value is None else value
