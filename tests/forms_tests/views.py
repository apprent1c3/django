from django import forms
from django.http import HttpResponse
from django.template import Context, Template
from django.views.generic.edit import UpdateView

from .models import Article


class ArticleForm(forms.ModelForm):
    content = forms.CharField(strip=False, widget=forms.Textarea)

    class Meta:
        model = Article
        fields = "__all__"


class ArticleFormView(UpdateView):
    model = Article
    success_url = "/"
    form_class = ArticleForm


def form_view(request):
    """

    Renders an HTML page containing a simple form with a single FloatField.

    This view generates a basic form that accepts a floating-point number as input. 
    The form is rendered within a minimal HTML template and returned as an HTTP response.

    Request Parameters:
        request (HttpRequest): The incoming HTTP request object.

    Returns:
        HttpResponse: An HTTP response containing the rendered HTML form.

    """
    class Form(forms.Form):
        number = forms.FloatField()

    template = Template("<html>{{ form }}</html>")
    context = Context({"form": Form()})
    return HttpResponse(template.render(context))
