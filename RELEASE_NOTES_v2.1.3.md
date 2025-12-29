# Theus V2.1.3 Release Notes

## 🔧 Patch Fixes

### 🛡️ Audit & Stability
- Verified `ContextGuard` behavior with deep nested structures (Parasitic Sandbox verification).
- **Fixed:** Audit Engine path resolution now supports hybrid traversal of Dictionary keys and Object methods (e.g., `domain.tensors.weights.mean()`), enabling validation of Numpy/Tensor statistics stored in internal maps.