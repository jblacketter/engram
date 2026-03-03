import type {
  Memory,
  CreateMemoryRequest,
  UpdateMemoryRequest,
  SearchRequest,
  SearchResult,
  Stats,
  TagCount,
  HealthStatus,
} from "../types";

const API_BASE = "/api";

function getCsrfToken(): string {
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  return match ? match[1] : "";
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  // Include CSRF token for unsafe methods (required by SessionAuthentication)
  if (options?.method && options.method !== "GET") {
    headers["X-CSRFToken"] = getCsrfToken();
  }

  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "same-origin",
    headers: { ...headers, ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(error.error || error.detail || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  // Health
  health: () => request<HealthStatus>("/health/"),

  // Memories
  listMemories: () => request<Memory[]>("/memories/"),
  getMemory: (id: string) => request<Memory>(`/memories/${id}/`),
  createMemory: (data: CreateMemoryRequest) =>
    request<Memory>("/memories/", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateMemory: (id: string, data: UpdateMemoryRequest) =>
    request<Memory>(`/memories/${id}/`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteMemory: (id: string) =>
    request<void>(`/memories/${id}/`, { method: "DELETE" }),

  // Search
  search: (data: SearchRequest) =>
    request<SearchResult[]>("/search/", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Stats & Tags
  stats: () => request<Stats>("/stats/"),
  tags: () => request<TagCount[]>("/tags/"),
};
