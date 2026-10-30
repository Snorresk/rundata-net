"""Cooperative export cancellation, shared by workers on the same host."""
import json
import tempfile
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
from uuid import UUID

from django.core.cache.backends.filebased import FileBasedCache
from django.http import JsonResponse

_cancelled = FileBasedCache(str(Path(tempfile.gettempdir()) / 'rundata-image-export-cancellation'), {
    'TIMEOUT': 3600, 'OPTIONS': {'MAX_ENTRIES': 10000},
})
_current_export = ContextVar('current_image_export', default=None)


class ImageExportCancelled(Exception):
    pass


def valid_export_id(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return None


def cancel_export(export_id):
    _cancelled.set(export_id, True)


def check_export_cancelled():
    export_id = _current_export.get()
    if export_id and _cancelled.get(export_id):
        raise ImageExportCancelled()


def cancellable_image_export(view):
    @wraps(view)
    def wrapped(request):
        try:
            payload = json.loads(request.body)
            export_id = valid_export_id(payload.get('export_id')) if isinstance(payload, dict) else None
        except (ValueError, UnicodeDecodeError):
            export_id = None
        token = _current_export.set(export_id)
        try:
            check_export_cancelled()
            return view(request)
        except ImageExportCancelled:
            return JsonResponse({'ok': False, 'cancelled': True}, status=409)
        finally:
            _current_export.reset(token)
    return wrapped
