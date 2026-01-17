Dưới đây là **ADR chính thức (Architecture Decision Record)** cho THEUS, viết theo **chuẩn ADR nghiêm túc**, có thể đặt tại:

```
docs/adr/ADR-000X-hybrid-context-zones.md
```

Ngôn ngữ: **English (chuẩn kỹ thuật, phù hợp OSS & Python ecosystem)**
Giọng: **trung lập, quyết định rõ ràng, không marketing**

---

# ADR-000X: Hybrid Context Zones for THEUS Context Management

**Status**: Accepted
**Date**: 2025-XX-XX
**Deciders**: THEUS Core Team
**Technical Area**: Runtime / Context / Determinism
**Language Target**: Python (primary), Rust (future core)

---

## Context

THEUS is a Process-Oriented Programming (POP) engine designed to support:

* deterministic execution
* auditable workflows
* event-driven and safety-aware systems
* semantic correctness over syntactic convenience

At the center of THEUS execution model lies the **Context (`ctx`)**, which is used to:

* transport business state between processes
* coordinate execution via events and commands
* expose runtime and diagnostic metadata

THEUS already defines two orthogonal semantic axes:

1. **Context Layers** (scope & lifetime)

   * Global
   * Domain
   * Local

2. **Semantic Roles**

   * input
   * output
   * side-effect
   * error

However, experience and analysis show that these two axes alone are insufficient to prevent the following systemic risks:

* Context degenerating into global mutable state
* Mixing of business state, coordination signals, and metadata
* Non-deterministic behavior caused by hidden dependencies
* Loss of replayability and audit integrity
* Inability for the engine to enforce semantic safety

A third axis is required to define **engine-level guarantees and enforcement policies** for context entries.

---

## Problem Statement

How can THEUS enforce semantic safety, determinism, and auditability of Context usage **without**:

* introducing excessive verbosity in user code
* causing large-scale breaking changes
* relying on developer discipline or naming conventions alone
* overcomplicating the process contract model

---

## Decision Drivers

* Deterministic replay must remain possible
* Audit logs must reflect meaningful business decisions
* Context misuse must be **detectable and enforceable by the engine**
* Python developers must retain a low-friction API
* The solution must align with THEUS’s non-dualistic POP philosophy

---

## Considered Options

### Option A – Flat Context (Status Quo)

A single, unstructured context object where all keys are treated equally.

**Pros**

* Minimal complexity
* No migration cost
* Simple mental model

**Cons**

* No enforceable semantic boundaries
* High risk of non-determinism
* Audit and replay are unreliable
* Violates safety goals of THEUS

---

### Option B – Explicit Structural Context Zones

Separate context objects such as `ctx.data`, `ctx.signals`, and `ctx.meta`.

**Pros**

* Clear semantic separation
* Strong engine enforcement
* Explicit intent

**Cons**

* High verbosity
* 100% breaking change
* Significant migration cost
* Complex guard and decorator APIs
* Poor adoption risk for Python ecosystem

---

### Option C – Hybrid Context Zones (Selected)

Maintain a **flat user-facing Context API**, while introducing **engine-internal semantic zones** enforced by policy.

Zone classification is inferred by the engine using deterministic rules, rather than relying on developer discipline.

---

## Decision

THEUS adopts **Hybrid Context Zones** as a third, orthogonal axis in its Context model.

Context entries are classified internally by the engine into one of the following zones:

* **Data** – durable business state
* **Signal** – transient coordination events or commands
* **Meta** – runtime observation and diagnostic information

This classification is enforced by the runtime and drives audit, replay, guard, and mutation policies.

---

## Zone Resolution Rules

Zone resolution is performed internally by the engine using the following default rules:

| Key Pattern    | Zone   |
| -------------- | ------ |
| no prefix      | Data   |
| `sig_`, `cmd_` | Signal |
| `meta_`        | Meta   |

**Important invariants**:

* Absence of a prefix implicitly places the entry in the **Data** zone.
* Prefixes do not grant power; they **opt into reduced guarantees**.
* Zone assignment is not user-configurable at runtime.

---

## Zone Enforcement Semantics

### Data Zone

* Versioned and auditable
* Participates in deterministic replay
* May be used in process guards and business decisions
* Mutation requires a valid execution and transaction context

### Signal Zone

* Ephemeral and execution-frame scoped
* Not persisted and not replayed
* Cannot be used as guard input
* Cannot cross execution boundaries

### Meta Zone

* Read-only or restricted for user code
* Excluded from business logic decisions
* Used solely for tracing, diagnostics, and observability

---

## Interaction with Existing Axes

Context Zones are **not** a replacement for existing semantics.

They are applied as a **policy lens** over the existing model:

```
ContextEntry =
  Layer (Global / Domain / Local)
+ SemanticRole (input / output / side-effect / error)
+ Zone (data / signal / meta)
```

Zones define **engine guarantees**, not business meaning.

---

## Consequences

### Positive

* Strong semantic safety without breaking user code
* Deterministic replay becomes enforceable
* Audit logs regain meaning
* Misuse of Context becomes visible and actionable
* Aligns with POP’s emphasis on process contracts and semantics

### Negative

* Increased engine complexity
* Need for violation detection and enforcement logic
* Potential learning curve for advanced users
* Some misuse patterns are allowed but intentionally degraded

---

## Enforcement Strategy

THEUS introduces two enforcement modes:

* **Warn Mode (default)**
  Violations are logged and audited.

* **Strict Mode (opt-in)**
  Violations raise runtime exceptions.

Replay divergence is treated as a **signal of semantic violation**, not as a runtime bug.

---

## Rationale

This decision reflects THEUS’s core philosophy:

> The engine must enforce semantics,
> but the developer should not be burdened with excessive ceremony.

Hybrid Context Zones preserve usability while ensuring that correctness, safety, and determinism are properties of the system — not of developer discipline.

---

## Status

This decision is **Accepted** and serves as the authoritative reference for Context implementation in THEUS.

---

Dưới đây là **bản phân tích & đề xuất kỹ thuật được viết lại TOÀN BỘ**, đã **tái cấu trúc hoàn chỉnh** để **phù hợp tuyệt đối với mô hình THEUS hiện tại** của bạn:

* 3 **Context Layer** (Global / Domain / Local)
* 4 **Semantic Level** (input / output / side-effect / error)
* bổ sung **Context Zones** như **trục policy**, không phải trục cấu trúc

Văn bản này có thể:

* đưa thẳng vào **whitepaper**
* dùng làm **Architecture Decision Record (ADR)**
* hoặc làm **spec nền cho implementer**

---

# THEUS Context Architecture

## Phân tích vấn đề, quyết định thiết kế và phương án kỹ thuật

---

## 1. Bối cảnh và vấn đề cốt lõi

THEUS là một POP engine hướng tới:

* thực thi theo process + contract
* deterministic execution
* audit & replay
* an toàn ngữ nghĩa (semantic safety)

Trong THEUS, **Context (`ctx`)** là trung tâm của mọi tương tác:

* truyền dữ liệu giữa process
* điều phối workflow
* lưu trạng thái nghiệp vụ
* phản ánh tác động phụ và lỗi

Tuy nhiên, **nếu Context không được kiểm soát chặt**, nó có xu hướng:

* thoái hóa thành *global mutable state*
* trộn lẫn data / event / meta
* sinh race condition không trace được
* phá vỡ determinism
* làm audit và replay mất ý nghĩa

**Vấn đề cần giải quyết không phải là “chia Context cho đẹp”**, mà là:

> **Làm sao để bảo vệ ngữ nghĩa của Context một cách engine-enforced,
> trong khi vẫn giữ được tính thực dụng, khả năng tiếp cận và chi phí triển khai hợp lý?**

---

## 2. Mô hình Context hiện tại của THEUS (nền tảng đúng đắn)

### 2.1. Trục 1 – Context Layer (Scope & Lifetime)

THEUS đã chia Context theo **phạm vi sống**:

| Layer  | Phạm vi               | Ý nghĩa                      |
| ------ | --------------------- | ---------------------------- |
| Global | Toàn runtime          | invariant hệ thống, cấu hình |
| Domain | Một domain / workflow | trạng thái nghiệp vụ chia sẻ |
| Local  | Một execution         | trạng thái tạm thời          |

→ Đây là **phân loại theo “ở đâu & sống bao lâu”**

---

### 2.2. Trục 2 – Semantic Level (Vai trò ngữ nghĩa)

THEUS đã định nghĩa **vai trò logic của dữ liệu**:

| Semantic level | Ý nghĩa                     |
| -------------- | --------------------------- |
| input          | dữ liệu đầu vào             |
| output         | kết quả sinh ra             |
| side-effect    | tác động phụ (I/O, command) |
| error          | lỗi / bất thường            |

→ Đây là **phân loại theo “để làm gì”**

---

📌 Hai trục này **độc lập và trực giao**
→ đây là nền rất tốt, **không nên phá**

---

## 3. Khoảng trống còn thiếu

Mặc dù đã có Layer + Semantic, THEUS vẫn còn **một lỗ hổng quan trọng**:

> **Chưa có trục nào định nghĩa “luật bảo đảm” cho dữ liệu**

Câu hỏi chưa được trả lời rõ:

