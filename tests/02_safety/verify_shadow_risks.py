"""
Kiểm chứng 5 rủi ro Shadow Copy — kết quả ghi VÀO FILE (bypass Rust trace noise).
"""
import sys, time, gc, tracemalloc, io, os, traceback

RESULTS_FILE = os.path.join(os.path.dirname(__file__), "shadow_risk_results.txt")

def log(msg):
    with open(RESULTS_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def main():
    # NOTE: Clear file
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        f.write("=== Shadow Copy Risk Verification ===\n\n")

    from theus import TheusEngine as Theus
    from theus_core import SupervisorProxy

    # ===== RISK 1: GC Pressure =====
    try:
        log("[RISK-1] GC Pressure từ deepcopy object lớn")
        t = Theus()
        big_data = {}
        for i in range(10_000):
            big_data[f"key_{i}"] = list(range(100))
        t.compare_and_swap(0, data={"domain": big_data})

        gc.collect()
        tracemalloc.start()
        mem_before = tracemalloc.get_traced_memory()[0]

        with t.transaction() as tx:
            root = SupervisorProxy(t.state.data, path="", read_only=False, transaction=tx)
            t_start = time.perf_counter()
            _ = root["domain"]
            access_ms = (time.perf_counter() - t_start) * 1000
            mem_after = tracemalloc.get_traced_memory()[0]
            mem_delta_mb = (mem_after - mem_before) / (1024 * 1024)

        tracemalloc.stop()
        log(f"  Dict: 10K keys × 100 items")
        log(f"  Memory delta: {mem_delta_mb:.2f} MB")
        log(f"  Access time: {access_ms:.2f} ms")
        if mem_delta_mb > 1.0:
            log(f"  ✅ CONFIRMED: deepcopy tạo bản sao lớn ({mem_delta_mb:.1f} MB)")
        else:
            log(f"  ❌ DISPROVED: memory delta nhỏ ({mem_delta_mb:.2f} MB)")
    except Exception as e:
        log(f"  ❌ ERROR: {e}")

    # ===== RISK 2: Proxy Leak =====
    try:
        log("\n[RISK-2] deep_merge_cow proxy leak vào state")
        t = Theus()
        t.compare_and_swap(0, data={"domain": {"items": ["a"], "nested": {"count": 1}}})

        with t.transaction() as tx:
            root = SupervisorProxy(t.state.data, path="", read_only=False, transaction=tx)
            domain = root["domain"]
            domain["new_ref"] = {"data": "test"}

        state = t.state.data["domain"]
        proxy_found = False
        for key, val in state.items():
            vt = type(val).__name__
            if "Proxy" in vt or "Supervisor" in vt:
                proxy_found = True
                log(f"  ⚠️ state['{key}'] = {vt}")
            else:
                log(f"  state['{key}'] type = {vt}")

        if proxy_found:
            log("  ✅ CONFIRMED: Proxy lẫn vào committed state")
        else:
            log("  ❌ DISPROVED: Không có proxy trong state")
    except Exception as e:
        log(f"  ❌ ERROR: {e}")

    # ===== RISK 3: Cache ID reuse =====
    try:
        log("\n[RISK-3] Cache ID reuse sau GC")
        t = Theus()
        t.compare_and_swap(0, data={"domain": {"items": ["a"]}})

        collision_count = 0
        seen_ids = set()
        for i in range(10_000):
            obj = {"temp_key": i, "data": list(range(10))}
            obj_id = id(obj)
            if obj_id in seen_ids:
                collision_count += 1
            seen_ids.add(obj_id)
            del obj
            if i % 1000 == 0:
                gc.collect()
        log(f"  ID collisions (reuse) ngoài transaction: {collision_count}/10000")

        with t.transaction() as tx:
            root = SupervisorProxy(t.state.data, path="", read_only=False, transaction=tx)
            domain1 = root["domain"]
            items1 = list(domain1["items"])

            # GC stress
            for _ in range(5000):
                temp = {"x": list(range(100))}
                del temp
            gc.collect()

            domain2 = root["domain"]
            items2 = list(domain2["items"])

        if items1 == items2 == ["a"]:
            log("  ❌ DISPROVED: Cache ổn định qua GC stress")
        else:
            log(f"  ✅ CONFIRMED: Cache corrupt! before={items1} after={items2}")
    except Exception as e:
        log(f"  ❌ ERROR: {e}")

    # ===== RISK 4: Deepcopy fallback =====
    try:
        log("\n[RISK-4] Deepcopy fallback phá isolation")
        t = Theus()
        # NOTE: BytesIO CÓ THỂ deepcopy trong Python. Thử object thật sự không deepcopy-able.
        import _thread
        lock = _thread.allocate_lock()
        # Lock objects KHÔNG THỂ pickle/deepcopy
        try:
            import copy
            copy.deepcopy({"lock": lock})
            can_deepcopy_lock = True
        except Exception:
            can_deepcopy_lock = False
        log(f"  _thread.lock deepcopy-able: {can_deepcopy_lock}")

        # Dùng dict chứa lock
        t.compare_and_swap(0, data={"domain": {"my_lock": lock, "counter": 0}})
        original_domain = t.state.data["domain"]
        original_id = id(original_domain)

        with t.transaction() as tx:
            root = SupervisorProxy(t.state.data, path="", read_only=False, transaction=tx)
            domain = root["domain"]
            inner = domain.supervisor_target
            shadow_id = id(inner)
            is_same = (shadow_id == original_id)

        log(f"  Original domain id: {original_id:#x}")
        log(f"  Shadow domain id:   {shadow_id:#x}")
        log(f"  Is same object: {is_same}")

        if is_same:
            log("  ✅ CONFIRMED: Deepcopy fail → fallback trả original (phá isolation)")
        else:
            log("  ❌ DISPROVED: Deepcopy thành công hoặc fallback tạo bản sao khác")
    except Exception as e:
        log(f"  ❌ ERROR: {e}")
        log(f"  traceback: {traceback.format_exc()}")

    # ===== RISK 5: O(N) delta per append =====
    try:
        log("\n[RISK-5] O(N) delta logging per append")
        t = Theus()
        big_list = list(range(10_000))
        t.compare_and_swap(0, data={"domain": {"items": big_list}})

        with t.transaction() as tx:
            root = SupervisorProxy(t.state.data, path="", read_only=False, transaction=tx)
            items = root["domain"]["items"]

            for i in range(5):
                items.append(f"new_{i}")

            delta_log = tx.get_delta_log()
            log(f"  List size: {len(big_list)}")
            log(f"  Appends: 5")
            log(f"  Delta entries: {len(delta_log)}")

            total_items = 0
            for entry in delta_log:
                if entry.value is not None and isinstance(entry.value, list):
                    total_items += len(entry.value)
                    log(f"    path='{entry.path}' op='{entry.op}' value_len={len(entry.value)}")
                else:
                    vt = type(entry.value).__name__ if entry.value is not None else "None"
                    log(f"    path='{entry.path}' op='{entry.op}' value_type={vt}")

        if total_items > 10_000:
            log(f"  ✅ CONFIRMED: Total items in deltas={total_items} (>> 5)")
        else:
            log(f"  ❌ DISPROVED: Delta size hợp lý ({total_items})")
    except Exception as e:
        log(f"  ❌ ERROR: {e}")

    # ===== BONUS: Deepcopy vs Heavy Zone =====
    try:
        log("\n[BONUS] Deepcopy vs Heavy Zone performance")
        t = Theus()
        data_50k = {}
        for i in range(50_000):
            data_50k[f"key_{i}"] = [i, i+1, i+2]
        t.compare_and_swap(0, data={"domain": data_50k}, heavy={"buffer": data_50k.copy()})

        # Data Zone
        with t.transaction() as tx:
            root = SupervisorProxy(t.state.data, path="", read_only=False, transaction=tx)
            t_start = time.perf_counter()
            _ = root["domain"]
            data_ms = (time.perf_counter() - t_start) * 1000

        # Heavy Zone
        with t.transaction() as tx:
            root_h = SupervisorProxy(t.state.heavy, path="heavy", read_only=False, transaction=tx)
            t_start = time.perf_counter()
            _ = root_h["buffer"]
            heavy_ms = (time.perf_counter() - t_start) * 1000

        log(f"  Data: 50K keys × 3 items")
        log(f"  Data Zone (deepcopy): {data_ms:.2f} ms")
        log(f"  Heavy Zone (zero-copy): {heavy_ms:.2f} ms")
        speedup = data_ms / max(heavy_ms, 0.001)
        log(f"  Speedup: {speedup:.1f}x")
        if speedup > 5:
            log(f"  ✅ CONFIRMED: Deepcopy overhead có đo được")
        elif data_ms > 10:
            log(f"  ⚠️ PARTIAL: Overhead tồn tại ({data_ms:.0f}ms) nhưng speedup chỉ {speedup:.1f}x")
        else:
            log(f"  ❌ DISPROVED: Deepcopy nhanh ({data_ms:.2f}ms)")
    except Exception as e:
        log(f"  ❌ ERROR: {e}")

    log("\n=== DONE ===")

if __name__ == "__main__":
    main()
