import os
from openai import OpenAI

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url=os.environ["LITELLM_BASE_URL"],
            api_key=os.environ["LITELLM_API_KEY"],
        )
    return _client


def get_embedding(text: str) -> list[float]:
    """Generate an embedding vector for the given text via LiteLLM."""
    model = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")
    response = _get_client().embeddings.create(
        input=text,
        model=model,
    )
    return response.data[0].embedding
