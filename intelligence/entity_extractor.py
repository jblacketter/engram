import logging
import re
from uuid import UUID

from asgiref.sync import sync_to_async

from core.models import Memory
from intelligence.llm_client import OllamaUnavailableError, chat_json

logger = logging.getLogger(__name__)

ENTITY_CATEGORIES = ("people", "projects", "organizations", "technologies")

SYSTEM_PROMPT = (
    "You are a named entity extraction assistant. Given a piece of text, identify named "
    "entities in four categories. Return a JSON object with exactly these keys: "
    '"people", "projects", "organizations", "technologies". Each value must be an array of '
    "strings. If a category has no matches, use an empty array. Only include clearly "
    "identifiable entities, not generic descriptions."
)

# Known technology terms for regex fallback
KNOWN_TECH = frozenset({
    "python", "javascript", "typescript", "rust", "golang", "java", "ruby", "swift",
    "kotlin", "react", "vue", "angular", "svelte", "django", "flask", "fastapi", "rails",
    "express", "nextjs", "nuxt", "postgres", "postgresql", "mysql", "mongodb", "redis",
    "sqlite", "elasticsearch", "docker", "kubernetes", "terraform", "ansible", "nginx",
    "apache", "linux", "macos", "windows", "aws", "gcp", "azure", "heroku", "vercel",
    "github", "gitlab", "bitbucket", "graphql", "grpc", "websocket", "tailwind", "vite",
    "webpack", "node", "deno", "bun", "ollama", "pytorch", "tensorflow", "pandas", "numpy",
    "langchain", "openai", "anthropic", "claude", "chatgpt", "llm", "mcp", "pgvector",
})


def _extract_entities_regex(content: str) -> dict[str, list[str]]:
    """Fallback: extract entities via regex heuristics."""
    entities: dict[str, list[str]] = {cat: [] for cat in ENTITY_CATEGORIES}

    # Technologies: match known terms (case-insensitive)
    words_lower = set(re.findall(r"\b[a-zA-Z][a-zA-Z0-9+#.-]*\b", content))
    for word in words_lower:
        if word.lower() in KNOWN_TECH:
            normalized = word.lower()
            if normalized not in entities["technologies"]:
                entities["technologies"].append(normalized)

    # People / Organizations: capitalized multi-word sequences (2-4 words)
    capitalized = re.findall(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b", content)
    for name in capitalized:
        if name not in entities["people"]:
            entities["people"].append(name)

    return entities


def _validate_entities(raw: dict) -> dict[str, list[str]]:
    """Validate and normalize LLM-extracted entities."""
    result: dict[str, list[str]] = {}
    for cat in ENTITY_CATEGORIES:
        items = raw.get(cat, [])
        if not isinstance(items, list):
            result[cat] = []
            continue
        validated = []
        for item in items:
            if isinstance(item, str) and item.strip():
                val = item.strip()
                if val not in validated:
                    validated.append(val)
        result[cat] = validated
    return result


async def extract_entities(content: str) -> dict[str, list[str]]:
    """Extract named entities. Returns dict with people, projects, organizations, technologies."""
    try:
        result = await chat_json(SYSTEM_PROMPT, content)
        if isinstance(result, dict) and any(cat in result for cat in ENTITY_CATEGORIES):
            validated = _validate_entities(result)
            if any(validated[cat] for cat in ENTITY_CATEGORIES):
                return validated
        logger.warning("LLM returned invalid entities, falling back to regex")
    except OllamaUnavailableError:
        logger.info("Ollama unavailable, using regex fallback for entity extraction")

    return _extract_entities_regex(content)


def _merge_entities(
    existing: dict[str, list[str]], new: dict[str, list[str]]
) -> dict[str, list[str]]:
    """Merge two entity dicts, taking the union per category."""
    merged: dict[str, list[str]] = {}
    for cat in ENTITY_CATEGORIES:
        existing_set = set(existing.get(cat, []))
        new_set = set(new.get(cat, []))
        merged[cat] = sorted(existing_set | new_set)
    return merged


async def enrich_entities(memory_id: UUID) -> dict[str, list[str]]:
    """Load memory, extract entities, store in metadata['entities'], save."""
    memory = await sync_to_async(Memory.objects.get)(pk=memory_id)
    extracted = await extract_entities(memory.content)

    existing = memory.metadata.get("entities", {})
    merged = _merge_entities(existing, extracted)

    metadata = dict(memory.metadata)
    metadata["entities"] = merged
    memory.metadata = metadata
    await sync_to_async(memory.save)(update_fields=["metadata", "updated_at"])

    return merged
