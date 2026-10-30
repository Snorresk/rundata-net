import json
from .image_export_control import check_export_cancelled
import re
import ssl
from html import unescape
from html.parser import HTMLParser
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlencode, urljoin, urlparse
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
SHM_UUID_PATTERN = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


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
    creator: str = ""

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
            "creator": self.creator,
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
    if is_runer_ku_url(link_url) or is_runer_ku_url(direct_url):
        return resolve_runer_ku_image(link_url, direct_url)
    if is_arild_hauge_url(link_url) or is_arild_hauge_url(direct_url):
        return resolve_arild_hauge_image(link_url, direct_url)
    if is_shm_url(link_url):
        return resolve_shm_image(link_url, direct_url, timeout=timeout)
    if extract_commons_file_title(link_url):
        return resolve_commons_image(link_url, timeout=timeout)
    if is_blekinge_museum_url(link_url):
        return resolve_blekinge_museum_image(link_url, direct_url, timeout=timeout)
    if is_jamtland_museum_url(link_url):
        return resolve_jamtland_museum_image(link_url, direct_url, timeout=timeout)
    if is_shfa_url(link_url):
        return resolve_shfa_image(link_url, direct_url, timeout=timeout)
    raise ImageResolveError("No resolver is available for this image source.")


def is_supported_image_source(*urls: str) -> bool:
    return bool(
        extract_raa_document_uuid(*urls)
        or any(
            is_sormlandsmuseum_url(url) or is_digitaltmuseum_url(url)
            or is_runer_ku_url(url) or is_arild_hauge_url(url)
            or is_shm_url(url)
            or bool(extract_commons_file_title(url))
            or is_blekinge_museum_url(url)
            or is_jamtland_museum_url(url)
            or is_shfa_url(url)
            for url in urls
        )
    )


def is_shfa_url(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme in {"http", "https"}
        and parsed.hostname == "shfa.dh.gu.se"
        and bool(re.fullmatch(r"/image/\d+/?", parsed.path))
    )


def _shfa_file_name(url: str, legacy: bool = False) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname != "data.dh.gu.se":
        return ""
    prefix = r"/(?:shfa|diana)/static/shfa/original/" if legacy else r"/shfa/static/shfa/original/"
    match = re.fullmatch(prefix + r"(\d+\.(?:jpe?g|png|tiff?))", parsed.path, re.I)
    return match[1] if match and not parsed.query and not parsed.fragment else ""


def resolve_shfa_image(link_url: str, direct_url: str = "", timeout: int = 15) -> ResolvedImage:
    image_id = int(urlparse(link_url).path.strip("/").split("/")[-1])
    document = _fetch_json(f"https://shfa.dh.gu.se/api/image/?id={image_id}&depth=1", timeout=timeout)
    results = document.get("results") if isinstance(document, dict) else None
    if not isinstance(results, list) or len(results) != 1 or not isinstance(results[0], dict):
        raise ImageResolveError("No SHFA image resource was found.")
    image = results[0]
    if image.get("id") != image_id or image.get("published") is not True:
        raise ImageResolveError("No matching published SHFA image resource was found.")
    download_url = image.get("file")
    filename = _shfa_file_name(download_url) if isinstance(download_url, str) else ""
    if not filename:
        raise ImageResolveError("No downloadable SHFA original image was found.")
    if direct_url and _shfa_file_name(direct_url, legacy=True) != filename:
        raise ImageResolveError("The selected SHFA image does not match the source image.")
    people = image.get("people")
    names = [person["name"].strip() for person in people
             if isinstance(person, dict) and isinstance(person.get("name"), str) and person["name"].strip()] if isinstance(people, list) else []
    author = image.get("author")
    if not names and isinstance(author, dict) and isinstance(author.get("name"), str):
        names = [author["name"].strip()]
    # SHFA's /about page explicitly licenses the archive's images under CC BY 4.0.
    return ResolvedImage(
        provider="SHFA", source_url=link_url, download_url=download_url,
        thumbnail_url=download_url, file_name=filename,
        media_type=_media_type_from_filename(filename), file_size=None,
        license_url="https://creativecommons.org/licenses/by/4.0/",
        license_name="CC BY 4.0", creator="; ".join(dict.fromkeys(names)),
    )


def is_blekinge_museum_url(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme in {"https", "http"}
        and parsed.hostname == "blm.kulturhotell.se"
        and bool(re.fullmatch(r"/objects/c32-\d+/?", parsed.path))
    )


def _blekinge_image_url(url: str, fullsize: bool = False) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    prefix = "/c32/files/" if parsed.hostname == "cust.kulturhotell.se" else "/files/"
    if parsed.hostname not in {"blm.kulturhotell.se", "cust.kulturhotell.se"}:
        return False
    sizes = "(?:fullsize|original)" if fullsize else "(?:fullsize|original|thumbnails|square_thumbnails)"
    return bool(re.fullmatch(re.escape(prefix) + sizes + r"/[^/]+\.(?:jpe?g|png|gif|tiff?)", parsed.path, re.I))


