# Extending Your Brain

## Add More MCP Tools

You can extend the MCP server with additional tools. Here are ideas:

- **`summarize_topic(topic)`:** Retrieve all memories about a topic and generate a summary.
- **`find_connections(memory_id)`:** Find memories semantically similar to a specific one.
- **`weekly_report()`:** Generate an automated weekly digest of all stored memories.
- **`store_from_url(url)`:** Scrape a webpage and store its content as a memory.
- **`export_brain()`:** Export all memories as JSON for backup.

## Ingest from More Sources

The open-brain Docker project supports ingestion from Telegram, WhatsApp, Gmail, and file uploads. For the Supabase approach, you can build similar ingestion pipelines using Edge Functions or simple Python scripts running on a schedule.

## Add a Dashboard

The Docker version includes a Streamlit dashboard. For the Supabase version, you can build a simple dashboard with:

- **Streamlit** (Python — easiest)
- **Next.js** + Supabase client library
- Any framework that can query PostgreSQL
