import json
from datetime import datetime

from asgiref.sync import sync_to_async

from core.managers import build_hybrid_query
from embeddings.registry import embed


async def search(
    query: str,
    limit: int = 10,
    tags: list[str] | None = None,
    source: str | None = None,
    after: datetime | None = None,
    before: datetime | None = None,
    semantic_weight: float = 0.5,
) -> list[dict]:
    """Hybrid search: vector similarity + BM25, fused via Reciprocal Rank Fusion."""
    query_vec = await embed(query)

    # Tags need JSON serialization for the jsonb @> operator
    serialized_tags = json.dumps(tags) if tags else None

    return await sync_to_async(build_hybrid_query)(
        query_vec=query_vec,
        query_text=query,
        limit=limit,
        tags=serialized_tags,
        source=source,
        after=after,
        before=before,
        semantic_weight=semantic_weight,
    )
