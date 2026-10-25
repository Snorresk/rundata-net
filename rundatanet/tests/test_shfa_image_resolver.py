import copy
import csv
import json
import zipfile
from io import BytesIO, StringIO
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from rundatanet.runes import views  # Load view aliases before patching resolver functions.
from rundatanet.runes.image_resolvers import ImageResolveError, is_supported_image_source, resolve_image_link
from rundatanet.runes.models import ImageLink, MetaInformation, Signature

SOURCE = 'https://shfa.dh.gu.se/image/109439'
LEGACY = 'https://data.dh.gu.se/diana/static/shfa/original/490.jpg'
ORIGINAL = 'https://data.dh.gu.se/shfa/static/shfa/original/490.jpg'
DOCUMENT = json.loads((Path(__file__).parent / 'fixtures/shfa/image-109439.json').read_text())


class TestShfaResolver(SimpleTestCase):
    def test_recognition(self):
        assert is_supported_image_source(SOURCE)
        assert is_supported_image_source(SOURCE + '/?foo=bar')
        for url in [SOURCE.replace('shfa.dh.gu.se', 'shfa.dh.gu.se.evil.org'), SOURCE.replace('https:', 'ftp:'), SOURCE.replace('/image/', '/site/'), SOURCE + '/other']:
            assert not is_supported_image_source(url)

    @patch('rundatanet.runes.image_resolvers._fetch_json', return_value=DOCUMENT)
    def test_current_api_url_replaces_legacy_url_and_preserves_attribution(self, fetch):
        result = resolve_image_link(SOURCE, LEGACY, timeout=8)
        assert result.download_url == result.thumbnail_url == ORIGINAL
        assert result.file_name == '490.jpg'
        assert result.media_type == 'image/jpeg'
        assert result.provider == 'SHFA'
        assert result.creator == 'Lagergren, Nils'
        assert result.license_name == 'CC BY 4.0'
        assert result.license_url == 'https://creativecommons.org/licenses/by/4.0/'
        fetch.assert_called_once_with('https://shfa.dh.gu.se/api/image/?id=109439&depth=1', timeout=8)

    @patch('rundatanet.runes.image_resolvers._fetch_json', return_value=DOCUMENT)
    def test_source_only_and_current_direct_url(self, fetch):
        for direct in ['', ORIGINAL]:
            assert resolve_image_link(SOURCE, direct).download_url == ORIGINAL

    @patch('rundatanet.runes.image_resolvers._fetch_json', return_value=DOCUMENT)
    def test_rejects_other_selected_image_and_foreign_direct_url(self, fetch):
        for direct in [LEGACY.replace('490.jpg', '489.jpg'), ORIGINAL.replace('data.dh.gu.se', 'example.org'), ORIGINAL + '?other=1']:
            with self.assertRaises(ImageResolveError):
                resolve_image_link(SOURCE, direct)

    @patch('rundatanet.runes.image_resolvers._fetch_json')
    def test_rejects_missing_malformed_mismatched_unpublished_or_unsafe_image(self, fetch):
        documents = [None, [], {}, {'results': []}, {'results': [None]}, {'results': [{}, {}]}]
        for field, value in [('id', 109438), ('published', False), ('file', 'https://example.org/490.jpg'), ('file', None), ('file', 'https://data.dh.gu.se/shfa/static/shfa/original/490.pdf')]:
            document = copy.deepcopy(DOCUMENT)
            document['results'][0][field] = value
            documents.append(document)
        for document in documents:
            fetch.return_value = document
            with self.assertRaises(ImageResolveError):
                resolve_image_link(SOURCE, LEGACY)

    @patch('rundatanet.runes.image_resolvers._fetch_json')
    def test_people_and_author_fallback_and_unknown_creator(self, fetch):
        document = copy.deepcopy(DOCUMENT)
        image = document['results'][0]
        fetch.return_value = document
        image['people'] = [{'name': 'Anna'}, {'name': 'Erik'}, {'name': 'Anna'}, None]
        assert resolve_image_link(SOURCE).creator == 'Anna; Erik'
        image['people'] = []
        assert resolve_image_link(SOURCE).creator == 'Lagergren, Nils'
        image['author'] = None
        assert resolve_image_link(SOURCE).creator == ''

    @patch('rundatanet.runes.image_resolvers._fetch_json', side_effect=ImageResolveError('Unavailable'))
    def test_api_failure(self, fetch):
        with self.assertRaisesMessage(ImageResolveError, 'Unavailable'):
            resolve_image_link(SOURCE)


class TestShfaExport(TestCase):
    databases = {'default', 'runes_db'}

    @patch('rundatanet.runes.views.fetch_url_bytes', return_value=b'shfa-original')
    @patch('rundatanet.runes.image_resolvers._fetch_json', return_value=DOCUMENT)
    def test_zip_contains_current_original_and_attribution(self, metadata_fetch, image_fetch):
        signature = Signature.objects.using('runes_db').create(signature_text='Sö 101')
        meta = MetaInformation.objects.using('runes_db').create(signature=signature)
        image = ImageLink.objects.using('runes_db').create(meta=meta, link_url=SOURCE, direct_url=LEGACY)
        response = self.client.post(reverse('runes:export_raa_images_zip'), data=json.dumps({'inscriptions': [{'signature': 'Sö 101', 'image_ids': [image.id]}]}), content_type='application/json')
        assert response.status_code == 200
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            assert archive.read('images/0001-so-101.jpg') == b'shfa-original'
            metadata = list(csv.DictReader(StringIO(archive.read('metadata.csv').decode('utf-8-sig'))))
            assert metadata[0]['provider'] == 'SHFA'
            assert metadata[0]['creator'] == 'Lagergren, Nils'
            assert metadata[0]['license_name'] == 'CC BY 4.0'
            assert metadata[0]['download_url'] == ORIGINAL
        image_fetch.assert_called_once_with(ORIGINAL)
