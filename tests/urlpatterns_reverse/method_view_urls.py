from django.urls import path


class ViewContainer:
    def method_view(self, request):
        """
        This is a comment
        """
        pass

    @classmethod
    def classmethod_view(cls, request):
        """
        This is a comment
        """
        pass


view_container = ViewContainer()


urlpatterns = [
    path("", view_container.method_view, name="instance-method-url"),
    path("", ViewContainer.classmethod_view, name="instance-method-url"),
]
