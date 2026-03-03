from django.db import connection


HYBRID_SEARCH_SQL = """\
WITH vector_leg AS (
    SELECT id,
           ROW_NUMBER() OVER (ORDER BY embedding <=> %(query_vec)s::vector) AS v_rank
    FROM core_memory
    WHERE 1=1 {vector_filters}
    ORDER BY embedding <=> %(query_vec)s::vector
    LIMIT %(pool_size)s
),
bm25_leg AS (
    SELECT id,
           ROW_NUMBER() OVER (
               ORDER BY ts_rank_cd(content_tsv, plainto_tsquery('english', %(query_text)s)) DESC
           ) AS t_rank
    FROM core_memory
    WHERE content_tsv @@ plainto_tsquery('english', %(query_text)s)
      {bm25_filters}
    LIMIT %(pool_size)s
),
fused AS (
    SELECT COALESCE(v.id, b.id) AS id,
           v.v_rank,
           b.t_rank,
           (COALESCE(1.0 / (60 + v.v_rank), 0) * %(sem_weight)s +
            COALESCE(1.0 / (60 + b.t_rank), 0) * %(kw_weight)s
           ) AS rrf_score
    FROM vector_leg v
    FULL OUTER JOIN bm25_leg b ON v.id = b.id
)
SELECT m.id, m.content, m.source, m.tags, m.metadata,
       m.importance, m.decay_factor, m.access_count,
       m.last_accessed, m.created_at, m.updated_at,
       f.rrf_score::double precision
FROM fused f
JOIN core_memory m ON m.id = f.id
ORDER BY f.rrf_score DESC
LIMIT %(limit)s;
"""


def build_hybrid_query(
    query_vec: list[float],
    query_text: str,
    limit: int = 10,
    tags: list[str] | None = None,
    source: str | None = None,
    after=None,
    before=None,
    semantic_weight: float = 0.5,
) -> list[dict]:
    """Execute hybrid search and return result dicts."""
    params: dict = {
        "query_vec": str(query_vec),
        "query_text": query_text,
        "pool_size": limit * 3,
        "limit": limit,
        "sem_weight": semantic_weight,
        "kw_weight": 1.0 - semantic_weight,
    }

    vector_filter_clauses = []
    bm25_filter_clauses = []

    if tags:
        # Memory must have ALL of these tags — jsonb @> operator
        params["filter_tags"] = tags
        clause = "AND tags @> %(filter_tags)s::jsonb"
        vector_filter_clauses.append(clause)
        bm25_filter_clauses.append(clause)

    if source:
        params["filter_source"] = source
        clause = "AND source = %(filter_source)s"
        vector_filter_clauses.append(clause)
        bm25_filter_clauses.append(clause)

    if after:
        params["filter_after"] = after
        clause = "AND created_at >= %(filter_after)s"
        vector_filter_clauses.append(clause)
        bm25_filter_clauses.append(clause)

    if before:
        params["filter_before"] = before
        clause = "AND created_at <= %(filter_before)s"
        vector_filter_clauses.append(clause)
        bm25_filter_clauses.append(clause)

    sql = HYBRID_SEARCH_SQL.format(
        vector_filters="\n      ".join(vector_filter_clauses),
        bm25_filters="\n      ".join(bm25_filter_clauses),
    )

    columns = [
        "id", "content", "source", "tags", "metadata",
        "importance", "decay_factor", "access_count",
        "last_accessed", "created_at", "updated_at",
        "rrf_score",
    ]

    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        rows = cursor.fetchall()

    return [dict(zip(columns, row)) for row in rows]
