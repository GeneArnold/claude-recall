"""SQLite database for Claude Recall."""

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

DEFAULT_DB_DIR = Path.home() / ".claude-recall"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "memories.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('user', 'feedback', 'project', 'reference')),
    content TEXT NOT NULL,
    project TEXT,
    embedding TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(type);
CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project);
CREATE INDEX IF NOT EXISTS idx_memories_name ON memories(name);
"""


def get_db_path() -> Path:
    return Path(os.environ.get("CLAUDE_RECALL_DB", DEFAULT_DB_PATH))


def get_connection() -> sqlite3.Connection:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {k: row[k] for k in row.keys()}


def cosine_similarity(a: list[float], b: list[float]) -> float:
    a_arr = np.array(a)
    b_arr = np.array(b)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a_arr, b_arr) / (norm_a * norm_b))


def insert_memory(
    conn: sqlite3.Connection,
    name: str,
    description: str,
    memory_type: str,
    content: str,
    embedding: list[float],
    project: str | None = None,
) -> dict:
    memory_id = _new_id()
    now = _now()
    conn.execute(
        "INSERT INTO memories (id, name, description, type, content, project, embedding, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (memory_id, name, description, memory_type, content, project, json.dumps(embedding), now, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
    return _row_to_dict(row)


def update_memory(
    conn: sqlite3.Connection,
    memory_id: str,
    embedding: list[float] | None = None,
    **fields,
) -> dict | None:
    allowed = {"name", "description", "type", "content", "project"}
    sets = []
    params = []

    for key, value in fields.items():
        if key in allowed:
            sets.append(f"{key} = ?")
            params.append(value)

    if embedding is not None:
        sets.append("embedding = ?")
        params.append(json.dumps(embedding))

    if not sets:
        return None

    sets.append("updated_at = ?")
    params.append(_now())
    params.append(memory_id)

    conn.execute(f"UPDATE memories SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
    return _row_to_dict(row) if row else None


def delete_memory(conn: sqlite3.Connection, memory_id: str) -> bool:
    cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
    conn.commit()
    return cursor.rowcount > 0


def get_memory_by_id(conn: sqlite3.Connection, memory_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
    return _row_to_dict(row) if row else None


def get_memory_by_name(conn: sqlite3.Connection, name: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM memories WHERE name = ? ORDER BY updated_at DESC LIMIT 1",
        (name,),
    ).fetchone()
    return _row_to_dict(row) if row else None


def list_memories(
    conn: sqlite3.Connection,
    memory_type: str | None = None,
    project: str | None = None,
    limit: int = 50,
) -> list[dict]:
    conditions = []
    params: list = []

    if memory_type:
        conditions.append("type = ?")
        params.append(memory_type)
    if project:
        conditions.append("project = ?")
        params.append(project)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    rows = conn.execute(
        f"SELECT * FROM memories {where} ORDER BY updated_at DESC LIMIT ?",
        params,
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def search_memories(
    conn: sqlite3.Connection,
    query_embedding: list[float],
    memory_type: str | None = None,
    project: str | None = None,
    limit: int = 10,
) -> list[dict]:
    conditions = ["embedding IS NOT NULL"]
    params: list = []

    if memory_type:
        conditions.append("type = ?")
        params.append(memory_type)
    if project:
        conditions.append("(project = ? OR project IS NULL)")
        params.append(project)

    where = f"WHERE {' AND '.join(conditions)}"

    rows = conn.execute(
        f"SELECT * FROM memories {where}",
        params,
    ).fetchall()

    # Compute similarity in Python and rank
    results = []
    for row in rows:
        row_dict = _row_to_dict(row)
        stored_embedding = json.loads(row_dict["embedding"])
        similarity = cosine_similarity(query_embedding, stored_embedding)
        row_dict["similarity"] = round(similarity, 6)
        del row_dict["embedding"]  # Don't return the raw vector
        results.append(row_dict)

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:limit]
