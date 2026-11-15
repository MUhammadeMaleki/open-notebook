"""Keep the small Nika metering extension stable across upstream updates."""

from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage

from api.routers._chat_shared import extract_chat_messages


def test_chat_response_preserves_provider_evidence_without_guessing_cost():
    messages = extract_chat_messages(
        [
            HumanMessage(content="Question", id="human-1"),
            AIMessage(
                content="Answer",
                id="gen-test-123",
                usage_metadata={
                    "input_tokens": 15,
                    "output_tokens": 4,
                    "total_tokens": 19,
                },
            ),
        ]
    )
    assert messages[0].provider_response_id is None
    assert messages[0].usage is None
    assert messages[1].provider_response_id == "gen-test-123"
    assert messages[1].usage == {
        "input_tokens": 15,
        "output_tokens": 4,
        "total_tokens": 19,
    }
    assert "cost" not in messages[1].model_dump()


def test_missing_or_untrusted_metadata_never_becomes_billing_evidence():
    messages = extract_chat_messages(
        [
            AIMessage(content="Answer", id="locally-generated-id"),
            SimpleNamespace(
                type="ai",
                content="Answer",
                id="chatcmpl-test-123",
                usage_metadata={"input_tokens": True, "output_tokens": -1},
            ),
        ]
    )
    assert messages[0].provider_response_id is None
    assert messages[0].usage is None
    assert messages[1].provider_response_id == "chatcmpl-test-123"
    assert messages[1].usage is None
