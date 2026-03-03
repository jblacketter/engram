# Database Schema Deep Dive

Here is the core schema for a full-featured Open Brain database. You can start with just the `memories` table and add the others as your needs grow.

> The SQL for the core schema is in [`sql/schema.sql`](../sql/schema.sql).

## memories table

| Column | Type | Purpose |
|--------|------|---------|
| id | bigint (PK, auto) | Unique identifier |
| content | text | The actual text/thought/note |
| source | text | Where it came from (manual, telegram, email, meeting, etc.) |
| tags | text[] | Array of topic tags |
| entities | jsonb | Extracted entities (people, projects, etc.) |
| embedding | vector(1536) | Vector embedding for semantic search |
| created_at | timestamptz | When it was stored |
| updated_at | timestamptz | Last modification time |

## Optional: projects table

```sql
create table projects (
    id bigint primary key generated always as identity,
    name text not null unique,
    description text,
    status text default 'active',
    created_at timestamptz default now()
);
```

## Optional: people table

```sql
create table people (
    id bigint primary key generated always as identity,
    name text not null,
    context text,  -- who they are, how you know them
    created_at timestamptz default now()
);
```

## Key SQL Queries

**Semantic search** (find memories by meaning):

```sql
select id, content, source, tags,
       1 - (embedding <=> $1) as similarity
from memories
where 1 - (embedding <=> $1) > 0.7
order by embedding <=> $1
limit 10;
```

**Full-text search fallback** (keyword matching):

```sql
select * from memories
where content ilike '%search_term%'
order by created_at desc limit 20;
```

**Tag-based retrieval:**

```sql
select * from memories
where 'project-x' = any(tags)
order by created_at desc;
```
