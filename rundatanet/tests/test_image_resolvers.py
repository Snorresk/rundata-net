import csv
import json
import zipfile
from io import BytesIO, StringIO
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from rundatanet.runes.image_resolvers import (
    ImageResolveError, extract_commons_file_title, extract_raa_document_uuid, is_supported_image_source, resolve_image_link,
)
from rundatanet.runes.models import ImageLink, MetaInformation, Signature


RAA_UUID = "d8875a4e-0e76-4eea-b571-f592189f5d5b"
RUNER_SOURCE_URL = "https://runer.ku.dk/q.php?p=runer/genstande/genstand/365"
RUNER_IMAGE_URL = "https://runer.ku.dk/projects/runer/RunerKUdk_userfiles/image/ImgCache/365/rune05b_502.jpg"
RAA_SOURCE_URL = f"https://pub.raa.se/visa/dokumentation/{RAA_UUID}"
RAA_THUMBNAIL_URL = f"https://pub.raa.se/dokumentation/{RAA_UUID}/visning/1/miniatyr"
RAA_DISPLAY_URL = f"https://pub.raa.se/dokumentation/{RAA_UUID}/visning/1"
RAA_ARCHIVE_URL = f"https://pub.raa.se/dokumentation/{RAA_UUID}/arkivbestandig/1"
SORMLAND_SOURCE_URL = "https://sokisamlingar.sormlandsmuseum.se/objects/c24-363406/"
SORMLAND_IMAGE_URL = "https://cust.kulturhotell.se/c24/files/fullsize/45dc66d1c25b38bc42c49d91ad8f6a84.jpg"
SORMLAND_LICENSE_URL = "https://creativecommons.org/publicdomain/mark/1.0/deed.sv"
DIGITALT_MUSEUM_SOURCE_URL = "https://digitaltmuseum.se/011013957649"
DIGITALT_MUSEUM_DOWNLOAD_URL = (
    "https://ems.dimu.org/image/022s93Xu15Yc"
    "?filename=DIA15081.jpg&dimension=max&quality=100&dpi=300&mediatype=image/jpg"
)
DIGITALT_MUSEUM_THUMBNAIL_URL = "https://ems.dimu.org/image/022s93Xu15Yc?dimension=1200x1200"
DIGITALT_MUSEUM_LICENSE_URL = "https://creativecommons.org/licenses/by-nc-nd/4.0/deed.en"
SHM_OBJECT_URL = "https://samlingar.shm.se/object/BD0ABD5C-09DE-4A1E-B271-7F04E724A059"
SHM_IMAGE_ID = "f65a25f3-dc74-4f47-9e97-d1534fa5eae9"
SHM_MEDIA_URL = f"https://samlingar.shm.se/media/{SHM_IMAGE_ID}"
SHM_DOWNLOAD_URL = f"https://media.samlingar.shm.se/item/{SHM_IMAGE_ID}"
SHM_THUMBNAIL_URL = SHM_DOWNLOAD_URL + "/thumbnail"
SHM_OTHER_ID = "45b9f342-ecc4-44f2-89cd-43128fcf1e37"
SHM_OBJECT_HTML = f"""
<meta property="og:image" content="https://media.samlingar.shm.se/item/{SHM_OTHER_ID}/large">
<a download href="{SHM_DOWNLOAD_URL}">Ladda ner media</a>
""".encode()
COMMONS_SOURCE_URL = "https://commons.wikimedia.org/wiki/File:G_157.jpg"
COMMONS_ORIGINAL_URL = "https://upload.wikimedia.org/wikipedia/commons/0/06/G_157.jpg"
COMMONS_THUMBNAIL_URL = "https://thumb.wikimedia.org/wikipedia/commons/thumb/0/06/G_157.jpg/330px-G_157.jpg"


def commons_document():
    return {"query": {"pages": [{"ns": 6, "title": "File:G 157.jpg", "imageinfo": [{
        "url": COMMONS_ORIGINAL_URL, "thumburl": COMMONS_THUMBNAIL_URL,
        "mime": "image/jpeg", "size": 212240,
        "extmetadata": {
            "Artist": {"value": '<a href="/wiki/User:Photographer">Anna &amp; Erik</a>'},
            "LicenseShortName": {"value": "CC BY-SA 4.0"},
            "LicenseUrl": {"value": "//creativecommons.org/licenses/by-sa/4.0/"},
        },
    }]}]}}


