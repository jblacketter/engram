from asgiref.sync import async_to_sync
from django.core.management.base import BaseCommand

from intelligence.memory_decay import run_decay


class Command(BaseCommand):
    help = "Recompute decay_factor for all memories"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Compute but don't save; print changes",
        )

    def handle(self, **options):
        dry_run = options.get("dry_run", False)
        changes = async_to_sync(run_decay)(dry_run=dry_run)

        if not changes:
            self.stdout.write("No decay changes needed.")
            return

        if dry_run:
            self.stdout.write("Dry run — no changes saved:\n")

        old_avg = sum(c["old"] for c in changes) / len(changes)
        new_avg = sum(c["new"] for c in changes) / len(changes)

        for change in changes[:20]:
            self.stdout.write(
                f"  {change['id']}: {change['old']:.4f} -> {change['new']:.4f}"
            )

        if len(changes) > 20:
            self.stdout.write(f"  ... and {len(changes) - 20} more")

        action = "Would update" if dry_run else "Updated"
        self.stdout.write(
            f"\n{action} {len(changes)} memories. "
            f"Avg decay: {old_avg:.4f} -> {new_avg:.4f}"
        )
