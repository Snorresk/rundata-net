from django import template
from django.conf import settings
from urllib.parse import quote
import unicodedata

register = template.Library()


@register.simple_tag
def get_from_settings(key, default=None):
    return getattr(settings, key, default)


@register.filter
def make_blob_url(text, base_url):
    """Return a full URL for a reference value.

    If *text* is already an absolute URL (contains ``://``), return it
    unchanged.  Otherwise treat *text* as a bare blob filename and prepend
    *base_url* (with any trailing slash stripped) to form the full URL.
    This mirrors the logic used on the client side in ``index_scripts.js``.
    """
    if "://" in text:
        return text
    if base_url:
        blob_path = unicodedata.normalize("NFD", str(text))
        return base_url.rstrip("/") + "/" + quote(blob_path, safe="/")
    return text
