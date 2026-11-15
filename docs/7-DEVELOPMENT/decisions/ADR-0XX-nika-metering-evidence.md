# ADR-0XX: Preserve provider evidence for Nika billing

- **Status**: Proposed (Nika fork only)
- **Date**: 2026-11
- **Related**: NIKA-MOD-03-03; upstream base `5e285b7` (v1.15.1)

## Context

Nika selects sources and asks Open Notebook to generate text. The chat API
currently turns AI messages into content-only responses, dropping a provider
response identifier and token usage when the underlying LangChain message has
them. Open Notebook's embedding helper returns vectors only. Neither path
currently provides a verified per-operation monetary charge to Nika.

## Decision

Keep the fork change additive and narrow: expose the AI message's candidate
provider response ID and reported token counts as optional chat fields. Nika
must verify the ID and actual cost with the billing provider before wallet
settlement. Missing evidence means `awaiting_cost`, never a guessed zero.

For Nika-signed source embedding jobs only, checkpoint the complete batch plan
and each batch before `aembed`. The fork may proceed only when Nika accepts the
one-time dispatch transition. A repeated or uncertain dispatch never calls
`aembed` again. The generic Esperanto embedding abstraction returns vectors
without provider response identity or usage, so even a successful metered
batch is marked `needs_review` until a separate evidence path exists. Ordinary
Open Notebook embedding jobs retain their upstream behavior. This does **not**
claim completed embedding billing or recovery of missing provider responses.
The fork branch is based on the exact version installed on Nika staging; do not
merge upstream updates into a deployed branch without the compatibility gate.

## Alternatives considered

- Token-count × advertised price: rejected because routing, caching, tools and
  provider-specific charges can change the bill.
- Replacing the source/LLM engine with Nika code: rejected because Nika should
  continue using the upstream engine.
- Passing through every raw provider payload: rejected because it expands the
  public API surface and could leak information unrelated to billing.

## Consequences

- This additive API field is easier to carry forward than a broad fork.
- The response ID is only a candidate; Nika must check ownership, cost and
  provider response before charging.
- Embedding cost and timeout reconciliation remain unresolved; paid multi-tenant
  execution stays disabled until they have tested evidence paths. The Nika
  callback mode requires a shared secret and a safe loopback/HTTPS destination.
- On every upstream update, rerun the tests and staging probe in
  `docs/NIKA_METERING_UPDATE_CHECKLIST.md` before changing the deployed pin.
