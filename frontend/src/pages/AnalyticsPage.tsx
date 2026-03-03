import { useQuery } from "@tanstack/react-query";
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { api } from "../api/client";

const COLORS = [
  "#3b82f6",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#8b5cf6",
  "#ec4899",
];

export default function AnalyticsPage() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ["stats"],
    queryFn: api.stats,
  });

  if (isLoading) return <p className="text-gray-500 text-sm">Loading...</p>;
  if (!stats) return null;

  const sourceData = Object.entries(stats.by_source).map(([name, value]) => ({
    name,
    value,
  }));

  const tagData = stats.top_tags.slice(0, 10);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Analytics</h2>

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-sm text-gray-500">Total Memories</p>
          <p className="text-3xl font-bold text-gray-900">{stats.total}</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-sm text-gray-500">Sources</p>
          <p className="text-3xl font-bold text-gray-900">
            {Object.keys(stats.by_source).length}
          </p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-sm text-gray-500">Date Range</p>
          <p className="text-sm font-medium text-gray-900">
            {stats.date_range
              ? `${new Date(stats.date_range.earliest!).toLocaleDateString()} - ${new Date(stats.date_range.latest!).toLocaleDateString()}`
              : "N/A"}
          </p>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Source distribution */}
        {sourceData.length > 0 && (
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <h3 className="text-sm font-medium text-gray-700 mb-4">
              Source Distribution
            </h3>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={sourceData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  label={({ name, value }) => `${name} (${value})`}
                >
                  {sourceData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Top tags */}
        {tagData.length > 0 && (
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <h3 className="text-sm font-medium text-gray-700 mb-4">
              Top Tags
            </h3>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={tagData}>
                <XAxis dataKey="tag" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#3b82f6" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}
