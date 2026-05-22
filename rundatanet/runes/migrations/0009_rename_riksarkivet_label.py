"""Rename the Riksarkivet reference label to Swedish Runic Bibliography.

This migration updates only the human-readable label on link references.
Reference URLs (``text``) are intentionally left unchanged.
"""

from django.db import migrations


OLD_LABEL = "Riksarkivet"
NEW_LABEL = "Swedish Runic Bibliography"


def rename_reference_label(apps, schema_editor):
    Reference = apps.get_model("runes", "Reference")
    db_alias = schema_editor.connection.alias

    (
        Reference.objects.using(db_alias)
        .filter(kind="link", label=OLD_LABEL)
        .update(label=NEW_LABEL)
    )


def reverse_rename_reference_label(apps, schema_editor):
    Reference = apps.get_model("runes", "Reference")
    db_alias = schema_editor.connection.alias

    (
        Reference.objects.using(db_alias)
        .filter(kind="link", label=NEW_LABEL)
        .update(label=OLD_LABEL)
    )


class Migration(migrations.Migration):

    dependencies = [
        ("runes", "0008_add_liljegren_links"),
    ]

    operations = [
        migrations.RunPython(rename_reference_label, reverse_rename_reference_label),
    ]

