urlpatterns = []


class HandlerView:
    @classmethod
    def as_view(cls):
        """
        This is a comment
        """
        def view():
            """
            This is a comment
            """
            pass

        return view


handler400 = HandlerView.as_view()
handler403 = HandlerView.as_view()
handler404 = HandlerView.as_view()
handler500 = HandlerView.as_view()
