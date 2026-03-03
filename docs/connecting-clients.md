# Connecting Multiple AI Tools

One of the biggest advantages of this system is that it works with any MCP-compatible client. Here's how to connect the most popular ones:

## Claude Desktop

See [Docker Setup](setup-docker.md#step-3-connect-claude-desktop) or [Supabase Setup](setup-supabase.md#step-4-run-and-connect) for the `claude_desktop_config.json` setup.

## Claude Code (Terminal)

```bash
# Add via CLI
claude mcp add open-brain http://localhost:8080/mcp
```

Or add to `.claude/settings.json` in your project:

```json
{
  "mcpServers": {
    "open-brain": {
      "url": "http://localhost:8080/mcp"
    }
  }
}
```

## Cursor / Windsurf / VS Code

Most MCP-compatible editors use a similar config pattern. Check your editor's MCP documentation and point it to your server URL or command.

```json
// Cursor: .cursor/mcp.json in your project root
{
  "mcpServers": {
    "open-brain": {
      "url": "http://localhost:8080/mcp"
    }
  }
}
```

## Custom Python Client

You can also query the REST API directly from any application:

```python
import httpx

# Store a memory
httpx.post("http://localhost:8000/memories", json={
    "content": "Important insight from today",
    "source": "manual",
    "tags": ["insight"]
})

# Search
results = httpx.get("http://localhost:8000/search",
    params={"query": "insights", "limit": 5})
```
