import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Memory } from "../types";
import TagBadge from "./TagBadge";
import MemoryForm from "./MemoryForm";

interface MemoryCardProps {
  memory: Memory;
  showScore?: number;
  onTagClick?: (tag: string) => void;
}

export default function MemoryCard({
  memory,
  showScore,
  onTagClick,
}: MemoryCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const queryClient = useQueryClient();

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteMemory(memory.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["memories"] });
    },
  });

  const handleDelete = () => {
    if (window.confirm("Delete this memory?")) {
      deleteMutation.mutate();
    }
  };

  if (editing) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <MemoryForm
          memory={memory}
          onSuccess={() => setEditing(false)}
          onCancel={() => setEditing(false)}
        />
      </div>
    );
  }

  const truncated = memory.content.length > 200 && !expanded;

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p
            className="text-gray-800 text-sm whitespace-pre-wrap cursor-pointer"
            onClick={() => setExpanded(!expanded)}
          >
            {truncated
              ? memory.content.slice(0, 200) + "..."
              : memory.content}
          </p>
        </div>
        {showScore !== undefined && (
          <span className="shrink-0 text-xs font-mono bg-green-100 text-green-800 px-2 py-0.5 rounded">
            {showScore.toFixed(3)}
          </span>
        )}
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs font-medium bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
          {memory.source}
        </span>
        {memory.tags.map((tag) => (
          <TagBadge
            key={tag}
            tag={tag}
            onClick={onTagClick ? () => onTagClick(tag) : undefined}
          />
        ))}
      </div>

      <div className="flex items-center justify-between text-xs text-gray-400">
        <div className="flex items-center gap-3">
          <span>Importance: {memory.importance.toFixed(1)}</span>
          <span>Views: {memory.access_count}</span>
          <span>{new Date(memory.created_at).toLocaleDateString()}</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setEditing(true)}
            className="text-blue-500 hover:text-blue-700"
          >
            Edit
          </button>
          <button
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
            className="text-red-500 hover:text-red-700"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}
