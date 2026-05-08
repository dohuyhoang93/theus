# RFC 004: Lớp Audit Semantic Cho Theus POP

**Phiên bản**: 0.1  
**Trạng thái**: Đề xuất  
**Ngày**: Tháng 5, 2026  
**Người đề xuất**: EmotionAgent Team  
**Liên quan**: Theus 3.0.26+  

---

## 1. Tóm tắt

Hiện tại, Theus có **structural audit** bên trong mỗi process (`@process` contract) — kiểm tra input/output/side-effects. Nhưng lỗi **cross-process semantic** (ví dụ: `current_time` double-increment, inconsistent spike rate) không bị phát hiện.

RFC này đề xuất xây dựng lớp **semantic audit** dựa trên **parameterized invariant templates** — cho phép định nghĩa các bất biến (invariant) có thể tái sử dụng trên bất kỳ tổ hợp parameter nào, mà không cần build một temporal logic engine đầy đủ.

**Giải pháp được khuyến nghị**: 10-15 template classes (~1-2 tuần implementation) thay vì fully general framework (~3-5 tuần + technical debt).

---

## 2. Bài toán

### 2.1 Sự kiện kích hoạt
EmotionAgent gặp bug: `avg_firing_rate = 0.0` dù neurons bắn spikes chính xác.

**Root cause**: `snn_composite_theus.py` increment `current_time` 2 lần/tick:
```python
# BỀU BỆNH
snn_ctx.domain_ctx.current_time = int(snn_ctx.domain_ctx.current_time) + 1  # Manual
_tick_impl(ctx)  # Cũng increment time
```

Homeostasis đọc tick sai → thấy không có spike → reset `avg_firing_rate = 0`.

### 2.2 Vấn đề hệ thống
Structural audit không thể phát hiện vì:
- ✅ Input của `homeostasis_process` = hợp lệ
- ✅ Output của `homeostasis_process` = hợp lệ (đó là cách nó hoạt động)
- ❌ Nhưng **cross-process invariant bị vi phạm**: `current_time` không đơn điệu

**Phạm vi**: Kiểu lỗi này sẽ lặp lại khi:
- Thêm process mới có temporal dependencies
- Refactor state storage (shared memory, heavy zones)
- Tối ưu hóa pipeline (parallel steps, batching)

### 2.3 Spectrum solution
| Cách tiếp cận | Effort | Coverage | Technical debt |
|---|---|---|---|
| Domain-specific checks | 1 ngày/invariant | SNN only | Cao (hardcoded) |
| **Parameterized templates** | 1-2 tuần (total) | 90% lỗi phổ biến | Thấp |
| Fully general semantic audit | 3-5 tuần | 99% lỗi | Cao (temporal logic engine) |
| Formal verification (TLA+) | 2-4 tháng | 100% | Extreme |

---

## 3. Giải pháp đề xuất

### 3.1 Kiến trúc tổng quan

```
┌─────────────────────────────────────────────────────┐
│     Theus Process Framework (existing)              │
│  - Input/Output contract audit                      │
│  - Per-process safety guards                        │
└─────────────────────────────────────────────────────┘
                        ↑
                        │ (Snapshot reads)
┌─────────────────────────────────────────────────────┐
│   Semantic Audit Layer (NEW)                        │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │  Parameterized Invariant Templates           │  │
│  │  - MonotonicCounter, EMAConsistency, etc.   │  │
│  └──────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────┐  │
│  │  Snapshot Store (Ring Buffer)                │  │
│  │  - Lưu process state theo tick               │  │
│  │  - Tunable window size & sampling            │  │
│  └──────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────┐  │
│  │  Invariant Registry & Executor               │  │
│  │  - Declarative registration                  │  │
│  │  - Run at: end-of-tick, async, periodic      │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### 3.2 Template catalog (Pha 1)

Mỗi template là một class Python ~50 LOC với method `check(snapshots) -> bool`.

#### Template 1: MonotonicCounter
```python
class MonotonicCounter(SemanticInvariant):
    """Giá trị counter phải tăng đơn điệu (hoặc giữ nguyên)."""
    
    def __init__(self, process_name: str, path: str, 
                 strict=True, window=2):
        # strict=True: a[i] <= a[i+1] (cho phép equal)
        # strict=False: a[i] < a[i+1]
        self.process_name = process_name
        self.path = path  # "domain_ctx.current_time"
        self.strict = strict
        self.window = window
    
    def check(self, snapshots: List[Dict]) -> bool:
        """snapshots[-window:] là N ticks gần nhất"""
        values = [extract_path(s[self.process_name], self.path) 
                  for s in snapshots[-self.window:]]
        
        for i in range(len(values) - 1):
            if self.strict and values[i] > values[i+1]:
                return False
            elif not self.strict and values[i] >= values[i+1]:
                return False
        return True
    
    def on_violation(self, snapshots: List[Dict]) -> str:
        """Thông báo chi tiết"""
        return f"MonotonicCounter violation at {self.path}: {values}"
