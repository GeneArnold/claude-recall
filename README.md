# Claude Recall

**Your AI's long-term memory.**

Claude Recall is a cross-project, cross-machine memory server for AI coding assistants. It gives your AI persistent memory with semantic search — so it remembers not just what you said, but what you meant.

Built as an [MCP](https://modelcontextprotocol.io/) (Model Context Protocol) server, it works with any MCP-compatible client: Claude Code, Cursor, Windsurf, Gemini, and more. Your memories aren't locked to one tool.

## Why This Exists

AI coding assistants have a memory problem. Claude Code, for example, stores memories as local markdown files scoped to whatever directory you launched from. That means:

- **Project A can't see Project B's memories** (unless they share a parent directory)
- **Machine A can't see Machine B's memories** (local files don't sync)
- **No search** — memories are loaded or they're not; there's no way to query "what do I know about API quirks?"
- **200-line limit** — only the first 200 lines of the memory index load per session

Claude Recall solves all four:

| Problem | Claude Recall's Answer |
|---|---|
| Cross-project | Single database, tagged by project, searchable across all |
| Cross-machine | One server, accessible from anywhere |
| No search | Semantic search via vector embeddings — "deployment preferences" finds memories about CI/CD |
| Size limits | No limit — the database grows as needed |

## How It Works

Claude Recall runs as an MCP server using **stdio transport**. That means there's no background server to manage — your AI client starts it automatically when a session begins and stops it when the session ends.

Memories are stored in a **SQLite database** at `~/.claude-recall/memories.db`. Every memory gets an embedding vector via your configured embedding API, enabling semantic similarity search at query time.

```
AI Client (Claude Code, Cursor, etc.)
    |
    | stdio (MCP protocol)
    v
Claude Recall (Python, started automatically)
    |
    | sqlite3 (built-in)          openai SDK
    v                              v
~/.claude-recall/memories.db    Embedding API (LiteLLM, OpenAI, etc.)
```

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/GeneArnold/claude-recall.git
cd claude-recall
pip install -r requirements.txt
```

### 2. Configure your embedding API

Create `~/.claude-recall/config.json`:

```json
{
  "base_url": "https://api.openai.com/v1",
  "api_key": "your-api-key",
  "embedding_model": "text-embedding-3-small"
}
```

Works with any OpenAI-compatible API: OpenAI directly, LiteLLM, Azure OpenAI, Ollama, etc.

### 3. Register with Claude Code

```bash
claude mcp add-json -s user claude-recall '{
  "type": "stdio",
  "command": "python3",
  "args": ["-m", "claude_recall"],
  "env": {"PYTHONPATH": "/path/to/claude-recall"}
}'
```

Replace `/path/to/claude-recall` with wherever you cloned the repo.

### 4. Restart Claude Code

That's it. Every session now has access to 7 memory tools. No Docker, no background server, no ports to manage.

## Memory Types

| Type | Purpose | Typical Scope |
|---|---|---|
| `user` | Who you are — role, preferences, expertise, personal details | Global |
| `feedback` | How you like to work — corrections, confirmed approaches | Global or project |
| `project` | Ongoing work context — goals, decisions, status, contacts | Project-specific |
| `reference` | Pointers to external resources, API quirks, environment details | Project-specific |

## MCP Tools

| Tool | Description |
|---|---|
| `save_memory` | Create a new memory with auto-generated embedding |
| `update_memory` | Modify an existing memory by ID or name (re-embeds on content change) |
| `delete_memory` | Remove a memory by ID or name |
| `get_memory` | Retrieve a specific memory by ID or name |
| `list_memories` | List/filter memories by type and/or project |
| `search_memories` | Semantic search — natural language queries ranked by relevance |
| `memory_stats` | Dashboard — counts by type, by project, recent activity |

## Memory Schema

| Field | Description |
|---|---|
| `id` | UUID, auto-generated |
| `name` | Short identifier (e.g., `feedback_no_api_key`) |
| `description` | One-line summary used for embedding and relevance matching |
| `type` | `user`, `feedback`, `project`, or `reference` |
| `content` | Full memory body, supports markdown |
| `project` | Working directory path, or null for global memories |
| `embedding` | Vector from your configured embedding model |
| `created_at` | ISO timestamp |
| `updated_at` | ISO timestamp |

## Configuration

### Config file: `~/.claude-recall/config.json`

```json
{
  "base_url": "https://api.openai.com/v1",
  "api_key": "sk-...",
  "embedding_model": "text-embedding-3-small"
}
```

### Environment variable overrides

| Variable | Overrides | Purpose |
|---|---|---|
| `LITELLM_BASE_URL` | `base_url` | Embedding API endpoint |
| `LITELLM_API_KEY` | `api_key` | API key |
| `EMBEDDING_MODEL` | `embedding_model` | Model name |
| `CLAUDE_RECALL_DB` | default db path | Custom database location |

### Database location

Default: `~/.claude-recall/memories.db`

Override with the `CLAUDE_RECALL_DB` environment variable.

### Backup

It's a single file. Copy it:

```bash
cp ~/.claude-recall/memories.db ~/.claude-recall/memories.db.backup
```

## Concurrency

Multiple AI sessions can use Claude Recall simultaneously. SQLite handles this via WAL (Write-Ahead Logging) mode with a 10-second busy timeout:

- **Multiple readers**: fully concurrent, no blocking
- **Multiple writers**: one at a time, others wait (typically milliseconds)
- **In practice**: memory writes take ~5-50ms; the chance of collision is negligible

## File Structure

```
claude-recall/
├── claude_recall/
│   ├── __init__.py          # Version
│   ├── __main__.py          # Entry point (stdio transport)
│   ├── server.py            # FastMCP server with 7 tools
│   ├── db.py                # SQLite operations + cosine similarity
│   └── embeddings.py        # Embedding API client
├── docs/
│   └── claude-code-memory-deep-dive.md   # Research on Claude Code's memory system
├── archive/
│   └── v1-docker/           # Original Docker+Postgres version (historical)
├── requirements.txt
├── README.md
└── TODO.md
```

---

## The Journey: How We Got Here

Claude Recall went through two major versions in one evening. Documenting the journey because the decisions matter more than the code.

### v1: Docker + Postgres + pgvector (April 1, 2026)

The original build was ambitious:

- **Docker Compose** with Postgres 17 + pgvector and a Python MCP server container
- **HTTP transport** — server running on port 8765, had to be started before Claude Code
- **PostToolUse hooks** on Write and Edit — automatically synced local memory files to the central database
- **Reconciliation system** — detected deleted memories by monitoring `MEMORY.md` changes
- **`source_file` tracking** — differentiated hook-synced memories from MCP-direct saves

It worked. We successfully tested saving, searching, editing, and deleting memories across two independent Claude Code sessions — including one session that didn't even have MCP enabled (it used local files, and the hooks silently synced them to Claude Recall).

### What we learned about Claude Code's memory

During the build, we discovered something important: **Claude Code's built-in memory isn't as siloed as we thought**.

Claude Code walks up the directory tree and loads memory from parent directories. So if you ever launched Claude Code from `~/Workspace/`, every project under that directory shares a memory scope. This is by design — it creates a natural hierarchy:

```
Global:     ~/.claude/CLAUDE.md                        (all projects)
Workspace:  ~/.claude/projects/-...-Workspace/memory/  (all projects under Workspace/)
Project:    ~/.claude/projects/-...-my-app/memory/     (just this project)
```

This meant the hooks were solving a problem that was already **partially solved** natively. The hooks added significant complexity:

- **Dual-write duplication** — sessions with MCP could save a memory AND trigger a hook write, creating two copies
- **Silent failures** — if Docker was down, syncs failed silently with no retry
- **Fragile parsing** — reconciliation depended on regex-parsing `MEMORY.md` links
- **Delete detection** — required tracking `source_file` and diffing against the index

### The pivot: what Claude Recall actually needed to solve

After the research, we identified four things local memory can't do:

1. **Bridge unrelated directory trees** — projects in different paths have zero shared memory
2. **Semantic search** — local memory has no search capability at all
3. **Cross-machine memory** — local files are machine-specific
4. **Intentional scoping** — local memory scope is an accident of launch directory; Claude Recall scopes explicitly

None of these require hooks. They require a **direct MCP tool** that the AI calls intentionally.

### v2: SQLite + stdio (April 2, 2026)

We stripped everything down:

| v1 (Docker) | v2 (Standalone) |
|---|---|
| Docker + Postgres + pgvector | SQLite (built-in, zero dependencies) |
| HTTP transport (server must be running) | stdio (started/stopped automatically) |
| pgvector for vector search | Cosine similarity in Python (numpy) |
| PostToolUse hooks for sync | No hooks — direct MCP tools only |
| Reconciliation system for deletes | Delete via MCP tool directly |
| 4 Docker containers | 0 background processes |
| `docker compose up` before every session | Nothing — just works |
| Backup = pg_dump cron | Backup = copy one 696KB file |

### Why we dropped the hooks

The hooks were clever engineering but violated a principle we established during the build:

> "Memories are meant to help, not harm. I would rather this work 95% of the time one way than 75% and try to have it all."

The hooks tried to have it all — sync every local memory file to the central store, detect deletes, prevent duplicates. Each edge case required more code, more fragile logic, and more ways to produce bad data. An LLM acting on stale or duplicated memory is worse than an LLM with no memory.

The clean model: **local auto-memory handles per-project context natively. Claude Recall handles cross-project, cross-machine, searchable memory via direct MCP tools.** Two systems, separate concerns, no sync layer between them.

### Why we dropped Docker

Docker was overkill for a personal tool with ~20 memories:

- **Startup dependency** — had to remember to `docker compose up` before every Claude Code session
- **pgvector** — designed for millions of vectors; we had 18
- **Container rebuilds** — every code change required a rebuild
- **Postgres connections** — stale connections after restarts, needed reconnection logic

SQLite eliminated every reliability concern:
- No connections to go stale (file-based)
- No server to keep running (stdio transport)
- No startup order dependency (starts automatically)
- Backup is copying one file
- Cosine similarity on 1,000 vectors takes <10ms in Python

### Why we dropped pgvector for numpy

At the scale of personal memory (hundreds, maybe low thousands of memories), brute-force cosine similarity in Python is instant. pgvector's IVFFlat indexing is built for datasets in the millions. Using it for 18 memories was like driving a semi truck to the corner store.

```python
# This is all the "vector database" we need
def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
```

If the memory count ever reaches tens of thousands, we can revisit. Until then, numpy is plenty.

---

## Understanding Claude Code's Memory System

We wrote a detailed research document during this project: [`docs/claude-code-memory-deep-dive.md`](docs/claude-code-memory-deep-dive.md)

Key findings:

- Claude Code has four memory layers: CLAUDE.md (instructions), auto-memory (learned context), settings, and MCP memory
- Auto-memory walks up the directory tree — parent directories create shared memory scopes
- `MEMORY.md` loads first 200 lines at session start; individual files load on demand
- Auto-Dream consolidates memory in the background after 24 hours and 5+ sessions
- `autoMemoryDirectory` setting lets you override the memory path (user/local settings only)

---

## Compatibility

Claude Recall is an MCP server. It works with any MCP-compatible client:

- **Claude Code** (CLI, desktop, web, IDE extensions)
- **Cursor**
- **Windsurf**
- **Any tool supporting MCP stdio transport**

The memory data is stored in a standard SQLite database. It's portable, inspectable with any SQLite client, and easy to back up or migrate.

## Requirements

- Python 3.10+
- An OpenAI-compatible embedding API (OpenAI, LiteLLM, Azure OpenAI, Ollama, etc.)
- ~700KB disk space per 20 memories (mostly embeddings)

## License

MIT

---

*Built in one evening, April 1-2, 2026. Started as a Docker+Postgres beast, ended as a single SQLite file that just works.*
