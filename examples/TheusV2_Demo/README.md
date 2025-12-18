# Theus V2.1 Demo Project

This project simulates a **Real-world GUI Application** running on Theus OS.
It demonstrates:
1.  **Event-Driven Architecture**: FSM controls flow via `specs/workflow.yaml`.
2.  **Concurrency**: Heavy jobs run in background without freezing UI.
3.  **Safety**: Strict Locking prevents unauthorized writes.
4.  **Resilience**: Component crashes do not crash the kernels.

## How to Run

```bash
# From project root
python examples/TheusV2_Demo/app.py
```

## Interactive Commands

| Command | Effect | What to verify |
| :--- | :--- | :--- |
| `start` | Triggers normal workflow (`p_init` -> `p_process` -> `p_finalize`) | Watch logs flow. UI remains responsive. |
| `status` | Checks internal state (`Global` + `Domain`) | Should show `SUCCESS` after run. |
| `hack` | Attempts unauthorized write to Context | Should show `UNSAFE MUTATION` error log. Status remains safe. |
| `crash` | Triggers a process crash | Logic error logged. App stays alive. |
| `reset` | Resets state to IDLE | Ready for next run. |

## Structure

*   `app.py`: Main Entry Point (Simulates GUI Loop).
*   `specs/workflow.yaml`: The Logic Mapping.
*   `specs/audit_recipe.yaml`: The Business Rules.
*   `src/processes/`: The Worker Functions.
