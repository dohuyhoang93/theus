"""
test_inc026_output_mapping_bypass.py
=====================================
Regression tests for INC-026:
  "Python _proxy_delta_exists Contradicts Rust v3.5 Explicit-Wins Policy
   — Silent Output Mapping Bypass"

ROOT CAUSE:
  In commit 9e19cff (INC-021 fix), two bugs were introduced in
  _attempt_execute() output mapping:
    A) pending_data[key] was initialized from to_dict() snapshot, pre-populating
       ALL domain fields before any return value was applied.
    B) _proxy_delta_exists check evaluated against that polluted pending_data,
       returning True for every domain field and silently skipping ALL return values.

INVARIANTS BEING TESTED:
  INV-1: A process that returns a non-None value for an output path MUST have
         that value reflected in committed state, even if the field already
         exists in current state with a different value.

  INV-2: A process returning a list for a domain field that starts empty MUST
         result in a non-empty committed state (simulates p_load_config pattern).

  INV-3: Multiple outputs declared in outputs=[...] MUST all be applied from
         the return tuple when non-None.

  INV-4: Explicit return value MUST win over the field's prior state value
         (aligned with Rust [v3.5 FIX] explicit-wins policy from INC-021).

  INV-5: Proxy mutation (return None) MUST still work correctly alongside
         explicit return — both patterns must co-exist.

  INV-6: Cross-layer consistency — explicit pending updates committed via
         output mapping must NOT be overwritten by stale inferred shadow deltas.
"""

import pytest
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from theus import TheusEngine, process
from theus.context import BaseSystemContext, BaseDomainContext


# ─────────────────────────── DOMAIN / CONTEXT ────────────────────────────

@dataclass
class ExpDomain(BaseDomainContext):
    """Domain mirroring the emotional-agent orchestrator pattern."""
    experiments: List[Dict[str, Any]] = field(default_factory=list)
    output_dir: str = "results"
    active_experiment_idx: int = 0
    counter: int = 0
    tags: List[str] = field(default_factory=list)
    nested: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExpContext(BaseSystemContext):
    domain: ExpDomain = field(default_factory=ExpDomain)


def _make_engine(domain: Optional[ExpDomain] = None) -> TheusEngine:
    """Fresh engine with ExpContext."""
    d = domain or ExpDomain()
    ctx = ExpContext(domain=d)
    return TheusEngine(ctx, strict_guards=False)


# ─────────────────────────── PROCESSES ───────────────────────────────────

@process(
    outputs=["domain.experiments"],
    semantic="effect",
)
def p_load_experiments(ctx, experiments_list):
    """
    Simulates p_load_config: returns a non-empty list for a field
    that starts as [] in current state.
    BUG: before INC-026 fix, this return was silently skipped.
    """
    return experiments_list


@process(
    outputs=["domain.experiments", "domain.output_dir", "domain.active_experiment_idx"],
    semantic="effect",
)
def p_load_multi_output(ctx, experiments_list, out_dir, idx):
    """
    Multiple outputs — all three must be committed.
    """
    return experiments_list, out_dir, idx


@process(
    outputs=["domain.counter"],
    semantic="effect",
)
def p_set_counter(ctx, value):
    """
    Return a specific integer for a field that already has a value.
    INV-4: return value wins over existing state.
    """
    return value


@process(
    outputs=["domain.counter"],
    semantic="effect",
)
def p_increment_counter(ctx):
    """
    Read current counter and return incremented value.
    Simulates p_advance_episode: return value must update counter.
    BUG: before INC-026 fix, counter was permanently stuck.
    """
    return int(ctx.domain.counter) + 1


@process(
    inputs=["domain.tags"],
    outputs=["domain.tags"],
    semantic="effect",
)
def p_replace_tags(ctx, new_tags):
    """
    Replace a list field — return value must overwrite existing list.
    """
    return new_tags


@process(
    outputs=["domain.counter"],
    semantic="effect",
)
def p_proxy_only_no_return(ctx, value):
    """
    Proxy mutation only — return None (proxy-wins for this path).
    INV-5: proxy pattern must still work after INC-026 fix.
    """
    ctx.domain.counter = value
    return None


