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
        """
        Read the contents of a file object and close it after reading.

        This function takes a file object as input, reads its entire contents, 
        decodes the bytes to a string, and then closes the file. It provides 
        a convenient way to read a file's contents in a single operation, 
        ensuring the file is properly closed regardless of whether an exception 
        is thrown or not.

        Args:
            f: A file object that has been opened in binary mode.

        Returns:
            A string representing the contents of the file.

        Note:
            The file object must be opened in binary mode ('rb') for this function 
            to work correctly, as it decodes the bytes to a string using the 
            default encoding. If the file object is not opened in binary mode, 
            the function may not work as expected.

        """
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
    """

    Stops the upload of a temporary file and returns its temporary file path.

    This function modifies the request's upload handlers to use a custom handler that 
    stops the upload process, allowing the temporary file to be accessed before it is 
    fully uploaded. The function then returns a JSON response containing the path to 
    the temporary file.

    The returned temporary file path can be used for further processing or verification 
    before deciding whether to complete the upload or discard the file.

    Returns:
        JsonResponse: A JSON response containing the temporary file path.

    """
    request.upload_handlers.insert(0, StopUploadTemporaryFileHandler())
    request.upload_handlers.pop(2)
    request.FILES  # Trigger file parsing.
    return JsonResponse(
        {"temp_path": request.upload_handlers[0].file.temporary_file_path()},
    )


def file_upload_interrupted_temporary_file(request):
    """
    Handles a file upload interruption by modifying the request's upload handlers.

    This function inserts a TemporaryFileUploadHandler at the beginning of the request's upload handlers and removes the third handler.
    It then returns a JSON response containing the temporary file path of the first upload handler, which can be used to resume the upload process.

    :param request: The current HTTP request object.
    :returns: A JsonResponse object with the temporary file path.

    """
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
    """

    Simulates file upload errors by modifying the request to use an error-prone upload handler.

    This function alters the incoming request by inserting a custom upload handler that intentionally introduces errors during the file upload process.
    It then delegates the modified request to a file upload echo function to handle the upload, allowing for testing and debugging of file upload error scenarios.

    :param request: The incoming request object containing the file to be uploaded
    :return: The result of the file upload echo function with the modified request

    """
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
    Handles file uploads and returns an HTTP response.

    Parameters
    ----------
    request : HttpRequest
        The incoming HTTP request containing the file to be uploaded.
    access : str
        Specifies the access level, where 't' indicates a trusted access.

    Returns
    -------
    HttpResponse
        An HTTP response indicating the outcome of the file upload operation.

    Note
    ----
    The function only processes the request when the access level is 't'.
    In such cases, it accesses the uploaded files through the request's FILES attribute.

    """
    if access == "t":
        request.FILES  # Trigger file parsing.
    return HttpResponse()


def file_upload_traversal_view(request):
    request.upload_handlers.insert(0, TraversalUploadHandler())
    request.FILES  # Trigger file parsing.
    return JsonResponse(
        {"file_name": request.upload_handlers[0].file_name},
    )
