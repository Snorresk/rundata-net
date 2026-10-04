"""Tests for the 0010_add_permanent_citation_links data migration."""

import importlib.util
import os

import django.apps
from django.db import connections
from django.test import TestCase

from rundatanet.runes.models import MetaInformation, Reference, Signature

_migration_path = os.path.join(
    os.path.dirname(__file__),
    "..",
    "migrations",
    "0010_add_permanent_citation_links.py",
)
_spec = importlib.util.spec_from_file_location("migration_0010", _migration_path)
_migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_migration)
add_permanent_citation_links = _migration.add_permanent_citation_links
reverse_permanent_citation_links = _migration.reverse_permanent_citation_links


class _SchemaEditor:
    connection = connections["runes_db"]


class PermanentCitationLinksTests(TestCase):
    """Unit tests for adding permanent citation links."""

    databases = {"default", "runes_db"}

    def setUp(self):
        self.sig = Signature.objects.using("runes_db").create(signature_text="Öl 1")
        self.meta = MetaInformation.objects.using("runes_db").create(
            signature=self.sig,
            found_location="Karlevi",
        )
        self.sig2 = Signature.objects.using("runes_db").create(signature_text="Ög F7;54")
        self.meta2 = MetaInformation.objects.using("runes_db").create(
            signature=self.sig2,
            found_location="Test",
        )

    def _run(self):
        add_permanent_citation_links(django.apps.apps, _SchemaEditor())

    def test_creates_permanent_citation_links(self):
        self._run()

        ref = self.meta.references.get(text="https://rundata.info/inscription/ol-1/")
        assert ref.kind == "link"
        assert ref.label == "Permanent link for citation"

        assert self.meta2.references.filter(
            text="https://rundata.info/inscription/og-f7-54/",
            kind="link",
            label="Permanent link for citation",
        ).exists()

    def test_second_run_does_not_duplicate_references(self):
        self._run()
        self._run()

        refs = Reference.objects.using("runes_db").filter(
            text="https://rundata.info/inscription/ol-1/",
        )
        assert refs.count() == 1
        assert self.meta.references.filter(pk=refs.get().pk).count() == 1

    def test_existing_link_label_is_updated(self):
        ref = Reference.objects.using("runes_db").create(
            text="https://rundata.info/inscription/ol-1/",
            kind="link",
            label="Old label",
        )
        self.meta.references.add(ref)

        self._run()

        ref.refresh_from_db()
        assert ref.label == "Permanent link for citation"

    def test_reverse_removes_only_permanent_citation_links(self):
        self._run()
        other = Reference.objects.using("runes_db").create(
            text="https://rundata.info/about/",
            kind="link",
            label="Other",
        )
        self.meta.references.add(other)

        reverse_permanent_citation_links(django.apps.apps, _SchemaEditor())

        assert not self.meta.references.filter(text="https://rundata.info/inscription/ol-1/").exists()
        assert self.meta.references.filter(pk=other.pk).exists()