@process(
    outputs=["domain.counter"],
    semantic="effect",
)
def p_proxy_with_ack(ctx, value):
    """
    Proxy mutation + return ack string.
    Classic hybrid pattern: proxy writes the real value,
    return "ok" is an acknowledgement (should NOT overwrite proxy value).
    INV-5b: _proxy_delta_exists must correctly skip the ack string.
    """
    ctx.domain.counter = value
    return "ok"


@process(
    outputs=["domain.counter", "domain.output_dir"],
    semantic="effect",
)
def p_partial_none_return(ctx, out_dir):
    """
    Returns (None, str) — None slot means proxy-only, str slot is explicit.
    The output_dir field must be updated; counter must not be touched.
    """
    return None, out_dir


@process(
    outputs=["domain.nested"],
    semantic="effect",
)
def p_set_nested(ctx, nested_dict):
    """
    Return a dict for a nested field — full replacement.
    """
    return nested_dict


# ═══════════════════════════════════════════════════════════════════════════
# INV-1 & INV-2: Empty list field must be populated by return value
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_INV1_return_value_populates_existing_empty_list():
    """
    INV-1 + INV-2: process returns non-empty list for domain.experiments
    which starts as []. Committed state must contain the returned list.

    This is the exact failure pattern from p_load_config in emotional-agent:
    domain.experiments stayed [] after load_config returned a full list.
    """
    engine = _make_engine()
    engine.register(p_load_experiments)

    experiments = [
        {"name": "Exp_A", "max_episodes": 10},
        {"name": "Exp_B", "max_episodes": 20},
    ]

    await engine.execute("p_load_experiments", experiments_list=experiments)

    committed = engine.state.data["domain"]["experiments"]
    assert committed == experiments, (
        f"INC-026 regression: domain.experiments should be {experiments} "
        f"but got {committed!r}. "
        "output mapping return value was silently skipped."
    )


@pytest.mark.asyncio
async def test_INV2_empty_to_nonempty_list_single_execute():
    """
    INV-2 specific: a single execute where the field starts empty
    and the return value is non-empty. Must not stay empty.
    """
    engine = _make_engine()
    engine.register(p_load_experiments)

    await engine.execute("p_load_experiments", experiments_list=[{"id": 1}])

    committed = engine.state.data["domain"]["experiments"]
    assert len(committed) == 1, (
        f"INC-026 regression: expected 1 experiment, got {len(committed)}. "
        "Return value was discarded."
    )


