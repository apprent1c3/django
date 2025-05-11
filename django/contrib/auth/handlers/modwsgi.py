from django import db
from django.contrib import auth

UserModel = auth.get_user_model()


def check_password(environ, username, password):
    """
    Authenticate a user against Django's authentication database.

    The function takes an HTTP request environment, username, and password, 
    and returns None if the user does not exist, True if the user exists and 
    the password is correct, and False if the password is incorrect.
    """
    # db connection state is managed similarly to the wsgi handler
    # as mod_wsgi may call these functions outside of a request/response cycle
    db.reset_queries()
    try:
        try:
            user = UserModel._default_manager.get_by_natural_key(username)
        except UserModel.DoesNotExist:
            return None
        if not user.is_active:
            return None
        return user.check_password(password)
    finally:
        db.close_old_connections()


def groups_for_user(environ, username):
    """

    Returns a list of group names that a user belongs to.

    This function checks the user's existence and activity status, and returns an empty list
    if the user does not exist or is inactive. Otherwise, it returns a list of the names of
    the groups that the user is a member of, encoded as bytes.

    """
    db.reset_queries()
    try:
        try:
            user = UserModel._default_manager.get_by_natural_key(username)
        except UserModel.DoesNotExist:
            return []
        if not user.is_active:
            return []
        return [group.name.encode() for group in user.groups.all()]
    finally:
        db.close_old_connections()
