# ADR-014: Rust-Native State — Thoát Khỏi Python Dependency

**Trạng thái:** PROPOSED  
**Ngày:** 2026-05-06  
**Tác giả:** Analysis Session  
**Liên quan:** ADR-002 (Supervisor Architecture), ADR-009 (Rust Stack), ADR-010 (Context Safety)

---

## 1. Bối Cảnh

Theus được thiết kế như một **Process-Oriented Programming framework** — không phải một Python library. POP là một mô hình tính toán tổng quát: state machine, isolation, CAS, zone physics. Không có lý do gì những khái niệm này phải được implemented bằng Python objects.

**Tuy nhiên, hiện tại engine hoàn toàn bị ràng buộc vào Python runtime:**

```rust
// src/structures.rs — State hiện tại:
use im::HashMap;
pub struct State {
    data: HashMap<String, Arc<PyObject>>,  // ← PyObject: Python interpreter required
    heavy: HashMap<String, Arc<PyObject>>,
    ...
}

// src/engine.rs — Transaction hiện tại:
pub struct Transaction {
    pending_data: Py<PyDict>,              // ← PyDict: GIL required
    shadow_cache: HashMap<usize, (PyObject, PyObject)>, // ← PyObject: deepcopy via Python
    delta_log: Vec<DeltaEntry>,            // ← DeltaEntry.value: PyObject
    ...
}
```

Hệ quả:
- **Không thể chạy Theus engine từ Go, Java, JS, WASM** — không có Python interpreter
- **Không thể expose C ABI** — mọi call phải qua PyO3/GIL
- **CAS và audit phải acquire GIL** — không thể chạy pure Rust concurrent
- **Unit test engine không cần Python** là không thể

**Đây là vấn đề kiến trúc, không phải vấn đề performance.**

---

## 2. Quyết Định

Migrate `State` từ `HashMap<String, Arc<PyObject>>` sang `HashMap<String, Arc<Value>>`, trong đó `Value` là Rust-native enum:

```rust
#[derive(Clone, Debug, PartialEq)]
pub enum Value {
    Null,
    Bool(bool),
    Int(i64),
    Float(f64),
    Str(Arc<str>),
    List(Arc<Vec<Value>>),
    Map(Arc<IndexMap<String, Value>>),
    Bytes(Arc<[u8]>),
    // Escape hatch cho Python objects không convert được — xem §5
    Opaque(Arc<Py<PyAny>>),
}
```

**Boundary model sau migration:**

```
Python process body:
  ctx.domain → to_py(state["domain"])   # 1× Rust→Python conversion, trả plain dict
  process runs on plain Python dict/list — no proxy, no FFI per read
  return StateUpdate(...)

Engine commit:
  from_py(update_value) → Value         # 1× Python→Rust conversion
  CAS(state, version, new_values)       # pure Rust, no GIL
```

Engine core (CAS, delta, zone physics, audit) chạy hoàn toàn trong Rust trên `Value` — không biết Python tồn tại. Python binding chỉ là một trong nhiều bindings có thể có.

---

## 3. Động Lực

### 3.1 Language Independence — Lý Do Chính

Khi engine không còn phụ thuộc `PyObject`, có thể expose nhiều hình thức:

| Interface | Cách thực hiện | Use case |
|---|---|---|
| Python | PyO3 wrapper (giữ nguyên) | Current users |
| C ABI | `extern "C"` functions | Embed vào C/C++ app |
| gRPC service | `tonic` server trên `Value` proto | Polyglot microservice |
| WASM | `wasm-bindgen` trên `Value` | Browser / Edge runtime |
| FFI cho Go/Java | C ABI + language bindings | Enterprise integration |

Theus POP protocol có thể trở thành **runtime-agnostic** — process logic viết bằng bất kỳ ngôn ngữ nào, engine Rust xử lý isolation, CAS, zone.

### 3.2 Correctness — CAS Và Audit Thuần Rust

Hiện tại CAS phải:
1. Acquire GIL
2. So sánh `PyObject` qua Python `__eq__`
3. Apply changes qua `PyDict` API

Với `Value`:
- `Value: PartialEq` — so sánh hoàn toàn trong Rust, không GIL
- CAS có thể chạy trong Rust async context (Tokio) mà không block Python thread
- Audit log có thể được viết sang file/network không cần GIL

### 3.3 Performance — Hệ Quả Tự Nhiên, Không Phải Mục Tiêu

