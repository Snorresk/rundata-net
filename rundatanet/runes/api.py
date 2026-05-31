import json
import logging
from typing import Any, Optional

from azure.core.exceptions import ServiceResponseTimeoutError
from django.conf import settings
from ninja import NinjaAPI, Schema

from .inference import inference
from .models import MetaInformation, Signature
from .normalization import SlugIndex, normalize_signature
from .serializers import MetaInformationSerializer

logger = logging.getLogger(__name__)

api = NinjaAPI(
    title="Rundata API",
    version="1.0.0",
    description=(
        "REST API for the Rundata runic inscription database. "
        "Provides endpoints for searching inscriptions, retrieving detailed metadata, "
        "and converting free-form text to normalized runic rules."
    ),
)


class TextRequest(Schema):
    text: str


class TextResponse(Schema):
    rules: str
    error: Optional[str] = None


class InscriptionResponse(Schema):
    signature: str
    canonical_slug: str
    aliases: list[str]
    meta: dict[str, Any]


class SearchOption(Schema):
    id: str
    title: str
    slug: str


class ErrorResponse(Schema):
    detail: str


@api.post("/txt2rules", response=TextResponse, tags=["Rules"])
def txt2rules(request, data: TextRequest):
    """
    Convert free-form text to normalized runic rules.

    Submits a plain-text description to the inference engine, which returns
    a structured rules string suitable for use in inscription searches.

    Returns an empty `rules` string and a populated `error` field if the
    inference step fails.
    """
    try:
        # Call the inference function to get the rules
        llm_response = inference(data.text)

        # Here you would call the function to convert text to rules
        resp = TextResponse(rules=llm_response)
    except ServiceResponseTimeoutError as e:
        logger.warning("Timed out while converting text to rules: %s", str(e), exc_info=True)
        resp = TextResponse(
            rules="",
            error="AI request timed out after 20 seconds. Please try again, or simplify the query."
        )
    except Exception as e:
        # Handle the exception and return an error response
        logger.error(f"Error converting text to rules: {str(e)}", exc_info=True)

        resp = TextResponse(rules="", error="Failed to convert text to rules")
    return resp


@api.get(
    "/search_options",
    response=list[SearchOption],
    tags=["Inscriptions"],
)
def search_options_api(request):
    """
    List all searchable inscription signatures.

    Returns every canonical runic signature as a lightweight option object
    containing an `id`, human-readable `title`, and URL-safe `slug`.
    Intended for populating client-side search datalists and autocomplete widgets.
    Results are sorted alphabetically by signature text.
    """
    index = SlugIndex.get()
    index._ensure_built()

    signatures = Signature.objects.filter(id__in=index._id_to_slug.keys()).values_list("id", "signature_text")

    options = [
        SearchOption(
            id=signature_text,
            title=signature_text,
            slug=index._id_to_slug[sig_id],
        )
        for sig_id, signature_text in signatures
        if sig_id in index._id_to_slug
    ]

    return sorted(options, key=lambda option: option.title)


@api.get(
    "/inscription/{slug}",
    response={200: InscriptionResponse, 404: ErrorResponse},
    tags=["Inscriptions"],
)
def inscription_detail_api(request, slug: str):
    """
    Retrieve full metadata for a single inscription by slug.

    Looks up an inscription using its URL-safe slug. Alias slugs (variant
    identifiers pointing to the same physical inscription) are resolved
    transparently to the canonical record.

    Returns the canonical signature text, canonical slug, a list of known
    alias signatures, and a full metadata object including material type,
    images, and references.

    Responds with **404** if the slug does not match any known inscription
    or if the associated metadata record is missing.
    """
    index = SlugIndex.get()
    result = index.resolve(slug)

    if result is None:
        return 404, {"detail": "Inscription not found"}

    canonical_id, canonical_slug = result

    try:
        signature = Signature.objects.get(id=canonical_id)
    except Signature.DoesNotExist:
        return 404, {"detail": "Inscription not found"}

    try:
        meta = (
            MetaInformation.objects.select_related("signature", "materialType")
            .prefetch_related("images", "references")
            .get(signature=signature)
        )
    except MetaInformation.DoesNotExist:
        return 404, {"detail": "Inscription metadata not found"}

    serializer = MetaInformationSerializer(meta)

    aliases = list(Signature.objects.filter(parent=signature).values_list("signature_text", flat=True))

    return 200, {
        "signature": signature.signature_text,
        "canonical_slug": canonical_slug,
        "aliases": aliases,
        "meta": serializer.data,
    }
