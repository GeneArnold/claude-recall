# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Claude Recall is a lightweight MCP (Model Context Protocol) server that provides cross-project, semantically searchable memory for AI assistants. It runs as a stdio MCP server and stores memories in SQLite with vector embeddings for similarity search.

**Why it exists:** Claude Code's native memory is siloed per working directory and lacks semantic search. Claude Recall provides a single shared store any session or project can read and write via MCP tools.

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the MCP server (stdio transport — normally invoked by the MCP client)
python -m claude_recall

# Register with Claude Code (one-time setup)
claude mcp add-json claude-recall '{"command":"python","args":["-m","claude_recall"]}'
```

No test suite, linter config, or Makefile exists yet.

## Architecture

```
AI Client (Claude Code, Cursor, etc.)
    ↓  stdio / MCP protocol
server.py   — FastMCP server; 7 MCP tools
    ├─ db.py         — SQLite operations + numpy cosine similarity
    └─ embeddings.py — OpenAI-compatible embedding client
    ↓  file I/O
~/.claude-recall/memories.db
    ↓  HTTP
OpenAI / LiteLLM / Ollama  (embedding generation)
```

**Data flow for `search_memories`:** query text → embedding API → 1536-dim float vector → cosine similarity against all stored embeddings → ranked results. Brute-force numpy; fast for <1000 memories.

**Database:** Single SQLite file. WAL mode, 10 s busy timeout. Schema created on first connect — no migration tooling needed. Global `_conn` in `server.py` initializes it.

## Key Source Files

| File | Role |
|------|------|
| `claude_recall/server.py` | FastMCP server; all 7 MCP tool handlers |
| `claude_recall/db.py` | All SQLite reads/writes; cosine similarity scorer |
| `claude_recall/embeddings.py` | OpenAI SDK client; reads config + env vars |
| `claude_recall/__main__.py` | Stdio transport entry point |

## MCP Tools (7)

`save_memory`, `update_memory`, `delete_memory`, `get_memory`, `list_memories`, `search_memories`, `memory_stats`

## Memory Schema

```
id           UUID (auto)
name         Short identifier  e.g. "feedback_no_api_key"
description  One-line summary  — used for embeddings + relevance filtering
type         user | feedback | project | reference
content      Full markdown body
project      Working directory path or null (global)
embedding    JSON float array (1536 dims for text-embedding-3-small)
created_at / updated_at  ISO timestamps
```

## Configuration

Config file: `~/.claude-recall/config.json`

```json
{
  "base_url": "https://api.openai.com/v1",
  "api_key": "sk-...",
  "embedding_model": "text-embedding-3-small"
}
```

Environment overrides (take precedence over the config file):

| Env var | Config key |
|---------|-----------|
| `LITELLM_BASE_URL` | `base_url` |
| `LITELLM_API_KEY` | `api_key` |
| `EMBEDDING_MODEL` | `embedding_model` |
| `CLAUDE_RECALL_DB` | database file path (default: `~/.claude-recall/memories.db`) |

## Reference

`docs/claude-code-memory-deep-dive.md` — research doc on Claude Code's 4 memory layers and how Claude Recall fits in; explains directory-tree-walk scoping, the 200-line MEMORY.md limit, and why hooks were removed from v1.

`archive/v1-docker/` — historical v1 that used Docker + Postgres + pgvector; kept for reference only.
