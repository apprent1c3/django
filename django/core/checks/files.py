from pathlib import Path

from django.conf import settings

from . import Error, Tags, register


@register(Tags.files)
def check_setting_file_upload_temp_dir(app_configs, **kwargs):
    """

    Checks the FILE_UPLOAD_TEMP_DIR setting for validity.

    This check verifies that the directory specified by the FILE_UPLOAD_TEMP_DIR setting exists.
    If the setting is defined but the directory does not exist, an error is raised.

    Returns:
        list: A list of errors, or an empty list if the setting is valid or undefined.

    """
    setting = getattr(settings, "FILE_UPLOAD_TEMP_DIR", None)
    if setting and not Path(setting).is_dir():
        return [
            Error(
                f"The FILE_UPLOAD_TEMP_DIR setting refers to the nonexistent "
                f"directory '{setting}'.",
                id="files.E001",
            ),
        ]
    return []
