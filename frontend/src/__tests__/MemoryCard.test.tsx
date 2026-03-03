import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import MemoryCard from "../components/MemoryCard";
import type { Memory } from "../types";

vi.mock("../api/client", () => ({
  api: {
    deleteMemory: vi.fn(),
  },
}));

const testMemory: Memory = {
  id: "test-id-123",
  content: "This is a test memory with some content.",
  source: "api",
  tags: ["python", "testing"],
  metadata: {},
  importance: 0.7,
  decay_factor: 1.0,
  access_count: 3,
  last_accessed: "2026-03-03T12:00:00Z",
  created_at: "2026-03-01T10:00:00Z",
  updated_at: "2026-03-02T14:00:00Z",
};

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("MemoryCard", () => {
  it("renders content", () => {
    renderWithProviders(<MemoryCard memory={testMemory} />);
    expect(screen.getByText(testMemory.content)).toBeInTheDocument();
  });

  it("renders source badge", () => {
    renderWithProviders(<MemoryCard memory={testMemory} />);
    expect(screen.getByText("api")).toBeInTheDocument();
  });

  it("renders tags", () => {
    renderWithProviders(<MemoryCard memory={testMemory} />);
    expect(screen.getByText("python")).toBeInTheDocument();
    expect(screen.getByText("testing")).toBeInTheDocument();
  });

  it("renders importance and access count", () => {
    renderWithProviders(<MemoryCard memory={testMemory} />);
    expect(screen.getByText("Importance: 0.7")).toBeInTheDocument();
    expect(screen.getByText("Views: 3")).toBeInTheDocument();
  });

  it("shows rrf_score when provided", () => {
    renderWithProviders(
      <MemoryCard memory={testMemory} showScore={0.0164} />,
    );
    expect(screen.getByText("0.016")).toBeInTheDocument();
  });

  it("renders edit and delete buttons", () => {
    renderWithProviders(<MemoryCard memory={testMemory} />);
    expect(screen.getByText("Edit")).toBeInTheDocument();
    expect(screen.getByText("Delete")).toBeInTheDocument();
  });
});
