"""Add stable Rundata citation links to every inscription."""

import re
import unicodedata

from django.db import migrations


BASE_URL = "https://rundata.info/inscription/"
LABEL = "Permanent link for citation"


def _normalize_signature(text):
    nfd = unicodedata.normalize("NFD", text)
    stripped = re.sub(r"[\u0300-\u036f]", "", nfd)
    lowered = stripped.lower()
    replaced = re.sub(r"[^a-z0-9-]", "-", lowered)
    collapsed = re.sub(r"-{2,}", "-", replaced)
    return collapsed.strip("-")


def _build_citation_link(signature_text):
    slug = _normalize_signature(signature_text)
    return f"{BASE_URL}{slug}/"


def add_permanent_citation_links(apps, schema_editor):
    MetaInformation = apps.get_model("runes", "MetaInformation")
    Reference = apps.get_model("runes", "Reference")

    db_alias = schema_editor.connection.alias

    for meta in MetaInformation.objects.using(db_alias).select_related("signature").all():
        url = _build_citation_link(meta.signature.signature_text)
        ref, _ = Reference.objects.using(db_alias).update_or_create(
            text=url,
            defaults={"kind": "link", "label": LABEL},
        )
        meta.references.add(ref)


def reverse_permanent_citation_links(apps, schema_editor):
    MetaInformation = apps.get_model("runes", "MetaInformation")
    Reference = apps.get_model("runes", "Reference")

    db_alias = schema_editor.connection.alias
    refs = Reference.objects.using(db_alias).filter(
        kind="link",
        label=LABEL,
        text__startswith=BASE_URL,
    )

    for meta in MetaInformation.objects.using(db_alias).prefetch_related("references").all():
        meta.references.remove(*refs)

    refs.filter(meta_informations__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("runes", "0009_rename_riksarkivet_label"),
    ]

    operations = [
        migrations.RunPython(add_permanent_citation_links, reverse_permanent_citation_links),
    ]
