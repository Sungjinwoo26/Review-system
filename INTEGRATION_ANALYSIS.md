# 🔍 INTEGRATION ANALYSIS: ML Pipeline + Grok LLM

## STEP 1: IDENTIFY EXISTING ENTRY POINTS

---

### 📊 **ML PIPELINE ENTRY POINTS**

#### **1. Input → ML Processing**

**Location**: `app.py` > `apply_ml_predictions()` (line 837)

```python
def apply_ml_predictions(aggregated_df: pd.DataFrame) -> pd.DataFrame:
    """
    Receives: Product-level aggregated DataFrame
    Returns: Same DataFrame with ML columns added
    """
```

**Input Data Structure**:
```python
aggregated_df = DataFrame with columns:
  - product (str): Product name/ID
  - total_reviews (int)
  - avg_rating (float)
  - negative_ratio (float)
  - final_score (float)  ← Used for risk labeling
  - total_revenue_at_risk (float)
  - [... 11 feature columns prepared by features_ml.py]
```

**Output Data Structure**:
```python
aggregated_df = Same DataFrame PLUS:
  - risk_probability (float): 0-1, ML model output
  - risk_category (str): 'Low', 'Medium', 'High'
  - high_risk_predicted (int): 0 or 1
```

---

#### **2. ML Processing Chain**

**Step 1**: Feature Preparation
```python
from processing.ml.features_ml import prepare_ml_features
ml_df, features = prepare_ml_features(aggregated_df)
# Returns: 11 computed features (impact_per_review, severity_impact, etc.)
```

**Step 2**: Model Training
```python
from processing.ml.train import train_risk_model
model_dict = train_risk_model(ml_df, features, quantile=0.75)
# Returns: {model, scaler, features, threshold, training_stats}
```

**Step 3**: Risk Prediction
```python
from processing.ml.predict import predict_risk
predictions_df = predict_risk(model_dict, ml_df)
# Returns: ml_df PLUS risk_probability, risk_category, high_risk_predicted
```

---

#### **3. Dashboard Connection**

**Location**: `app.py` > `main()` (line 1116-1135)

```python
# After filtering:
filtered_agg = aggregate_to_products(filtered_df)

# **CURRENT OUTPUT LOCATION**:
# ML predictions available in: filtered_agg.columns
#   - risk_probability
#   - risk_category  
#   - high_risk_predicted

# Rendered in dashboard sections:
#   1. render_enhanced_kpis() - Shows "High Risk Products" count
#   2. render_table() - Shows risk_probability and risk_category for each product
#   3. render_ml_insights() - Shows portfolio risk metrics
```

---

### ❓ **GROK LLM ENTRY POINTS**

**STATUS**: ❌ NOT FOUND IN CODEBASE

No Grok/LLM integration currently exists. Searched for:
- `grok`, `Grok`, `GROK`
- `llm_`, `generate_insights`, `xai`
- LLM API clients, prompt builders
- Insight generation functions

**Result**: Only reference is in `test_ml_integrity.py` line 84:
```python
print("  • Ready for Grok/LLM integration (as separate layer)")
```

---

## STEP 2: CREATE INTEGRATION LAYER (CONCEPTUAL PLAN)

### **Option A: Grok Already Exists (User Provides)**

If you have Grok code, I need:
1. **Grok function signature**: `generate_insights(products_df, processed_reviews_df) → insights_dict`
2. **Input expectations**: What columns/format does Grok need?
3. **Output format**: What does Grok return? (JSON, Dict, Text, etc.)
4. **Where is it**: File path to Grok module

---

### **Option B: Create Grok LLM Module** (RECOMMENDED)

I can create a NEW service module:

```
services/
├── llm_insights.py  ← NEW FILE
│   ├── generate_product_insights()      # Insight generation per product
│   ├── generate_portfolio_summary()     # Overall portfolio insights
│   ├── generate_risk_recommendations()  # ML-based risk recommendations
│   └── format_grok_prompt()             # Prompt builder
```

**Integration Architecture**:

```
Data Flow:
  
  aggregated_df (ML outputs)
      ↓
  [EXISTING: risk_probability, risk_category]
      ↓
  services/llm_insights.generate_product_insights()  ← NEW LAYER
      ↓
  LLM Insights (text summaries, recommendations)
      ↓
  Dashboard renders both:
      - ML metrics (quantitative)
      - LLM insights (qualitative)
```

---

## 🤔 NEXT QUESTION FOR YOU

**Before I proceed, please answer:**

### Q1: Do you have Grok code already?
- [ ] **Yes** → Provide the code/file path
- [ ] **No** → Create it for me

### Q2: Grok Integration Type?
- [ ] **API-based** (call external Grok API)
- [ ] **Local** (library installed in venv)
- [ ] **Not sure**

### Q3: What insights should Grok generate?
- [ ] Product-level insights (per product)
- [ ] Portfolio-level summary (all products)
- [ ] Risk recommendations (highest-risk products)
- [ ] All of the above

### Q4: Where should Grok output appear in dashboard?
- [ ] New section below ML metrics
- [ ] Side panel
- [ ] Replace some existing section
- [ ] Not sure

---

**Awaiting your answers to proceed with the integration.**

