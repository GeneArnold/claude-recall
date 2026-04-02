# Claude Code Memory System: A Deep Dive

**Purpose**: Understand every layer of Claude Code's memory and instruction system before making architectural decisions about Claude Recall. This document is a living reference — chat against it, challenge it, update it as we learn more.

---

## The Big Picture

Claude Code has **four distinct memory/instruction layers** that work together. They are NOT the same thing, they serve different purposes, and understanding when each one fires is critical.

| Layer | What It Is | Who Writes It | When It Loads | Scope |
|---|---|---|---|---|
| **CLAUDE.md** | Instructions and rules | You (or `/init`) | Every session start | Project, global, or managed |
| **Auto-Memory** | Learned context from conversations | Claude (automatically) | Session start (MEMORY.md index only) | Per working directory |
| **Settings** | Configuration and permissions | You | Session start | User, project, local, managed |
| **MCP Memory** | External memory store (e.g., Claude Recall) | Claude via tools | On demand (tool calls) | Whatever the server supports |

---

## Layer 1: CLAUDE.md Files (Instructions)

### What They Are

CLAUDE.md files are **instructions you give to Claude**. Think of them as a briefing document that Claude reads before every conversation. They tell Claude *how to behave*, not what it has learned.

### Where They Live

| Scope | Location | Shared via Git? | Purpose |
|---|---|---|---|
| **Managed/Policy** | `/Library/Application Support/ClaudeCode/CLAUDE.md` (macOS) | No (IT-deployed) | Organization-wide standards, security policies |
| **Global/User** | `~/.claude/CLAUDE.md` | No | Personal preferences across all projects |
| **Project** | `./CLAUDE.md` or `./.claude/CLAUDE.md` | Yes | Project-specific conventions, tech stack, commands |

### How They Load

Claude Code **walks up the directory tree** from your working directory:

```
Working dir:  ~/WorkSpace/my-project/src/
Loads:        ~/WorkSpace/my-project/src/CLAUDE.md  (if exists)
              ~/WorkSpace/my-project/CLAUDE.md       (if exists)
              ~/WorkSpace/CLAUDE.md                   (if exists)  <-- gotcha!
              ~/.claude/CLAUDE.md                     (global)
              /Library/.../CLAUDE.md                  (managed)
```

**Gotcha**: If there's a `CLAUDE.md` in `~/WorkSpace/`, it loads for EVERY project under that directory. This is the tree-walking behavior — it doesn't stop at the project root.

CLAUDE.md files in **subdirectories below** your CWD are lazy-loaded — they only load when Claude reads files in those directories.

### Importing Other Files

CLAUDE.md files can reference other files with `@path/to/file`:

```markdown
See @README for project overview.
Git workflow: @docs/git-instructions.md
Personal notes: @~/.claude/my-notes.md
```

Relative paths resolve from the file containing the import. Nesting up to 5 levels deep.

### The .claude/rules/ System

For modular instructions, use `.claude/rules/` instead of one giant CLAUDE.md:

```
.claude/rules/
  ├── code-style.md          # Always loaded
  ├── testing.md             # Always loaded
  └── api/
      └── endpoints.md       # Always loaded (subdirs supported)
```

Rules can be **path-scoped** with YAML frontmatter:

```markdown
---
paths:
  - "src/api/**/*.ts"
---

# API Rules
- All endpoints must include input validation
```

Path-scoped rules only load when Claude reads matching files.

**User-level rules** at `~/.claude/rules/` apply to every project. They load BEFORE project rules, giving project rules higher priority.

### Best Practices

- Keep under 200 lines per file — longer files consume context tokens and reduce adherence
- Be specific: "Use 2-space indentation" beats "Format code properly"
- Review periodically for contradictions between nested files and rules
- Use `/init` to generate a starting CLAUDE.md, then refine it

---

## Layer 2: Auto-Memory (What Claude Learns)

### What It Is

Auto-memory is Claude's **learned knowledge** from conversations. When Claude discovers something useful (a debugging insight, an architecture pattern, a user preference), it writes it to markdown files that persist across sessions.

This is **different from CLAUDE.md** — instructions tell Claude how to behave; auto-memory tells Claude what it has learned.

### Where It Lives

```
~/.claude/projects/<sanitized-path>/memory/
  ├── MEMORY.md              # Index file — loaded every session
  ├── user_role.md           # Individual memory files
  ├── feedback_testing.md    # (loaded on demand, not at startup)
  └── project_status.md
```

