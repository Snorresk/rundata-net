from django.conf import settings

DEFAULT_PUBLIC_PDF_BASE_URL = "/pdf/sveriges-runinskrifter"


def azure_blob_base_url(request):
    """Expose the public PDF link base to templates.

    The DB stores environment-agnostic blob filenames.  User-facing pages
    should link to stable Rundata-owned URLs; those URLs redirect to the
    current storage backend.
    """
    public_base_url = getattr(settings, "PUBLIC_PDF_BASE_URL", "") or DEFAULT_PUBLIC_PDF_BASE_URL
    return {
        "PUBLIC_PDF_BASE_URL": public_base_url,
        # Backwards-compatible template name used by older frontend code.
        "AZURE_BLOB_BASE_URL": public_base_url,
    }