def is_jamtland_museum_url(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme in {"http", "https"}
        and parsed.hostname == "jlm.kulturhotell.se"
        and bool(re.fullmatch(r"/items/show/\d+/?", parsed.path))
    )


def _jamtland_image_url(url: str, fullsize: bool = False) -> bool:
    parsed = urlparse(url)
    sizes = "(?:fullsize|original)" if fullsize else "(?:fullsize|original|thumbnails|square_thumbnails)"
    return (
        parsed.scheme in {"http", "https"}
        and parsed.hostname == "jlm.kulturhotell.se"
        and bool(re.fullmatch(r"/files/" + sizes + r"/[^/]+\.(?:jpe?g|png|gif|tiff?)", parsed.path, re.I))
    )


class _KulturhotellPageParser(HTMLParser):
    def __init__(self, source_url, image_url_check):
        super().__init__()
        self.source_url = source_url
        self.image_url_check = image_url_check
        self.images = []
        self.license_url = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        value = attrs.get("href") if tag == "a" else attrs.get("src") if tag == "img" else (
            attrs.get("content") if tag == "meta" and attrs.get("property") == "og:image" else ""
        )
        url = urljoin(self.source_url, value or "")
        if self.image_url_check(url, fullsize=True) and url not in self.images:
            self.images.append(url)
        if tag == "a" and urlparse(url).hostname == "creativecommons.org":
            self.license_url = url


def resolve_blekinge_museum_image(link_url: str, direct_url: str = "", timeout: int = 15) -> ResolvedImage:
    return _resolve_kulturhotell_image(link_url, direct_url, "Blekinge museum", _blekinge_image_url, timeout)


def resolve_jamtland_museum_image(link_url: str, direct_url: str = "", timeout: int = 15) -> ResolvedImage:
    return _resolve_kulturhotell_image(link_url, direct_url, "Jämtlands läns museum", _jamtland_image_url, timeout)


def _resolve_kulturhotell_image(link_url, direct_url, provider, image_url_check, timeout):
    # Never guess a fullsize URL from a thumbnail, or substitute another photo.
    page = _KulturhotellPageParser(link_url, image_url_check)
    page.feed(fetch_url_bytes(link_url, timeout=timeout).decode("utf-8", errors="replace"))
    if image_url_check(direct_url):
        selected_name = unquote(_filename_from_url(direct_url))
        candidates = [url for url in page.images if unquote(_filename_from_url(url)) == selected_name]
    elif direct_url:
        candidates = []
    else:
        candidates = page.images if len(page.images) == 1 else []
    if not candidates:
        raise ImageResolveError(f"No verified fullsize {provider} image was found for the selected image.")
    image_url = candidates[0]
    license_url = page.license_url
    license_match = re.fullmatch(r"/licenses/([a-z-]+)/([0-9.]+)/?(?:deed\.[a-z-]+)?", urlparse(license_url).path)
    license_name = (
        f"CC {license_match[1].upper()} {license_match[2]}" if license_match
        else _license_name_from_url(license_url)
    )
    return ResolvedImage(
        provider=provider, source_url=link_url,
        download_url=image_url, thumbnail_url=direct_url or image_url,
        file_name=_filename_from_url(image_url),
        media_type=_media_type_from_filename(_filename_from_url(image_url)),
        file_size=None, license_url=license_url, license_name=license_name,
    )


