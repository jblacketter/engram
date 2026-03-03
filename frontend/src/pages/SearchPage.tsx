import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { SearchRequest } from "../types";
import MemoryCard from "../components/MemoryCard";
import SearchFilters from "../components/SearchFilters";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [source, setSource] = useState("");
  const [after, setAfter] = useState("");
  const [before, setBefore] = useState("");
  const [semanticWeight, setSemanticWeight] = useState(0.5);

  // Debounce query input
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 300);
    return () => clearTimeout(timer);
  }, [query]);

  const searchRequest: SearchRequest | null = debouncedQuery
    ? {
        query: debouncedQuery,
        ...(selectedTags.length > 0 && { tags: selectedTags }),
        ...(source && { source }),
        ...(after && { after: new Date(after).toISOString() }),
        ...(before && { before: new Date(before).toISOString() }),
        semantic_weight: semanticWeight,
      }
    : null;

  const {
    data: results,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["search", searchRequest],
    queryFn: () => api.search(searchRequest!),
    enabled: !!searchRequest,
  });

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <h2 className="text-2xl font-bold text-gray-900">Search</h2>

      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search your memories..."
        className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />

      <SearchFilters
        selectedTags={selectedTags}
        onTagsChange={setSelectedTags}
        source={source}
        onSourceChange={setSource}
        after={after}
        onAfterChange={setAfter}
        before={before}
        onBeforeChange={setBefore}
        semanticWeight={semanticWeight}
        onSemanticWeightChange={setSemanticWeight}
      />

      {isLoading && <p className="text-gray-500 text-sm">Searching...</p>}
      {error && (
        <p className="text-red-500 text-sm">Error: {error.message}</p>
      )}

      <div className="space-y-3">
        {results?.map((result) => (
          <MemoryCard
            key={result.id}
            memory={{
              ...result,
              decay_factor: 1.0,
              access_count: 0,
              last_accessed: null,
            }}
            showScore={result.rrf_score}
            onTagClick={(tag) => {
              if (!selectedTags.includes(tag)) {
                setSelectedTags([...selectedTags, tag]);
              }
            }}
          />
        ))}
        {results?.length === 0 && debouncedQuery && (
          <p className="text-gray-400 text-sm text-center py-8">
            No results found.
          </p>
        )}
      </div>
    </div>
  );
}
