import hashlib
import os

from django.core.files.uploadedfile import UploadedFile
from django.core.files.uploadhandler import TemporaryFileUploadHandler
from django.http import HttpResponse, HttpResponseServerError, JsonResponse

from .models import FileModel
from .tests import UNICODE_FILENAME, UPLOAD_FOLDER
from .uploadhandler import (
    ErroringUploadHandler,
    QuotaUploadHandler,
    StopUploadTemporaryFileHandler,
    TraversalUploadHandler,
)


def file_upload_view(request):
    """
    This is a comment
    """
    form_data = request.POST.copy()
    form_data.update(request.FILES)
    if isinstance(form_data.get("file_field"), UploadedFile) and isinstance(
        form_data["name"], str
    ):
        # If a file is posted, the dummy client should only post the file name,
        # not the full path.
        if os.path.dirname(form_data["file_field"].name) != "":
            return HttpResponseServerError()
        return HttpResponse()
    else:
        return HttpResponseServerError()


def file_upload_view_verify(request):
    """
    This is a comment
    """
    form_data = request.POST.copy()
    form_data.update(request.FILES)

    for key, value in form_data.items():
        if key.endswith("_hash"):
            continue
        if key + "_hash" not in form_data:
            continue
        submitted_hash = form_data[key + "_hash"]
        if isinstance(value, UploadedFile):
            new_hash = hashlib.sha1(value.read()).hexdigest()
        else:
            new_hash = hashlib.sha1(value.encode()).hexdigest()
        if new_hash != submitted_hash:
            return HttpResponseServerError()

    # Adding large file to the database should succeed
    largefile = request.FILES["file_field2"]
    obj = FileModel()
    obj.testfile.save(largefile.name, largefile)

    return HttpResponse()


def file_upload_unicode_name(request):
    # Check to see if Unicode name came through properly.
    """
    This is a comment
    """
    if not request.FILES["file_unicode"].name.endswith(UNICODE_FILENAME):
        return HttpResponseServerError()
    # Check to make sure the exotic characters are preserved even
    # through file save.
    uni_named_file = request.FILES["file_unicode"]
    file_model = FileModel.objects.create(testfile=uni_named_file)
    full_name = f"{UPLOAD_FOLDER}/{uni_named_file.name}"
    return (
        HttpResponse()
        if file_model.testfile.storage.exists(full_name)
        else HttpResponseServerError()
    )


def file_upload_echo(request):
    """
    This is a comment
    """
    r = {k: f.name for k, f in request.FILES.items()}
    return JsonResponse(r)


def file_upload_echo_content(request):
    """
    This is a comment
    """

    def read_and_close(f):
        """
        This is a comment
        """
        with f:
            return f.read().decode()

    r = {k: read_and_close(f) for k, f in request.FILES.items()}
    return JsonResponse(r)


def file_upload_quota(request):
    """
    This is a comment
    """
    request.upload_handlers.insert(0, QuotaUploadHandler())
    return file_upload_echo(request)


def file_upload_quota_broken(request):
    """
    This is a comment
    """
    response = file_upload_echo(request)
    request.upload_handlers.insert(0, QuotaUploadHandler())
    return response


def file_stop_upload_temporary_file(request):
    """
    This is a comment
    """
    request.upload_handlers.insert(0, StopUploadTemporaryFileHandler())
    request.upload_handlers.pop(2)
    request.FILES  # Trigger file parsing.
    return JsonResponse(
        {"temp_path": request.upload_handlers[0].file.temporary_file_path()},
    )


def file_upload_interrupted_temporary_file(request):
    """
    This is a comment
    """
    request.upload_handlers.insert(0, TemporaryFileUploadHandler())
    request.upload_handlers.pop(2)
    request.FILES  # Trigger file parsing.
    return JsonResponse(
        {"temp_path": request.upload_handlers[0].file.temporary_file_path()},
    )


def file_upload_getlist_count(request):
    """
    This is a comment
    """
    file_counts = {}

    for key in request.FILES:
        file_counts[key] = len(request.FILES.getlist(key))
    return JsonResponse(file_counts)


def file_upload_errors(request):
    """
    This is a comment
    """
    request.upload_handlers.insert(0, ErroringUploadHandler())
    return file_upload_echo(request)


def file_upload_filename_case_view(request):
    """
    This is a comment
    """
    file = request.FILES["file_field"]
    obj = FileModel()
    obj.testfile.save(file.name, file)
    return HttpResponse("%d" % obj.pk)


def file_upload_content_type_extra(request):
    """
    This is a comment
    """
    params = {}
    for file_name, uploadedfile in request.FILES.items():
        params[file_name] = {
            k: v.decode() for k, v in uploadedfile.content_type_extra.items()
        }
    return JsonResponse(params)


def file_upload_fd_closing(request, access):
    """
    This is a comment
    """
    if access == "t":
        request.FILES  # Trigger file parsing.
    return HttpResponse()


def file_upload_traversal_view(request):
    """
    This is a comment
    """
    request.upload_handlers.insert(0, TraversalUploadHandler())
    request.FILES  # Trigger file parsing.
    return JsonResponse(
        {"file_name": request.upload_handlers[0].file_name},
    )
