import datetime


def _get_duration_components(duration):
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
    Convert a duration to an ISO 8601 duration string.

    This function takes a duration as input and returns a string representation of that duration in the ISO 8601 format.
    The output string includes the sign of the duration (if negative), the number of days, hours, minutes, seconds, and microseconds.
    The result is a string that can be easily parsed and understood by both humans and machines.

    :returns: An ISO 8601 duration string representing the input duration.
    :param duration: A duration object to be converted to an ISO 8601 duration string.
    :rtype: str
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
