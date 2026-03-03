import { describe, it, expect, vi, beforeEach } from "vitest";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

// Mock document.cookie for CSRF
Object.defineProperty(document, "cookie", {
  writable: true,
  value: "csrftoken=test-csrf-token",
});

// Import after mocks
import { api } from "../api/client";

beforeEach(() => {
  mockFetch.mockReset();
});

describe("api.listMemories", () => {
  it("returns array of memories", async () => {
    const memories = [{ id: "1", content: "test" }];
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(memories),
    });

    const result = await api.listMemories();
    expect(result).toEqual(memories);
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/memories/",
      expect.any(Object),
    );
  });
});

describe("api.createMemory", () => {
  it("sends POST with CSRF token", async () => {
    const memory = { id: "1", content: "new" };
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: () => Promise.resolve(memory),
    });

    await api.createMemory({ content: "new" });

    const [, options] = mockFetch.mock.calls[0];
    expect(options.method).toBe("POST");
    expect(options.headers["X-CSRFToken"]).toBe("test-csrf-token");
    expect(options.credentials).toBe("same-origin");
  });
});

describe("api.deleteMemory", () => {
  it("returns void on 204", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 204,
    });

    const result = await api.deleteMemory("123");
    expect(result).toBeUndefined();
  });
});

describe("error handling", () => {
  it("throws on non-OK response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      statusText: "Not Found",
      json: () => Promise.resolve({ error: "Memory not found." }),
    });

    await expect(api.getMemory("bad-id")).rejects.toThrow(
      "Memory not found.",
    );
  });
});
