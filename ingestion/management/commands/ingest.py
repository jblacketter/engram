"""Management command for CLI-driven ingestion."""

from django.core.management.base import BaseCommand, CommandError

from asgiref.sync import async_to_sync


class Command(BaseCommand):
    help = "Ingest files, URLs, or Obsidian vaults into the memory system."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--file", type=str, help="Path to a file to ingest")
        group.add_argument("--url", type=str, help="URL to scrape and ingest")
        group.add_argument("--vault", type=str, help="Path to an Obsidian vault directory")

        parser.add_argument("--source", type=str, default=None, help="Override source label")
        parser.add_argument("--tags", type=str, default="", help="Comma-separated additional tags")

    def handle(self, *args, **options):
        tags = [t.strip() for t in options["tags"].split(",") if t.strip()] if options["tags"] else []

        if options["file"]:
            self._ingest_file(options["file"], options["source"], tags)
        elif options["url"]:
            self._ingest_url(options["url"], options["source"], tags)
        elif options["vault"]:
            self._ingest_vault(options["vault"], options["source"], tags)

    def _ingest_file(self, file_path, source, tags):
        from ingestion.file_ingestor import ingest_file

        source = source or "import"
        try:
            results = async_to_sync(ingest_file)(
                file_path=file_path,
                source=source,
                tags=tags,
            )
        except Exception as exc:
            raise CommandError(str(exc))

        ok = sum(1 for r in results if r["status"] == "ok")
        self.stdout.write(f"Ingested {file_path}: {ok} memories created")

    def _ingest_url(self, url, source, tags):
        from ingestion.url_scraper import scrape_url

        source = source or "url"
        try:
            results = async_to_sync(scrape_url)(
                url=url,
                source=source,
                tags=tags,
            )
        except Exception as exc:
            raise CommandError(str(exc))

        ok = sum(1 for r in results if r["status"] == "ok")
        self.stdout.write(f"Ingested {url}: {ok} memories created")

    def _ingest_vault(self, vault_path, source, tags):
        from ingestion.obsidian_importer import import_vault

        source = source or "obsidian"
        try:
            results = async_to_sync(import_vault)(
                vault_path=vault_path,
                source=source,
                extra_tags=tags,
            )
        except Exception as exc:
            raise CommandError(str(exc))

        ok_count = sum(1 for r in results if r["status"] == "ok")
        err_count = sum(1 for r in results if r["status"] == "error")
        files = len(set(r.get("file", "") for r in results))
        self.stdout.write(f"Ingested {files} files from vault: {ok_count} memories created")
        if err_count:
            self.stderr.write(f"  {err_count} errors occurred")
            for r in results:
                if r["status"] == "error":
                    self.stderr.write(f"  - {r.get('file', '?')}: {r.get('error', '?')}")
