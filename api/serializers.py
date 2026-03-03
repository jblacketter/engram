from rest_framework import serializers

from core.models import Memory


class MemorySerializer(serializers.ModelSerializer):
    """Read serializer — full memory representation."""

    class Meta:
        model = Memory
        fields = [
            "id",
            "content",
            "source",
            "tags",
            "metadata",
            "importance",
            "decay_factor",
            "access_count",
            "last_accessed",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class MemoryCreateSerializer(serializers.Serializer):
    """Write serializer — create a new memory."""

    content = serializers.CharField(max_length=50000)
    source = serializers.CharField(max_length=50, default="api")
    tags = serializers.ListField(
        child=serializers.CharField(max_length=100), max_length=20, required=False
    )
    metadata = serializers.JSONField(required=False)
    importance = serializers.FloatField(min_value=0.0, max_value=1.0, default=0.5)


class MemoryUpdateSerializer(serializers.Serializer):
    """Write serializer — partial update."""

    content = serializers.CharField(max_length=50000, required=False)
    tags = serializers.ListField(
        child=serializers.CharField(max_length=100), max_length=20, required=False
    )
    metadata = serializers.JSONField(required=False)
    importance = serializers.FloatField(min_value=0.0, max_value=1.0, required=False)


class SearchRequestSerializer(serializers.Serializer):
    """Input for hybrid search."""

    query = serializers.CharField()
    limit = serializers.IntegerField(min_value=1, max_value=100, default=10)
    tags = serializers.ListField(child=serializers.CharField(), required=False)
    source = serializers.CharField(required=False)
    after = serializers.DateTimeField(required=False)
    before = serializers.DateTimeField(required=False)
    semantic_weight = serializers.FloatField(min_value=0.0, max_value=1.0, default=0.5)


class SearchResultSerializer(serializers.Serializer):
    """Output for hybrid search — memory fields + rrf_score."""

    id = serializers.UUIDField()
    content = serializers.CharField()
    source = serializers.CharField()
    tags = serializers.ListField()
    metadata = serializers.JSONField()
    importance = serializers.FloatField()
    rrf_score = serializers.FloatField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


# --- Ingestion serializers ---


class IngestFileSerializer(serializers.Serializer):
    """Input for file ingestion endpoint (multipart upload)."""

    source = serializers.CharField(max_length=50, default="import")
    tags = serializers.JSONField(required=False)
    importance = serializers.FloatField(min_value=0.0, max_value=1.0, default=0.5)


class IngestURLSerializer(serializers.Serializer):
    """Input for URL ingestion endpoint."""

    url = serializers.URLField()
    source = serializers.CharField(max_length=50, default="url")
    tags = serializers.ListField(
        child=serializers.CharField(max_length=100), max_length=20, required=False
    )
    importance = serializers.FloatField(min_value=0.0, max_value=1.0, default=0.5)


class IngestBatchItemSerializer(serializers.Serializer):
    """Single item in a batch ingestion request."""

    type = serializers.ChoiceField(choices=["file", "url"])
    # URL fields
    url = serializers.URLField(required=False)
    # File fields (base64)
    content_base64 = serializers.CharField(required=False)
    filename = serializers.CharField(required=False)
    # Common fields
    source = serializers.CharField(max_length=50, required=False)
    tags = serializers.ListField(
        child=serializers.CharField(max_length=100), max_length=20, required=False
    )
    importance = serializers.FloatField(min_value=0.0, max_value=1.0, default=0.5)


class IngestBatchSerializer(serializers.Serializer):
    """Input for batch ingestion endpoint."""

    items = IngestBatchItemSerializer(many=True)