**Sanitized path**: Your working directory with `/` replaced by `-`:
- `/Users/gene/WorkSpace/my-project` becomes `-Users-gene-WorkSpace-my-project`
- `/Users/gene/WorkSpace` becomes `-Users-gene-WorkSpace` (the parent directory problem!)

### How It Works

1. **MEMORY.md** (first 200 lines / 25KB) loads at every session start
2. MEMORY.md is an **index** — one-line pointers to detailed memory files
3. Individual memory files are NOT loaded at startup — Claude reads them on demand
4. Claude writes new memories throughout the session as it learns things
5. Each memory file has YAML frontmatter: `name`, `description`, `type`
6. Four types: `user`, `feedback`, `project`, `reference`

### The Memory Scope Hierarchy (Confirmed)

**This is critical and confirmed from a second machine**: Claude Code doesn't just look at one memory directory — it **walks up the directory tree** and loads memory from parent scopes too. This is by design, not a bug.

Here's the actual hierarchy from a live system:

```
~/.claude/projects/
├── -home-genearnold-Workspace/
│   └── memory/                          ← PARENT-LEVEL: visible to ALL Workspace projects
│       ├── MEMORY.md
│       ├── project_linux_flow.md        ← This is how one project "knew" about another
│       ├── project_soundcard_debugger.md
│       ├── feedback_tech_stack.md
│       └── feedback_gtk4_image.md
├── -home-genearnold-Workspace-socialmedia-manager/
│   └── (no memory/ dir yet)             ← Project-specific: only this project
├── -home-genearnold-Workspace-nexus-server-v2/
│   └── memory/                          ← Project-specific: only this project
└── ... 45 more project dirs
```

This creates three memory visibility levels:

| Level | Example Path | Visible To |
|---|---|---|
| **Global** | `~/.claude/CLAUDE.md` | Every project, every session |
| **Parent/Workspace** | `~/.claude/projects/-home-user-Workspace/memory/` | All projects under `~/Workspace/` |
| **Project** | `~/.claude/projects/-home-user-Workspace-my-app/memory/` | Only that project |

**How the parent scope gets created**: If you ever launch Claude Code from `~/Workspace/` (the parent), it creates a memory directory at that level. From that point on, any session launched from a child directory (`~/Workspace/my-app/`) loads BOTH the project memory AND the parent memory.

**This is the "cross-project bleed" behavior** — it's not a bug, it's the directory tree walk. Memories saved at the parent level become shared context for all child projects.

**For git repositories**: Claude Code uses the git repository root, so all subdirectories within a repo share the same memory. If you're NOT in a git repo, it uses the literal working directory.

### What Claude Recall Actually Needs to Solve

Given the confirmed hierarchy, the gap Claude Recall fills is specifically:

1. **Bridging projects that don't share a common parent directory** — two repos in completely different paths have zero shared memory without MCP
2. **Semantic search** — local memory has no search; you either load MEMORY.md or you don't
3. **Cross-machine memory** — local files are machine-specific; Claude Recall can serve multiple machines
4. **Intentional scoping** — local memory scope is an accident of where you launched from; Claude Recall lets you explicitly tag memories as global vs project-specific

### Auto-Dream (Background Consolidation)

Auto-Dream is a background agent that automatically consolidates memory files:

