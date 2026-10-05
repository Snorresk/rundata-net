import csv
import io
import json
import unicodedata
import zipfile
from urllib.parse import quote

from django.conf import settings
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt

from .image_resolvers import ImageResolveError, fetch_url_bytes, is_supported_image_source, resolve_image_link
from .models import ImageLink, MetaInformation, Signature
from .normalization import SlugIndex, normalize_signature
from .serializers import MetaInformationSerializer

DEFAULT_AZURE_PDF_STORAGE_BASE_URL = "https://rundatapdfssk.blob.core.windows.net/rundatapdfs"
MAX_AUTO_IMAGES_PER_INSCRIPTION = 5
MAX_IMAGE_EXPORT_FILES = 750

SWEDISH_PROVINCES = {
    "Öl": "Öland",
    "Ög": "Östergötland",
    "Sö": "Södermanland",
    "Sm": "Småland",
    "Vg": "Västergötland",
    "U": "Uppland",
    "Vs": "Västmanland",
    "Nä": "Närke",
    "Vr": "Värmland",
    "Gs": "Gästrikland",
    "Hs": "Hälsingland",
    "M": "Medelpad",
    "Ån": "Ångermanland",
    "D": "Dalarna",
    "Hr": "Härjedalen",
    "J": "Jämtland",
    "Lp": "Lappland",
    "Ds": "Dalsland",
    "Bo": "Bohuslän",
    "G": "Gotland",
    "SE": "Sweden, other",
}


def _province_country_for_signature(signature_text: str) -> str:
    code = signature_text.split(maxsplit=1)[0]
    province = SWEDISH_PROVINCES.get(code)
    if not province:
        return ""
    return f"{province}, Sweden"


def sri_pdf_redirect(request, filename: str):
    """Redirect stable Rundata PDF links to the current storage backend.

    The public URL is intentionally stable and storage-agnostic:
    /pdf/sveriges-runinskrifter/<filename>

    Azure currently stores the Swedish-letter filenames in decomposed Unicode
    form, so normalize before quoting the redirect target.
    """
    storage_base = getattr(settings, "AZURE_BLOB_BASE_URL", "") or DEFAULT_AZURE_PDF_STORAGE_BASE_URL
    normalized_filename = unicodedata.normalize("NFD", filename)
    target = storage_base.rstrip("/") + "/" + quote(normalized_filename, safe="/")
    return redirect(target, permanent=False)


def resolve_image_download(request, image_id: int):
    try:
        image_link = ImageLink.objects.get(pk=image_id)
    except ImageLink.DoesNotExist:
        raise Http404("Image link not found")

    try:
        resolved = resolve_image_link(image_link.link_url, image_link.direct_url)
    except ImageResolveError as error:
        return JsonResponse(
            {
                "ok": False,
                "image_id": image_id,
                "error": str(error),
            },
            status=422,
        )

    return JsonResponse(
        {
            "ok": True,
            "image_id": image_id,
            "image": resolved.as_dict(),
        }
    )