Khi process nhận `to_py(value)` = plain Python dict:
- Reads: native Python dict lookup (~0.07μs), không còn `SupervisorProxy.__getattr__` (3–4 FFI/read)
- Writes: process mutate bản copy local, không ảnh hưởng engine state
- `Arc::clone()` trên `Value` là O(1) — nếu state immutable, clone = atomic counter increment

**Performance là hệ quả của kiến trúc đúng, không phải lý do migrate.**

---

## 4. Thiết Kế Boundary

### 4.1 `from_py` — Python → Value (tại input boundary)

```rust
pub fn from_py(py: Python, obj: &Bound<'_, PyAny>) -> PyResult<Value> {
    if obj.is_none() { return Ok(Value::Null); }
    if let Ok(b) = obj.extract::<bool>() { return Ok(Value::Bool(b)); }
    if let Ok(i) = obj.extract::<i64>() { return Ok(Value::Int(i)); }
    if let Ok(f) = obj.extract::<f64>() { return Ok(Value::Float(f)); }
    if let Ok(s) = obj.extract::<String>() { return Ok(Value::Str(Arc::from(s))); }
    if let Ok(list) = obj.downcast::<PyList>() {
        let items: PyResult<Vec<Value>> = list.iter().map(|x| from_py(py, &x)).collect();
        return Ok(Value::List(Arc::new(items?)));
    }
    if let Ok(dict) = obj.downcast::<PyDict>() {
        let mut map = IndexMap::new();
        for (k, v) in dict.iter() {
            map.insert(k.extract::<String>()?, from_py(py, &v)?);
        }
        return Ok(Value::Map(Arc::new(map)));
    }
    // Không convert được → Opaque (giữ Python object, behavior như hiện tại)
    Ok(Value::Opaque(Arc::new(obj.clone().unbind())))
}
```

### 4.2 `to_py` — Value → Python (tại output boundary, mỗi process execution)

```rust
pub fn to_py(py: Python, val: &Value) -> PyResult<PyObject> {
    match val {
        Value::Null     => Ok(py.None()),
        Value::Bool(b)  => Ok(b.into_py(py)),
        Value::Int(i)   => Ok(i.into_py(py)),
        Value::Float(f) => Ok(f.into_py(py)),
        Value::Str(s)   => Ok(s.as_ref().into_py(py)),
        Value::List(l)  => { /* recursive → PyList */ }
        Value::Map(m)   => { /* recursive → PyDict */ }
        Value::Bytes(b) => Ok(PyBytes::new_bound(py, b).into()),
        Value::Opaque(o) => Ok(o.clone_ref(py)),  // giữ nguyên PyObject
    }
}
```

`to_py` trả về Python object được sở hữu bởi process — có thể mutate tự do, không ảnh hưởng `Value` trong engine.

---

## 5. Escape Hatch: `Opaque` Variant

`Opaque(Arc<Py<PyAny>>)` cho phép bất kỳ Python object nào tồn tại trong state mà không cần conversion. Behavior:

- **`from_py`**: gặp type không nhận dạng được → tạo `Opaque`
- **`to_py`**: trả `Arc::clone()` của PyObject — vẫn cần deepcopy để isolate
- **CAS**: fallback sang Python `__eq__` với GIL
- **Zone Heavy**: tất cả numpy, tensor, custom objects nên khai báo `heavy_*` zone → tự động `Opaque`

`Opaque` là backward-compatible bridge. Mọi field `Opaque` giữ behavior hiện tại (deepcopy, proxy isolation). Không có correctness regression.

---

## 6. Hậu Quả

### 6.1 Positive

- Engine core (`engine.rs`, `conflict.rs`, `audit.rs`, `zones.rs`) không còn `use pyo3` — compilable standalone
- CAS và audit lock-free trong Rust async context
- `Value: Clone` = O(1) với immutable subtrees (Arc shared)
- Python binding giữ nguyên API — users không thấy thay đổi
- Mở đường cho C ABI và polyglot bindings

### 6.2 Negative / Risks

**A. Type coverage — blocker chính:**

`Value` không biểu diễn được một số types Python phổ biến:
- `datetime`, `date`, `time` → cần thêm variant hoặc serialize sang `Str`
- `set`, `frozenset` → cần variant hoặc map thành `List`
- Pydantic `BaseModel`, custom dataclass → fallback `Opaque`
- `numpy.ndarray`, `torch.Tensor` → `Opaque` (nên là `heavy_*` zone)

