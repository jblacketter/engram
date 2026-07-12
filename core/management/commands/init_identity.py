from django.core.management.base import BaseCommand

from core.services import identity_service


class Command(BaseCommand):
    help = (
        "Scaffold the identity directory (ENGRAM_IDENTITY_DIR) with "
        "commented placeholder templates. Never overwrites existing files; "
        "authoritative content is written by you, not by tooling."
    )

    def handle(self, *args, **options):
        root = identity_service.identity_root()
        created = identity_service.scaffold(root)
        if created:
            for relpath in created:
                self.stdout.write(f"created {root / relpath}")
        else:
            self.stdout.write(f"nothing to do — {root} already scaffolded")
        self.stdout.write(
            "Next: edit identity.md (and context/, projects/) yourself, "
            "then run `python manage.py sync_identity`."
        )
