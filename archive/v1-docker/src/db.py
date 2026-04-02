import os
import uuid
from datetime import datetime, timezone

import psycopg
from pgvector.psycopg import register_vector


EXTENSION_SQL = "CREATE EXTENSION IF NOT EXISTS vector;"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('user', 'feedback', 'project', 'reference')),
    content TEXT NOT NULL,
    project TEXT,
    source_file TEXT,
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(type);
CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project);
CREATE INDEX IF NOT EXISTS idx_memories_name ON memories(name);
CREATE INDEX IF NOT EXISTS idx_memories_source_file ON memories(source_file);
"""

MIGRATION_SQL = """
ALTER TABLE memories ADD COLUMN IF NOT EXISTS source_file TEXT;
CREATE INDEX IF NOT EXISTS idx_memories_source_file ON memories(source_file);
"""


def get_connection() -> psycopg.Connection:
    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    return conn


def init_schema(conn: psycopg.Connection) -> None:
    conn.execute(EXTENSION_SQL)
    register_vector(conn)
    conn.execute(SCHEMA_SQL)
    conn.execute(MIGRATION_SQL)


def insert_memory(
    conn: psycopg.Connection,
    name: str,
    description: str,
    memory_type: str,
    content: str,
    embedding: list[float],
    project: str | None = None,
    source_file: str | None = None,
) -> dict:
    row = conn.execute(
        """
        INSERT INTO memories (name, description, type, content, project, source_file, embedding)
        VALUES (%s, %s, %s, %s, %s, %s, %s::vector)
        RETURNING id, name, description, type, content, project, source_file, created_at, updated_at
        """,
        (name, description, memory_type, content, project, source_file, str(embedding)),
    ).fetchone()
    return _row_to_dict(row)


def update_memory(
    conn: psycopg.Connection,
    memory_id: str,
    embedding: list[float] | None = None,
    **fields,
) -> dict | None:
    if not fields and embedding is None:
        return None

    sets = []
    params = []

    for key, value in fields.items():
        if key in ("name", "description", "type", "content", "project", "source_file"):
            sets.append(f"{key} = %s")
            params.append(value)

    if embedding is not None:
        sets.append("embedding = %s::vector")
        params.append(str(embedding))

    sets.append("updated_at = %s")
    params.append(datetime.now(timezone.utc))
    params.append(memory_id)

    row = conn.execute(
        f"""
        UPDATE memories SET {', '.join(sets)}
        WHERE id = %s
        RETURNING id, name, description, type, content, project, source_file, created_at, updated_at
        """,
        params,
    ).fetchone()
    return _row_to_dict(row) if row else None


def delete_memory(conn: psycopg.Connection, memory_id: str) -> bool:
    cur = conn.execute("DELETE FROM memories WHERE id = %s", (memory_id,))
    return cur.rowcount > 0


def get_memory_by_id(conn: psycopg.Connection, memory_id: str) -> dict | None:
    row = conn.execute(
        "SELECT id, name, description, type, content, project, source_file, created_at, updated_at FROM memories WHERE id = %s",
        (memory_id,),
    ).fetchone()
    return _row_to_dict(row) if row else None


def get_memory_by_name(conn: psycopg.Connection, name: str) -> dict | None:
    row = conn.execute(
        "SELECT id, name, description, type, content, project, source_file, created_at, updated_at FROM memories WHERE name = %s ORDER BY updated_at DESC LIMIT 1",
        (name,),
    ).fetchone()
    return _row_to_dict(row) if row else None


def list_memories(
    conn: psycopg.Connection,
    memory_type: str | None = None,
    project: str | None = None,
    limit: int = 50,
) -> list[dict]:
    conditions = []
    params: list = []

    if memory_type:
        conditions.append("type = %s")
        params.append(memory_type)
    if project:
        conditions.append("project = %s")
        params.append(project)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    rows = conn.execute(
        f"SELECT id, name, description, type, content, project, source_file, created_at, updated_at FROM memories {where} ORDER BY updated_at DESC LIMIT %s",
        params,
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def search_memories(
    conn: psycopg.Connection,
    embedding: list[float],
    memory_type: str | None = None,
    project: str | None = None,
    limit: int = 10,
) -> list[dict]:
    conditions = ["embedding IS NOT NULL"]
    filter_params: list = []

    if memory_type:
        conditions.append("type = %s")
        filter_params.append(memory_type)
    if project:
        conditions.append("(project = %s OR project IS NULL)")
        filter_params.append(project)

    where = f"WHERE {' AND '.join(conditions)}"
    embedding_str = str(embedding)

    # params: similarity calc, then WHERE filters, then ORDER BY, then LIMIT
    params = [embedding_str] + filter_params + [embedding_str, limit]

    rows = conn.execute(
        f"""
        SELECT id, name, description, type, content, project, source_file, created_at, updated_at,
               1 - (embedding <=> %s::vector) AS similarity
        FROM memories
        {where}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
        """,
        params,
    ).fetchall()
    return [_row_to_dict(r, has_similarity=True) for r in rows]


def get_memories_by_source_project(conn: psycopg.Connection, project: str) -> list[dict]:
    """Get all memories with a source_file for a given project."""
    rows = conn.execute(
        "SELECT id, name, description, type, content, project, source_file, created_at, updated_at FROM memories WHERE project = %s AND source_file IS NOT NULL",
        (project,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row, has_similarity: bool = False) -> dict:
    keys = ["id", "name", "description", "type", "content", "project", "source_file", "created_at", "updated_at"]
    if has_similarity:
        keys.append("similarity")
    return {k: str(v) if isinstance(v, (uuid.UUID, datetime)) else v for k, v in zip(keys, row)}
