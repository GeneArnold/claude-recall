#!/usr/bin/env python3
"""Claude Recall — PostToolUse hook for Write and Edit tools.

Syncs local memory files to the central Claude Recall server.
Receives hook JSON on stdin with tool_input.file_path.

Two modes:
- Regular memory files (*.md): sync content to Claude Recall via /api/sync
- MEMORY.md: reconcile deletions via /api/reconcile
"""

import json
import os
import re
import sys
import urllib.request

RECALL_URL = os.environ.get("CLAUDE_RECALL_URL", "http://localhost:8765")


def derive_project(hook_input, file_path):
    """Get the project path from hook cwd or environment."""
    project = hook_input.get("cwd") or os.environ.get("PWD")
    if not project:
        m = re.search(r"\.claude/projects/(-[^/]+)/memory/", file_path)
        if m:
            sanitized = m.group(1)
            project = "/" + sanitized[1:].replace("-", "/")
    return project


def sync_memory_file(hook_input, file_path):
    """Sync a regular memory .md file to Claude Recall."""
    if not os.path.isfile(file_path):
        return

    project = derive_project(hook_input, file_path)
    source_file = os.path.basename(file_path)

    with open(file_path) as f:
        text = f.read()

    name = ""
    description = ""
    mem_type = "project"
    content = text

    # Parse YAML frontmatter
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            frontmatter = parts[1]
            content = parts[2].strip()
            for line in frontmatter.strip().split("\n"):
                if ":" in line:
                    key, _, val = line.partition(":")
                    key = key.strip()
                    val = val.strip()
                    if key == "name":
                        name = val
                    elif key == "description":
                        description = val
                    elif key == "type":
                        mem_type = val

    # Fallback name from filename
    if not name:
        name = os.path.splitext(source_file)[0]

    payload = json.dumps({
        "name": name,
        "description": description,
        "type": mem_type,
        "content": content,
        "project": project,
        "source_file": source_file,
    }).encode()

    req = urllib.request.Request(
        f"{RECALL_URL}/api/sync",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


def reconcile_memory_index(hook_input, file_path):
    """When MEMORY.md is edited, detect deleted entries and remove from Claude Recall."""
    if not os.path.isfile(file_path):
        return

    project = derive_project(hook_input, file_path)
    if not project:
        return

    with open(file_path) as f:
        text = f.read()

    # Extract filenames from MEMORY.md links: [Title](filename.md)
    source_files = re.findall(r"\]\(([^)]+\.md)\)", text)

    payload = json.dumps({
        "project": project,
        "source_files": source_files,
    }).encode()

    req = urllib.request.Request(
        f"{RECALL_URL}/api/reconcile",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


def main():
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    # Extract file path from tool input
    tool_input = hook_input.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    # Only process memory files
    if "/memory/" not in file_path or not file_path.endswith(".md"):
        return

    if os.path.basename(file_path) == "MEMORY.md":
        reconcile_memory_index(hook_input, file_path)
    else:
        sync_memory_file(hook_input, file_path)


if __name__ == "__main__":
    main()
