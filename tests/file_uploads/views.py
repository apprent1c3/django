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
    Handle file uploads, validating the upload and filename to prevent potential security issues. Returns a successful response if the upload is valid, otherwise returns an error response.
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
    Verifies the integrity of uploaded files by comparing the SHA-1 hashes of the file contents with the submitted hashes, and saves the uploaded file to a database model if verification succeeds.
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
    Handles file upload with unicode name in the request.

    Verifies that the uploaded file has a unicode filename, 
    saves it using the FileModel, and checks if the file was stored successfully.

    Returns an HTTP success response if the file was stored, 
    otherwise returns an HTTP server error response.
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
    Simple view to echo back info about uploaded files for tests.
    """
    r = {k: f.name for k, f in request.FILES.items()}
    return JsonResponse(r)


def file_upload_echo_content(request):
    """
    Simple view to echo back the content of uploaded files for tests. 

    It reads the content of all files provided in the request, decodes them, and returns a JSON response containing the file names as keys and their respective content as values.
    """

    def read_and_close(f):
        with f:
            return f.read().decode()

    r = {k: read_and_close(f) for k, f in request.FILES.items()}
    return JsonResponse(r)


def file_upload_quota(request):
    """
    Dynamically add in an upload handler.
    """
    request.upload_handlers.insert(0, QuotaUploadHandler())
    return file_upload_echo(request)


def file_upload_quota_broken(request):
    """
    You can't change handlers after reading FILES; this view shouldn't work.
    """
    response = file_upload_echo(request)
    request.upload_handlers.insert(0, QuotaUploadHandler())
    return response


def file_stop_upload_temporary_file(request):
    request.upload_handlers.insert(0, StopUploadTemporaryFileHandler())
    request.upload_handlers.pop(2)
    request.FILES  # Trigger file parsing.
    return JsonResponse(
        {"temp_path": request.upload_handlers[0].file.temporary_file_path()},
    )


def file_upload_interrupted_temporary_file(request):
    request.upload_handlers.insert(0, TemporaryFileUploadHandler())
    request.upload_handlers.pop(2)
    request.FILES  # Trigger file parsing.
    return JsonResponse(
        {"temp_path": request.upload_handlers[0].file.temporary_file_path()},
    )


def file_upload_getlist_count(request):
    """
    Returns a JSON response containing the count of files uploaded for each file input field in the request.
    """
    file_counts = {}

    for key in request.FILES:
        file_counts[key] = len(request.FILES.getlist(key))
    return JsonResponse(file_counts)


def file_upload_errors(request):
    request.upload_handlers.insert(0, ErroringUploadHandler())
    return file_upload_echo(request)


def file_upload_filename_case_view(request):
    """

    Checks if uploading a file preserves the original filename case by simulating the upload process and storing the file in the database.

    """
    file = request.FILES["file_field"]
    obj = FileModel()
    obj.testfile.save(file.name, file)
    return HttpResponse("%d" % obj.pk)


def file_upload_content_type_extra(request):
    """
    Echos back extra content-type parameters for uploaded files in the request. Returns a JSON response containing the extra parameters for each uploaded file.
    """
    params = {}
    for file_name, uploadedfile in request.FILES.items():
        params[file_name] = {
            k: v.decode() for k, v in uploadedfile.content_type_extra.items()
        }
    return JsonResponse(params)


def file_upload_fd_closing(request, access):
    if access == "t":
        request.FILES  # Trigger file parsing.
    return HttpResponse()


def file_upload_traversal_view(request):
    request.upload_handlers.insert(0, TraversalUploadHandler())
    request.FILES  # Trigger file parsing.
    return JsonResponse(
        {"file_name": request.upload_handlers[0].file_name},
    )
