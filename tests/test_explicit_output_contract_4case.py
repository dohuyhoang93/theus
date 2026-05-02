import asyncio
import pytest

from theus.engine import TheusEngine
from theus.contracts import process


# -----------------------------------------------------------------------------
# Explicit-output-only processes (no proxy mutation in process body)
# -----------------------------------------------------------------------------

@process(outputs=["domain.data"])
async def p_set_data_explicit(ctx, value):
    return value


@process(inputs=["domain.log"], outputs=["domain.log"])
async def p_append_log_explicit(ctx, msg):
    current = list(ctx.domain.log)
    current.append(msg)
    return current


@process(outputs=["domain.nested.sub.key", "domain.nested.sibling.flag"])
async def p_set_nested_explicit(ctx, value, flag):
    return value, flag


@process(inputs=["domain.documents"], outputs=["domain.documents"])
async def p_save_document_explicit(ctx, doc_id, payload):
    # Explicit return contract style: read snapshot -> build new object -> return
    docs = dict(ctx.domain.documents)
    docs[doc_id] = payload
    return docs


@process(inputs=["domain.counter_a"], outputs=["domain.counter_a"])
async def p_inc_a_explicit(ctx):
    return int(ctx.domain.counter_a) + 1


@process(inputs=["domain.counter_b"], outputs=["domain.counter_b"])
async def p_inc_b_explicit(ctx):
    return int(ctx.domain.counter_b) + 1


# -----------------------------------------------------------------------------
# 4 CASES: Mau / Lien quan / Bien / Xung dot
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_case_1_mau_explicit_basic_flow():
    """Mau: explicit contract writes simple scalar/list state correctly."""
    engine = TheusEngine(context={"domain": {"data": None, "log": []}})
    engine.register(p_set_data_explicit)
    engine.register(p_append_log_explicit)

    await engine.execute(p_set_data_explicit, value="hello")
    assert engine.state.data["domain"]["data"] == "hello"

    await engine.execute(p_append_log_explicit, msg="m1")
    await engine.execute(p_append_log_explicit, msg="m2")
    assert list(engine.state.data["domain"]["log"]) == ["m1", "m2"]


@pytest.mark.asyncio
async def test_case_2_lien_quan_explicit_nested_and_sibling_preserved():
    """Lien quan: deep-path explicit mapping must not destroy sibling branches."""
    engine = TheusEngine(
        context={
            "domain": {
                "nested": {
                    "sub": {"key": "old", "untouched": 1},
                    "sibling": {"x": 9},
                }
            }
        }
    )
    engine.register(p_set_nested_explicit)

    await engine.execute(p_set_nested_explicit, value="new", flag=True)

    assert engine.state.data["domain"]["nested"]["sub"]["key"] == "new"
    assert engine.state.data["domain"]["nested"]["sub"]["untouched"] == 1
    assert engine.state.data["domain"]["nested"]["sibling"]["x"] == 9
    assert engine.state.data["domain"]["nested"]["sibling"]["flag"] is True


@pytest.mark.asyncio
async def test_case_3_bien_explicit_burst_sequential_no_loss():
    """Bien: burst sequential explicit returns should not lose accumulated entries."""
    engine = TheusEngine(context={"domain": {"documents": {}}})
    engine.register(p_save_document_explicit)

    n = 200
    for i in range(n):
        doc_id = f"DOC-{i:04d}"
        await engine.execute(p_save_document_explicit, doc_id=doc_id, payload={"idx": i})

    docs = dict(engine.state.data["domain"]["documents"])
    assert len(docs) == n
    for i in range(n):
        k = f"DOC-{i:04d}"
        assert k in docs
        assert docs[k]["idx"] == i


@pytest.mark.asyncio
async def test_case_4_xung_dot_explicit_smart_cas_cross_field_concurrency():
    """
    Xung dot: concurrent writes to different fields should converge correctly.
    This validates field-level Smart CAS behavior under explicit output contract.
    """
    engine = TheusEngine(context={"domain": {"counter_a": 0, "counter_b": 0}})
    engine.register(p_inc_a_explicit)
    engine.register(p_inc_b_explicit)

    rounds = 30
    for _ in range(rounds):
        # Two independent-field updates launched concurrently each round
        await asyncio.gather(
            engine.execute(p_inc_a_explicit, retries=5),
            engine.execute(p_inc_b_explicit, retries=5),
        )

    assert int(engine.state.data["domain"]["counter_a"]) == rounds
    assert int(engine.state.data["domain"]["counter_b"]) == rounds
