"""Embedding generation via LiteLLM / OpenAI-compatible API."""

import os
import json
from pathlib import Path
from openai import OpenAI

_client: OpenAI | None = None

CONFIG_PATH = Path.home() / ".claude-recall" / "config.json"


def _load_config() -> dict:
    """Load config from ~/.claude-recall/config.json, with env var overrides."""
    config = {}
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            config = json.load(f)

    # Env vars override config file
    if os.environ.get("LITELLM_BASE_URL"):
        config["base_url"] = os.environ["LITELLM_BASE_URL"]
    if os.environ.get("LITELLM_API_KEY"):
        config["api_key"] = os.environ["LITELLM_API_KEY"]
    if os.environ.get("EMBEDDING_MODEL"):
        config["embedding_model"] = os.environ["EMBEDDING_MODEL"]

    return config


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        config = _load_config()
        _client = OpenAI(
            base_url=config.get("base_url", "https://api.openai.com/v1"),
            api_key=config.get("api_key", ""),
        )
    return _client


def get_embedding(text: str) -> list[float]:
    """Generate an embedding vector for the given text."""
    config = _load_config()
    model = config.get("embedding_model", "text-embedding-3-small")
    response = _get_client().embeddings.create(input=text, model=model)
    return response.data[0].embedding
