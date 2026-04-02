"""Entry point: python -m claude_recall"""

from .server import mcp

mcp.run(transport="stdio")
