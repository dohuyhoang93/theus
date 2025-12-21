# Chapter 10: Dual-Thresholds - System Tolerance

Real systems always have Noise. Theus v2 allows you to configure "Tolerance" via Threshold mechanism.

## 1. How Threshold Works
Each Rule has its own Counter in `AuditTracker`.
- **min_threshold:** Threshold to start Warning (Yellow).
- **max_threshold:** Threshold to trigger Punishment (Red Action - S/A/B).

**Example:** `max_threshold: 3`.
- 1st Error: Allow (or Warn if >= min).
- 2nd Error: Allow.
- 3rd Error: **BOOM!** Trigger Level (e.g., Block).
- After "BOOM", counter resets to 0.

## 2. Important Note: Error Accumulation
By default in Theus v2 codebase, counter **DOES NOT RESET ON SUCCESS**.
This is a feature, not a bug.
- It helps detect Flaky systems.
- If you error once every 10 runs -> After 30 runs, you get Blocked (accumulated 3 errors).
- Want reset? Restart Engine or reconfigure Tracker (advanced feature).

## 3. Real World Applications
- **Rate Limiting:** Allow speed violation 5 times before blocking IP.
- **Sensor Glitch:** Temp sensor sometimes jumps 1 value. Don't stop machine immediately. Wait for 3 consecutive wrong values.

---
**Exercise:**
Configure `max_threshold: 3` for rule `price >= 0`.
Try calling `add_product` with negative price consecutively.
Observe: 1st OK (Warn). 2nd OK (Warn). 3rd -> Exception!
Then call 4th time -> OK (Warn) again because counter reset.
