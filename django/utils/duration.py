import datetime


def _get_duration_components(duration):
    """
    Break down a duration into its constituent time components.

    Returns a tuple containing the number of days, hours, minutes, seconds, and microseconds in the given duration.
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
    """
    Returns a string representation of a duration that is not specific to the English language, providing a format that includes days, hours, minutes, seconds, and microseconds.
    """
    days, hours, minutes, seconds, microseconds = _get_duration_components(duration)

    string = "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)
    if days:
        string = "{} ".format(days) + string
    if microseconds:
        string += ".{:06d}".format(microseconds)

    return string


def duration_iso_string(duration):
    """
    Returns a duration as an ISO 8601 duration string.

    The duration is formatted as 'PnDTnHnMnS', where 'n' represents the number of days, hours, minutes, and seconds.
    If the duration is negative, the string is prefixed with a minus sign.
    The function preserves microseconds accuracy by appending them to the seconds, if present.
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
