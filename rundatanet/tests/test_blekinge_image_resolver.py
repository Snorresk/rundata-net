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

SOURCE = 'https://blm.kulturhotell.se/objects/c32-38619/'
THUMB = 'https://blm.kulturhotell.se/files/thumbnails/selected.jpg'
FULL = 'https://cust.kulturhotell.se/c32/files/fullsize/selected.jpg'
OTHER = 'https://cust.kulturhotell.se/c32/files/fullsize/other.jpg'
LICENSE = 'https://creativecommons.org/licenses/by-nc/4.0/'
HTML = f'<meta content="{OTHER}" property="og:image"><a href="{FULL}" download>Ladda ner</a><a href="{LICENSE}">Licens</a>'.encode()


class TestBlekingeResolver(SimpleTestCase):
    def test_source_recognition(self):
        assert is_supported_image_source(SOURCE)
        for url in [SOURCE.replace('blm.kulturhotell.se', 'blm.kulturhotell.se.evil.org'), SOURCE.replace('https:', 'ftp:'), SOURCE.replace('/objects/', '/items/')]:
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
        assert result.download_url == 'https://blm.kulturhotell.se/files/fullsize/selected.jpg'
        assert result.license_url == result.license_name == result.creator == ''

    @patch('rundatanet.runes.image_resolvers.fetch_url_bytes', side_effect=ImageResolveError('Unavailable'))
    def test_fetch_failure_is_reported(self, fetch):
        with self.assertRaisesMessage(ImageResolveError, 'Unavailable'):
            resolve_image_link(SOURCE, THUMB)


class TestBlekingeExport(TestCase):
    databases = {'default', 'runes_db'}

    @patch('rundatanet.runes.views.fetch_url_bytes', return_value=b'blekinge-image')
    @patch('rundatanet.runes.image_resolvers.fetch_url_bytes', return_value=HTML)
    def test_zip_contains_selected_image_and_license(self, metadata_fetch, image_fetch):
        signature = Signature.objects.using('runes_db').create(signature_text='DR 356')
        meta = MetaInformation.objects.using('runes_db').create(signature=signature)
        image = ImageLink.objects.using('runes_db').create(meta=meta, link_url=SOURCE, direct_url=THUMB)
        response = self.client.post(reverse('runes:export_raa_images_zip'), data=json.dumps({'inscriptions': [{'signature': 'DR 356', 'image_ids': [image.id]}]}), content_type='application/json')
        assert response.status_code == 200
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            assert archive.read('images/0001-dr-356.jpg') == b'blekinge-image'
            metadata = list(csv.DictReader(StringIO(archive.read('metadata.csv').decode('utf-8-sig'))))
            assert metadata[0]['provider'] == 'Blekinge museum'
            assert metadata[0]['license_url'] == LICENSE
            assert metadata[0]['download_url'] == FULL
        image_fetch.assert_called_once_with(FULL)
