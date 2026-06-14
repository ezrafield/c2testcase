# ADR 0001: Agent-Native Documentation Architecture

## Status
Accepted

## Decision
Use thin auto-loaded instruction files plus on-demand agent documentation.

## Rationale
Small entrypoint files reduce automatic context load. Richer docs remain available through `docs/agent/INDEX.md` when a task requires them.

## Consequences
- Agents need a routing habit before editing.
- Documentation must stay organized by task and module.
- Generated code maps should be refreshed as the project grows.