def shm_media_html(license_slug="cc-by-4_0", media_type="image/jpeg"):
    return f"""
    <table>
      <tr><th>Mediatyp</th><td><div>{media_type}</div></td></tr>
      <tr><th>Fotograf</th><td><a>Huber, John-Björn</a></td></tr>
      <tr><th>Licens för media</th><td>
        <span class="license-icon-collection license-icon-collection--{license_slug}"></span>
      </td></tr>
    </table>
    <p>All textinformation (metadata) på denna sida är fri att använda enligt licensen CC0.</p>
    <a href="https://media.samlingar.shm.se/item/{SHM_OTHER_ID}" download>Other image</a>
    <a class="download-button" href="{SHM_DOWNLOAD_URL}" download>Ladda ner media</a>
    """.encode()


def raa_document_json():
    return {
        "license": {
            "license": "https://creativecommons.org/licenses/by/4.0/",
            "licenseName": "CC-BY 4.0",
        },
        "resourceGroups": [
            {
                "presentationThumbnailUrl": RAA_THUMBNAIL_URL,
                "resources": [
                    {
                        "fileName": "index_1.tiff",
                        "fileSize": 37758930,
                        "format": "arkivbestandig",
                        "media": "image/tiff",
                        "uri": RAA_ARCHIVE_URL,
                    },
                    {
                        "fileName": "thumbnail.png",
                        "fileSize": 43273,
                        "format": "visning",
                        "media": "image/png",
                        "uri": RAA_THUMBNAIL_URL,
                    },
                    {
                        "fileName": "index_1.jpeg",
                        "fileSize": 741459,
                        "format": "visning",
                        "media": "image/jpeg",
                        "uri": RAA_DISPLAY_URL,
                    },
                ],
            }
        ],
    }


class FakeUrlopenResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(raa_document_json()).encode("utf-8")


class FakeSormlandUrlopenResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return f"""
        <html>
          <head>
            <meta property="og:image" content="{SORMLAND_IMAGE_URL}" />
          </head>
          <body>
            <a href="{SORMLAND_LICENSE_URL}">Public Domain-märke (PDM)</a>
          </body>
        </html>
        """.encode("utf-8")


class FakeDigitaltMuseumUrlopenResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return f"""
        <html>
          <head>
            <meta property="og:image" content="{DIGITALT_MUSEUM_THUMBNAIL_URL}" />
          </head>
          <body>
            <script>
              window.app.data = {{"images":[{{"dms_url":"https://ems.dimu.org/image/022s93Xu15Yc","license_data":{{"licenses":[{{"label":"CC by-nc-nd","link":{{"url":"{DIGITALT_MUSEUM_LICENSE_URL}"}}}}]}}}}]}};
            </script>
            <a download href="{DIGITALT_MUSEUM_DOWNLOAD_URL}">Accept license and download photo</a>
            <a href="{DIGITALT_MUSEUM_LICENSE_URL}">Attribution-NonCommercial-NoDerivs (CC BY-NC-ND)</a>
          </body>
        </html>
        """.encode("utf-8")


