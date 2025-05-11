import datetime


def _get_duration_components(duration):
    """
    Breaks down a duration into its constituent time components.

    :param duration: A duration object
    :return: A tuple containing days, hours, minutes, seconds, and microseconds
    :rtype: tuple[int, int, int, int, int]
    """
    days = duration.days
    seconds = duration.seconds
    microseconds = duration.microseconds

    minutes = seconds // 60
    seconds %= 60

    hours = minutes // 60
    minutes %= 60

    return days, hours, minutes, seconds, microseconds


def duration_string(duration):
    """Version of str(timedelta) which is not English specific."""
    days, hours, minutes, seconds, microseconds = _get_duration_components(duration)

    string = "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)
    if days:
        string = "{} ".format(days) + string
    if microseconds:
        string += ".{:06d}".format(microseconds)

    return string


def duration_iso_string(duration):
    """

    Formats a time duration into an ISO 8601 duration string.

    Args:
        duration: A time duration, represented as a datetime.timedelta object.

    Returns:
        A string representing the duration in ISO 8601 format (e.g., \"P3DT12H30M45S\").

    """
    if duration < datetime.timedelta(0):
        sign = "-"
        duration *= -1
    else:
        sign = ""

    days, hours, minutes, seconds, microseconds = _get_duration_components(duration)
    ms = ".{:06d}".format(microseconds) if microseconds else ""
    return "{}P{}DT{:02d}H{:02d}M{:02d}{}S".format(
        sign, days, hours, minutes, seconds, ms
    )


def duration_microseconds(delta):
    return (24 * 60 * 60 * delta.days + delta.seconds) * 1000000 + delta.microseconds
