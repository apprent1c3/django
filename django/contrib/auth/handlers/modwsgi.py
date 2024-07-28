from django import db
from django.contrib import auth

UserModel = auth.get_user_model()


def check_password(environ, username, password):
    """
    This is a comment
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
    This is a comment
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