class TestCommonsImageResolver(SimpleTestCase):
    def test_extracts_encoded_titles_and_index_urls(self):
        assert extract_commons_file_title("https://commons.wikimedia.org/wiki/File:S%C3%B6_1_%28a%29.jpg") == "File:Sö 1 (a).jpg"
        assert extract_commons_file_title("https://commons.wikimedia.org/w/index.php?title=File%3AS%C3%B6_1.jpg&oldid=123") == "File:Sö 1.jpg"
        for url in ("https://commons.wikimedia.org.example.org/wiki/File:G_157.jpg",
                    "https://example.org/commons.wikimedia.org/wiki/File:G_157.jpg",
                    "https://commons.wikimedia.org/wiki/Category:Runestones",
                    "https://commons.wikimedia.org/wiki/File:A.jpg%7CFile:B.jpg",
                    "https://commons.wikimedia.org/wiki/File:"):
            assert not is_supported_image_source(url)

    @patch("rundatanet.runes.image_resolvers.fetch_url_bytes")
    def test_uses_api_original_instead_of_saved_thumbnail(self, mocked_fetch):
        mocked_fetch.return_value = json.dumps(commons_document()).encode()
        resolved = resolve_image_link(COMMONS_SOURCE_URL, "https://example.org/wrong-thumbnail.jpg", timeout=9)
        assert resolved.provider == "Wikimedia Commons"
        assert resolved.source_url == COMMONS_SOURCE_URL
        assert resolved.download_url == COMMONS_ORIGINAL_URL
        assert resolved.thumbnail_url == COMMONS_THUMBNAIL_URL
        assert resolved.file_name == "G 157.jpg"
        assert resolved.file_size == 212240
        assert resolved.creator == "Anna & Erik"
        assert resolved.license_name == "CC BY-SA 4.0"
        assert resolved.license_url == "https://creativecommons.org/licenses/by-sa/4.0/"
        request_url = mocked_fetch.call_args.args[0]
        assert urlparse(request_url).hostname == "commons.wikimedia.org"
        params = parse_qs(urlparse(request_url).query)
        assert params["titles"] == ["File:G 157.jpg"]
        assert params["redirects"] == ["1"]
        assert mocked_fetch.call_args.kwargs["timeout"] == 9

    @patch("rundatanet.runes.image_resolvers.fetch_url_bytes")
    def test_preserves_redirected_filename_and_original_format(self, mocked_fetch):
        document = commons_document()
        page = document["query"]["pages"][0]
        page["title"] = "File:Renamed stone.svg"
        image = page["imageinfo"][0]
        image.update(url=COMMONS_ORIGINAL_URL.replace(".jpg", ".svg"), mime="image/svg+xml")
        mocked_fetch.return_value = json.dumps(document).encode()
        resolved = resolve_image_link(COMMONS_SOURCE_URL)
        assert resolved.file_name == "Renamed stone.svg"
        assert resolved.media_type == "image/svg+xml"
        assert resolved.download_url.endswith(".svg")

    @patch("rundatanet.runes.image_resolvers.fetch_url_bytes")
    def test_missing_license_is_not_inferred_and_artist_is_not_uploader(self, mocked_fetch):
        document = commons_document()
        image = document["query"]["pages"][0]["imageinfo"][0]
        image.update(extmetadata={}, user="Upload bot")
        del image["thumburl"]
        mocked_fetch.return_value = json.dumps(document).encode()
        resolved = resolve_image_link(COMMONS_SOURCE_URL)
        assert resolved.creator == resolved.license_name == resolved.license_url == ""
        assert resolved.thumbnail_url == COMMONS_ORIGINAL_URL

    @patch("rundatanet.runes.image_resolvers.fetch_url_bytes")
    def test_handles_missing_files_api_errors_and_invalid_json(self, mocked_fetch):
        for payload in (b'{"query":{"pages":[{"ns":6,"missing":true}]}}',
                        b'{"error":{"code":"ratelimited"}}', b'not json', b'[]'):
            mocked_fetch.return_value = payload
            with self.assertRaises(ImageResolveError):
                resolve_image_link(COMMONS_SOURCE_URL)

    @patch("rundatanet.runes.image_resolvers.fetch_url_bytes")
    def test_rejects_non_image_originals_and_external_download_urls(self, mocked_fetch):
        for field, value in (("mime", "application/pdf"),
                             ("url", "https://example.org/image.jpg"),
                             ("url", "https://upload.wikimedia.org/wikipedia/en/a/a0/image.jpg")):
            document = commons_document()
            document["query"]["pages"][0]["imageinfo"][0][field] = value
            mocked_fetch.return_value = json.dumps(document).encode()
            with self.assertRaises(ImageResolveError):
                resolve_image_link(COMMONS_SOURCE_URL)


