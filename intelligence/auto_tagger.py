import logging
import re
from collections import Counter
from uuid import UUID

from asgiref.sync import sync_to_async

from core.models import Memory
from intelligence.llm_client import OllamaUnavailableError, chat_json

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a tag extraction assistant. Given a piece of text, extract 3 to 8 concise, "
    "lowercase tags that capture the key topics. Return a JSON object with a single key "
    '"tags" whose value is an array of strings. Each tag should be a single word or '
    "hyphenated compound (e.g. \"machine-learning\"). Do not include generic words like "
    '"information", "topic", or "note".'
)

# fmt: off
STOP_WORDS = frozenset({
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "had", "her", "was",
    "one", "our", "out", "has", "have", "been", "some", "then", "them", "these", "this",
    "that", "with", "will", "each", "make", "like", "from", "just", "also", "more", "into",
    "over", "such", "than", "most", "what", "when", "which", "their", "about", "would",
    "there", "could", "other", "after", "should", "being", "where", "does", "doing",
    "during", "before", "between", "through", "very", "only", "here", "were", "they",
    "its", "how", "may", "use", "used", "using", "any", "many", "well", "way", "own",
    "because", "those", "while", "still", "both", "even", "same", "much", "need", "get",
    "back", "made", "work", "come", "good", "new", "first", "last", "long", "great", "old",
    "right", "big", "high", "small", "large", "next", "early", "young", "important", "few",
    "public", "bad", "sure", "want", "give", "day", "time", "year", "thing", "man", "world",
    "life", "hand", "part", "child", "eye", "woman", "place", "case", "point", "company",
    "number", "group", "problem", "fact", "able", "try", "ask", "end", "set", "another",
    "take", "keep", "let", "begin", "seem", "help", "show", "hear", "play", "run", "move",
    "live", "believe", "hold", "bring", "happen", "write", "provide", "sit", "stand", "lose",
    "pay", "meet", "include", "continue", "learn", "change", "lead", "understand",
})
# fmt: on


def _extract_tags_tfidf(content: str) -> list[str]:
    """Fallback: extract tags via simple term frequency."""
    words = re.findall(r"\b[a-z]{3,}\b", content.lower())
    filtered = [w for w in words if w not in STOP_WORDS]
    if not filtered:
        return []
    counts = Counter(filtered)
    return [word for word, _ in counts.most_common(5)]


def _validate_tags(raw: list) -> list[str]:
    """Validate and normalize LLM-extracted tags."""
    tags = []
    for item in raw:
        if not isinstance(item, str):
            continue
        tag = item.strip().lower()
        tag = re.sub(r"[^a-z0-9-]", "", tag)
        if len(tag) >= 2 and tag not in tags:
            tags.append(tag)
    return tags[:8]


async def extract_tags(content: str) -> list[str]:
    """Extract 3-8 tags from content. Tries Ollama LLM, falls back to TF-IDF."""
    try:
        result = await chat_json(SYSTEM_PROMPT, content)
        raw_tags = result.get("tags", [])
        if isinstance(raw_tags, list) and raw_tags:
            validated = _validate_tags(raw_tags)
            if validated:
                return validated
        logger.warning("LLM returned invalid tags, falling back to TF-IDF")
    except OllamaUnavailableError:
        logger.info("Ollama unavailable, using TF-IDF fallback for tagging")

    return _extract_tags_tfidf(content)


async def enrich_tags(memory_id: UUID) -> list[str]:
    """Load memory, extract tags, merge with existing tags, save. Returns final tag list."""
    memory = await sync_to_async(Memory.objects.get)(pk=memory_id)
    extracted = await extract_tags(memory.content)

    existing = set(memory.tags or [])
    merged = list(existing | set(extracted))

    if set(merged) != existing:
        memory.tags = merged
        await sync_to_async(memory.save)(update_fields=["tags", "updated_at"])

    return merged
