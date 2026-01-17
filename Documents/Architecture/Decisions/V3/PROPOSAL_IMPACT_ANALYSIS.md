# Proposal Impact Analysis: Theus v3.0 Candidates
**Date:** 2026-01-15
**Purpose:** Deep evaluation of technical complexity and trade-offs for proposed architectural changes.

---

# [ENGLISH] Trade-off Matrix

## 1. Zero-Copy Immutable Models
*Replace Recursive Shadowing with Immutable Data Structures (Pydantic frozen).*

| Aspect | Rating | Analysis |
| :--- | :---: | :--- |
| **Complexity** | **High (8/10)** | **User Burden:** Devs must unlearn `obj.x = 1` and learn `obj = obj.copy(update={x:1})`. Requires rewriting all legacy processes. <br> **Framework:** Simple. Just stop intercepting `__setattr__`. |
| **Positive Impact** | **Massive** | **Performance:** O(1) Reads. No more defensive copying. <br> **Safety:** Mathematical certainty of state history. |
| **Negative Impact** | **Velocity** | "Developer Friction". Writing immutable code in Python is verbose and annoying compared to standard OOP. |

## 2. Hierarchical Write Scopes
*Allow `outputs=["domain.users.*"]` instead of just `["domain"]`.*

| Aspect | Rating | Analysis |
| :--- | :---: | :--- |
| **Complexity** | **Low (3/10)** | **Framework:** Rust `starts_with` string matching is trivial and fast. <br> **User:** Zero learning curve. |
| **Positive Impact** | **High** | **Security:** Eliminates the "Wildcard Trap". Encourages granular permissions without tedious listing. |
| **Negative Impact** | **None** | Pure win. Minimal runtime overhead (string comparison). |

## 3. Lifecycle & Capability Enforcers
*Auto-delete `Local` context; Static Analysis for IO bans.*

| Aspect | Rating | Analysis |
| :--- | :---: | :--- |
| **Complexity** | **Medium (5/10)** | **Framework:** `del ctx.local` is easy. <br> **Tooling:** Writing a robust AST Linter to detect IO imports is tricky (Python dynamic imports are hard to catch statically). |
| **Positive Impact** | **Medium** | **Cleanliness:** Prevents memory leaks in Local context. <br> **Honesty:** "Data" processes actually become pure (mostly). |
| **Negative Impact** | **False Security** | Smart devs can always bypass static analysis (`importlib.import_module(...)`). It's a seatbelt, not a cage. |

## 4. Transactional Outbox
*Flush IO only after RAM Commit.*

| Aspect | Rating | Analysis |
| :--- | :---: | :--- |
| **Complexity** | **Medium (6/10)** | **Framework:** Requires a new `PostCommit` hook and an `Outbox` queue in Context. <br> **User:** Must split logic: "Decide what to write" (Process) vs "Actually write it" (System/Outbox Worker). |
| **Positive Impact** | **Critical** | **Consistency:** Eliminates "Ghost Writes" on power failure. Essential for FinTech/Audit apps. |
| **Negative Impact** | **Latency** | DB writes happen *after* process logic returns. UI might imply "Done" before DB confirms. |

## 5. Hybrid Schema
*Typed Domain + Dynamic Scratchpad.*

| Aspect | Rating | Analysis |
| :--- | :---: | :--- |
| **Complexity** | **Medium (4/10)** | **Framework:** Dual-mode serialization logic. <br> **User:** Must verify "Is this experimental?" before choosing where to store data. |
| **Positive Impact** | **High** | **Stability:** Keeps Production history clean. Enables rapid AI prototyping without crashing the persistence layer. |
| **Negative Impact** | **Fragmentation** | Data might get scattered between "Strict Config" and "Loose Scratchpad". |

## 6. Async/Tokio Integration (The "Big One")
*Rewrite Core to support `async def` and `await`.*

| Aspect | Rating | Analysis |
| :--- | :---: | :--- |
| **Complexity** | **Extreme (10/10)** | **Framework:** Total rewrite of `engine.rs` to use `pyo3-asyncio`. Must manage Event Loop bridging. <br> **Migration:** All synchronous processes become blocking hazards. |
| **Positive Impact** | **Transformative** | **Concurrency:** Enables high-throughput IO orchestration (Web Scrapers, API Gateways). |
| **Negative Impact** | **Instability** | "Async coloring" problem. Mixing Sync and Async code is notorious for deadlocks and bugs. |

---

# [VIETNAMESE] Ma trận Đánh đổi (Trade-off Matrix)

## 1. Zero-Copy Immutable Models (Model Bất biến)
*Thay thế Shadowing đệ quy bằng Model bất biến (Pydantic frozen).*