def extract_commons_file_title(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname != "commons.wikimedia.org":
        return ""
    if parsed.path.startswith("/wiki/"):
        title = unquote(parsed.path[len("/wiki/"):])
    elif parsed.path == "/w/index.php":
        title = parse_qs(parsed.query).get("title", [""])[0]
    else:
        return ""
    if not title.startswith("File:") or not title[5:].strip() or re.search(r"[|#\[\]{}\r\n]", title):
        return ""
    return title.replace("_", " ")


def _commons_image_url(url: str, thumbnail: bool = False) -> str:
    parsed = urlparse(url)
    hosts = {"upload.wikimedia.org", "thumb.wikimedia.org"} if thumbnail else {"upload.wikimedia.org"}
    if parsed.scheme not in {"https", "http"} or parsed.hostname not in hosts or not parsed.path.startswith("/wikipedia/commons/"):
        return ""
    return quote(url, safe=":/?&=%+#")


def _plain_metadata(value: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]*>", " ", value)).split())


def resolve_commons_image(link_url: str, timeout: int = 15) -> ResolvedImage:
    title = extract_commons_file_title(link_url)
    params = urlencode({
        "action": "query", "format": "json", "formatversion": 2,
        "prop": "imageinfo", "titles": title, "redirects": 1,
        "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 320,
        "iiextmetadatafilter": "Artist|Attribution|LicenseShortName|LicenseUrl|UsageTerms",
        "maxlag": 5,
    })
    document = _fetch_json(f"https://commons.wikimedia.org/w/api.php?{params}", timeout=timeout)
    if not isinstance(document, dict) or document.get("error"):
        raise ImageResolveError("Wikimedia Commons image metadata is temporarily unavailable.")
    pages = (document.get("query") or {}).get("pages") or []
    if isinstance(pages, dict):
        pages = list(pages.values())
    if not isinstance(pages, list) or len(pages) != 1 or not isinstance(pages[0], dict):
        raise ImageResolveError("No Wikimedia Commons image resource was found.")
    if "missing" in pages[0] or pages[0].get("ns") != 6 or not pages[0].get("imageinfo"):
        raise ImageResolveError("No Wikimedia Commons image resource was found.")
    page = pages[0]
    image = page["imageinfo"][0]
    media_type = image.get("mime", "")
    download_url = _commons_image_url(image.get("url", ""))
    if not download_url or not media_type.startswith("image/"):
        raise ImageResolveError("No downloadable Wikimedia Commons image resource was found.")
    metadata = image.get("extmetadata") or {}

    def value(key):
        return _plain_metadata(str((metadata.get(key) or {}).get("value") or ""))

    license_url = value("LicenseUrl")
    if license_url.startswith("//"):
        license_url = "https:" + license_url
    if urlparse(license_url).scheme not in {"http", "https"}:
        license_url = ""
    size = image.get("size")
    return ResolvedImage(
        provider="Wikimedia Commons",
        source_url=link_url,
        download_url=download_url,
        thumbnail_url=_commons_image_url(image.get("thumburl", ""), thumbnail=True) or download_url,
        file_name=(page.get("title") or title).removeprefix("File:"),
        media_type=media_type,
        file_size=size if isinstance(size, int) and size >= 0 else None,
        license_url=license_url,
        license_name=value("LicenseShortName") or value("UsageTerms"),
        creator=value("Artist") or value("Attribution"),
    )


def is_shm_url(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme in {"http", "https"}
        and parsed.hostname == "samlingar.shm.se"
        and bool(re.fullmatch(rf"/(?:object|media)/{SHM_UUID_PATTERN}/?", parsed.path, re.I))
    )


def _shm_image_id(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname != "media.samlingar.shm.se":
        return ""
    match = re.fullmatch(rf"/item/({SHM_UUID_PATTERN})(?:/(?:thumbnail|small|medium|large))?/?", parsed.path, re.I)
    return match[1].lower() if match else ""


class _ShmPageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []
        self.downloads = []
        self.image_url = ""
        self.fields = {}
        self.license_slug = ""
        self._cell = ""
        self._header = ""
        self._text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for key in ("href", "src", "content", "data-url"):
            if attrs.get(key):
                self.urls.append(attrs[key])
        if tag == "meta" and attrs.get("property") == "og:image":
            self.image_url = attrs.get("content", "")
        if tag == "a" and "download" in attrs and attrs.get("href"):
            self.downloads.append(attrs["href"])
        if tag in {"th", "td"}:
            self._cell = tag
            self._text = []
        if self._cell == "td" and self._header == "Licens för media":
            match = re.search(r"\blicense-icon-collection--([\w-]+)", attrs.get("class", ""))
            if match:
                self.license_slug = match[1]

    def handle_data(self, data):
        if self._cell:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == self._cell:
            value = " ".join(" ".join(self._text).split())
            if tag == "th":
                self._header = value
            else:
                self.fields[self._header] = value
            self._cell = ""


def resolve_shm_image(link_url: str, direct_url: str = "", timeout: int = 15) -> ResolvedImage:
    source = _ShmPageParser()
    source.feed(fetch_url_bytes(link_url, timeout=timeout).decode("utf-8", errors="replace"))
    if "/object/" in urlparse(link_url).path:
        image_id = _shm_image_id(direct_url or source.image_url)
        if not image_id or image_id not in {_shm_image_id(url) for url in source.urls}:
            raise ImageResolveError("The selected SHM image is not attached to this object.")
        media = _ShmPageParser()
        media.feed(fetch_url_bytes(f"https://samlingar.shm.se/media/{image_id}", timeout=timeout).decode("utf-8", errors="replace"))
    else:
        image_id = urlparse(link_url).path.rstrip("/").rsplit("/", 1)[-1].lower()
        if direct_url and _shm_image_id(direct_url) != image_id:
            raise ImageResolveError("The selected SHM image does not match the media page.")
        media = source
    download_url = next((url for url in media.downloads if _shm_image_id(url) == image_id
                         and urlparse(url).path.rstrip("/").lower() == f"/item/{image_id}"), "")
    media_type = media.fields.get("Mediatyp", "").lower()
    file_size = None
    if download_url and not media_type:
        # Some SHM media pages omit Mediatyp; read the original's HTTP metadata.
        request = Request(download_url, method="HEAD", headers={"User-Agent": "Rundata-net image export"})
        ssl_context = ssl.create_default_context(cafile=certifi.where() if certifi else None)
        try:
            with urlopen(request, timeout=timeout, context=ssl_context) as response:
                media_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                length = response.headers.get("Content-Length", "")
                file_size = int(length) if length.isdecimal() else None
        except (HTTPError, URLError, TimeoutError) as error:
            raise ImageResolveError("Could not read SHM image metadata.") from error
    extensions = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/tiff": "tif", "image/webp": "webp"}
    if not download_url or media_type not in extensions:
        raise ImageResolveError("No downloadable SHM image resource was found.")
    slug = media.license_slug
    license_url = ""
    license_name = media.fields.get("Licens för media", "")
    match = re.fullmatch(r"cc-(by(?:-nc)?(?:-nd|-sa)?)-(\d+)_(\d+)", slug)
    if match:
        version = f"{match[2]}.{match[3]}"
        license_name = f"CC {match[1].upper()} {version}"
        license_url = f"https://creativecommons.org/licenses/{match[1]}/{version}/"
    elif slug in {"cc0", "cc0-1_0", "pdm", "public-domain", "public-domain-mark"}:
        zero = slug.startswith("cc0")
        license_name = "CC0 1.0" if zero else "Public Domain Mark"
        license_url = f"https://creativecommons.org/publicdomain/{'zero' if zero else 'mark'}/1.0/"
    return ResolvedImage(
        provider="SHM",
        source_url=link_url,
        download_url=download_url,
        thumbnail_url=direct_url or f"https://media.samlingar.shm.se/item/{image_id}/thumbnail",
        file_name=f"shm-{image_id}.{extensions[media_type]}",
        media_type=media_type,
        file_size=file_size,
        license_url=license_url,
        license_name=license_name,
        creator=media.fields.get("Fotograf", ""),
    )


def is_runer_ku_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and parsed.hostname == "runer.ku.dk"


def resolve_runer_ku_image(link_url: str, direct_url: str = "") -> ResolvedImage:
    # Keep the selected image: an object page can contain several photographs.
    image_url = direct_url or link_url
    filename = unquote(_filename_from_url(image_url))
    if not is_runer_ku_url(image_url) or _media_type_from_filename(filename) == "application/octet-stream":
        raise ImageResolveError("No direct Runer KU image resource was found.")
    return ResolvedImage(
        provider="Runer KU",
        source_url=link_url or direct_url,
        download_url=quote(image_url, safe=":/?&=%+#"),
        thumbnail_url=quote(image_url, safe=":/?&=%+#"),
        file_name=filename,
        media_type=_media_type_from_filename(filename),
        file_size=None,
        license_url="",
        license_name="",
    )


def is_arild_hauge_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and parsed.hostname in {"arild-hauge.com", "www.arild-hauge.com"}


def resolve_arild_hauge_image(link_url: str, direct_url: str = "") -> ResolvedImage:
    image_url = unescape(direct_url or link_url)
    filename = unquote(_filename_from_url(image_url))
    if not is_arild_hauge_url(image_url) or _media_type_from_filename(filename) == "application/octet-stream":
        raise ImageResolveError("No direct Arild Hauge image resource was found.")
    image_url = quote(image_url, safe=":/?&=%+#")
    return ResolvedImage(
        provider="Arild Hauge",
        source_url=link_url or direct_url,
        download_url=image_url,
        thumbnail_url=image_url,
        file_name=filename,
        media_type=_media_type_from_filename(filename),
        file_size=None,
        license_url="",
        license_name="",
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
    check_export_cancelled()
    request = Request(url, headers={"User-Agent": "Rundata-net image export (https://rundata.info/)"})
    ssl_context = ssl.create_default_context(cafile=certifi.where() if certifi else None)
    try:
        with urlopen(request, timeout=timeout, context=ssl_context) as response:
            if not hasattr(response, "read1"):
                data = response.read()
                check_export_cancelled()
                return data
            chunks = []
            while True:
                check_export_cancelled()
                chunk = response.read1(64 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            check_export_cancelled()
            return b"".join(chunks)
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
    if extension == "gif":
        return "image/gif"
    if extension in {"tif", "tiff"}:
        return "image/tiff"
    return "application/octet-stream"


def _license_name_from_url(license_url: str) -> str:
    if "publicdomain/mark" in license_url:
        return "Public Domain Mark"
    if "creativecommons.org/licenses/by/4.0" in license_url:
        return "CC-BY 4.0"
    return ""
