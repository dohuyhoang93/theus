# Theus v3.0 Test Strategy & Coverage Matrix
**Date:** 2026-01-15
**Status:** FULLY COMPLIANT with `THEUS_V3_MIGRATION_AUDIT.md`.
**Purpose:** Re-designing the Test Suite to align with the "Hardened" architecture of v3.0, ensuring coverage of Legacy Mechanics and New Parallel Safety guarantees.

---

# 1. Triết lý Kiểm thử v3.0
*   **Proof-based Testing:** Cố tình vi phạm ràng buộc để kiểm chứng sự cứng rắn của hệ thống.
*   **Stress Testing:** Tập trung vào các kịch bản Data Race và Deadlock trong môi trường Async.

---

# 2. Cấu trúc Thư mục Test Mới

```bash
tests/
├── 01_core/              # [RETAINED/EVOLVED] Test cơ chế cốt lõi
│   ├── test_context_immutability.py  # Check Zero-Copy Structs
│   ├── test_engine_polymorphism.py   # Ensure Sync/Async executes on correct threads
│   ├── test_config_schema.py         # Verify Serde strict typing & validation
│   └── test_transaction_rollback.py  # Verify Persistent Struct Rollback (MVCC)
├── 02_safety/            # [CRITICAL] Test an toàn song song & Semantic
│   ├── test_concurrency_cas.py       # (New) Verify Atomic CAS (Compare-And-Swap) logic
│   ├── test_snapshot_isolation.py    # (New) Verify Consistent Reads during concurrent writes
│   ├── test_semantic_firewall.py     # Verify Pure Process is blocked from Signal/Meta
│   └── test_hierarchical_scopes.py   # Verify Output Permissions
├── 03_mechanics/         # [RETAINED] Test cơ chế vận hành cũ
│   ├── test_audit_levels.py          # (New) Verify S-A-B-C, Dual Thresholds, Reset Logic
│   ├── test_workflow_graph.py        # (New) Verify Graph Execution (Flux/Pipeline unified)
│   └── test_lifecycle_scopes.py      # Verify Local Auto-drop (RAII)
├── 04_features/          # [NEW] Tính năng mới v3
│   ├── test_heavy_zone.py            # Verify Arc<T> Reference Counting
│   ├── test_outbox_transaction.py    # Verify Intent Recording & Worker Retry
│   └── test_sub_interpreter.py       # (Experimental) Parallelism
└── 05_compat/            # [RETAINED] Đảm bảo tương thích ngược
    └── test_workflow_legacy.py       # Legacy YAML parsing check
```

---

# 3. Ma trận Bao phủ (Coverage Matrix)

### Nhóm 1: Cơ chế Cốt lõi & Vận hành (Core & Mechanics)

| Cơ chế (Audit) | Test Case Logic | File Đại diện |
| :--- | :--- | :--- |
| **Audit Log** | 1. Trigger lỗi cấp 'C'. <br> 2. Verify Count tăng. <br> 3. Verify Block khi vượt Max Threshold. <br> 4. Verify Reset khi Success (nếu config bật). | `test_audit_levels.py` |
| **Workflow** | Define Complex Graph (If/Loop). Run Engine. Verify path traversal matches Expression outcome. | `test_workflow_graph.py` |
| **Config Loader** | Load Malformed YAML. Check Rust Logic (Serde) reject types. | `test_config_schema.py` |

### Nhóm 2: An toàn Song song (Parallel Safety) - QUAN TRỌNG NHẤT

| Cơ chế (Audit) | Test Case Logic | File Đại diện |
| :--- | :--- | :--- |
| **Data Race (CAS)** | 1. 100 Process cùng đọc `x=0` và ghi `x=x+1`. <br> 2. Verify kết quả cuối cùng phải là 100 (hoặc retry log). <br> 3. Verify `StateUpdate` version mismatch bị từ chối. | `test_concurrency_cas.py` |
| **Inconsistency** | 1. Process A (Long running) đọc `x`. <br> 2. Process B (Fast) sửa `x`. <br> 3. Verify Process A vẫn thấy giá trị cũ của `x` cho đến khi nó kết thúc (Snapshot Isolation). | `test_snapshot_isolation.py` |
| **Deadlock** | 1. Spawn Process giữ lock lâu. <br> 2. Verify Writer khác bị Timeout (không treo mãi mãi). | `test_concurrency_cas.py` |

### Nhóm 3: Semantic & An toàn Bộ nhớ

| Cơ chế (Audit) | Test Case Logic | File Đại diện |
| :--- | :--- | :--- |
| **Semantic Firewal** | Pure Function attempt access `ctx.signal`. Verify `PermissionError` (Compile/Load time). | `test_semantic_firewall.py` |
| **Lifecycles** | Async Task finish -> Access `ctx.local` -> Verify `None` (Memory Freed). | `test_lifecycle_scopes.py` |
| **Heavy Zone** | Init `Heavy(Tensor)`. Pass to multiple processes. Verify Address Unchanged (No Copy). | `test_heavy_zone.py` |

---

# 4. Kế hoạch Hành động (Action Plan)

1.  **Phase 1: Deep Mechanics Tests (Audit & Workflow)**
    *   Implement `test_audit_levels.py` để đảm bảo logic đa ngưỡng S-A-B-C (v2 legacy) được tái hiện chính xác trên Rust.
    *   Implement `test_workflow_graph.py` để kiểm tra Execution Engine mới.

2.  **Phase 2: Extreme Concurrency Tests**
    *   Đây là phần khó nhất. Cần implement `test_concurrency_cas.py` và `test_snapshot_isolation.py` dùng `pytest-asyncio`. Đây là nơi kiểm chứng độ "cường hóa" của v3.

3.  **Phase 3: Integration Tests**
    *   Kết nối Context, Engine, và Outbox để chạy các luồng nghiệp vụ thực tế.
