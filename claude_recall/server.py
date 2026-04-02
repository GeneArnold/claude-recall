"""Claude Recall — MCP server for cross-project AI memory with semantic search."""

from fastmcp import FastMCP
from .db import (
    get_connection,
    init_schema,
    insert_memory,
    update_memory as db_update_memory,
    delete_memory as db_delete_memory,
    get_memory_by_id,
    get_memory_by_name,
    list_memories as db_list_memories,
    search_memories as db_search_memories,
)
from .embeddings import get_embedding

mcp = FastMCP("Claude Recall")

_conn = None


def _get_conn():
    global _conn
    if _conn is None:
        _conn = get_connection()
        init_schema(_conn)
    return _conn


def _embed_memory(name: str, description: str, content: str) -> list[float]:
    text = f"{name}\n{description}\n{content}"
    return get_embedding(text)


@mcp.tool()
def save_memory(
    name: str,
    description: str,
    memory_type: str,
    content: str,
    project: str | None = None,
) -> dict:
    """Save a new memory to the central store.

    Args:
        name: Short name for the memory (e.g., "user_role", "feedback_testing")
        description: One-line description used for relevance matching
        memory_type: One of: user, feedback, project, reference
        content: The full memory content (markdown supported)
        project: Optional project identifier (working directory path). Null = global memory.
    """
    conn = _get_conn()
    embedding = _embed_memory(name, description, content)
    result = insert_memory(conn, name, description, memory_type, content, embedding, project)
    return {"status": "saved", "memory": result}


@mcp.tool()
def update_memory(
    memory_id: str | None = None,
    memory_name: str | None = None,
    name: str | None = None,
    description: str | None = None,
    memory_type: str | None = None,
    content: str | None = None,
    project: str | None = None,
) -> dict:
    """Update an existing memory by ID or name.

    Args:
        memory_id: UUID of the memory to update (provide this or memory_name)
        memory_name: Name of the memory to look up (used if memory_id not provided)
        name: New name (optional)
        description: New description (optional)
        memory_type: New type (optional)
        content: New content (optional)
        project: New project tag (optional)
    """
    conn = _get_conn()

    if not memory_id and memory_name:
        existing = get_memory_by_name(conn, memory_name)
        if not existing:
            return {"status": "error", "message": f"No memory found with name '{memory_name}'"}
        memory_id = existing["id"]
    elif not memory_id:
        return {"status": "error", "message": "Provide either memory_id or memory_name"}

    fields = {}
    if name is not None:
        fields["name"] = name
    if description is not None:
        fields["description"] = description
    if memory_type is not None:
        fields["type"] = memory_type
    if content is not None:
        fields["content"] = content
    if project is not None:
        fields["project"] = project

    embedding = None
    if any(k in fields for k in ("name", "description", "content")):
        existing = get_memory_by_id(conn, memory_id)
        if existing:
            embed_name = fields.get("name", existing["name"])
            embed_desc = fields.get("description", existing["description"])
            embed_content = fields.get("content", existing["content"])
            embedding = _embed_memory(embed_name, embed_desc, embed_content)

    result = db_update_memory(conn, memory_id, embedding=embedding, **fields)
    if result is None:
        return {"status": "error", "message": "Memory not found or no changes provided"}
    return {"status": "updated", "memory": result}


@mcp.tool()
def delete_memory(
    memory_id: str | None = None,
    memory_name: str | None = None,
) -> dict:
    """Delete a memory by ID or name.

    Args:
        memory_id: UUID of the memory to delete (provide this or memory_name)
        memory_name: Name of the memory to look up (used if memory_id not provided)
    """
    conn = _get_conn()

    if not memory_id and memory_name:
        existing = get_memory_by_name(conn, memory_name)
        if not existing:
            return {"status": "error", "message": f"No memory found with name '{memory_name}'"}
        memory_id = existing["id"]
    elif not memory_id:
        return {"status": "error", "message": "Provide either memory_id or memory_name"}

    deleted = db_delete_memory(conn, memory_id)
    return {"status": "deleted" if deleted else "not_found"}


@mcp.tool()
def get_memory(
    memory_id: str | None = None,
    memory_name: str | None = None,
) -> dict:
    """Retrieve a specific memory by ID or name.

    Args:
        memory_id: UUID of the memory (provide this or memory_name)
        memory_name: Name of the memory to look up (used if memory_id not provided)
    """
    conn = _get_conn()

    if memory_id:
        result = get_memory_by_id(conn, memory_id)
    elif memory_name:
        result = get_memory_by_name(conn, memory_name)
    else:
        return {"status": "error", "message": "Provide either memory_id or memory_name"}

    if result is None:
        return {"status": "not_found"}
    return {"status": "found", "memory": result}


@mcp.tool()
def list_memories(
    memory_type: str | None = None,
    project: str | None = None,
    limit: int = 50,
) -> dict:
    """List memories, optionally filtered by type and/or project.

    Args:
        memory_type: Filter by type (user, feedback, project, reference). Null = all types.
        project: Filter by project identifier. Null = all projects including global.
        limit: Max number of results (default 50)
    """
    conn = _get_conn()
    results = db_list_memories(conn, memory_type=memory_type, project=project, limit=limit)
    return {"status": "ok", "count": len(results), "memories": results}


@mcp.tool()
def search_memories(
    query: str,
    memory_type: str | None = None,
    project: str | None = None,
    limit: int = 10,
) -> dict:
    """Semantic search across all memories using natural language.

    Args:
        query: Natural language search query (e.g., "deployment preferences", "testing approach")
        memory_type: Filter by type (user, feedback, project, reference). Null = all types.
        project: Filter to a specific project's memories + global. Null = search everything.
        limit: Max number of results (default 10)
    """
    conn = _get_conn()
    embedding = get_embedding(query)
    results = db_search_memories(conn, embedding, memory_type=memory_type, project=project, limit=limit)
    return {"status": "ok", "count": len(results), "memories": results}


@mcp.tool()
def memory_stats() -> dict:
    """Get statistics about the memory store — counts by type, project, and recent activity."""
    conn = _get_conn()

    total = conn.execute("SELECT count(*) FROM memories").fetchone()[0]

    by_type = conn.execute(
        "SELECT type, count(*) as cnt FROM memories GROUP BY type ORDER BY cnt DESC"
    ).fetchall()

    by_project = conn.execute(
        "SELECT COALESCE(project, '(global)') as proj, count(*) as cnt FROM memories GROUP BY project ORDER BY cnt DESC"
    ).fetchall()

    recent = conn.execute(
        "SELECT name, type, COALESCE(project, '(global)') as proj, updated_at FROM memories ORDER BY updated_at DESC LIMIT 5"
    ).fetchall()

    return {
        "total_memories": total,
        "by_type": {row["type"]: row["cnt"] for row in by_type},
        "by_project": {row["proj"]: row["cnt"] for row in by_project},
        "recent": [
            {"name": r["name"], "type": r["type"], "project": r["proj"], "updated_at": r["updated_at"]}
            for r in recent
        ],
    }