@csrf_exempt
def export_raa_images_zip(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST is required."}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "error": "Could not read export request."}, status=400)

    requested_images = _normalize_image_export_request(payload)
    if not requested_images:
        return JsonResponse({"ok": False, "error": "No RAÄ images were selected for export."}, status=400)

    image_ids = [item["image_id"] for item in requested_images[:MAX_IMAGE_EXPORT_FILES]]
    image_links = {
        image.id: image
        for image in ImageLink.objects.select_related("meta__signature").filter(id__in=image_ids)
    }

    zip_buffer = io.BytesIO()
    metadata_rows = []
    skipped_rows = []
    downloaded_count = 0

    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in requested_images[:MAX_IMAGE_EXPORT_FILES]:
            image_link = image_links.get(item["image_id"])
            if not image_link:
                skipped_rows.append([item["signature"], item["image_id"], "", "Image link not found"])
                continue
            if not is_supported_image_source(image_link.link_url, image_link.direct_url):
                skipped_rows.append([item["signature"], item["image_id"], image_link.link_url, "Unsupported image source"])
                continue

            try:
                resolved = resolve_image_link(image_link.link_url, image_link.direct_url)
                image_bytes = fetch_url_bytes(resolved.download_url)
            except ImageResolveError as error:
                skipped_rows.append([item["signature"], item["image_id"], image_link.link_url, str(error)])
                continue

            downloaded_count += 1
            signature = item["signature"] or image_link.meta.signature.signature_text
            filename = _image_export_filename(signature, downloaded_count, resolved.file_name)
            archive.writestr(f"images/{filename}", image_bytes)
            metadata_rows.append(
                [
                    signature,
                    image_link.id,
                    filename,
                    resolved.provider,
                    image_link.link_url,
                    resolved.download_url,
                    resolved.thumbnail_url,
                    resolved.file_name,
                    resolved.media_type,
                    resolved.file_size or "",
                    resolved.license_name,
                    resolved.license_url,
                ]
            )

        archive.writestr("metadata.csv", _image_export_csv(metadata_rows, [
            "signature",
            "image_id",
            "zip_filename",
            "provider",
            "source_url",
            "download_url",
            "thumbnail_url",
            "source_file_name",
            "media_type",
            "file_size",
            "license_name",
            "license_url",
        ]))
        archive.writestr("skipped-images.csv", _image_export_csv(skipped_rows, [
            "signature",
            "image_id",
            "source_url",
            "reason",
        ]))
        archive.writestr(
            "README.txt",
            "Images exported from Rundata-net search results.\n\n"
            "This image export version supports RAÄ, Sörmlands museum, and Digitalt museum image sources.\n"
            "Users must check image licences and reuse conditions with the original source before publishing or sharing downloaded images.\n",
        )

    if downloaded_count == 0:
        return JsonResponse(
            {
                "ok": False,
                "error": "No supported images could be downloaded.",
                "skipped": len(skipped_rows),
            },
            status=422,
        )

    response = HttpResponse(zip_buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="rundata-images.zip"'
    return response


def _normalize_image_export_request(payload):
    normalized = []
    seen = set()
    for inscription in payload.get("inscriptions", []):
        signature = str(inscription.get("signature") or "").strip()
        selected_for_inscription = 0
        for raw_image_id in inscription.get("image_ids", []):
            if selected_for_inscription >= MAX_AUTO_IMAGES_PER_INSCRIPTION:
                break
            try:
                image_id = int(raw_image_id)
            except (TypeError, ValueError):
                continue
            if image_id in seen:
                continue
            seen.add(image_id)
            selected_for_inscription += 1
            normalized.append({"signature": signature, "image_id": image_id})
            if len(normalized) >= MAX_IMAGE_EXPORT_FILES:
                return normalized
    return normalized


def _image_export_filename(signature: str, index: int, source_file_name: str) -> str:
    extension = "jpg"
    if "." in source_file_name:
        extension = source_file_name.rsplit(".", 1)[1].lower() or extension
    ascii_signature = unicodedata.normalize("NFKD", signature).encode("ascii", "ignore").decode("ascii")
    safe_signature = "".join(char if char.isalnum() else "-" for char in ascii_signature).strip("-").lower()
    if not safe_signature:
        safe_signature = "inscription"
    return f"{index:04d}-{safe_signature}.{extension}"


def _image_export_csv(rows, headers):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue()


def inscription_detail(request, slug: str):
    """Display a single inscription by its normalized slug.

    If the slug matches an alias signature, 301-redirects to the canonical URL.
    """
    index = SlugIndex.get()
    result = index.resolve(slug)

    if result is None:
        raise Http404("Inscription not found")

    canonical_id, canonical_slug = result

    # Redirect aliases and non-canonical slug forms to the canonical URL
    if slug != canonical_slug:
        return redirect("runes:inscription_detail", slug=canonical_slug, permanent=True)

    try:
        signature = Signature.objects.get(id=canonical_id)
    except Signature.DoesNotExist:
        raise Http404("Inscription not found")

    try:
        meta = (
            MetaInformation.objects.select_related("signature", "materialType")
            .prefetch_related("images", "references")
            .get(signature=signature)
        )
    except MetaInformation.DoesNotExist:
        raise Http404("Inscription metadata not found")

    serializer = MetaInformationSerializer(meta)
    data = serializer.data

    # Build display signature with † and $ decorators
    display_signature = signature.signature_text
    decorators = ""
    if meta.lost:
        decorators += "†"
    if meta.new_reading:
        decorators += "$"
    if decorators:
        display_signature += " " + decorators

    # Gather aliases
    aliases = list(Signature.objects.filter(parent=signature).values_list("signature_text", flat=True))

    context = {
        "signature": signature.signature_text,
        "display_signature": display_signature,
        "canonical_slug": canonical_slug,
        "aliases": aliases,
        "meta": meta,
        "data": data,
        "province_country": _province_country_for_signature(signature.signature_text),
    }
    return render(request, "runes/inscription_detail.html", context)
