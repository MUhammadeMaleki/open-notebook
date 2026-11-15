"""One-call OpenRouter embedding with response identity for Nika jobs only.

The ordinary Open Notebook embedding path stays on Esperanto. This path does
not retry HTTP requests: after dispatch, a missing response is ambiguous.
"""

import os

import httpx


async def embed_metered_batch(
    texts: list[str], *, batch_id: str
) -> tuple[list[list[float]], str, int]:
    from open_notebook.ai.models import Model, model_manager

    defaults = await model_manager.get_defaults()
    model = await Model.get(defaults.default_embedding_model)
    if model is None or model.type != "embedding" or model.provider != "openrouter":
        raise ValueError(
            "Nika metered embedding requires an OpenRouter embedding model"
        )
    credential = await model.get_credential_obj() if model.credential else None
    if credential is not None:
        if (
            credential.base_url
            and credential.base_url.rstrip("/") != "https://openrouter.ai/api/v1"
        ):
            raise ValueError(
                "Nika metered embedding requires the official OpenRouter endpoint"
            )
        key = credential.api_key.get_secret_value() if credential.api_key else ""
    else:
        key = os.getenv("OPENROUTER_API_KEY", "")
    if not key:
        raise ValueError("OpenRouter embedding credential is missing")

    return await call_openrouter(
        texts, batch_id=batch_id, model_name=model.name, key=key
    )


async def call_openrouter(
    texts: list[str],
    *,
    batch_id: str,
    model_name: str,
    key: str,
    transport=None,
) -> tuple[list[list[float]], str, int]:
    """One paid POST. No retry and no model abstraction that discards usage."""
    if not texts or not batch_id or not model_name or not key:
        raise ValueError("Invalid metered embedding request")

    async with httpx.AsyncClient(
        base_url="https://openrouter.ai",
        timeout=30,
        trust_env=False,
        follow_redirects=False,
        headers={"Authorization": f"Bearer {key}"},
        transport=transport,
    ) as client:
        response = await client.post(
            "/api/v1/embeddings",
            json={
                "model": model_name,
                "input": texts,
                "user": batch_id,
            },
        )
        response.raise_for_status()
        payload = response.json()

    response_id = payload.get("id") if isinstance(payload, dict) else None
    usage = payload.get("usage") if isinstance(payload, dict) else None
    entries = payload.get("data") if isinstance(payload, dict) else None
    tokens = usage.get("prompt_tokens") if isinstance(usage, dict) else None
    if (
        not isinstance(response_id, str)
        or not response_id.startswith("gen-emb-")
        or not isinstance(tokens, int)
        or isinstance(tokens, bool)
        or tokens < 0
        or not isinstance(entries, list)
        or len(entries) != len(texts)
    ):
        raise ValueError("Invalid OpenRouter embedding evidence")
    if any(not isinstance(entry, dict) for entry in entries):
        raise ValueError("Invalid OpenRouter embedding vectors")
    ordered = sorted(entries, key=lambda entry: entry.get("index", -1))
    if any(
        not isinstance(entry, dict)
        or entry.get("index") != index
        or not isinstance(entry.get("embedding"), list)
        or not entry["embedding"]
        for index, entry in enumerate(ordered)
    ):
        raise ValueError("Invalid OpenRouter embedding vectors")
    return [entry["embedding"] for entry in ordered], response_id, tokens