* Cái gì được audit?
* Cái gì được replay?
* Cái gì được dùng làm business decision?
* Cái gì chỉ là tín hiệu thoáng qua?
* Cái gì engine phải cưỡng chế?

Nếu không có trục này:

* mọi enforcement trở nên mơ hồ
* guard yếu
* dev có thể “hack ngữ nghĩa” mà engine không biết

---

## 4. Các phương án thiết kế đã xem xét

### 4.1. Context phẳng (Flat Context)

* Một `ctx`
* Mọi key ngang hàng

❌ Không thể enforce semantics
❌ Không phù hợp với safety / audit

---

### 4.2. Context Zones thuần túy (ctx.data / ctx.signals / ctx.meta)

* Ngữ nghĩa rõ
* Enforcement mạnh

❌ Verbosity cao
❌ 100% breaking change
❌ Migration cost lớn
❌ Guard phức tạp

---

## 5. Quyết định: Hybrid Context Zones (phi nhị nguyên)

### 5.1. Triết lý quyết định

THEUS **không chọn nhị nguyên**:

* không hi sinh kiến trúc vì tiện
* không hi sinh thực tế vì thuần khiết

👉 Chọn **Hybrid**:

* API bề mặt mềm
* Engine lõi cứng

---

## 6. Mô hình Context 3-trục hoàn chỉnh

### Trục 1 – Layer (scope)

* Global / Domain / Local

### Trục 2 – Semantic level

* input / output / side-effect / error

### Trục 3 – Zone (policy & guarantee)

| Zone   | Ý nghĩa             |
| ------ | ------------------- |
| data   | business state      |
| signal | event / command     |
| meta   | runtime observation |

📌 **Zone KHÔNG định nghĩa ý nghĩa**,
nó **định nghĩa luật engine áp dụng**

---

## 7. Cách Hybrid Context Zones hoạt động

### 7.1. API bề mặt cho dev

Dev **vẫn dùng ctx phẳng**:

```python
ctx.user_id = 1
ctx.sig_stop = True
ctx.meta_trace_id = "abc"
```

Không ép:

```python
ctx.data.user_id
```

---

### 7.2. Engine phân loại zone nội bộ

| Prefix       | Zone   |
| ------------ | ------ |
| không prefix | data   |
| sig_, cmd_   | signal |
| meta_        | meta   |

📌 Không prefix **KHÔNG phải tự do**
→ mặc định là `data` (luật nghiêm nhất)

---

## 8. Quyền lực và luật theo Zone

| Thuộc tính        | data | signal        | meta |
| ----------------- | ---- | ------------- | ---- |
| Persist           | ✅    | ❌             | ❌    |
| Replay            | ✅    | ❌             | ⚠️   |
| Guard input       | ✅    | ❌             | ❌    |
| Business decision | ✅    | ⚠️ (ngắn hạn) | ❌    |
| Audit             | ✅    | ❌             | ⚠️   |
| Cross-process     | ✅    | ❌             | ❌    |

---

## 9. Guard, Determinism và Replay

### 9.1. Guard

```python
@process(inputs=["user_id"])
```

Engine:

* resolve `user_id`
* nếu không thuộc `Zone=data` → reject

---

### 9.2. Determinism

Replay chỉ dựa trên:

* initial ctx.data
* sequence event

Signal bị bỏ qua → nếu logic phụ thuộc signal:

* replay mismatch
* lỗi lộ diện

---

## 10. Ánh xạ Layer × Semantic × Zone (ví dụ)

| Layer  | Semantic    | Zone   | Ý nghĩa         |
| ------ | ----------- | ------ | --------------- |
| Local  | input       | data   | input nghiệp vụ |
| Domain | side-effect | signal | command         |
| Local  | meta        | meta   | trace           |
| Global | error       | data   | lỗi hệ thống    |

---

## 11. Enforcement & Violation Handling

### Mode

* Warn (default)
* Strict (opt-in)

### Vi phạm bị phát hiện:

* decision phụ thuộc signal
* ghi meta trái phép
* data mutation không guard

---

## 12. Cạm bẫy và cách xử lý

### Dev bỏ prefix

→ tất cả thành data → luật nghiêm → tự điều chỉnh

### Dev lạm dụng signal

→ mất replay / audit → failure visible

### Ambiguity

→ zone là **luật vận hành**, không phải tranh luận triết học

---

## 13. Kết luận

Hybrid Context Zones:

* không phá kiến trúc hiện có
* bổ sung đúng trục còn thiếu
* enforce semantics ở mức engine
* giữ được tính thực dụng
* phản ánh đúng tinh thần POP / THEUS

> **THEUS không ép dev viết đúng,
> mà làm cho viết sai trở nên không có lợi.**

---
