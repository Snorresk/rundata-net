"""Synthetic parser fixtures; museum is temporarily closed, live QA is pending."""
import csv
import json
import zipfile
from io import BytesIO, StringIO
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from rundatanet.runes.image_resolvers import ImageResolveError, is_supported_image_source, resolve_image_link
from rundatanet.runes.models import ImageLink, MetaInformation, Signature
from rundatanet.runes import views  # Load aliases before patching the resolver's fetch function.

SOURCE = 'https://jlm.kulturhotell.se/items/show/272754'
THUMB = 'https://jlm.kulturhotell.se/files/thumbnails/selected.jpg'
FULL = 'https://jlm.kulturhotell.se/files/fullsize/selected.jpg'
OTHER = 'https://jlm.kulturhotell.se/files/fullsize/other.jpg'
LICENSE = 'https://creativecommons.org/licenses/by-nc/4.0/'
HTML = f'<meta content="{OTHER}" property="og:image"><a href="{FULL}" download>Ladda ner</a><a href="{LICENSE}">Licens</a>'.encode()


class TestJamtlandResolver(SimpleTestCase):
    def test_source_recognition(self):
        assert is_supported_image_source(SOURCE)
        for url in [SOURCE.replace('jlm.kulturhotell.se', 'jlm.kulturhotell.se.evil.org'), SOURCE.replace('https:', 'ftp:'), SOURCE.replace('/items/show/', '/objects/')]:
            assert not is_supported_image_source(url)

    @patch('rundatanet.runes.image_resolvers.fetch_url_bytes', return_value=HTML)
    def test_preserves_selected_photo_and_license(self, fetch):
        result = resolve_image_link(SOURCE, THUMB)
        assert result.download_url == FULL
        assert result.thumbnail_url == THUMB
        assert result.license_url == LICENSE
        assert result.license_name == 'CC BY-NC 4.0'
        assert result.creator == ''
        fetch.assert_called_once_with(SOURCE, timeout=15)

    @patch('rundatanet.runes.image_resolvers.fetch_url_bytes', return_value=HTML)
    def test_rejects_missing_selected_photo_and_ambiguous_selection(self, fetch):
        for direct in ['', THUMB.replace('selected', 'missing'), 'https://example.org/selected.jpg']:
            with self.assertRaises(ImageResolveError):
                resolve_image_link(SOURCE, direct)

    @patch('rundatanet.runes.image_resolvers.fetch_url_bytes')
    def test_rejects_shutdown_page_thumbnail_only_and_foreign_hosts(self, fetch):
        for html in ['<h1>Tillfälligt stängt</h1>', f'<img src="{THUMB}">', '<a download href="https://example.org/files/fullsize/selected.jpg">Download</a>']:
            fetch.return_value = html.encode()
            with self.assertRaises(ImageResolveError):
                resolve_image_link(SOURCE, THUMB)

    @patch('rundatanet.runes.image_resolvers.fetch_url_bytes', return_value=b'<img src="/files/fullsize/selected.jpg">')
    def test_relative_image_and_missing_rights(self, fetch):
        result = resolve_image_link(SOURCE, THUMB)
        assert result.download_url == 'https://jlm.kulturhotell.se/files/fullsize/selected.jpg'
        assert result.license_url == result.license_name == result.creator == ''

    @patch('rundatanet.runes.image_resolvers.fetch_url_bytes', side_effect=ImageResolveError('Unavailable'))
    def test_fetch_failure_is_reported(self, fetch):
        with self.assertRaisesMessage(ImageResolveError, 'Unavailable'):
            resolve_image_link(SOURCE, THUMB)

    @patch('rundatanet.runes.image_resolvers.fetch_url_bytes')
    def test_original_link_and_cross_museum_isolation(self, fetch):
        original = FULL.replace('/fullsize/', '/original/')
        fetch.return_value = f'<a href="{original}">Download</a>'.encode()
        assert resolve_image_link(SOURCE, THUMB).download_url == original
        fetch.return_value = f'<a href="{FULL.replace("jlm.kulturhotell.se", "blm.kulturhotell.se")}">Download</a>'.encode()
        with self.assertRaises(ImageResolveError):
            resolve_image_link(SOURCE, THUMB)


class TestJamtlandExport(TestCase):
    databases = {'default', 'runes_db'}

    @patch('rundatanet.runes.views.fetch_url_bytes', return_value=b'jamtland-image')
    @patch('rundatanet.runes.image_resolvers.fetch_url_bytes', return_value=HTML)
    def test_zip_contains_selected_image_and_license(self, metadata_fetch, image_fetch):
        signature = Signature.objects.using('runes_db').create(signature_text='J RS1928;66')
        meta = MetaInformation.objects.using('runes_db').create(signature=signature)
        image = ImageLink.objects.using('runes_db').create(meta=meta, link_url=SOURCE, direct_url=THUMB)
        response = self.client.post(reverse('runes:export_raa_images_zip'), data=json.dumps({'inscriptions': [{'signature': 'J RS1928;66', 'image_ids': [image.id]}]}), content_type='application/json')
        assert response.status_code == 200
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            assert archive.read('images/0001-j-rs1928-66.jpg') == b'jamtland-image'
            metadata = list(csv.DictReader(StringIO(archive.read('metadata.csv').decode('utf-8-sig'))))
            assert metadata[0]['provider'] == 'Jämtlands läns museum'
            assert metadata[0]['license_url'] == LICENSE
            assert metadata[0]['download_url'] == FULL
        image_fetch.assert_called_once_with(FULL)
