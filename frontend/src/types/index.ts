export interface Memory {
  id: string;
  content: string;
  source: string;
  tags: string[];
  metadata: Record<string, unknown>;
  importance: number;
  decay_factor: number;
  access_count: number;
  last_accessed: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateMemoryRequest {
  content: string;
  source?: string;
  tags?: string[];
  metadata?: Record<string, unknown>;
  importance?: number;
}

export interface UpdateMemoryRequest {
  content?: string;
  tags?: string[];
  metadata?: Record<string, unknown>;
  importance?: number;
}

export interface SearchRequest {
  query: string;
  limit?: number;
  tags?: string[];
  source?: string;
  after?: string;
  before?: string;
  semantic_weight?: number;
}

export interface SearchResult
  extends Pick<
    Memory,
    | "id"
    | "content"
    | "source"
    | "tags"
    | "metadata"
    | "importance"
    | "created_at"
    | "updated_at"
  > {
  rrf_score: number;
}

export interface Stats {
  total: number;
  by_source: Record<string, number>;
  top_tags: { tag: string; count: number }[];
  date_range: { earliest: string | null; latest: string | null } | null;
}

export interface TagCount {
  tag: string;
  count: number;
}

export interface HealthStatus {
  status: string;
  database: boolean;
}
