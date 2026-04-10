# SEVERITY THRESHOLD SYSTEM - ROOT CAUSE ANALYSIS

## 🔍 FINDINGS

### Current System Architecture

**TWO SEPARATE FILTER CONCEPTS:**

1. **Risk Threshold (Slider 0→1)**
   - Controls: `product.riskProbability >= state.threshold`
   - Current default: 0.7
   - Expected behavior: Only shows products with risk probability >= selected value

2. **Severity Category (Dropdown)**
   - Controls: `product.severity === state.severity` (if not "All")
   - Options: All, High, Medium, Low
   - Categories are HARDCODED in backend:
     - High: risk_score >= 0.7
     - Medium: 0.4 <= risk_score < 0.7
     - Low: risk_score < 0.4

### The Problem

**Issue #1: Confusing UI Labels**
- "Risk Threshold" (slider) doesn't directly cause severity label changes
- "Severity" (dropdown) filters by category, NOT by threshold adjustment
- Users might think moving the threshold slider should change product severity categories

**Issue #2: Hardcoded Backend Severity**
- Severity categories are STATIC and determined DURING data transformation
- Backend has NO KNOWLEDGE of user's threshold slider preference
- Slider only filters WHICH products appear, not their severity labels

**Issue #3: Dual AND Logic in Filtering**
```javascript
return matchesProduct && matchesDate && matchesSeverity && matchesThreshold;
```
- Both severity AND threshold must match (AND logic)
- When severity="All": Works correctly (only threshold matters)
- When severity="High": Restricts to High category PLUS threshold >= value
- This can hide the threshold effect if user is filtering by a specific severity

### Test Data Distribution

```
Drift Frame:      0.44 → Low
Cove Kettle:      0.49 → Low
Vale Chair:       0.58 → Low
Harbor Lamp:      0.69 → Medium
Summit Bottle:    0.63 → Medium
North Mug:        0.74 → Medium (borderline High)
Pulse Earbuds:    0.86 → High
Atlas Desk:       0.92 → High
```

**Expected behavior with default threshold 0.7:**
- **Severity="All", Threshold=0.7** → 3 products (Atlas, Pulse, North)
- **Severity="High", Threshold=0.9** → 1 product (Atlas only)
- **Severity="All", Threshold=0.5** → 7 products (all except Drift)

---

## ✅ FIXES REQUIRED

### FIX #1: Improve UI Clarity & Debugging
- Add debug panel showing current filter state
- Show which filters are actually applied
- Display filtered product count vs total
- Highlight the active threshold value

### FIX #2: Add Event Listeners for Real-Time Filtering ✓ DONE
- Risk threshold input → auto-apply filters
- Severity dropdown → auto-apply filters
- Date changes → auto-apply filters

### FIX #3: Validate Filter Logic
- Ensure threshold comparison is correct (>= not <)
- Verify AND logic is intentional
- Test with edge cases (threshold=0, threshold=1, severity="All")

### FIX #4: Backend Enhancement (OPTIONAL)
- Consider making severity classification dynamic based on received threshold
- Or keep static and ensure frontend clearly communicates this to users

---

## 📊 VALIDATION MATRIX

| Severity | Threshold | Products Expected | Test Case |
|----------|-----------|-------------------|-----------|
| All      | 0.0       | 8 (all)          | All data visible |
| All      | 0.5       | 7 (exclude Drift) | Mid-range threshold |
| All      | 0.7       | 3 (Atlas, Pulse, North) | Default |
| All      | 0.9       | 1 (Atlas only)   | High threshold |
| High     | 0.7       | 2 (Atlas, Pulse) | Category + threshold |
| Medium   | 0.7       | 3 (N. Mug, Harbor, Summit) | Should show >= 0.7 AND Medium category |
| Low      | 0.5       | 3 (Vale, Cove, Drift) | Should show Low category |

---

## 🔧 IMPLEMENTATION STATUS

- ✅ Event listeners added for real-time filtering
- ⏳ Debug UI needs enhancement
- ⏳ Filter logic validation needed
- ⏳ Backend severity classification review needed

