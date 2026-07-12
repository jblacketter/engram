from asgiref.sync import async_to_sync
from django.core.management.base import BaseCommand

from core.services import memory_service
from intelligence.memory_decay import run_decay
from intelligence.report_generator import generate_report


class Command(BaseCommand):
    help = (
        "Scheduled upkeep: recompute memory decay, and with --digest also "
        "generate the periodic report and store it as a type:digest memory "
        "(owner-surface only; embedded locally — digests aggregate private "
        "content). Intended for cron/launchd or the compose scheduler "
        "profile. Exits non-zero on failure."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--digest", action="store_true",
            help="Also generate the digest report and store it as a memory",
        )
        parser.add_argument(
            "--days", type=int, default=7,
            help="Digest window in days (default 7)",
        )

    def handle(self, *args, **options):
        try:
            changes = async_to_sync(run_decay)()
            self.stdout.write(f"decay: {len(changes)} memories updated")
        except Exception as exc:
            self.stderr.write(f"decay failed: {type(exc).__name__}: {exc}")
            raise SystemExit(1)

        if not options["digest"]:
            return

        try:
            report = async_to_sync(generate_report)(days=options["days"])
            memory = async_to_sync(memory_service.create_memory)(
                content=report,
                source="maintenance",
                tags=["type:digest"],
                allow_cloud_fallback=False,
            )
            self.stdout.write(f"digest: stored as memory {memory.id}")
            self.stdout.write(report)
        except Exception as exc:
            self.stderr.write(f"digest failed: {type(exc).__name__}: {exc}")
            raise SystemExit(1)
