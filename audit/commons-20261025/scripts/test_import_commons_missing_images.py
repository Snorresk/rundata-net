from import_commons_missing_images import clean, image_data


def test_image_verification_rejects_html_and_accepts_common_formats():
    for data in (b'\xff\xd8\xffimage', b'\x89PNG\r\n\x1a\nimage', b'GIF89aimage', b'II*\x00image'):
        assert image_data(data)
    assert not image_data(b'<html>Not found</html>')
    assert not image_data(b'%PDF-1.4 document')


def test_credit_text_keeps_names_but_removes_markup_and_extra_spaces():
    assert clean('<a href="https://example.org">Anna &amp; Erik</a>\n Photo') == 'Anna & Erik Photo'


def test_svg_must_be_the_document_root():
    assert image_data(b'<svg xmlns="http://www.w3.org/2000/svg"><path/></svg>')
    assert not image_data(b'<html><svg/></html>')