# ═══════════════════════════════════════════════════════════════════════════
# INV-3: All outputs in multi-output tuple must be committed
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_INV3_multi_output_all_fields_committed():
    """
    INV-3: Three outputs declared. All three return values must appear
    in committed state.

    Before INC-026 fix, ALL three would be skipped (pending_data['domain']
    was pre-populated via to_dict()).
    """
    engine = _make_engine()
    engine.register(p_load_multi_output)

    experiments = [{"name": "X"}]
    out_dir = "custom_results"
    idx = 2

    await engine.execute(
        "p_load_multi_output",
        experiments_list=experiments,
        out_dir=out_dir,
        idx=idx,
    )

    domain_data = engine.state.data["domain"]
    assert domain_data["experiments"] == experiments, (
        f"experiments not committed: {domain_data['experiments']!r}"
    )
    assert domain_data["output_dir"] == out_dir, (
        f"output_dir not committed: {domain_data['output_dir']!r}"
    )
    assert domain_data["active_experiment_idx"] == idx, (
        f"active_experiment_idx not committed: {domain_data['active_experiment_idx']!r}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# INV-4: Return value wins over existing state value
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_INV4_return_value_overwrites_existing_field():
    """
    INV-4: domain.counter starts at 5. Process returns 99.
    Committed state must be 99, not 5.

    This verifies: return value wins over current state
    (aligned with Rust [v3.5 FIX] explicit-wins policy from INC-021).
    """
    initial_domain = ExpDomain(counter=5)
    engine = _make_engine(domain=initial_domain)
    engine.register(p_set_counter)

    await engine.execute("p_set_counter", value=99)

    committed = engine.state.data["domain"]["counter"]
    assert committed == 99, (
        f"INC-026 regression: counter should be 99, got {committed}. "
        "Return value was skipped, leaving stale state value."
    )


@pytest.mark.asyncio
async def test_INV4_counter_increments_on_sequential_executes():
    """
    INV-4 sequential: p_increment_counter reads and returns counter+1.
    After 3 executes starting from 0, counter must be 3.

    This is the exact failure pattern from p_advance_episode:
    counter was permanently stuck at 0 before INC-026 fix.
    """
    engine = _make_engine()
    engine.register(p_increment_counter)

    for expected in [1, 2, 3]:
        await engine.execute("p_increment_counter")
        committed = engine.state.data["domain"]["counter"]
        assert committed == expected, (
            f"INC-026 regression: after execute #{expected}, "
            f"counter should be {expected}, got {committed}. "
            "p_advance_episode pattern broken."
        )


@pytest.mark.asyncio
async def test_INV4_replace_list_field_with_different_values():
    """
    INV-4 list variant: tags starts as ['a', 'b'].
    Process returns ['x', 'y', 'z']. State must reflect the new list.
    """
    initial_domain = ExpDomain(tags=["a", "b"])
    engine = _make_engine(domain=initial_domain)
    engine.register(p_replace_tags)

    await engine.execute("p_replace_tags", new_tags=["x", "y", "z"])

    committed = engine.state.data["domain"]["tags"]
    assert committed == ["x", "y", "z"], (
        f"INC-026 regression: tags should be ['x','y','z'], got {committed!r}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# INV-5: Proxy mutation (return None) still works after INC-026 fix
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_INV5_proxy_mutation_return_none_still_commits():
    """
    INV-5: Process uses ctx.domain.counter = value (proxy) and returns None.
    After INC-026 fix, the empty-dict merge base must not break the proxy path.
    """
    engine = _make_engine()
    engine.register(p_proxy_only_no_return)

    await engine.execute("p_proxy_only_no_return", value=42)

    committed = engine.state.data["domain"]["counter"]
    assert committed == 42, (
        f"Proxy mutation broken after INC-026 fix: counter should be 42, got {committed}"
    )


@pytest.mark.asyncio
async def test_INV5_proxy_mutation_sequential_3_times():
    """
    INV-5 sequential: proxy mutation 3 times with different values.
    Each must commit correctly.
    """
    engine = _make_engine()
    engine.register(p_proxy_only_no_return)

    for v in [10, 20, 30]:
        await engine.execute("p_proxy_only_no_return", value=v)
        committed = engine.state.data["domain"]["counter"]
        assert committed == v, (
            f"Proxy mutation sequential: after setting {v}, got {committed}"
        )


@pytest.mark.asyncio
async def test_INV5b_proxy_with_ack_string_proxy_wins():
    """
    INV-5b: Hybrid proxy+ack pattern.
    Process does: ctx.domain.counter = value; return "ok"

    Proxy value (value) must be committed, NOT the ack string "ok".
    This verifies that _proxy_delta_exists correctly suppresses the ack
    when pending_data[key] was already populated by build_pending_from_deltas().

    This is the CORRECT behavior: proxy-wins for hybrid patterns.
    Contrast with return-only (INV-1/INV-4) where return value wins.
    """
    engine = _make_engine()
    engine.register(p_proxy_with_ack)

    await engine.execute("p_proxy_with_ack", value=99)

    committed = engine.state.data["domain"]["counter"]
    assert committed == 99, (
        f"INC-026 INV-5b: proxy value should win over ack string. "
        f"Expected 99, got {committed!r}. "
        "If 'ok' is committed, _proxy_delta_exists check is broken."
    )


@pytest.mark.asyncio
async def test_INV5b_proxy_ack_sequential_3_times():
    """
    INV-5b sequential: hybrid proxy+ack pattern, 3 iterations.
    Each execution: proxy writes the correct value; ack must not overwrite.
    """
    engine = _make_engine()
    engine.register(p_proxy_with_ack)

    for v in [10, 20, 30]:
        await engine.execute("p_proxy_with_ack", value=v)
        committed = engine.state.data["domain"]["counter"]
        assert committed == v, (
            f"Proxy+ack sequential: after setting {v}, got {committed!r} "
            "(ack string may have overwritten proxy value)"
        )


# ═══════════════════════════════════════════════════════════════════════════
# INV-6: Cross-layer consistency — explicit output wins over shadow delta
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_INV6_explicit_return_wins_over_shadow_delta():
    """
    INV-6: Process reads domain.experiments (triggering shadow tracking),
    then returns a completely different list for domain.experiments.
    The returned list must win over any inferred shadow delta.

    This validates that Rust [v3.5 FIX] + INC-026 Fix 2 are consistent:
    explicit pending updates override stale shadow deltas at both layers.
    """
    initial = [{"name": "old_exp"}]
    initial_domain = ExpDomain(experiments=initial)
    engine = _make_engine(domain=initial_domain)
    engine.register(p_load_experiments)

    new_experiments = [{"name": "new_exp_A"}, {"name": "new_exp_B"}]
    await engine.execute("p_load_experiments", experiments_list=new_experiments)

    committed = engine.state.data["domain"]["experiments"]
    assert committed == new_experiments, (
        f"INC-026 / INV-6: explicit return should overwrite shadow delta. "
        f"Expected {new_experiments}, got {committed!r}"
    )


@pytest.mark.asyncio
async def test_INV6_partial_none_does_not_overwrite_other_output():
    """
    INV-6 partial: outputs=['domain.counter', 'domain.output_dir'].
    Return (None, 'new_dir'). 
    - domain.output_dir must be 'new_dir'
    - domain.counter must be unchanged (None = skip)
    """
    initial_domain = ExpDomain(counter=7, output_dir="old")
    engine = _make_engine(domain=initial_domain)
    engine.register(p_partial_none_return)

    await engine.execute("p_partial_none_return", out_dir="new_dir")

    domain_data = engine.state.data["domain"]
    assert domain_data["output_dir"] == "new_dir", (
        f"output_dir not updated: {domain_data['output_dir']!r}"
    )
    assert domain_data["counter"] == 7, (
        f"counter should be unchanged (None return), got {domain_data['counter']}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# INTEGRATION: Combined scenario — load config then advance episode
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_INTEGRATION_load_then_increment_pattern():
    """
    Integration regression: simulates the emotional-agent workflow that
    triggered INC-026.

    Step 1: p_load_experiments — returns experiment list (INV-2)
    Step 2: p_set_counter — sets counter to max_episodes (INV-4)
    Step 3: p_increment_counter x3 — counter must reach 3 (INV-4 sequential)

    Before INC-026 fix: Step 1 produced [], Step 2/3 left counter at 0.
    After fix: all steps commit correctly, counter reaches 3.
    """
    engine = _make_engine()
    engine.register(p_load_experiments)
    engine.register(p_set_counter)
    engine.register(p_increment_counter)

    # Step 1: load experiments
    experiments = [{"name": "SanityCheck", "max_episodes": 10}]
    await engine.execute("p_load_experiments", experiments_list=experiments)
    assert engine.state.data["domain"]["experiments"] == experiments, \
        "Step 1 failed: experiments not loaded"

    # Step 2: set counter (initialize episode tracking)
    await engine.execute("p_set_counter", value=0)
    assert engine.state.data["domain"]["counter"] == 0, \
        "Step 2 failed: counter not set to 0"

    # Step 3: increment 3 times
    for i in range(1, 4):
        await engine.execute("p_increment_counter")
        committed = engine.state.data["domain"]["counter"]
        assert committed == i, (
            f"Step 3 failed at episode {i}: counter stuck at {committed}. "
            "p_advance_episode pattern broken (INC-026 regression)."
        )

    # Final state: experiments still intact, counter at 3
    final = engine.state.data["domain"]
    assert final["experiments"] == experiments, "experiments corrupted during counter increments"
    assert final["counter"] == 3, f"Final counter should be 3, got {final['counter']}"
