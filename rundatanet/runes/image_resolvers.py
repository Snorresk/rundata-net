import json
import re
import ssl
from html import unescape
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    import certifi
except ImportError:  # pragma: no cover - depends on deployment environment
    certifi = None


RAA_DOCUMENT_UUID_RE = re.compile(
    r"pub\.raa\.se/(?:visa/)?dokumentation/"
    r"(?P<uuid>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)
SORMLAND_OBJECT_RE = re.compile(
    r"sokisamlingar\.sormlandsmuseum\.se/objects/(?P<object_id>c24-\d+)/?",
    re.IGNORECASE,
)
DIGITALT_MUSEUM_RE = re.compile(
    r"digitaltmuseum\.(?:se|no|org)/(?P<dimu_code>\d+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ResolvedImage:
    provider: str
    source_url: str
    download_url: str
    thumbnail_url: str
    file_name: str
    media_type: str
    file_size: int | None
    license_url: str
    license_name: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "source_url": self.source_url,
            "download_url": self.download_url,
            "thumbnail_url": self.thumbnail_url,
            "file_name": self.file_name,
            "media_type": self.media_type,
            "file_size": self.file_size,
            "license_url": self.license_url,
            "license_name": self.license_name,
        }


class ImageResolveError(Exception):
    pass


def extract_raa_document_uuid(*urls: str) -> str:
    for url in urls:
        if not url:
            continue
        match = RAA_DOCUMENT_UUID_RE.search(url)
        if match:
            return match.group("uuid")
    return ""


def resolve_image_link(link_url: str, direct_url: str = "", timeout: int = 15) -> ResolvedImage:
    raa_uuid = extract_raa_document_uuid(link_url, direct_url)
    if raa_uuid:
        return resolve_raa_image(raa_uuid, link_url or direct_url, timeout=timeout)
    if is_sormlandsmuseum_url(link_url):
        return resolve_sormlandsmuseum_image(link_url, direct_url, timeout=timeout)
    if is_digitaltmuseum_url(link_url):
        return resolve_digitaltmuseum_image(link_url, direct_url, timeout=timeout)
    raise ImageResolveError("No resolver is available for this image source.")


def is_supported_image_source(*urls: str) -> bool:
    return bool(
        extract_raa_document_uuid(*urls)
        or any(is_sormlandsmuseum_url(url) or is_digitaltmuseum_url(url) for url in urls)
    )


def resolve_raa_image(document_uuid: str, source_url: str, timeout: int = 15) -> ResolvedImage:
    document_url = f"https://pub.raa.se/dokumentation/{document_uuid}"
    document = _fetch_json(document_url, timeout=timeout)
    resource = _choose_raa_download_resource(document)
    thumbnail_url = _get_raa_thumbnail_url(document)
    license_data = document.get("license") or {}

    return ResolvedImage(
        provider="RAÄ",
        source_url=source_url,
        download_url=resource.get("uri", ""),
        thumbnail_url=thumbnail_url,
        file_name=resource.get("fileName", ""),
        media_type=resource.get("media", ""),
        file_size=resource.get("fileSize"),
        license_url=license_data.get("license", ""),
        license_name=license_data.get("licenseName", ""),
    )


def is_sormlandsmuseum_url(url: str) -> bool:
    if not url:
        return False
    hostname = urlparse(url).hostname or ""
    return hostname == "sokisamlingar.sormlandsmuseum.se" and bool(SORMLAND_OBJECT_RE.search(url))


def resolve_sormlandsmuseum_image(link_url: str, direct_url: str = "", timeout: int = 15) -> ResolvedImage:
    page_html = fetch_url_bytes(link_url, timeout=timeout).decode("utf-8", errors="replace")
    image_url = direct_url if _is_sormlandsmuseum_fullsize_image(direct_url) else ""
    if not image_url:
        image_url = _extract_first_match(
            page_html,
            [
                r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
                r'"fifu_image_url"\s*:\s*"([^"]+)"',
                r'<img[^>]+class=["\'][^"\']*sofieBild[^"\']*["\'][^>]+src=["\']([^"\']+)["\']',
                r'<img[^>]+src=["\']([^"\']*cust\.kulturhotell\.se/c24/files/fullsize/[^"\']+)["\']',
            ],
        )
    if not image_url:
        raise ImageResolveError("No downloadable Sörmlands museum image resource was found.")

    image_url = unescape(image_url).replace("\\/", "/")
    image_url = urljoin(link_url, image_url)
    file_name = _filename_from_url(image_url) or "sormlandsmuseum-image.jpg"
    license_url = _extract_first_match(
        page_html,
        [
            r'<a[^>]+href=["\']([^"\']*creativecommons\.org/[^"\']+)["\'][^>]*>\s*Public Domain',
            r'<a[^>]+href=["\']([^"\']*creativecommons\.org/[^"\']+)["\'][^>]*>[^<]*Licens',
            r'href=["\']([^"\']*creativecommons\.org/[^"\']+)["\']',
        ],
    )
    license_url = unescape(license_url).replace("\\/", "/")

    return ResolvedImage(
        provider="Sörmlands museum",
        source_url=link_url,
        download_url=image_url,
        thumbnail_url=direct_url or image_url,
        file_name=file_name,
        media_type=_media_type_from_filename(file_name),
        file_size=None,
        license_url=license_url,
        license_name=_license_name_from_url(license_url),
    )


def is_digitaltmuseum_url(url: str) -> bool:
    return bool(url and DIGITALT_MUSEUM_RE.search(url))


def resolve_digitaltmuseum_image(link_url: str, direct_url: str = "", timeout: int = 15) -> ResolvedImage:
    page_html = fetch_url_bytes(link_url, timeout=timeout).decode("utf-8", errors="replace")
    download_url = _extract_first_match(
        page_html,
        [
            r'<a[^>]+download[^>]+href=["\']([^"\']*ems\.dimu\.org/image/[^"\']*dimension=max[^"\']*)["\']',
            r'href=["\']([^"\']*ems\.dimu\.org/image/[^"\']*dimension=max[^"\']*)["\'][^>]+download',
        ],
    )
    if not download_url:
        dms_url = _extract_first_match(page_html, [r'"dms_url"\s*:\s*"([^"]+)"'])
        if dms_url:
            download_url = dms_url.replace("\\/", "/") + "?dimension=max&quality=100"
    if not download_url:
        download_url = _extract_first_match(
            page_html,
            [
                r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
                r'<img[^>]+src=["\']([^"\']*ems\.dimu\.org/image/[^"\']+)["\']',
            ],
        )
    if not download_url:
        raise ImageResolveError("No downloadable Digitalt museum image resource was found.")

    download_url = unescape(download_url).replace("&amp;", "&")
    download_url = urljoin(link_url, download_url)
    thumbnail_url = direct_url or _extract_first_match(
        page_html,
        [r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']'],
    )
    thumbnail_url = unescape(thumbnail_url).replace("&amp;", "&")
    file_name = _extract_first_match(download_url, [r"[?&]filename=([^&]+)"])
    if not file_name:
        file_name = _filename_from_url(download_url) or "digitaltmuseum-image.jpg"
    license_url = _extract_first_match(
        page_html,
        [r'href=["\']([^"\']*creativecommons\.org/[^"\']+)["\']'],
    )
    license_label = _extract_first_match(
        page_html,
        [r'"label"\s*:\s*"([^"]+)"', r'<b class="meta__label">License</b>\s*<a[^>]*>\s*([^<]+)'],
    )

    return ResolvedImage(
        provider="Digitalt museum",
        source_url=link_url,
        download_url=download_url,
        thumbnail_url=thumbnail_url,
        file_name=file_name,
        media_type=_media_type_from_filename(file_name),
        file_size=None,
        license_url=unescape(license_url).replace("\\/", "/"),
        license_name=unescape(license_label).strip() or _license_name_from_url(license_url),
    )
def _fetch_json(url: str, timeout: int = 15) -> dict[str, Any]:
    try:
        return json.loads(fetch_url_bytes(url, timeout=timeout).decode("utf-8"))
    except json.JSONDecodeError as error:
        raise ImageResolveError(f"Could not read image metadata from {url}.") from error


def fetch_url_bytes(url: str, timeout: int = 30) -> bytes:
    request = Request(url, headers={"User-Agent": "Rundata-net image export"})
    ssl_context = ssl.create_default_context(cafile=certifi.where() if certifi else None)
    try:
        with urlopen(request, timeout=timeout, context=ssl_context) as response:
            return response.read()
    except (HTTPError, URLError, TimeoutError) as error:
        raise ImageResolveError(f"Could not read image data from {url}.") from error


def _choose_raa_download_resource(document: dict[str, Any]) -> dict[str, Any]:
    resources = [
        resource
        for group in document.get("resourceGroups", [])
        for resource in group.get("resources", [])
        if resource.get("uri") and resource.get("fileName") != "thumbnail.png"
    ]
    for preferred_format in ("visning", "original", "arkivbestandig"):
        for resource in resources:
            if resource.get("format") == preferred_format and resource.get("media", "").startswith("image/"):
                return resource
    raise ImageResolveError("No downloadable RAÄ image resource was found.")


def _get_raa_thumbnail_url(document: dict[str, Any]) -> str:
    for group in document.get("resourceGroups", []):
        thumbnail_url = group.get("presentationThumbnailUrl")
        if thumbnail_url:
            return thumbnail_url
    return ""


def _extract_first_match(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def _is_sormlandsmuseum_fullsize_image(url: str) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.hostname == "cust.kulturhotell.se" and "/c24/files/fullsize/" in parsed.path


def _filename_from_url(url: str) -> str:
    path = urlparse(url).path
    filename = path.rsplit("/", 1)[-1]
    return filename if "." in filename else ""


def _media_type_from_filename(filename: str) -> str:
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension in {"jpg", "jpeg"}:
        return "image/jpeg"
    if extension == "png":
        return "image/png"
    if extension in {"tif", "tiff"}:
        return "image/tiff"
    return "application/octet-stream"


def _license_name_from_url(license_url: str) -> str:
    if "publicdomain/mark" in license_url:
        return "Public Domain Mark"
    if "creativecommons.org/licenses/by/4.0" in license_url:
        return "CC-BY 4.0"
    return ""
