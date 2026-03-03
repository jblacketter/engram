# Troubleshooting

| Problem | Solution |
|---------|----------|
| Docker containers won't start | Check Docker Desktop is running. Run: `docker compose logs` |
| MCP tools not showing in Claude | Restart Claude Desktop after editing config. Check JSON syntax. |
| Search returns no results | Verify embeddings are being generated (check API key). Lower the `match_threshold`. |
| Embedding API errors | Check your OpenRouter API key. Verify the model name is correct. |
| Database connection refused | Ensure PostgreSQL is running on port 5432. Check `DB_PASSWORD` matches. |
| Vector dimension mismatch | Your embedding model's output dimension must match the `vector()` size in your schema. |
| Supabase URL issues | Ensure `https://` prefix, no trailing slash. Check project reference is correct. |
