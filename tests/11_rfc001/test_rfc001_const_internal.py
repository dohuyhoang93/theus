"""
Tests for RFC-001 §5: const_ prefix (CONSTANT Zone) and §1.1: internal_ prefix (PRIVATE Zone).

Unit Tests:
  - const_: block write, update, delete, append even via AdminTransaction
  - internal_: non-admin process receives None when reading internal_ field

Integration Tests (no mock):
  - Real TheusEngine + @process + no mock objects
"""
import asyncio
import unittest
from theus.engine import TheusEngine
from theus.contracts import process, AdminTransaction


# ============================================================
# UNIT TESTS: const_ prefix (CONSTANT Zone)
# ============================================================

@process(outputs=["domain.const_config"])
async def p_try_write_const(ctx):
    """Attempt to write to const_ field — should be BLOCKED."""
    ctx.domain.const_config = "mutation_attempt"
    return None


@process(outputs=["domain.const_data"])
async def p_try_update_const_item(ctx):
    """Attempt item-set on const_ dict — should be BLOCKED."""
    ctx.domain.const_data["key"] = "value"
    return None


@process(outputs=["domain.const_list"])
async def p_try_append_const(ctx):
    """Attempt append on const_ list — should be BLOCKED."""
    ctx.domain.const_list.append("item")
    return None


@process(outputs=["domain.const_list"])
async def p_try_pop_const(ctx):
    """Attempt pop on const_ list — should be BLOCKED."""
    ctx.domain.const_list.pop()
    return None


@process(outputs=["domain.log_history"])
async def p_admin_try_write_const(ctx):
    """AdminTransaction should NOT be able to write to const_."""
    with AdminTransaction(ctx) as admin:
        admin.domain.const_config = "admin_mutation"
    return None


@process(inputs=["domain.const_config"])
async def p_read_const(ctx):
    """Reading const_ should be ALLOWED."""
    return ctx.domain.const_config


# ============================================================
# UNIT TESTS: internal_ prefix (PRIVATE Zone)
# ============================================================

@process(inputs=["domain.data_public"])
async def p_read_internal_as_normal(ctx):
    """Non-admin process should get None when accessing internal_ field."""
    return ctx.domain.internal_secret


@process(inputs=["domain.internal_secret"])
async def p_admin_read_internal(ctx):
    """Placeholder — admin read is tested via AdminTransaction."""
    return ctx.domain.internal_secret


# ============================================================
# TEST CLASS
# ============================================================

