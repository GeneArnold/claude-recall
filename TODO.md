# Claude Recall — Roadmap

## Next Up

- [ ] **Global CLAUDE.md** — create `~/.claude/CLAUDE.md` with instructions telling all sessions about Claude Recall and when to use it vs local memory

- [ ] **Bulk import tool** — MCP tool or script to import existing local memory files from `~/.claude/projects/*/memory/` across all projects. Useful for bootstrapping or after a database reset.

- [ ] **Multi-machine access** — expose Claude Recall to the network so the Linux machine can use the same memory store. Requires adding auth (API key or token).

## Quality of Life

- [ ] **Memory staleness** — flag or auto-archive memories not accessed in N days. Consider an `accessed_at` field that updates on read.

- [ ] **Better stats** — oldest memory, memories by age, never-accessed memories. Help identify dead weight.

- [ ] **Tag/label support** — optional tags beyond the 4 types for cross-project themes (e.g., "databricks", "compliance", "demo").

- [ ] **Dedup guard** — before creating a new memory, check if one with very similar content already exists (high cosine similarity).

- [ ] **Export to markdown** — dump all memories back to `.md` files for portability.

## Future

- [ ] **Logo** — Claude's sparkle merged with a brain silhouette
- [ ] **pip installable** — `pyproject.toml` so it can be installed as a proper package
- [ ] **Embedding model swap** — re-embed everything when switching models
- [ ] **Web UI** — read-only dashboard to browse memories (nice to have, not critical)

## Archived

### Hooks (removed April 2, 2026)

PostToolUse hooks on Write/Edit that auto-synced local memory files to Claude Recall. Included a reconciliation system for detecting deletes via `MEMORY.md` changes and a `source_file` field for deduplication.

**Why removed**: After researching how Claude Code's auto-memory actually works (directory tree walk, parent-scope sharing), the hooks were solving a problem that was partially solved natively. The complexity they introduced (dual-write duplication, silent failures, fragile MEMORY.md parsing, delete reconciliation) wasn't worth the benefit. Claude Recall's value is as a direct MCP tool, not a sync layer.

Code preserved in `archive/v1-docker/` for reference.

### Docker + Postgres + pgvector (replaced April 2, 2026)

Original infrastructure using Docker Compose with Postgres 17 + pgvector and HTTP MCP transport.

**Why replaced**: Docker had to be running before every Claude Code session (startup order dependency), Postgres connections went stale on restart, pgvector was overkill for <100 memories, and container rebuilds were slow. SQLite + stdio eliminated every reliability concern.

Code preserved in `archive/v1-docker/` for reference.

## Decisions Log

| Date | Decision | Reasoning |
|---|---|---|
| 2026-04-01 | Postgres + pgvector | Semantic search needed, Docker already planned |
| 2026-04-01 | text-embedding-3-small | Fast, cheap, 1536 dims is plenty |
| 2026-04-01 | Hooks (Write + Edit) | Sync local memory files to central store |
| 2026-04-01 | source_file field | Match hook-synced memories for dedup/reconciliation |
| 2026-04-02 | **Hooks removed** | Native auto-memory partially solves cross-project; hooks added too many edge cases |
| 2026-04-02 | **SQLite replaced Postgres** | Overkill for personal use; SQLite eliminates startup/connection/backup issues |
| 2026-04-02 | **stdio replaced HTTP** | No background server needed; Claude Code starts/stops it automatically |
| 2026-04-02 | **numpy replaced pgvector** | Brute-force cosine similarity is instant at our scale (<1000 memories) |
