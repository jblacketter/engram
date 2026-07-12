from asgiref.sync import async_to_sync
from django.core.management.base import BaseCommand

from core.services import identity_service


class Command(BaseCommand):
    help = (
        "Sync identity files into engram (deterministic per-file provenance, "
        "local-only embedding by default). Default run is non-destructive: "
        "orphans and duplicate sets are reported only."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--prune", action="store_true",
            help="Delete orphaned identity_sync records (files removed from "
                 "the identity directory). Restricted to identity-sync "
                 "provenance rows; never touches organic memories.",
        )
        parser.add_argument(
            "--repair-duplicates", action="store_true",
            help="For files with multiple identity_sync rows, keep the "
                 "canonical row (latest updated_at) and delete the extras. "
                 "Content update happens on the next ordinary sync.",
        )

    def handle(self, *args, **options):
        root = identity_service.identity_root()
        if not root.is_dir():
            self.stderr.write(
                f"identity directory not found: {root} — run "
                "`python manage.py init_identity` first"
            )
            raise SystemExit(1)
        report = async_to_sync(identity_service.sync)(
            root,
            prune=options["prune"],
            repair_duplicates=options["repair_duplicates"],
        )
        for outcome in (
            "created", "updated", "skipped", "orphaned",
            "duplicates", "rejected", "errors", "pruned", "repaired",
        ):
            entries = report[outcome]
            self.stdout.write(f"{outcome}: {len(entries)}")
            for entry in entries:
                self.stdout.write(f"  {entry}")
        if report["errors"]:
            raise SystemExit(1)
