"""Management command: upload inscription PDFs to Azure Blob Storage and
create Reference links for each inscription.

Usage
-----
Dry run (no uploads, no DB writes):
    python manage.py upload_pdfs_to_azure --dry-run

Full run:
    python manage.py upload_pdfs_to_azure

Custom JSON file:
    python manage.py upload_pdfs_to_azure --json-file /path/to/inscriptions_pdfs.json

Authentication
--------------
Two modes, selected automatically:

1. **Azurite / local emulator** – set ``AZURE_BLOB_CONNECTION_STRING`` in your
   environment.  The well-known Azurite default string is::

     DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;\
     AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4\
     I6tq/K1SZFPTOtr/KBHBeksoGMGw==;\
     BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;

2. **Production (managed identity / az login)** – leave
   ``AZURE_BLOB_CONNECTION_STRING`` unset.  ``DefaultAzureCredential`` picks up
   credentials from ``az login`` locally and the app's managed identity in
   Azure.  ``AZURE_BLOB_BASE_URL`` must be set in this mode.

Stored reference format
-----------------------
``Reference(kind='link', text='<blob-filename>', label='Sveriges runinskrifter PDF')``

The blob filename (e.g. ``Öl_1.pdf``) is environment-agnostic.  User-facing
pages link to stable Rundata-owned URLs under ``PUBLIC_PDF_BASE_URL``; those
URLs redirect to the current storage backend configured by
``settings.AZURE_BLOB_BASE_URL``.
"""

import json
import os
from urllib.parse import urlparse

from azure.core.exceptions import ResourceExistsError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings, PublicAccess
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from rundatanet.runes.models import MetaInformation, Reference, Signature

PDF_LABEL = "Sveriges runinskrifter PDF"
PDF_CONTENT_TYPE = "application/pdf"


class Command(BaseCommand):
    help = (
        "Upload inscription PDFs to Azure Blob Storage and create Reference "
        "links for each inscription. Idempotent: already-uploaded blobs and "
        "already-linked references are skipped."
    )

    def add_arguments(self, parser):
        default_json = os.path.join(str(settings.ROOT_DIR), "pdfs_raw", "inscriptions_pdfs.json")
        default_pdfs_dir = os.path.join(str(settings.ROOT_DIR), "pdfs_raw", "all_pdfs")
        parser.add_argument(
            "--json-file",
            default=default_json,
            help=f"Path to inscriptions JSON file (default: {default_json})",
        )
        parser.add_argument(
            "--pdfs-dir",
            default=default_pdfs_dir,
            help=f"Directory containing the local PDF files to upload (default: {default_pdfs_dir})",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate the run without uploading or writing to the DB.",
        )

    def handle(self, *args, **options):
        json_path = options["json_file"]
        all_pdfs_dir = options["pdfs_dir"]
        dry_run = options["dry_run"]

        blob_base_url = settings.AZURE_BLOB_BASE_URL
        if not blob_base_url:
            raise CommandError(
                "AZURE_BLOB_BASE_URL is not configured. "
                "Set it in your environment or .env file.\n"
                "  Production:  https://<account>.blob.core.windows.net/<container>\n"
                "  Azurite:     http://127.0.0.1:10000/devstoreaccount1/<container>"
            )

        # Derive account URL and container name from AZURE_BLOB_BASE_URL so that
        # one setting covers both the frontend URL and server-side uploads.
        parsed = urlparse(blob_base_url)
        path_parts = parsed.path.strip("/").split("/")
        container = path_parts[-1]
        account_path = "/" + "/".join(path_parts[:-1]) if len(path_parts) > 1 else ""
        account_url = parsed._replace(path=account_path).geturl()

        connection_string = settings.AZURE_BLOB_CONNECTION_STRING
        if connection_string:
            self.stdout.write("Using connection string (Azurite / explicit credentials).")
            service = BlobServiceClient.from_connection_string(connection_string)
        else:
            self.stdout.write(f"Using DefaultAzureCredential, account URL: {account_url}")
            service = BlobServiceClient(account_url=account_url, credential=DefaultAzureCredential())

        container_client = service.get_container_client(container)

        # Create the container if it doesn't exist yet (idempotent).
        # Always ensure public blob-level read access so PDFs are URL-accessible.
        if not dry_run:
            try:
                container_client.create_container(public_access=PublicAccess.BLOB)
                self.stdout.write(f"Created container '{container}' with public blob access.")
            except ResourceExistsError:
                # Container already exists — ensure it has public access set.
                container_client.set_container_access_policy(signed_identifiers={}, public_access=PublicAccess.BLOB)
                self.stdout.write(f"Container '{container}' already exists; public access confirmed.")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no uploads or DB writes."))

        # Load JSON
        try:
            with open(json_path, encoding="utf-8") as f:
                entries = json.load(f)
        except FileNotFoundError:
            raise CommandError(f"JSON file not found: {json_path}")

        stats = {"uploaded": 0, "skipped_existing": 0, "skipped_missing": 0, "errors": 0}

        for entry in entries:
            inscription_id = entry.get("inscription")
            local_pdf = entry.get("local_pdf")

            # Skip entries without a PDF file
            if not local_pdf:
                stats["skipped_missing"] += 1
                continue

            local_path = os.path.join(all_pdfs_dir, local_pdf)
            if not os.path.isfile(local_path):
                stats["skipped_missing"] += 1
                continue

            # Look up the signature / meta
            try:
                signature = Signature.objects.get(signature_text=inscription_id)
            except Signature.DoesNotExist:
                self.stderr.write(f"  WARN: Signature not found for '{inscription_id}', skipping.")
                stats["errors"] += 1
                continue

            try:
                meta = signature.meta
            except MetaInformation.DoesNotExist:
                self.stderr.write(f"  WARN: MetaInformation not found for '{inscription_id}', skipping.")
                stats["errors"] += 1
                continue

            # Idempotency: if this blob filename is already linked to this
            # inscription as a Reference, nothing left to do.
            if meta.references.filter(text=local_pdf, kind=Reference.Kind.LINK).exists():
                stats["skipped_existing"] += 1
                continue

            if dry_run:
                self.stdout.write(f"  [dry-run] Would upload: {local_pdf} → {inscription_id}")
                stats["uploaded"] += 1
                continue

            # Upload blob (skip if already in Azure)
            blob_client = container_client.get_blob_client(local_pdf)
            try:
                with open(local_path, "rb") as f:
                    blob_client.upload_blob(
                        f,
                        overwrite=False,
                        content_settings=ContentSettings(content_type=PDF_CONTENT_TYPE),
                    )
            except ResourceExistsError:
                pass  # Blob already in Azure, proceed to link

            # Upsert Reference (text=blob filename, kind=link, label=display name)
            ref, _ = Reference.objects.get_or_create(
                text=local_pdf,
                defaults={"kind": Reference.Kind.LINK, "label": PDF_LABEL},
            )
            # Ensure label is up to date if the ref already existed without a label
            if ref.label != PDF_LABEL:
                ref.label = PDF_LABEL
                ref.save(update_fields=["label"])

            # Link to MetaInformation (add is idempotent on M2M)
            meta.references.add(ref)

            self.stdout.write(f"  Uploaded and linked: {local_pdf} → {inscription_id}")
            stats["uploaded"] += 1

        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. "
                f"Uploaded/linked: {stats['uploaded']}, "
                f"Already linked (skipped): {stats['skipped_existing']}, "
                f"File not found (skipped): {stats['skipped_missing']}, "
                f"Errors: {stats['errors']}"
            )
        )
