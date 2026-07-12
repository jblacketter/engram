from pathlib import Path

from asgiref.sync import async_to_sync
from django.core.management.base import BaseCommand

from core.services import tagteam_ingest


class Command(BaseCommand):
    help = (
        "Ingest APPROVED tagteam cycles from a repo's rendered JSONL exports "
        "(docs/handoffs/*_rounds.jsonl). Prerequisite: refresh exports with "
        "`tagteam cycle render --phase <phase> --type <plan|impl>` in the "
        "target repo. Tagteam's database is never read; engram never writes "
        "tagteam state."
    )

    def add_arguments(self, parser):
        parser.add_argument("--repo", required=True, help="Path to the target repository")
        parser.add_argument(
            "--domain", default=None,
            help="Domain slug for the summaries (default: repo directory name)",
        )

    def handle(self, *args, **options):
        repo = Path(options["repo"]).expanduser()
        if not repo.is_dir():
            self.stderr.write(f"not a readable directory: {repo}")
            raise SystemExit(1)
        report = async_to_sync(tagteam_ingest.ingest_repo)(repo, options["domain"])
        if report["files"] == 0:
            self.stdout.write(self.style.WARNING(
                f"no rendered exports found under {repo}/docs/handoffs/ — "
                "they may be absent or stale; refresh with "
                "`tagteam cycle render --phase <phase> --type <plan|impl>`"
            ))
        for outcome in ("created", "updated", "skipped", "not_approved", "errors"):
            entries = report[outcome]
            self.stdout.write(f"{outcome}: {len(entries)}")
            for entry in entries:
                self.stdout.write(f"  {entry}")
        self.stdout.write(f"malformed_lines: {report['malformed_lines']}")
        if report["errors"]:
            raise SystemExit(1)
