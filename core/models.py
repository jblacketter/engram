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


class AgentKey(models.Model):
    """Per-agent API key with domain binding (Phase 12: agent-scoping).

    The plaintext secret (egk_...) is shown exactly once at creation and
    never stored — only its SHA-256 hex. allowed_domains always contains
    default_domain (enforced at the service layer).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.SlugField(max_length=50, unique=True)
    key_hash = models.CharField(max_length=64, unique=True, db_index=True)
    default_domain = models.CharField(max_length=100)
    allowed_domains = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"AgentKey {self.name} (default={self.default_domain})"
