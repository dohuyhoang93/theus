---
id: INC-XXX
title: <short, descriptive title>
area: <core | plugin-system | lifecycle | di | config | runtime | ...>
severity: <low | medium | high | critical>
introduced_in: <version or commit>
fixed_in: <version or commit>
status: <resolved | mitigated | accepted-risk>
---

# INC-XXX: <Title>

## Summary
One-paragraph summary of what happened and why this incident matters.

## Background
Explain the relevant architectural context.
Assume the reader is **not familiar** with the internal design.

## What Went Wrong
Describe the unexpected behavior or failure.
Focus on **system behavior**, not individual mistakes.

## Impact
- Who was affected
- What broke or behaved incorrectly
- Why this was serious (or not)

## Root Cause
Explain the fundamental cause:
- Invalid assumptions
- Missing constraints
- Ambiguous contracts
- Design limitations

Avoid symptoms — focus on **why it was possible**.

## Why This Was Hard to Detect
- Missing tests?
- Non-deterministic behavior?
- Inadequate observability?
- Misleading abstractions?

## Resolution
Describe what was done to fix or mitigate the issue:
- Code changes
- Contract changes
- Behavioral guarantees

## Long-Term Changes
What permanent improvements were made?
- New invariants
- API or contract updates
- Architecture rules

## Preventive Actions
Concrete actions to prevent recurrence:
- Tests to add
- Docs to update
- Lint rules / CI checks
- Contributor guidelines

## Related
- GitHub Issue: #
- Pull Request: #
- ADR: ADR-XXXX
- Design doc: link

## Lessons Learned
Short, generalizable lessons applicable beyond this incident.
