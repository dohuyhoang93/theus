# Chương 13: Hệ sinh thái & Công cụ (Theus Ecosystem)

---

## 13.1. Theus CLI (`theus`)

Theus không chỉ là thư viện, nó là một **Framework Agentic** hoàn chỉnh.
Trung tâm của hệ sinh thái là lệnh `theus` - công cụ giúp bạn khởi tạo, vận hành và kiểm tra Agent.

### Các lệnh phổ biến:
```bash
# Khởi tạo dự án chuẩn
py -m theus.cli init [project_name]

# Quét code để sinh file audit recipe
py -m theus.cli audit gen-spec

# Inspect process audit rules
py -m theus.cli audit inspect [process_name]

# Sinh file Context Schema từ Python dataclass
py -m theus.cli schema gen

# Chạy POP Linter kiểm tra code
py -m theus.cli check [path]
```

---

## 13.2. Thành phần chính (v3.0)

| Component | Mô tả | Backend |
|:----------|:------|:--------|
| **TheusEngine** | Core engine | Rust |
| **WorkflowEngine** | Flux DSL executor | Rust |
| **SignalHub** | Event system | Tokio |
| **AuditSystem** | Rule enforcement | Rust |
| **ContextGuard** | Zero-trust memory | Rust |

---

## 13.3. Tiện ích mở rộng (Theus Extensions)

Theus được thiết kế để mở rộng (Extensible). Cộng đồng có thể đóng góp các "Process Pack".

### Adapter Patterns
Tuy Theus Core không tích hợp sẵn các Adapter cụ thể (để giữ kernel nhẹ), chúng tôi cung cấp các **Template & Interface** chuẩn để bạn dễ dàng tích hợp:
*   **API Wrapper:** Pattern để bọc `requests` hoặc `httpx`.
*   **Database:** Pattern để bọc `SQLAlchemy` hoặc `Redis`.
*   **LLM:** Pattern để integrate với OpenAI, Anthropic, etc.

### Community Hub (Future Vision)
Trong tương lai, chúng tôi hướng tới việc đóng gói sẵn các module này:
```bash
pip install theus-opencv-adapter
pip install theus-llm-adapter
```

---

## 13.4. Yêu cầu hệ thống (v3.0)

| Requirement | Minimum | Recommended |
|:------------|:--------|:------------|
| Python | 3.14+ | 3.14.1+ |
| Rust | 1.70+ (build only) | 1.75+ |
| OS | Windows/Linux/macOS | - |

> **Lưu ý:** Python 3.14+ yêu cầu cho Sub-interpreter support.

---

## 13.5. Tầm nhìn: From Ops to No-Code

Lộ trình phát triển của Theus:
1.  **Giai đoạn 1 (Current):** Python SDK, Rust Core, CLI Tools.
2.  **Giai đoạn 2 (Visual Editor):** UI kéo thả Workflow cho Non-tech user.
3.  **Giai đoạn 3 (AI Architect):** *"Theus, hãy tạo workflow nhận diện khách hàng VIP"*, và AI sẽ tự viết YAML + Python cho bạn.

Theus chính là nền tảng (Foundation) vững chắc để xây dựng những giấc mơ đó.
