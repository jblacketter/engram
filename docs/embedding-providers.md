# Embedding Providers Compared

The embedding provider generates the vector representations of your text. Here are your options:

| Provider | Cost | Quality | Privacy | Setup |
|----------|------|---------|---------|-------|
| **OpenRouter (recommended)** | Free tier available | High (routes to OpenAI models) | Data sent to API | Easiest — just an API key |
| **OpenAI direct** | ~$0.02 per 1M tokens | Highest | Data sent to OpenAI | API key from platform.openai.com |
| **Ollama (local)** | Free (runs on your hardware) | Good (model-dependent) | 100% private | Install Ollama, pull a model |
| **Cohere** | Free tier (1000 calls/min) | High | Data sent to Cohere | API key from cohere.com |

## Using Ollama for Free Local Embeddings

If you want 100% free and private embeddings, install Ollama and pull an embedding model:

```bash
# Install Ollama (ollama.ai)
ollama pull nomic-embed-text

# Ollama serves embeddings on localhost:11434
# Modify your embedder.py to call:
# POST http://localhost:11434/api/embeddings
# {"model": "nomic-embed-text", "prompt": "your text"}
```

`nomic-embed-text` produces 768-dimensional vectors, so you'd change your SQL schema to use `vector(768)` instead of `vector(1536)`.