class TestShmImageResolver(SimpleTestCase):
    @patch("rundatanet.runes.image_resolvers.fetch_url_bytes")
    def test_preserves_selected_photo_and_reads_its_own_rights(self, mocked_fetch):
        mocked_fetch.side_effect = [SHM_OBJECT_HTML, shm_media_html()]
        resolved = resolve_image_link(SHM_OBJECT_URL, SHM_THUMBNAIL_URL, timeout=7)
        assert is_supported_image_source(SHM_OBJECT_URL)
        assert resolved.provider == "SHM"
        assert resolved.source_url == SHM_OBJECT_URL
        assert resolved.download_url == SHM_DOWNLOAD_URL
        assert resolved.thumbnail_url == SHM_THUMBNAIL_URL
        assert resolved.file_name == f"shm-{SHM_IMAGE_ID}.jpg"
        assert resolved.media_type == "image/jpeg"
        assert resolved.license_name == "CC BY 4.0"
        assert resolved.license_url == "https://creativecommons.org/licenses/by/4.0/"
        assert resolved.creator == "Huber, John-Björn"
        assert mocked_fetch.call_args.args[0] == SHM_MEDIA_URL
        assert mocked_fetch.call_args.kwargs["timeout"] == 7

    @patch("rundatanet.runes.image_resolvers.fetch_url_bytes")
    def test_uses_object_image_when_no_thumbnail_was_saved(self, mocked_fetch):
        mocked_fetch.side_effect = [f'<meta content="{SHM_DOWNLOAD_URL}/large" property="og:image">'.encode(), shm_media_html()]
        assert resolve_image_link(SHM_OBJECT_URL).download_url == SHM_DOWNLOAD_URL

    @patch("rundatanet.runes.image_resolvers.fetch_url_bytes")
    def test_reads_media_pages_and_public_domain_license(self, mocked_fetch):
        mocked_fetch.return_value = shm_media_html("pdm", "image/tiff")
        resolved = resolve_image_link(SHM_MEDIA_URL)
        assert resolved.media_type == "image/tiff"
        assert resolved.file_name.endswith(".tif")
        assert resolved.license_name == "Public Domain Mark"
        assert resolved.license_url == "https://creativecommons.org/publicdomain/mark/1.0/"
        mocked_fetch.assert_called_once_with(SHM_MEDIA_URL, timeout=15)

    @patch("rundatanet.runes.image_resolvers.urlopen")
    @patch("rundatanet.runes.image_resolvers.fetch_url_bytes")
    def test_missing_media_type_is_read_from_the_original_headers(self, mocked_fetch, mocked_open):
        mocked_fetch.return_value = shm_media_html().replace(
            b'<tr><th>Mediatyp</th><td><div>image/jpeg</div></td></tr>', b'')
        mocked_open.return_value.__enter__.return_value.headers = {
            "Content-Type": "image/jpeg", "Content-Length": "12345"}
        resolved = resolve_image_link(SHM_MEDIA_URL)
        assert resolved.media_type == "image/jpeg"
        assert resolved.file_size == 12345
        assert mocked_open.call_args.args[0].get_method() == "HEAD"
        assert mocked_open.call_args.args[0].full_url == SHM_DOWNLOAD_URL

    @patch("rundatanet.runes.image_resolvers.fetch_url_bytes")
    def test_preserves_restrictive_media_license(self, mocked_fetch):
        mocked_fetch.return_value = shm_media_html("cc-by-nc-nd-2_5")
        resolved = resolve_image_link(SHM_MEDIA_URL)
        assert resolved.license_name == "CC BY-NC-ND 2.5"
        assert resolved.license_url == "https://creativecommons.org/licenses/by-nc-nd/2.5/"

    @patch("rundatanet.runes.image_resolvers.fetch_url_bytes", return_value=SHM_OBJECT_HTML)
    def test_rejects_a_thumbnail_that_is_not_attached_to_the_object(self, mocked_fetch):
        for direct in (SHM_DOWNLOAD_URL.replace(SHM_IMAGE_ID, "00000000-0000-0000-0000-000000000000"),
                       "https://example.org/image.jpg"):
            with self.assertRaises(ImageResolveError):
                resolve_image_link(SHM_OBJECT_URL, direct)

    @patch("rundatanet.runes.image_resolvers.fetch_url_bytes")
    def test_does_not_infer_a_license_from_the_metadata_cc0_notice(self, mocked_fetch):
        mocked_fetch.return_value = shm_media_html("unknown-license")
        resolved = resolve_image_link(SHM_MEDIA_URL)
        assert resolved.license_name == resolved.license_url == ""

    @patch("rundatanet.runes.image_resolvers.fetch_url_bytes")
    def test_rejects_missing_original_or_non_image_media(self, mocked_fetch):
        for page in (shm_media_html().replace(b" download", b" data-download"),
                     shm_media_html(media_type="application/pdf"),
                     b"<html>Service unavailable</html>"):
            mocked_fetch.return_value = page
            with self.assertRaises(ImageResolveError):
                resolve_image_link(SHM_MEDIA_URL)

    def test_rejects_lookalike_hosts_and_non_object_paths(self):
        for url in (SHM_OBJECT_URL.replace("shm.se", "shm.se.example.org"),
                    "https://example.org/samlingar.shm.se/object/test", "https://samlingar.shm.se/person/test"):
            assert not is_supported_image_source(url)


