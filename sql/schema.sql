-- Reference DDL for Engram — mirrors core/migrations/0001_initial.py.
-- Table name is core_memory (Django convention: appname_modelname).
-- Vector dimension (768) must stay in sync with settings.VECTOR_DIMENSIONS.
-- Requires PostgreSQL 13+ (gen_random_uuid is built-in, no pgcrypto needed).

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE core_memory (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    content text NOT NULL,
    embedding vector(768) NOT NULL,
    content_tsv tsvector,

    source varchar(50) NOT NULL DEFAULT 'manual',
    tags jsonb NOT NULL DEFAULT '[]'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,

    importance double precision NOT NULL DEFAULT 0.5,
    decay_factor double precision NOT NULL DEFAULT 1.0,
    access_count integer NOT NULL DEFAULT 0,
    last_accessed timestamptz,

    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Note: Django manages id via Python uuid4 and timestamps via auto_now/auto_now_add.
-- The DB-level defaults above are for standalone use outside Django.

-- Trigger: keep content_tsv in sync with content
CREATE OR REPLACE FUNCTION core_memory_tsv_trigger() RETURNS trigger AS $$
BEGIN
    NEW.content_tsv := to_tsvector('english', NEW.content);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER core_memory_content_tsv_update
    BEFORE INSERT OR UPDATE OF content ON core_memory
    FOR EACH ROW EXECUTE FUNCTION core_memory_tsv_trigger();

-- Indexes
CREATE INDEX memory_embedding_hnsw ON core_memory
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX memory_content_tsv_gin ON core_memory USING gin (content_tsv);
CREATE INDEX memory_tags_gin ON core_memory USING gin (tags);
CREATE INDEX core_memory_source_idx ON core_memory (source);
CREATE INDEX memory_created_at_idx ON core_memory (created_at DESC);
