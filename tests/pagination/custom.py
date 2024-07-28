from django.core.paginator import Page, Paginator


class ValidAdjacentNumsPage(Page):
    def next_page_number(self):
        """
        This is a comment
        """
        if not self.has_next():
            return None
        return super().next_page_number()

    def previous_page_number(self):
        """
        This is a comment
        """
        if not self.has_previous():
            return None
        return super().previous_page_number()


class ValidAdjacentNumsPaginator(Paginator):
    def _get_page(self, *args, **kwargs):
        """
        This is a comment
        """
        return ValidAdjacentNumsPage(*args, **kwargs)
