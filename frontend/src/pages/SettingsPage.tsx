import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export default function SettingsPage() {
  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 30_000,
  });

  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: api.stats,
  });

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Settings</h2>

      {/* Health status */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-3">
        <h3 className="text-sm font-medium text-gray-700">System Health</h3>
        {healthLoading ? (
          <p className="text-gray-500 text-sm">Checking...</p>
        ) : health ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span
                className={`w-3 h-3 rounded-full ${
                  health.status === "ok" ? "bg-green-500" : "bg-red-500"
                }`}
              />
              <span className="text-sm text-gray-800">
                Status: {health.status}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span
                className={`w-3 h-3 rounded-full ${
                  health.database ? "bg-green-500" : "bg-red-500"
                }`}
              />
              <span className="text-sm text-gray-800">
                Database: {health.database ? "Connected" : "Disconnected"}
              </span>
            </div>
          </div>
        ) : (
          <p className="text-red-500 text-sm">Could not reach server.</p>
        )}
      </div>

      {/* System info */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-3">
        <h3 className="text-sm font-medium text-gray-700">System Info</h3>
        <div className="text-sm text-gray-800 space-y-1">
          <p>
            Total memories: {stats?.total ?? "..."}
          </p>
          <p>
            Sources:{" "}
            {stats
              ? Object.keys(stats.by_source).join(", ") || "none"
              : "..."}
          </p>
        </div>
      </div>

      {/* API docs link */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-3">
        <h3 className="text-sm font-medium text-gray-700">
          API Documentation
        </h3>
        <a
          href="/api/docs/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-blue-600 hover:text-blue-800 underline"
        >
          Open Swagger UI
        </a>
      </div>
    </div>
  );
}
