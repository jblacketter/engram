# Contributing to Engram

Thanks for your interest in contributing! This guide will help you get started.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/jblacketter/engram.git
cd engram

# Start PostgreSQL and Ollama
docker compose up -d

# Pull the embedding model
ollama pull nomic-embed-text

# Install Python dependencies (with dev extras)
pip install -e ".[dev]"

# Run migrations
python manage.py migrate

# Start the development servers
python manage.py runserver        # REST API on :8000
python -m mcp_server              # MCP server on :8080
```

## Running Tests

```bash
# Run all tests
pytest

# Run a specific test file
pytest tests/test_mcp_tools.py

# Run with coverage
pytest --cov=. --cov-report=term-missing
```

Note: Some tests require a running PostgreSQL instance with pgvector. The Docker Compose dev setup provides this.

## Making Changes

1. **Fork** the repository and create a branch from `main`
2. **Write tests** for any new functionality
3. **Run the test suite** to make sure nothing is broken
4. **Keep commits focused** — one logical change per commit
5. **Open a pull request** with a clear description of what changed and why

## Code Style

- Python code follows standard PEP 8 conventions
- Use type hints for function signatures
- Keep functions focused and reasonably sized
- Write docstrings for public APIs

## Reporting Issues

Use the GitHub issue templates:
- **Bug reports:** Include steps to reproduce, expected vs. actual behavior, and your environment
- **Feature requests:** Describe the problem you're trying to solve and your proposed solution

## Questions?

Open a discussion on GitHub or file an issue. We're happy to help.