```

#### Template 2: EMAConsistency
```python
class EMAConsistency(SemanticInvariant):
    """Kiểm tra: avg ≈ EMA(spike_count)"""
    
    def __init__(self, process_name: str, 
                 count_path: str,    # "metrics.spike_count"
                 ema_path: str,       # "metrics.avg_firing_rate"
                 alpha: float,        # EMA decay
                 tolerance: float):   # ±tolerance
        self.process_name = process_name
        self.count_path = count_path
        self.ema_path = ema_path
        self.alpha = alpha
        self.tolerance = tolerance
    
    def check(self, snapshots: List[Dict]) -> bool:
        """Tính EMA thủ công và so sánh với stored ema"""
        counts = [extract_path(s[self.process_name], self.count_path)
                  for s in snapshots]
        ema_stored = extract_path(snapshots[-1][self.process_name], 
                                  self.ema_path)
        
        # Tính EMA từ counts
        ema_computed = 0.0
        for count in counts:
            ema_computed = self.alpha * count + (1 - self.alpha) * ema_computed
        
        return abs(ema_computed - ema_stored) <= self.tolerance
```

#### Template 3: CrossProcessMatch
```python
class CrossProcessMatch(SemanticInvariant):
    """Kiểm tra: writer value ≈ reader value (within lag)"""
    
    def __init__(self, writer_process: str, writer_path: str,
                 reader_process: str, reader_path: str,
                 max_lag: int = 2):
        self.writer_process = writer_process
        self.writer_path = writer_path
        self.reader_process = reader_process
        self.reader_path = reader_path
        self.max_lag = max_lag
    
    def check(self, snapshots: List[Dict]) -> bool:
        """Kiểm tra writer value xuất hiện trong reader 
        trong vòng max_lag ticks."""
        writer_value = extract_path(snapshots[-1][self.writer_process],
                                    self.writer_path)
        
        # Tìm reader_value trong max_lag ticks gần đây
        for i in range(-self.max_lag, 0):
            reader_value = extract_path(snapshots[i][self.reader_process],
                                       self.reader_path)
            if reader_value == writer_value:
                return True
        return False
```

#### Template 4-15: Khác
- `RateBoundedness`: metric nằm trong [min, max]
- `SumConservation`: tổng input = tổng output (±tolerance)
- `CausalityOrdering`: event A xảy ra trước B
- `NoRegression`: metric không thoái hóa (gradual)
- `DeadlockDetection`: process không bị stuck
- v.v.

### 3.3 Snapshot Store

```python
class SnapshotStore:
    """Ring buffer lưu (tick, process_states) tuples"""
    
    def __init__(self, window_size: int = 20):
        self.window_size = window_size
        self.buffer = collections.deque(maxlen=window_size)
        self.current_tick = 0
    
    def record(self, tick: int, process_name: str, state: Dict):
        """Ghi state của 1 process tại 1 tick"""
        # Lazy init: nếu tick mới, tạo entry mới
        if not self.buffer or self.buffer[-1]["tick"] != tick:
            self.buffer.append({"tick": tick, "processes": {}})
        
        self.buffer[-1]["processes"][process_name] = state
    
    def get_window(self, num_ticks: int = None) -> List[Dict]:
        """Trả về snapshots của N ticks gần nhất
        Mỗi snapshot = {tick, {process_name: state}}"""
        if num_ticks is None:
            num_ticks = len(self.buffer)
        return list(self.buffer)[-num_ticks:]
