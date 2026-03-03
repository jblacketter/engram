import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import MemoryCard from "../components/MemoryCard";
import MemoryForm from "../components/MemoryForm";

export default function HomePage() {
  const {
    data: memories,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["memories"],
    queryFn: api.listMemories,
  });

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Memories</h2>

      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <MemoryForm />
      </div>

      {isLoading && <p className="text-gray-500 text-sm">Loading...</p>}
      {error && (
        <p className="text-red-500 text-sm">Error: {error.message}</p>
      )}

      <div className="space-y-3">
        {memories?.map((memory) => (
          <MemoryCard key={memory.id} memory={memory} />
        ))}
        {memories?.length === 0 && (
          <p className="text-gray-400 text-sm text-center py-8">
            No memories yet. Create one above.
          </p>
        )}
      </div>
    </div>
  );
}
