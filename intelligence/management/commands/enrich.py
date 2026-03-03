from uuid import UUID

from asgiref.sync import async_to_sync
from django.core.management.base import BaseCommand
from django.db.models import Q

from core.models import Memory
from intelligence.auto_tagger import enrich_tags
from intelligence.entity_extractor import enrich_entities


class Command(BaseCommand):
    help = "Enrich memories with auto-generated tags and entities"

    def add_arguments(self, parser):
        parser.add_argument("--id", type=str, help="Enrich a single memory by UUID")
        parser.add_argument(
            "--all", action="store_true",
            help="Enrich unenriched memories (empty tags or missing entities)",
        )
        parser.add_argument("--source", type=str, help="Enrich memories from a specific source")
        parser.add_argument(
            "--tags-only", action="store_true", help="Only extract tags, skip entities"
        )
        parser.add_argument(
            "--entities-only", action="store_true", help="Only extract entities, skip tags"
        )

    def handle(self, **options):
        memory_id = options.get("id")
        enrich_all = options.get("all")
        source = options.get("source")
        tags_only = options.get("tags_only")
        entities_only = options.get("entities_only")

        if memory_id:
            memories = Memory.objects.filter(pk=UUID(memory_id))
        elif source:
            memories = Memory.objects.filter(source=source)
        elif enrich_all:
            memories = Memory.objects.filter(
                Q(tags=[]) | ~Q(metadata__has_key="entities")
            )
        else:
            self.stderr.write("Specify --id, --all, or --source")
            return

        total = memories.count()
        if total == 0:
            self.stdout.write("No memories to enrich.")
            return

        enriched = 0
        for memory in memories.iterator():
            try:
                if not entities_only:
                    async_to_sync(enrich_tags)(memory.id)
                if not tags_only:
                    async_to_sync(enrich_entities)(memory.id)
                enriched += 1
                self.stdout.write(f"Enriched {enriched}/{total} memories", ending="\r")
                self.stdout.flush()
            except Exception as exc:
                self.stderr.write(f"\nFailed to enrich {memory.id}: {exc}")

        self.stdout.write(f"\nEnriched {enriched}/{total} memories")
