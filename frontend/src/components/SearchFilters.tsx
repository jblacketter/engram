import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

interface SearchFiltersProps {
  selectedTags: string[];
  onTagsChange: (tags: string[]) => void;
  source: string;
  onSourceChange: (source: string) => void;
  after: string;
  onAfterChange: (date: string) => void;
  before: string;
  onBeforeChange: (date: string) => void;
  semanticWeight: number;
  onSemanticWeightChange: (weight: number) => void;
}

export default function SearchFilters({
  selectedTags,
  onTagsChange,
  source,
  onSourceChange,
  after,
  onAfterChange,
  before,
  onBeforeChange,
  semanticWeight,
  onSemanticWeightChange,
}: SearchFiltersProps) {
  const [open, setOpen] = useState(false);
  const { data: tags } = useQuery({ queryKey: ["tags"], queryFn: api.tags });
  const { data: stats } = useQuery({ queryKey: ["stats"], queryFn: api.stats });

  const toggleTag = (tag: string) => {
    if (selectedTags.includes(tag)) {
      onTagsChange(selectedTags.filter((t) => t !== tag));
    } else {
      onTagsChange([...selectedTags, tag]);
    }
  };

  const sources = stats ? Object.keys(stats.by_source) : [];

  return (
    <div className="bg-white rounded-lg border border-gray-200">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-4 py-2 text-sm font-medium text-gray-700 text-left flex items-center justify-between"
      >
        Filters
        <span className="text-gray-400">{open ? "\u2212" : "+"}</span>
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-4 border-t border-gray-100">
          {/* Semantic weight slider */}
          <div className="pt-3">
            <label className="text-xs font-medium text-gray-600 block mb-1">
              Search Mode
            </label>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400">Keyword</span>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={semanticWeight}
                onChange={(e) =>
                  onSemanticWeightChange(parseFloat(e.target.value))
                }
                className="flex-1"
              />
              <span className="text-xs text-gray-400">Semantic</span>
            </div>
          </div>

          {/* Tags */}
          {tags && tags.length > 0 && (
            <div>
              <label className="text-xs font-medium text-gray-600 block mb-1">
                Tags
              </label>
              <div className="flex flex-wrap gap-1">
                {tags.map((t) => (
                  <span
                    key={t.tag}
                    onClick={() => toggleTag(t.tag)}
                    className={`inline-block px-2 py-0.5 text-xs font-medium rounded-full cursor-pointer ${
                      selectedTags.includes(t.tag)
                        ? "bg-blue-600 text-white"
                        : "bg-blue-100 text-blue-800 hover:bg-blue-200"
                    }`}
                  >
                    {t.tag} ({t.count})
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Source */}
          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1">
              Source
            </label>
            <select
              value={source}
              onChange={(e) => onSourceChange(e.target.value)}
              className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
            >
              <option value="">All sources</option>
              {sources.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          {/* Date range */}
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="text-xs font-medium text-gray-600 block mb-1">
                After
              </label>
              <input
                type="date"
                value={after}
                onChange={(e) => onAfterChange(e.target.value)}
                className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
              />
            </div>
            <div className="flex-1">
              <label className="text-xs font-medium text-gray-600 block mb-1">
                Before
              </label>
              <input
                type="date"
                value={before}
                onChange={(e) => onBeforeChange(e.target.value)}
                className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