Nếu >40% state thực tế là `Opaque`, complexity tăng mà benefit không đủ bù.

**B. `to_py` cost ≈ `deepcopy` cost:**

`to_py` là O(n) tree walk + Python object allocation — tương đương deepcopy về complexity. Điểm khác: không cần GIL cho phần Rust tree walk. Với `Value::Opaque`, vẫn cần deepcopy.

**C. Migration scope lớn:**

| Component | Thay đổi |
|---|---|
| `src/structures.rs` | `State`: `Arc<PyObject>` → `Arc<Value>` |
| `src/engine.rs` | `Transaction`: bỏ `shadow_cache`, rewrite commit/CAS |
| `src/proxy.rs` | `SupervisorProxy`: deprecate trong hot path, giữ cho admin/audit |
| `src/delta.rs` | `DeltaEntry.value`: `PyObject` → `Value` |
| `theus/engine.py` | Adapt `execute()` — process nhận plain dict từ `to_py` |
| `theus/theus_core.pyi` | Full stub regen |
| Tests | Verify parity trên toàn bộ suite |

---

## 7. Điều Kiện Để Tiến Hành

Trước khi bắt đầu migration:

1. **Type audit**: Inventory toàn bộ types xuất hiện trong `@process` `inputs`/`outputs` trong codebase và examples. Tính tỉ lệ `Value`-compatible vs `Opaque`-required.
   - **GO**: ≥70% fields là JSON-compatible types
   - **NO-GO**: >40% fields cần `Opaque`

2. **Datetime policy**: Quyết định `datetime` được xử lý thế nào — thêm `Value::DateTime(i64)` (epoch) hay serialize sang `Str` (ISO-8601) hay luôn `Opaque`.

3. **Boundary benchmark**: Đo `to_py(from_py(x))` round-trip vs `deepcopy(x)` trên workload thực tế để xác nhận có win thực.

4. **Phased plan**: Không rewrite toàn bộ một lúc — migrate từng subsystem với feature flag.

---

## 8. Lựa Chọn Đã Bác

### 8A. Transaction Snapshot (Python-only, không migrate Value)

**Ý tưởng:** Giữ `PyObject` state, nhưng snapshot declared inputs khi tx begin bằng `deepcopy`, trả plain dict cho process.

**Lợi ích thực:** Loại bỏ 3–4 FFI/field × N fields → ~3× improvement cho processes đọc nhiều fields.

**Tại sao không đủ:** Giải quyết triệu chứng performance, không giải quyết vấn đề kiến trúc. Engine vẫn bị ràng buộc Python. CAS vẫn cần GIL. Không mở đường cho C ABI hay polyglot.

**Khi nào có thể chọn:** Nếu type audit cho thấy NO-GO cho `Arc<Value>` (>40% `Opaque`), Snapshot là fallback hợp lý với zero risk và zero Rust changes.

### 8B. FrozenDict Promotion

**Tại sao không:** `FrozenDict` vẫn là `PyObject` — không giải quyết Python dependency. Reads vẫn có FFI overhead.

### 8C. redb + Arrow

**Tại sao không:** Write cost không giảm. Read latency tăng (B-tree vs HashMap). Phân tích đầy đủ trong ADR-009.

### 8D. Background Async Shadow Worker

**Ý tưởng:** Worker tạo copy song song, rollback từ shadow nếu CAS fail.

**Tại sao không:** Timing paradox — shadow phải chụp atomic trước mọi mutation, tức là process vẫn phải đợi. Ngoài ra: dirty reads giữa processes; external side effects (outbox, signals) không rollback được. Đề xuất này về bản chất mô tả MVCC — và MVCC yêu cầu state immutable-by-design (`Arc<Value>`), không phải async copy.

---

## 9. Trạng Thái

**PROPOSED — Pending type audit (§7).**

Migration này là điều kiện cần cho Theus trở thành language-independent POP runtime. Không nên thực hiện trước khi type audit xác nhận feasibility.

---

## 10. Liên Kết

- Current State impl: [src/structures.rs](../../../src/structures.rs)
- Current proxy impl: [src/proxy.rs](../../../src/proxy.rs)
- Engine + Transaction: [src/engine.rs](../../../src/engine.rs)
- Technical debt tracking: [Documents/Technical-Debt-v3.0.23.md](../../Technical-Debt-v3.0.23.md)
- Benchmark data: [Documents/Benchmarks/benchmark_report_v3.0.26.md](../Benchmarks/benchmark_report_v3.0.26.md)