- **Triggers after**: 24 hours AND at least 5 sessions
- **What it does**: Prunes duplicates, merges related info, removes stale entries
- **Runs in background**: Non-blocking
- **Known bug**: May ignore `autoMemoryDirectory` setting ([GitHub #39204](https://github.com/anthropics/claude-code/issues/39204))

### Controlling Auto-Memory

| Setting | Where | What |
|---|---|---|
| `autoMemoryEnabled` | `settings.json` or env var | Enable/disable auto-memory entirely |
| `autoMemoryDirectory` | User or local settings ONLY | Override the memory directory path |
| `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` | Environment variable | Disable auto-memory (highest precedence) |

**Security note**: `autoMemoryDirectory` cannot be set in project settings (`.claude/settings.json`) to prevent shared projects from redirecting writes to sensitive locations. User (`~/.claude/settings.json`) or local (`.claude/settings.local.json`) only.

---

## Layer 3: Settings Hierarchy

Settings control permissions, hooks, MCP servers, and configuration. They merge from multiple sources with clear precedence:

```
Lowest  →  User (~/.claude/settings.json)
           Local (.claude/settings.local.json)
           Project (.claude/settings.json)
           Command-line arguments
Highest →  Managed policy
```

Key files:

| File | Scope | Shared | Purpose |
|---|---|---|---|
| `~/.claude/settings.json` | User/global | No | Personal preferences, hooks, memory settings |
| `.claude/settings.json` | Project | Yes (git) | Team rules, tool permissions |
| `.claude/settings.local.json` | Local | No (gitignored) | Personal overrides for this project |

Settings **merge** rather than replace. A project deny can override a user allow, but not vice versa.

---

## Layer 4: MCP-Based Memory (Claude Recall, Mem0, etc.)

### What It Is

External memory systems accessed via MCP (Model Context Protocol) tools. Claude calls these tools explicitly during conversations — they don't load automatically.

### How It Differs from Auto-Memory

| Aspect | Auto-Memory | MCP Memory (Claude Recall) |
|---|---|---|
| **Storage** | Local markdown files | External database (Postgres, etc.) |
| **Scope** | Per working directory | Global or custom scoping |
| **Loaded at startup** | MEMORY.md index, yes | No — queried on demand |
| **Search** | None (full text at best) | Semantic search via embeddings |
| **Cross-project** | No (siloed per directory) | Yes |
| **Deduplication** | No built-in mechanism | Can implement |
| **Survives machine change** | No (machine-local) | Yes (if server is accessible) |

### Available Solutions

| Solution | Storage | Embeddings | Self-hosted? |
|---|---|---|---|
| **Claude Recall** (ours) | Postgres + pgvector | LiteLLM (text-embedding-3-small) | Yes (Docker) |
| **Mem0** | Cloud | Cloud | No (SaaS) |
| **mem0-mcp-selfhosted** | Qdrant + Neo4j | Ollama (local) | Yes |
| **OpenMemory MCP** | Local | Local | Yes |
| **MCP Memory Keeper** | Various | Various | Yes |

---

## How All Four Layers Interact

Here's what happens when you start a Claude Code session:

```
1. Session starts in ~/WorkSpace/my-project
   │
2. Load CLAUDE.md files (walk up directory tree)
   │  ├── ./CLAUDE.md
   │  ├── ~/.claude/CLAUDE.md
   │  └── .claude/rules/*.md (non-path-scoped ones)
   │
3. Load auto-memory
   │  └── ~/.claude/projects/-Users-...-my-project/memory/MEMORY.md (first 200 lines)
   │
4. Load settings (merge hierarchy)
   │  ├── ~/.claude/settings.json
   │  ├── .claude/settings.local.json
   │  └── .claude/settings.json
   │
5. Connect MCP servers (from settings + .mcp.json)
   │  └── Claude Recall at localhost:8765 (if configured)
   │
6. Session ready — user sends first message
   │
7. During conversation:
   │  ├── Claude reads path-scoped rules on demand
   │  ├── Claude reads individual memory/*.md files on demand
   │  ├── Claude calls MCP tools (save_memory, search_memories) on demand
   │  └── Claude writes new auto-memory files as it learns things
   │
8. PostToolUse hooks fire on Write/Edit
   │  └── sync_memory.py syncs local memory to Claude Recall
```

---

## The Overlap Problem

Auto-memory and Claude Recall can contain the **same information in two places**:

1. Claude learns your preferred coding style → writes to `auto-memory/feedback_style.md`
2. Hook syncs it to Claude Recall → now it's in Postgres too
3. Next session, Claude reads MEMORY.md AND can search Claude Recall
4. Two sources, potentially divergent over time

### When This Is Fine

- User preferences (stored globally in Claude Recall, also in local auto-memory) — redundancy is harmless
- Project-specific context — auto-memory is the natural home, Claude Recall is backup

### When This Is Dangerous

- Stale auto-memory contradicts current Claude Recall data
- Duplicate memories cause Claude to over-weight certain information
- Delete from one system but not the other → ghost data
- Claude gets confused about which source to trust

### Possible Strategies

**Strategy A: MCP-primary, auto-memory as local cache**
- Global `CLAUDE.md` instructs Claude to prefer Claude Recall for all memory operations
- Auto-memory still works locally but is not the source of truth
- Hooks sync local → central (current approach)
- Risk: hook failures cause silent data loss

**Strategy B: Separate concerns**
- Auto-memory handles ephemeral, project-specific context (debugging notes, current task state)
- Claude Recall handles durable, cross-project knowledge (user profile, feedback, references)
- No hooks — no sync between systems
- Risk: useful local memories never make it to the central store

**Strategy C: Disable auto-memory, go full MCP**
- Set `autoMemoryEnabled: false`
- All memory goes through Claude Recall
- Cleanest architecture, single source of truth
- Risk: sessions without MCP access have no memory at all

**Strategy D: Keep both, accept some redundancy**
- Auto-memory for local/project context
- Claude Recall for cross-project and user context
- Hooks as best-effort sync (current approach)
- Risk: complexity, edge cases, but works 95% of the time

---

## Known Issues and Gotchas

### 1. Parent Directory Memory Scope (Confirmed, By Design)
Launching Claude Code from `~/WorkSpace/` creates a workspace-wide memory scope that is visible to ALL child projects. This is intentional — Claude walks up the directory tree. The scope persists once created. This is actually useful if understood, but dangerous if accidental — memories from one project leak into every sibling project.

### 2. Auto-Dream Ignores autoMemoryDirectory
[GitHub #39204](https://github.com/anthropics/claude-code/issues/39204) — Auto-Dream writes to the default path even if you've set a custom directory.

### 3. Worktree Memory Fragmentation
[GitHub #24382](https://github.com/anthropics/claude-code/issues/24382) — Each worktree gets its own memory directory instead of sharing with the repository.

### 4. MEMORY.md 200-Line Limit
Only the first 200 lines of MEMORY.md are loaded at session start. If the index grows large, older entries fall off.

### 5. autoMemoryDirectory Security Restriction
Cannot be set in project `.claude/settings.json` — only user or local settings. This prevents shared projects from redirecting memory writes.

### 6. Cross-Project Memory Is Partial, Not Absent
The parent-directory tree walk DOES provide some cross-project memory — but only for projects that share a common parent. Projects in completely different directory trees have zero shared memory without an MCP server. Claude Recall fills this gap intentionally rather than relying on the accidental scoping of the directory tree walk.

### 7. Hook Timing
PostToolUse hooks fire AFTER the tool completes. If Claude writes a memory file and the hook fails (Docker down, network issue), the local file exists but the central store doesn't know about it. There is no retry mechanism.

---

## Multi-Machine Reality

Gene runs Claude Code on at least two machines:

| Machine | OS | Workspace Path | Parent Memory Exists? |
|---|---|---|---|
| MacBook Pro | macOS | `/Users/gene.arnold/WorkSpace/` | Yes (this machine) |
| Linux box | Linux | `/home/genearnold/Workspace/` | Yes (confirmed parent-level memory with 5+ files) |

**Key insight**: Local auto-memory is machine-specific. The Linux machine has memories about `linux_flow`, `soundcard_debugger`, and `gtk4_image` that this Mac has never seen. Without Claude Recall (or a shared MCP server), these machines have completely separate memory stores.

Claude Recall running on one machine doesn't help the other unless:
- Both machines can reach the same Claude Recall instance (network accessible)
- Or memories are exported/imported between machines

This is another argument for Claude Recall's value — if exposed beyond localhost (with auth), it becomes the single brain across all machines.

---

## Questions to Answer Before Making Changes

1. **Which strategy (A/B/C/D) fits how Gene works?** This determines whether hooks are worth the complexity.

2. **Should auto-memory be disabled globally?** If Claude Recall is the source of truth, local files add confusion. But sessions without MCP lose all memory.

3. **Should we create a global CLAUDE.md?** If yes, what goes in it? Instructions to prefer Claude Recall? General coding preferences?

4. **How to handle the parent directory memory scope?** Clean it up? Redirect it? Ignore it?

5. **Is Auto-Dream helping or hurting?** If it's consolidating local memories that are also in Claude Recall, it might create drift.

6. **What happens when Docker is down?** Should Claude Recall failing gracefully fall back to local memory? Or should we warn and stop?

---

## References

### Official Documentation
- [How Claude Remembers Your Project](https://code.claude.com/docs/en/memory)
- [Claude Code Settings Reference](https://code.claude.com/docs/en/settings)
- [Hooks Reference](https://code.claude.com/docs/en/hooks)

### Community Resources
- [You (probably) don't understand Claude Code memory](https://joseparreogarcia.substack.com/p/claude-code-memory-explained)
- [Anatomy of the .claude/ Folder](https://blog.dailydoseofds.com/p/anatomy-of-the-claude-folder)
- [Auto Memory and Auto Dream Explained](https://antoniocortes.com/en/2026/03/30/auto-memory-and-auto-dream-how-claude-code-learns-and-consolidates-its-memory/)

### GitHub Issues
- [Worktrees should share auto-memory (#24382)](https://github.com/anthropics/claude-code/issues/24382)
- [Auto-dream ignores autoMemoryDirectory (#39204)](https://github.com/anthropics/claude-code/issues/39204)
- [Multi-root workspace memory (#30771)](https://github.com/anthropics/claude-code/issues/30771)
