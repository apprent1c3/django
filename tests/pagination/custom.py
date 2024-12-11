from django.core.paginator import Page, Paginator


class ValidAdjacentNumsPage(Page):
    def next_page_number(self):
        """
        ..: Returns the page number of the next page if it exists, otherwise returns None.
            The existence of a next page is determined by the :meth:`has_next` method.
            If a next page is available, the implementation is delegated to the parent class.
        """
        if not self.has_next():
            return None
        return super().next_page_number()

    def previous_page_number(self):
        """
        Returns the page number of the previous page if it exists, otherwise returns None.

        This method is used for navigation purposes, allowing you to determine the page number that comes before the current one in a paginated sequence. If there is no previous page (i.e., the current page is the first one), the method returns None, indicating that there is no previous page to navigate to.
        """
        if not self.has_previous():
            return None
        return super().previous_page_number()


class ValidAdjacentNumsPaginator(Paginator):
    def _get_page(self, *args, **kwargs):
        return ValidAdjacentNumsPage(*args, **kwargs)