```

### 3.4 Registry & Executor

```python
class SemanticAuditRegistry:
    """Quản lý & chạy invariant checks"""
    
    def __init__(self, snapshot_store: SnapshotStore):
        self.store = snapshot_store
        self.invariants: List[SemanticInvariant] = []
        self.violations: List[str] = []
    
    def register(self, invariant: SemanticInvariant):
        """Thêm 1 invariant vào registry"""
        self.invariants.append(invariant)
    
    def check_all(self, trigger: str = "end-of-tick"):
        """Chạy tất cả invariants"""
        snapshots = self.store.get_window()
        for inv in self.invariants:
            if not inv.check(snapshots):
                violation = inv.on_violation(snapshots)
                self.violations.append(violation)
                
                # Log hoặc raise tùy mode
                if self.strict_mode:
                    raise SemanticViolation(violation)
                else:
                    logger.warning(violation)
    
    def report(self) -> Dict:
        """Trả về báo cáo toàn bộ violations"""
        return {
            "total_checks": len(self.invariants),
            "violations": self.violations,
            "violation_rate": len(self.violations) / (len(self.invariants) * num_checks)
        }
```

### 3.5 Integration với Theus

```python
# Trong snn_composite_theus.py (hoặc orchestrator process)

from audit import SemanticAuditRegistry, MonotonicCounter, EMAConsistency

# Khởi tạo
audit = SemanticAuditRegistry(snapshot_store=SnapshotStore(window_size=20))

# Đăng ký invariants
audit.register(MonotonicCounter(
    process_name="snn_composite",
    path="domain_ctx.current_time",
    strict=True, window=2
))

audit.register(EMAConsistency(
    process_name="snn_core",
    count_path="metrics.spike_count",
    ema_path="metrics.avg_firing_rate",
    alpha=0.05,
    tolerance=0.01
))

# Trong transaction loop
for tick in range(num_ticks):
    # ... run processes ...
    
    # Ghi snapshot
    audit.store.record(tick, "snn_composite", ctx.domain)
    audit.store.record(tick, "snn_core", metrics)
    
    # Kiểm tra semantic
    audit.check_all(trigger="end-of-tick")
