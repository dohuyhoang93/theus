---
id: INC-021
title: Flux DSL Safety Trip Fails to Catch Empty While Loops
area: workflow
severity: high
introduced_in: v3.0 (Flux DSL initial implementation)
fixed_in: v3.0.23
status: resolved
---

# INC-021: Flux DSL Safety Trip Fails to Catch Empty While Loops

## Summary

The Flux DSL's infinite-loop protection mechanism (Safety Trip) places its operation counter (`ops_counter`) inside the step iterator (`for step in steps`), not at the while-loop level. When a while loop has an empty body (`do: []`), the step iterator never executes, the counter never increments, the safety trip never fires, and the program hangs indefinitely.

## Background

Flux DSL is a declarative workflow language (YAML) compiled into an Abstract Syntax Tree (AST) by the Rust parser in `fsm.rs`. The AST consists of four node types: `Process` (execute), `While` (loop), `If` (branch), and `Run` (group).

Safety Trip is a protection mechanism: a counter increments each time a step executes. When it exceeds `max_ops` (default 10,000), the engine halts with an error. This is intended to catch runaway loops in user-defined workflows.

## What Went Wrong

The `execute_steps` function in `fsm.rs` (lines 392–467) has this structure:

```
execute_steps(steps):
    for step in steps:          ← Counter increments here
        ops_counter += 1
        if ops_counter > max_ops: HALT
        match step:
            While { condition, do_steps }:
                while eval(condition):
                    execute_steps(do_steps)   ← Recursive call
```

When `do_steps` is empty (0 elements), the inner `for step in steps` loop body never runs. The counter stays at its initial value. The outer `while` loop iterates indefinitely with no check.

## Impact

- **Who:** Any user writing a workflow YAML with `do: []` and an always-true condition.
- **What broke:** The program hangs indefinitely — no error message, no timeout, no log output. The only recovery is killing the process.
- **Severity:** High — if YAML files are generated programmatically (e.g., from experiment parameters or external tooling), a minor bug in the generator could produce `do: []`, hanging the entire pipeline with no diagnostic output.

## Root Cause

**Micro cause (Logic):** The implicit assumption *"every while loop body contains at least one step"* is reasonable for hand-written workflows but is never validated. The YAML parser accepts `do: []` without warning.

**Macro cause (System):** The safety counter is placed at the wrong architectural layer. It is attached to the "step execution" layer (inside `for step`), while the actual hazard lives at the "control structure" layer (the `while` loop itself). When the step layer is empty, the control layer loses all oversight.

This is a classic case of **incomplete protection coverage** — the safety mechanism exists but does not span all execution paths.

## Why This Was Hard to Detect

1. **Normal workflows always work correctly** — every valid workflow has steps inside `do:`, so Safety Trip functions as intended.
2. **No edge-case tests for Flux DSL** — the original test suite (15 tests) only covered happy paths; no test exercised empty blocks.
3. **Silent failure mode** — no exception, no log output, the program simply hangs. There is no timeout mechanism at the Python layer to detect this.
4. **Same pattern hidden in `flux: run`** — `flux: run` with `steps: []` inside a `while` also fails to increment the counter, though it is less dangerous since `run` does not loop.

## Resolution

### Plan C (A + B combined) — Implemented

**Part A — Runtime fix (`fsm.rs` lines 460–471):**
Added `ops_counter += 1` and a Safety Trip check directly inside the `while` loop body, before calling `execute_steps` for the child step list:

```rust
FluxStep::While { condition, do_steps } => {
    while self.eval_condition(py, condition, ctx)? {
        // Plan A: count each loop iteration
        *ops_counter += 1;
        if *ops_counter > self.max_ops {
            return Err(PyRuntimeError::new_err(...));
        }
        self.execute_steps(py, do_steps, ...)?;
    }
}
```

**Part B — Parse-time warnings (`fsm.rs` lines 84–90, 106–112, 115–121):**
Added `eprintln!("[FLUX-WARN] ...")` when the parser encounters:
- `flux: while` with empty `do: []`
- `flux: if` with both `then` and `else` empty
- `flux: run` with empty `steps: []`

### Result

- `cargo clippy -- -D warnings`: 0 warnings
- `test_while_empty_do_block`: PASSED (previously had to be skipped due to hang)
- All 68 Flux DSL tests: PASSED
- Local CI: ALL GREEN

## Long-Term Changes

- Safety Trip now counts at both layers: the step layer (`for step`) AND the loop layer (`while` iteration).
- The parser emits early warnings for empty blocks — defense in depth.

## Preventive Actions

- [x] 53 new Flux DSL tests covering 4-case methodology: standard, related, boundary, conflict.
- [x] `test_while_empty_do_block` — exact reproduction test, now PASSED.
- [x] `test_while_max_ops_equals_1` — boundary test for minimum threshold.
- [x] `test_while_respects_max_ops_across_nesting` — Safety Trip across nested structures.
- [x] `cargo clippy -- -D warnings` enforced in Local CI pipeline.

## Related

- File modified: [fsm.rs](file:///c:/Users/dohoang/projects/EmotionAgent/theus_framework/src/fsm.rs)
- Reproduction test: [test_flux_while_4case.py](file:///c:/Users/dohoang/projects/EmotionAgent/theus_framework/tests/06_flux/test_flux_while_4case.py)
- Critical analysis: [critical_analysis_report.md](file:///C:/Users/dohoang/.gemini/antigravity/brain/4ff5a32f-30e5-4d78-ad75-a9019d0f6879/critical_analysis_report.md)

## Lessons Learned

1. **Safety mechanisms must be placed at the layer closest to the hazard** — the while loop is the source of infinite repetition, so it must have its own counter check, not rely solely on its children.
2. **If the parser permits it, the runtime must handle it** — if `do: []` is valid syntax, the executor must behave correctly when it encounters an empty body.
3. **Defense in depth outperforms single-layer protection** — an early warning (parser) combined with a late guard (runtime) ensures failures are caught regardless of which layer is bypassed.
