# Claude Recall — Roadmap

## In Progress

- [ ] **Global CLAUDE.md** — create `~/.claude/CLAUDE.md` with instructions telling all sessions about Claude Recall and when to use it vs local memory

## Up Next

### Core Features

- [ ] **Web UI** — browser-based dashboard to browse, search, edit, and delete memories. Read/write access. Makes it easy to audit what your AI knows about you without needing a terminal.

- [ ] **Model switcher** — easily change embedding models from the config or Web UI. Include a re-embed command that regenerates all vectors when switching models (e.g., from `text-embedding-3-small` to `text-embedding-3-large` or a local model via Ollama).

- [ ] **Bulk import** — MCP tool or CLI command to import existing local memory files from `~/.claude/projects/*/memory/` across all projects. Useful for bootstrapping or after a database reset.

- [ ] **Multi-machine access** — expose Claude Recall over the network so multiple machines can share the same memory store. Requires adding authentication (API key or token).

### Reliability

- [ ] **Dedup guard** — before creating a new memory, check if one with very similar content already exists (high cosine similarity + same project). Prevent accidental duplicates.

- [ ] **Memory validation** — reject saves with empty content, invalid types, or names that are too long. Fail gracefully with clear error messages.

- [ ] **Automated backup** — optional scheduled backup of the SQLite database to a configurable location. Could be as simple as a cron-friendly CLI command: `python -m claude_recall backup`

### Quality of Life

- [ ] **Memory staleness tracking** — add an `accessed_at` field that updates on read. Flag or auto-archive memories not accessed in N days. Help identify dead weight.

- [ ] **Tags/labels** — optional tags beyond the 4 types for cross-cutting themes (e.g., "databricks", "compliance", "demo", "debugging"). Filterable in search and list.

- [ ] **Memory pinning** — mark critical memories as "pinned" so they're always surfaced in relevant searches regardless of similarity score.

- [ ] **Export to markdown** — dump all memories back to `.md` files with frontmatter. Useful for portability, version control, or migrating between machines.

- [ ] **Import from markdown** — read a directory of `.md` files with frontmatter and import them. Inverse of export. Enables sharing memory sets.

- [ ] **CLI interface** — command-line tool for managing memories without an AI session. `claude-recall search "API patterns"`, `claude-recall list --type feedback`, `claude-recall stats`, `claude-recall backup`.

### Platform Expansion

- [ ] **pip installable** — `pyproject.toml` so it can be `pip install claude-recall` from PyPI. Makes setup a one-liner.

- [ ] **HTTP transport mode** — optional `--http` flag to run as a persistent HTTP server (for network/multi-machine use). stdio remains the default for local use.

- [ ] **Cursor integration guide** — document how to register Claude Recall as an MCP server in Cursor.

- [ ] **Windsurf integration guide** — document how to register in Windsurf.

- [ ] **Gemini / other clients** — document MCP registration for any client that supports the protocol.

### Polish

- [ ] **Logo** — Claude's sparkle merged with a brain silhouette

- [ ] **Landing page** — simple GitHub Pages site explaining what Claude Recall is and why it exists

- [ ] **Demo GIF** — terminal recording showing save, search, and cross-session recall in action

- [ ] **Contributing guide** — for when/if this goes public and others want to help

## Ideas (not committed)

- **Memory categories/folders** — organize memories into user-defined categories beyond the 4 types
- **Memory relationships** — link related memories (e.g., "this feedback applies to this project")
- **Semantic dedup on save** — automatically merge similar memories instead of creating duplicates
- **Memory usage analytics** — which memories are searched most, which are never accessed
- **Ollama embedding support** — zero-API-key setup using local embeddings (already works if Ollama exposes an OpenAI-compatible endpoint)
- **Memory sharing** — export a curated set of memories as a shareable package (e.g., "here's my API reference set for this project")
- **Webhook on memory change** — notify external systems when memories are created/updated/deleted
- **Vector index** — if memory count exceeds 10,000+, add FAISS or hnswlib for faster search (unnecessary at current scale)

## Archived

### Hooks (removed April 2, 2026)

PostToolUse hooks on Write/Edit that auto-synced local memory files to Claude Recall. Included a reconciliation system for detecting deletes via `MEMORY.md` changes and a `source_file` field for deduplication.

**Why removed**: After researching how Claude Code's auto-memory actually works (directory tree walk, parent-scope sharing), the hooks were solving a problem that was partially solved natively. The complexity they introduced (dual-write duplication, silent failures, fragile MEMORY.md parsing, delete reconciliation) wasn't worth the benefit.

### Docker + Postgres + pgvector (replaced April 2, 2026)

Original infrastructure using Docker Compose with Postgres 17 + pgvector and HTTP MCP transport.

**Why replaced**: Overkill for a personal memory tool. SQLite + stdio eliminated every reliability concern — no startup order dependency, no stale connections, no container rebuilds, backup is copying one file.

Code for both preserved in `archive/v1-docker/` for reference.

## Decisions Log

| Date | Decision | Reasoning |
|---|---|---|
| 2026-04-01 | Postgres + pgvector | Semantic search needed, Docker already planned |
| 2026-04-01 | text-embedding-3-small | Fast, cheap, 1536 dims is plenty |
| 2026-04-01 | Hooks (Write + Edit) | Sync local memory files to central store |
| 2026-04-02 | **Hooks removed** | Native auto-memory partially solves cross-project; hooks too many edge cases |
| 2026-04-02 | **SQLite replaced Postgres** | Overkill for personal use; eliminates startup/connection/backup issues |
| 2026-04-02 | **stdio replaced HTTP** | No background server; AI client starts/stops it automatically |
| 2026-04-02 | **numpy replaced pgvector** | Brute-force cosine similarity instant at <1000 memories |
