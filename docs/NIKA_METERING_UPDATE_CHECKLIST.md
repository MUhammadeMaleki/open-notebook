# Nika / Open Notebook metering compatibility gate

This is a fork-specific integration note, not an upstream feature claim.
The Nika staging engine was pinned to upstream commit `5e285b7` (v1.15.1)
when the `nika-metering-1.15.1` branch was started. Keep the deployed commit
pin explicit; a new upstream release does **not** silently replace it.

Before updating the pinned engine:

1. Back up the engine database and checkpoint file. Record the old and new
   commit hashes; compare the fork patch with `git range-diff` or an equivalent
   review. Reapply only the small additive change if upstream changed chat
   serialization. Do not modify `main` just to update Nika staging.
2. Run `uv run pytest -q tests/test_nika_chat_usage_evidence.py` and the
   relevant upstream chat tests. Check that both `/api/chat/execute` and
   `GET /api/chat/sessions/{id}` still expose the optional evidence fields on
   AI messages and omit them on human messages.
3. With the approved capped test key, make one staging chat call and verify
   the returned response ID against the provider's generation endpoint.
   Compare provider-reported cost with the wallet's pending operation. A token
   count or candidate ID alone is **not** enough to settle.
4. Repeat with a lost-response/timeout simulation. The client must keep one
   operation in `needs_review` / `awaiting_cost`, not call the model again or
   refund as zero. Verify no provider key or source text appears in logs.
5. Test a source embedding job separately. This patch does **not** expose its
   per-batch provider usage, so paid embedding remains blocked until a verified
   accounting path and retry behavior are implemented and tested.
6. Only then update the deployed pin, document the new hash in Nika's 03.3
   ClickUp subtask, and perform a rollback drill. If any check fails, keep the
   old pin and paid multi-tenant traffic disabled.

The API change is additive: `ChatMessage.provider_response_id` and
`ChatMessage.usage` may be null. Never treat null as zero cost.
