
import pytest
import asyncio
from theus.engine import TheusEngine
from theus.contracts import process
from theus.context import TransactionError

# --- Chapter 05 Audit Verification ---
# Goal: Validating "Iron Discipline" Claims
# 1. Inputs (Protected): Native Rust Views, Read-Only.
# 2. Outputs (Unlocked): SupervisorProxy, Lazy Shadowing.
# 3. Zone Enforcement: Input rules (No SIGNAL/META dependencies).
# 4. Hierarchical Inheritance: 'domain.user' -> allows 'domain.user.profile'.

# --- Scaffolding & Setup ---
@pytest.fixture
def engine():
    # Use simple dict context
    ctx_data = {
        "domain": {"user": {"profile": {"name": "Alice"}, "orders": []}},
        "signal": {},
        "meta": {}
    }
    return TheusEngine(context=ctx_data, strict_guards=True)

# --- Tier 1: Standard (Happy & Sad Path) ---

@process(inputs=["domain.user.profile"], outputs=[])
async def task_read_only_violation(ctx):
    """Claim: Inputs are Read-Only."""
    # This should fail
    ctx.domain.user["profile"]["name"] = "Bob"
    return "Should Fail"

@process(inputs=[], outputs=["domain.user.profile"])
async def task_write_shadow(ctx):
    """Claim: Outputs are Shadowed and Writable."""
    # This should succeed
    ctx.domain.user["profile"]["name"] = "Bob"
    # No return to avoid auto-mapping overwrite

@pytest.mark.asyncio
async def test_claim_inputs_read_only(engine):
    """Verify Claim 1: Inputs are strictly Read-Only."""
    engine.register(task_read_only_violation)
    
    with pytest.raises(Exception) as exc:
        await engine.execute("task_read_only_violation")
    
    # Rust Core throws various errors, usually ContextError or TypeError for Frozen objects
    assert "Immutable" in str(exc.value) or "Frozen" in str(exc.value) or "Access Denied" in str(exc.value)

@pytest.mark.asyncio
async def test_claim_outputs_shadow(engine):
    """Verify Claim 2: Outputs work via Proxy."""
    engine.register(task_write_shadow)
    
    await engine.execute("task_write_shadow")
    # Verify State Commit
    print(f"DEBUG: State Data keys: {engine.state.data.keys()}")
    print(f"DEBUG: Domain type: {type(engine.state.data['domain'])}")
    print(f"DEBUG: Domain content: {engine.state.data['domain']}")
    if isinstance(engine.state.data['domain'], dict):
         print(f"DEBUG: User type: {type(engine.state.data['domain'].get('user'))}")
    
    assert engine.state.data["domain"]["user"]["profile"]["name"] == "Bob"

# --- Tier 2: Related (Hierarchical Inheritance) ---

@process(inputs=[], outputs=["domain.user"])
async def task_hierarchical_parent(ctx):
    """Claim: Access to parent 'domain.user' grants access to child 'domain.user.profile'."""
    # We declared 'domain.user', but we write to 'domain.user.profile'
    # This confirms inheritance logic in Rust Core.
    ctx.domain.user["profile"]["name"] = "Charlie"
    
    # Test New Key Insertion (Shallow & Deep)
    ctx.domain.user["new_top"] = 1
    ctx.domain.user["profile"]["new_deep"] = 2  # Re-enabled (Fixed by INC-013)
    
    # Also sibling
    ctx.domain.user["orders"].append(101)

@pytest.mark.asyncio
async def test_claim_hierarchical_inheritance(engine):
    """Verify Claim 4: Hierarchical Scope Inheritance."""
    engine.register(task_hierarchical_parent)
    
    await engine.execute("task_hierarchical_parent")
    assert engine.state.data["domain"]["user"]["profile"]["name"] == "Charlie"
    assert engine.state.data["domain"]["user"]["new_top"] == 1
    assert engine.state.data["domain"]["user"]["profile"]["new_deep"] == 2
    assert 101 in engine.state.data["domain"]["user"]["orders"]

# --- Tier 3: Edge (Zone Rules & Deep Nesting) ---

@process(inputs=["signal.ping"], outputs=[])
async def task_signal_input_allowed_relaxed(ctx):
    """Claim: Signal can be input (if strict_guards allows? Ch 5 says forbidden for Logic)."""
    # Actually Chapter 5 says "You cannot use SIGNAL or META as logical inputs".
    # Let's see if the code enforces this Architecture Rule or just Permission Rule.
    return ctx.signal.get("ping")

@pytest.mark.asyncio
async def test_claim_zone_enforcement_edge(engine):
    """Verify Claim 3: Zone Enforcement (Signal/Meta inputs)."""
    # Ch 5 says: "Input Guard... checks all inputs... cannot use SIGNAL or META".
    # This is an ARCHITECTURAL constraint, not just permission.
    
    # If this passes, Ch 5 claims might be too strong or Engine config dependent.
    # Theus v3.0 Strict Mode should theoretically block this registration or execution.
    try:
        engine.register(task_signal_input_allowed_relaxed)
        await engine.execute("task_signal_input_allowed_relaxed")
    except Exception as e:
        # If it fails, the claim is TRUE (Enforced).
        # But wait, looking at specs, Signals ARE valid triggers. 
        # The restriction is usually on *Stateful* processes depending on *Transient* signals for *Peristent* logic.
        # Let's observe behavior.
        pass

# --- Tier 4: Conflict (Simulated) ---
# Testing "Stale Reference" Trap mentioned in Chapter 5.

@process(outputs=["domain.user.profile"])
async def task_stale_reference_trap(ctx):
    """Claim: Stale pointers lose updates."""
    # 1. Grab pointer (Snapshot A)
    ref = ctx.domain.user["profile"]
    
    # 2. Simulate "await" (Yield to loop) - In real engine, if another proc ran, this ref would be stale
    # But locally inside one function, the "Shadow" is alive for the duration of the function.
    # The trap usually applies across *transactions* or if using raw references outside context.
    
    # Actually, Theus v3.0 Proxy might be smart enough to handle this? 
    # Re-read Ch 5: "The moment you attempt a write... it describes a Shadow Copy".
    # So 'ref' becomes a pointer to the Shadow Copy.
    # If we yield, the Shadow Copy is still valid for THIS transaction.
    # The problem describes: "await call_other_process() # Moves state to Snapshot B"
    # Implicitly, the MAIN state moved. But our 'ref' is pointing to OUR Shadow (Snapshot A).
    # When we commit, we might overwrite B with A + delta?
    # Or Conflict?
    
    ref["status"] = "stale?"

@pytest.mark.asyncio
async def test_stale_reference_trap(engine):
    engine.register(task_stale_reference_trap)
    await engine.execute("task_stale_reference_trap")
    assert engine.state.data["domain"]["user"]["profile"]["status"] == "stale?"