class TestArildHaugeImageResolver(SimpleTestCase):
    @patch("rundatanet.runes.image_resolvers.urlopen")
    def test_resolves_direct_images_without_fetching_page(self, mocked_urlopen):
        for extension, media_type in (("jpg", "image/jpeg"), ("jpeg", "image/jpeg"), ("gif", "image/gif"), ("png", "image/png")):
            url = f"https://www.arild-hauge.com/arild-hauge/tunestein.{extension}"
            resolved = resolve_image_link(url, url)
            assert is_supported_image_source(url)
            assert resolved.provider == "Arild Hauge"
            assert resolved.download_url == url
            assert resolved.media_type == media_type
            assert resolved.license_url == resolved.license_name == ""
        mocked_urlopen.assert_not_called()

    def test_normalizes_entities_spaces_and_unicode(self):
        url = "https://arild-hauge.com/Futhark/Bug&aring;rd photo%20one.JPG"
        resolved = resolve_image_link(url)
        assert resolved.download_url.endswith("Bug%C3%A5rd%20photo%20one.JPG")
        assert resolved.file_name == "Bugård photo one.JPG"
        assert resolved.media_type == "image/jpeg"

    def test_rejects_pages_and_other_hosts(self):
        with self.assertRaises(ImageResolveError):
            resolve_image_link("https://www.arild-hauge.com/runer.htm")
        with self.assertRaises(ImageResolveError):
            resolve_image_link("https://www.arild-hauge.com/runer.htm", "https://example.org/image.jpg")
        assert not is_supported_image_source("https://arild-hauge.com.example.org/photo.jpg")
        assert not is_supported_image_source("https://example.org/arild-hauge.com/photo.jpg")


class TestRunerKuImageResolver(SimpleTestCase):
    @patch("rundatanet.runes.image_resolvers.urlopen")
    def test_preserves_selected_image_without_fetching_object_page(self, mocked_urlopen):
        resolved = resolve_image_link(RUNER_SOURCE_URL, RUNER_IMAGE_URL)
        assert is_supported_image_source(RUNER_SOURCE_URL, RUNER_IMAGE_URL)
        assert resolved.provider == "Runer KU"
        assert resolved.download_url == RUNER_IMAGE_URL
        assert resolved.source_url == RUNER_SOURCE_URL
        assert resolved.file_name == "rune05b_502.jpg"
        assert resolved.media_type == "image/jpeg"
        assert resolved.license_url == resolved.license_name == ""
        mocked_urlopen.assert_not_called()

    def test_encodes_spaces_and_preserves_existing_escapes(self):
        resolved = resolve_image_link(RUNER_SOURCE_URL, RUNER_IMAGE_URL.replace("rune05b_502", "photo%20one two"))
        assert resolved.download_url.endswith("photo%20one%20two.jpg")
        assert resolved.file_name == "photo one two.jpg"

    def test_accepts_direct_image_without_object_page(self):
        assert resolve_image_link("", RUNER_IMAGE_URL).download_url == RUNER_IMAGE_URL

    def test_rejects_missing_image_and_other_hosts(self):
        for direct_url in ("", "https://example.org/image.jpg"):
            with self.assertRaises(ImageResolveError):
                resolve_image_link(RUNER_SOURCE_URL, direct_url)
        assert not is_supported_image_source("https://runer.ku.dk.example.org/image.jpg")
        assert not is_supported_image_source("https://example.org/runer.ku.dk/image.jpg")


class TestRaaImageResolver(TestCase):
    def test_extracts_raa_uuid_from_source_or_thumbnail_urls(self):
        assert extract_raa_document_uuid(RAA_SOURCE_URL) == RAA_UUID
        assert extract_raa_document_uuid("", RAA_THUMBNAIL_URL) == RAA_UUID

    @patch("rundatanet.runes.image_resolvers.urlopen", return_value=FakeUrlopenResponse())
    def test_resolves_raa_thumbnail_to_display_image(self, mocked_urlopen):
        resolved = resolve_image_link(RAA_SOURCE_URL, RAA_THUMBNAIL_URL)

        assert resolved.provider == "RAÄ"
        assert resolved.download_url == RAA_DISPLAY_URL
        assert resolved.thumbnail_url == RAA_THUMBNAIL_URL
        assert resolved.file_name == "index_1.jpeg"
        assert resolved.media_type == "image/jpeg"
        assert resolved.file_size == 741459
        assert resolved.license_url == "https://creativecommons.org/licenses/by/4.0/"
        assert resolved.license_name == "CC-BY 4.0"

        request = mocked_urlopen.call_args.args[0]
        assert request.full_url == f"https://pub.raa.se/dokumentation/{RAA_UUID}"

    @patch("rundatanet.runes.image_resolvers.urlopen", return_value=FakeSormlandUrlopenResponse())
    def test_resolves_sormlandsmuseum_object_to_fullsize_image(self, mocked_urlopen):
        resolved = resolve_image_link(SORMLAND_SOURCE_URL, "")

        assert resolved.provider == "Sörmlands museum"
        assert resolved.download_url == SORMLAND_IMAGE_URL
        assert resolved.thumbnail_url == SORMLAND_IMAGE_URL
        assert resolved.file_name == "45dc66d1c25b38bc42c49d91ad8f6a84.jpg"
        assert resolved.media_type == "image/jpeg"
        assert resolved.license_url == SORMLAND_LICENSE_URL
        assert resolved.license_name == "Public Domain Mark"
        assert mocked_urlopen.called

    @patch("rundatanet.runes.image_resolvers.urlopen", return_value=FakeDigitaltMuseumUrlopenResponse())
    def test_resolves_digitaltmuseum_object_to_download_image(self, mocked_urlopen):
        resolved = resolve_image_link(DIGITALT_MUSEUM_SOURCE_URL, "")

        assert resolved.provider == "Digitalt museum"
        assert resolved.download_url == DIGITALT_MUSEUM_DOWNLOAD_URL
        assert resolved.thumbnail_url == DIGITALT_MUSEUM_THUMBNAIL_URL
        assert resolved.file_name == "DIA15081.jpg"
        assert resolved.media_type == "image/jpeg"
        assert resolved.license_url == DIGITALT_MUSEUM_LICENSE_URL
        assert resolved.license_name == "CC by-nc-nd"
        assert mocked_urlopen.called