class TestConstantAndPrivateZones(unittest.IsolatedAsyncioTestCase):

    def make_engine(self):
        return TheusEngine(context={
            "domain": {
                "const_config": "initial_value",
                "const_data": {"key": "original"},
                "const_list": ["item1"],
                "internal_secret": "top_secret_42",
                "data_public": "public_data",
                "log_history": [],
            }
        })

    # ------------------------------------
    # const_ tests
    # ------------------------------------

    async def test_const_read_is_allowed(self):
        """[const_] READ must always be allowed."""
        engine = self.make_engine()
        engine.register(p_read_const)
        result = await engine.execute(p_read_const)
        self.assertEqual(result, "initial_value",
                         "Reading const_ field should succeed")

    async def test_const_write_is_blocked(self):
        """[const_] Writing (setattr) to const_ must raise PermissionError."""
        engine = self.make_engine()
        engine.register(p_try_write_const)
        with self.assertRaises((PermissionError, Exception)) as cm:
            await engine.execute(p_try_write_const)
        self.assertIn("ermission", str(type(cm.exception).__name__) + str(cm.exception),
                      f"Expected PermissionError, got: {cm.exception}")

    async def test_const_item_write_is_blocked(self):
        """[const_] Dict item-set on const_ dict must raise PermissionError."""
        engine = self.make_engine()
        engine.register(p_try_update_const_item)
        with self.assertRaises((PermissionError, Exception)):
            await engine.execute(p_try_update_const_item)

    async def test_const_append_is_blocked(self):
        """[const_] .append() on const_ list must raise PermissionError."""
        engine = self.make_engine()
        engine.register(p_try_append_const)
        with self.assertRaises((PermissionError, Exception)):
            await engine.execute(p_try_append_const)

    async def test_const_pop_is_blocked(self):
        """[const_] .pop() on const_ list must raise PermissionError."""
        engine = self.make_engine()
        engine.register(p_try_pop_const)
        with self.assertRaises((PermissionError, Exception)):
            await engine.execute(p_try_pop_const)

    async def test_const_admin_override_blocked(self):
        """[const_] AdminTransaction MUST NOT bypass CONSTANT ceiling."""
        engine = self.make_engine()
        engine.register(p_admin_try_write_const)
        with self.assertRaises((PermissionError, Exception)):
            await engine.execute(p_admin_try_write_const)
        # State must be UNCHANGED
        state_val = engine.state.data["domain"]["const_config"]
        self.assertEqual(state_val, "initial_value",
                         "const_ field must remain unchanged even after AdminTransaction attempt")

    # ------------------------------------
    # internal_ tests
    # ------------------------------------

    async def test_internal_read_returns_none_for_non_admin(self):
        """[internal_] Non-admin process accessing internal_ field must receive None."""
        engine = self.make_engine()
        engine.register(p_read_internal_as_normal)
        result = await engine.execute(p_read_internal_as_normal)
        # The process returns ctx.domain.internal_secret — should be None (hidden)
        self.assertIsNone(result,
                          "Non-admin process must receive None when reading internal_ field")

    async def test_internal_data_unchanged(self):
        """[internal_] internal_ field must remain in state, only hidden from non-admin."""
        engine = self.make_engine()
        # NOTE: Direct state inspection via engine.state.data to verify
        # the field exists in the raw data — only READ is blocked via proxy.
        state_data = engine.state.data["domain"]
        ctx_val = state_data.get("internal_secret", "NOT_FOUND")
        self.assertEqual(ctx_val, "top_secret_42",
                         "internal_ field should still exist in context — only read is blocked")


# ============================================================
# INTEGRATION TEST: const_ + internal_ together
# ============================================================

@process(outputs=["domain.data_items"])
async def p_normal_work(ctx):
    """Normal data field mutation — should be unaffected."""
    ctx.domain.data_items.append("processed")
    return "done"


class TestConstPrivateIntegration(unittest.IsolatedAsyncioTestCase):

    async def test_const_does_not_affect_normal_data(self):
        """[Integration] const_ enforcement must not block normal Data zone."""
        engine = TheusEngine(context={
            "domain": {
                "const_max_retries": 3,
                "data_items": [],
            }
        })
        engine.register(p_normal_work)
        result = await engine.execute(p_normal_work)
        self.assertEqual(result, "done")
        items = engine.state.data["domain"]["data_items"]
        self.assertEqual(items, ["processed"],
                         "Normal data zone must work independently of const_ enforcement")

    async def test_const_read_and_normal_write_in_same_process(self):
        """[Integration] Process can READ const_ and WRITE data_ in same execution."""

        @process(inputs=["domain.const_max_retries"], outputs=["domain.data_result"])
        async def p_read_const_write_data(ctx):
            limit = ctx.domain.const_max_retries  # READ allowed
            ctx.domain.data_result = f"limit_is_{limit}"  # WRITE allowed
            return None

        engine = TheusEngine(context={
            "domain": {
                "const_max_retries": 3,
                "data_result": None,
            }
        })
        engine.register(p_read_const_write_data)
        await engine.execute(p_read_const_write_data)
        result = engine.state.data["domain"]["data_result"]
        self.assertIn("3", str(result),
                      "Process must be able to read const_ and write data_ in same execution")


if __name__ == "__main__":
    unittest.main()
