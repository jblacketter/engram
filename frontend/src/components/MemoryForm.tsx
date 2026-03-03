import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Memory } from "../types";

interface MemoryFormProps {
  memory?: Memory;
  onSuccess?: () => void;
  onCancel?: () => void;
}

export default function MemoryForm({
  memory,
  onSuccess,
  onCancel,
}: MemoryFormProps) {
  const [content, setContent] = useState(memory?.content ?? "");
  const [tags, setTags] = useState(memory?.tags.join(", ") ?? "");
  const [importance, setImportance] = useState(memory?.importance ?? 0.5);
  const [source, setSource] = useState(memory?.source ?? "dashboard");
  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: api.createMemory,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["memories"] });
      setContent("");
      setTags("");
      setImportance(0.5);
      onSuccess?.();
    },
  });

  const updateMutation = useMutation({
    mutationFn: (data: Parameters<typeof api.updateMemory>[1]) =>
      api.updateMemory(memory!.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["memories"] });
      onSuccess?.();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) return;

    const parsedTags = tags
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);

    if (memory) {
      updateMutation.mutate({
        content,
        tags: parsedTags.length > 0 ? parsedTags : undefined,
        importance,
      });
    } else {
      createMutation.mutate({
        content,
        source,
        tags: parsedTags.length > 0 ? parsedTags : undefined,
        importance,
      });
    }
  };

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="What do you want to remember?"
        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm resize-y min-h-[80px] focus:outline-none focus:ring-2 focus:ring-blue-500"
        required
      />
      <div className="flex gap-3 flex-wrap">
        <input
          type="text"
          value={tags}
          onChange={(e) => setTags(e.target.value)}
          placeholder="Tags (comma-separated)"
          className="flex-1 min-w-[150px] px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        {!memory && (
          <input
            type="text"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder="Source"
            className="w-32 px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        )}
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-500">Importance:</label>
          <input
            type="range"
            min="0"
            max="1"
            step="0.1"
            value={importance}
            onChange={(e) => setImportance(parseFloat(e.target.value))}
            className="w-20"
          />
          <span className="text-xs text-gray-500 w-6">
            {importance.toFixed(1)}
          </span>
        </div>
      </div>
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={isPending || !content.trim()}
          className="px-4 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          {isPending ? "Saving..." : memory ? "Update" : "Save Memory"}
        </button>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-1.5 text-gray-600 text-sm rounded-lg hover:bg-gray-100"
          >
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