| Khía cạnh | Điểm số | Phân tích |
| :--- | :---: | :--- |
| **Độ khó (Complexity)** | **Cao (8/10)** | **Người dùng:** Dev phải "học lại từ đầu". Bỏ thói quen `x=1`, chuyển sang `copy(update={x=1})`. <br> **Framework:** Dễ. Chỉ cần tắt tính năng chặn `__setattr__`. |
| **Tác động tích cực** | **Khổng lồ** | **Hiệu năng:** Đọc dữ liệu nhanh tức thì (O(1)). Không còn copy ngầm. <br> **An toàn:** Lịch sử trạng thái được đảm bảo toán học. |
| **Tác động tiêu cực** | **Tốc độ Dev** | Code bất biến trong Python khá dài dòng và gây ức chế (so với Rust/Scala). |

## 2. Hierarchical Write Scopes (Ghi phân cấp)
*Cho phép `outputs=["domain.users.*"]`.*

| Khía cạnh | Điểm số | Phân tích |
| :--- | :---: | :--- |
| **Độ khó** | **Thấp (3/10)** | **Framework:** So khớp chuỗi `starts_with` trong Rust là chuyện nhỏ. |
| **Tác động tích cực** | **Cao** | **Bảo mật:** Loại bỏ bẫy "Wildcard". Khuyến khích phân quyền chi tiết mà không gây nản lòng. |
| **Tác động tiêu cực** | **Không** | Logic này gần như free về mặt chi phí. |

## 3. Lifecycle & Capability Enforcers (Trấn áp Vòng đời)
*Tự xóa `Local`; Dùng Static Analysis cấm IO.*

| Khía cạnh | Điểm số | Phân tích |
| :--- | :---: | :--- |
| **Độ khó** | **Trung bình (5/10)** | **Framework:** Xóa `local` thì dễ. <br> **Tooling:** Viết Linter quét cây AST để bắt import lậu là khó (Python quá động). |
| **Tác động tích cực** | **Trung bình** | **Sạch sẽ:** Tránh rác bộ nhớ. <br> **Trung thực:** Process được dán nhãn "Data" sẽ thực sự thuần khiết (tương đối). |
| **Tác động tiêu cực** | **An toàn giả** | Cao thủ vẫn lách luật được (`importlib`). Đây chỉ là dây an toàn, không phải lồng sắt. |

## 4. Transactional Outbox (Hộp thư đi)
*Chỉ ghi IO sau khi Commit RAM.*

| Khía cạnh | Điểm số | Phân tích |
| :--- | :---: | :--- |
| **Độ khó** | **Trung bình (6/10)** | **Framework:** Cần thêm hook `PostCommit` và hàng đợi `Outbox`. <br> **Người dùng:** Phải tách tư duy: "Quyết định ghi" vs "Thực thi ghi". |
| **Tác động tích cực** | **Thiết yếu** | **Nhất quán:** Loại bỏ "Ghi ma" khi mất điện. Cần thiết cho ứng dụng tài chính/Audit. |
| **Tác động tiêu cực** | **Độ trễ** | Ghi DB xảy ra *sau* khi logic process kết thúc. UI có thể báo "Xong" trước khi DB thực sự có dữ liệu. |

## 5. Hybrid Schema (Schema Lai)
*Domain chặt chẽ + Scratchpad thả lỏng.*

| Khía cạnh | Điểm số | Phân tích |
| :--- | :---: | :--- |
| **Độ khó** | **Trung bình (4/10)** | **Framework:** Logic serialize 2 chế độ. |
| **Tác động tích cực** | **Cao** | **Ổn định:** Giữ lịch sử Production sạch đẹp. Cho phép AI quậy phá trong vùng riêng mà không làm sập hệ thống. |
| **Tác động tiêu cực** | **Phân mảnh** | Dữ liệu bị xé lẻ giữa 2 vùng. Code xử lý có thể rối rắm. |

## 6. Async/Tokio Integration (Tích hợp Async - "Trùm cuối")
*Viết lại Core để hỗ trợ `async def`.*

| Khía cạnh | Điểm số | Phân tích |
| :--- | :---: | :--- |
| **Độ khó** | **Cực đại (10/10)** | **Framework:** Đập đi xây lại `engine.rs` dùng `pyo3-asyncio`. Quản lý cầu nối Event Loop cực khó. <br> **Di trú:** Code cũ (đồng bộ) sẽ trở thành cục tạ chặn luồng (blocking hazards). |
| **Tác động tích cực** | **Cách mạng** | **Concurrency:** Mở khóa khả năng điều phối IO cường độ cao (Crawl web, API Gateway). |
| **Tác động tiêu cực** | **Bất ổn** | Bài toán "Async coloring" (Pha trộn Sync/Async) là ác mộng debug. |
