# Tổng quan Theus V2.1 (Industrial Agent OS)

## 1. Cấu trúc Dự án (Project Structure)
Gói `theus` được tổ chức theo kiến trúc Microkernel phân lớp:

```
theus/
├── context.py       # Dữ liệu (Pydantic V2)
├── zones.py         # SAFETY: Context Zones (Data, Signal, Meta)
├── contracts.py     # Hợp đồng (@process decorator)
├── engine.py        # KERNEL: POPEngine (Audit, Atomic execution)
├── locks.py         # SAFETY: LockManager (Mutex + Permission)
├── cli.py           # TOOLING: CLI (init, schema gen, audit gen)
├── interfaces.py    # CONTRACTS: IEngine, IScheduler...
└── orchestrator/    # ORCHESTRATOR LAYER (New in V2.1)
    ├── bus.py       # SignalBus (Queue an toàn)
    ├── executor.py  # ThreadExecutor (ThreadPool)
    ├── fsm.py       # StateMachine Logic
    └── manager.py   # WorkflowManager (Nhạc trưởng)
```

## 2. Luồng Hoạt động (Data Flow) - Cơ chế "Reactive"
Theus V2.1 hoạt động theo mô hình **Sự kiện (Event-Driven)**:

1.  **TRIGGER:** GUI/Main Thread gửi tín hiệu (ví dụ: `"CMD_SCAN"`) vào `SignalBus`.
2.  **DECIDE:** `WorkflowManager` (chạy vòng lặp) nhận tín hiệu, hỏi `FSM` xem trạng thái hiện tại (ví dụ: `IDLE`) gặp tín hiệu này thì làm gì? -> FSM trả về Hành động (ví dụ: `"p_scan"`).
3.  **EXECUTE:** `WorkflowManager` ném `"p_scan"` cho `ThreadExecutor`.
4.  **RUN:** `ThreadExecutor` chạy `POPEngine.execute("p_scan")` trên luồng phụ (Background Thread).
    *   *Tại đây:* Audit Input -> Lock Mutex -> Chạy Logic -> Audit Output -> Commit Transaction -> Unlock.
5.  **FEEDBACK:** Process chạy xong, gửi tín hiệu `"EVT_DONE"` ngược lại `SignalBus` để GUI cập nhật.

## 3. Các Tính năng Chính (Key Features)

| Tính năng | Mô tả | Lợi ích |
| :--- | :--- | :--- |
| **Hybrid Context** | Phân chia dữ liệu thành 3 vùng: Data (lưu), Signal (reset), Meta (log). | Chống "Context Drift", quản lý trạng thái sạch sẽ. |
| **Microkernel** | Tách biệt Engine (kỹ thuật) và Orchestrator (nghiệp vụ). | Dễ mở rộng, dễ test, code gọn gàng. |
| **Non-Blocking** | Sử dụng `ThreadPool` để xử lý tác vụ nặng. | **Không bao giờ đơ GUI**. |
| **State Machine** | Quản lý workflow bằng đồ thị trạng thái (YAML). | Tránh "If/Else Spaghetti" trong code điều khiển. |
| **Audit Strict** | Kiểm tra Input/Output ngay cả trong Thread phụ. | Đảm bảo an toàn dữ liệu 100% mọi lúc. |
| **Mutex Lock** | Cơ chế khóa Thread-safe. | Ngăn chặn Race Condition (xung đột luồng). |