class TestResolveImageDownloadView(TestCase):
    databases = {"default", "runes_db"}

    def setUp(self):
        self.signature = Signature.objects.using("runes_db").create(signature_text="Öl 26")
        self.meta = MetaInformation.objects.using("runes_db").create(signature=self.signature)
        self.image = ImageLink.objects.using("runes_db").create(
            meta=self.meta,
            link_url=RAA_SOURCE_URL,
            direct_url=RAA_THUMBNAIL_URL,
        )

    @patch("rundatanet.runes.image_resolvers.urlopen", return_value=FakeUrlopenResponse())
    def test_resolve_image_download_endpoint_returns_display_image(self, mocked_urlopen):
        url = reverse("runes:resolve_image_download", kwargs={"image_id": self.image.id})
        response = self.client.get(url)

        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["image_id"] == self.image.id
        assert payload["image"]["provider"] == "RAÄ"
        assert payload["image"]["download_url"] == RAA_DISPLAY_URL
        assert payload["image"]["thumbnail_url"] == RAA_THUMBNAIL_URL
        assert mocked_urlopen.called

    @patch("rundatanet.runes.views.fetch_url_bytes", return_value=b"runer-image-bytes")
    def test_export_runer_image_zip(self, mocked_fetch):
        self.image.link_url = RUNER_SOURCE_URL
        self.image.direct_url = RUNER_IMAGE_URL
        self.image.save(using="runes_db")
        response = self.client.post(
            reverse("runes:export_raa_images_zip"),
            data=json.dumps({"inscriptions": [{"signature": "Öl 26", "image_ids": [self.image.id]}]}),
            content_type="application/json",
        )
        assert response.status_code == 200
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            assert archive.read("images/0001-ol-26.jpg") == b"runer-image-bytes"
            assert RUNER_IMAGE_URL in archive.read("metadata.csv").decode("utf-8")
            assert "Runer KU" in archive.read("README.txt").decode("utf-8")
        mocked_fetch.assert_called_once_with(RUNER_IMAGE_URL)

    @patch("rundatanet.runes.views.fetch_url_bytes", return_value=b"GIF89a-image-bytes")
    def test_export_arild_hauge_gif_zip(self, mocked_fetch):
        image_url = "https://www.arild-hauge.com/arild-hauge/tunesteina.gif"
        self.image.link_url = self.image.direct_url = image_url
        self.image.save(using="runes_db")
        response = self.client.post(
            reverse("runes:export_raa_images_zip"),
            data=json.dumps({"inscriptions": [{"signature": "Öl 26", "image_ids": [self.image.id]}]}),
            content_type="application/json",
        )
        assert response.status_code == 200
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            assert archive.read("images/0001-ol-26.gif") == b"GIF89a-image-bytes"
            metadata = archive.read("metadata.csv").decode("utf-8")
            assert "Arild Hauge" in metadata
            assert "image/gif" in metadata
        mocked_fetch.assert_called_once_with(image_url)

    @patch("rundatanet.runes.views.fetch_url_bytes", return_value=b"shm-original-image")
    @patch("rundatanet.runes.image_resolvers.fetch_url_bytes")
    def test_export_shm_zip_includes_original_and_attribution(self, mocked_metadata, mocked_image):
        mocked_metadata.side_effect = [SHM_OBJECT_HTML, shm_media_html()]
        self.image.link_url = SHM_OBJECT_URL
        self.image.direct_url = SHM_THUMBNAIL_URL
        self.image.save(using="runes_db")
        response = self.client.post(
            reverse("runes:export_raa_images_zip"),
            data=json.dumps({"inscriptions": [{"signature": "Öl 26", "image_ids": [self.image.id]}]}),
            content_type="application/json",
        )
        assert response.status_code == 200
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            assert archive.read("images/0001-ol-26.jpg") == b"shm-original-image"
            metadata = list(csv.DictReader(StringIO(archive.read("metadata.csv").decode("utf-8-sig"))))
            assert metadata[0]["provider"] == "SHM"
            assert metadata[0]["download_url"] == SHM_DOWNLOAD_URL
            assert metadata[0]["creator"] == "Huber, John-Björn"
            assert metadata[0]["license_name"] == "CC BY 4.0"
        mocked_image.assert_called_once_with(SHM_DOWNLOAD_URL)

    @patch("rundatanet.runes.views.fetch_url_bytes", return_value=b"commons-original-image")
    @patch("rundatanet.runes.image_resolvers.fetch_url_bytes")
    def test_export_commons_zip_includes_original_license_and_artist(self, mocked_metadata, mocked_image):
        mocked_metadata.return_value = json.dumps(commons_document()).encode()
        self.image.link_url = COMMONS_SOURCE_URL
        self.image.direct_url = COMMONS_THUMBNAIL_URL
        self.image.save(using="runes_db")
        response = self.client.post(
            reverse("runes:export_raa_images_zip"),
            data=json.dumps({"inscriptions": [{"signature": "Öl 26", "image_ids": [self.image.id]}]}),
            content_type="application/json",
        )
        assert response.status_code == 200
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            assert archive.read("images/0001-ol-26.jpg") == b"commons-original-image"
            rows = list(csv.DictReader(StringIO(archive.read("metadata.csv").decode("utf-8-sig"))))
            assert rows[0]["provider"] == "Wikimedia Commons"
            assert rows[0]["creator"] == "Anna & Erik"
            assert rows[0]["license_name"] == "CC BY-SA 4.0"
            assert rows[0]["download_url"] == COMMONS_ORIGINAL_URL
        mocked_image.assert_called_once_with(COMMONS_ORIGINAL_URL)

    @patch("rundatanet.runes.image_resolvers.urlopen", return_value=FakeUrlopenResponse())
    def test_export_raa_images_zip_returns_archive_with_metadata(self, mocked_urlopen):
        url = reverse("runes:export_raa_images_zip")
        response = self.client.post(
            url,
            data=json.dumps({
                "inscriptions": [
                    {
                        "signature": "Öl 26",
                        "image_ids": [self.image.id],
                    }
                ]
            }),
            content_type="application/json",
        )

        assert response.status_code == 200
        assert response["Content-Type"] == "application/zip"
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            names = archive.namelist()
            assert "metadata.csv" in names
            assert "skipped-images.csv" in names
            assert "README.txt" in names
            assert "images/0001-ol-26.jpeg" in names
            metadata = archive.read("metadata.csv").decode("utf-8")
            assert "CC-BY 4.0" in metadata
            assert RAA_DISPLAY_URL in metadata
        assert mocked_urlopen.call_count == 2

    @patch("rundatanet.runes.views.fetch_url_bytes")
    @patch("rundatanet.runes.views.resolve_image_link")
    def test_export_counts_successful_downloads_and_tries_remaining_candidates(self, mocked_resolve, mocked_fetch):
        other_signature = Signature.objects.using("runes_db").create(signature_text="U 1")
        other_meta = MetaInformation.objects.using("runes_db").create(signature=other_signature)
        inscriptions = []
        failed_urls = set()
        for meta in [self.meta, other_meta]:
            images = [ImageLink.objects.using("runes_db").create(
                meta=meta, link_url=RAA_SOURCE_URL, direct_url=RAA_THUMBNAIL_URL,
            ) for _ in range(13)]
            for image in images[:2]:
                failed_urls.add(f"https://example.org/{image.id}.jpg")
            inscriptions.append({"signature": meta.signature.signature_text,
                                 "image_ids": [image.id for image in images]})

        # Use each image's ID as its download URL so the first two candidates per
        # inscription fail, and the thirteenth must never be requested.
        def resolve_candidate(*args):
            index = mocked_resolve.call_count - 1
            image_id = candidate_ids[index]
            return SimpleNamespace(
                download_url=f"https://example.org/{image_id}.jpg",
                file_name="image.jpg", provider="raa", thumbnail_url="",
                media_type="image/jpeg", file_size=None, license_name="",
                license_url="", creator="",
            )

        def download(url):
            if url in failed_urls:
                raise ImageResolveError("Image unavailable")
            return b"image bytes"

        for total_limit in [750, 12]:
            with self.subTest(total_limit=total_limit):
                mocked_resolve.reset_mock()
                mocked_fetch.reset_mock()
                candidate_ids = inscriptions[0]["image_ids"][:12] + inscriptions[1]["image_ids"][:12]
                mocked_resolve.side_effect = resolve_candidate
                mocked_fetch.side_effect = download
                with patch("rundatanet.runes.views.MAX_IMAGE_EXPORT_FILES", total_limit):
                    response = self.client.post(
                        reverse("runes:export_raa_images_zip"),
                        data=json.dumps({"mode": "auto", "inscriptions": inscriptions}),
                        content_type="application/json",
                    )
                assert response.status_code == 200
                with zipfile.ZipFile(BytesIO(response.content)) as archive:
                    metadata = list(csv.DictReader(StringIO(archive.read("metadata.csv").decode())))
                    skipped = list(csv.DictReader(StringIO(archive.read("skipped-images.csv").decode())))
                    assert len(metadata) == min(total_limit, 20)
                    assert sum(row["signature"] == "Öl 26" for row in metadata) == 10
                    assert sum(row["signature"] == "U 1" for row in metadata) == min(total_limit - 10, 10)
                    assert len(skipped) == 4
                assert mocked_fetch.call_count == min(total_limit, 20) + 4

    def test_cancel_export_before_it_starts(self):
        from uuid import uuid4
        export_id = str(uuid4())
        response = self.client.post(reverse('runes:cancel_image_export'),
                                    data=json.dumps({'export_id': export_id}),
                                    content_type='application/json')
        assert response.status_code == 200
        with patch('rundatanet.runes.views.resolve_image_link') as resolve:
            response = self.client.post(reverse('runes:export_raa_images_zip'),
                data=json.dumps({'export_id': export_id, 'inscriptions': [
                    {'signature': 'Öl 26', 'image_ids': [self.image.id]}]}),
                content_type='application/json')
        assert response.status_code == 409
        assert response.json()['cancelled'] is True
        resolve.assert_not_called()

    @patch('rundatanet.runes.image_resolvers.urlopen')
    def test_cancel_during_download_stops_reads_and_allows_new_export(self, mocked_urlopen):
        from uuid import uuid4
        export_id = str(uuid4())
        client = self.client

        class CancelDuringRead(FakeUrlopenResponse):
            reads = 0

            def read1(inner_self, size):
                inner_self.reads += 1
                response = client.post(reverse('runes:cancel_image_export'),
                    data=json.dumps({'export_id': export_id}), content_type='application/json')
                assert response.status_code == 200
                return b'partial image'

        partial = CancelDuringRead()
        mocked_urlopen.return_value = partial
        payload = {'export_id': export_id, 'inscriptions': [
            {'signature': 'Öl 26', 'image_ids': [self.image.id]}]}
        response = client.post(reverse('runes:export_raa_images_zip'),
            data=json.dumps(payload), content_type='application/json')
        assert response.status_code == 409
        assert partial.reads == 1
        assert mocked_urlopen.call_count == 1

        mocked_urlopen.return_value = FakeUrlopenResponse()
        payload['export_id'] = str(uuid4())
        response = client.post(reverse('runes:export_raa_images_zip'),
            data=json.dumps(payload), content_type='application/json')
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/zip'

    @patch('rundatanet.runes.image_resolvers.urlopen', return_value=FakeUrlopenResponse())
    def test_manual_export_downloads_only_selected_images_without_auto_cap(self, mocked_urlopen):
        images = [self.image] + [ImageLink.objects.using('runes_db').create(
            meta=self.meta, link_url=RAA_SOURCE_URL, direct_url=RAA_THUMBNAIL_URL,
        ) for _ in range(12)]
        selected_ids = [image.id for image in images[1:]]
        response = self.client.post(reverse('runes:export_raa_images_zip'),
            data=json.dumps({'mode': 'manual', 'inscriptions': [
                {'signature': 'Öl 26', 'image_ids': selected_ids}]}),
            content_type='application/json')
        assert response.status_code == 200
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            rows = list(csv.DictReader(StringIO(archive.read('metadata.csv').decode())))
        assert [int(row['image_id']) for row in rows] == selected_ids
        assert len(rows) == 12
        assert mocked_urlopen.call_count == 24

    def test_manual_export_rejects_too_many_selections_before_downloading(self):
        with patch('rundatanet.runes.views.resolve_image_link') as resolve:
            response = self.client.post(reverse('runes:export_raa_images_zip'),
                data=json.dumps({'mode': 'manual', 'inscriptions': [
                    {'signature': 'Öl 26', 'image_ids': list(range(1, 752))}]}),
                content_type='application/json')
        assert response.status_code == 400
        resolve.assert_not_called()