```

---

## 4. Lợi ích

| Lợi ích | Chi tiết |
|---|---|
| **Phát hiện lỗi sớm** | Bug cross-process lộ diện trong 1-2 tick |
| **Tái sử dụng** | Template có thể dùng cho bất kỳ project Theus nào |
| **Ít technical debt** | Parameterized ≠ hardcoded; không phải maintain 100 checks |
| **Giáo dục** | Document lỗi temporal phổ biến qua template catalog |
| **Tunable overhead** | Có thể turn off checks trong production, async mode |
| **Composable** | Combine multiple templates để kiểm tra complex scenarios |

---

## 5. Chi phí & Rủi ro

### 5.1 Chi phí

| Giai đoạn | Effort | Công việc |
|---|---|---|
| **Phase 0: Design** | 2 ngày | Finalize template API, snapshot store design |
| **Phase 1: Core** | 5 ngày | SemanticInvariant base class, SnapshotStore, Registry |
| **Phase 2: Templates** | 5 ngày | Implement 10-15 template classes |
| **Phase 3: Integration** | 3 ngày | Integrate vào snn_composite, rl_bridge, orchestrator |
| **Phase 4: Testing** | 3 ngày | Unit tests + integration tests |
| **Tổng** | **~2 tuần** | - |

### 5.2 Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| **Memory overhead** | Snapshot store có max window; có thể sample thinly |
| **CPU overhead** | Check chỉ run end-of-tick, không mỗi nanosecond |
| **False positives** | Template config cần tuning (alpha, tolerance) |
| **Incomplete coverage** | 90% lỗi phổ biến; 10% cần case-specific checks |

### 5.3 Không phát hiện được
- Lỗi quá tinh tế (ví dụ: cache miss timing)
- Lỗi deterministic chaos (seed-dependent)
- Lỗi ngoài Theus (OS, CUDA timing)

---

## 6. Milestone & Success Criteria

### Milestone 1 (Day 1-2): Design finalized
- [ ] Template interface defined
- [ ] Snapshot store API frozen
- [ ] Registry design approved

### Milestone 2 (Day 3-7): Core implementation
- [ ] SemanticInvariant base class ✅
- [ ] SnapshotStore with ring buffer ✅
- [ ] Registry with check_all() ✅
- [ ] 10-12 templates implemented ✅

### Milestone 3 (Day 8-10): Integration
- [ ] snn_composite hoàn tác double-increment bug ✅ (đã làm)
- [ ] Audit registry integrated vào snn_composite ✅
- [ ] Violations properly logged + reported ✅

### Milestone 4 (Day 11-14): Validation & Rollout
- [ ] Unit test coverage >= 80%
- [ ] EmotionAgent runs 100+ episodes without audit violations
- [ ] Memory overhead < 5% (window_size=20)
- [ ] CPU overhead < 1% (end-of-tick checks)

### Success Criteria
```
✅ RFC bug (double-increment) được detect bởi MonotonicCounter
✅ EMAConsistency catches spike-rate inconsistencies
✅ CrossProcessMatch validates writer-reader handoff
✅ Violations logged với stack trace rõ ràng
✅ Zero regression trong other processes
✅ Documentation & examples cho team
```

---

## 7. Alternative Approaches Considered

### 7.1 Domain-specific hardcoded checks
```python
if snn_ctx.domain_ctx.current_time != prev_current_time + 1:
    raise ValueError("current_time not monotonic")
```
**Đánh giá**: Nhanh nhưng không scale; mỗi bug cần 1 check.

### 7.2 Fully general temporal logic engine
Implement TLA+ hoặc LTL model checker.

**Đánh giá**: Rất mạnh nhưng 2-4 tháng; overkill cho EmotionAgent.

### 7.3 Machine learning anomaly detection
Train model để detect suspicious state patterns.

**Đánh giá**: Cao cấp nhưng black box; debug khó; cần lớn data.

### 7.4 Proposed approach (Parameterized templates)
**Lý do chọn**: Best tradeoff — reusable, understandable, 1-2 tuần, maintenance thấp.

---

## 8. Questions for Reviewers

1. **Snapshot overhead**: Window size = 20 ticks, lưu ~5 processes × 50 fields = ~5KB/tick. Chấp nhận được?
2. **Trigger frequency**: End-of-tick, mỗi N ticks, hay async? Recommendation?
3. **Failure mode**: Violations nên raise exception hay log warning?
4. **Template priority**: Nên implement MonotonicCounter, EMAConsistency, CrossProcessMatch trước, hay khác?
5. **Future scope**: Có extend scope thành formal verification sau không?

---

## 9. References

- [Theus: Process-Oriented Programming](../00_Start_Here_Map.md)
- [EmotionAgent: SNN-RL Hybrid](../../EmotionAgent)
- [RFC 001: POP Zones](./RFC_001.md) — state organization precedent
- [RFC 002: Temporal Consistency](./RFC_002.md) — temporal concerns in POP
- [RFC 003: Cross-process Communication](./RFC_003.md) — inter-process sync model

---

## 10. Timeline

```
Week 1 (May 8-14):
  Mon-Tue: Design finalize
  Wed-Fri: Core + Phase 1-2 templates

Week 2 (May 15-21):
  Mon-Wed: Remaining templates + Integration
  Thu-Fri: Testing + Documentation

Week 3 (May 22-28):
  Mon: Validation runs
  Tue-Wed: Bug fixes
  Thu-Fri: Rollout + team onboarding
```

---

## 11. Sign-off

| Role | Người | Ký | Ngày |
|---|---|---|---|
| Proposer | EmotionAgent Team | - | 2026-05-08 |
| Theus Maintainer | - | [ ] | [ ] |
| Tech Lead | - | [ ] | [ ] |

