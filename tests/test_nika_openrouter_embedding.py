"""Dependency-light tests for Nika's opt-in direct provider boundary."""

import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

path = (
    Path(__file__).resolve().parents[1]
    / "open_notebook/utils/nika_openrouter_embedding.py"
)
spec = importlib.util.spec_from_file_location("nika_openrouter_embedding_leaf", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_response_keeps_provider_identity_and_usage():
    calls = []

    def respond(request):
        calls.append(request)
        assert request.url.path == "/api/v1/embeddings"
        assert request.headers["authorization"] == "Bearer test-key"
        assert request.content.count(b'"user":"batch-id"') == 1
        return httpx.Response(
            200,
            json={
                "id": "gen-emb-one",
                "usage": {"prompt_tokens": 4, "cost": 0.00000008},
                "data": [
                    {"index": 1, "embedding": [0.3, 0.4]},
                    {"index": 0, "embedding": [0.1, 0.2]},
                ],
            },
        )

    vectors, response_id, tokens = asyncio.run(
        module.call_openrouter(
            ["one", "two"],
            batch_id="batch-id",
            model_name="openai/test",
            key="test-key",
            transport=httpx.MockTransport(respond),
        )
    )
    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert (response_id, tokens) == ("gen-emb-one", 4)
    assert len(calls) == 1


def test_timeout_does_not_repeat_paid_request():
    calls = []

    def fail(request):
        calls.append(request)
        raise httpx.ReadTimeout("response lost")

    with pytest.raises(httpx.ReadTimeout):
        asyncio.run(
            module.call_openrouter(
                ["one"],
                batch_id="batch-id",
                model_name="openai/test",
                key="test-key",
                transport=httpx.MockTransport(fail),
            )
        )
    assert len(calls) == 1


def test_signed_path_uses_exact_configured_model_and_credential():
    from pydantic import SecretStr

    model = SimpleNamespace(
        type="embedding",
        provider="openrouter",
        name="openai/text-embedding-3-small",
        credential="credential:one",
        get_credential_obj=AsyncMock(
            return_value=SimpleNamespace(
                api_key=SecretStr("credential-key"),
                base_url=None,
            )
        ),
    )
    direct = AsyncMock(return_value=([[0.1]], "gen-emb-one", 3))
    with (
        patch(
            "open_notebook.ai.models.model_manager.get_defaults",
            new_callable=AsyncMock,
            return_value=SimpleNamespace(default_embedding_model="model:one"),
        ),
        patch(
            "open_notebook.ai.models.Model.get",
            new_callable=AsyncMock,
            return_value=model,
        ),
        patch.object(module, "call_openrouter", direct),
    ):
        result = asyncio.run(module.embed_metered_batch(["text"], batch_id="batch-id"))
    assert result == ([[0.1]], "gen-emb-one", 3)
    direct.assert_awaited_once_with(
        ["text"],
        batch_id="batch-id",
        model_name="openai/text-embedding-3-small",
        key="credential-key",
    )
