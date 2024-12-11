from django.core.paginator import Page, Paginator


class ValidAdjacentNumsPage(Page):
    def next_page_number(self):
        if not self.has_next():
            return None
        return super().next_page_number()

    def previous_page_number(self):
        """
        Returns the page number of the previous page if it exists, otherwise returns None.

        This method checks if there is a previous page, and if so, it calls the superclass's 
        previous_page_number method to get the page number. If there is no previous page, 
        it returns None, indicating that the current page is the first one. This is 
        useful for pagination and navigation purposes.
        """
        if not self.has_previous():
            return None
        return super().previous_page_number()


class ValidAdjacentNumsPaginator(Paginator):
    def _get_page(self, *args, **kwargs):
        return ValidAdjacentNumsPage(*args, **kwargs)
