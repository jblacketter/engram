import uuid

from django.conf import settings
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from pgvector.django import HnswIndex, VectorField


class Memory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content = models.TextField()
    embedding = VectorField(dimensions=settings.VECTOR_DIMENSIONS)

    # Full-text search — maintained by a PostgreSQL trigger (see migration)
    content_tsv = SearchVectorField(null=True)

    source = models.CharField(
        max_length=50,
        default="manual",
        db_index=True,
    )
    tags = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    # Decay / importance scoring
    importance = models.FloatField(default=0.5)
    decay_factor = models.FloatField(default=1.0)
    access_count = models.IntegerField(default=0)
    last_accessed = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            HnswIndex(
                name="memory_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
            models.Index(fields=["-created_at"], name="memory_created_at_idx"),
        ]

    def __str__(self):
        return f"Memory {self.id}: {self.content[:80]}"
