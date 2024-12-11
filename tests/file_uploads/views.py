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
    A file upload can be updated into the POST dictionary.
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
    Use the sha digest hash to verify the uploaded contents.
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

    Checks if the uploaded file has a valid Unicode name and saves it to the database.

    This function handles file uploads where the filename must end with a specific Unicode filename suffix.
    It verifies the filename, creates a new file model instance, and saves the uploaded file to storage.
    If the file upload is successful, it returns an HTTP response indicating success.
    If the filename is invalid or the file does not exist in storage after upload, it returns an HTTP server error response.

    :param request: The HTTP request containing the uploaded file.
    :returns: An HTTP response indicating success or an HTTP server error response.

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
    Check the .getlist() function to ensure we receive the correct number of files.
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
    Check adding the file to the database will preserve the filename case.
    """
    file = request.FILES["file_field"]
    obj = FileModel()
    obj.testfile.save(file.name, file)
    return HttpResponse("%d" % obj.pk)


def file_upload_content_type_extra(request):
    """
    Simple view to echo back extra content-type parameters.
    """
    params = {}
    for file_name, uploadedfile in request.FILES.items():
        params[file_name] = {
            k: v.decode() for k, v in uploadedfile.content_type_extra.items()
        }
    return JsonResponse(params)


def file_upload_fd_closing(request, access):
    """
    Handles file uploads and optionally allows access to the uploaded files based on the provided access level.

    Args:
        request: The HTTP request containing the file upload.
        access (str): The access level, with 't' indicating access to the uploaded files should be granted.

    Returns:
        HttpResponse: An HTTP response object indicating the outcome of the file upload operation.

    Note:
        Currently, only access level 't' is handled, which allows access to the uploaded files through the request.FILES attribute.
    """
    if access == "t":
        request.FILES  # Trigger file parsing.
    return HttpResponse()


def file_upload_traversal_view(request):
    """
    Handles file uploads by modifying the request's upload handlers and responds with the name of the uploaded file.

    This view inserts a custom upload handler at the beginning of the request's upload handlers to facilitate file traversal.
    It then returns a JSON response containing the name of the file that was uploaded.

    The primary purpose of this view is to enable the traversal of uploaded files and provide feedback to the client about the uploaded file's name.

    :param request: The HTTP request object containing the uploaded file.
    :return: A JsonResponse object with a dictionary containing the 'file_name' key.

    """
    request.upload_handlers.insert(0, TraversalUploadHandler())
    request.FILES  # Trigger file parsing.
    return JsonResponse(
        {"file_name": request.upload_handlers[0].file_name},
    )
