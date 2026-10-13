# Changelog

## 1.2.0-rc.1 — 2026-10-13

First independent public distribution, derived from diaverso/Arma3-Eden-Editor-MCP-Server at the baseline identified in ATTRIBUTION.md.

- Validate numeric fields and entity IDs without lossy coercion; resolve native editor kinds and correct entity bucket indexes.
- Replace runtime-only grouping with native Eden Group connections and complete membership/leader/link readback; guard undefined native returns.
- Correct catalogue side labels/filter semantics and invalidate stale schema caches.
- Add bounded reads, per-field errors, diagnostics, JSON escaping/Unicode handling, response limits and a missing-response guard without replay.
- Add configured attribute discovery, player/playable/name/yaw aliases, type/range validation, engine acceptance, and effective readback.
- Account for numeric precision in readback while retaining exact type/array-shape/nonnumeric comparisons.
- Replace inventory saving with a truthful native scenario-save request; implement native Undo with observed-event reporting.
- Define ATL/ASL/terrain/water placement, normalize marker creation, and report actual positions.
- Retain data-only request parsing, current-user pipe access, remote-client rejection, reconnect/lifecycle protections, wiki path containment, and backed-up/hash-verified installation.
- Publish source, installation guidance, attribution, Windows package, checksums, and explicit validation limits.

Direct dependency versions are pinned; a full transitive lockfile is not included. The optional wiki dataset, bulk mission creation, route authoring, filtered/delta reads, and reusable mission recipes are not included. See docs/validation.md and ROADMAP.md.
