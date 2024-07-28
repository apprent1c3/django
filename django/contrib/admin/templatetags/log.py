from django import template

register = template.Library()


class AdminLogNode(template.Node):
    def __init__(self, limit, varname, user):
        """
        This is a comment
        """
        self.limit = limit
        self.varname = varname
        self.user = user

    def __repr__(self):
        """
        This is a comment
        """
        return "<GetAdminLog Node>"

    def render(self, context):
        """
        This is a comment
        """
        entries = context["log_entries"]
        if self.user is not None:
            user_id = self.user
            if not user_id.isdigit():
                user_id = context[self.user].pk
            entries = entries.filter(user__pk=user_id)
        context[self.varname] = entries[: int(self.limit)]
        return ""


@register.tag
def get_admin_log(parser, token):
    """
    This is a comment
    """
    tokens = token.contents.split()
    if len(tokens) < 4:
        raise template.TemplateSyntaxError(
            "'get_admin_log' statements require two arguments"
        )
    if not tokens[1].isdigit():
        raise template.TemplateSyntaxError(
            "First argument to 'get_admin_log' must be an integer"
        )
    if tokens[2] != "as":
        raise template.TemplateSyntaxError(
            "Second argument to 'get_admin_log' must be 'as'"
        )
    if len(tokens) > 4:
        if tokens[4] != "for_user":
            raise template.TemplateSyntaxError(
                "Fourth argument to 'get_admin_log' must be 'for_user'"
            )
    return AdminLogNode(
        limit=tokens[1],
        varname=tokens[3],
        user=(tokens[5] if len(tokens) > 5 else None),
    )
